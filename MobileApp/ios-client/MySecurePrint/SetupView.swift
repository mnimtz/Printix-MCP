import SwiftUI

/// Erster Bildschirm: der User trägt hier nur die Server-URL des
/// MCP-Hosts ein. Alles Weitere (Tenant, Owner, Queue) ergibt sich aus
/// dem Login — der Server kennt ja bereits unseren User.
struct SetupView: View {

    @EnvironmentObject private var settings: SettingsStore

    @State private var draftURL: String = ""
    @State private var showLogin: Bool = false
    @State private var showScanner: Bool = false
    @State private var scanNote: String = ""

    var body: some View {
        NavigationStack {
            Form {
                Section("Server") {
                    TextField("https://printix-mcp.example.com", text: $draftURL)
                        .textInputAutocapitalization(.never)
                        .keyboardType(.URL)
                        .autocorrectionDisabled()

                    Button {
                        scanNote = ""
                        showScanner = true
                    } label: {
                        HStack {
                            Image(systemName: "qrcode.viewfinder")
                            Text("QR scannen")
                            Spacer()
                        }
                    }

                    if !scanNote.isEmpty {
                        Text(scanNote).font(.footnote).foregroundColor(.secondary)
                    }
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
            .sheet(isPresented: $showScanner) {
                QRScannerView { value in
                    showScanner = false
                    guard let v = value, !v.isEmpty else {
                        scanNote = String(localized: "Scan abgebrochen oder Kamera nicht verfügbar.")
                        return
                    }
                    // Nur akzeptieren, wenn es nach URL aussieht — sonst
                    // blenden wir den Rohwert als Hinweis ein.
                    if v.lowercased().hasPrefix("http://") || v.lowercased().hasPrefix("https://") {
                        draftURL = v
                        scanNote = String(localized: "Server-URL aus QR übernommen.")
                    } else {
                        scanNote = String(localized: "QR enthält keine gültige Server-URL.")
                    }
                }
                .ignoresSafeArea()
            }
        }
    }
}
