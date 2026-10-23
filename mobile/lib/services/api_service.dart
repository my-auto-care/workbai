import 'dart:convert';
import 'dart:io';
import 'package:http/http.dart' as http;
import 'package:uuid/uuid.dart';

import 'auth_service.dart';

const String kBaseUrl = String.fromEnvironment(
  'WORKBAI_API_BASE_URL',
  defaultValue: 'https://app.workbai.autorepairsolutions.ai',
);

class ApiService {
  static final ApiService _i = ApiService._();
  factory ApiService() => _i;
  ApiService._();

  /// Every request carries the signed-in technician's Auth0 access token.
  /// Shop and technician are derived by the server from that token; the app
  /// never sends them.
  Future<Map<String, String>> _headers({bool json = true}) async {
    final token = await AuthService().accessToken();
    return {
      if (json) 'Content-Type': 'application/json',
      'Authorization': 'Bearer $token',
    };
  }

  static String _detail(String body) {
    try {
      final decoded = jsonDecode(body);
      if (decoded is Map && decoded['detail'] is String) return decoded['detail'] as String;
    } catch (_) {}
    return body;
  }

  static Exception _failure(String what, int statusCode, String body) =>
      Exception('$what ($statusCode): ${_detail(body)}');

  Future<List<Map<String, dynamic>>> getSessions({String? status, String? technicianId}) async {
    var url = '$kBaseUrl/sessions';
    final params = <String>[];
    if (status != null) params.add('status=$status');
    if (technicianId != null) params.add('technician_id=$technicianId');
    if (params.isNotEmpty) url += '?${params.join('&')}';
    final r = await http.get(Uri.parse(url), headers: await _headers());
    if (r.statusCode == 200) return List<Map<String, dynamic>>.from(jsonDecode(r.body));
    throw _failure('Failed to load inspections', r.statusCode, r.body);
  }

  /// Starts the technician's own (non-template) voice/transcript inspection.
  /// The server assigns the shop, the technician and the checklist.
  Future<Map<String, dynamic>> createSession({
    String? vehicleId,
    int? vehicleYear,
    String? vehicleMake,
    String? vehicleModel,
    String? vehicleVin,
    int? vehicleMileage,
    String? customerConcern,
  }) async {
    final r = await http.post(Uri.parse('$kBaseUrl/sessions'), headers: await _headers(),
        body: jsonEncode({
          if (vehicleId != null) 'vehicle_id': vehicleId,
          if (vehicleYear != null) 'vehicle_year': vehicleYear,
          if (vehicleMake != null) 'vehicle_make': vehicleMake,
          if (vehicleModel != null) 'vehicle_model': vehicleModel,
          if (vehicleVin != null) 'vehicle_vin': vehicleVin,
          if (vehicleMileage != null) 'vehicle_mileage': vehicleMileage,
          if (customerConcern != null) 'customer_concern': customerConcern,
        }));
    if (r.statusCode == 201) return jsonDecode(r.body);
    throw _failure('Failed to start inspection', r.statusCode, r.body);
  }

  Future<Map<String, dynamic>> startSession(String sessionId) async {
    final r = await http.post(Uri.parse('$kBaseUrl/sessions/$sessionId/start'), headers: await _headers());
    if (r.statusCode == 200) return jsonDecode(r.body);
    throw _failure('Failed to start inspection', r.statusCode, r.body);
  }

  Future<Map<String, dynamic>> getReport(String sessionId) async {
    final r = await http.get(Uri.parse('$kBaseUrl/sessions/$sessionId/report'), headers: await _headers());
    if (r.statusCode == 200) return jsonDecode(r.body);
    throw _failure('Failed to load report', r.statusCode, r.body);
  }

  Future<void> completeSession(String sessionId) async {
    final r = await http.post(Uri.parse('$kBaseUrl/sessions/$sessionId/complete'), headers: await _headers());
    if (r.statusCode != 200) throw _failure('Failed to complete inspection', r.statusCode, r.body);
  }

