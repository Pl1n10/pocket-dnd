"""Calcoli di regole 5e — puri, nessun DB, nessuno stato.

Questi sono i pochi calcoli che pocket-dnd GARANTISCE (il "nucleo vivo",
vedi DECISIONS.md D2 e D8). Tutto il resto delle regole 5e NON e' qui:
lo arbitra il DM.
"""
from __future__ import annotations

# Valore "medio" del dado vita usato al level-up assistito.
# E' la regola opzionale di 5e per HP fissi: (faces / 2) + 1.
_HIT_DIE_AVERAGE = {6: 4, 8: 5, 10: 6, 12: 7}


def ability_modifier(score: int) -> int:
    """Modificatore di un ability score: floor((score - 10) / 2)."""
    if score < 1:
        raise ValueError(f"ability score non valido: {score}")
    # // in Python e' floor division, corretto anche per i negativi
    return (score - 10) // 2


def proficiency_bonus(level: int) -> int:
    """Proficiency bonus dal livello del personaggio (1-20)."""
    if not 1 <= level <= 20:
        raise ValueError(f"livello fuori range 1-20: {level}")
    # +2 a liv 1, poi +1 ogni 4 livelli
    return 2 + (level - 1) // 4


def skill_bonus(ability_score: int, level: int, proficient: bool) -> int:
    """Bonus totale di un tiro di skill.

    = modificatore dell'attributo (+ proficiency bonus se competente).
    """
    bonus = ability_modifier(ability_score)
    if proficient:
        bonus += proficiency_bonus(level)
    return bonus


def level_up_hp_gain(hit_die: int, con_modifier: int) -> int:
    """HP guadagnati salendo di un livello.

    = valore medio del dado vita + modificatore di Costituzione,
    con un minimo garantito di 1 (regola 5e).
    """
    if hit_die not in _HIT_DIE_AVERAGE:
        raise ValueError(f"dado vita non valido: d{hit_die}")
    return max(1, _HIT_DIE_AVERAGE[hit_die] + con_modifier)
