# Printix Send — Windows-Client

Leichtgewichtiger WPF-Client für den Printix-MCP-Server. Integriert sich in Windows *Senden an* und überträgt Dateien an serverseitig konfigurierte Ziele (Secure Print, Delegate Print, später Capture).

## Features (MVP v6.7.36)

- **Login**: Lokaler Login *oder* Microsoft Entra SSO (Device-Code-Flow)
- **Targets**: Live vom Server geladen (`GET /desktop/targets`) — keine hartkodierten Ziele im Client
- **Senden**: Datei-Upload an `POST /desktop/send` mit Ziel-ID
- **Windows-Integration**: MSI-Installer legt einen *Senden an*-Eintrag an (per-user)
- **Sicher**: Token in Windows DPAPI verschlüsselt (`%LocalAppData%\PrintixSend\token.bin`)

## Projekt-Struktur

```
windows-client/
├── PrintixSend.sln
├── PrintixSend/              # WPF-App (.NET 8)
│   ├── Models/               # DTOs für Desktop-API
│   ├── Services/             # ApiClient, TokenStore (DPAPI), ConfigService, Logger
│   └── Views/                # LoginWindow, SendWindow, ConfigWindow, EntraDeviceWindow
├── PrintixSend.Setup/        # WiX v5 MSI-Projekt
│   ├── Product.wxs           # MSI-Definition (Per-User, SendTo-Shortcut)
│   └── License.rtf
├── scripts/
│   ├── build-msi.ps1         # Lokaler Build (Publish + MSI)
│   ├── install-sendto.ps1    # Dev-Shortcut ohne MSI
│   └── uninstall-sendto.ps1
└── .github/workflows/
    └── build-windows-client.yml  # CI: baut x64 + arm64 MSI
```

## Voraussetzungen

- Windows 10 (17763+) oder Windows 11
- Für den Build: .NET 8 SDK
- Laufender Printix-MCP-Server mit aktiver Desktop-API (v6.7.31+)

## Installation (Endnutzer)

1. Passendes MSI herunterladen:
   - **PrintixSend-\<ver\>-x64.msi** — für Intel/AMD-PCs
   - **PrintixSend-\<ver\>-arm64.msi** — für ARM-Windows (Snapdragon)
2. Doppelklick → Installer durchlaufen (kein Admin nötig — Per-User)
3. Erster Start öffnet den Config-Dialog — Server-URL eintragen (z.B. `https://printix.cloud`)
4. Einloggen: *Mit Microsoft anmelden* (SSO) oder lokale Zugangsdaten
5. **Fertig** — Rechtsklick auf eine Datei → *Senden an > Printix Send*

## Lokaler Build (Mac/Linux → nur Cross-Build, WiX braucht Windows!)

```bash
# WPF-App kann man auf macOS/Linux via dotnet publish bauen (für RID win-x64):
cd windows-client
dotnet publish PrintixSend/PrintixSend.csproj -c Release -r win-x64 --self-contained true
```

**Wichtig**: WiX v5 läuft nur unter Windows. MSI-Build daher auf Windows-Rechner oder via GitHub Actions (`.github/workflows/build-windows-client.yml`).

## Build unter Windows

```powershell
cd windows-client
.\scripts\build-msi.ps1 -Platform x64      # → PrintixSend.Setup\bin\x64\Release\PrintixSend-6.7.36-x64.msi
.\scripts\build-msi.ps1 -Platform ARM64    # → PrintixSend.Setup\bin\ARM64\Release\PrintixSend-6.7.36-ARM64.msi
```

## Release (beide MSIs via CI)

```bash
git tag client-v6.7.36
git push origin client-v6.7.36
```

GitHub Actions baut x64 + arm64 MSI und legt ein Release an.

## Ablauf beim Senden (End-to-End)

```
┌─────────────────────┐
│ Explorer            │
│ Rechtsklick → SendTo│
└──────────┬──────────┘
           │  .exe <Dateipfade>
           ▼
┌─────────────────────────────────┐
│ PrintixSend.exe                 │
│ 1. Config prüfen (ServerUrl)    │
│ 2. Token laden (DPAPI)          │
│ 3. Login-Dialog (falls nötig)   │
│ 4. GET /desktop/targets         │
│ 5. Benutzer wählt Ziel          │
│ 6. POST /desktop/send + Datei   │
│ 7. Erfolgs-Toast                │
└─────────────────────────────────┘
```

## Datenablage

| Was               | Wo                                                 | Verschlüsselt?     |
|-------------------|----------------------------------------------------|--------------------|
| Bearer-Token      | `%LocalAppData%\PrintixSend\token.bin`             | DPAPI (CurrentUser)|
| Config            | `%LocalAppData%\PrintixSend\config.json`           | Nein               |
| Logs              | `%LocalAppData%\PrintixSend\logs\printix-send-*.log` | Nein             |

## Sicherheit

- Token nur für den anmeldenden Windows-User entschlüsselbar (DPAPI)
- Keine Passwörter lokal gespeichert
- Server-URL ist HTTPS-pflichtig (außer HTTP explizit konfiguriert)
- Client-Code-Signing: noch nicht aktiv (MVP) — Nutzer muss SmartScreen einmalig bestätigen

## Bekannte Limitierungen (MVP)

- Keine Preview (PDF-Thumbnail) — folgt
- Keine Offline-Queue — Upload erfordert Netzwerk
- Keine Capture-Ziele (`capture_*`) — folgt, sobald Server sie liefert
- Kein Auto-Update — manuell neues MSI installieren

## Roadmap

- **v6.8**: Capture-Targets, Parameter-Dialog (z.B. Kopien/SW/Farbe)
- **v6.9**: PDF-Vorschau, Job-History
- **v7.0**: Auto-Update über `/desktop/client/latest-version`
- **v7.x**: MSIX-Paket für Windows Store / Intune ohne MSI-Handling
