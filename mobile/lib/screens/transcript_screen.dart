import 'dart:io';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:image_picker/image_picker.dart';
import 'package:http/http.dart' as http;
import 'package:record/record.dart';
import 'package:path_provider/path_provider.dart';
import '../services/api_service.dart';
import 'session_screen.dart';

class _PhotoMarker {
  final String localPath;
  final DateTime timestamp;
  final Duration recordingOffset;
  String? s3Key;
  bool uploading;

  _PhotoMarker({
    required this.localPath,
    required this.timestamp,
    required this.recordingOffset,
    this.s3Key,
    this.uploading = true,
  });
}

enum _State { recording, paused, processing, done, error }

class TranscriptScreen extends StatefulWidget {
  final String sessionId;
  const TranscriptScreen({super.key, required this.sessionId});
  @override
  State<TranscriptScreen> createState() => _TranscriptScreenState();
}

class _TranscriptScreenState extends State<TranscriptScreen> {
  final AudioRecorder _recorder = AudioRecorder();
  final ScrollController _scrollCtrl = ScrollController();

  _State _state = _State.recording;
  String? _error;
  String? _audioPath;
  DateTime? _recordingStartTime;
  Duration _elapsed = Duration.zero;

  final List<_PhotoMarker> _photos = [];
  final List<String> _log = []; // activity log shown on screen

  // Timer for elapsed display
  late final Stream<Duration> _elapsedStream = Stream.periodic(
    const Duration(seconds: 1),
    (i) => Duration(seconds: i + 1),
  );

  @override
  void initState() {
    super.initState();
    _startRecording();
  }

  Future<void> _startRecording() async {
    try {
      final hasPermission = await _recorder.hasPermission();
      if (!hasPermission) {
        setState(() { _error = 'Microphone permission denied'; _state = _State.error; });
        return;
      }

      final dir = await getTemporaryDirectory();
      _audioPath = '${dir.path}/inspection_${widget.sessionId}.m4a';
      _recordingStartTime = DateTime.now();

      await _recorder.start(
        const RecordConfig(
          encoder: AudioEncoder.aacLc,
          bitRate: 64000,
          sampleRate: 16000, // optimal for speech recognition
          numChannels: 1,
        ),
        path: _audioPath!,
      );

      setState(() {
        _state = _State.recording;
        _log.add('🎙️ Recording started — speak freely');
      });
    } catch (e) {
      setState(() { _error = e.toString(); _state = _State.error; });
    }
  }

  Future<void> _pause() async {
    await _recorder.pause();
    setState(() {
      _state = _State.paused;
      _log.add('⏸️ Paused');
    });
  }

  Future<void> _resume() async {
    await _recorder.resume();
    setState(() {
      _state = _State.recording;
      _log.add('🎙️ Resumed');
    });
  }

  Duration get _currentOffset {
    if (_recordingStartTime == null) return Duration.zero;
    return DateTime.now().difference(_recordingStartTime!);
  }

  Future<void> _insertPhoto() async {
    HapticFeedback.mediumImpact();

    // Pause recording while camera is open so we don't record shutter sounds
    final wasRecording = _state == _State.recording;
    if (wasRecording) await _recorder.pause();

    final picker = ImagePicker();
    final XFile? photo = await picker.pickImage(source: ImageSource.camera, imageQuality: 80);

    if (wasRecording) await _recorder.resume();

    if (photo == null) return;

    final marker = _PhotoMarker(
      localPath: photo.path,
      timestamp: DateTime.now(),
      recordingOffset: _currentOffset,
    );

    setState(() {
      _photos.add(marker);
      _log.add('📷 Photo inserted at ${_formatDuration(_currentOffset)}');
    });

    _uploadPhoto(photo, marker);
  }

  Future<void> _uploadPhoto(XFile photo, _PhotoMarker marker) async {
    try {
      final uploadData = await ApiService().getUploadUrl(
        sessionId: widget.sessionId,
        filename: 'transcript_photo_${DateTime.now().millisecondsSinceEpoch}.jpg',
      );
      final bytes = await File(photo.path).readAsBytes();
      final resp = await http.put(
        Uri.parse(uploadData['upload_url']),
        headers: {'Content-Type': 'image/jpeg'},
        body: bytes,
      );
      if (resp.statusCode == 200 || resp.statusCode == 204) {
        await ApiService().attachMedia(sessionId: widget.sessionId, s3Key: uploadData['s3_key']);
        setState(() { marker.s3Key = uploadData['s3_key']; marker.uploading = false; });
        HapticFeedback.lightImpact();
      }
    } catch (e) {
      setState(() => marker.uploading = false);
    }
  }

