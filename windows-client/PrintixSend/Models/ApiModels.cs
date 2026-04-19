using System.Text.Json.Serialization;

namespace PrintixSend.Models;

public class UserInfo
{
    [JsonPropertyName("id")]         public string? Id { get; set; }
    [JsonPropertyName("username")]   public string? Username { get; set; }
    [JsonPropertyName("email")]      public string? Email { get; set; }
    [JsonPropertyName("full_name")]  public string? FullName { get; set; }
    [JsonPropertyName("role_type")]  public string? RoleType { get; set; }
    [JsonPropertyName("device_name")]public string? DeviceName { get; set; }
}

public class LoginResponse
{
    [JsonPropertyName("token")] public string? Token { get; set; }
    [JsonPropertyName("user")]  public UserInfo? User { get; set; }
}

public class Target
{
    [JsonPropertyName("id")]              public string Id { get; set; } = "";
    [JsonPropertyName("type")]            public string Type { get; set; } = "";
    [JsonPropertyName("label")]           public string Label { get; set; } = "";
    [JsonPropertyName("description")]     public string? Description { get; set; }
    [JsonPropertyName("icon")]            public string? Icon { get; set; }
    [JsonPropertyName("is_default")]      public bool IsDefault { get; set; }
    [JsonPropertyName("delegate_email")]  public string? DelegateEmail { get; set; }
}

public class TargetsResponse
{
    [JsonPropertyName("targets")] public List<Target> Targets { get; set; } = new();
}

public class SendResult
{
    [JsonPropertyName("ok")]              public bool Ok { get; set; }
    [JsonPropertyName("job_id")]          public string? JobId { get; set; }
    [JsonPropertyName("printix_job_id")]  public string? PrintixJobId { get; set; }
    [JsonPropertyName("target")]          public string? Target { get; set; }
    [JsonPropertyName("filename")]        public string? Filename { get; set; }
    [JsonPropertyName("size")]            public long Size { get; set; }
    [JsonPropertyName("owner_email")]     public string? OwnerEmail { get; set; }
    [JsonPropertyName("error")]           public string? Error { get; set; }
    [JsonPropertyName("message")]         public string? Message { get; set; }
}

public class EntraStartResponse
{
    [JsonPropertyName("user_code")]        public string? UserCode { get; set; }
    [JsonPropertyName("verification_uri")] public string? VerificationUri { get; set; }
    [JsonPropertyName("device_code")]      public string? DeviceCode { get; set; }
    [JsonPropertyName("interval")]         public int Interval { get; set; } = 5;
    [JsonPropertyName("expires_in")]       public int ExpiresIn { get; set; } = 900;
    [JsonPropertyName("message")]          public string? Message { get; set; }
}

public class EntraPollResponse
{
    [JsonPropertyName("status")] public string? Status { get; set; }   // "pending" | "ok" | "error"
    [JsonPropertyName("token")]  public string? Token { get; set; }
    [JsonPropertyName("user")]   public UserInfo? User { get; set; }
    [JsonPropertyName("error")]  public string? Error { get; set; }
}

public class VersionResponse
{
    [JsonPropertyName("server_version")]     public string? ServerVersion { get; set; }
    [JsonPropertyName("min_client_version")] public string? MinClientVersion { get; set; }
    [JsonPropertyName("download_url")]       public string? DownloadUrl { get; set; }
    [JsonPropertyName("api_version")]        public string? ApiVersion { get; set; }
}
