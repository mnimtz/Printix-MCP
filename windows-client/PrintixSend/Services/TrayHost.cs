using System;
using System.ComponentModel;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Media.Imaging;
using Hardcodet.Wpf.TaskbarNotification;
using PrintixSend.Views;

namespace PrintixSend.Services;

/// <summary>
/// Permanentes Tray-Icon im Benachrichtigungsbereich (neben der Uhr).
///
/// - Linksklick öffnet das HomeWindow
/// - Rechtsklick: Öffnen / Ziele aktualisieren / Einstellungen / Abmelden / Beenden
/// - Schließen des HomeWindow versteckt es nur — Tray bleibt; App läuft weiter.
/// - "Beenden" ruft Application.Shutdown() auf.
/// </summary>
public class TrayHost : IDisposable
{
    private TaskbarIcon? _tray;
    private HomeWindow? _home;
    private bool _disposed;

    public void Show()
    {
        _tray = new TaskbarIcon
        {
            ToolTipText = "Printix Send",
        };

        // Icon aus den eingebetteten WPF-Resources laden (app.ico).
        try
        {
            var uri = new Uri("pack://application:,,,/Resources/app.ico", UriKind.Absolute);
            _tray.IconSource = new BitmapImage(uri);
        }
        catch (Exception ex) { App.Log.Warn($"Tray-Icon konnte nicht geladen werden: {ex.Message}"); }

        // Kontextmenü
        var menu = new ContextMenu();
        menu.Items.Add(MenuItem("Öffnen",              (_, _) => ShowHome()));
        menu.Items.Add(MenuItem("Ziele aktualisieren", async (_, _) => { ShowHome(); if (_home != null) await _home.RefreshAsync(); }));
        menu.Items.Add(new Separator());
        menu.Items.Add(MenuItem("Server-Einstellungen …", (_, _) => OpenConfig()));
        menu.Items.Add(MenuItem("Abmelden",               (_, _) => Logout()));
        menu.Items.Add(new Separator());
        menu.Items.Add(MenuItem("Beenden", (_, _) => ExitApp()));
        _tray.ContextMenu = menu;

        // Linksklick öffnet Home
        _tray.TrayLeftMouseUp += (_, _) => ShowHome();

        App.Log.Info("Tray-Icon aktiv.");
    }

    private static MenuItem MenuItem(string header, RoutedEventHandler click)
    {
        var mi = new MenuItem { Header = header };
        mi.Click += click;
        return mi;
    }

    private void ShowHome()
    {
        if (_home == null)
        {
            _home = new HomeWindow();
            _home.Closing += OnHomeClosing;
        }
        _home.Show();
        if (_home.WindowState == WindowState.Minimized) _home.WindowState = WindowState.Normal;
        _home.Activate();
    }

    private void OnHomeClosing(object? sender, CancelEventArgs e)
    {
        if (_disposed) return;
        // Schließen versteckt nur — Tray bleibt, App läuft weiter
        e.Cancel = true;
        _home?.Hide();
    }

    private void OpenConfig()
    {
        var cfg = new ConfigWindow();
        cfg.ShowDialog();
    }

    private async void Logout()
    {
        var r = MessageBox.Show(
            "Wirklich abmelden? Die „Senden an\"-Einträge werden entfernt.",
            "Printix Send", MessageBoxButton.YesNo, MessageBoxImage.Question);
        if (r != MessageBoxResult.Yes) return;
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
    }

    private void ExitApp()
    {
        App.Log.Info("Tray: Beenden angefordert.");
        Dispose();
        Application.Current.Shutdown();
    }

    public void Dispose()
    {
        if (_disposed) return;
        _disposed = true;
        try
        {
            if (_home != null)
            {
                _home.Closing -= OnHomeClosing;
                _home.Close();
                _home = null;
            }
            _tray?.Dispose();
            _tray = null;
        }
        catch { /* ignore */ }
    }
}
