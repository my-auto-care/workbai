import 'package:flutter/material.dart';
import '../models/session.dart';
import '../services/api_service.dart';
import '../services/auth_service.dart';
import 'new_session_screen.dart';
import 'inspection_screen.dart';
import 'session_screen.dart';
import 'login_screen.dart';

class HomeScreen extends StatefulWidget {
  const HomeScreen({super.key});
  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> {
  List<InspectionSession> _sessions = [];
  bool _loading = true;
  String? _error;

  static const String _kTechId = '00000000-0000-0000-0000-000000000002';

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() { _loading = true; _error = null; });
    try {
      final data = await ApiService().getSessions();
      setState(() {
        _sessions = data.map(InspectionSession.fromJson).toList();
        _loading = false;
      });
    } catch (e) {
      setState(() { _error = e.toString(); _loading = false; });
    }
  }

  Future<void> _logout() async {
    await AuthService().logout();
    if (mounted) Navigator.pushReplacement(context, MaterialPageRoute(builder: (_) => const LoginScreen()));
  }

  Future<void> _startPending(InspectionSession session) async {
    try {
      await ApiService().startSession(session.id);
      if (mounted) {
        Navigator.push(context, MaterialPageRoute(
          builder: (_) => InspectionScreen(sessionId: session.id),
        )).then((_) => _load());
      }
    } catch (e) {
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Error: $e')));
    }
  }

  List<InspectionSession> get _pending => _sessions.where((s) => s.isPending).toList();
  List<InspectionSession> get _others => _sessions.where((s) => !s.isPending).toList();

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFF0A0A0F),
      appBar: AppBar(
        backgroundColor: const Color(0xFF111827),
        title: const Text('Workbay AI', style: TextStyle(color: Colors.white, fontWeight: FontWeight.bold)),
        actions: [
          IconButton(icon: const Icon(Icons.refresh, color: Colors.white), onPressed: _load),
          IconButton(icon: const Icon(Icons.logout, color: Color(0xFF9CA3AF)), onPressed: _logout),
        ],
      ),
      floatingActionButton: FloatingActionButton.extended(
        onPressed: () async {
          await Navigator.push(context, MaterialPageRoute(builder: (_) => const NewSessionScreen()));
          _load();
        },
        backgroundColor: const Color(0xFF3B82F6),
        icon: const Icon(Icons.mic, color: Colors.white),
        label: const Text('New Inspection', style: TextStyle(color: Colors.white, fontWeight: FontWeight.w600)),
      ),
      body: _loading
          ? const Center(child: CircularProgressIndicator(color: Color(0xFF3B82F6)))
          : _error != null
              ? Center(child: Column(mainAxisAlignment: MainAxisAlignment.center, children: [
                  const Icon(Icons.error_outline, color: Color(0xFFEF4444), size: 48),
                  const SizedBox(height: 12),
                  Text(_error!, style: const TextStyle(color: Color(0xFF9CA3AF))),
                  const SizedBox(height: 16),
                  ElevatedButton(onPressed: _load, child: const Text('Retry')),
                ]))
              : RefreshIndicator(
                  onRefresh: _load,
                  color: const Color(0xFF3B82F6),
                  child: ListView(
                    padding: const EdgeInsets.all(16),
                    children: [
                      if (_pending.isNotEmpty) ...[
                        const Padding(
                          padding: EdgeInsets.only(bottom: 10),
                          child: Text('ASSIGNED TO YOU', style: TextStyle(color: Color(0xFFFBBF24), fontSize: 12, fontWeight: FontWeight.w600, letterSpacing: 1)),
                        ),
                        ..._pending.map((s) => _PendingJobTile(session: s, onStart: () => _startPending(s))),
                        const SizedBox(height: 20),
                      ],
                      if (_others.isNotEmpty) ...[
                        const Padding(
                          padding: EdgeInsets.only(bottom: 10),
                          child: Text('RECENT INSPECTIONS', style: TextStyle(color: Color(0xFF6B7280), fontSize: 12, fontWeight: FontWeight.w600, letterSpacing: 1)),
                        ),
                        ..._others.map((s) => _SessionTile(session: s)),
                      ],
                      if (_sessions.isEmpty)
                        const Center(
                          child: Padding(
                            padding: EdgeInsets.only(top: 80),
                            child: Column(children: [
                              Icon(Icons.car_repair, size: 64, color: Color(0xFF374151)),
                              SizedBox(height: 16),
                              Text('No inspections yet', style: TextStyle(color: Color(0xFF6B7280), fontSize: 18)),
                              SizedBox(height: 8),
                              Text('Tap New Inspection to begin', style: TextStyle(color: Color(0xFF4B5563), fontSize: 14)),
                            ]),
                          ),
                        ),
                      const SizedBox(height: 80),
                    ],
                  ),
                ),
    );
  }
}

