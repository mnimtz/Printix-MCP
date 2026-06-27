import UIKit
import UniformTypeIdentifiers
import Security

/// iOS Share-Extension: aus einer anderen App "Drucken via MySecurePrint".
///
/// Die Extension teilt sich mit der Haupt-App die App-Group
/// `group.de.nimtz.mysecureprint` (UserDefaults: Server-URL, Target-ID,
/// Upload-Status) sowie eine geteilte Keychain-Access-Group
/// `group.de.nimtz.mysecureprint` (Bearer-Token, C-4).
///
/// I-4: Upload laeuft ueber `URLSession` mit `background:`-Identifier
/// und einer auf Disk geschriebenen temporaeren Datei. Damit kann iOS
/// den Upload zu Ende fuehren, auch wenn die Extension nach `close()`
/// abgeraeumt wird. Das letzte Ergebnis (success/failure) schreiben
/// wir in die App-Group-UserDefaults — die Haupt-App kann es beim
/// naechsten Start anzeigen.
final class ShareViewController: UIViewController {

    private let appGroupID = "group.de.nimtz.mysecureprint"
    private let backgroundSessionID = "de.nimtz.mysecureprint.share.upload"
    private let keychainService = "de.nimtz.mysecureprint"
    private let keychainAccount = "bearerToken"

    private enum Keys {
        static let serverURL        = "serverURL"
        static let lastTargetId     = "lastTargetId"
        // Spiegelt das letzte Upload-Resultat in die App-Group.
        static let lastUploadStatus = "share_lastUploadStatus"   // "queued"|"success"|"failure"
        static let lastUploadAt     = "share_lastUploadAt"
        static let lastUploadError  = "share_lastUploadError"
        static let lastUploadFile   = "share_lastUploadFilename"
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

