using System;
using System.IO;
using System.Text.Json;

namespace PrintixSend.Services;

/// <summary>
/// Config — Server-URL, Device-Name.
/// Wird in %LocalAppData%\PrintixSend\config.json abgelegt.
/// Unverschlüsselt (keine Secrets hier — Token liegt im TokenStore/DPAPI).
/// </summary>
public class ConfigService
{
    private readonly string _path;
    private ConfigData _data;

    public ConfigService()
    {
        var dir = Path.Combine(
            Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
            "PrintixSend");
        Directory.CreateDirectory(dir);
        _path = Path.Combine(dir, "config.json");
        _data = Load();
    }

    public string ServerUrl
    {
        get => _data.ServerUrl ?? "";
        set { _data.ServerUrl = value?.TrimEnd('/') ?? ""; Save(); }
    }

    public string DeviceName
    {
        get => string.IsNullOrWhiteSpace(_data.DeviceName)
            ? $"{Environment.MachineName}-{Environment.UserName}"
            : _data.DeviceName;
        set { _data.DeviceName = value ?? ""; Save(); }
    }

    public string DefaultTargetId
    {
        get => _data.DefaultTargetId ?? "";
        set { _data.DefaultTargetId = value ?? ""; Save(); }
    }

    public bool SendToHintShown
    {
        get => _data.SendToHintShown;
        set { _data.SendToHintShown = value; Save(); }
    }

    private ConfigData Load()
    {
        try
        {
            if (File.Exists(_path))
            {
                var json = File.ReadAllText(_path);
                return JsonSerializer.Deserialize<ConfigData>(json) ?? new ConfigData();
            }
        }
        catch { /* corrupt — ignore, fresh start */ }
        return new ConfigData();
    }

    private void Save()
    {
        try
        {
            var json = JsonSerializer.Serialize(_data, new JsonSerializerOptions { WriteIndented = true });
            File.WriteAllText(_path, json);
        }
        catch { /* ignore */ }
    }

    private class ConfigData
    {
        public string? ServerUrl { get; set; }
        public string? DeviceName { get; set; }
        public string? DefaultTargetId { get; set; }
        public bool SendToHintShown { get; set; }
    }
}
