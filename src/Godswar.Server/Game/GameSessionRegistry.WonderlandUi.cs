using System.Collections.Concurrent;
using Godswar.Server.Application.WorldInstances;
using Godswar.Server.Domain.World.Instances;
using Godswar.Server.Game.WorldInstances;
using Godswar.Server.Networking;
using Godswar.Server.Packets;

namespace Godswar.Server.Game;

internal sealed partial class GameSessionRegistry
{
    private readonly ConcurrentDictionary<ClientSession, WonderlandUiStamp> _wonderlandUi = [];

    private async Task PublishWonderlandRunUiAsync(WorldInstanceRuntime runtime, WonderlandSnapshot run,
        WonderlandAdmission admission, IReadOnlyList<GameSessionContext> members,
        DateTimeOffset now, CancellationToken cancellationToken)
    {
        var completed = run.State == WonderlandRunState.Completed;
        var remaining = checked((int)Math.Clamp(Math.Ceiling(completed
            ? (run.TerminalAt!.Value + WonderlandCompletionPolicy.TreasureWindow - now).TotalSeconds
            : (run.Deadline - run.LastObservedAt).TotalSeconds), 0,
            completed ? WonderlandCompletionPolicy.TreasureWindow.TotalSeconds : 2400));
        var roster = members.Select(member => new RepetitionInstanceMember(member.CharacterId,
            member.Character.Name, member.Character.Level, true, member.Character.Profession)).ToArray();
        var signature = string.Join('|', roster.Select(member =>
            $"{member.CharacterId}:{member.Name}:{member.Level}:{member.Profession}"));
        var stamp = new WonderlandUiStamp(runtime.InstanceId, run.State, run.CurrentIsland,
            run.CompletedIslands, remaining, signature);
        foreach (var member in members)
        {
            Task? write = null;
            lock (_gate)
            {
                if (!IsCurrentWonderlandMember(member, runtime.InstanceId)) continue;
                // A prior member's transport write may have yielded while the
                // leader cancelled or combat advanced the authoritative run.
                if (!TryGetWonderlandEncounterSnapshot(runtime.InstanceId, out var currentRun) ||
                    currentRun.State != run.State || currentRun.CurrentIsland != run.CurrentIsland ||
                    currentRun.CompletedIslands != run.CompletedIslands) continue;
                _wonderlandUi.TryGetValue(member.Session, out var previous);
                if (previous == stamp || previous?.InstanceId == stamp.InstanceId &&
                    (previous.CompletedIslands > stamp.CompletedIslands ||
                     previous.State == WonderlandRunState.Completed && completed)) continue;
                var packets = new List<ReadOnlyMemory<byte>>();
                // Nonzero10231 only opens its native countdown while the
                // client's repetition state is5/6. Reassert state5 in the
                // completion batch instead of relying on its entry-time sync.
                if (completed || previous?.InstanceId != stamp.InstanceId)
                    packets.Add(PacketBuilder.RepetitionSync(WonderlandClientSceneId, 0, 0, 5, admission.DailyLimit));
                if (previous?.InstanceId != stamp.InstanceId || previous.Roster != signature)
                    packets.Add(PacketBuilder.RepetitionInstanceMembers(roster));
                packets.Add(PacketBuilder.RepetitionFightInfo(remaining, run.CompletedIslands));
                if (completed)
                {
                    packets.Add(PacketBuilder.RepetitionPanelCompletion());
                    packets.Add(PacketBuilder.RepetitionCompletionState(WonderlandClientSceneId, true));
                    packets.Add(PacketBuilder.RepetitionCountdown(remaining));
                }
                else if (run.State != WonderlandRunState.Active)
                    packets.Add(PacketBuilder.RepetitionCompletionState(WonderlandClientSceneId, false));
                if (member.Session.TryAdmitExactBatch(packets, out var admitted)) _wonderlandUi[member.Session] = stamp;
                write = admitted;
            }
            if (write is not null)
            {
                try
                {
                    await write;
                    if (completed)
                        Console.WriteLine($"[wonderland] completion countdown published instance={runtime.InstanceId} " +
                            $"character={member.CharacterId} seconds={remaining}");
                }
                catch (Exception error) when (error is not OperationCanceledException || !cancellationToken.IsCancellationRequested)
                { member.Session.Disconnect(); }
            }
        }
    }

    private sealed record WonderlandUiStamp(WorldInstanceId InstanceId, WonderlandRunState State,
        int Island, int CompletedIslands, int RemainingSeconds, string Roster);
}
