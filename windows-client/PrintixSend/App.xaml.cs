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

        // 3a. Start ohne Dateien: Send-To-Einträge synchronisieren und still beenden.
        //     Der User nutzt den Explorer-"Senden an"-Kontext statt eines Datei-Dialogs.
        if (files.Length == 0)
        {
            Log.Info("Keine Dateien übergeben — synchronisiere 'Senden an' und beende.");
            await SyncSendToMenuAsync();
            // Kurzer Hinweis beim ersten Mal, danach still (keine Dialog-Flut)
            if (!Config.SendToHintShown)
            {
                MessageBox.Show(
                    "Printix Send ist eingerichtet.\n\n" +
                    "Rechtsklick auf eine Datei → „Senden an" → wähle dein Ziel (z. B. „Mein Secure Print" oder einen Delegate).\n\n" +
                    "Die Ziele werden automatisch aus dem Server übernommen.",
                    "Printix Send", MessageBoxButton.OK, MessageBoxImage.Information);
                Config.SendToHintShown = true;
            }
            Shutdown();
            return;
        }

        // 3b. Dateien + evtl. preselect-Target → Send-Fenster öffnen
        Log.Info($"{files.Length} Datei(en) übergeben, preselectTarget={preselectTarget ?? "<keins>"}");
        // Send-To-Sync im Hintergrund anstoßen, blockiert den Send nicht
        _ = SyncSendToMenuAsync();

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
