using System;
using System.IO;
using System.Net.Http;
using System.Net.Http.Headers;
using System.Net.Http.Json;
using System.Text.Json;
using System.Threading;
using System.Threading.Tasks;
using PrintixSend.Models;

namespace PrintixSend.Services;

/// <summary>
/// Kommuniziert mit dem Printix-MCP-Desktop-API (Phase A).
/// Endpunkte: /desktop/auth/login, /desktop/auth/logout, /desktop/me,
/// /desktop/targets, /desktop/send, /desktop/auth/entra/start + /poll,
/// /desktop/client/latest-version
/// </summary>
public class ApiClient : IDisposable
{
    private readonly HttpClient _http;
    private readonly string _baseUrl;
    private readonly Logger _log;
    private string? _token;

    public ApiClient(string baseUrl, string? token, Logger log)
    {
        _baseUrl = baseUrl.TrimEnd('/');
        _token = token;
        _log = log;
        // Standard-Timeout kurz halten, damit die UI nicht minutenlang
        // hängt. Der Upload (SendFileAsync) setzt einen eigenen längeren
        // CancellationToken, der den HttpClient-Default überschreibt.
        _http = new HttpClient
        {
            Timeout = TimeSpan.FromSeconds(30)
        };
        _http.DefaultRequestHeaders.UserAgent.ParseAdd("PrintixSend-Windows/6.7.49");
        if (!string.IsNullOrEmpty(_token))
            _http.DefaultRequestHeaders.Authorization = new AuthenticationHeaderValue("Bearer", _token);
    }

    public void SetToken(string? token)
    {
        _token = token;
        _http.DefaultRequestHeaders.Authorization = string.IsNullOrEmpty(token)
            ? null
            : new AuthenticationHeaderValue("Bearer", token);
    }

    private string MaskToken(string? t)
        => string.IsNullOrEmpty(t) ? "<null>" : (t.Length > 8 ? $"{t[..4]}…{t[^4..]}" : "<short>");

    // ── Login (lokal) ──────────────────────────────────────────
    public async Task<LoginResponse?> LoginAsync(string username, string password, string deviceName, CancellationToken ct = default)
    {
        _log.Info($"POST {_baseUrl}/desktop/auth/login — user={username} device={deviceName}");
        var req = new
        {
            username,
            password,
            device_name = deviceName
        };
        var resp = await _http.PostAsJsonAsync($"{_baseUrl}/desktop/auth/login", req, ct);
        var body = await resp.Content.ReadAsStringAsync(ct);
        if (!resp.IsSuccessStatusCode)
        {
            _log.Warn($"Login fehlgeschlagen: HTTP {(int)resp.StatusCode} — {body}");
            return null;
        }
        var result = JsonSerializer.Deserialize<LoginResponse>(body);
        if (result?.Token != null)
        {
            SetToken(result.Token);
            _log.Info($"Login ok — token={MaskToken(result.Token)} user={result.User?.Username}");
        }
        return result;
    }

    // ── Logout ────────────────────────────────────────────────
    public async Task LogoutAsync(CancellationToken ct = default)
    {
        try
        {
            _log.Info("POST /desktop/auth/logout");
            await _http.PostAsync($"{_baseUrl}/desktop/auth/logout", null, ct);
        }
        catch (Exception ex) { _log.Warn($"Logout-Fehler (ignoriert): {ex.Message}"); }
    }

    // ── /me ───────────────────────────────────────────────────
    public async Task<UserInfo?> GetMeAsync(CancellationToken ct = default)
    {
        _log.Info($"GET {_baseUrl}/desktop/me");
        try
        {
            var resp = await _http.GetAsync($"{_baseUrl}/desktop/me", ct);
            if (!resp.IsSuccessStatusCode)
            {
                _log.Warn($"Me-Fehler: HTTP {(int)resp.StatusCode}");
                return null;
            }
            var json = await resp.Content.ReadAsStringAsync(ct);
            using var doc = JsonDocument.Parse(json);
            if (doc.RootElement.TryGetProperty("user", out var u))
            {
                var info = JsonSerializer.Deserialize<UserInfo>(u.GetRawText());
                _log.Info($"Me ok — user={info?.Username}");
                return info;
            }
            return null;
        }
        catch (TaskCanceledException)
        {
            _log.Warn("Me-Abruf Timeout (30s) — server nicht erreichbar?");
            return null;
        }
        catch (Exception ex)
        {
            _log.Warn($"Me-Abruf Fehler: {ex.Message}");
            return null;
        }
    }

    // ── Targets ───────────────────────────────────────────────
    public async Task<List<Target>> GetTargetsAsync(CancellationToken ct = default)
    {
        _log.Info($"GET {_baseUrl}/desktop/targets");
        var resp = await _http.GetAsync($"{_baseUrl}/desktop/targets", ct);
        if (!resp.IsSuccessStatusCode)
        {
            var err = await resp.Content.ReadAsStringAsync(ct);
            _log.Warn($"Targets-Fehler: HTTP {(int)resp.StatusCode} — {err}");
            throw new HttpRequestException($"Targets-Abruf fehlgeschlagen (HTTP {(int)resp.StatusCode}).");
        }
        var tr = await resp.Content.ReadFromJsonAsync<TargetsResponse>(cancellationToken: ct);
        _log.Info($"Targets: {tr?.Targets.Count ?? 0} Eintrag/Einträge");
        return tr?.Targets ?? new();
    }

