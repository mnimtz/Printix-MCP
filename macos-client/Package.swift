// swift-tools-version:5.9
//
// Printix Send — macOS-Client
// ============================
// Drei Targets:
//  - PrintixSendCore : Shared-Lib (API, Keychain, Models, Config, Logger)
//  - printix-send-cli: Worker, der von Quick-Actions aufgerufen wird
//  - PrintixSendApp  : Menu-Bar-App (Login, Config, Quick-Action-Sync)
//
// Gebaut wird per `swift build -c release --arch arm64 --arch x86_64`
// (Universal-Binary). Das .app-Bundle wird via scripts/make-app-bundle.sh
// aus dem Build-Output zusammengesteckt.

import PackageDescription

let package = Package(
    name: "PrintixSend",
    platforms: [
        .macOS(.v13)  // macOS 13 Ventura — deckt 2022+ ab
    ],
    products: [
        .library(name: "PrintixSendCore", targets: ["PrintixSendCore"]),
        .executable(name: "printix-send-cli", targets: ["PrintixSendCLI"]),
        .executable(name: "PrintixSendApp",   targets: ["PrintixSendApp"]),
    ],
    targets: [
        .target(
            name: "PrintixSendCore",
            path: "Sources/PrintixSendCore"
        ),
        .executableTarget(
            name: "PrintixSendCLI",
            dependencies: ["PrintixSendCore"],
            path: "Sources/PrintixSendCLI"
        ),
        .executableTarget(
            name: "PrintixSendApp",
            dependencies: ["PrintixSendCore"],
            path: "Sources/PrintixSendApp"
        ),
    ]
)
