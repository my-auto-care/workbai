import 'dart:convert';
import 'dart:io';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:image_picker/image_picker.dart';
import 'package:http/http.dart' as http;
import 'package:livekit_client/livekit_client.dart';
import '../services/api_service.dart';
import 'session_screen.dart';

enum InspectionState { connecting, active, completing, done, error }

class InspectionScreen extends StatefulWidget {
  final String sessionId;
  const InspectionScreen({super.key, required this.sessionId});
  @override
  State<InspectionScreen> createState() => _InspectionScreenState();
}

class _InspectionScreenState extends State<InspectionScreen> {
  InspectionState _state = InspectionState.connecting;
  Room? _room;
  EventsListener<RoomEvent>? _listener;
  String? _error;
  final List<String> _log = [];
  bool _photoRequested = false;
  String? _pendingPhotoItemId;
  String? _pendingPhotoReason;
  bool _isCapturingPhoto = false;

  @override
  void initState() {
    super.initState();
    _connect();
  }

  Future<void> _connect() async {
    try {
      final tokenData = await ApiService().getVoiceToken(
        sessionId: widget.sessionId,
        technicianName: 'Technician',
      );

      final room = Room();
      _room = room;
      _listener = room.createListener();

      _listener!.on<DataReceivedEvent>((event) {
        try {
          final msg = jsonDecode(utf8.decode(event.data));
          if (msg['type'] == 'photo_request') {
            final itemId = msg['item_id'] ?? '';
            final reason = msg['reason'] ?? 'Photo needed';
            final isAuto = msg['auto'] == true;
            _addLog('📷 ${isAuto ? "Auto photo" : "Photo"}: $reason');
            setState(() {
              _photoRequested = true;
              _pendingPhotoItemId = itemId;
              _pendingPhotoReason = reason;
            });
            if (isAuto) {
              _handleAutoPhotoRequest();
            }
          }
        } catch (_) {}
      });

      await room.connect(
        tokenData['livekit_url'],
        tokenData['token'],
        roomOptions: const RoomOptions(adaptiveStream: true, dynacast: true),
      );

      await room.localParticipant?.setMicrophoneEnabled(true);
      setState(() => _state = InspectionState.active);
      _addLog('Connected — speak to begin inspection');
    } catch (e) {
      setState(() { _state = InspectionState.error; _error = e.toString(); });
    }
  }

  void _addLog(String msg) {
    setState(() {
      _log.add(msg);
      if (_log.length > 50) _log.removeAt(0);
    });
  }

  /// Called when the agent auto-detects an issue — vibrate and open camera immediately
  Future<void> _handleAutoPhotoRequest() async {
    if (_isCapturingPhoto) return;
    // Vibrate to alert the technician hands-free
    HapticFeedback.heavyImpact();
    await Future.delayed(const Duration(milliseconds: 300));
    HapticFeedback.heavyImpact();
    await Future.delayed(const Duration(milliseconds: 300));
    HapticFeedback.heavyImpact();
    // Small delay so the vibration registers before camera opens
    await Future.delayed(const Duration(milliseconds: 500));
    if (mounted) {
      await _capturePhoto(auto: true);
    }
  }

  Future<void> _capturePhoto({bool auto = false}) async {
    if (_isCapturingPhoto) return;
    setState(() => _isCapturingPhoto = true);

    final picker = ImagePicker();
    final XFile? photo = await picker.pickImage(source: ImageSource.camera, imageQuality: 80);

    if (photo == null) {
      // User cancelled — keep banner visible so they can tap manually
      setState(() => _isCapturingPhoto = false);
      return;
    }

    _addLog('📤 Uploading photo...');
    try {
      final uploadData = await ApiService().getUploadUrl(
        sessionId: widget.sessionId,
        filename: '${_pendingPhotoItemId ?? 'photo'}_${DateTime.now().millisecondsSinceEpoch}.jpg',
      );

      final uploadUrl = uploadData['upload_url'] as String;
      final s3Key = uploadData['s3_key'] as String;

      final bytes = await File(photo.path).readAsBytes();
      final uploadResp = await http.put(
        Uri.parse(uploadUrl),
        headers: {'Content-Type': 'image/jpeg'},
        body: bytes,
      );

      if (uploadResp.statusCode == 200 || uploadResp.statusCode == 204) {
        await ApiService().attachMedia(
          sessionId: widget.sessionId,
          s3Key: s3Key,
        );
        _addLog('✅ Photo uploaded');
        HapticFeedback.lightImpact();
      } else {
        _addLog('⚠️ Photo upload failed (${uploadResp.statusCode})');
      }
    } catch (e) {
      _addLog('⚠️ Photo error: $e');
    }

    setState(() {
      _photoRequested = false;
      _pendingPhotoItemId = null;
      _pendingPhotoReason = null;
      _isCapturingPhoto = false;
    });
  }