  Future<void> _complete() async {
    setState(() { _state = _State.processing; _log.add('⏹️ Stopped — processing audio...'); });

    try {
      // Stop recording
      await _recorder.stop();

      if (_audioPath == null || !File(_audioPath!).existsSync()) {
        throw Exception('Audio file not found');
      }

      setState(() => _log.add('📡 Uploading to AI for transcription & cleanup...'));

      // Send to backend for AssemblyAI + Claude processing
      final photoOffsets = _photos.map((p) => _formatDuration(p.recordingOffset)).join(',');
      final result = await ApiService().processTranscript(
        sessionId: widget.sessionId,
        audioPath: _audioPath!,
        photoMarkers: photoOffsets,
      );

      final wordsRemoved = result['words_removed'] ?? 0;
      setState(() => _log.add('✅ Done — $wordsRemoved irrelevant words removed by AI'));

      await ApiService().completeSession(widget.sessionId);
      setState(() => _state = _State.done);

      await Future.delayed(const Duration(seconds: 1));
      if (mounted) {
        Navigator.pushReplacement(context,
            MaterialPageRoute(builder: (_) => SessionScreen(sessionId: widget.sessionId)));
      }
    } catch (e) {
      setState(() { _error = e.toString(); _state = _State.error; });
    }
  }

  String _formatDuration(Duration d) {
    final m = d.inMinutes.toString().padLeft(2, '0');
    final s = (d.inSeconds % 60).toString().padLeft(2, '0');
    return '$m:$s';
  }

