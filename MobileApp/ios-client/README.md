# Mobile Print — iOS Client

iOS-Companion zur Printix-MCP-Serverlandschaft. Teilt sich mit dem
macOS-Client den gesamten Netzwerk-Layer via Swift-Package
`PrintixSendCore` (unter `macos-client/`).

## Aufbau

```
ios-client/
├── Printix MobilePrint.xcodeproj/      Xcode-Projekt (beibehalten aus app.old)
├── Printix MobilePrint/                Haupt-App-Target
│   ├── Printix_MobilePrintApp.swift    @main (MobilePrintApp)
│   ├── ContentView.swift               Router: Setup→Login vs. Tabs
│   ├── SetupView.swift                 Server-URL-Eingabe
│   ├── LoginView.swift                 Password + Entra Device-Code
│   ├── TargetsView.swift               Druck-Ziele auswählen
│   ├── UploadView.swift                Datei wählen + senden
│   ├── SettingsStore.swift             App-Group-UserDefaults-Wrapper
│   ├── ApiClientFactory.swift          PrintixSendCore-Client-Factory
│   ├── DocumentPicker.swift            UIKit-Bridge (bisher ungenutzt, Reserve)
│   └── Printix MobilePrint.entitlements
├── PrintixShareExtension/              Share-Extension-Target
│   ├── ShareViewController.swift       PDF/Bild → PrintixSendCore.sendData
│   ├── PrintixShareExtension.entitlements
│   ├── Info.plist
│   └── Base.lproj/MainInterface.storyboard
└── Printix-MobilePrint-Info.plist
```

## App Group

Beide Targets teilen:

```
group.com.mnimtz.printixmobileprint
```

Dort liegen (in UserDefaults des App-Group-Suites):
- `serverURL` — Basis-URL des MCP-Servers
- `bearerToken` — Login-Token aus `/desktop/auth/login`
- `userEmail`, `userFullName` — angemeldeter User
- `lastTargetId` — zuletzt gewähltes Druck-Ziel
- `deviceName` — Gerätename für Login-Device-Binding

> Der Token liegt für das MVP/TestFlight bewusst in den App-Group-
> Defaults (nicht im Keychain). iOS-Apps sind sandboxed, das Risiko ist
> überschaubar. Ein Migrations-Schritt auf Keychain-Access-Group kann
> jederzeit ohne Änderung der UI nachgeschoben werden.

## Einmalige Xcode-Schritte nach dem Öffnen

Die Swift-Dateien sind bereits angepasst, aber das Xcode-Projekt kennt
noch ein paar Dinge nicht automatisch:

1. **Local Swift Package einbinden**
   In Xcode: `File → Add Packages → Add Local…` → Ordner
   `../../macos-client` wählen. Beim Dialog beide Targets
   (`Printix MobilePrint` + `PrintixShareExtension`) an
   `PrintixSendCore` anhängen. Die iOS-Unterstützung ist im
   `Package.swift` bereits deklariert (`.iOS(.v16)`).

2. **Alte Dateien entfernen** (falls im Projekt-Navigator noch rot):
   `APIClient.swift`, `Models.swift`, `GatewayStore.swift`,
   `StatusView.swift`, `JobOwnerSection.swift`,
   `JobOwnerViewModel.swift`. Diese wurden aus `Printix MobilePrint/`
   bereits gelöscht.

3. **Neue Dateien zum Target hinzufügen**:
   `SettingsStore.swift`, `LoginView.swift`, `TargetsView.swift`,
   `ApiClientFactory.swift` → Target Membership `Printix MobilePrint`.

4. **Display-Name**: In `Printix-MobilePrint-Info.plist`
   `CFBundleDisplayName` auf `Mobile Print` setzen. Bundle-ID und
   Signing bleiben unverändert.

5. **Share-Extension — Info.plist anpassen**: unter
   `NSExtensionAttributes → NSExtensionActivationRule` sollten PDFs +
   Bilder aktiv bleiben; der neue Upload-Pfad verlangt nichts
   Zusätzliches.

## Build & Run

- Scheme `Printix MobilePrint` auf einem iOS-16+ Simulator oder Gerät
  starten.
- Erst-Start: Server-URL eingeben → Login mit Portal-Credentials oder
  Entra Device-Code → Ziel auswählen → Datei hochladen.
- Aus anderen Apps: „Teilen → Mobile Print“ → Datei geht an das zuletzt
  gewählte Ziel.

## TestFlight

Bundle-ID + App-Group sind bereits im Apple-Developer-Account
registriert (Altbestand aus `app.old`). Für TestFlight genügt es,
Version+Build im Archiv zu erhöhen und hochzuladen.
