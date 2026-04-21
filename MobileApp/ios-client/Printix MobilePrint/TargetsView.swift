import SwiftUI
import PrintixSendCore

/// Zeigt die Liste der verfügbaren Druck-Ziele (Queues/Printer aus
/// Printix). Auswahl speichert die Target-Id im SettingsStore, damit
/// UploadView + Share-Extension das gleiche Default-Ziel verwenden.
struct TargetsView: View {

    @EnvironmentObject private var settings: SettingsStore

    @State private var targets: [Target] = []
    @State private var loading: Bool = false
    @State private var error: String = ""

    var body: some View {
        NavigationStack {
            List {
                if let account = accountSummary {
                    Section("Account") {
                        Text(account).font(.footnote).foregroundColor(.secondary)
                    }
                }

                Section("Druck-Ziele") {
                    if loading && targets.isEmpty {
                        HStack { ProgressView(); Text("Lade Ziele …") }
                    } else if targets.isEmpty {
                        Text("Keine Ziele gefunden.")
                            .foregroundColor(.secondary)
                    } else {
                        ForEach(targets) { t in
                            Button {
                                settings.lastTargetId = t.id
                            } label: {
                                HStack {
                                    VStack(alignment: .leading, spacing: 2) {
                                        Text(t.label).foregroundColor(.primary)
                                        if let s = t.subtitle, !s.isEmpty {
                                            Text(s).font(.caption).foregroundColor(.secondary)
                                        }
                                    }
                                    Spacer()
                                    if settings.lastTargetId == t.id {
                                        Image(systemName: "checkmark.circle.fill")
                                            .foregroundColor(.accentColor)
                                    }
                                }
                            }
                        }
                    }
                }

                if !error.isEmpty {
                    Section("Fehler") {
                        Text(error).foregroundColor(.red).textSelection(.enabled)
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
            }
            .navigationTitle("Ziele")
            .refreshable { await reload() }
            .task { await reload() }
        }
    }

    private var accountSummary: String? {
        let e = settings.userEmail.trimmingCharacters(in: .whitespaces)
        let n = settings.userFullName.trimmingCharacters(in: .whitespaces)
        if e.isEmpty && n.isEmpty { return nil }
        return n.isEmpty ? e : "\(n) · \(e)"
    }

    @MainActor
    private func reload() async {
        error = ""
        guard let client = ApiClientFactory.make(baseURL: settings.serverURL,
                                                 token: settings.bearerToken) else {
            error = "Keine gültige Server-Konfiguration."
            return
        }
        loading = true
        defer { loading = false }
        do {
            targets = try await client.targets()
            // Falls noch kein Default gesetzt: erstes Ziel nehmen.
            if settings.lastTargetId.isEmpty, let first = targets.first {
                settings.lastTargetId = first.id
            }
        } catch {
            self.error = error.localizedDescription
        }
    }
}
