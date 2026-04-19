using System;
using System.Diagnostics;
using System.Threading;
using System.Threading.Tasks;
using System.Windows;
using PrintixSend.Models;
using PrintixSend.Services;

namespace PrintixSend.Views;

public partial class EntraDeviceWindow : Window
{
    private readonly EntraStartResponse _start;
    private readonly CancellationTokenSource _cts = new();
    public string? ResultToken { get; private set; }

    public EntraDeviceWindow(EntraStartResponse start)
    {
        InitializeComponent();
        _start = start;
        TxtCode.Text = start.UserCode ?? "?";
        TxtUri.Text = start.VerificationUri ?? "";
        Loaded += async (_, _) => await PollLoopAsync(_cts.Token);
        Closed += (_, _) => _cts.Cancel();
    }

    private void OnOpenBrowser(object sender, RoutedEventArgs e)
    {
        if (string.IsNullOrEmpty(_start.VerificationUri)) return;
        try
        {
            Process.Start(new ProcessStartInfo(_start.VerificationUri) { UseShellExecute = true });
        }
        catch (Exception ex)
        {
            App.Log.Error("Browser öffnen fehlgeschlagen", ex);
            MessageBox.Show(this, $"Browser konnte nicht geöffnet werden.\nURL: {_start.VerificationUri}",
                "Printix Send", MessageBoxButton.OK, MessageBoxImage.Warning);
        }
    }

    private async Task PollLoopAsync(CancellationToken ct)
    {
        if (string.IsNullOrEmpty(_start.DeviceCode))
        {
            TxtStatus.Text = "Kein Device-Code erhalten.";
            return;
        }

        var interval = Math.Max(3, _start.Interval);
        var deadline = DateTime.UtcNow.AddSeconds(Math.Max(60, _start.ExpiresIn));

        using var api = new ApiClient(App.Config.ServerUrl, null, App.Log);

        while (!ct.IsCancellationRequested && DateTime.UtcNow < deadline)
        {
            try
            {
                await Task.Delay(TimeSpan.FromSeconds(interval), ct);
                var poll = await api.EntraPollAsync(_start.DeviceCode, ct);
                if (poll == null) continue;

                if (poll.Status == "ok" && !string.IsNullOrEmpty(poll.Token))
                {
                    ResultToken = poll.Token;
                    TxtStatus.Text = $"✓ Angemeldet als {poll.User?.Email ?? poll.User?.Username}";
                    ProgBar.IsIndeterminate = false;
                    ProgBar.Value = 100;
                    await Task.Delay(600, ct);
                    DialogResult = true;
                    Close();
                    return;
                }
                if (poll.Status == "error")
                {
                    TxtStatus.Text = $"Fehler: {poll.Error ?? "unbekannt"}";
                    ProgBar.IsIndeterminate = false;
                    return;
                }
                // "pending" → weiter pollen
                TxtStatus.Text = "Warte auf Anmeldung im Browser…";
            }
            catch (OperationCanceledException) { return; }
            catch (Exception ex)
            {
                App.Log.Warn($"Poll-Fehler (retry): {ex.Message}");
            }
        }

        if (!ct.IsCancellationRequested)
            TxtStatus.Text = "Zeit abgelaufen — bitte erneut starten.";
    }

    private void OnCancel(object sender, RoutedEventArgs e)
    {
        _cts.Cancel();
        DialogResult = false;
        Close();
    }
}
