using System;
using System.Windows;
using PrintixSend.Services;

namespace PrintixSend.Views;

public partial class LoginWindow : Window
{
    public LoginWindow()
    {
        InitializeComponent();
        TxtServerHint.Text = $"Server: {App.Config.ServerUrl}";
    }

    private async void OnLocalLogin(object sender, RoutedEventArgs e)
    {
        var user = TxtUsername.Text?.Trim() ?? "";
        var pw   = TxtPassword.Password;
        if (string.IsNullOrEmpty(user) || string.IsNullOrEmpty(pw))
        {
            ShowError("Benutzername und Passwort erforderlich.");
            return;
        }

        IsEnabled = false;
        ShowError(null);
        try
        {
            using var api = new ApiClient(App.Config.ServerUrl, null, App.Log);
            var result = await api.LoginAsync(user, pw, App.Config.DeviceName);
            if (result?.Token == null)
            {
                ShowError("Login fehlgeschlagen — Anmeldedaten prüfen.");
                return;
            }
            App.Tokens.SaveToken(result.Token);
            App.Log.Info($"Lokaler Login ok — user={result.User?.Username}");
            DialogResult = true;
            Close();
        }
        catch (Exception ex)
        {
            App.Log.Error("Lokaler Login Exception", ex);
            ShowError($"Netzwerk-Fehler: {ex.Message}");
        }
        finally { IsEnabled = true; }
    }

    private async void OnEntraLogin(object sender, RoutedEventArgs e)
    {
        IsEnabled = false;
        try
        {
            using var api = new ApiClient(App.Config.ServerUrl, null, App.Log);
            var start = await api.EntraStartAsync(App.Config.DeviceName);
            if (start == null || string.IsNullOrEmpty(start.DeviceCode))
            {
                ShowError("Entra-Start fehlgeschlagen — Server-Logs prüfen.");
                return;
            }
            var dev = new EntraDeviceWindow(start) { Owner = this };
            if (dev.ShowDialog() == true && !string.IsNullOrEmpty(dev.ResultToken))
            {
                App.Tokens.SaveToken(dev.ResultToken);
                App.Log.Info("Entra-Login ok");
                DialogResult = true;
                Close();
            }
        }
        catch (Exception ex)
        {
            App.Log.Error("Entra-Login Exception", ex);
            ShowError($"Netzwerk-Fehler: {ex.Message}");
        }
        finally { IsEnabled = true; }
    }

    private void OnSettings(object sender, RoutedEventArgs e)
    {
        var cfg = new ConfigWindow { Owner = this };
        if (cfg.ShowDialog() == true)
            TxtServerHint.Text = $"Server: {App.Config.ServerUrl}";
    }

    private void ShowError(string? msg)
    {
        if (string.IsNullOrEmpty(msg))
        {
            TxtError.Visibility = Visibility.Collapsed;
            TxtError.Text = "";
        }
        else
        {
            TxtError.Text = msg;
            TxtError.Visibility = Visibility.Visible;
        }
    }
}
