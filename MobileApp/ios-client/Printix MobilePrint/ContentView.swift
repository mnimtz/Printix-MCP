import SwiftUI

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
    var body: some View {
        TabView {
            UploadView()
                .tabItem { Label("Upload", systemImage: "paperplane.fill") }

            TargetsView()
                .tabItem { Label("Ziele", systemImage: "printer.fill") }

            AccountView()
                .tabItem { Label("Konto", systemImage: "person.crop.circle") }
        }
    }
}

/// Kleiner Einstellungs-/Konto-Tab. Login-Daten, Server-URL,
/// Abmelde-Button. Hier kommt in Runde 2 auch der QR-Scanner rein.
private struct AccountView: View {
    @EnvironmentObject private var settings: SettingsStore

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
            }
            .navigationTitle("Konto")
        }
    }
}
