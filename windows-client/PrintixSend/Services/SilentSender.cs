using System;
using System.IO;
using System.Linq;
using System.Threading.Tasks;
using System.Windows;

namespace PrintixSend.Services;

/// <summary>
/// Führt das Senden rein im Hintergrund aus — kein Fenster, kein Fortschrittsdialog.
///
/// Wird vom "Senden an"-Kontextmenü aus aufgerufen (PrintixSend.exe --target=&lt;id&gt; &lt;files...&gt;):
/// Die UI-Unterbrechung (alte SendWindow mit "Lade Ziele …") entfällt.
/// Erfolg = still beenden. Fehler = einmalige MessageBox (Abbruch darf nicht unbemerkt bleiben).
/// </summary>
public static class SilentSender
{
    public static async Task RunAsync(string[] files, string targetId)
    {
        App.Log.Info($"SilentSender — {files.Length} Datei(en) → target={targetId}");
        var token = App.Tokens.LoadToken();
        if (string.IsNullOrEmpty(token))
        {
            App.Log.Warn("SilentSender: kein Token — Abbruch.");
            ShowError("Nicht angemeldet.\nBitte Printix Send einmal öffnen und anmelden.");
            return;
        }

        using var api = new ApiClient(App.Config.ServerUrl, token, App.Log);

        // Ziel-Label für Fehlermeldung auflösen (best effort, nicht blockierend)
        string? targetLabel = null;
        try
        {
            var targets = await api.GetTargetsAsync();
            targetLabel = targets.FirstOrDefault(t => t.Id == targetId)?.Label;
        }
        catch (Exception ex) { App.Log.Warn($"SilentSender: Targets-Abruf fehlgeschlagen: {ex.Message}"); }

        int ok = 0, fail = 0;
        var errors = new System.Collections.Generic.List<string>();

        foreach (var f in files)
        {
            try
            {
                App.Log.Info($"SilentSender — sende {Path.GetFileName(f)}");
                var r = await api.SendFileAsync(f, targetId, comment: null);
                if (r.Ok) ok++;
                else { fail++; errors.Add($"{Path.GetFileName(f)}: {r.Error ?? r.Message ?? "unbekannt"}"); }
            }
            catch (Exception ex)
            {
                App.Log.Error($"SilentSender — Fehler bei {f}", ex);
                fail++;
                errors.Add($"{Path.GetFileName(f)}: {ex.Message}");
            }
        }

        // Ziel als Default merken — nächstes Mal wäre es wieder die bevorzugte Wahl
        App.Config.DefaultTargetId = targetId;

        App.Log.Info($"SilentSender — fertig: {ok} ok, {fail} fail");

        if (fail == 0)
        {
            // Erfolg = absolut still. Kein Fenster, kein Piepen. Nutzer sieht
            // das Ergebnis im Printix-Client oder am Drucker.
            return;
        }

        // Fehler muss der Nutzer mitbekommen
        var labelPart = string.IsNullOrEmpty(targetLabel) ? "" : $" an „{targetLabel}\"";
        var header = ok > 0
            ? $"{ok} von {files.Length} Datei(en){labelPart} gesendet.\n\nFehler:\n"
            : $"Senden{labelPart} fehlgeschlagen.\n\n";
        ShowError(header + string.Join("\n", errors));
    }

    private static void ShowError(string msg)
    {
        try
        {
            MessageBox.Show(msg, "Printix Send", MessageBoxButton.OK, MessageBoxImage.Error);
        }
        catch (Exception ex) { App.Log.Warn($"SilentSender.ShowError: {ex.Message}"); }
    }
}
