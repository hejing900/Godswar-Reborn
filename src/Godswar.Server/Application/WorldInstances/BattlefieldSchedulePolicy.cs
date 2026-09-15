using Godswar.Server.Application.Realms;
using Godswar.Server.Domain.World.Content;

namespace Godswar.Server.Application.WorldInstances;

/// <summary>
/// Realm-calendar admission windows advertised by the current event panel.
/// A window is start-inclusive and end-exclusive.
/// </summary>
internal static class BattlefieldSchedulePolicy
{
    private static readonly TimeSpan EventDuration =
        TimeSpan.FromMinutes(45);

    public static bool IsOpen(
        BattlefieldDestinationKind destination,
        RealmCalendar calendar,
        DateTimeOffset instant)
    {
        ArgumentNullException.ThrowIfNull(calendar);
        if (destination == BattlefieldDestinationKind.DuelArena)
        {
            return true;
        }

        var local = calendar.ToRealmTime(instant);
        var time = TimeOnly.FromDateTime(local.DateTime);
        return Starts(destination, local.DayOfWeek)
            .Any(start => IsWithin(time, start, EventDuration));
    }

    private static IEnumerable<TimeOnly> Starts(
        BattlefieldDestinationKind destination,
        DayOfWeek day) =>
        destination switch
        {
            BattlefieldDestinationKind.Pindus => day switch
            {
                DayOfWeek.Wednesday => [new TimeOnly(21, 0)],
                DayOfWeek.Friday => [new TimeOnly(21, 0)],
                DayOfWeek.Saturday =>
                    [new TimeOnly(8, 0), new TimeOnly(15, 0)],
                DayOfWeek.Sunday =>
                    [new TimeOnly(8, 0), new TimeOnly(21, 0)],
                _ => []
            },
            BattlefieldDestinationKind.NiMiniLower or
            BattlefieldDestinationKind.NiMiniUpper => day switch
            {
                DayOfWeek.Friday => [new TimeOnly(19, 0)],
                DayOfWeek.Saturday => [new TimeOnly(7, 0)],
                DayOfWeek.Sunday => [new TimeOnly(19, 0)],
                _ => []
            },
            _ => []
        };

    private static bool IsWithin(
        TimeOnly current,
        TimeOnly start,
        TimeSpan duration)
    {
        var elapsed = current.ToTimeSpan() - start.ToTimeSpan();
        return elapsed >= TimeSpan.Zero && elapsed < duration;
    }
}
