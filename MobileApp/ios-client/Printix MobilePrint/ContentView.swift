import SwiftUI
import PrintixSendCore

/// Top-Level-Router.
/// - Nicht eingeloggt → SetupView → LoginView
/// - Eingeloggt → Tabs Upload / Ziele / Konto
struct ContentView: View {

    @StateObject private var settings = SettingsStore()

    var body: some View {
        Group {
            if settings.isLoggedIn {
                MainTabs()
            } else {
                SetupView()
            }
        }
        .environmentObject(settings)
    }
}

private struct MainTabs: View {
    @EnvironmentObject private var settings: SettingsStore

    var body: some View {
        TabView {
            UploadView()
                .tabItem { Label("Upload", systemImage: "paperplane.fill") }

            TargetsView()
                .tabItem { Label("Ziele", systemImage: "printer.fill") }

            // Nur fuer Admin/User (nicht Employee) — Tenant-Uebersicht.
            if settings.hasManagementAccess {
                ManagementView()
                    .tabItem { Label("Management", systemImage: "building.2.fill") }

                CardsView()
                    .tabItem { Label("Karten", systemImage: "creditcard.fill") }
            }

            AccountView()
                .tabItem { Label("Konto", systemImage: "person.crop.circle") }
        }
        // Auf /desktop/me synchronisieren — deckt auch bestehende Sessions
        // ab, fuer die beim urspruenglichen Login der roleType noch nicht
        // gespeichert wurde (App-Update von einer Vorversion).
        .task { await refreshRole() }
    }

    private func refreshRole() async {
        guard let base = settings.serverBaseURL,
              let client = ApiClientFactory.make(baseURL: base.absoluteString,
                                                 token: settings.bearerToken) else {
            return
        }
        do {
            if let me = try await client.me() {
                settings.userRoleType = me.roleType ?? settings.userRoleType
                if let e = me.email, !e.isEmpty { settings.userEmail = e }
                if let n = me.fullName, !n.isEmpty { settings.userFullName = n }
            }
        } catch {
            // Silent — Tab bleibt dann eben erstmal versteckt, und beim
            // naechsten Login greift der gespeicherte Wert.
        }
    }
}

/// Kleiner Einstellungs-/Konto-Tab. Login-Daten, Server-URL,
/// Abmelde-Button. Hier kommt in Runde 2 auch der QR-Scanner rein.
private struct AccountView: View {
    @EnvironmentObject private var settings: SettingsStore
    @EnvironmentObject private var l10n: L10n

    /// "1.5.0 (2)" — Marketing-Version + Build-Nummer. Bundle-Keys sind
    /// bei iOS fix, deshalb ohne Localized-Lookup.
    private var appVersionString: String {
        let info = Bundle.main.infoDictionary
        let version = info?["CFBundleShortVersionString"] as? String ?? "?"
        let build   = info?["CFBundleVersion"] as? String ?? "?"
        return "\(version) (\(build))"
    }

    var body: some View {
        NavigationStack {
            Form {
                Section("Angemeldet als") {
                    if !settings.userFullName.isEmpty {
                        Text(settings.userFullName)
                    }
                    if !settings.userEmail.isEmpty {
                        Text(settings.userEmail).font(.footnote).foregroundColor(.secondary)
                    }
                }
                Section("Server") {
                    Text(settings.serverURL).font(.footnote).foregroundColor(.secondary)
                }
                Section("Gerät") {
                    TextField("Gerätename", text: $settings.deviceName)
                        .autocorrectionDisabled()
                }
                Section("Sprache") {
                    Picker("Sprache", selection: Binding(
                        get: { l10n.pendingLanguage },
                        set: { newLang in
                            l10n.apply(newLang)
                            settings.appLanguage = newLang
                        }
                    )) {
                        ForEach(L10n.supportedLanguages, id: \.code) { lang in
                            // Display-Text bleibt in der jeweiligen Muttersprache
                            // — niemals uebersetzt, damit man "Deutsch" auch
                            // als Englisch-Sprecher findet.
                            Text(verbatim: lang.display).tag(lang.code)
                        }
                    }
                    if l10n.restartRequired {
                        // Hinweis dass die Aenderung erst nach App-Restart greift.
                        // Bewusst in der ZIEL-Sprache (aus dem jeweiligen lproj)
                        // gefallen — sonst liest der User einen deutschen Hinweis
                        // waehrend er gerade auf Englisch umgestellt hat.
                        Label {
                            Text("Zum Wechseln die App neu starten.")
                                .font(.footnote)
                        } icon: {
                            Image(systemName: "arrow.clockwise.circle")
                                .foregroundColor(.orange)
                        }
                    }
                }
                Section {
                    Button(role: .destructive) {
                        settings.clearSession()
                    } label: {
                        HStack {
                            Image(systemName: "rectangle.portrait.and.arrow.right")
                            Text("Abmelden")
                        }
                    }
                }

                // Version-Footer: zieht MARKETING_VERSION und Build aus
                // dem Bundle — so sieht man sofort, welcher Stand auf dem
                // Geraet laeuft (wichtig bei TestFlight-Rollouts).
                Section {
                    HStack {
                        Text("Version")
                        Spacer()
                        Text(appVersionString)
                            .font(.footnote)
                            .foregroundColor(.secondary)
                    }
                }
            }
            .navigationTitle("Konto")
        }
    }
}
