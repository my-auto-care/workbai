# Workbay AI — Mobile App (Android)

Flutter app for hands-free automotive inspection via voice.

## Setup

1. Install Flutter SDK >= 3.3.0
2. `flutter pub get`
3. Set Auth0 client ID in `lib/services/auth_service.dart` (`kAuth0ClientId`)
4. Run: `flutter run` (device/emulator connected)

## Build APK

```bash
flutter build apk --release
# Output: build/app/outputs/flutter-apk/app-release.apk
```

## Architecture

- `main.dart` — entry, splash, auth restore
- `screens/login_screen.dart` — Auth0 login
- `screens/home_screen.dart` — session list
- `screens/new_session_screen.dart` — start inspection form
- `screens/inspection_screen.dart` — live voice session (LiveKit)
- `screens/session_screen.dart` — inspection report
- `services/api_service.dart` — backend API calls
- `services/auth_service.dart` — Auth0 wrapper

## MVP Notes

- Android only
- `shop_id`, `technician_id`, `vehicle_id` are hardcoded placeholders in `new_session_screen.dart`
  — replace with real values from Auth0 user profile once auth is wired end-to-end
- Backend URL: `https://app.workbai.autorepairsolutions.ai`
