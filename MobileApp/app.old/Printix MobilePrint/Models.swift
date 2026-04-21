import Foundation

struct HealthResponse: Codable {
    let ok: Bool
    let hasConfig: Bool?
    let tenantLen: Int?
    let clientIdLen: Int?
    let secretLen: Int?
    let scopeMode: String?
    let authUrl: String?
    let apiBase: String?
    let apiVersionHeader: String?
    let clientIdMasked: String?
    let pageSize: Int?
    let default_queue_id: String?
    let default_queue_name: String?
    let default_job_owner: String?
    let uploadLimitMb: Int?
}

struct SubmitResponse: Codable {
    let ok: Bool
    let securePrint: Bool?
    let user: String?
    let userSource: String?
    let jobId: String?
    let jobStatus: String?
    let queue: QueueInfo?
    let links: LinksInfo?
}

struct QueueInfo: Codable {
    let id: String?
    let name: String?
    let printerId: String?
    let printerName: String?
}

struct LinksInfo: Codable {
    let jobSelf: String?
    let uploadCompleted: String?
    let changeOwner: String?
}
