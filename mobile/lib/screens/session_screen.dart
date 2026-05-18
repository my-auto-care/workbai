import 'package:flutter/material.dart';
import '../services/api_service.dart';

class SessionScreen extends StatefulWidget {
  final String sessionId;
  const SessionScreen({super.key, required this.sessionId});
  @override
  State<SessionScreen> createState() => _SessionScreenState();
}

class _SessionScreenState extends State<SessionScreen> {
  Map<String, dynamic>? _report;
  bool _loading = true;
  String? _error;

  @override
  void initState() { super.initState(); _load(); }

  Future<void> _load() async {
    setState(() { _loading = true; _error = null; });
    try {
      final data = await ApiService().getReport(widget.sessionId);
      setState(() { _report = data['report']; _loading = false; });
    } catch (e) {
      setState(() { _error = e.toString(); _loading = false; });
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFF0A0A0F),
      appBar: AppBar(
        backgroundColor: const Color(0xFF111827),
        title: const Text('Inspection Report', style: TextStyle(color: Colors.white)),
        iconTheme: const IconThemeData(color: Colors.white),
      ),
      body: _loading
          ? const Center(child: CircularProgressIndicator(color: Color(0xFF3B82F6)))
          : _error != null
              ? Center(child: Text(_error!, style: const TextStyle(color: Color(0xFF9CA3AF))))
              : _buildReport(),
    );
  }

  Widget _buildReport() {
    final r = _report!;
    final findings = (r['findings'] as List?) ?? [];

    return RefreshIndicator(
      onRefresh: _load,
      color: const Color(0xFF3B82F6),
      child: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          // Header card
          _card(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Row(mainAxisAlignment: MainAxisAlignment.spaceBetween, children: [
              Text('Session ${(r['session_id'] as String).substring(0, 8)}...',
                  style: const TextStyle(color: Colors.white, fontWeight: FontWeight.w600)),
              _statusChip(r['status'] ?? 'unknown'),
            ]),
            if (r['customer_concern'] != null) ...[
              const SizedBox(height: 12),
              const Text('Customer Concern', style: TextStyle(color: Color(0xFF6B7280), fontSize: 12)),
              const SizedBox(height: 4),
              Text(r['customer_concern'], style: const TextStyle(color: Color(0xFFD1D5DB))),
            ],
          ])),
          const SizedBox(height: 16),

          // Findings
          Text('Findings (${findings.length})',
              style: const TextStyle(color: Color(0xFF9CA3AF), fontSize: 13, fontWeight: FontWeight.w500)),
          const SizedBox(height: 8),
          if (findings.isEmpty)
            _card(child: const Center(
              child: Padding(
                padding: EdgeInsets.all(24),
                child: Text('No findings recorded', style: TextStyle(color: Color(0xFF4B5563))),
              ),
            ))
          else
            ...findings.map<Widget>((f) => Padding(
              padding: const EdgeInsets.only(bottom: 8),
              child: _card(child: Row(children: [
                Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                  Text(f['checklist_item_id'] ?? 'General finding',
                      style: const TextStyle(color: Colors.white, fontWeight: FontWeight.w500)),
                  if (f['transcript'] != null) ...[
                    const SizedBox(height: 6),
                    Text(f['transcript'], style: const TextStyle(color: Color(0xFF9CA3AF), fontSize: 13)),
                  ],
                ])),
                const SizedBox(width: 12),
                _conditionChip(f['condition'] ?? 'na'),
              ])),
            )),
        ],
      ),
    );
  }

  Widget _card({required Widget child}) => Container(
    padding: const EdgeInsets.all(16),
    decoration: BoxDecoration(
      color: const Color(0xFF111827),
      borderRadius: BorderRadius.circular(12),
      border: Border.all(color: const Color(0xFF1F2937)),
    ),
    child: child,
  );

  Widget _statusChip(String status) {
    final (color, bg) = status == 'completed'
        ? (const Color(0xFF10B981), const Color(0xFF064E3B))
        : (const Color(0xFF3B82F6), const Color(0xFF1E3A5F));
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
      decoration: BoxDecoration(color: bg, borderRadius: BorderRadius.circular(20)),
      child: Text(status, style: TextStyle(color: color, fontSize: 12, fontWeight: FontWeight.w500)),
    );
  }

  Widget _conditionChip(String condition) {
    final (color, bg) = switch (condition) {
      'good' => (const Color(0xFF10B981), const Color(0xFF064E3B)),
      'fair' => (const Color(0xFFFBBF24), const Color(0xFF451A03)),
      'poor' => (const Color(0xFFEF4444), const Color(0xFF7F1D1D)),
      _ => (const Color(0xFF6B7280), const Color(0xFF1F2937)),
    };
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
      decoration: BoxDecoration(color: bg, borderRadius: BorderRadius.circular(20)),
      child: Text(condition, style: TextStyle(color: color, fontSize: 12, fontWeight: FontWeight.w500)),
    );
  }
}
