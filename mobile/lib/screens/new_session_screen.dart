import 'package:flutter/material.dart';
import '../services/api_service.dart';
import 'inspection_screen.dart';

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
  final _mileageCtrl = TextEditingController();
  bool _loading = false;
  String? _error;

  // Hardcoded for MVP — will come from Auth0 user profile post-auth integration
  static const String _kShopId = '00000000-0000-0000-0000-000000000001';
  static const String _kTechId = '00000000-0000-0000-0000-000000000002';
  static const String _kVehicleId = '00000000-0000-0000-0000-000000000003';
  static const String _kChecklistId = '1bbf9892-68b8-4842-bfd9-7a4cd53dcca8';

  Future<void> _start() async {
    setState(() { _loading = true; _error = null; });
    try {
      final session = await ApiService().createSession(
        shopId: _kShopId,
        technicianId: _kTechId,
        vehicleId: _kVehicleId,
        checklistTemplateId: _kChecklistId,
        customerConcern: _concernCtrl.text.trim().isEmpty ? null : _concernCtrl.text.trim(),
      );
      if (mounted) {
        Navigator.pushReplacement(context, MaterialPageRoute(
          builder: (_) => InspectionScreen(sessionId: session['id']),
        ));
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
          const Text('Vehicle', style: TextStyle(color: Color(0xFF9CA3AF), fontSize: 13, fontWeight: FontWeight.w500)),
          const SizedBox(height: 12),
          Row(children: [
            Expanded(child: _field(_yearCtrl, 'Year', TextInputType.number)),
            const SizedBox(width: 8),
            Expanded(child: _field(_makeCtrl, 'Make')),
            const SizedBox(width: 8),
            Expanded(child: _field(_modelCtrl, 'Model')),
          ]),
          const SizedBox(height: 12),
          _field(_mileageCtrl, 'Mileage', TextInputType.number),
          const SizedBox(height: 24),
          const Text('Customer Concern', style: TextStyle(color: Color(0xFF9CA3AF), fontSize: 13, fontWeight: FontWeight.w500)),
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
          SizedBox(
            width: double.infinity,
            child: ElevatedButton.icon(
              onPressed: _loading ? null : _start,
              style: ElevatedButton.styleFrom(
                backgroundColor: const Color(0xFF3B82F6),
                padding: const EdgeInsets.symmetric(vertical: 16),
                shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
              ),
              icon: _loading
                  ? const SizedBox(width: 18, height: 18, child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white))
                  : const Icon(Icons.mic, color: Colors.white),
              label: Text(_loading ? 'Starting...' : 'Begin Inspection',
                  style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w600, color: Colors.white)),
            ),
          ),
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
