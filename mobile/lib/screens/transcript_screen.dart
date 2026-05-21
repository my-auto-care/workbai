import 'dart:convert';
import 'dart:io';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:image_picker/image_picker.dart';
import 'package:http/http.dart' as http;
import 'package:speech_to_text/speech_to_text.dart' as stt;
import '../services/api_service.dart';
import 'session_screen.dart';

// A single segment of the transcript — either text or a photo anchor
class _TranscriptSegment {
  final String? text;        // null if this is a photo segment
  final String? photoS3Key;  // null if this is a text segment
  final String? photoLocalPath;
  final DateTime timestamp;
  bool isPhotoUploading;

  _TranscriptSegment.text(this.text)
      : photoS3Key = null,
        photoLocalPath = null,
        timestamp = DateTime.now(),
        isPhotoUploading = false;

  _TranscriptSegment.photo({this.photoLocalPath, this.photoS3Key})
      : text = null,
        timestamp = DateTime.now(),
        isPhotoUploading = photoS3Key == null;
}

enum _RecordState { idle, listening, paused, completing, done, error }

class TranscriptScreen extends StatefulWidget {
  final String sessionId;
  const TranscriptScreen({super.key, required this.sessionId});
  @override
  State<TranscriptScreen> createState() => _TranscriptScreenState();
}

class _TranscriptScreenState extends State<TranscriptScreen> {
  final stt.SpeechToText _speech = stt.SpeechToText();
  final ScrollController _scrollCtrl = ScrollController();

  _RecordState _state = _RecordState.idle;
  bool _speechAvailable = false;
  String? _error;

  final List<_TranscriptSegment> _segments = [];
  String _liveText = ''; // partial / in-progress text from STT

  @override
  void initState() {
    super.initState();
    _initSpeech();
  }

  Future<void> _initSpeech() async {
    _speechAvailable = await _speech.initialize(
      onStatus: _onSpeechStatus,
      onError: (e) => setState(() { _error = e.errorMsg; _state = _RecordState.error; }),
    );
    setState(() {});
    if (_speechAvailable) _startListening();
  }

  void _onSpeechStatus(String status) {
    if (status == 'done' || status == 'notListening') {
      // Commit live text to segments if any
      if (_liveText.trim().isNotEmpty) {
        setState(() {
          _segments.add(_TranscriptSegment.text(_liveText.trim()));
          _liveText = '';
        });
      }
      // Auto-restart unless paused/completing
      if (_state == _RecordState.listening) {
        _startListening();
      }
    }
  }

  Future<void> _startListening() async {
    if (!_speechAvailable) return;
    setState(() => _state = _RecordState.listening);
    await _speech.listen(
      onResult: (result) {
        setState(() => _liveText = result.recognizedWords);
        // Check for photo trigger phrase
        final words = result.recognizedWords.toLowerCase();
        if (result.finalResult) {
          if (_containsPhotoTrigger(words)) {
            // Strip the trigger phrase from transcript
            final cleaned = _stripPhotoTrigger(result.recognizedWords);
            if (cleaned.trim().isNotEmpty) {
              _segments.add(_TranscriptSegment.text(cleaned.trim()));
            }
            _liveText = '';
            _triggerPhoto();
          } else {
            _segments.add(_TranscriptSegment.text(result.recognizedWords.trim()));
            _liveText = '';
          }
          _scrollToBottom();
        }
      },
      listenFor: const Duration(minutes: 10),
      pauseFor: const Duration(seconds: 4),
      partialResults: true,
      localeId: 'en_US',
      cancelOnError: false,
    );
  }

  bool _containsPhotoTrigger(String words) {
    const triggers = ['insert photo', 'take photo', 'add photo', 'photo here', 'take a photo', 'insert a photo'];
    return triggers.any((t) => words.contains(t));
  }

  String _stripPhotoTrigger(String text) {
    const triggers = ['insert photo', 'take photo', 'add photo', 'photo here', 'take a photo', 'insert a photo'];
    var result = text;
    for (final t in triggers) {
      result = result.replaceAll(RegExp(t, caseSensitive: false), '').trim();
    }
    return result;
  }

  Future<void> _pauseListening() async {
    await _speech.stop();
    setState(() => _state = _RecordState.paused);
  }

  Future<void> _resumeListening() async {
    await _startListening();
  }

