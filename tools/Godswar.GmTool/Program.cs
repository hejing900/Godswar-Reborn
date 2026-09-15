using System.Text.Json;
using Godswar.GmTool;
using Npgsql;

var builder = WebApplication.CreateBuilder(args);

var connectionString = GmConnection.Resolve(builder.Configuration, args);
var bindUrl = Environment.GetEnvironmentVariable("GODSWAR_GM_BIND_URL") ?? "http://127.0.0.1:8090";
builder.WebHost.UseUrls(bindUrl);

builder.Services.AddSingleton(_ => NpgsqlDataSource.Create(connectionString));
builder.Services.AddSingleton(_ => ClientLocalization.Load(GmConnection.ResolveClientRoot(args)));
builder.Services.AddSingleton<GmStore>();
// The UI is a static page: it may be opened from the tool's own origin, from
// file://, or from another local page. Allow those callers so a mis-opened page
// still reports a real database result instead of an opaque fetch failure.
// The listener stays loopback-bound; write access still requires the operator
// to confirm the target character is offline on every request.
builder.Services.AddCors(options => options.AddDefaultPolicy(policy => policy
    .AllowAnyOrigin()
    .AllowAnyHeader()
    .AllowAnyMethod()));
builder.Services.ConfigureHttpJsonOptions(options =>
{
    options.SerializerOptions.PropertyNamingPolicy = JsonNamingPolicy.CamelCase;
    options.SerializerOptions.WriteIndented = false;
});

var app = builder.Build();
app.UseCors();
app.UseDefaultFiles();
app.UseStaticFiles();

app.MapGet("/api/status", async (GmStore store, CancellationToken token) =>
{
    try
    {
        return Results.Ok(new
        {
            ok = true,
            connection = GmConnection.Describe(connectionString),
            server = await store.ReadServerInfoAsync(token)
        });
    }
    catch (Exception error)
    {
        return Results.Json(
            new { ok = false, error = error.Message, connection = GmConnection.Describe(connectionString) },
            statusCode: StatusCodes.Status503ServiceUnavailable);
    }
});

app.MapGet("/api/characters", async (
    string? name,
    int? limit,
    GmStore store,
    CancellationToken token) =>
{
    var rows = await store.SearchCharactersAsync(name, limit ?? 50, token);
    return Results.Ok(new { count = rows.Count, characters = rows });
});

app.MapGet("/api/characters/{id:int}", async (
    int id,
    GmStore store,
    CancellationToken token) =>
{
    var character = await store.ReadCharacterAsync(id, token);
    return character is null
        ? Results.NotFound(new { error = $"角色不存在：id={id}" })
        : Results.Ok(character);
});

app.MapGet("/api/items", async (
    string? q,
    string? kind,
    int? limit,
    GmStore store,
    CancellationToken token) =>
{
    var rows = await store.SearchItemsAsync(q, kind, limit ?? 60, token);
    return Results.Ok(new { count = rows.Count, items = rows });
});

app.MapGet("/api/items/kinds", async (GmStore store, CancellationToken token) =>
    Results.Ok(await store.ReadItemKindsAsync(token)));

app.MapPost("/api/grant", async (
    GrantRequestPayload payload,
    GmStore store,
    CancellationToken token) =>
{
    if (payload.CharacterId <= 0 || payload.ItemId <= 0)
    {
        return Results.BadRequest(new { error = "characterId 与 itemId 必须为正整数。" });
    }

    if (!payload.ConfirmOffline)
    {
        return Results.Json(
            new
            {
                error = "未确认角色已下线。直连写库时若角色仍在游戏中，" +
                        "服务器内存中的角色状态会在下次存档时覆盖本次发放。" +
                        "请先让角色下线，然后勾选确认。"
            },
            statusCode: StatusCodes.Status409Conflict);
    }

    try
    {
        var outcome = await store.GrantAsync(
            new GrantRequest(
                payload.CharacterId,
                payload.ItemId,
                payload.Quantity <= 0 ? 1 : payload.Quantity,
                payload.DryRun,
                payload.Note),
            token);
        return Results.Ok(outcome);
    }
    catch (GmToolException error)
    {
        return Results.BadRequest(new { error = error.Message });
    }
});

