import UIKit
import UniformTypeIdentifiers

final class ShareViewController: UIViewController {

    // ✅ MUSS zu deiner App Group passen
    private let appGroupID = "group.com.mnimtz.printixmobileprint"

    private enum Keys {
        static let gatewayURLString = "gatewayURL"
        static let jobOwnerEmail    = "jobOwnerEmail"
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

        // 1) PDF bevorzugen
        if let pdfProvider = providers.first(where: { $0.hasItemConformingToTypeIdentifier(UTType.pdf.identifier) }) {
            loadPDF(from: pdfProvider)
            return
        }

        // 2) sonst Bild
        if let imageProvider = providers.first(where: { $0.hasItemConformingToTypeIdentifier(UTType.image.identifier) }) {
            loadImageAndConvertToPDF(from: imageProvider)
            return
        }

        close()
    }

    // MARK: - PDF

    private func loadPDF(from provider: NSItemProvider) {
        let typeId = UTType.pdf.identifier

        provider.loadItem(forTypeIdentifier: typeId, options: nil) { [weak self] item, _ in
            guard let self = self else { return }

            if let url = item as? URL {
                self.sendPDF(fileURL: url, fallbackName: url.lastPathComponent.isEmpty ? "document.pdf" : url.lastPathComponent)
                return
            }

            if let data = item as? Data {
                self.sendPDFData(data, filename: "document.pdf")
                return
            }

            self.close()
        }
    }

    // MARK: - Image -> PDF

    private func loadImageAndConvertToPDF(from provider: NSItemProvider) {
        let typeId = UTType.image.identifier

        provider.loadItem(forTypeIdentifier: typeId, options: nil) { [weak self] item, _ in
            guard let self = self else { return }

            // Häufig: URL
            if let url = item as? URL {
                self.sendImageURLAsPDF(url)
                return
            }

            // Manchmal: UIImage
            if let image = item as? UIImage {
                let pdf = self.renderSingleImageToPDF(image)
                self.sendPDFData(pdf, filename: "image.pdf")
                return
            }

            self.close()
        }
    }

    private func sendImageURLAsPDF(_ url: URL) {
        // security-scoped Zugriff (wichtig bei Files/Share)
        let secured = url.startAccessingSecurityScopedResource()
        defer {
            if secured { url.stopAccessingSecurityScopedResource() }
        }

        // Bild laden
        guard
            let data = try? Data(contentsOf: url),
            let image = UIImage(data: data)
        else {
            close()
            return
        }

        let pdfData = renderSingleImageToPDF(image)

        // Dateiname ableiten und .pdf setzen
        let baseName = url.deletingPathExtension().lastPathComponent
        let filename = (baseName.isEmpty ? "image" : baseName) + ".pdf"

        sendPDFData(pdfData, filename: filename)
    }

    private func renderSingleImageToPDF(_ image: UIImage) -> Data {
        // Klassisch: Bild exakt auf eine PDF-Seite (Punkte = Pixel/Scale berücksichtigen)
        let pageRect = CGRect(origin: .zero, size: image.size)

        let renderer = UIGraphicsPDFRenderer(bounds: pageRect)
        return renderer.pdfData { ctx in
            ctx.beginPage()
            image.draw(in: pageRect)
        }
    }

    // MARK: - Sending to Gateway

    private func sendPDF(fileURL: URL, fallbackName: String) {
        let secured = fileURL.startAccessingSecurityScopedResource()
        defer {
            if secured { fileURL.stopAccessingSecurityScopedResource() }
        }

        guard let data = try? Data(contentsOf: fileURL) else {
            close()
            return
        }

        let filename = fallbackName.isEmpty ? "document.pdf" : fallbackName
        sendPDFData(data, filename: filename)
    }

    private func sendPDFData(_ data: Data, filename: String) {
        let defaults = UserDefaults(suiteName: appGroupID)
        let gateway = (defaults?.string(forKey: Keys.gatewayURLString) ?? "").trimmingCharacters(in: .whitespacesAndNewlines)
        let jobOwner = (defaults?.string(forKey: Keys.jobOwnerEmail) ?? "").trimmingCharacters(in: .whitespacesAndNewlines)

        guard !gateway.isEmpty, !jobOwner.isEmpty else {
            close()
            return
        }

        let safeFilename = filename.isEmpty ? "document.pdf" : filename
        let encodedTitle = safeFilename.addingPercentEncoding(withAllowedCharacters: .urlQueryAllowed) ?? "document.pdf"

        guard let uploadURL = URL(string: "\(gateway)/printix/jobs/submit?title=\(encodedTitle)") else {
            close()
            return
        }

        var request = URLRequest(url: uploadURL)
        request.httpMethod = "POST"
        request.setValue("application/pdf", forHTTPHeaderField: "Content-Type")
        request.setValue(jobOwner.lowercased(), forHTTPHeaderField: "x-user-email")

        URLSession.shared.uploadTask(with: request, from: data) { [weak self] _, _, _ in
            self?.close()
        }.resume()
    }

    // MARK: - Close Extension

    private func close() {
        DispatchQueue.main.async {
            self.extensionContext?.completeRequest(returningItems: nil)
        }
    }
}
