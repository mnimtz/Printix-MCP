import SwiftUI
import PrintixSendCore

/// Login-Bildschirm mit zwei Pfaden:
///   1) klassisches Username/Passwort gegen /desktop/auth/login
///   2) Entra Device-Code (Microsoft Login) gegen /desktop/auth/entra/*
///
/// Erfolgreicher Login speichert Bearer-Token + User-Info im
/// SettingsStore, die App schaltet danach automatisch auf den
/// Haupt-Tab-Flow um (siehe ContentView).
struct LoginView: View {

    @EnvironmentObject private var settings: SettingsStore

    @State private var username: String = ""
    @State private var password: String = ""
    @State private var busy: Bool = false
    @State private var error: String = ""

    // Entra-Device-Flow State
    @State private var entraMessage: String = ""
    @State private var entraUserCode: String = ""
    @State private var entraVerificationURI: String = ""
    @State private var entraPollTask: Task<Void, Never>?

    var body: some View {
        Form {
            Section("Anmeldung") {
                TextField("E-Mail / Benutzername", text: $username)
                    .textInputAutocapitalization(.never)
                    .autocorrectionDisabled()
                    .keyboardType(.emailAddress)
                SecureField("Passwort", text: $password)
            }

            Section {
                Button {
                    Task { await doPasswordLogin() }
                } label: {
                    HStack {
                        Spacer()
                        if busy { ProgressView() }
                        else {
                            Image(systemName: "lock.open.fill")
                            Text("Einloggen").fontWeight(.semibold)
                        }
                        Spacer()
                    }
                }
                .disabled(busy || username.isEmpty || password.isEmpty)
            }

            Section("Oder mit Microsoft") {
                Button {
                    Task { await startEntra() }
                } label: {
                    HStack {
                        Image(systemName: "person.badge.key.fill")
                        Text("Per Microsoft-Konto einloggen")
                    }
                }
                .disabled(busy)

                if !entraUserCode.isEmpty {
                    VStack(alignment: .leading, spacing: 8) {
                        Text("Öffne auf deinem Rechner:")
                            .font(.footnote).foregroundColor(.secondary)
                        if let u = URL(string: entraVerificationURI) {
                            Link(entraVerificationURI, destination: u)
                                .font(.callout)
                        }
                        Text("Code:")
                            .font(.footnote).foregroundColor(.secondary)
                        Text(entraUserCode)
                            .font(.system(.title2, design: .monospaced).weight(.bold))
                            .textSelection(.enabled)
                        if !entraMessage.isEmpty {
                            Text(entraMessage)
                                .font(.caption).foregroundColor(.secondary)
                        }
                    }
                }
            }

            if !error.isEmpty {
                Section("Fehler") {
                    Text(error).foregroundColor(.red).textSelection(.enabled)
                }
            }
        }
        .navigationTitle("Login")
        .onDisappear { entraPollTask?.cancel() }
    }

    @MainActor
    private func doPasswordLogin() async {
        error = ""
        busy = true
        defer { busy = false }

        guard let client = ApiClientFactory.make(baseURL: settings.serverURL, token: nil) else {
            error = String(localized: "Ungültige Server-URL.")
            return
        }
        do {
            let result = try await client.login(username: username,
                                                password: password,
                                                deviceName: settings.deviceName)
            guard let token = result.token, !token.isEmpty else {
                error = String(localized: "Kein Token erhalten.")
                return
            }
            applyLogin(token: token, user: result.user)
        } catch {
            self.error = error.localizedDescription
        }
    }

    @MainActor
    private func startEntra() async {
        error = ""
        entraUserCode = ""
        entraVerificationURI = ""
        entraMessage = ""
        guard let client = ApiClientFactory.make(baseURL: settings.serverURL, token: nil) else {
            error = String(localized: "Ungültige Server-URL.")
            return
        }
        do {
            let start = try await client.entraStart(deviceName: settings.deviceName)
            entraUserCode        = start.userCode ?? ""
            entraVerificationURI = start.verificationUri ?? ""
            entraMessage         = start.message ?? ""
            guard let session = start.sessionId else {
                error = String(localized: "Keine Session-ID vom Server.")
                return
            }
            let interval = max(2, start.interval ?? 5)
            entraPollTask?.cancel()
            entraPollTask = Task { await pollEntra(client: client, sessionId: session, interval: interval) }
        } catch {
            self.error = error.localizedDescription
        }
    }

    private func pollEntra(client: PrintixSendCore.ApiClient,
                           sessionId: String,
                           interval: Int) async {
        // Polling-Schleife: bis „success“ oder Cancel. Bei „pending“
        // weiter warten, bei allen anderen Status = aus dem Loop raus.
        while !Task.isCancelled {
            do {
                try await Task.sleep(nanoseconds: UInt64(interval) * 1_000_000_000)
                let poll = try await client.entraPoll(sessionId: sessionId)
                let status = poll.status ?? ""
                if status == "success", let token = poll.token, !token.isEmpty {
                    await MainActor.run {
                        applyLogin(token: token, user: poll.user)
                    }
                    return
                }
                if status == "pending" { continue }
                await MainActor.run {
                    self.error = poll.error ?? poll.message ?? String(localized: "Login abgebrochen (\(status)).")
                    self.entraUserCode = ""
                }
                return
            } catch is CancellationError {
                return
            } catch {
                await MainActor.run { self.error = error.localizedDescription }
                return
            }
        }
    }

    @MainActor
    private func applyLogin(token: String, user: UserInfo?) {
        settings.bearerToken  = token
        settings.userEmail    = user?.email ?? username
        settings.userFullName = user?.fullName ?? ""
        settings.userRoleType = user?.roleType ?? ""
        entraUserCode = ""
        // ContentView beobachtet isLoggedIn und wechselt automatisch auf Main-Flow.
    }
}
