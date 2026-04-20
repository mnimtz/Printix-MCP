import Foundation

// DTOs für die Desktop-API des Printix-MCP-Servers.
// 1:1-Pendant zu windows-client/PrintixSend/Models/*.cs — die gleichen
// JSON-Felder, damit beide Clients dieselbe Server-Version nutzen.

public struct LoginResponse: Codable, Sendable {
    public let ok: Bool?
    public let token: String?
    public let user: UserInfo?

    public init(ok: Bool? = nil, token: String? = nil, user: UserInfo? = nil) {
        self.ok = ok
        self.token = token
        self.user = user
    }
}

public struct UserInfo: Codable, Sendable {
    public let userId: Int?
    public let username: String?
    public let email: String?
    public let fullName: String?
    public let roleType: String?
    public let deviceName: String?

    enum CodingKeys: String, CodingKey {
        case userId = "user_id"
        case username, email
        case fullName = "full_name"
        case roleType = "role_type"
        case deviceName = "device_name"
    }

    public init(userId: Int? = nil, username: String? = nil, email: String? = nil,
                fullName: String? = nil, roleType: String? = nil, deviceName: String? = nil) {
        self.userId = userId
        self.username = username
        self.email = email
        self.fullName = fullName
        self.roleType = roleType
        self.deviceName = deviceName
    }
}

public struct Target: Codable, Identifiable, Hashable, Sendable {
    public let id: String
    public let label: String
    public let type: String?
    public let subtitle: String?

    enum CodingKeys: String, CodingKey {
        case id, label, type, subtitle
    }
}

public struct TargetsResponse: Codable, Sendable {
    public let targets: [Target]
}

public struct SendResult: Codable, Sendable {
    public let ok: Bool?
    public let status: String?
    public let jobId: String?
    public let printixJobId: String?
    public let target: String?
    public let filename: String?
    public let size: Int?
    public let ownerEmail: String?
    public let error: String?
    public let code: String?
    public let message: String?

    enum CodingKeys: String, CodingKey {
        case ok, status, target, filename, size, error, code, message
        case jobId = "job_id"
        case printixJobId = "printix_job_id"
        case ownerEmail = "owner_email"
    }
}

public struct EntraStartResponse: Codable, Sendable {
    public let deviceCode: String?
    public let userCode: String?
    public let verificationUri: String?
    public let expiresIn: Int?
    public let interval: Int?
    public let message: String?

    enum CodingKeys: String, CodingKey {
        case deviceCode = "device_code"
        case userCode = "user_code"
        case verificationUri = "verification_uri"
        case expiresIn = "expires_in"
        case interval, message
    }
}

public struct EntraPollResponse: Codable, Sendable {
    public let ok: Bool?
    public let status: String?     // "pending" | "success" | "error"
    public let token: String?
    public let user: UserInfo?
    public let error: String?
    public let message: String?
}

public struct VersionResponse: Codable, Sendable {
    public let latest: String?
    public let downloadUrlX64: String?
    public let downloadUrlArm64: String?
    public let downloadUrlMac: String?

    enum CodingKeys: String, CodingKey {
        case latest
        case downloadUrlX64   = "download_url_x64"
        case downloadUrlArm64 = "download_url_arm64"
        case downloadUrlMac   = "download_url_mac"
    }
}
