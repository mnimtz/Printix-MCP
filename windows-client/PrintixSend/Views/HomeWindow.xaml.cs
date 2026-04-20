using System;
using System.Threading.Tasks;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Media;
using PrintixSend.Models;
using PrintixSend.Services;

namespace PrintixSend.Views;

/// <summary>
/// Status-Fenster für das Tray-Icon:
/// - zeigt angemeldeten User + Server
/// - listet aktuelle Ziele (aus /desktop/targets)
/// - Buttons: Ziele aktualisieren, Einstellungen, Abmelden, Schließen
///
/// Schließen versteckt nur (Tray bleibt). Beenden läuft über das Tray-Menü.
/// </summary>
public partial class HomeWindow : Window
{
    public HomeWindow()
    {
        InitializeComponent();
        Loaded += async (_, _) => await RefreshAsync();
    }

    public async Task RefreshAsync()
    {
        TxtServer.Text = "Server: " + App.Config.ServerUrl;
        TxtUser.Text   = "Lade Status …";
        TargetsPanel.Children.Clear();
        var token = App.Tokens.LoadToken();
        if (string.IsNullOrEmpty(token))
        {
            TxtUser.Text = "Nicht angemeldet.";
            return;
        }
        try
        {
            using var api = new ApiClient(App.Config.ServerUrl, token, App.Log);
            var me = await api.GetMeAsync();
            TxtUser.Text = me == null
                ? "Angemeldet (Benutzerinfo nicht verfügbar)"
                : $"Angemeldet als {me.Email ?? me.Username} ({me.RoleType})";

            var targets = await api.GetTargetsAsync();
            foreach (var t in targets)
            {
                TargetsPanel.Children.Add(RenderTarget(t));
            }
            // Send-To-Einträge sofort mit synchronisieren
            var exe = Environment.ProcessPath
                      ?? System.Diagnostics.Process.GetCurrentProcess().MainModule?.FileName
                      ?? "";
            if (!string.IsNullOrEmpty(exe))
                new SendToSync(App.Log).Sync(targets, exe);
        }
        catch (Exception ex)
        {
            App.Log.Warn($"HomeWindow.Refresh: {ex.Message}");
            TxtUser.Text = "Fehler: " + ex.Message;
        }
    }

    private UIElement RenderTarget(Target t)
    {
        var b = new Border
        {
            Background = (Brush)App.Current.Resources["CardBrush"],
            BorderBrush = (Brush)App.Current.Resources["BorderBrush"],
            BorderThickness = new Thickness(1),
            CornerRadius = new CornerRadius(6),
            Padding = new Thickness(10),
            Margin = new Thickness(0, 0, 0, 6),
        };
        var sp = new StackPanel();
        sp.Children.Add(new TextBlock
        {
            Text = t.Label,
            FontWeight = FontWeights.SemiBold,
            Foreground = (Brush)App.Current.Resources["TextBrush"],
        });
        if (!string.IsNullOrEmpty(t.Description))
        {
            sp.Children.Add(new TextBlock
            {
                Text = t.Description,
                FontSize = 11,
                Foreground = (Brush)App.Current.Resources["MutedBrush"],
            });
        }
        b.Child = sp;
        return b;
    }

    private async void OnRefresh(object sender, RoutedEventArgs e) => await RefreshAsync();

    private void OnConfig(object sender, RoutedEventArgs e)
    {
        var cfg = new ConfigWindow { Owner = this };
        cfg.ShowDialog();
        _ = RefreshAsync();
    }

    private async void OnLogout(object sender, RoutedEventArgs e)
    {
        var result = MessageBox.Show(this,
            "Wirklich abmelden? Die \"Senden an\"-Einträge werden entfernt.",
            "Printix Send", MessageBoxButton.YesNo, MessageBoxImage.Question);
        if (result != MessageBoxResult.Yes) return;

        try
        {
            var token = App.Tokens.LoadToken();
            if (!string.IsNullOrEmpty(token))
            {
                using var api = new ApiClient(App.Config.ServerUrl, token, App.Log);
                await api.LogoutAsync();
            }
        }
        catch { /* ignore */ }
        App.Tokens.Clear();
        try { new SendToSync(App.Log).ClearAll(); } catch { /* ignore */ }
        await RefreshAsync();
    }

    private void OnClose(object sender, RoutedEventArgs e) => Hide();
}
