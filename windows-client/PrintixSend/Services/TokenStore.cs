using System;
using System.IO;
using System.Security.Cryptography;
using System.Text;

namespace PrintixSend.Services;

/// <summary>
/// Token sicher speichern via Windows DPAPI (CurrentUser-Scope).
/// Datei-Ablage: %LocalAppData%\PrintixSend\token.bin
/// Nur der aktuelle Windows-User kann den Token entschlüsseln.
/// </summary>
public class TokenStore
{
    private readonly string _path;

    public TokenStore()
    {
        var dir = Path.Combine(
            Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
            "PrintixSend");
        Directory.CreateDirectory(dir);
        _path = Path.Combine(dir, "token.bin");
    }

    public void SaveToken(string token)
    {
        if (string.IsNullOrEmpty(token))
        {
            Clear();
            return;
        }
        var raw = Encoding.UTF8.GetBytes(token);
        var enc = ProtectedData.Protect(raw, null, DataProtectionScope.CurrentUser);
        File.WriteAllBytes(_path, enc);
    }

    public string? LoadToken()
    {
        try
        {
            if (!File.Exists(_path)) return null;
            var enc = File.ReadAllBytes(_path);
            var raw = ProtectedData.Unprotect(enc, null, DataProtectionScope.CurrentUser);
            return Encoding.UTF8.GetString(raw);
        }
        catch
        {
            return null;
        }
    }

    public void Clear()
    {
        try { if (File.Exists(_path)) File.Delete(_path); }
        catch { /* ignore */ }
    }

    public bool HasToken() => !string.IsNullOrWhiteSpace(LoadToken());
}
