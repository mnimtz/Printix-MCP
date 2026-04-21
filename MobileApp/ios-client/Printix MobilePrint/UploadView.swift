import SwiftUI
import UniformTypeIdentifiers
import PrintixSendCore

/// Haupt-Upload-Screen: Datei aus dem Files-Picker wählen, optional
/// Copies/Color/Duplex setzen, an gewähltes Target senden.
struct UploadView: View {

    @EnvironmentObject private var settings: SettingsStore

    @State private var pickedURL: URL?
    @State private var copies: Int = 1
    @State private var color: Bool = false
    @State private var duplex: Bool = false
    @State private var comment: String = ""

    @State private var isSending: Bool = false
    @State private var resultText: String = ""
    @State private var errorText: String = ""
    @State private var showImporter: Bool = false

    // Alle unterstützten Upload-Typen — der Server nimmt mehr als nur
    // PDF entgegen (LibreOffice-Konvertierung im MCP). PDF/Bilder sind
    // aber unsere Hauptszenarien aus dem iOS-Share-Flow.
    private var allowedTypes: [UTType] {
        var t: [UTType] = [.pdf, .image, .plainText]
        if let docx = UTType(filenameExtension: "docx") { t.append(docx) }
        if let xlsx = UTType(filenameExtension: "xlsx") { t.append(xlsx) }
        return t
    }

    var body: some View {
        NavigationStack {
            Form {
                Section("Datei") {
                    Button {
                        showImporter = true
                    } label: {
                        HStack {
                            Image(systemName: "doc.fill")
                            Text("Datei auswählen")
                            Spacer()
                            Text(pickedURL?.lastPathComponent ?? "—")
                                .foregroundColor(.secondary)
                                .lineLimit(1)
                        }
                    }
                }

                Section("Optionen") {
                    Stepper("Kopien: \(copies)", value: $copies, in: 1...50)
                    Toggle("Farbe", isOn: $color)
                    Toggle("Duplex", isOn: $duplex)
                    TextField("Kommentar (optional)", text: $comment)
                        .autocorrectionDisabled()
                }

                Section("Ziel") {
                    if settings.lastTargetId.isEmpty {
                        Text("Kein Ziel gewählt — unter „Ziele“ auswählen.")
                            .foregroundColor(.secondary)
                    } else {
                        Text("target_id: \(settings.lastTargetId)")
                            .font(.footnote.monospaced())
                            .foregroundColor(.secondary)
                    }
                }

                Section {
                    Button {
                        Task { await sendNow() }
                    } label: {
                        HStack {
                            Spacer()
                            if isSending { ProgressView() }
                            else {
                                Image(systemName: "paperplane.fill")
                                Text("An Printix senden").fontWeight(.semibold)
                            }
                            Spacer()
                        }
                    }
                    .disabled(isSending || pickedURL == nil || settings.lastTargetId.isEmpty)
                }

                if !errorText.isEmpty {
                    Section("Fehler") {
                        Text(errorText).foregroundColor(.red).textSelection(.enabled)
                    }
                }

                if !resultText.isEmpty {
                    Section("Ergebnis") {
                        Text(resultText).font(.footnote).textSelection(.enabled)
                    }
                }
            }
            .navigationTitle("Upload")
            .fileImporter(isPresented: $showImporter,
                          allowedContentTypes: allowedTypes,
                          allowsMultipleSelection: false) { result in
                switch result {
                case .success(let urls): pickedURL = urls.first
                case .failure(let err):  errorText = err.localizedDescription
                }
            }
        }
    }

    @MainActor
    private func sendNow() async {
        errorText = ""
        resultText = ""
        guard let fileURL = pickedURL else {
            errorText = "Bitte zuerst eine Datei auswählen."
            return
        }
        guard let client = ApiClientFactory.make(baseURL: settings.serverURL,
                                                 token: settings.bearerToken) else {
            errorText = "Keine gültige Server-Konfiguration."
            return
        }

        // Security-scoped Zugriff: zwingend für Files-Picker-URLs.
        let secured = fileURL.startAccessingSecurityScopedResource()
        defer { if secured { fileURL.stopAccessingSecurityScopedResource() } }

        isSending = true
        defer { isSending = false }

        do {
            let data = try Data(contentsOf: fileURL)
            let filename = fileURL.lastPathComponent
            let result = try await client.sendData(data,
                                                   filename: filename,
                                                   targetId: settings.lastTargetId,
                                                   comment: comment.isEmpty ? nil : comment,
                                                   copies: copies,
                                                   color: color,
                                                   duplex: duplex)
            if result.ok == true || result.status?.lowercased() == "queued" {
                resultText = format(result: result)
            } else {
                errorText = "⚠️ \(result.error ?? result.message ?? "Unbekannter Fehler")"
            }
        } catch {
            errorText = error.localizedDescription
        }
    }

    private func format(result: SendResult) -> String {
        var parts: [String] = []
        parts.append("✅ Gesendet")
        if let s = result.status { parts.append("Status: \(s)") }
        if let j = result.jobId { parts.append("Job-Id: \(j)") }
        if let p = result.printixJobId { parts.append("Printix-Job: \(p)") }
        if let t = result.target { parts.append("Target: \(t)") }
        if let f = result.filename { parts.append("Datei: \(f)") }
        return parts.joined(separator: "\n")
    }
}
