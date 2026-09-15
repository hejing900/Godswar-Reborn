using Godswar.Server.State;
using Godswar.Server.World.Systems.Combat;

namespace Godswar.Server.Game;

internal enum CharacterHealthProjectionMode
{
    PreserveAbsolute,
    PreservePercentage
}

internal static class CharacterCalculatedStatsProjectionApplier
{
    public static void Apply(
        GameCharacter liveCharacter,
        CharacterStats persistedStats,
        CharacterHealthProjectionMode healthMode)
    {
        ArgumentNullException.ThrowIfNull(liveCharacter);
        ArgumentNullException.ThrowIfNull(persistedStats);

        lock (liveCharacter.VitalsSync)
        {
            var previousMaximumHealth = Math.Max(1, liveCharacter.MaxHp);
            var previousHealth = Math.Clamp(
                liveCharacter.CurrentHp,
                0,
                previousMaximumHealth);
            var baseMaximumHealth = Math.Max(1, persistedStats.MaxHp);
            var effectiveMaximumHealth = ResolveEffectiveMaximumHealth(
                liveCharacter,
                persistedStats);
            var maximumMana = Math.Max(0, persistedStats.MaxMp);
            var currentHealth = healthMode switch
            {
                CharacterHealthProjectionMode.PreservePercentage =>
                    ScaleHealth(
                        previousHealth,
                        previousMaximumHealth,
                        effectiveMaximumHealth),
                _ => Math.Clamp(
                    previousHealth,
                    0,
                    effectiveMaximumHealth)
            };
            var currentMana = Math.Clamp(
                liveCharacter.CurrentMp,
                0,
                maximumMana);
            var projectedStats = new CharacterStats
            {
                CharacterId = persistedStats.CharacterId,
                AccountId = persistedStats.AccountId,
                Name = persistedStats.Name,
                Profession = persistedStats.Profession,
                Level = persistedStats.Level,
                // Keep the reusable calculated projection passive-free so a
                // later refresh cannot compound its effective maximum.
                MaxHp = baseMaximumHealth,
                MaxMp = maximumMana,
                CurrentHp = currentHealth,
                CurrentMp = currentMana,
                PhysicalAttack = persistedStats.PhysicalAttack,
                PhysicalDefense = persistedStats.PhysicalDefense,
                MagicAttack = persistedStats.MagicAttack,
                MagicDefense = persistedStats.MagicDefense,
                Hit = persistedStats.Hit,
                Dodge = persistedStats.Dodge,
                StatusHit = persistedStats.StatusHit,
                StatusResistance = persistedStats.StatusResistance,
                Critical = persistedStats.Critical,
                CriticalResistance = persistedStats.CriticalResistance,
                DamageAbsorb = persistedStats.DamageAbsorb,
                PhysicalDamageBonus = persistedStats.PhysicalDamageBonus,
                MagicDamageBonus = persistedStats.MagicDamageBonus,
                CureBonus = persistedStats.CureBonus,
                BeCureBonus = persistedStats.BeCureBonus,
                HpRecovery = persistedStats.HpRecovery,
                MpRecovery = persistedStats.MpRecovery,
                IgnorePhysicalDefense =
                    persistedStats.IgnorePhysicalDefense,
                IgnoreMagicDefense = persistedStats.IgnoreMagicDefense,
                PhysicalAppendDamage =
                    persistedStats.PhysicalAppendDamage,
                MagicAppendDamage = persistedStats.MagicAppendDamage,
                CriticalDamagePercent =
                    persistedStats.CriticalDamagePercent,
                CriticalDamageFlat = persistedStats.CriticalDamageFlat,
                PhysicalDamageReduction =
                    persistedStats.PhysicalDamageReduction,
                MagicDamageReduction =
                    persistedStats.MagicDamageReduction,
                CriticalDamageReduction =
                    persistedStats.CriticalDamageReduction,
                LifeAbsorption = persistedStats.LifeAbsorption,
                DamageRebound = persistedStats.DamageRebound,
                PhysicalFlatAbsorption =
                    persistedStats.PhysicalFlatAbsorption,
                MagicFlatAbsorption = persistedStats.MagicFlatAbsorption,
                CriticalDamageFlatReduction =
                    persistedStats.CriticalDamageFlatReduction,
                DamageReboundFlat = persistedStats.DamageReboundFlat,
                LifeAbsorptionFlat = persistedStats.LifeAbsorptionFlat,
                BasicAttackIntervalMilliseconds =
                    persistedStats.BasicAttackIntervalMilliseconds,
                BasicAttackRange = persistedStats.BasicAttackRange,
                WeaponScore = persistedStats.WeaponScore,
                WeaponRank = persistedStats.WeaponRank,
                WeaponAuraEffect = persistedStats.WeaponAuraEffect,
                ArmorScore = persistedStats.ArmorScore,
                ArmorRank = persistedStats.ArmorRank,
                ArmorAuraEffect = persistedStats.ArmorAuraEffect,
                LearnedSkillCount = persistedStats.LearnedSkillCount
            };

            liveCharacter.MaxHp = effectiveMaximumHealth;
            liveCharacter.MaxMp = maximumMana;
            liveCharacter.CurrentHp = currentHealth;
            liveCharacter.CurrentMp = currentMana;
            liveCharacter.WeaponRank = projectedStats.WeaponRank;
            liveCharacter.WeaponAuraEffect =
                projectedStats.WeaponAuraEffect;
            liveCharacter.ArmorRank = projectedStats.ArmorRank;
            liveCharacter.ArmorAuraEffect = projectedStats.ArmorAuraEffect;
            liveCharacter.CalculatedStats = projectedStats;
            liveCharacter.MarkVitalsChanged();
        }
    }

    public static int ResolveEffectiveMaximumHealth(
        GameCharacter character,
        CharacterStats baseStats)
    {
        var passive = ElementalResonanceExecutionPolicy.ApplyPassiveBonuses(
            character.ElementalEquipment,
            Math.Max(1, baseStats.MaxHp),
            movementSpeed: 0);
        return Math.Max(
            1,
            checked((int)Math.Min(
                passive.MaximumHealth,
                int.MaxValue)));
    }

    private static int ScaleHealth(
        int previousHealth,
        int previousMaximumHealth,
        int newMaximumHealth)
    {
        if (previousHealth <= 0)
        {
            return 0;
        }

        var scaled =
            ((long)previousHealth * newMaximumHealth +
             (previousMaximumHealth / 2L)) /
            previousMaximumHealth;
        return (int)Math.Clamp(scaled, 0L, newMaximumHealth);
    }
}
