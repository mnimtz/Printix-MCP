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
                                toggle(t)
                            } label: {
                                HStack {
                                    VStack(alignment: .leading, spacing: 2) {
                                        Text(t.label).foregroundColor(.primary)
                                        if let s = t.subtitle, !s.isEmpty {
                                            Text(s).font(.caption).foregroundColor(.secondary)
                                        }
                                    }
                                    Spacer()
                                    // Multi-Select: Haken wenn das Ziel in der
                                    // ausgewaehlten Liste steht. Tap toggelt
                                    // Mitgliedschaft — so kann man delegate1 +
                                    // capture1 gleichzeitig anvisieren.
                                    if settings.selectedTargetIds.contains(t.id) {
                                        Image(systemName: "checkmark.circle.fill")
                                            .foregroundColor(.accentColor)
                                    } else {
                                        Image(systemName: "circle")
                                            .foregroundColor(.secondary)
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

    private func toggle(_ t: Target) {
        if let idx = settings.selectedTargetIds.firstIndex(of: t.id) {
            settings.selectedTargetIds.remove(at: idx)
        } else {
            settings.selectedTargetIds.append(t.id)
        }
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
            // Label-Cache aktualisieren, damit UploadView die
            // Anzeigenamen statt nur die IDs rendert.
            var labels: [String: String] = [:]
            for t in targets { labels[t.id] = t.label }
            settings.targetLabels = labels
            // Falls noch nichts ausgewaehlt ist: erstes Ziel als Default
            // setzen, damit der Upload-Button nicht sofort disabled ist.
            if settings.selectedTargetIds.isEmpty, let first = targets.first {
                settings.selectedTargetIds = [first.id]
            }
        } catch {
            self.error = error.localizedDescription
        }
    }
}