  @override
  void dispose() {
    _recorder.dispose();
    _scrollCtrl.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final isRecording = _state == _State.recording;
    final isPaused = _state == _State.paused;
    final isProcessing = _state == _State.processing;

    return Scaffold(
      backgroundColor: const Color(0xFF0A0A0F),
      appBar: AppBar(
        backgroundColor: const Color(0xFF111827),
        title: const Text('Transcript Mode', style: TextStyle(color: Colors.white)),
        iconTheme: const IconThemeData(color: Colors.white),
        automaticallyImplyLeading: false,
        actions: [
          IconButton(
            icon: const Icon(Icons.camera_alt, color: Color(0xFF10B981)),
            tooltip: 'Insert Photo',
            onPressed: (isRecording || isPaused) ? _insertPhoto : null,
          ),
        ],
      ),
      body: SafeArea(
        child: Column(children: [

          // Status bar
          Container(
            width: double.infinity,
            padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
            color: const Color(0xFF111827),
            child: Row(children: [
              if (isRecording) ...[
                _PulsingDot(color: const Color(0xFFEF4444)),
                const SizedBox(width: 8),
                const Text('Recording', style: TextStyle(color: Color(0xFFEF4444), fontWeight: FontWeight.w700, fontSize: 14)),
              ] else if (isPaused) ...[
                Container(width: 8, height: 8, decoration: const BoxDecoration(color: Color(0xFFFBBF24), shape: BoxShape.circle)),
                const SizedBox(width: 8),
                const Text('Paused', style: TextStyle(color: Color(0xFFFBBF24), fontWeight: FontWeight.w700, fontSize: 14)),
              ] else if (isProcessing) ...[
                const SizedBox(width: 14, height: 14, child: CircularProgressIndicator(strokeWidth: 2, color: Color(0xFF3B82F6))),
                const SizedBox(width: 8),
                const Text('AI Processing...', style: TextStyle(color: Color(0xFF3B82F6), fontWeight: FontWeight.w700, fontSize: 14)),
              ],
              const Spacer(),
              // Elapsed timer
              if (isRecording || isPaused)
                StreamBuilder<Duration>(
                  stream: _elapsedStream,
                  builder: (_, snap) {
                    final d = snap.data ?? Duration.zero;
                    return Text(_formatDuration(d),
                        style: const TextStyle(color: Color(0xFF6B7280), fontFamily: 'monospace', fontSize: 13));
                  },
                ),
            ]),
          ),

          // Instruction banner
          if (isRecording || isPaused)
            Container(
              width: double.infinity,
              padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
              color: const Color(0xFF0A0A0F),
              child: const Text(
                'Speak freely — mic stays on. Say "insert photo" or tap 📷 to add photos.',
                style: TextStyle(color: Color(0xFF4B5563), fontSize: 12),
                textAlign: TextAlign.center,
              ),
            ),

          // Activity log
          Expanded(
            child: ListView.builder(
              controller: _scrollCtrl,
              padding: const EdgeInsets.all(16),
              itemCount: _log.length + (_photos.isNotEmpty ? 1 : 0),
              itemBuilder: (_, i) {
                // Photo strip at top
                if (i == 0 && _photos.isNotEmpty) {
                  return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                    const Text('PHOTOS', style: TextStyle(color: Color(0xFF6B7280), fontSize: 11, fontWeight: FontWeight.w600, letterSpacing: 1)),
                    const SizedBox(height: 8),
                    SizedBox(
                      height: 80,
                      child: ListView.builder(
                        scrollDirection: Axis.horizontal,
                        itemCount: _photos.length,
                        itemBuilder: (_, j) {
                          final p = _photos[j];
                          return Container(
                            margin: const EdgeInsets.only(right: 8),
                            width: 80,
                            decoration: BoxDecoration(
                              borderRadius: BorderRadius.circular(8),
                              border: Border.all(color: const Color(0xFF10B981)),
                            ),
                            child: Stack(children: [
                              ClipRRect(
                                borderRadius: BorderRadius.circular(7),
                                child: Image.file(File(p.localPath), width: 80, height: 80, fit: BoxFit.cover),
                              ),
                              Positioned(bottom: 2, left: 2,
                                child: Container(
                                  padding: const EdgeInsets.symmetric(horizontal: 4, vertical: 2),
                                  decoration: BoxDecoration(color: Colors.black54, borderRadius: BorderRadius.circular(4)),
                                  child: Text(_formatDuration(p.recordingOffset),
                                      style: const TextStyle(color: Colors.white, fontSize: 9)),
                                ),
                              ),
                              if (p.uploading)
                                const Positioned.fill(child: Center(
                                  child: SizedBox(width: 16, height: 16,
                                      child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white)),
                                )),
                            ]),
                          );
                        },
                      ),
                    ),
                    const SizedBox(height: 16),
                  ]);
                }

                final logIndex = _photos.isNotEmpty ? i - 1 : i;
                if (logIndex >= _log.length) return const SizedBox.shrink();

                return Padding(
                  padding: const EdgeInsets.only(bottom: 8),
                  child: Text(_log[logIndex],
                      style: const TextStyle(color: Color(0xFF9CA3AF), fontSize: 14, height: 1.5)),
                );
              },
            ),
          ),

          // Processing state
          if (isProcessing)
            Container(
              width: double.infinity,
              padding: const EdgeInsets.all(20),
              color: const Color(0xFF111827),
              child: const Column(children: [
                CircularProgressIndicator(color: Color(0xFF3B82F6)),
                SizedBox(height: 12),
                Text('Transcribing & removing background noise...', style: TextStyle(color: Color(0xFF9CA3AF), fontSize: 13)),
                SizedBox(height: 4),
                Text('This takes 1–2 minutes', style: TextStyle(color: Color(0xFF4B5563), fontSize: 12)),
              ]),
            ),

          // Bottom controls
          if (!isProcessing && _state != _State.done && _state != _State.error)
            Container(
              padding: const EdgeInsets.all(16),
              color: const Color(0xFF111827),
              child: Row(children: [
                // Pause/Resume
                Expanded(
                  child: ElevatedButton.icon(
                    onPressed: isRecording ? _pause : _resume,
                    style: ElevatedButton.styleFrom(
                      backgroundColor: isRecording ? const Color(0xFF374151) : const Color(0xFF1E3A5F),
                      padding: const EdgeInsets.symmetric(vertical: 14),
                      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
                    ),
                    icon: Icon(isRecording ? Icons.pause : Icons.mic, color: Colors.white, size: 18),
                    label: Text(isRecording ? 'Pause' : 'Resume',
                        style: const TextStyle(color: Colors.white, fontWeight: FontWeight.w600)),
                  ),
                ),
                const SizedBox(width: 10),
                // Photo
                ElevatedButton(
                  onPressed: _insertPhoto,
                  style: ElevatedButton.styleFrom(
                    backgroundColor: const Color(0xFF064E3B),
                    padding: const EdgeInsets.symmetric(vertical: 14, horizontal: 16),
                    shape: RoundedRectangleBorder(
                        borderRadius: BorderRadius.circular(10),
                        side: const BorderSide(color: Color(0xFF10B981))),
                  ),
                  child: const Icon(Icons.camera_alt, color: Color(0xFF10B981), size: 22),
                ),
                const SizedBox(width: 10),
                // Done
                Expanded(
                  child: ElevatedButton.icon(
                    onPressed: _complete,
                    style: ElevatedButton.styleFrom(
                      backgroundColor: const Color(0xFF10B981),
                      padding: const EdgeInsets.symmetric(vertical: 14),
                      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
                    ),
                    icon: const Icon(Icons.check_circle_outline, color: Colors.white, size: 18),
                    label: const Text('Done', style: TextStyle(color: Colors.white, fontWeight: FontWeight.w600)),
                  ),
                ),
              ]),
            ),

          if (_state == _State.error)
            Container(
              padding: const EdgeInsets.all(16),
              color: const Color(0xFF7F1D1D),
              child: Text(_error ?? 'Unknown error', style: const TextStyle(color: Color(0xFFFCA5A5))),
            ),
        ]),
      ),
    );
  }
}

class _PulsingDot extends StatefulWidget {
  final Color color;
  const _PulsingDot({required this.color});
  @override
  State<_PulsingDot> createState() => _PulsingDotState();
}

class _PulsingDotState extends State<_PulsingDot> with SingleTickerProviderStateMixin {
  late AnimationController _ctrl;
  @override
  void initState() {
    super.initState();
    _ctrl = AnimationController(vsync: this, duration: const Duration(milliseconds: 800))..repeat(reverse: true);
  }
  @override
  void dispose() { _ctrl.dispose(); super.dispose(); }
  @override
  Widget build(BuildContext context) => FadeTransition(
    opacity: Tween(begin: 0.3, end: 1.0).animate(_ctrl),
    child: Container(width: 8, height: 8, decoration: BoxDecoration(color: widget.color, shape: BoxShape.circle)),
  );
}
