import SwiftUI

struct SetupView: View {

    @EnvironmentObject private var store: GatewayStore

    var body: some View {
        NavigationView {
            Form {
                Section("Gateway") {
                    TextField("https://printix-gateway.example.de", text: $store.gatewayURLString)
                        .textInputAutocapitalization(.never)
                        .keyboardType(.URL)
                        .autocorrectionDisabled()
                }

                Section("Job Owner") {
                    TextField("user@company.tld", text: $store.jobOwnerEmail)
                        .textInputAutocapitalization(.never)
                        .keyboardType(.emailAddress)
                        .autocorrectionDisabled()
                }

                Section("Optional") {
                    TextField("Queue ID (optional)", text: $store.lastQueueId)
                        .textInputAutocapitalization(.never)
                        .autocorrectionDisabled()

                    TextField("Default Title (optional)", text: $store.lastTitle)
                        .textInputAutocapitalization(.never)
                        .autocorrectionDisabled()
                }

                Section {
                    Text("Tipp: Wenn du ein PDF auswählst, wird der Dateiname automatisch als Title verwendet.")
                        .font(.footnote)
                        .foregroundColor(.secondary)
                }
            }
            .navigationTitle("Setup")
        }
    }
}