  Future<void> _complete() async {
    setState(() => _state = InspectionState.completing);
    try {
      await _room?.localParticipant?.setMicrophoneEnabled(false);
      await _room?.disconnect();
      await ApiService().completeSession(widget.sessionId);
      setState(() => _state = InspectionState.done);
      if (mounted) {
        await Future.delayed(const Duration(seconds: 1));
        Navigator.pushReplacement(context,
            MaterialPageRoute(builder: (_) => SessionScreen(sessionId: widget.sessionId)));
      }
    } catch (e) {
      setState(() { _state = InspectionState.error; _error = e.toString(); });
    }
  }

  @override
  void dispose() {
    _listener?.dispose();
    _room?.disconnect();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFF0A0A0F),
      appBar: AppBar(
        backgroundColor: const Color(0xFF111827),
        title: const Text('Inspection Active', style: TextStyle(color: Colors.white)),
        iconTheme: const IconThemeData(color: Colors.white),
        automaticallyImplyLeading: false,
      ),
      body: SafeArea(
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Column(children: [
            _StatusBadge(state: _state),
            const SizedBox(height: 24),

            if (_state == InspectionState.error) ...[
              const Icon(Icons.error_outline, color: Color(0xFFEF4444), size: 48),
              const SizedBox(height: 12),
              Text(_error ?? 'Unknown error', style: const TextStyle(color: Color(0xFF9CA3AF)), textAlign: TextAlign.center),
              const SizedBox(height: 16),
              ElevatedButton(onPressed: () => Navigator.pop(context), child: const Text('Go Back')),
            ] else ...[
              if (_state == InspectionState.active) const _PulsingMic(),
              const SizedBox(height: 16),

              // Photo request banner — shown for manual requests or if auto-capture was cancelled
              if (_photoRequested && !_isCapturingPhoto)
                GestureDetector(
                  onTap: () => _capturePhoto(),
                  child: Container(
                    width: double.infinity,
                    padding: const EdgeInsets.all(16),
                    margin: const EdgeInsets.only(bottom: 12),
                    decoration: BoxDecoration(
                      color: const Color(0xFF7F1D1D),
                      borderRadius: BorderRadius.circular(12),
                      border: Border.all(color: const Color(0xFFEF4444), width: 2),
                    ),
                    child: Row(children: [
                      const Icon(Icons.camera_alt, color: Color(0xFFEF4444), size: 28),
                      const SizedBox(width: 12),
                      Expanded(child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          const Text('⚠️ Issue Detected — Photo Required',
                              style: TextStyle(color: Colors.white, fontWeight: FontWeight.w700, fontSize: 14)),
                          if (_pendingPhotoReason != null)
                            Text(_pendingPhotoReason!,
                                style: const TextStyle(color: Color(0xFFFCA5A5), fontSize: 12)),
                        ],
                      )),
                      const Icon(Icons.chevron_right, color: Color(0xFF9CA3AF)),
                    ]),
                  ),
                ),

              // Capturing indicator
              if (_isCapturingPhoto)
                Container(
                  width: double.infinity,
                  padding: const EdgeInsets.all(16),
                  margin: const EdgeInsets.only(bottom: 12),
                  decoration: BoxDecoration(
                    color: const Color(0xFF1E3A5F),
                    borderRadius: BorderRadius.circular(12),
                    border: Border.all(color: const Color(0xFF3B82F6), width: 1.5),
                  ),
                  child: const Row(children: [
                    SizedBox(width: 20, height: 20, child: CircularProgressIndicator(strokeWidth: 2, color: Color(0xFF3B82F6))),
                    SizedBox(width: 12),
                    Text('Uploading photo...', style: TextStyle(color: Colors.white)),
                  ]),
                ),

              Expanded(
                child: Container(
                  padding: const EdgeInsets.all(16),
                  decoration: BoxDecoration(
                    color: const Color(0xFF111827),
                    borderRadius: BorderRadius.circular(12),
                    border: Border.all(color: const Color(0xFF1F2937)),
                  ),
                  child: _log.isEmpty
                      ? const Center(child: Text('Waiting for voice activity...', style: TextStyle(color: Color(0xFF4B5563))))
                      : ListView.builder(
                          reverse: true,
                          itemCount: _log.length,
                          itemBuilder: (_, i) => Padding(
                            padding: const EdgeInsets.symmetric(vertical: 4),
                            child: Text(_log[_log.length - 1 - i],
                                style: const TextStyle(color: Color(0xFFD1D5DB), fontSize: 14)),
                          ),
                        ),
                ),
              ),

              const SizedBox(height: 24),

              if (_state == InspectionState.active)
                SizedBox(
                  width: double.infinity,
                  child: ElevatedButton.icon(
                    onPressed: _complete,
                    style: ElevatedButton.styleFrom(
                      backgroundColor: const Color(0xFF10B981),
                      padding: const EdgeInsets.symmetric(vertical: 16),
                      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                    ),
                    icon: const Icon(Icons.check_circle_outline, color: Colors.white),
                    label: const Text('Complete Inspection',
                        style: TextStyle(fontSize: 16, fontWeight: FontWeight.w600, color: Colors.white)),
                  ),
                ),

              if (_state == InspectionState.completing)
                const CircularProgressIndicator(color: Color(0xFF10B981)),
            ],
          ]),
        ),
      ),
    );
  }
}

