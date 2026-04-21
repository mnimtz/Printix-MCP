import SwiftUI

/// Erster Bildschirm: der User trägt hier nur die Server-URL des
/// MCP-Hosts ein. Alles Weitere (Tenant, Owner, Queue) ergibt sich aus
/// dem Login — der Server kennt ja bereits unseren User.
struct SetupView: View {

    @EnvironmentObject private var settings: SettingsStore

    @State private var draftURL: String = ""
    @State private var showLogin: Bool = false

    var body: some View {
        NavigationStack {
            Form {
                Section("Server") {
                    TextField("https://printix-mcp.example.com", text: $draftURL)
                        .textInputAutocapitalization(.never)
                        .keyboardType(.URL)
                        .autocorrectionDisabled()
                }

                Section {
                    Button {
                        settings.serverURL = draftURL.trimmingCharacters(in: .whitespacesAndNewlines)
                        showLogin = true
                    } label: {
                        HStack {
                            Spacer()
                            Image(systemName: "arrow.right.circle.fill")
                            Text("Weiter zum Login").fontWeight(.semibold)
                            Spacer()
                        }
                    }
                    .disabled(URL(string: draftURL.trimmingCharacters(in: .whitespacesAndNewlines)) == nil)
                }

                Section {
                    Text("Den QR-Code für die schnelle Einrichtung findest du im Self-Service-Bereich des Management-Portals unter „Mobile App“.")
                        .font(.footnote)
                        .foregroundColor(.secondary)
                }
            }
            .navigationTitle("Setup")
            .onAppear { draftURL = settings.serverURL }
            .navigationDestination(isPresented: $showLogin) {
                LoginView()
            }
        }
    }
}