  Future<void> _triggerPhoto() async {
    HapticFeedback.mediumImpact();
    // Pause listening while camera is open
    await _speech.stop();

    final picker = ImagePicker();
    final XFile? photo = await picker.pickImage(source: ImageSource.camera, imageQuality: 80);

    if (photo == null) {
      // Cancelled — resume
      if (_state == _RecordState.listening) _startListening();
      return;
    }

    // Insert a photo placeholder segment
    final seg = _TranscriptSegment.photo(photoLocalPath: photo.path);
    setState(() {
      _segments.add(seg);
      _scrollToBottom();
    });

    // Upload in background
    _uploadPhoto(photo, seg);

    // Resume listening
    if (_state == _RecordState.listening) _startListening();
  }

  Future<void> _uploadPhoto(XFile photo, _TranscriptSegment seg) async {
    try {
      final uploadData = await ApiService().getUploadUrl(
        sessionId: widget.sessionId,
        filename: 'transcript_${DateTime.now().millisecondsSinceEpoch}.jpg',
      );
      final uploadUrl = uploadData['upload_url'] as String;
      final s3Key = uploadData['s3_key'] as String;
      final bytes = await File(photo.path).readAsBytes();
      final resp = await http.put(
        Uri.parse(uploadUrl),
        headers: {'Content-Type': 'image/jpeg'},
        body: bytes,
      );
      if (resp.statusCode == 200 || resp.statusCode == 204) {
        await ApiService().attachMedia(sessionId: widget.sessionId, s3Key: s3Key);
        setState(() {
          seg.isPhotoUploading = false;
          // Store s3Key reference in segment
        });
        HapticFeedback.lightImpact();
      }
    } catch (e) {
      setState(() => seg.isPhotoUploading = false);
    }
  }

