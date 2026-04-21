import Foundation
import Combine
import SwiftUI
#if canImport(UIKit)
import UIKit
#endif

/// Gemeinsamer Settings-Store für Haupt-App und Share-Extension.
///
/// Alle Werte liegen in der App-Group, damit die Share-Extension
/// denselben Server und Token verwendet wie die App. Der Bearer-Token
/// bleibt fürs MVP auch in den App-Group-Defaults — gut genug für
/// TestFlight; später kann er in einen Keychain-Access-Group-Eintrag
/// wandern. iOS-Geräte sind sandboxed, also ist das Risiko überschaubar.
@MainActor
final class SettingsStore: ObservableObject {

    // MUSS mit den Entitlements von Haupt-App + Share-Extension übereinstimmen.
    static let appGroupID = "group.com.mnimtz.printixmobileprint"

    private enum Keys {
        static let serverURL         = "serverURL"
        static let bearerToken       = "bearerToken"
        static let userEmail         = "userEmail"
        static let userFullName      = "userFullName"
        static let lastTargetId      = "lastTargetId"      // legacy/single (Share-Ext)
        static let selectedTargetIds = "selectedTargetIds" // JSON-Array (Multi)
        static let deviceName        = "deviceName"
    }

    private let defaults: UserDefaults

    @Published var serverURL: String {
        didSet { defaults.set(serverURL, forKey: Keys.serverURL) }
    }

    @Published var bearerToken: String {
        didSet { defaults.set(bearerToken, forKey: Keys.bearerToken) }
    }

    @Published var userEmail: String {
        didSet { defaults.set(userEmail, forKey: Keys.userEmail) }
    }

    @Published var userFullName: String {
        didSet { defaults.set(userFullName, forKey: Keys.userFullName) }
    }

    @Published var lastTargetId: String {
        didSet { defaults.set(lastTargetId, forKey: Keys.lastTargetId) }
    }

    /// Multi-Select: Liste der aktuell ausgewaehlten Ziel-Ids.
    /// Die Haupt-App nutzt diese fuer den "Gleichzeitig an mehrere
    /// Ziele"-Upload. Wir halten `lastTargetId` parallel auf das erste
    /// Element synchron, damit die Share-Extension (die nur ein Ziel
    /// kennt) weiter funktioniert — die lesen wir nicht um, damit die
    /// Extension keinen Build-Anschluss an den JSON-Parser braucht.
    @Published var selectedTargetIds: [String] {
        didSet {
            if let data = try? JSONEncoder().encode(selectedTargetIds) {
                defaults.set(data, forKey: Keys.selectedTargetIds)
            }
            // Share-Extension bleibt auf single-target → primaeres Ziel mirror'n.
            let primary = selectedTargetIds.first ?? ""
            if lastTargetId != primary {
                lastTargetId = primary
            }
        }
    }

    @Published var deviceName: String {
        didSet { defaults.set(deviceName, forKey: Keys.deviceName) }
    }

    init() {
        let appGroupDefaults = UserDefaults(suiteName: Self.appGroupID)
        self.defaults = appGroupDefaults ?? .standard

        self.serverURL    = defaults.string(forKey: Keys.serverURL)    ?? ""
        self.bearerToken  = defaults.string(forKey: Keys.bearerToken)  ?? ""
        self.userEmail    = defaults.string(forKey: Keys.userEmail)    ?? ""
        self.userFullName = defaults.string(forKey: Keys.userFullName) ?? ""
        let legacyTarget = defaults.string(forKey: Keys.lastTargetId) ?? ""
        self.lastTargetId = legacyTarget
        // Multi-Target aus JSON laden; Fallback = Single aus Legacy-Key.
        if let data = defaults.data(forKey: Keys.selectedTargetIds),
           let arr  = try? JSONDecoder().decode([String].self, from: data) {
            self.selectedTargetIds = arr
        } else {
            self.selectedTargetIds = legacyTarget.isEmpty ? [] : [legacyTarget]
        }
        let storedDeviceName = defaults.string(forKey: Keys.deviceName) ?? ""
        self.deviceName = storedDeviceName.isEmpty ? Self.defaultDeviceName() : storedDeviceName
    }

    // MARK: - Derived

    var serverBaseURL: URL? {
        let trimmed = serverURL.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmed.isEmpty else { return nil }
        return URL(string: trimmed)
    }

    var isLoggedIn: Bool {
        !bearerToken.isEmpty && serverBaseURL != nil
    }

    func clearSession() {
        bearerToken = ""
        userEmail = ""
        userFullName = ""
        lastTargetId = ""
    }

    private static func defaultDeviceName() -> String {
        #if canImport(UIKit)
        return UIDevice.current.name
        #else
        return "iOS Device"
        #endif
    }
}
