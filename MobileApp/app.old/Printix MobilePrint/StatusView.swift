import SwiftUI

struct StatusView: View {

    @EnvironmentObject private var store: GatewayStore
    private let api = APIClient()

    @State private var loading = false
    @State private var healthText: String = "Noch nicht geprüft."
    @State private var errorText: String = ""

    var body: some View {
        NavigationView {
            VStack(spacing: 16) {

                Button {
                    Task { await refresh() }
                } label: {
                    HStack {
                        Spacer()
                        if loading { ProgressView() }
                        else {
                            Image(systemName: "heart.text.square")
                            Text("Gateway Health prüfen")
                                .fontWeight(.semibold)
                        }
                        Spacer()
                    }
                }
                .buttonStyle(.borderedProminent)
                .disabled(loading)

                if !errorText.isEmpty {
                    Text(errorText)
                        .foregroundColor(.red)
                        .textSelection(.enabled)
                }

                ScrollView {
                    Text(healthText)
                        .font(.system(.footnote, design: .monospaced))
                        .frame(maxWidth: .infinity, alignment: .leading)
                        .padding()
                }

                Spacer()
            }
            .padding()
            .navigationTitle("Status")
        }
    }

    @MainActor
    private func refresh() async {
        errorText = ""
        loading = true
        defer { loading = false }

        guard let base = store.gatewayBaseURL else {
            errorText = "Gateway URL fehlt/ungültig."
            return
        }

        do {
            let h = try await api.fetchHealth(baseURL: base)

            healthText = """
            ok: \(h.ok)
            hasConfig: \(h.hasConfig ?? false)
            tenantLen: \(h.tenantLen ?? 0)
            clientIdMasked: \(h.clientIdMasked ?? "")
            default_queue_id: \(h.default_queue_id ?? "")
            default_queue_name: \(h.default_queue_name ?? "")
            default_job_owner: \(h.default_job_owner ?? "")
            uploadLimitMb: \(h.uploadLimitMb ?? 0)
            """

        } catch {
            errorText = "❌ \(error.localizedDescription)"
        }
    }
}
