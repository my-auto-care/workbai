import 'package:flutter/material.dart';
import '../services/api_service.dart';
import 'inspection_screen.dart';
import 'transcript_screen.dart';

class NewSessionScreen extends StatefulWidget {
  const NewSessionScreen({super.key});
  @override
  State<NewSessionScreen> createState() => _NewSessionScreenState();
}

class _NewSessionScreenState extends State<NewSessionScreen> {
  final _concernCtrl = TextEditingController();
  final _yearCtrl = TextEditingController();
  final _makeCtrl = TextEditingController();
  final _modelCtrl = TextEditingController();
  final _vinCtrl = TextEditingController();
  final _mileageCtrl = TextEditingController();
  bool _loading = false;
  String? _error;

  static const String _kShopId = '00000000-0000-0000-0000-000000000001';
  static const String _kTechId = '00000000-0000-0000-0000-000000000002';
  static const String _kChecklistId = '1bbf9892-68b8-4842-bfd9-7a4cd53dcca8';

  Future<void> _start(String mode) async {
    setState(() { _loading = true; _error = null; });
    try {
      final year = int.tryParse(_yearCtrl.text.trim());
      final mileage = int.tryParse(_mileageCtrl.text.trim().replaceAll(',', ''));
      final session = await ApiService().createSession(
        shopId: _kShopId,
        technicianId: _kTechId,
        vehicleYear: year,
        vehicleMake: _makeCtrl.text.trim().isEmpty ? null : _makeCtrl.text.trim(),
        vehicleModel: _modelCtrl.text.trim().isEmpty ? null : _modelCtrl.text.trim(),
        vehicleVin: _vinCtrl.text.trim().isEmpty ? null : _vinCtrl.text.trim(),
        vehicleMileage: mileage,
        checklistTemplateId: _kChecklistId,
        customerConcern: _concernCtrl.text.trim().isEmpty ? null : _concernCtrl.text.trim(),
      );
      if (mounted) {
        if (mode == 'ai') {
          Navigator.pushReplacement(context, MaterialPageRoute(
            builder: (_) => InspectionScreen(sessionId: session['id']),
          ));
        } else {
          Navigator.pushReplacement(context, MaterialPageRoute(
            builder: (_) => TranscriptScreen(sessionId: session['id']),
          ));
        }
      }
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
        title: const Text('New Inspection', style: TextStyle(color: Colors.white)),
        iconTheme: const IconThemeData(color: Colors.white),
      ),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(24),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          if (_error != null)
            Container(
              padding: const EdgeInsets.all(12),
              margin: const EdgeInsets.only(bottom: 16),
              decoration: BoxDecoration(color: const Color(0xFF7F1D1D), borderRadius: BorderRadius.circular(8)),
              child: Text(_error!, style: const TextStyle(color: Color(0xFFFCA5A5), fontSize: 13)),
            ),

          const Text('VEHICLE INFO', style: TextStyle(color: Color(0xFF9CA3AF), fontSize: 12, fontWeight: FontWeight.w600, letterSpacing: 1)),
          const SizedBox(height: 12),
          Row(children: [
            Expanded(child: _field(_yearCtrl, 'Year', TextInputType.number)),
            const SizedBox(width: 8),
            Expanded(child: _field(_makeCtrl, 'Make')),
            const SizedBox(width: 8),
            Expanded(child: _field(_modelCtrl, 'Model')),
          ]),
          const SizedBox(height: 8),
          Row(children: [
            Expanded(child: _field(_mileageCtrl, 'Mileage', TextInputType.number)),
            const SizedBox(width: 8),
            Expanded(child: _field(_vinCtrl, 'VIN (optional)')),
          ]),
          const SizedBox(height: 24),

          const Text('CUSTOMER CONCERN', style: TextStyle(color: Color(0xFF9CA3AF), fontSize: 12, fontWeight: FontWeight.w600, letterSpacing: 1)),
          const SizedBox(height: 12),
          TextField(
            controller: _concernCtrl,
            maxLines: 3,
            style: const TextStyle(color: Colors.white),
            decoration: InputDecoration(
              hintText: 'e.g. Noise when braking, check engine light on...',
              hintStyle: const TextStyle(color: Color(0xFF4B5563)),
              filled: true,
              fillColor: const Color(0xFF111827),
              border: OutlineInputBorder(borderRadius: BorderRadius.circular(10), borderSide: const BorderSide(color: Color(0xFF1F2937))),
              enabledBorder: OutlineInputBorder(borderRadius: BorderRadius.circular(10), borderSide: const BorderSide(color: Color(0xFF1F2937))),
              focusedBorder: OutlineInputBorder(borderRadius: BorderRadius.circular(10), borderSide: const BorderSide(color: Color(0xFF3B82F6))),
            ),
          ),
          const SizedBox(height: 32),

          const Text('SELECT MODE', style: TextStyle(color: Color(0xFF9CA3AF), fontSize: 12, fontWeight: FontWeight.w600, letterSpacing: 1)),
          const SizedBox(height: 12),

          // AI Conversation button
          _ModeButton(
            icon: Icons.smart_toy_outlined,
            title: 'AI Conversation',
            subtitle: 'AI guides you through the inspection step by step with vehicle-specific questions',
            color: const Color(0xFF3B82F6),
            bg: const Color(0xFF1E3A5F),
            border: const Color(0xFF3B82F6),
            loading: _loading,
            onTap: () => _start('ai'),
          ),
          const SizedBox(height: 12),

          // Transcript Only button
          _ModeButton(
            icon: Icons.mic_none,
            title: 'Transcript Only',
            subtitle: 'Speak freely at your own pace — everything is transcribed live and documented',
            color: const Color(0xFF10B981),
            bg: const Color(0xFF064E3B),
            border: const Color(0xFF10B981),
            loading: _loading,
            onTap: () => _start('transcript'),
          ),

          const SizedBox(height: 80),
        ]),
      ),
    );
  }

  Widget _field(TextEditingController ctrl, String hint, [TextInputType? type]) {
    return TextField(
      controller: ctrl,
      keyboardType: type,
      style: const TextStyle(color: Colors.white),
      decoration: InputDecoration(
        hintText: hint,
        hintStyle: const TextStyle(color: Color(0xFF4B5563)),
        filled: true,
        fillColor: const Color(0xFF111827),
        border: OutlineInputBorder(borderRadius: BorderRadius.circular(10), borderSide: const BorderSide(color: Color(0xFF1F2937))),
        enabledBorder: OutlineInputBorder(borderRadius: BorderRadius.circular(10), borderSide: const BorderSide(color: Color(0xFF1F2937))),
        focusedBorder: OutlineInputBorder(borderRadius: BorderRadius.circular(10), borderSide: const BorderSide(color: Color(0xFF3B82F6))),
        contentPadding: const EdgeInsets.symmetric(horizontal: 12, vertical: 12),
      ),
    );
  }
}