app.MapFallbackToFile("index.html");

app.Run();

internal sealed record GrantRequestPayload(
    int CharacterId,
    int ItemId,
    int Quantity,
    bool ConfirmOffline,
    bool DryRun,
    string? Note);

internal static class GmConnection
{
    private const string ToolVariable = "GODSWAR_GM_POSTGRES_CONNECTION_STRING";

    public static string Resolve(IConfiguration configuration, string[] args)
    {
        var fromArgument = ReadArgument(args, "--connection-string");
        if (!string.IsNullOrWhiteSpace(fromArgument))
        {
            return fromArgument;
        }

        foreach (var variable in new[]
                 {
                     ToolVariable,
                     "GODSWAR_POSTGRES_CONNECTION_STRING"
                 })
        {
            var value = Environment.GetEnvironmentVariable(variable);
            if (!string.IsNullOrWhiteSpace(value))
            {
                return value;
            }
        }

        var fromConfiguration = configuration["postgresConnectionString"];
        if (!string.IsNullOrWhiteSpace(fromConfiguration))
        {
            return fromConfiguration;
        }

        // Fall back to the server's own settings so the tool works out of the box.
        var serverSettings = Path.Combine(
            AppContext.BaseDirectory,
            "..", "..", "..", "..", "..",
            "appsettings.json");
        if (File.Exists(serverSettings))
        {
            using var document = JsonDocument.Parse(File.ReadAllText(serverSettings));
            if (TryFindConnectionString(document.RootElement, out var discovered))
            {
                return discovered;
            }
        }

        throw new InvalidOperationException(
            "未找到 PostgreSQL 连接串。请设置环境变量 " + ToolVariable +
            "，或传入 --connection-string。");
    }

    private static bool TryFindConnectionString(JsonElement element, out string value)
    {
        switch (element.ValueKind)
        {
            case JsonValueKind.Object:
                foreach (var property in element.EnumerateObject())
                {
                    if (property.NameEquals("postgresConnectionString") &&
                        property.Value.ValueKind == JsonValueKind.String)
                    {
                        value = property.Value.GetString()!;
                        return true;
                    }

                    if (TryFindConnectionString(property.Value, out value))
                    {
                        return true;
                    }
                }

                break;
            case JsonValueKind.Array:
                foreach (var item in element.EnumerateArray())
                {
                    if (TryFindConnectionString(item, out value))
                    {
                        return true;
                    }
                }

                break;
        }

        value = string.Empty;
        return false;
    }

    private static string? ReadArgument(string[] args, string name)
    {
        for (var index = 0; index < args.Length; index++)
        {
            if (args[index].StartsWith(name + "=", StringComparison.OrdinalIgnoreCase))
            {
                return args[index][(name.Length + 1)..];
            }

            if (args[index].Equals(name, StringComparison.OrdinalIgnoreCase) &&
                index + 1 < args.Length)
            {
                return args[index + 1];
            }
        }

        return null;
    }

    /// <summary>
    /// Installed client root, used only to read localized item/equipment names.
    /// </summary>
    public static string? ResolveClientRoot(string[] args)
    {
        var fromArgument = ReadArgument(args, "--client-root");
        if (!string.IsNullOrWhiteSpace(fromArgument))
        {
            return fromArgument;
        }

        var fromEnvironment = Environment.GetEnvironmentVariable("GODSWAR_GM_CLIENT_ROOT");
        if (!string.IsNullOrWhiteSpace(fromEnvironment))
        {
            return fromEnvironment;
        }

        const string conventional = @"D:\Godswar Origin";
        return Directory.Exists(conventional) ? conventional : null;
    }

    /// <summary>Host/database only; never echo credentials.</summary>
    public static object Describe(string connectionString)
    {
        var parsed = new NpgsqlConnectionStringBuilder(connectionString);
        return new
        {
            host = parsed.Host,
            port = parsed.Port,
            database = parsed.Database,
            username = parsed.Username
        };
    }
}
