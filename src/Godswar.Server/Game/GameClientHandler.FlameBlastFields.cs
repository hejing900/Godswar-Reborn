using Godswar.Server.Application.Characters;
using Godswar.Server.State;

namespace Godswar.Server.Game;

internal sealed partial class GameClientHandler
{
    private readonly TimeProvider _flameBlastTimeProvider;
    private readonly object _flameBlastSync = new();
    private readonly CancellationTokenSource _flameBlastLifetime = new();
    private readonly Dictionary<ulong, Task> _flameBlastTasks = [];
    private static long _nextFlameBlastFieldId;
    private Task? _flameBlastStopTask;

    private FlameBlastSource? CaptureFlameBlastFieldSource(
        GameCharacter character, SkillCombatDefinition combat) =>
        FlameBlastPulsePolicy.AppliesTo(combat) &&
        _registry.TryCaptureFlameBlastSource(_session, character, out var source)
            ? source : null;

    private void StartFlameBlastField(FlameBlastSource? source,
        SkillCombatDefinition combat, float centerX, float centerZ)
    {
        if (source is not { } captured || !_registry.IsCurrentFlameBlastSource(captured)) return;
        lock (_flameBlastSync)
        {
            if (_flameBlastStopTask is not null) return;
            var fieldId = checked((ulong)Interlocked.Increment(ref _nextFlameBlastFieldId));
            var startedAt = _flameBlastTimeProvider.GetTimestamp();
            // Each accepted cast owns its field. Recasts, movement and later
            // intonation interruption must not replace an already placed field.
            var task = RunFlameBlastFieldAsync(captured, combat, centerX, centerZ,
                fieldId, startedAt, _flameBlastLifetime.Token);
            if (!task.IsCompleted) _flameBlastTasks.Add(fieldId, task);
        }
    }

    private async Task RunFlameBlastFieldAsync(FlameBlastSource source,
        SkillCombatDefinition combat, float centerX, float centerZ,
        ulong fieldId, long startedAt, CancellationToken cancellationToken)
    {
        try
        {
            // The normal accepted cast has already committed ordinal zero.
            for (var ordinal = 1; ordinal < FlameBlastPulsePolicy.TotalPulses; ordinal++)
            {
                var due = FlameBlastPulsePolicy.Interval * ordinal;
                var delay = due - _flameBlastTimeProvider.GetElapsedTime(startedAt);
                if (delay > TimeSpan.Zero)
                    await Task.Delay(delay, _flameBlastTimeProvider, cancellationToken);

                await _characterStateGate.WaitAsync(cancellationToken);
                try
                {
                    cancellationToken.ThrowIfCancellationRequested();
                    if (!_registry.IsCurrentFlameBlastSource(source)) return;
                    // A stalled handler must not burst old damage after the
                    // field's scheduled window. Each ordinal is visited once.
                    if (_flameBlastTimeProvider.GetElapsedTime(startedAt) >=
                        due + FlameBlastPulsePolicy.Interval) continue;
                    if (!await ApplyFlameBlastPulseAsync(source, combat, centerX, centerZ,
                            fieldId, ordinal, _flameBlastTimeProvider.GetUtcNow(),
                            cancellationToken)) return;
                }
                finally
                {
                    _characterStateGate.Release();
                }
            }
        }
        catch (OperationCanceledException) when (cancellationToken.IsCancellationRequested) { }
        catch (PlayerOwnershipValidationException)
        {
            RejectLostPlayerOwnership();
        }
        catch (Exception ex)
        {
            Console.WriteLine($"[skill] Flame Blast field failed field={fieldId}: {ex.Message}");
            _session.Disconnect();
        }
        finally
        {
            lock (_flameBlastSync) _flameBlastTasks.Remove(fieldId);
        }
    }

    private Task StopFlameBlastFieldsAsync()
    {
        TaskCompletionSource stopped;
        Task[] tasks;
        lock (_flameBlastSync)
        {
            // Join every field before session teardown can dispose its gate.
            if (_flameBlastStopTask is not null) return _flameBlastStopTask;
            stopped = new(TaskCreationOptions.RunContinuationsAsynchronously);
            _flameBlastStopTask = stopped.Task;
            tasks = _flameBlastTasks.Values.ToArray();
        }
        // Cancellation callbacks and task completion run outside the task lock.
        _ = StopFlameBlastFieldsCoreAsync(tasks, stopped);
        return stopped.Task;
    }

    private async Task StopFlameBlastFieldsCoreAsync(Task[] tasks, TaskCompletionSource stopped)
    {
        try
        {
            _flameBlastLifetime.Cancel();
            await Task.WhenAll(tasks);
            _flameBlastLifetime.Dispose();
            stopped.SetResult();
        }
        catch (Exception ex)
        {
            _flameBlastLifetime.Dispose();
            stopped.SetException(ex);
        }
    }
}
