using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using PrintixSend.Models;

namespace PrintixSend.Services;

/// <summary>
/// Synchronisiert Windows-"Senden an"-Einträge mit den Server-Zielen.
///
/// Für jedes Ziel wird ein .lnk in %AppData%\Microsoft\Windows\SendTo\ angelegt:
///
///   Send2Printix — Mein Secure Print.lnk
///   Send2Printix — Delegate: Max Mustermann.lnk
///
/// Shortcut ruft "PrintixSend.exe --target=&lt;id&gt;" auf. Beim Senden-an-
/// Klick hängt Windows die Dateipfade automatisch an die Argumente an.
///
/// Veraltete "Send2Printix — *.lnk"-Einträge werden bei jedem Sync-Lauf
/// entfernt (z. B. wenn ein Delegate serverseitig entfernt wurde).
/// </summary>
public class SendToSync
{
    private const string Prefix = "Send2Printix — ";
    private readonly Logger _log;

    public SendToSync(Logger log) => _log = log;

    private static string SendToDir =>
        Environment.GetFolderPath(Environment.SpecialFolder.SendTo);

    /// <summary>Ein Shortcut je Ziel anlegen/aktualisieren, Veraltetes löschen.</summary>
    public void Sync(IEnumerable<Target> targets, string exePath)
    {
        try
        {
            var dir = SendToDir;
            if (string.IsNullOrEmpty(dir) || !Directory.Exists(dir))
            {
                _log.Warn($"SendTo-Ordner nicht gefunden: '{dir}'");
                return;
            }

            // Soll-Liste: Dateiname → (Ziel-ID, Beschreibung)
            var want = targets.ToDictionary(
                t => SafeFileName(Prefix + t.Label) + ".lnk",
                t => t,
                StringComparer.OrdinalIgnoreCase);

            // Veraltete "Send2Printix — *.lnk" entfernen
            foreach (var existing in Directory.GetFiles(dir, Prefix + "*.lnk"))
            {
                var name = Path.GetFileName(existing);
                if (!want.ContainsKey(name))
                {
                    try { File.Delete(existing); _log.Info($"SendTo entfernt: {name}"); }
                    catch (Exception ex) { _log.Warn($"SendTo konnte {name} nicht löschen: {ex.Message}"); }
                }
            }

            // Neue/geänderte Shortcuts schreiben
            foreach (var kv in want)
            {
                var lnkPath = Path.Combine(dir, kv.Key);
                var t = kv.Value;
                try
                {
                    WriteShortcut(
                        lnkPath: lnkPath,
                        target: exePath,
                        arguments: $"--target=\"{t.Id}\"",
                        description: t.Description ?? $"Printix Send — {t.Label}",
                        iconPath: exePath);
                    _log.Info($"SendTo geschrieben: {kv.Key} → target={t.Id}");
                }
                catch (Exception ex)
                {
                    _log.Warn($"SendTo konnte {kv.Key} nicht schreiben: {ex.Message}");
                }
            }
        }
        catch (Exception ex)
        {
            _log.Warn($"SendToSync-Fehler: {ex.Message}");
        }
    }

    /// <summary>Alle "Send2Printix — *.lnk"-Einträge löschen (Logout).</summary>
    public void ClearAll()
    {
        try
        {
            var dir = SendToDir;
            if (!Directory.Exists(dir)) return;
            foreach (var f in Directory.GetFiles(dir, Prefix + "*.lnk"))
            {
                try { File.Delete(f); _log.Info($"SendTo entfernt: {Path.GetFileName(f)}"); }
                catch (Exception ex) { _log.Warn($"SendTo Löschfehler {Path.GetFileName(f)}: {ex.Message}"); }
            }
        }
        catch (Exception ex) { _log.Warn($"SendToSync.ClearAll-Fehler: {ex.Message}"); }
    }

    /// <summary>Shortcut via WScript.Shell COM schreiben (kein NuGet-Paket nötig).</summary>
    private static void WriteShortcut(string lnkPath, string target, string arguments,
                                       string description, string iconPath)
    {
        // WScript.Shell hat CreateShortcut, das sowohl .lnk als auch .url kann.
        var shellType = Type.GetTypeFromProgID("WScript.Shell")
            ?? throw new InvalidOperationException("WScript.Shell COM nicht verfügbar.");
        dynamic shell = Activator.CreateInstance(shellType)!;
        try
        {
            dynamic link = shell.CreateShortcut(lnkPath);
            try
            {
                link.TargetPath = target;
                link.Arguments = arguments;
                link.Description = description;
                link.IconLocation = iconPath + ",0";
                link.WorkingDirectory = Path.GetDirectoryName(target) ?? "";
                link.Save();
            }
            finally
            {
                System.Runtime.InteropServices.Marshal.FinalReleaseComObject(link);
            }
        }
        finally
        {
            System.Runtime.InteropServices.Marshal.FinalReleaseComObject(shell);
        }
    }

    private static string SafeFileName(string name)
    {
        foreach (var c in Path.GetInvalidFileNameChars())
            name = name.Replace(c, '_');
        return name;
    }
}
