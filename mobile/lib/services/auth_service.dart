import 'package:auth0_flutter/auth0_flutter.dart';
import 'package:shared_preferences/shared_preferences.dart';

const String kAuth0Domain = 'dev-bs1544neeany10qn.us.auth0.com';
const String kAuth0ClientId = 'odoPUeNefjahtA3mXsNiSKoZzNSORQ6u';
const String kAuth0Scheme = 'workbay';

/// Must equal AUTH0_API_AUDIENCE on the backend. Without an audience Auth0
/// issues a token the Workbai API rejects (401).
/// Override per build: --dart-define=WORKBAI_API_AUDIENCE=https://...
const String kAuth0ApiAudience = String.fromEnvironment(
  'WORKBAI_API_AUDIENCE',
  defaultValue: 'https://api.workbai.autorepairsolutions.ai',
);

/// Key older builds used to store the pre-Auth0 "dev_token" placeholder.
const String _kLegacyTokenKey = 'access_token';

class AuthService {
  static final AuthService _i = AuthService._();
  factory AuthService() => _i;
  AuthService._();

  final Auth0 _auth0 = Auth0(kAuth0Domain, kAuth0ClientId);
  Credentials? _credentials;

  UserProfile? get user => _credentials?.user;
  bool get isLoggedIn => _credentials != null;

  /// Restores a saved Auth0 session, renewing it with the refresh token when
  /// needed. A placeholder token saved by an older build is discarded, never
  /// reused.
  Future<bool> tryRestoreSession() async {
    try {
      final prefs = await SharedPreferences.getInstance();
      await prefs.remove(_kLegacyTokenKey);
      if (!await _auth0.credentialsManager.hasValidCredentials()) return false;
      _credentials = await _auth0.credentialsManager.credentials();
      return true;
    } catch (_) {
      return false;
    }
  }

  /// Universal Login for the Workbai API audience. The credentials manager
  /// stores the result (including the refresh token) securely on the device.
  Future<void> login() async {
    _credentials = await _auth0.webAuthentication(scheme: kAuth0Scheme).login(
      audience: kAuth0ApiAudience,
      scopes: {'openid', 'profile', 'email', 'offline_access'},
    );
  }

  /// A current Workbai API access token, renewed when it has under a minute left.
  Future<String> accessToken() async {
    final credentials = await _auth0.credentialsManager.credentials(minTtl: 60);
    _credentials = credentials;
    return credentials.accessToken;
  }

  Future<void> logout() async {
    try {
      await _auth0.webAuthentication(scheme: kAuth0Scheme).logout();
    } catch (_) {}
    try {
      await _auth0.credentialsManager.clearCredentials();
    } catch (_) {}
    _credentials = null;
    final prefs = await SharedPreferences.getInstance();
    await prefs.remove(_kLegacyTokenKey);
  }
}
