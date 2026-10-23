class InspectionSession {
  final String id;
  final String status;
  final String? customerConcern;
  final String? vehicleYear;
  final String? vehicleMake;
  final String? vehicleModel;
  final String? vehicleVin;
  final DateTime? startedAt;
  final DateTime? completedAt;
  /// Set when the visit was created by Check-in with the shop's controlled
  /// inspection checklist (a template snapshot); null for the app's own sessions.
  final int? templateVersion;

  InspectionSession({
    required this.id,
    required this.status,
    this.customerConcern,
    this.vehicleYear,
    this.vehicleMake,
    this.vehicleModel,
    this.vehicleVin,
    this.startedAt,
    this.completedAt,
    this.templateVersion,
  });

  factory InspectionSession.fromJson(Map<String, dynamic> j) => InspectionSession(
    id: j['id'],
    status: j['status'],
    customerConcern: j['customer_concern'],
    vehicleYear: j['vehicle_year']?.toString(),
    vehicleMake: j['vehicle_make'],
    vehicleModel: j['vehicle_model'],
    vehicleVin: j['vehicle_vin'],
    startedAt: j['started_at'] != null ? DateTime.tryParse(j['started_at']) : null,
    completedAt: j['completed_at'] != null ? DateTime.tryParse(j['completed_at']) : null,
    templateVersion: j['template_version'] is int ? j['template_version'] as int : null,
  );

  bool get isActive => status == 'in_progress';
  bool get isCompleted => status == 'completed';
  bool get isPending => status == 'pending';
  bool get isTemplateDriven => templateVersion != null;

  String get vehicleLabel {
    final parts = [vehicleYear, vehicleMake, vehicleModel].where((p) => p != null && p.isNotEmpty).toList();
    return parts.isNotEmpty ? parts.join(' ') : 'Unknown Vehicle';
  }
}

class Finding {
  final String id;
  final String? checklistItemId;
  final String? transcript;
  final String condition;

  Finding({required this.id, this.checklistItemId, this.transcript, required this.condition});

  factory Finding.fromJson(Map<String, dynamic> j) => Finding(
    id: j['id'],
    checklistItemId: j['checklist_item_id'],
    transcript: j['transcript'],
    condition: j['condition'] ?? 'na',
  );
}
