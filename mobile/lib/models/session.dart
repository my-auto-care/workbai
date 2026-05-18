class InspectionSession {
  final String id;
  final String status;
  final String? customerConcern;
  final DateTime? startedAt;
  final DateTime? completedAt;

  InspectionSession({
    required this.id,
    required this.status,
    this.customerConcern,
    this.startedAt,
    this.completedAt,
  });

  factory InspectionSession.fromJson(Map<String, dynamic> j) => InspectionSession(
    id: j['id'],
    status: j['status'],
    customerConcern: j['customer_concern'],
    startedAt: j['started_at'] != null ? DateTime.tryParse(j['started_at']) : null,
    completedAt: j['completed_at'] != null ? DateTime.tryParse(j['completed_at']) : null,
  );

  bool get isActive => status == 'in_progress';
  bool get isCompleted => status == 'completed';
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
