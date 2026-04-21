import SwiftUI
import UniformTypeIdentifiers
import PhotosUI
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
    // Foto-Picker nutzt PhotosUI, nicht fileImporter — die Fotos-
    // Mediathek kriegt man ueber den Files-Picker nicht erreicht.
    @State private var photoItem: PhotosPickerItem?

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
                    // Datei aus der Files-App (PDF, Office, Textdateien etc.)
                    Button {
                        showImporter = true
                    } label: {
                        HStack {
                            Image(systemName: "folder.fill")
                            Text("Aus Dateien wählen")
                            Spacer()
                        }
                    }
                    // Foto aus der Fotos-Mediathek — nutzt PhotosPicker,
                    // damit der User wirklich an seine Fotos/Screenshots
                    // rankommt ohne Umweg ueber "In Dateien speichern".
                    PhotosPicker(selection: $photoItem,
                                 matching: .any(of: [.images, .screenshots]),
                                 photoLibrary: .shared()) {
                        HStack {
                            Image(systemName: "photo.fill")
                            Text("Aus Fotos wählen")
                            Spacer()
                        }
                    }
                    // Anzeige der aktuell gewaehlten Quelle
                    HStack {
                        Image(systemName: "doc.text")
                            .foregroundColor(.secondary)
                        Text(pickedURL?.lastPathComponent ?? "Noch nichts ausgewählt")
                            .foregroundColor(.secondary)
                            .lineLimit(1)
                    }
                }

                Section("Optionen") {
                    Stepper("Kopien: \(copies)", value: $copies, in: 1...50)
                    Toggle("Farbe", isOn: $color)
                    Toggle("Duplex", isOn: $duplex)
                    TextField("Kommentar (optional)", text: $comment)
                        .autocorrectionDisabled()
                }

                Section("Ziele") {
                    if settings.selectedTargetIds.isEmpty {
                        Text("Kein Ziel gewählt — unter „Ziele“ auswählen.")
                            .foregroundColor(.secondary)
                    } else {
                        Text("\(settings.selectedTargetIds.count) Ziel(e) ausgewählt")
                            .font(.footnote)
                            .foregroundColor(.secondary)
                        ForEach(settings.selectedTargetIds, id: \.self) { id in
                            Text(id)
                                .font(.footnote.monospaced())
                                .foregroundColor(.secondary)
                                .lineLimit(1)
                        }
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
                    .disabled(isSending || pickedURL == nil || settings.selectedTargetIds.isEmpty)
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
            .onChange(of: photoItem) { _, newItem in
                guard let newItem else { return }
                Task { await importPhoto(newItem) }
            }
        }
    }

    /// PhotosPickerItem → temporaere Datei im Tmp-Verzeichnis.
    /// Der Rest von sendNow() kann dann ueber pickedURL wie gewohnt
    /// arbeiten (security-scoped entfaellt, weil /tmp uns gehoert).
    @MainActor
    private func importPhoto(_ item: PhotosPickerItem) async {
        errorText = ""
        do {
            guard let data = try await item.loadTransferable(type: Data.self) else {
                errorText = "Konnte das Foto nicht laden."
                return
            }
            // Dateiendung bestmoeglich raten — bei HEIC/JPEG steht das
            // im ersten Content-Type-Eintrag, sonst Fallback auf .jpg.
            let ext = fileExtension(for: item.supportedContentTypes.first) ?? "jpg"
            let name = "photo-\(Int(Date().timeIntervalSince1970)).\(ext)"
            let url  = FileManager.default.temporaryDirectory.appendingPathComponent(name)
            try data.write(to: url, options: .atomic)
            pickedURL = url
        } catch {
            errorText = "Foto-Import: \(error.localizedDescription)"
        }
    }

    private func fileExtension(for type: UTType?) -> String? {
        guard let type else { return nil }
        if type.conforms(to: .png)  { return "png" }
        if type.conforms(to: .jpeg) { return "jpg" }
        if type.conforms(to: .heic) { return "heic" }
        if type.conforms(to: .gif)  { return "gif" }
        return type.preferredFilenameExtension
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
            // Multi-Target: pro ausgewaehltem Ziel einmal senden.
            // Wir sammeln Erfolge/Fehler pro Ziel und zeigen die Liste
            // anschliessend an — ein Fehler bei einem Ziel bricht den
            // Rest nicht ab (z.B. wenn ein Drucker offline ist, soll
            // der andere trotzdem losgehen).
            var successes: [String] = []
            var failures:  [String] = []
            for targetId in settings.selectedTargetIds {
                do {
                    let result = try await client.sendData(data,
                                                           filename: filename,
                                                           targetId: targetId,
                                                           comment: comment.isEmpty ? nil : comment,
                                                           copies: copies,
                                                           color: color,
                                                           duplex: duplex)
                    if result.ok == true || result.status?.lowercased() == "queued" {
                        successes.append("✅ \(targetId): \(shortResult(result))")
                    } else {
                        failures.append("⚠️ \(targetId): \(result.error ?? result.message ?? "Unbekannter Fehler")")
                    }
                } catch {
                    failures.append("⚠️ \(targetId): \(error.localizedDescription)")
                }
            }
            resultText = successes.joined(separator: "\n")
            errorText  = failures.joined(separator: "\n")
        } catch {
            errorText = error.localizedDescription
        }
    }

    private func shortResult(_ r: SendResult) -> String {
        var parts: [String] = []
        if let s = r.status { parts.append(s) }
        if let j = r.jobId { parts.append("job=\(j)") }
        return parts.isEmpty ? "gesendet" : parts.joined(separator: " ")
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
