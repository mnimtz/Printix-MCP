using System;
using System.Windows;

namespace PrintixSend.Views;

public partial class ConfigWindow : Window
{
    public ConfigWindow()
    {
        InitializeComponent();
        TxtServerUrl.Text = string.IsNullOrWhiteSpace(App.Config.ServerUrl) ? "https://printix.cloud" : App.Config.ServerUrl;
        TxtDeviceName.Text = App.Config.DeviceName;
    }

    private void OnSave(object sender, RoutedEventArgs e)
    {
        var url = TxtServerUrl.Text?.Trim() ?? "";
        if (!Uri.TryCreate(url, UriKind.Absolute, out var uri) ||
            (uri.Scheme != "https" && uri.Scheme != "http"))
        {
            TxtError.Text = "Bitte eine gültige URL eingeben (https://…).";
            TxtError.Visibility = Visibility.Visible;
            return;
        }
        App.Config.ServerUrl = url;
        App.Config.DeviceName = TxtDeviceName.Text?.Trim() ?? "";
        App.Log.Info($"Config gespeichert — server={App.Config.ServerUrl} device={App.Config.DeviceName}");
        DialogResult = true;
        Close();
    }

    private void OnCancel(object sender, RoutedEventArgs e)
    {
        DialogResult = false;
        Close();
    }
}