  Future<Map<String, dynamic>> getVoiceToken({
    required String sessionId,
    String language = 'en',
  }) async {
    final r = await http.post(Uri.parse('$kBaseUrl/voice/token'), headers: await _headers(),
        body: jsonEncode({'session_id': sessionId, 'language': language}));
    if (r.statusCode == 200) return jsonDecode(r.body);
    throw _failure('Failed to start voice inspection', r.statusCode, r.body);
  }

  Future<Map<String, dynamic>> getUploadUrl({
    required String sessionId,
    required String filename,
    String contentType = 'image/jpeg',
  }) async {
    final r = await http.post(Uri.parse('$kBaseUrl/media/upload-url'), headers: await _headers(),
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
    final mediaId = const Uuid().v4();
    final r = await http.post(Uri.parse('$kBaseUrl/media/$mediaId/attach'), headers: await _headers(),
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
    request.headers.addAll(await _headers(json: false));
    request.files.add(http.MultipartFile.fromBytes('audio', bytes, filename: 'inspection.m4a'));
    request.fields['photo_markers'] = photoMarkers;
    final streamed = await request.send().timeout(const Duration(minutes: 15));
    final body = await streamed.stream.bytesToString();
    if (streamed.statusCode == 200) return jsonDecode(body);
    throw Exception('Transcript processing failed: $body');
  }

  // ── Vehicle Lookup — VIN decode ──────────────────────────────────────────

  /// Decode a VIN → full vehicle info + recalls + maintenance + repairs + warranty
  Future<Map<String, dynamic>> decodeVin(String vin) async {
    final request = http.MultipartRequest('POST', Uri.parse('$kBaseUrl/vehicle/decode-vin'));
    request.headers.addAll(await _headers(json: false));
    request.fields['vin'] = vin.trim().toUpperCase();
    final streamed = await request.send().timeout(const Duration(seconds: 30));
    final body = await streamed.stream.bytesToString();
    if (streamed.statusCode == 200) return jsonDecode(body);
    throw Exception('VIN decode failed: $body');
  }

  // ── Vehicle Lookup — License plate photo → auto-fill ────────────────────

  /// Photo of license plate → OCR → plate-to-VIN → full vehicle decode
  Future<Map<String, dynamic>> ocrPlateFromFile(File image, {String state = 'FL'}) async {
    final bytes = await image.readAsBytes();
    final filename = image.path.split('/').last;
    final request = http.MultipartRequest('POST', Uri.parse('$kBaseUrl/vehicle/lookup-plate-vin'));
    request.headers.addAll(await _headers(json: false));
    request.fields['state'] = state;
    request.fields['region'] = 'us';
    request.files.add(http.MultipartFile.fromBytes('image', bytes, filename: filename));
    final streamed = await request.send().timeout(const Duration(seconds: 30));
    final body = await streamed.stream.bytesToString();
    if (streamed.statusCode == 200) return jsonDecode(body);
    throw Exception('Plate OCR failed: $body');
  }

  // ── Vehicle Lookup — VIN tag photo → auto-fill ───────────────────────────

  /// Photo of VIN sticker/tag → VIN OCR → full vehicle decode
  Future<Map<String, dynamic>> ocrVinFromFile(File image) async {
    final bytes = await image.readAsBytes();
    final filename = image.path.split('/').last;
    final request = http.MultipartRequest('POST', Uri.parse('$kBaseUrl/vehicle/ocr-vin'));
    request.headers.addAll(await _headers(json: false));
    request.files.add(http.MultipartFile.fromBytes('image', bytes, filename: filename));
    final streamed = await request.send().timeout(const Duration(seconds: 30));
    final body = await streamed.stream.bytesToString();
    if (streamed.statusCode == 200) return jsonDecode(body);
    throw Exception('VIN OCR failed: $body');
  }
}
