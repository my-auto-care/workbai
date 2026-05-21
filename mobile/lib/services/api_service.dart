import 'dart:convert';
import 'dart:io';
import 'package:http/http.dart' as http;

const String kBaseUrl = 'https://app.workbai.autorepairsolutions.ai';

class ApiService {
  static final ApiService _i = ApiService._();
  factory ApiService() => _i;
  ApiService._();

  String? _authToken;
  void setAuthToken(String t) => _authToken = t;

  Map<String, String> get _h => {
    'Content-Type': 'application/json',
    if (_authToken != null) 'Authorization': 'Bearer $_authToken',
  };

  Future<List<Map<String, dynamic>>> getSessions({String? status, String? technicianId}) async {
    var url = '$kBaseUrl/sessions';
    final params = <String>[];
    if (status != null) params.add('status=$status');
    if (technicianId != null) params.add('technician_id=$technicianId');
    if (params.isNotEmpty) url += '?${params.join('&')}';
    final r = await http.get(Uri.parse(url), headers: _h);
    if (r.statusCode == 200) return List<Map<String, dynamic>>.from(jsonDecode(r.body));
    throw Exception('Failed to load sessions');
  }

  Future<Map<String, dynamic>> createSession({
    required String shopId,
    String? technicianId,
    String? vehicleId,
    int? vehicleYear,
    String? vehicleMake,
    String? vehicleModel,
    String? vehicleVin,
    int? vehicleMileage,
    String? checklistTemplateId,
    String? customerConcern,
    String? status,
  }) async {
    final r = await http.post(Uri.parse('$kBaseUrl/sessions'), headers: _h,
        body: jsonEncode({
          'shop_id': shopId,
          if (technicianId != null) 'technician_id': technicianId,
          if (vehicleId != null) 'vehicle_id': vehicleId,
          if (vehicleYear != null) 'vehicle_year': vehicleYear,
          if (vehicleMake != null) 'vehicle_make': vehicleMake,
          if (vehicleModel != null) 'vehicle_model': vehicleModel,
          if (vehicleVin != null) 'vehicle_vin': vehicleVin,
          if (vehicleMileage != null) 'vehicle_mileage': vehicleMileage,
          if (checklistTemplateId != null) 'checklist_template_id': checklistTemplateId,
          if (customerConcern != null) 'customer_concern': customerConcern,
          if (status != null) 'status': status,
        }));
    if (r.statusCode == 201) return jsonDecode(r.body);
    throw Exception('Failed to create session: ${r.body}');
  }

  Future<Map<String, dynamic>> startSession(String sessionId) async {
    final r = await http.post(Uri.parse('$kBaseUrl/sessions/$sessionId/start'), headers: _h);
    if (r.statusCode == 200) return jsonDecode(r.body);
    throw Exception('Failed to start session');
  }

  Future<Map<String, dynamic>> getReport(String sessionId) async {
    final r = await http.get(Uri.parse('$kBaseUrl/sessions/$sessionId/report'), headers: _h);
    if (r.statusCode == 200) return jsonDecode(r.body);
    throw Exception('Failed to load report');
  }

  Future<void> completeSession(String sessionId) async {
    final r = await http.post(Uri.parse('$kBaseUrl/sessions/$sessionId/complete'), headers: _h);
    if (r.statusCode != 200) throw Exception('Failed to complete session');
  }

  Future<Map<String, dynamic>> getVoiceToken({
    required String sessionId,
    required String technicianName,
    String language = 'en',
  }) async {
    final r = await http.post(Uri.parse('$kBaseUrl/voice/token'), headers: _h,
        body: jsonEncode({'session_id': sessionId, 'technician_name': technicianName, 'language': language}));
    if (r.statusCode == 200) return jsonDecode(r.body);
    throw Exception('Failed to get voice token');
  }

  Future<List<Map<String, dynamic>>> getChecklists() async {
    final r = await http.get(Uri.parse('$kBaseUrl/checklists'), headers: _h);
    if (r.statusCode == 200) return List<Map<String, dynamic>>.from(jsonDecode(r.body));
    throw Exception('Failed to load checklists');
  }

  Future<Map<String, dynamic>> getUploadUrl({
    required String sessionId,
    required String filename,
    String contentType = 'image/jpeg',
  }) async {
    final r = await http.post(Uri.parse('$kBaseUrl/media/upload-url'), headers: _h,
        body: jsonEncode({
          'session_id': sessionId,
          'filename': filename,
          'media_type': 'photo',
          'content_type': contentType,
        }));
    if (r.statusCode == 200) return jsonDecode(r.body);
    throw Exception('Failed to get upload URL: ${r.body}');
  }

  Future<void> attachMedia({
    required String sessionId,
    required String s3Key,
    String? findingId,
  }) async {
    final mediaId = DateTime.now().millisecondsSinceEpoch.toString();
    final r = await http.post(Uri.parse('$kBaseUrl/media/$mediaId/attach'), headers: _h,
        body: jsonEncode({
          'session_id': sessionId,
          's3_key': s3Key,
          'media_type': 'photo',
          if (findingId != null) 'finding_id': findingId,
        }));
    if (r.statusCode != 201) throw Exception('Failed to attach media: ${r.body}');
  }

  /// Send audio file to backend for AssemblyAI transcription + Claude cleanup
  Future<Map<String, dynamic>> processTranscript({
    required String sessionId,
    required String audioPath,
    String photoMarkers = '',
  }) async {
    final file = File(audioPath);
    final bytes = await file.readAsBytes();

    final request = http.MultipartRequest(
      'POST',
      Uri.parse('$kBaseUrl/sessions/$sessionId/process-transcript'),
    );
    if (_authToken != null) request.headers['Authorization'] = 'Bearer $_authToken';
    request.files.add(http.MultipartFile.fromBytes('audio', bytes,
        filename: 'inspection.m4a'));
    request.fields['photo_markers'] = photoMarkers;

    final streamed = await request.send().timeout(const Duration(minutes: 15));
    final body = await streamed.stream.bytesToString();
    if (streamed.statusCode == 200) return jsonDecode(body);
    throw Exception('Transcript processing failed: $body');
  }
}