  void _scrollToBottom() {
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (_scrollCtrl.hasClients) {
        _scrollCtrl.animateTo(
          _scrollCtrl.position.maxScrollExtent,
          duration: const Duration(milliseconds: 200),
          curve: Curves.easeOut,
        );
      }
    });
  }

  Future<void> _complete() async {
    await _speech.stop();
    setState(() => _state = _RecordState.completing);

    // Save full transcript as a single finding
    final fullText = _segments
        .where((s) => s.text != null)
        .map((s) => s.text!)
        .join(' ');

    try {
      await ApiService().saveTranscriptFinding(
        sessionId: widget.sessionId,
        transcript: fullText,
      );
      await ApiService().completeSession(widget.sessionId);
      setState(() => _state = _RecordState.done);
      if (mounted) {
        await Future.delayed(const Duration(seconds: 1));
        Navigator.pushReplacement(context,
            MaterialPageRoute(builder: (_) => SessionScreen(sessionId: widget.sessionId)));
      }
    } catch (e) {
      setState(() { _error = e.toString(); _state = _RecordState.error; });
    }
  }

  @override
  void dispose() {
    _speech.stop();
    _scrollCtrl.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final isLive = _state == _RecordState.listening;
    final isPaused = _state == _RecordState.paused;

    return Scaffold(
      backgroundColor: const Color(0xFF0A0A0F),
      appBar: AppBar(
        backgroundColor: const Color(0xFF111827),
        title: const Text('Transcript Mode', style: TextStyle(color: Colors.white)),
        iconTheme: const IconThemeData(color: Colors.white),
        automaticallyImplyLeading: false,
        actions: [
          // Camera button always visible in app bar
          IconButton(
            icon: const Icon(Icons.camera_alt, color: Color(0xFF10B981)),
            tooltip: 'Insert Photo',
            onPressed: _triggerPhoto,
          ),
        ],
      ),
      body: SafeArea(
        child: Column(children: [

          // Status bar
          Container(
            width: double.infinity,
            padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
            color: const Color(0xFF111827),
            child: Row(children: [
              // Recording indicator
              if (isLive) ...[
                Container(width: 8, height: 8,
                    decoration: const BoxDecoration(color: Color(0xFF10B981), shape: BoxShape.circle)),
                const SizedBox(width: 8),
                const Text('Recording', style: TextStyle(color: Color(0xFF10B981), fontWeight: FontWeight.w600, fontSize: 13)),
              ] else if (isPaused) ...[
                Container(width: 8, height: 8,
                    decoration: const BoxDecoration(color: Color(0xFFFBBF24), shape: BoxShape.circle)),
                const SizedBox(width: 8),
                const Text('Paused', style: TextStyle(color: Color(0xFFFBBF24), fontWeight: FontWeight.w600, fontSize: 13)),
              ] else if (_state == _RecordState.completing) ...[
                const SizedBox(width: 16, height: 16, child: CircularProgressIndicator(strokeWidth: 2, color: Color(0xFF3B82F6))),
                const SizedBox(width: 8),
                const Text('Saving...', style: TextStyle(color: Color(0xFF3B82F6), fontSize: 13)),
              ],
              const Spacer(),
              Text('Say "insert photo" or tap 📷',
                  style: const TextStyle(color: Color(0xFF4B5563), fontSize: 11)),
            ]),
          ),

          // Transcript area
          Expanded(
            child: ListView.builder(
              controller: _scrollCtrl,
              padding: const EdgeInsets.all(16),
              itemCount: _segments.length + (_liveText.isNotEmpty ? 1 : 0),
              itemBuilder: (_, i) {
                // Live partial text at the bottom
                if (i == _segments.length && _liveText.isNotEmpty) {
                  return Padding(
                    padding: const EdgeInsets.only(bottom: 8),
                    child: Text(
                      _liveText,
                      style: const TextStyle(color: Color(0xFF6B7280), fontSize: 15, fontStyle: FontStyle.italic, height: 1.6),
                    ),
                  );
                }

                final seg = _segments[i];

                if (seg.text != null) {
                  return Padding(
                    padding: const EdgeInsets.only(bottom: 6),
                    child: Text(
                      seg.text!,
                      style: const TextStyle(color: Color(0xFFE5E7EB), fontSize: 15, height: 1.6),
                    ),
                  );
                }

                // Photo segment
                return Container(
                  margin: const EdgeInsets.symmetric(vertical: 10),
                  padding: const EdgeInsets.all(12),
                  decoration: BoxDecoration(
                    color: const Color(0xFF064E3B),
                    borderRadius: BorderRadius.circular(10),
                    border: Border.all(color: const Color(0xFF10B981), width: 1),
                  ),
                  child: Row(children: [
                    if (seg.photoLocalPath != null)
                      ClipRRect(
                        borderRadius: BorderRadius.circular(8),
                        child: Image.file(File(seg.photoLocalPath!),
                            width: 60, height: 60, fit: BoxFit.cover),
                      )
                    else
                      const Icon(Icons.image, color: Color(0xFF10B981), size: 40),
                    const SizedBox(width: 12),
                    Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                      const Text('📷 Photo inserted',
                          style: TextStyle(color: Color(0xFF10B981), fontWeight: FontWeight.w600, fontSize: 13)),
                      const SizedBox(height: 2),
                      Text(
                        seg.isPhotoUploading ? 'Uploading...' : 'Saved',
                        style: TextStyle(
                          color: seg.isPhotoUploading ? const Color(0xFFFBBF24) : const Color(0xFF6B7280),
                          fontSize: 12,
                        ),
                      ),
                    ])),
                    if (seg.isPhotoUploading)
                      const SizedBox(width: 16, height: 16,
                          child: CircularProgressIndicator(strokeWidth: 2, color: Color(0xFF10B981))),
                  ]),
                );
              },
            ),
          ),

          // Bottom controls
          Container(
            padding: const EdgeInsets.all(16),
            color: const Color(0xFF111827),
            child: Row(children: [
              // Pause / Resume
              Expanded(
                child: ElevatedButton.icon(
                  onPressed: isLive ? _pauseListening : (isPaused ? _resumeListening : null),
                  style: ElevatedButton.styleFrom(
                    backgroundColor: isLive ? const Color(0xFF374151) : const Color(0xFF1E3A5F),
                    padding: const EdgeInsets.symmetric(vertical: 14),
                    shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
                  ),
                  icon: Icon(isLive ? Icons.pause : Icons.mic, color: Colors.white, size: 18),
                  label: Text(isLive ? 'Pause' : 'Resume',
                      style: const TextStyle(color: Colors.white, fontWeight: FontWeight.w600)),
                ),
              ),
              const SizedBox(width: 10),
              // Photo button
              ElevatedButton(
                onPressed: _triggerPhoto,
                style: ElevatedButton.styleFrom(
                  backgroundColor: const Color(0xFF064E3B),
                  padding: const EdgeInsets.symmetric(vertical: 14, horizontal: 16),
                  shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10),
                      side: const BorderSide(color: Color(0xFF10B981))),
                ),
                child: const Icon(Icons.camera_alt, color: Color(0xFF10B981), size: 22),
              ),
              const SizedBox(width: 10),
              // Complete
              Expanded(
                child: ElevatedButton.icon(
                  onPressed: (_state == _RecordState.completing) ? null : _complete,
                  style: ElevatedButton.styleFrom(
                    backgroundColor: const Color(0xFF10B981),
                    padding: const EdgeInsets.symmetric(vertical: 14),
                    shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
                  ),
                  icon: const Icon(Icons.check_circle_outline, color: Colors.white, size: 18),
                  label: const Text('Done',
                      style: TextStyle(color: Colors.white, fontWeight: FontWeight.w600)),
                ),
              ),
            ]),
          ),
        ]),
      ),
    );
  }
}
