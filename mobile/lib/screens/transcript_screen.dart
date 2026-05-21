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

  // Track multiple audio segment files (stop/start instead of pause/resume)
  final List<String> _audioSegments = [];
  String? _currentSegmentPath;
  int _segmentIndex = 0;

  // Total recorded duration across all segments
  Duration _totalRecorded = Duration.zero;
  DateTime? _segmentStartTime;

  // Elapsed ticker
  int _elapsedSeconds = 0;
  late final Stream<int> _ticker = Stream.periodic(
    const Duration(seconds: 1), (i) => i,
  );

  final List<_PhotoMarker> _photos = [];
  final List<String> _log = [];

  @override
  void initState() {
    super.initState();
    _startSegment();
  }

  Future<void> _startSegment() async {
    try {
      final hasPermission = await _recorder.hasPermission();
      if (!hasPermission) {
        setState(() { _error = 'Microphone permission denied'; _state = _State.error; });
        return;
      }

      final dir = await getTemporaryDirectory();
      _currentSegmentPath = '${dir.path}/seg_${widget.sessionId}_$_segmentIndex.m4a';
      _segmentIndex++;
      _segmentStartTime = DateTime.now();

      await _recorder.start(
        const RecordConfig(
          encoder: AudioEncoder.aacLc,
          bitRate: 64000,
          sampleRate: 16000,
          numChannels: 1,
        ),
        path: _currentSegmentPath!,
      );

      setState(() {
        _state = _State.recording;
        if (_segmentIndex == 1) _log.add('🎙️ Recording — speak freely at your own pace');
      });
    } catch (e) {
      setState(() { _error = e.toString(); _state = _State.error; });
    }
  }

  Future<void> _pause() async {
    // Stop current segment and save it
    final path = await _recorder.stop();
    if (path != null && File(path).existsSync()) {
      _audioSegments.add(path);
    }
    // Accumulate duration
    if (_segmentStartTime != null) {
      _totalRecorded += DateTime.now().difference(_segmentStartTime!);
      _segmentStartTime = null;
    }
    setState(() {
      _state = _State.paused;
      _log.add('⏸️ Paused');
    });
  }

  Future<void> _resume() async {
    setState(() => _log.add('🎙️ Resumed'));
    await _startSegment();
  }

  Duration get _currentOffset {
    final segmentSoFar = _segmentStartTime != null
        ? DateTime.now().difference(_segmentStartTime!)
        : Duration.zero;
    return _totalRecorded + segmentSoFar;
  }

  Future<void> _insertPhoto() async {
    HapticFeedback.mediumImpact();

    // Stop current segment while camera is open
    final wasRecording = _state == _State.recording;
    if (wasRecording) {
      final path = await _recorder.stop();
      if (path != null && File(path).existsSync()) _audioSegments.add(path);
      if (_segmentStartTime != null) {
        _totalRecorded += DateTime.now().difference(_segmentStartTime!);
        _segmentStartTime = null;
      }
    }

    final offset = _currentOffset;
    final picker = ImagePicker();
    final XFile? photo = await picker.pickImage(
      source: ImageSource.camera,
      imageQuality: 60,       // lower quality = faster upload
      maxWidth: 1280,         // cap resolution
      maxHeight: 960,
    );

    // Resume immediately — don't wait for upload
    if (wasRecording) await _startSegment();

    if (photo == null) return;

    final marker = _PhotoMarker(
      localPath: photo.path,
      timestamp: DateTime.now(),
      recordingOffset: offset,
    );

    setState(() {
      _photos.add(marker);
      _log.add('📷 Photo at ${_formatDuration(offset)} — uploading...');
    });

    // Fire and forget — do NOT await
    _uploadPhoto(photo, marker);
  }

  void _uploadPhoto(XFile photo, _PhotoMarker marker) {
    () async {
      try {
        final uploadData = await ApiService().getUploadUrl(
          sessionId: widget.sessionId,
          filename: 'photo_${DateTime.now().millisecondsSinceEpoch}.jpg',
        );
        final bytes = await File(photo.path).readAsBytes();
        final resp = await http.put(
          Uri.parse(uploadData['upload_url']),
          headers: {'Content-Type': 'image/jpeg'},
          body: bytes,
        );
        if (resp.statusCode == 200 || resp.statusCode == 204) {
          await ApiService().attachMedia(
            sessionId: widget.sessionId,
            s3Key: uploadData['s3_key'],
          );
          if (mounted) {
            setState(() {
              marker.s3Key = uploadData['s3_key'];
              marker.uploading = false;
              // Replace last log entry for this photo
              final idx = _log.lastIndexWhere((l) => l.contains(_formatDuration(marker.recordingOffset)));
              if (idx >= 0) _log[idx] = '📷 Photo at ${_formatDuration(marker.recordingOffset)} ✅';
            });
          }
          HapticFeedback.lightImpact();
        }
      } catch (_) {
        if (mounted) setState(() => marker.uploading = false);
      }
    }();
  }

  Future<void> _complete() async {
    setState(() {
      _state = _State.processing;
      _log.add('⏹️ Stopped — sending to AI...');
    });

    try {
      // Stop current segment
      if (await _recorder.isRecording()) {
        final path = await _recorder.stop();
        if (path != null && File(path).existsSync()) _audioSegments.add(path);
      }

      if (_audioSegments.isEmpty) {
        throw Exception('No audio recorded');
      }

      // Use the largest segment (most content) if only one,
      // or concatenate by sending all segments
      // For now send the first/only segment — backend handles it
      // TODO: merge segments server-side for multi-segment sessions
      final primaryAudio = _audioSegments.reduce(
        (a, b) => File(a).lengthSync() >= File(b).lengthSync() ? a : b,
      );

      final photoOffsets = _photos.map((p) => _formatDuration(p.recordingOffset)).join(',');

      setState(() => _log.add('📡 Transcribing with AssemblyAI + Claude cleanup...'));

      final result = await ApiService().processTranscript(
        sessionId: widget.sessionId,
        audioPath: primaryAudio,
        photoMarkers: photoOffsets,
      );

      final removed = result['words_removed'] ?? 0;
      setState(() => _log.add('✅ Done — $removed irrelevant words removed'));

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

          // Status bar with live elapsed timer
          StreamBuilder<int>(
            stream: _ticker,
            builder: (_, snap) {
              if (isRecording && snap.hasData) _elapsedSeconds = snap.data! + 1;
              final display = _totalRecorded + (isRecording
                  ? Duration(seconds: _elapsedSeconds)
                  : Duration.zero);
              return Container(
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
                  Text(_formatDuration(display),
                      style: const TextStyle(color: Color(0xFF6B7280), fontFamily: 'monospace', fontSize: 14, fontWeight: FontWeight.w600)),
                ]),
              );
            },
          ),

          // Hint
          if (isRecording || isPaused)
            Container(
              width: double.infinity,
              padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 6),
              color: const Color(0xFF0A0A0F),
              child: const Text(
                'Mic stays on — speak at your own pace. Tap 📷 anytime to insert a photo.',
                style: TextStyle(color: Color(0xFF4B5563), fontSize: 12),
                textAlign: TextAlign.center,
              ),
            ),

          // Photo strip
          if (_photos.isNotEmpty)
            Container(
              height: 90,
              padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
              child: ListView.builder(
                scrollDirection: Axis.horizontal,
                itemCount: _photos.length,
                itemBuilder: (_, i) {
                  final p = _photos[i];
                  return Container(
                    margin: const EdgeInsets.only(right: 8),
                    width: 76,
                    decoration: BoxDecoration(
                      borderRadius: BorderRadius.circular(8),
                      border: Border.all(color: p.uploading ? const Color(0xFFFBBF24) : const Color(0xFF10B981)),
                    ),
                    child: Stack(children: [
                      ClipRRect(
                        borderRadius: BorderRadius.circular(7),
                        child: Image.file(File(p.localPath), width: 76, height: 76, fit: BoxFit.cover),
                      ),
                      Positioned(bottom: 0, left: 0, right: 0,
                        child: Container(
                          padding: const EdgeInsets.symmetric(vertical: 2),
                          decoration: const BoxDecoration(
                            color: Colors.black54,
                            borderRadius: BorderRadius.vertical(bottom: Radius.circular(7)),
                          ),
                          child: Text(_formatDuration(p.recordingOffset),
                              textAlign: TextAlign.center,
                              style: const TextStyle(color: Colors.white, fontSize: 9)),
                        ),
                      ),
                      if (p.uploading)
                        const Positioned.fill(child: Center(
                          child: SizedBox(width: 18, height: 18,
                              child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white)),
                        )),
                    ]),
                  );
                },
              ),
            ),

          // Activity log
          Expanded(
            child: ListView.builder(
              controller: _scrollCtrl,
              padding: const EdgeInsets.all(16),
              itemCount: _log.length,
              itemBuilder: (_, i) => Padding(
                padding: const EdgeInsets.only(bottom: 8),
                child: Text(_log[i],
                    style: const TextStyle(color: Color(0xFF9CA3AF), fontSize: 14, height: 1.5)),
              ),
            ),
          ),

          // Processing
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
                Text('Takes 1–2 minutes', style: TextStyle(color: Color(0xFF4B5563), fontSize: 12)),
              ]),
            ),

          // Controls
          if (!isProcessing && _state != _State.done && _state != _State.error)
            Container(
              padding: const EdgeInsets.fromLTRB(16, 12, 16, 20),
              color: const Color(0xFF111827),
              child: Row(children: [
                Expanded(
                  child: ElevatedButton.icon(
                    onPressed: isRecording ? _pause : _resume,
                    style: ElevatedButton.styleFrom(
                      backgroundColor: isRecording ? const Color(0xFF374151) : const Color(0xFF1D4ED8),
                      padding: const EdgeInsets.symmetric(vertical: 16),
                      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                    ),
                    icon: Icon(isRecording ? Icons.pause_circle_outline : Icons.mic, color: Colors.white, size: 20),
                    label: Text(isRecording ? 'Pause' : 'Resume',
                        style: const TextStyle(color: Colors.white, fontWeight: FontWeight.w700, fontSize: 15)),
                  ),
                ),
                const SizedBox(width: 10),
                ElevatedButton(
                  onPressed: _insertPhoto,
                  style: ElevatedButton.styleFrom(
                    backgroundColor: const Color(0xFF064E3B),
                    padding: const EdgeInsets.symmetric(vertical: 16, horizontal: 18),
                    shape: RoundedRectangleBorder(
                        borderRadius: BorderRadius.circular(12),
                        side: const BorderSide(color: Color(0xFF10B981), width: 1.5)),
                  ),
                  child: const Icon(Icons.camera_alt, color: Color(0xFF10B981), size: 24),
                ),
                const SizedBox(width: 10),
                Expanded(
                  child: ElevatedButton.icon(
                    onPressed: _complete,
                    style: ElevatedButton.styleFrom(
                      backgroundColor: const Color(0xFF10B981),
                      padding: const EdgeInsets.symmetric(vertical: 16),
                      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                    ),
                    icon: const Icon(Icons.check_circle_outline, color: Colors.white, size: 20),
                    label: const Text('Done', style: TextStyle(color: Colors.white, fontWeight: FontWeight.w700, fontSize: 15)),
                  ),
                ),
              ]),
            ),

          if (_state == _State.error)
            Container(
              padding: const EdgeInsets.all(16),
              color: const Color(0xFF7F1D1D),
              child: Column(children: [
                Text(_error ?? 'Unknown error', style: const TextStyle(color: Color(0xFFFCA5A5))),
                const SizedBox(height: 8),
                ElevatedButton(onPressed: _startSegment, child: const Text('Retry')),
              ]),
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
