import 'package:flutter/material.dart';
import '../models/session.dart';
import '../services/api_service.dart';
import '../services/auth_service.dart';
import 'new_session_screen.dart';
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

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() { _loading = true; _error = null; });
    try {
      final data = await ApiService().getSessions();
      setState(() { _sessions = data.map(InspectionSession.fromJson).toList(); _loading = false; });
    } catch (e) {
      setState(() { _error = e.toString(); _loading = false; });
    }
  }

  Future<void> _logout() async {
    await AuthService().logout();
    if (mounted) Navigator.pushReplacement(context, MaterialPageRoute(builder: (_) => const LoginScreen()));
  }

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
          final result = await Navigator.push(context, MaterialPageRoute(builder: (_) => const NewSessionScreen()));
          if (result == true) _load();
        },
        backgroundColor: const Color(0xFF3B82F6),
        icon: const Icon(Icons.mic, color: Colors.white),
        label: const Text('Start Inspection', style: TextStyle(color: Colors.white, fontWeight: FontWeight.w600)),
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
              : _sessions.isEmpty
                  ? Center(child: Column(mainAxisAlignment: MainAxisAlignment.center, children: [
                      const Icon(Icons.car_repair, size: 64, color: Color(0xFF374151)),
                      const SizedBox(height: 16),
                      const Text('No inspections yet', style: TextStyle(color: Color(0xFF6B7280), fontSize: 18)),
                      const SizedBox(height: 8),
                      const Text('Tap Start Inspection to begin', style: TextStyle(color: Color(0xFF4B5563), fontSize: 14)),
                    ]))
                  : RefreshIndicator(
                      onRefresh: _load,
                      color: const Color(0xFF3B82F6),
                      child: ListView.builder(
                        padding: const EdgeInsets.all(16),
                        itemCount: _sessions.length,
                        itemBuilder: (_, i) => _SessionTile(session: _sessions[i]),
                      ),
                    ),
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
        child: Row(
          children: [
            Expanded(
              child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                Text('Session ${session.id.substring(0, 8)}...', style: const TextStyle(color: Colors.white, fontWeight: FontWeight.w500)),
                const SizedBox(height: 4),
                Text(session.customerConcern ?? 'No concern noted', style: const TextStyle(color: Color(0xFF6B7280), fontSize: 13)),
                if (session.startedAt != null) ...[
                  const SizedBox(height: 4),
                  Text(session.startedAt!.toLocal().toString().substring(0, 16), style: const TextStyle(color: Color(0xFF4B5563), fontSize: 12)),
                ],
              ]),
            ),
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
              decoration: BoxDecoration(color: statusBg, borderRadius: BorderRadius.circular(20)),
              child: Text(session.status, style: TextStyle(color: statusColor, fontSize: 12, fontWeight: FontWeight.w500)),
            ),
          ],
        ),
      ),
    );
  }
}
