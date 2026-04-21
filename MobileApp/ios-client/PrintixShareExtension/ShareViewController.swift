import UIKit
import UniformTypeIdentifiers
import PrintixSendCore

/// iOS Share-Extension: aus einer anderen App "Drucken via Mobile Print".
///
/// Die Extension teilt sich mit der Haupt-App die App-Group
/// `group.com.mnimtz.printixmobileprint` — dort liegen Server-URL,
/// Bearer-Token und das zuletzt gewählte Target. Das genügt, um
/// unterwegs eine PDF/ein Bild mit einem Klick an die SecurePrint-Queue
/// zu senden, ohne die Extension selbst zu einer Login-UI auszubauen.
final class ShareViewController: UIViewController {

    private let appGroupID = "group.com.mnimtz.printixmobileprint"

    private enum Keys {
        static let serverURL    = "serverURL"
        static let bearerToken  = "bearerToken"
        static let lastTargetId = "lastTargetId"
    }

    override func viewDidAppear(_ animated: Bool) {
        super.viewDidAppear(animated)
        handleSharedItem()
    }

    private func handleSharedItem() {
        guard
            let extensionItem = extensionContext?.inputItems.first as? NSExtensionItem,
            let providers = extensionItem.attachments,
            !providers.isEmpty
        else {
            close()
            return
        }

        // PDF bevorzugen, sonst Bild → in-memory in PDF rendern.
        if let pdfProvider = providers.first(where: { $0.hasItemConformingToTypeIdentifier(UTType.pdf.identifier) }) {
            loadPDF(from: pdfProvider)
            return
        }
        if let imageProvider = providers.first(where: { $0.hasItemConformingToTypeIdentifier(UTType.image.identifier) }) {
            loadImage(from: imageProvider)
            return
        }
        close()
    }

    // MARK: - PDF

    private func loadPDF(from provider: NSItemProvider) {
        provider.loadItem(forTypeIdentifier: UTType.pdf.identifier, options: nil) { [weak self] item, _ in
            guard let self = self else { return }
            if let url = item as? URL {
                let secured = url.startAccessingSecurityScopedResource()
                defer { if secured { url.stopAccessingSecurityScopedResource() } }
                guard let data = try? Data(contentsOf: url) else { self.close(); return }
                let name = url.lastPathComponent.isEmpty ? "document.pdf" : url.lastPathComponent
                self.upload(data: data, filename: name)
                return
            }
            if let data = item as? Data {
                self.upload(data: data, filename: "document.pdf")
                return
            }
            self.close()
        }
    }

    // MARK: - Image → PDF

    private func loadImage(from provider: NSItemProvider) {
        provider.loadItem(forTypeIdentifier: UTType.image.identifier, options: nil) { [weak self] item, _ in
            guard let self = self else { return }
            if let url = item as? URL {
                let secured = url.startAccessingSecurityScopedResource()
                defer { if secured { url.stopAccessingSecurityScopedResource() } }
                guard let data = try? Data(contentsOf: url),
                      let image = UIImage(data: data) else { self.close(); return }
                let pdfData = self.renderSingleImageToPDF(image)
                let baseName = url.deletingPathExtension().lastPathComponent
                let filename = (baseName.isEmpty ? "image" : baseName) + ".pdf"
                self.upload(data: pdfData, filename: filename)
                return
            }
            if let image = item as? UIImage {
                let pdfData = self.renderSingleImageToPDF(image)
                self.upload(data: pdfData, filename: "image.pdf")
                return
            }
            self.close()
        }
    }

    private func renderSingleImageToPDF(_ image: UIImage) -> Data {
        let pageRect = CGRect(origin: .zero, size: image.size)
        let renderer = UIGraphicsPDFRenderer(bounds: pageRect)
        return renderer.pdfData { ctx in
            ctx.beginPage()
            image.draw(in: pageRect)
        }
    }

    // MARK: - Upload via PrintixSendCore

    private func upload(data: Data, filename: String) {
        let defaults = UserDefaults(suiteName: appGroupID)
        let serverURL  = (defaults?.string(forKey: Keys.serverURL) ?? "").trimmingCharacters(in: .whitespacesAndNewlines)
        let token      = (defaults?.string(forKey: Keys.bearerToken) ?? "").trimmingCharacters(in: .whitespacesAndNewlines)
        let targetId   = (defaults?.string(forKey: Keys.lastTargetId) ?? "").trimmingCharacters(in: .whitespacesAndNewlines)

        guard !serverURL.isEmpty, !token.isEmpty, !targetId.isEmpty,
              let client = try? PrintixSendCore.ApiClient(baseUrl: serverURL, token: token) else {
            close()
            return
        }

        // Auf MainActor sind wir hier nicht zwingend — sendData ist async
        // und threadsafe. Task detached genügt.
        Task.detached { [weak self] in
            defer { self?.close() }
            do {
                _ = try await client.sendData(data,
                                              filename: filename,
                                              targetId: targetId,
                                              comment: nil,
                                              copies: 1,
                                              color: false,
                                              duplex: false)
            } catch {
                // Silent fail: die Share-Extension ist kein Ort für
                // Error-Dialoge. Details landen im PrintixSendCore-Log.
            }
        }
    }

    private func close() {
        DispatchQueue.main.async {
            self.extensionContext?.completeRequest(returningItems: nil)
        }
    }
}
