import 'dart:io';
import 'package:flutter/material.dart';
import 'package:image_picker/image_picker.dart';
import '../services/api_service.dart';
import 'inspection_screen.dart';
import 'transcript_screen.dart';

class NewSessionScreen extends StatefulWidget {
  const NewSessionScreen({super.key});
  @override
  State<NewSessionScreen> createState() => _NewSessionScreenState();
}

class _NewSessionScreenState extends State<NewSessionScreen> {
  final _concernCtrl  = TextEditingController();
  final _yearCtrl     = TextEditingController();
  final _makeCtrl     = TextEditingController();
  final _modelCtrl    = TextEditingController();
  final _vinCtrl      = TextEditingController();
  final _mileageCtrl  = TextEditingController();
  bool _loading  = false;
  bool _scanning = false;
  String? _error;

  static const String _kShopId       = '00000000-0000-0000-0000-000000000001';
  static const String _kTechId       = '00000000-0000-0000-0000-000000000002';
  static const String _kChecklistId  = '1bbf9892-68b8-4842-bfd9-7a4cd53dcca8';

  // ── Auto-fill helpers ──────────────────────────────────────────────────

  void _fillFromVehicleData(Map<String, dynamic> data) {
    final v = data['vehicle'] as Map<String, dynamic>? ?? data;
    final year  = v['year']?.toString()  ?? '';
    final make  = v['make']?.toString()  ?? '';
    final model = v['model']?.toString() ?? '';
    final vin   = v['vin']?.toString()   ?? '';
    if (year.isNotEmpty)  _yearCtrl.text  = year;
    if (make.isNotEmpty)  _makeCtrl.text  = make;
    if (model.isNotEmpty) _modelCtrl.text = model;
    if (vin.isNotEmpty)   _vinCtrl.text   = vin;
  }

