import Foundation
import Combine

@MainActor
final class JobOwnerViewModel: ObservableObject {

    private enum Keys {
        static let jobOwnerEmail = "job_owner_email"
        static let authMode = "job_owner_auth_mode" // "entra" | "manual"
    }

    @Published var jobOwnerEmail: String {
        didSet {
            UserDefaults.standard.set(jobOwnerEmail.trimmingCharacters(in: .whitespacesAndNewlines),
                                      forKey: Keys.jobOwnerEmail)
        }
    }

    @Published var authMode: String {
        didSet {
            UserDefaults.standard.set(authMode, forKey: Keys.authMode)
        }
    }

    init() {
        self.jobOwnerEmail = UserDefaults.standard.string(forKey: Keys.jobOwnerEmail) ?? ""
        self.authMode = UserDefaults.standard.string(forKey: Keys.authMode) ?? "manual"
    }

    func setManualEmail(_ email: String) {
        authMode = "manual"
        jobOwnerEmail = email.trimmingCharacters(in: .whitespacesAndNewlines).lowercased()
    }

    func setEntraUPN(_ upn: String) {
        authMode = "entra"
        jobOwnerEmail = upn.trimmingCharacters(in: .whitespacesAndNewlines).lowercased()
    }

    // Placeholder: später MSAL Login
    func signInWithEntraMock() async {
        // Simuliert einen Login und liefert eine UPN zurück
        try? await Task.sleep(nanoseconds: 600_000_000)
        setEntraUPN("user@company.com")
    }
}
