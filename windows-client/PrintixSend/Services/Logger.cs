using System;
using System.IO;

namespace PrintixSend.Services;

public class Logger
{
    private readonly string _logFile;
    private readonly object _lock = new();

    public Logger()
    {
        var baseDir = Path.Combine(
            Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
            "PrintixSend", "logs");
        Directory.CreateDirectory(baseDir);
        _logFile = Path.Combine(baseDir, $"printix-send-{DateTime.Now:yyyyMMdd}.log");
    }

    public string LogFilePath => _logFile;

    public void Info(string msg)  => Write("INFO",  msg);
    public void Warn(string msg)  => Write("WARN",  msg);
    public void Error(string msg) => Write("ERROR", msg);
    public void Error(string msg, Exception ex) => Write("ERROR", $"{msg} — {ex.GetType().Name}: {ex.Message}\n{ex.StackTrace}");

    private void Write(string level, string msg)
    {
        var line = $"{DateTime.Now:yyyy-MM-dd HH:mm:ss} [{level}] {msg}";
        lock (_lock)
        {
            try { File.AppendAllText(_logFile, line + Environment.NewLine); }
            catch { /* ignore */ }
        }
#if DEBUG
        System.Diagnostics.Debug.WriteLine(line);
#endif
    }
}