class _PendingJobTile extends StatelessWidget {
  final InspectionSession session;
  final VoidCallback onStart;
  const _PendingJobTile({required this.session, required this.onStart});

  @override
  Widget build(BuildContext context) {
    return Container(
      margin: const EdgeInsets.only(bottom: 12),
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: const Color(0xFF111827),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: const Color(0xFFF59E0B), width: 1.5),
      ),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Row(children: [
          const Icon(Icons.assignment_outlined, color: Color(0xFFFBBF24), size: 18),
          const SizedBox(width: 8),
          Expanded(child: Text(session.vehicleLabel, style: const TextStyle(color: Colors.white, fontWeight: FontWeight.w600, fontSize: 15))),
        ]),
        if (session.customerConcern != null) ...[
          const SizedBox(height: 6),
          Text(session.customerConcern!, style: const TextStyle(color: Color(0xFF9CA3AF), fontSize: 13)),
        ],
        const SizedBox(height: 12),
        SizedBox(
          width: double.infinity,
          child: ElevatedButton.icon(
            onPressed: onStart,
            style: ElevatedButton.styleFrom(
              backgroundColor: const Color(0xFF3B82F6),
              padding: const EdgeInsets.symmetric(vertical: 12),
              shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
            ),
            icon: const Icon(Icons.mic, color: Colors.white, size: 18),
            label: const Text('Start Inspection', style: TextStyle(color: Colors.white, fontWeight: FontWeight.w600)),
          ),
        ),
      ]),
    );
  }
}

class _SessionTile extends StatelessWidget {
  final InspectionSession session;
  const _SessionTile({required this.session});

  @override
  Widget build(BuildContext context) {
    final statusColor = session.isCompleted ? const Color(0xFF10B981) : const Color(0xFF3B82F6);
    final statusBg = session.isCompleted ? const Color(0xFF064E3B) : const Color(0xFF1E3A5F);

    return GestureDetector(
      onTap: () => Navigator.push(context, MaterialPageRoute(builder: (_) => SessionScreen(sessionId: session.id))),
      child: Container(
        margin: const EdgeInsets.only(bottom: 12),
        padding: const EdgeInsets.all(16),
        decoration: BoxDecoration(
          color: const Color(0xFF111827),
          borderRadius: BorderRadius.circular(12),
          border: Border.all(color: const Color(0xFF1F2937)),
        ),
        child: Row(children: [
          Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Text(session.vehicleLabel, style: const TextStyle(color: Colors.white, fontWeight: FontWeight.w500)),
            const SizedBox(height: 4),
            Text(session.customerConcern ?? 'No concern noted', style: const TextStyle(color: Color(0xFF6B7280), fontSize: 13)),
            if (session.startedAt != null) ...[
              const SizedBox(height: 4),
              Text(session.startedAt!.toLocal().toString().substring(0, 16), style: const TextStyle(color: Color(0xFF4B5563), fontSize: 12)),
            ],
          ])),
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
            decoration: BoxDecoration(color: statusBg, borderRadius: BorderRadius.circular(20)),
            child: Text(session.status, style: TextStyle(color: statusColor, fontSize: 12, fontWeight: FontWeight.w500)),
          ),
        ]),
      ),
    );
  }
}