  void _showSnack(String msg, {bool error = false}) {
    if (!mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(SnackBar(
      content: Text(msg),
      backgroundColor: error ? const Color(0xFF7F1D1D) : const Color(0xFF064E3B),
      duration: const Duration(seconds: 4),
    ));
  }

  // ── Scan plate ─────────────────────────────────────────────────────────

  Future<void> _scanPlate() async {
    final picker = ImagePicker();
    final picked = await picker.pickImage(source: ImageSource.camera, imageQuality: 90);
    if (picked == null) return;
    setState(() => _scanning = true);
    try {
      final result = await ApiService().ocrPlateFromFile(File(picked.path), state: 'FL');
      final vin    = result['vehicle']?['vin']?.toString() ?? result['vin']?.toString() ?? '';
      final make   = result['vehicle']?['make']?.toString() ?? '';
      final model  = result['vehicle']?['model']?.toString() ?? '';
      final year   = result['vehicle']?['year']?.toString() ?? '';
      _fillFromVehicleData(result);
      if (vin.isNotEmpty || make.isNotEmpty) {
        _showSnack('✅ Vehicle identified: $year $make $model');
      } else {
        final plate = result['plate']?.toString() ?? '';
        _showSnack('Plate "$plate" detected but VIN not found — fill in manually.', error: true);
      }
    } catch (e) {
      _showSnack('Plate scan failed: $e', error: true);
    } finally {
      if (mounted) setState(() => _scanning = false);
    }
  }

  // ── Scan VIN tag ───────────────────────────────────────────────────────

  Future<void> _scanVin() async {
    final picker = ImagePicker();
    final picked = await picker.pickImage(source: ImageSource.camera, imageQuality: 90);
    if (picked == null) return;
    setState(() => _scanning = true);
    try {
      final result = await ApiService().ocrVinFromFile(File(picked.path));
      _fillFromVehicleData(result);
      final v    = result['vehicle'] as Map<String, dynamic>? ?? {};
      final year = v['year']?.toString() ?? '';
      final make = v['make']?.toString() ?? '';
      final model= v['model']?.toString() ?? '';
      _showSnack('✅ VIN scanned: $year $make $model');
    } catch (e) {
      _showSnack('VIN scan failed: $e', error: true);
    } finally {
      if (mounted) setState(() => _scanning = false);
    }
  }

  // ── Start session ──────────────────────────────────────────────────────

  Future<void> _start(String mode) async {
    setState(() { _loading = true; _error = null; });
    try {
      final year    = int.tryParse(_yearCtrl.text.trim());
      final mileage = int.tryParse(_mileageCtrl.text.trim().replaceAll(',', ''));
      final session = await ApiService().createSession(
        shopId: _kShopId,
        technicianId: _kTechId,
        vehicleYear:  year,
        vehicleMake:  _makeCtrl.text.trim().isEmpty  ? null : _makeCtrl.text.trim(),
        vehicleModel: _modelCtrl.text.trim().isEmpty ? null : _modelCtrl.text.trim(),
        vehicleVin:   _vinCtrl.text.trim().isEmpty   ? null : _vinCtrl.text.trim(),
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

  // ── Build ──────────────────────────────────────────────────────────────

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

          // ── VEHICLE INFO header ─────────────────────────────────────
          const Text('VEHICLE INFO', style: TextStyle(color: Color(0xFF9CA3AF), fontSize: 12, fontWeight: FontWeight.w600, letterSpacing: 1)),
          const SizedBox(height: 12),

          // ── Scan buttons ────────────────────────────────────────────
          Row(children: [
            Expanded(
              child: _ScanButton(
                icon: Icons.camera_alt_outlined,
                label: _scanning ? 'Scanning…' : 'Scan Plate',
                color: const Color(0xFF3B82F6),
                loading: _scanning,
                onTap: _scanning ? null : _scanPlate,
              ),
            ),
            const SizedBox(width: 10),
            Expanded(
              child: _ScanButton(
                icon: Icons.qr_code_scanner,
                label: _scanning ? 'Scanning…' : 'Scan VIN Tag',
                color: const Color(0xFF10B981),
                loading: _scanning,
                onTap: _scanning ? null : _scanVin,
              ),
            ),
          ]),
          const SizedBox(height: 12),

          // ── Manual fields ───────────────────────────────────────────
          Row(children: [
            Expanded(child: _field(_yearCtrl,  'Year',  TextInputType.number)),
            const SizedBox(width: 8),
            Expanded(child: _field(_makeCtrl,  'Make')),
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

          // ── CUSTOMER CONCERN ────────────────────────────────────────
          const Text('CUSTOMER CONCERN', style: TextStyle(color: Color(0xFF9CA3AF), fontSize: 12, fontWeight: FontWeight.w600, letterSpacing: 1)),
          const SizedBox(height: 12),
          TextField(
            controller: _concernCtrl,
            maxLines: 3,
            style: const TextStyle(color: Colors.white),
            decoration: InputDecoration(
              hintText: 'e.g. Noise when braking, check engine light on…',
              hintStyle: const TextStyle(color: Color(0xFF4B5563)),
              filled: true,
              fillColor: const Color(0xFF111827),
              border:        OutlineInputBorder(borderRadius: BorderRadius.circular(10), borderSide: const BorderSide(color: Color(0xFF1F2937))),
              enabledBorder: OutlineInputBorder(borderRadius: BorderRadius.circular(10), borderSide: const BorderSide(color: Color(0xFF1F2937))),
              focusedBorder: OutlineInputBorder(borderRadius: BorderRadius.circular(10), borderSide: const BorderSide(color: Color(0xFF3B82F6))),
            ),
          ),
          const SizedBox(height: 32),

          // ── SELECT MODE ─────────────────────────────────────────────
          const Text('SELECT MODE', style: TextStyle(color: Color(0xFF9CA3AF), fontSize: 12, fontWeight: FontWeight.w600, letterSpacing: 1)),
          const SizedBox(height: 12),

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
        border:        OutlineInputBorder(borderRadius: BorderRadius.circular(10), borderSide: const BorderSide(color: Color(0xFF1F2937))),
        enabledBorder: OutlineInputBorder(borderRadius: BorderRadius.circular(10), borderSide: const BorderSide(color: Color(0xFF1F2937))),
        focusedBorder: OutlineInputBorder(borderRadius: BorderRadius.circular(10), borderSide: const BorderSide(color: Color(0xFF3B82F6))),
        contentPadding: const EdgeInsets.symmetric(horizontal: 12, vertical: 12),
      ),
    );
  }
}

// ── Scan button widget ────────────────────────────────────────────────────

class _ScanButton extends StatelessWidget {
  final IconData icon;
  final String label;
  final Color color;
  final bool loading;
  final VoidCallback? onTap;

  const _ScanButton({
    required this.icon,
    required this.label,
    required this.color,
    required this.loading,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onTap,
      child: Container(
        padding: const EdgeInsets.symmetric(vertical: 13, horizontal: 12),
        decoration: BoxDecoration(
          color: color.withOpacity(0.08),
          borderRadius: BorderRadius.circular(10),
          border: Border.all(color: color.withOpacity(0.6), width: 1.5),
        ),
        child: Row(mainAxisAlignment: MainAxisAlignment.center, children: [
          if (loading)
            SizedBox(width: 18, height: 18, child: CircularProgressIndicator(strokeWidth: 2, color: color))
          else
            Icon(icon, color: color, size: 18),
          const SizedBox(width: 8),
          Text(label, style: TextStyle(color: color, fontWeight: FontWeight.w600, fontSize: 13)),
        ]),
      ),
    );
  }
}

// ── Mode button widget ────────────────────────────────────────────────────

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
