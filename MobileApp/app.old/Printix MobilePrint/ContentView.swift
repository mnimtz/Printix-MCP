import SwiftUI

struct ContentView: View {

    @StateObject private var store = GatewayStore()

    var body: some View {
        TabView {
            SetupView()
                .tabItem { Label("Setup", systemImage: "gearshape.fill") }

            UploadView()
                .tabItem { Label("Upload", systemImage: "paperplane.fill") }

            StatusView()
                .tabItem { Label("Status", systemImage: "waveform.path.ecg") }
        }
        .environmentObject(store)
    }
}
