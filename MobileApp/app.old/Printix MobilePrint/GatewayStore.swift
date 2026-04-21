import Foundation
import Combine
import SwiftUI

@MainActor
final class GatewayStore: ObservableObject {

    // ✅ MUSS zu deinen Entitlements/App Group passen
    private static let appGroupID = "group.com.mnimtz.printixmobileprint"

    private enum Keys {
        static let gatewayURLString = "gatewayURL"
        static let jobOwnerEmail    = "jobOwnerEmail"
        static let lastQueueId      = "lastQueueId"
        static let lastTitle        = "lastTitle"
    }

    // ✅ Fix: Defaults als gespeicherte Property (nicht computed), damit init sauber ist
    private let defaults: UserDefaults

    // MARK: - Published (speichert automatisch in App Group Defaults)

    @Published var gatewayURLString: String {
        didSet { defaults.set(gatewayURLString, forKey: Keys.gatewayURLString) }
    }

    @Published var jobOwnerEmail: String {
        didSet { defaults.set(jobOwnerEmail, forKey: Keys.jobOwnerEmail) }
    }

    @Published var lastQueueId: String {
        didSet { defaults.set(lastQueueId, forKey: Keys.lastQueueId) }
    }

    @Published var lastTitle: String {
        didSet { defaults.set(lastTitle, forKey: Keys.lastTitle) }
    }

    // MARK: - Init

    init() {
        // App Group defaults oder fallback
        let appGroupDefaults = UserDefaults(suiteName: Self.appGroupID)
        self.defaults = appGroupDefaults ?? .standard

        // Migration: wenn vorher in standard gespeichert wurde, übernehmen wir einmalig
        let old = UserDefaults.standard

        let migratedGateway = defaults.string(forKey: Keys.gatewayURLString)
            ?? old.string(forKey: Keys.gatewayURLString)
            ?? ""

        let migratedOwner = defaults.string(forKey: Keys.jobOwnerEmail)
            ?? old.string(forKey: Keys.jobOwnerEmail)
            ?? ""

        let migratedQueue = defaults.string(forKey: Keys.lastQueueId)
            ?? old.string(forKey: Keys.lastQueueId)
            ?? ""

        let migratedTitle = defaults.string(forKey: Keys.lastTitle)
            ?? old.string(forKey: Keys.lastTitle)
            ?? ""

        // ✅ alle @Published initialisieren
        self.gatewayURLString = migratedGateway
        self.jobOwnerEmail    = migratedOwner
        self.lastQueueId      = migratedQueue
        self.lastTitle        = migratedTitle

        // in AppGroup speichern (damit Extension es garantiert findet)
        defaults.set(self.gatewayURLString, forKey: Keys.gatewayURLString)
        defaults.set(self.jobOwnerEmail, forKey: Keys.jobOwnerEmail)
        defaults.set(self.lastQueueId, forKey: Keys.lastQueueId)
        defaults.set(self.lastTitle, forKey: Keys.lastTitle)
    }

    // MARK: - Helpers

    var gatewayBaseURL: URL? {
        let trimmed = gatewayURLString.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmed.isEmpty else { return nil }
        return URL(string: trimmed)
    }
}
