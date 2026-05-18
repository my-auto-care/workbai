import 'dart:convert';
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

  Future<List<Map<String, dynamic>>> getSessions() async {
    final r = await http.get(Uri.parse('$kBaseUrl/sessions'), headers: _h);
    if (r.statusCode == 200) return List<Map<String, dynamic>>.from(jsonDecode(r.body));
    throw Exception('Failed to load sessions');
  }

  Future<Map<String, dynamic>> createSession({
    required String shopId,
    required String technicianId,
    required String vehicleId,
    String? checklistTemplateId,
    String? customerConcern,
  }) async {
    final r = await http.post(Uri.parse('$kBaseUrl/sessions'), headers: _h,
        body: jsonEncode({
          'shop_id': shopId,
          'technician_id': technicianId,
          'vehicle_id': vehicleId,
          if (checklistTemplateId != null) 'checklist_template_id': checklistTemplateId,
          if (customerConcern != null) 'customer_concern': customerConcern,
        }));
    if (r.statusCode == 201) return jsonDecode(r.body);
    throw Exception('Failed to create session: ${r.body}');
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
}
