using System.Text;

namespace Godswar.GmTool;

/// <summary>
/// Optional side-car over the installed client's EquipName.dat so the GM can
/// search by localized name. The server's own display_name column is English;
/// the client ships the localized text. Absent client resources simply disable
/// localized search.
/// </summary>
internal sealed class ClientLocalization
{
    private readonly Dictionary<string, string> _localized = new(StringComparer.Ordinal);
    private readonly Dictionary<string, string> _english = new(StringComparer.Ordinal);

    private ClientLocalization()
    {
    }

    public bool HasLocalizedNames => _localized.Count > 0;

    public static ClientLocalization Load(string? clientRoot)
    {
        var localization = new ClientLocalization();
        if (string.IsNullOrWhiteSpace(clientRoot) ||
            !Directory.Exists(clientRoot))
        {
            return localization;
        }

        localization.ReadLocale(Path.Combine(clientRoot, "Localization", "zh_cn"), localization._localized);
        localization.ReadLocale(Path.Combine(clientRoot, "Localization", "en_us"), localization._english);
        return localization;
    }

    public string? LocalizedName(string nameKey) =>
        _localized.TryGetValue(nameKey, out var value)
            ? value
            : _english.TryGetValue(nameKey, out var english) ? english : null;

    /// <summary>Name keys whose localized or English text contains the query.</summary>
    public IReadOnlyList<string> ResolveKeys(string query)
    {
        if (string.IsNullOrWhiteSpace(query))
        {
            return [];
        }

        var trimmed = query.Trim();
        var keys = new HashSet<string>(StringComparer.Ordinal);
        foreach (var source in new[] { _localized, _english })
        {
            foreach (var pair in source)
            {
                if (pair.Value.Contains(trimmed, StringComparison.OrdinalIgnoreCase))
                {
                    keys.Add(pair.Key);
                }
            }
        }

        return keys.ToArray();
    }

    private void ReadLocale(string localeRoot, Dictionary<string, string> target)
    {
        var path = Path.Combine(localeRoot, "Text", "EquipName.dat");
        if (!File.Exists(path))
        {
            return;
        }

        foreach (var line in File.ReadLines(path, Encoding.UTF8))
        {
            if (string.IsNullOrWhiteSpace(line) || line.StartsWith("//", StringComparison.Ordinal))
            {
                continue;
            }

            var parts = line.Split('\t', 2);
            if (parts.Length != 2)
            {
                continue;
            }

            var key = parts[0].Trim();
            var value = parts[1].Trim();
            if (key.Length > 0 && value.Length > 0)
            {
                target[key] = value;
            }
        }
    }
}
