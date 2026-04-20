using System;
using System.IO;
using System.Linq;
using System.Threading.Tasks;
using System.Windows;
using PrintixSend.Services;
using PrintixSend.Views;

namespace PrintixSend;

public partial class App : Application
{
    public static ConfigService Config { get; } = new();
    public static TokenStore Tokens { get; } = new();
    public static Logger Log { get; } = new();

    // Gehalten, damit der GC das Tray-Icon nicht wegräumt.
    private static TrayHost? _tray;

    protected override async void OnStartup(StartupEventArgs e)
    {
        base.OnStartup(e);
        Log.Info($"Printix Send gestartet — Args: {e.Args.Length}");

        // CLI-Args: --target=<id>  (von "Senden an"-Shortcut) + Dateien
        string? preselectTarget = null;
        var rawArgs = new System.Collections.Generic.List<string>();
        foreach (var a in e.Args)
        {
            if (a.StartsWith("--target=", StringComparison.OrdinalIgnoreCase))
                preselectTarget = a.Substring("--target=".Length).Trim('"');
            else
                rawArgs.Add(a);
        }
        var files = rawArgs.Where(File.Exists).ToArray();

        // 1. Konfiguration prüfen — erster Start öffnet Config-Dialog
        if (string.IsNullOrWhiteSpace(Config.ServerUrl))
        {
            Log.Info("Keine Server-URL konfiguriert → Config-Dialog");
            var cfg = new ConfigWindow();
            if (cfg.ShowDialog() != true)
            {
                Log.Info("Config abgebrochen — beende");
                Shutdown();
                return;
            }
        }

        // 2. Login-Status prüfen
        var token = Tokens.LoadToken();
        if (string.IsNullOrWhiteSpace(token))
        {
            Log.Info("Kein Token → Login-Dialog");
            var login = new LoginWindow();
            if (login.ShowDialog() != true)
            {
                Log.Info("Login abgebrochen — beende");
                Shutdown();
                return;
            }
            token = Tokens.LoadToken();
        }

        // 3a. Start ohne Dateien: Send-To-Einträge synchronisieren und dauerhaft
        //     als Tray-Icon laufen. Der User nutzt den Explorer-"Senden an"-Kontext
        //     zum Drucken; über das Tray-Icon sind GUI/Einstellungen/Abmelden
        //     jederzeit erreichbar.
        if (files.Length == 0)
        {
            Log.Info("Keine Dateien übergeben — synchronisiere 'Senden an' und zeige Tray.");
            await SyncSendToMenuAsync();
            _tray = new TrayHost();
            _tray.Show();
            // Kurzer Hinweis beim ersten Mal, danach still (keine Dialog-Flut)
            if (!Config.SendToHintShown)
            {
                MessageBox.Show(
                    "Printix Send ist eingerichtet und läuft im Infobereich (neben der Uhr).\n\n" +
                    "Rechtsklick auf eine Datei \u2192 \u201eSenden an\u201c \u2192 waehle dein Ziel " +
                    "(z. B. \u201eMein Secure Print\u201c oder einen Delegate).\n\n" +
                    "Ein Klick auf das Tray-Icon öffnet Status und Einstellungen.",
                    "Printix Send", MessageBoxButton.OK, MessageBoxImage.Information);
                Config.SendToHintShown = true;
            }
            return;
        }

        // Send-To-Sync im Hintergrund anstoßen, blockiert den Upload nicht
        _ = SyncSendToMenuAsync();

        // 3b. "Senden an"-Pfad: --target=<id> ist gesetzt → komplett headless senden.
        //     Keine SendWindow, kein "Lade Ziele …", keine weiteren Klicks.
        //     Erfolg ist stumm, Fehler zeigt eine MessageBox.
        if (!string.IsNullOrEmpty(preselectTarget))
        {
            Log.Info($"{files.Length} Datei(en) → silent send an target={preselectTarget}");
            try
            {
                await SilentSender.RunAsync(files, preselectTarget);
            }
            catch (Exception ex)
            {
                Log.Error("SilentSender unerwarteter Fehler", ex);
                MessageBox.Show($"Senden fehlgeschlagen.\n\n{ex.Message}",
                    "Printix Send", MessageBoxButton.OK, MessageBoxImage.Error);
            }
            Shutdown();
            return;
        }

        // 3c. Dateien OHNE --target (z.B. manuell per Drag&Drop auf exe) → normales Fenster
        Log.Info($"{files.Length} Datei(en) übergeben (ohne Target) → SendWindow");
        var send = new SendWindow(files, preselectTarget);
        send.Show();
    }

    /// <summary>Ziele vom Server holen und Windows-"Senden an"-Shortcuts aktualisieren.</summary>
    private async Task SyncSendToMenuAsync()
    {
        try
        {
            var token = Tokens.LoadToken();
            if (string.IsNullOrEmpty(token)) return;
            using var api = new ApiClient(Config.ServerUrl, token, Log);
            var targets = await api.GetTargetsAsync();
            var exe = System.Diagnostics.Process.GetCurrentProcess().MainModule?.FileName
                      ?? Environment.ProcessPath
                      ?? "";
            if (string.IsNullOrEmpty(exe)) { Log.Warn("SendToSync: Exe-Pfad unbekannt"); return; }
            var sync = new SendToSync(Log);
            sync.Sync(targets, exe);
        }
        catch (Exception ex)
        {
            Log.Warn($"SendToSync-Fehler: {ex.Message}");
        }
    }
}
