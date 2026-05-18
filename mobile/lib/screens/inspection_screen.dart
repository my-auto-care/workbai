import 'package:flutter/material.dart';
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
  String? _error;
  String _transcript = '';
  final List<String> _log = [];

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

      room.addListener(_onRoomEvent);

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

  void _onRoomEvent() {
    // Track data messages from agent (transcripts)
    _room?.participants.forEach((_, p) {
      // Data track handling done via event listeners set at connect time
    });
  }

  void _addLog(String msg) {
    setState(() {
      _log.add(msg);
      if (_log.length > 50) _log.removeAt(0);
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
    _room?.removeListener(_onRoomEvent);
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
            // Status indicator
            _StatusBadge(state: _state),
            const SizedBox(height: 24),

            if (_state == InspectionState.error) ...[
              const Icon(Icons.error_outline, color: Color(0xFFEF4444), size: 48),
              const SizedBox(height: 12),
              Text(_error ?? 'Unknown error', style: const TextStyle(color: Color(0xFF9CA3AF)), textAlign: TextAlign.center),
              const SizedBox(height: 16),
              ElevatedButton(onPressed: () => Navigator.pop(context), child: const Text('Go Back')),
            ] else ...[
              // Mic visual
              if (_state == InspectionState.active)
                const _PulsingMic(),

              const SizedBox(height: 24),

              // Transcript log
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

              // Complete button
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
