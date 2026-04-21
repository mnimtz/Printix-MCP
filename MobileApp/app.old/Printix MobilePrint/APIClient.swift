import Foundation

enum APIError: Error, LocalizedError {
    case invalidBaseURL
    case invalidResponse
    case httpStatus(Int, String)
    case decodingFailed

    var errorDescription: String? {
        switch self {
        case .invalidBaseURL: return "Ungültige Gateway URL"
        case .invalidResponse: return "Ungültige Server-Antwort"
        case .httpStatus(let code, let body): return "HTTP \(code): \(body)"
        case .decodingFailed: return "Antwort konnte nicht gelesen werden"
        }
    }
}

final class APIClient {

    func fetchHealth(baseURL: URL) async throws -> HealthResponse {
        let url = baseURL.appendingPathComponent("printix/health")

        var req = URLRequest(url: url)
        req.httpMethod = "GET"

        let (data, response) = try await URLSession.shared.data(for: req)
        guard let http = response as? HTTPURLResponse else { throw APIError.invalidResponse }
        guard (200..<300).contains(http.statusCode) else {
            let body = String(data: data, encoding: .utf8) ?? ""
            throw APIError.httpStatus(http.statusCode, body)
        }

        do {
            return try JSONDecoder().decode(HealthResponse.self, from: data)
        } catch {
            throw APIError.decodingFailed
        }
    }

    /// Upload an dein Gateway:
    /// POST /printix/jobs/submit?title=...&releaseImmediately=...&queueId=...
    /// Header: x-user-email
    /// Body: raw PDF
    func submitPDF(
        baseURL: URL,
        pdfData: Data,
        userEmail: String,
        title: String,
        releaseImmediately: Bool,
        queueId: String?
    ) async throws -> SubmitResponse {

        // Basis: .../printix/jobs/submit
        var url = baseURL.appendingPathComponent("printix/jobs/submit")

        // Query Items
        var items: [URLQueryItem] = []
        items.append(URLQueryItem(name: "title", value: title))
        items.append(URLQueryItem(name: "releaseImmediately", value: releaseImmediately ? "true" : "false"))
        if let q = queueId, !q.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
            items.append(URLQueryItem(name: "queueId", value: q))
        }

        url = url.appending(queryItems: items)

        var req = URLRequest(url: url)
        req.httpMethod = "POST"
        req.setValue("application/pdf", forHTTPHeaderField: "Content-Type")
        req.setValue(userEmail, forHTTPHeaderField: "x-user-email")
        req.httpBody = pdfData

        let (data, response) = try await URLSession.shared.data(for: req)
        guard let http = response as? HTTPURLResponse else { throw APIError.invalidResponse }
        guard (200..<300).contains(http.statusCode) else {
            let body = String(data: data, encoding: .utf8) ?? ""
            throw APIError.httpStatus(http.statusCode, body)
        }

        do {
            return try JSONDecoder().decode(SubmitResponse.self, from: data)
        } catch {
            throw APIError.decodingFailed
        }
    }
}

// MARK: - URL helper (klassisch & robust)
extension URL {
    func appending(queryItems: [URLQueryItem]) -> URL {
        guard var comps = URLComponents(url: self, resolvingAgainstBaseURL: false) else { return self }
        var existing = comps.queryItems ?? []
        existing.append(contentsOf: queryItems)
        comps.queryItems = existing
        return comps.url ?? self
    }
}