class _StatusBadge extends StatelessWidget {
  final InspectionState state;
  const _StatusBadge({required this.state});

  @override
  Widget build(BuildContext context) {
    final (label, color, bg) = switch (state) {
      InspectionState.connecting => ('Connecting...', const Color(0xFFFBBF24), const Color(0xFF451A03)),
      InspectionState.active => ('Live', const Color(0xFF10B981), const Color(0xFF064E3B)),
      InspectionState.completing => ('Completing...', const Color(0xFF3B82F6), const Color(0xFF1E3A5F)),
      InspectionState.done => ('Done', const Color(0xFF10B981), const Color(0xFF064E3B)),
      InspectionState.error => ('Error', const Color(0xFFEF4444), const Color(0xFF7F1D1D)),
    };
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
      decoration: BoxDecoration(color: bg, borderRadius: BorderRadius.circular(20)),
      child: Row(mainAxisSize: MainAxisSize.min, children: [
        if (state == InspectionState.active)
          Container(width: 8, height: 8, margin: const EdgeInsets.only(right: 8),
              decoration: BoxDecoration(color: color, shape: BoxShape.circle)),
        Text(label, style: TextStyle(color: color, fontWeight: FontWeight.w600)),
      ]),
    );
  }
}

class _PulsingMic extends StatefulWidget {
  const _PulsingMic();
  @override
  State<_PulsingMic> createState() => _PulsingMicState();
}

class _PulsingMicState extends State<_PulsingMic> with SingleTickerProviderStateMixin {
  late AnimationController _ctrl;
  late Animation<double> _anim;

  @override
  void initState() {
    super.initState();
    _ctrl = AnimationController(vsync: this, duration: const Duration(seconds: 1))..repeat(reverse: true);
    _anim = Tween(begin: 0.8, end: 1.2).animate(CurvedAnimation(parent: _ctrl, curve: Curves.easeInOut));
  }

  @override
  void dispose() { _ctrl.dispose(); super.dispose(); }

  @override
  Widget build(BuildContext context) => ScaleTransition(
    scale: _anim,
    child: Container(
      width: 80, height: 80,
      decoration: const BoxDecoration(color: Color(0xFF1E3A5F), shape: BoxShape.circle),
      child: const Icon(Icons.mic, color: Color(0xFF3B82F6), size: 40),
    ),
  );
}
