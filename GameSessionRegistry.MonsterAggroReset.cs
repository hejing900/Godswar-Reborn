using Godswar.Server.Game.WorldInstances;
using Godswar.Server.Networking;

namespace Godswar.Server.Game;

internal sealed partial class GameSessionRegistry
{
    // 角色复活/回城后清空怪物对该角色的仇恨,使其回到原始刷新点巡逻。
    // Clears monster aggro toward a character after revival or map recall, so
    // the monsters return to their original spawn points.
    internal void ClearMonsterAggroForCharacter(
        byte legacyMapId,
        ClientSession routingSession,
        int characterId,
        DateTimeOffset now)
    {
        if (!TryResolveWorldInstance(
                legacyMapId,
                routingSession,
                out var runtime))
        {
            return;
        }

        InvokeWorldOwner(
            runtime,
            map => map.ClearMonsterAggroForCharacter(characterId, now));
    }
}