class _ModeButton extends StatelessWidget {
  final IconData icon;
  final String title;
  final String subtitle;
  final Color color;
  final Color bg;
  final Color border;
  final bool loading;
  final VoidCallback onTap;

  const _ModeButton({
    required this.icon, required this.title, required this.subtitle,
    required this.color, required this.bg, required this.border,
    required this.loading, required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: loading ? null : onTap,
      child: Container(
        width: double.infinity,
        padding: const EdgeInsets.all(20),
        decoration: BoxDecoration(
          color: bg,
          borderRadius: BorderRadius.circular(14),
          border: Border.all(color: border, width: 1.5),
        ),
        child: Row(children: [
          Container(
            width: 48, height: 48,
            decoration: BoxDecoration(color: color.withOpacity(0.2), borderRadius: BorderRadius.circular(12)),
            child: Icon(icon, color: color, size: 26),
          ),
          const SizedBox(width: 16),
          Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Text(title, style: TextStyle(color: color, fontWeight: FontWeight.w700, fontSize: 16)),
            const SizedBox(height: 4),
            Text(subtitle, style: const TextStyle(color: Color(0xFF9CA3AF), fontSize: 13, height: 1.4)),
          ])),
          if (loading)
            SizedBox(width: 20, height: 20, child: CircularProgressIndicator(strokeWidth: 2, color: color))
          else
            Icon(Icons.arrow_forward_ios, color: color, size: 16),
        ]),
      ),
    );
  }
}