    // ── Send ──────────────────────────────────────────────────
    public async Task<SendResult> SendFileAsync(string filePath, string targetId, string? comment,
                                                IProgress<double>? progress = null, CancellationToken ct = default)
    {
        if (!File.Exists(filePath))
            throw new FileNotFoundException("Datei nicht gefunden", filePath);

        var fi = new FileInfo(filePath);
        _log.Info($"POST /desktop/send — target={targetId} file={fi.Name} size={fi.Length}");

        using var form = new MultipartFormDataContent();
        // Server erwartet 'target_id' (nicht 'target') — siehe
        // desktop_routes.py:desktop_send(target_id: str = Form(...)).
        form.Add(new StringContent(targetId), "target_id");
        if (!string.IsNullOrWhiteSpace(comment))
            form.Add(new StringContent(comment), "comment");

        // Streaming-Upload (IProgress optional, grobe Meldungen)
        var fileStream = File.OpenRead(filePath);
        var fileContent = new StreamContent(fileStream);
        fileContent.Headers.ContentType = new MediaTypeHeaderValue(GuessMime(fi.Extension));
        form.Add(fileContent, "file", fi.Name);

        progress?.Report(0.1);
        // Upload darf länger dauern als der Default-Timeout von 30s.
        // Wir nutzen SendAsync mit einer expliziten Frist von 10 Minuten
        // per linked CTS, damit der HttpClient-Default umgangen wird.
        using var uploadCts = CancellationTokenSource.CreateLinkedTokenSource(ct);
        uploadCts.CancelAfter(TimeSpan.FromMinutes(10));
        using var sendRequest = new HttpRequestMessage(HttpMethod.Post, $"{_baseUrl}/desktop/send")
        {
            Content = form
        };
        var resp = await _http.SendAsync(sendRequest, HttpCompletionOption.ResponseHeadersRead, uploadCts.Token);
        progress?.Report(0.9);
        var body = await resp.Content.ReadAsStringAsync(ct);

        if (!resp.IsSuccessStatusCode)
        {
            _log.Warn($"Send-Fehler: HTTP {(int)resp.StatusCode} — {body}");
            // Server liefert evtl. {"error":"...","message":"..."}
            try
            {
                var errResult = JsonSerializer.Deserialize<SendResult>(body);
                if (errResult != null) return errResult;
            }
            catch { /* ignore */ }
            return new SendResult { Ok = false, Error = $"HTTP {(int)resp.StatusCode}", Message = body };
        }

        progress?.Report(1.0);
        var result = JsonSerializer.Deserialize<SendResult>(body) ?? new SendResult { Ok = false, Error = "parse_error" };
        _log.Info($"Send ok — job_id={result.JobId} printix_job_id={result.PrintixJobId}");
        return result;
    }

    // ── Entra: Device-Code ────────────────────────────────────
    public async Task<EntraStartResponse?> EntraStartAsync(string deviceName, CancellationToken ct = default)
    {
        _log.Info("POST /desktop/auth/entra/start");
        var req = new { device_name = deviceName };
        var resp = await _http.PostAsJsonAsync($"{_baseUrl}/desktop/auth/entra/start", req, ct);
        var body = await resp.Content.ReadAsStringAsync(ct);
        if (!resp.IsSuccessStatusCode)
        {
            _log.Warn($"Entra-Start fehlgeschlagen: HTTP {(int)resp.StatusCode} — {body}");
            return null;
        }
        return JsonSerializer.Deserialize<EntraStartResponse>(body);
    }

    public async Task<EntraPollResponse?> EntraPollAsync(string deviceCode, CancellationToken ct = default)
    {
        var req = new { device_code = deviceCode };
        var resp = await _http.PostAsJsonAsync($"{_baseUrl}/desktop/auth/entra/poll", req, ct);
        var body = await resp.Content.ReadAsStringAsync(ct);
        return JsonSerializer.Deserialize<EntraPollResponse>(body);
    }

    // ── Version ───────────────────────────────────────────────
    public async Task<VersionResponse?> GetLatestVersionAsync(CancellationToken ct = default)
    {
        try
        {
            var resp = await _http.GetAsync($"{_baseUrl}/desktop/client/latest-version", ct);
            if (!resp.IsSuccessStatusCode) return null;
            return await resp.Content.ReadFromJsonAsync<VersionResponse>(cancellationToken: ct);
        }
        catch { return null; }
    }

    private static string GuessMime(string ext) => ext.ToLowerInvariant() switch
    {
        ".pdf"  => "application/pdf",
        ".png"  => "image/png",
        ".jpg" or ".jpeg" => "image/jpeg",
        ".gif"  => "image/gif",
        ".txt"  => "text/plain",
        ".docx" => "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ".xlsx" => "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        ".pptx" => "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        ".doc"  => "application/msword",
        ".xls"  => "application/vnd.ms-excel",
        ".ppt"  => "application/vnd.ms-powerpoint",
        _       => "application/octet-stream"
    };

    public void Dispose() => _http.Dispose();
}
