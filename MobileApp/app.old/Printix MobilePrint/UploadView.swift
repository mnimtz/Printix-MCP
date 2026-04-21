import SwiftUI
import UniformTypeIdentifiers

struct UploadView: View {

    @EnvironmentObject private var store: GatewayStore
    private let api = APIClient()

    @State private var pickedURL: URL?
    @State private var releaseImmediately: Bool = false

    @State private var isSending: Bool = false
    @State private var resultText: String = ""
    @State private var errorText: String = ""

    @State private var showImporter: Bool = false

    var body: some View {
        NavigationView {
            Form {
                Section("PDF") {
                    Button {
                        showImporter = true
                    } label: {
                        HStack {
                            Image(systemName: "doc.fill")
                            Text("PDF auswählen")
                            Spacer()
                            Text(pickedURL?.lastPathComponent ?? "—")
                                .foregroundColor(.secondary)
                                .lineLimit(1)
                        }
                    }

                    if let url = pickedURL {
                        Text(url.path)
                            .font(.footnote)
                            .foregroundColor(.secondary)
                            .lineLimit(2)
                    }
                }

                Section("Optionen") {
                    Toggle("SecurePrint (releaseImmediately=false)", isOn: Binding(
                        get: { !releaseImmediately },
                        set: { releaseImmediately = !$0 }
                    ))
                }

                Section("Senden") {
                    Button {
                        Task { await sendSelectedPDF() }
                    } label: {
                        HStack {
                            Spacer()
                            if isSending {
                                ProgressView()
                            } else {
                                Image(systemName: "paperplane.fill")
                                Text("An Printix senden")
                                    .fontWeight(.semibold)
                            }
                            Spacer()
                        }
                    }
                    .disabled(isSending)
                }

                if !errorText.isEmpty {
                    Section("Fehler") {
                        Text(errorText)
                            .foregroundColor(.red)
                            .textSelection(.enabled)
                    }
                }

                if !resultText.isEmpty {
                    Section("Antwort") {
                        Text(resultText)
                            .font(.footnote)
                            .textSelection(.enabled)
                    }
                }
            }
            .navigationTitle("Upload")
        }
        .fileImporter(
            isPresented: $showImporter,
            allowedContentTypes: [UTType.pdf],
            allowsMultipleSelection: false
        ) { result in
            switch result {
            case .success(let urls):
                guard let url = urls.first else { return }
                pickedURL = url

                // Dateiname als Default-Title merken (klassisch sinnvoll)
                store.lastTitle = url.lastPathComponent

            case .failure(let err):
                errorText = "Dateiauswahl fehlgeschlagen: \(err.localizedDescription)"
            }
        }
    }

    @MainActor
    private func sendSelectedPDF() async {
        errorText = ""
        resultText = ""

        guard let base = store.gatewayBaseURL else {
            errorText = "Gateway URL fehlt/ungültig."
            return
        }
        let owner = store.jobOwnerEmail.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !owner.isEmpty else {
            errorText = "Job Owner (E-Mail) fehlt."
            return
        }
        guard let fileURL = pickedURL else {
            errorText = "Bitte zuerst ein PDF auswählen."
            return
        }

        // Wichtig: Security-Scoped Zugriff (Simulator/Share/Files)
        let didStart = fileURL.startAccessingSecurityScopedResource()
        defer {
            if didStart { fileURL.stopAccessingSecurityScopedResource() }
        }

        let title = store.lastTitle.isEmpty ? fileURL.lastPathComponent : store.lastTitle

        do {
            isSending = true
            defer { isSending = false }

            let pdfData = try Data(contentsOf: fileURL)

            let resp = try await api.submitPDF(
                baseURL: base,
                pdfData: pdfData,
                userEmail: owner,
                title: title,                     // ✅ HIER: Dateiname wird als title gesendet
                releaseImmediately: releaseImmediately,
                queueId: store.lastQueueId.isEmpty ? nil : store.lastQueueId
            )

            if resp.ok {
                let job = resp.jobId ?? "—"
                let qname = resp.queue?.name ?? "—"
                resultText = "✅ Gesendet\nTitel: \(title)\nJobId: \(job)\nQueue: \(qname)\nUser: \(resp.user ?? owner)"
            } else {
                errorText = "⚠️ Gateway meldet ok=false"
            }

        } catch {
            errorText = "❌ \(error.localizedDescription)"
        }
    }
}