        // PDF bevorzugen, sonst Bild -> in-memory in PDF rendern.
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
                // I-10: statt in den RAM zu lesen, in einen temporaeren
                // Container im App-Group-Verzeichnis kopieren — Background-
                // URLSession streamed das dann von Disk.
                let name = url.lastPathComponent.isEmpty ? "document.pdf" : url.lastPathComponent
                guard let tmp = self.copyIntoSharedTemp(url: url, suggestedName: name) else {
                    self.close(); return
                }
                self.upload(fileURL: tmp, filename: name)
                return
            }
            if let data = item as? Data {
                guard let tmp = self.writeDataToSharedTemp(data, suggestedName: "document.pdf") else {
                    self.close(); return
                }
                self.upload(fileURL: tmp, filename: "document.pdf")
                return
            }
            self.close()
        }
    }

    // MARK: - Image -> PDF

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
                guard let tmp = self.writeDataToSharedTemp(pdfData, suggestedName: filename) else {
                    self.close(); return
                }
                self.upload(fileURL: tmp, filename: filename)
                return
            }
            if let image = item as? UIImage {
                let pdfData = self.renderSingleImageToPDF(image)
                guard let tmp = self.writeDataToSharedTemp(pdfData, suggestedName: "image.pdf") else {
                    self.close(); return
                }
                self.upload(fileURL: tmp, filename: "image.pdf")
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

    // MARK: - Background Upload

    private func upload(fileURL: URL, filename: String) {
        let defaults = UserDefaults(suiteName: appGroupID)
        let serverURL  = (defaults?.string(forKey: Keys.serverURL) ?? "").trimmingCharacters(in: .whitespacesAndNewlines)
        let token      = readTokenFromKeychain()
        let targetId   = (defaults?.string(forKey: Keys.lastTargetId) ?? "").trimmingCharacters(in: .whitespacesAndNewlines)

        guard !serverURL.isEmpty, !token.isEmpty, !targetId.isEmpty,
              let url = URL(string: serverURL.trimmingTrailingSlash() + "/desktop/send") else {
            recordStatus(status: "failure", error: "missing config", filename: filename)
            close()
            return
        }

        // Multipart-Body als Datei in den App-Group-Container schreiben,
        // damit `uploadTask(with:fromFile:)` ihn auch nach Tod der
        // Extension streamen kann (Background-URLSession-Constraint:
        // body MUSS aus einer Datei kommen, nicht aus In-Memory-Data).
        let boundary = "Boundary-\(UUID().uuidString)"
        guard let multipartURL = writeMultipartBody(boundary: boundary,
                                                    fileURL: fileURL,
                                                    filename: filename,
                                                    targetId: targetId) else {
            recordStatus(status: "failure", error: "could not assemble multipart", filename: filename)
            close()
            return
        }

        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        request.setValue("multipart/form-data; boundary=\(boundary)", forHTTPHeaderField: "Content-Type")

        let config = URLSessionConfiguration.background(withIdentifier: backgroundSessionID + "." + UUID().uuidString)
        config.sharedContainerIdentifier = appGroupID
        let session = URLSession(configuration: config, delegate: nil, delegateQueue: nil)
        let task = session.uploadTask(with: request, fromFile: multipartURL)
        task.resume()

        recordStatus(status: "queued", error: nil, filename: filename)
        // close() darf laufen — der Background-Upload geht von iOS
        // weitergefuehrt, auch wenn die Extension stirbt.
        close()
    }

    private func recordStatus(status: String, error: String?, filename: String) {
        let defaults = UserDefaults(suiteName: appGroupID)
        defaults?.set(status, forKey: Keys.lastUploadStatus)
        defaults?.set(Date().timeIntervalSince1970, forKey: Keys.lastUploadAt)
        defaults?.set(filename, forKey: Keys.lastUploadFile)
        if let e = error {
            defaults?.set(e, forKey: Keys.lastUploadError)
        } else {
            defaults?.removeObject(forKey: Keys.lastUploadError)
        }
    }

    // MARK: - File-Helper (App-Group-Container)

    private func sharedTempDirectory() -> URL? {
        guard let container = FileManager.default.containerURL(forSecurityApplicationGroupIdentifier: appGroupID) else {
            return nil
        }
        let dir = container.appendingPathComponent("share-uploads", isDirectory: true)
        try? FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
        return dir
    }

    private func copyIntoSharedTemp(url src: URL, suggestedName: String) -> URL? {
        guard let dir = sharedTempDirectory() else { return nil }
        let dst = dir.appendingPathComponent("\(Int(Date().timeIntervalSince1970))-\(suggestedName)")
        try? FileManager.default.removeItem(at: dst)
        do {
            try FileManager.default.copyItem(at: src, to: dst)
            return dst
        } catch {
            return nil
        }
    }

    /// Baut den Multipart-Body inkl. target_id + file und schreibt
    /// ihn als zusammenhaengende Datei in den App-Group-Container.
    /// Mime-Type wird grob aus der Dateiendung geraten (Server
    /// akzeptiert auch application/octet-stream).
    private func writeMultipartBody(boundary: String, fileURL: URL, filename: String, targetId: String) -> URL? {
        guard let dir = sharedTempDirectory() else { return nil }
        let bodyURL = dir.appendingPathComponent("\(Int(Date().timeIntervalSince1970))-body.bin")
        FileManager.default.createFile(atPath: bodyURL.path, contents: nil)
        guard let handle = try? FileHandle(forWritingTo: bodyURL) else { return nil }
        defer { try? handle.close() }

        func write(_ s: String) {
            if let data = s.data(using: .utf8) { handle.write(data) }
        }

        let ext = (filename as NSString).pathExtension.lowercased()
        let mime: String
        switch ext {
        case "pdf":              mime = "application/pdf"
        case "png":              mime = "image/png"
        case "jpg", "jpeg":      mime = "image/jpeg"
        default:                 mime = "application/octet-stream"
        }

        write("--\(boundary)\r\n")
        write("Content-Disposition: form-data; name=\"target_id\"\r\n\r\n")
        write("\(targetId)\r\n")
        write("--\(boundary)\r\n")
        write("Content-Disposition: form-data; name=\"copies\"\r\n\r\n1\r\n")
        write("--\(boundary)\r\n")
        write("Content-Disposition: form-data; name=\"color\"\r\n\r\n\r\n")
        write("--\(boundary)\r\n")
        write("Content-Disposition: form-data; name=\"duplex\"\r\n\r\n\r\n")
        write("--\(boundary)\r\n")
        write("Content-Disposition: form-data; name=\"file\"; filename=\"\(filename)\"\r\n")
        write("Content-Type: \(mime)\r\n\r\n")

        // Datei streamen — vermeidet das Laden grosser PDFs in den RAM
        // (I-10) auch im Build-Pfad der Extension.
        guard let inHandle = try? FileHandle(forReadingFrom: fileURL) else { return nil }
        defer { try? inHandle.close() }
        while true {
            let chunk = inHandle.readData(ofLength: 64 * 1024)
            if chunk.isEmpty { break }
            handle.write(chunk)
        }
        write("\r\n--\(boundary)--\r\n")
        return bodyURL
    }

    private func writeDataToSharedTemp(_ data: Data, suggestedName: String) -> URL? {
        guard let dir = sharedTempDirectory() else { return nil }
        let dst = dir.appendingPathComponent("\(Int(Date().timeIntervalSince1970))-\(suggestedName)")
        do {
            try data.write(to: dst, options: .atomic)
            return dst
        } catch {
            return nil
        }
    }

    // MARK: - Keychain (geteilte Access-Group, C-4)

    private func readTokenFromKeychain() -> String {
        let query: [String: Any] = [
            kSecClass as String:            kSecClassGenericPassword,
            kSecAttrService as String:      keychainService,
            kSecAttrAccount as String:      keychainAccount,
            kSecAttrAccessGroup as String:  appGroupID,
            kSecMatchLimit as String:       kSecMatchLimitOne,
            kSecReturnData as String:       true,
        ]
        var item: CFTypeRef?
        let status = SecItemCopyMatching(query as CFDictionary, &item)
        guard status == errSecSuccess,
              let data = item as? Data,
              let str = String(data: data, encoding: .utf8) else {
            return ""
        }
        return str
    }

    private func close() {
        DispatchQueue.main.async {
            self.extensionContext?.completeRequest(returningItems: nil)
        }
    }
}

private extension String {
    func trimmingTrailingSlash() -> String {
        var s = self
        while s.hasSuffix("/") { s.removeLast() }
        return s
    }

    func urlEncoded() -> String {
        addingPercentEncoding(withAllowedCharacters: .urlQueryAllowed) ?? self
    }
}
