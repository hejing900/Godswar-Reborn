using Godswar.Server.Application.Realms;
using Godswar.Server.Domain.World.Content;

namespace Godswar.Server.Application.WorldInstances;

internal enum LegacyInstanceScheduleStatus : byte
{
    Open = 1,
    WrongDay = 2,
    DailyCutoffPassed = 3
}

internal static class LegacyInstanceAdmissionPolicy
{
    private static readonly TimeOnly WonderlandCutoff =
        new(23, 0);

    public static LegacyInstanceScheduleStatus CheckSchedule(
        InstanceCallerEntryKind kind,
        RealmCalendar calendar,
        DateTimeOffset instant)
    {
        ArgumentNullException.ThrowIfNull(calendar);
        if (kind != InstanceCallerEntryKind.Wonderland)
        {
            return LegacyInstanceScheduleStatus.Open;
        }

        var local = calendar.ToRealmTime(instant);
        if (local.DayOfWeek is not
            (DayOfWeek.Saturday or DayOfWeek.Sunday))
        {
            return LegacyInstanceScheduleStatus.WrongDay;
        }

        return TimeOnly.FromDateTime(local.DateTime) < WonderlandCutoff
            ? LegacyInstanceScheduleStatus.Open
            : LegacyInstanceScheduleStatus.DailyCutoffPassed;
    }
}
