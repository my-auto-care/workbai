# Workbay AI — Mobile App (Android)

Flutter app for hands-free automotive inspection via voice.

## Verified Build Environment (Windows)

| Component | Version |
|---|---|
| Flutter | 3.27.4 |
| Java | 17 (Adoptium JDK 17) |
| Kotlin | 1.9.10 |
| AGP | 8.1.4 |
| Gradle | 8.3 |
| compileSdk | 35 |
| Android NDK | 28.2.13676358 |

## Run on Emulator (Windows)

```powershell
$env:JAVA_HOME = "C:\Users\ChadBechtel\jdk17\jdk-17.0.11+9"
cd C:\workbai\mobile
flutter run -d emulator-5554
```

## Build Release APK

```powershell
$env:JAVA_HOME = "C:\Users\ChadBechtel\jdk17\jdk-17.0.11+9"
flutter build apk --release
# Output: build\app\outputs\flutter-apk\app-release.apk
```

## Architecture

- `main.dart` — entry, splash, auth restore
- `screens/login_screen.dart` — login (dev bypass active, Auth0 re-enable for prod)
- `screens/home_screen.dart` — session list
- `screens/new_session_screen.dart` — start inspection form
- `screens/inspection_screen.dart` — live voice session (LiveKit)
- `screens/session_screen.dart` — inspection report
- `services/api_service.dart` — backend API calls
- `services/auth_service.dart` — Auth0 wrapper

## Backend

`https://app.workbai.autorepairsolutions.ai`

## Test Data (seeded)

- Shop ID: `00000000-0000-0000-0000-000000000001`
- Technician ID: `00000000-0000-0000-0000-000000000002`
- Vehicle ID: `00000000-0000-0000-0000-000000000003`
- Checklist ID: `1bbf9892-68b8-4842-bfd9-7a4cd53dcca8`
