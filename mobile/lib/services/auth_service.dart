import 'package:auth0_flutter/auth0_flutter.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'api_service.dart';

const String kAuth0Domain = 'dev-bs1544neeany10qn.us.auth0.com';
const String kAuth0ClientId = 'odoPUeNefjahtA3mXsNiSKoZzNSORQ6u';

class AuthService {
  static final AuthService _i = AuthService._();
  factory AuthService() => _i;
  AuthService._();

  final _auth0 = Auth0(kAuth0Domain, kAuth0ClientId);
  Credentials? _credentials;

  UserProfile? get user => _credentials?.user;
  bool get isLoggedIn => _credentials != null;

  Future<bool> tryRestoreSession() async {
    try {
      final prefs = await SharedPreferences.getInstance();
      final token = prefs.getString('access_token');
      if (token != null) {
        ApiService().setAuthToken(token);
        return true;
      }
    } catch (_) {}
    return false;
  }

  Future<void> login() async {
    _credentials = await _auth0.webAuthentication(scheme: 'workbay').login(
      // No audience — use default Auth0 scopes only, no custom API
      scopes: {'openid', 'profile', 'email', 'offline_access'},
    );
    ApiService().setAuthToken(_credentials!.accessToken);
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString('access_token', _credentials!.accessToken);
  }

  Future<void> logout() async {
    try {
      await _auth0.webAuthentication(scheme: 'workbay').logout();
    } catch (_) {}
    _credentials = null;
    final prefs = await SharedPreferences.getInstance();
    await prefs.remove('access_token');
  }
}
