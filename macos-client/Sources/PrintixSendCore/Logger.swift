import Foundation

// Einfacher Datei-Logger nach dem Muster des Windows-Clients.
// Schreibt nach ~/Library/Logs/PrintixSend/printix-send-YYYYMMDD.log
// und – optional – zusätzlich nach stderr, damit die CLI auch im Terminal
// Feedback gibt, wenn man sie manuell aufruft.

public final class AppLogger: @unchecked Sendable {
    public static let shared = AppLogger()

    private let queue = DispatchQueue(label: "de.printix.send.log")
    private let formatter: DateFormatter
    private let dayFormatter: DateFormatter
    public var alsoStderr: Bool = false

    private init() {
        let f = DateFormatter()
        f.locale = Locale(identifier: "en_US_POSIX")
        f.dateFormat = "yyyy-MM-dd HH:mm:ss"
        self.formatter = f
        let d = DateFormatter()
        d.locale = Locale(identifier: "en_US_POSIX")
        d.dateFormat = "yyyyMMdd"
        self.dayFormatter = d
    }

    private var logDir: URL {
        let home = FileManager.default.homeDirectoryForCurrentUser
        return home.appendingPathComponent("Library/Logs/PrintixSend", isDirectory: true)
    }

    private var logFile: URL {
        let name = "printix-send-\(dayFormatter.string(from: Date())).log"
        return logDir.appendingPathComponent(name)
    }

    private func ensureDir() {
        try? FileManager.default.createDirectory(at: logDir, withIntermediateDirectories: true)
    }

    public func info(_ msg: String) { write("INFO",  msg) }
    public func warn(_ msg: String) { write("WARN",  msg) }
    public func error(_ msg: String) { write("ERROR", msg) }

    private func write(_ level: String, _ msg: String) {
        let line = "\(formatter.string(from: Date())) [\(level)] \(msg)\n"
        queue.async { [self] in
            ensureDir()
            if let data = line.data(using: .utf8) {
                if let fh = try? FileHandle(forWritingTo: logFile) {
                    fh.seekToEndOfFile()
                    fh.write(data)
                    try? fh.close()
                } else {
                    try? data.write(to: logFile)
                }
            }
            if alsoStderr {
                FileHandle.standardError.write(Data(line.utf8))
            }
        }
    }
}
