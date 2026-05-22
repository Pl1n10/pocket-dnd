"""Motore dadi di pocket-dnd.

Puro: nessun DB, nessuna rete. L'unica sorgente di non-determinismo e' l'RNG,
che e' iniettabile (qualsiasi oggetto con .randint(a, b)) per i test.

Separazione netta (vedi DECISIONS.md):
  - parsing  -> fragile, gestisce input sporco; produce un DiceFormula.
  - rolling  -> puro, lavora solo su DiceFormula, mai su stringhe.

Vantaggio/svantaggio NON e' parte della formula: e' un parametro del tiro,
applicabile solo a un singolo d20 (in 5e adv/dis tocca solo quel tiro).
"""
from __future__ import annotations

import random
import re
from dataclasses import dataclass, field
from enum import Enum


class DiceError(ValueError):
    """Input dadi malformato o operazione non valida."""


class Advantage(Enum):
    NORMAL = "normal"
    ADVANTAGE = "advantage"
    DISADVANTAGE = "disadvantage"


# ───────────────────────────── formula ─────────────────────────────

@dataclass(frozen=True)
class DiceFormula:
    """Una formula di dadi gia' parsata.

    rolls: lista di (count, sides), es. [(2, 6)] per 2d6.
    modifier: bonus/malus fisso sommato al totale.
    """
    rolls: list[tuple[int, int]] = field(default_factory=list)
    modifier: int = 0

    @property
    def is_single_d20(self) -> bool:
        """True se la formula e' esattamente 1d20 (+ eventuale modificatore)."""
        return self.rolls == [(1, 20)]


# un gruppo di dadi: "2d6", "d20", oppure un intero nudo "+3"
_DIE_RE = re.compile(r"([+-]?)(\d*)[dD](\d+)")
_MOD_RE = re.compile(r"([+-]?)(\d+)")


def parse_formula(text: str) -> DiceFormula:
    """Parsa 'NdS+M' (e varianti) in un DiceFormula. Rifiuta input invalidi."""
    if text is None:
        raise DiceError("formula dadi vuota")
    raw = text.strip()
    if not raw:
        raise DiceError("formula dadi vuota")

    compact = raw.replace(" ", "")
    rolls: list[tuple[int, int]] = []
    modifier = 0

    # consumiamo la stringa token per token; cio' che resta non consumato = errore
    pos = 0
    n = len(compact)
    while pos < n:
        m_die = _DIE_RE.match(compact, pos)
        if m_die:
            sign, count_s, sides_s = m_die.groups()
            count = int(count_s) if count_s else 1   # "d20" => 1d20
            sides = int(sides_s)
            if count <= 0:
                raise DiceError(f"numero di dadi non valido in '{text}'")
            if sides <= 0:
                raise DiceError(f"numero di facce non valido in '{text}'")
            if sign == "-":
                # un gruppo di dadi negativo non ha senso in questo dominio
                raise DiceError(f"gruppo di dadi negativo non valido in '{text}'")
            rolls.append((count, sides))
            pos = m_die.end()
            continue

        m_mod = _MOD_RE.match(compact, pos)
        if m_mod:
            sign, num_s = m_mod.groups()
            value = int(num_s)
            modifier += -value if sign == "-" else value
            pos = m_mod.end()
            continue

        # carattere non riconosciuto: input sporco
        raise DiceError(f"formula dadi non valida: '{text}'")

    if not rolls and modifier == 0 and not re.search(r"\d", compact):
        raise DiceError(f"formula dadi non valida: '{text}'")

    return DiceFormula(rolls=rolls, modifier=modifier)


def normalize_srd_dice(value) -> str:
    """Riconduce le varie forme di dado dei JSON SRD alla stringa 'NdS'.

    Accetta: stringa gia' canonica, dict {dice_count,dice_value} o
    {number,faces}, oppure None/vuoto -> ''.
    Il contratto e': cio' che produce dev'essere accettato da parse_formula.
    """
    if not value:
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, dict):
        count = value.get("dice_count", value.get("number"))
        sides = value.get("dice_value", value.get("faces"))
        try:
            c, s = int(count), int(sides)
        except (TypeError, ValueError):
            return ""
        if c <= 0 or s <= 0:
            return ""
        return f"{c}d{s}"
    return ""


# ───────────────────────────── risultato ─────────────────────────────

@dataclass(frozen=True)
class RollResult:
    """Esito di un tiro, pronto per il roll_log e il feed del master."""
    formula: str
    total: int
    breakdown: str


# ───────────────────────────── rolling ─────────────────────────────

def _roll_group(count: int, sides: int, rng) -> list[int]:
    return [rng.randint(1, sides) for _ in range(count)]


def roll(text: str, rng=None, advantage: Advantage = Advantage.NORMAL) -> RollResult:
    """Tira una formula. RNG iniettabile (default: random.Random()).

    advantage si applica solo a un singolo d20; su qualsiasi altra formula
    e' un errore (in 5e adv/dis tocca solo il tiro per colpire / salvezza).
    """
    if rng is None:
        rng = random.Random()

    formula = parse_formula(text)

    if advantage is not Advantage.NORMAL:
        if not formula.is_single_d20:
            raise DiceError(
                f"vantaggio/svantaggio applicabile solo a 1d20, non a '{text}'"
            )
        a, b = rng.randint(1, 20), rng.randint(1, 20)
        kept = max(a, b) if advantage is Advantage.ADVANTAGE else min(a, b)
        total = kept + formula.modifier
        tag = "vantaggio" if advantage is Advantage.ADVANTAGE else "svantaggio"
        mod_s = _format_modifier(formula.modifier)
        breakdown = f"{tag} [{a}, {b}] -> {kept}{mod_s}"
        return RollResult(formula=text, total=total, breakdown=breakdown)

    # tiro normale
    all_dice: list[int] = []
    parts: list[str] = []
    for count, sides in formula.rolls:
        results = _roll_group(count, sides, rng)
        all_dice.extend(results)
        parts.append("[" + ", ".join(str(d) for d in results) + "]")

    total = sum(all_dice) + formula.modifier

    if parts:
        breakdown = " + ".join(parts) + _format_modifier(formula.modifier)
    else:
        # formula senza dadi: solo un valore fisso
        breakdown = str(formula.modifier)

    return RollResult(formula=text, total=total, breakdown=breakdown)


def _format_modifier(mod: int) -> str:
    """' +5', ' -1', oppure '' se zero — per concatenare al breakdown."""
    if mod == 0:
        return ""
    return f" {'+' if mod > 0 else '-'}{abs(mod)}"
