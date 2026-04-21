import SwiftUI

struct JobOwnerSection: View {

    @ObservedObject var viewModel: JobOwnerViewModel

    @State private var manualEmail: String = ""
    @State private var isSigningIn = false
    @State private var errorText: String = ""

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("Job Owner")
                .font(.headline)

            // Aktueller Owner
            VStack(alignment: .leading, spacing: 6) {
                Text("Aktuell")
                    .font(.subheadline)
                    .foregroundColor(.secondary)

                Text(viewModel.jobOwnerEmail.isEmpty ? "—" : viewModel.jobOwnerEmail)
                    .font(.system(.body, design: .monospaced))
            }

            if !errorText.isEmpty {
                Text(errorText)
                    .foregroundColor(.red)
                    .font(.footnote)
            }

            // Buttons
            HStack(spacing: 12) {
                Button {
                    Task {
                        errorText = ""
                        isSigningIn = true
                        defer { isSigningIn = false }
                        await viewModel.signInWithEntraMock()
                    }
                } label: {
                    HStack {
                        if isSigningIn { ProgressView().padding(.trailing, 4) }
                        Text("Mit Entra anmelden")
                    }
                }
                .buttonStyle(.borderedProminent)
                .disabled(isSigningIn)

                Button {
                    // nur UI fokus, macht nix kaputt
                    manualEmail = viewModel.jobOwnerEmail
                } label: {
                    Text("E-Mail manuell")
                }
                .buttonStyle(.bordered)
                .disabled(isSigningIn)
            }

            // Manuelle Eingabe
            VStack(alignment: .leading, spacing: 8) {
                Text("Manuelle E-Mail")
                    .font(.subheadline)
                    .foregroundColor(.secondary)

                TextField("name@firma.de", text: $manualEmail)
                    .textInputAutocapitalization(.never)
                    .autocorrectionDisabled()
                    .keyboardType(.emailAddress)
                    .padding(12)
                    .background(Color(.systemGray6))
                    .cornerRadius(10)

                Button {
                    let v = manualEmail.trimmingCharacters(in: .whitespacesAndNewlines)
                    guard v.contains("@"), v.contains(".") else {
                        errorText = "Bitte eine gültige E-Mail eingeben."
                        return
                    }
                    errorText = ""
                    viewModel.setManualEmail(v)
                } label: {
                    HStack {
                        Spacer()
                        Text("Übernehmen")
                            .fontWeight(.semibold)
                        Spacer()
                    }
                }
                .buttonStyle(.bordered)
            }
        }
        .padding()
        .background(Color(.secondarySystemBackground))
        .cornerRadius(14)
        .onAppear {
            manualEmail = viewModel.jobOwnerEmail
        }
    }
}
