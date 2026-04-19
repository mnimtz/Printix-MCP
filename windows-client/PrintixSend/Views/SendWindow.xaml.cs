using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Threading.Tasks;
using System.Windows;
using PrintixSend.Models;
using PrintixSend.Services;

namespace PrintixSend.Views;

public partial class SendWindow : Window
{
    private readonly string[] _files;
    private List<Target> _targets = new();

    public SendWindow(string[] files)
    {
        InitializeComponent();
        _files = files;
        foreach (var f in _files)
        {
            var fi = new FileInfo(f);
            LstFiles.Items.Add($"📄 {fi.Name}  ({FormatSize(fi.Length)})");
        }
        Loaded += async (_, _) => await InitializeAsync();
    }

    private async Task InitializeAsync()
    {
        SetBusy("Lade Ziele …", true);
        try
        {
            var token = App.Tokens.LoadToken();
            using var api = new ApiClient(App.Config.ServerUrl, token, App.Log);

            // Me
            var me = await api.GetMeAsync();
            TxtUserHint.Text = me == null
                ? "Nicht angemeldet"
                : $"Angemeldet als {me.Email ?? me.Username} ({me.RoleType})";

            // Targets
            _targets = await api.GetTargetsAsync();
            LstTargets.ItemsSource = _targets;

            // Default vorselektieren — bevorzugt zuletzt verwendet
            Target? pick = null;
            if (!string.IsNullOrEmpty(App.Config.DefaultTargetId))
                pick = _targets.FirstOrDefault(t => t.Id == App.Config.DefaultTargetId);
            pick ??= _targets.FirstOrDefault(t => t.IsDefault);
            pick ??= _targets.FirstOrDefault();
            if (pick != null) LstTargets.SelectedItem = pick;

            SetBusy(_targets.Count == 0 ? "Keine Ziele verfügbar." : $"{_targets.Count} Ziel(e) geladen.", false);
        }
        catch (Exception ex)
        {
            App.Log.Error("Targets-Abruf fehlgeschlagen", ex);
            // Token evtl. abgelaufen → Token löschen + beenden mit Hinweis
            if (ex.Message.Contains("401") || ex.Message.Contains("403"))
            {
                App.Tokens.Clear();
                MessageBox.Show(this, "Sitzung abgelaufen. Bitte erneut anmelden.",
                    "Printix Send", MessageBoxButton.OK, MessageBoxImage.Warning);
                Close();
                return;
            }
            SetBusy($"Fehler: {ex.Message}", false);
        }
    }

    private async void OnSend(object sender, RoutedEventArgs e)
    {
        if (LstTargets.SelectedItem is not Target t)
        {
            MessageBox.Show(this, "Bitte ein Ziel auswählen.", "Printix Send", MessageBoxButton.OK, MessageBoxImage.Information);
            return;
        }

        BtnSend.IsEnabled = false;
        SetBusy($"Sende {_files.Length} Datei(en) an „{t.Label}“ …", true);

        var token = App.Tokens.LoadToken();
        using var api = new ApiClient(App.Config.ServerUrl, token, App.Log);

        int ok = 0, fail = 0;
        var errors = new List<string>();

        foreach (var (f, i) in _files.Select((f, i) => (f, i)))
        {
            SetBusy($"[{i + 1}/{_files.Length}] {Path.GetFileName(f)} → {t.Label}", true);
            try
            {
                var result = await api.SendFileAsync(f, t.Id, comment: null);
                if (result.Ok) ok++;
                else
                {
                    fail++;
                    errors.Add($"{Path.GetFileName(f)}: {result.Error ?? result.Message ?? "unbekannt"}");
                }
            }
            catch (Exception ex)
            {
                App.Log.Error($"Send-Fehler für {f}", ex);
                fail++;
                errors.Add($"{Path.GetFileName(f)}: {ex.Message}");
            }
        }

        // Merke Ziel als neuen Default
        App.Config.DefaultTargetId = t.Id;

        SetBusy(null, false);
        if (fail == 0)
        {
            MessageBox.Show(this,
                $"✓ {ok} Datei(en) erfolgreich an „{t.Label}“ gesendet.",
                "Printix Send", MessageBoxButton.OK, MessageBoxImage.Information);
            Close();
        }
        else
        {
            var msg = $"{ok} erfolgreich, {fail} fehlgeschlagen.\n\n" + string.Join("\n", errors);
            MessageBox.Show(this, msg, "Printix Send", MessageBoxButton.OK, MessageBoxImage.Warning);
            BtnSend.IsEnabled = true;
        }
    }

    private async void OnLogout(object sender, RoutedEventArgs e)
    {
        try
        {
            var token = App.Tokens.LoadToken();
            using var api = new ApiClient(App.Config.ServerUrl, token, App.Log);
            await api.LogoutAsync();
        }
        catch { /* ignore */ }
        App.Tokens.Clear();
        Close();
    }

    private void OnCancel(object sender, RoutedEventArgs e) => Close();

    private void SetBusy(string? status, bool busy)
    {
        if (status != null) TxtStatus.Text = status;
        ProgBar.Visibility = busy ? Visibility.Visible : Visibility.Collapsed;
        ProgBar.IsIndeterminate = busy;
    }

    private static string FormatSize(long bytes)
    {
        if (bytes < 1024) return $"{bytes} B";
        if (bytes < 1024 * 1024) return $"{bytes / 1024.0:F1} KB";
        return $"{bytes / (1024.0 * 1024.0):F1} MB";
    }
}
