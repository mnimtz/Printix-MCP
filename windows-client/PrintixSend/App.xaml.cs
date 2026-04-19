using System;
using System.IO;
using System.Linq;
using System.Windows;
using PrintixSend.Services;
using PrintixSend.Views;

namespace PrintixSend;

public partial class App : Application
{
    public static ConfigService Config { get; } = new();
    public static TokenStore Tokens { get; } = new();
    public static Logger Log { get; } = new();

    protected override void OnStartup(StartupEventArgs e)
    {
        base.OnStartup(e);
        Log.Info($"Printix Send gestartet — Args: {e.Args.Length}");

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

        // 3. Dateien aus Command-Line — oder über OpenFileDialog
        var files = e.Args.Where(File.Exists).ToArray();
        if (files.Length == 0)
        {
            var dlg = new Microsoft.Win32.OpenFileDialog
            {
                Title = "Datei zum Senden auswählen",
                Multiselect = true,
                Filter = "Alle Dateien (*.*)|*.*|PDF (*.pdf)|*.pdf|Office (*.docx;*.xlsx;*.pptx)|*.docx;*.xlsx;*.pptx|Bilder (*.png;*.jpg)|*.png;*.jpg;*.jpeg"
            };
            if (dlg.ShowDialog() == true)
                files = dlg.FileNames;
        }

        if (files.Length == 0)
        {
            Log.Info("Keine Dateien ausgewählt — beende");
            Shutdown();
            return;
        }

        Log.Info($"{files.Length} Datei(en) übergeben");
        var send = new SendWindow(files);
        send.Show();
    }
}
