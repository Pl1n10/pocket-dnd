"""Test del motore dadi — scritti PRIMA dell'implementazione (TDD).

Il motore e' puro: nessun DB, nessuna rete. L'unica fonte di non-determinismo
e' l'RNG, che e' iniettabile per rendere i test deterministici.

Copertura:
  - parsing di NdS+M e forme sporche dei JSON SRD
  - rifiuto esplicito di input invalidi
  - rolling deterministico (RNG fittizio)
  - vantaggio / svantaggio (solo come parametro, mai nella formula)
  - breakdown leggibile per il feed del master
"""
import random

import pytest

from app.dice import (
    DiceFormula,
    DiceError,
    parse_formula,
    normalize_srd_dice,
    roll,
    Advantage,
)


# ───────────────────────────── parsing ─────────────────────────────

class TestParseFormula:
    def test_simple_single_die(self):
        f = parse_formula("1d20")
        assert f.rolls == [(1, 20)]
        assert f.modifier == 0

    def test_multiple_dice_with_positive_modifier(self):
        f = parse_formula("2d6+3")
        assert f.rolls == [(2, 6)]
        assert f.modifier == 3

    def test_negative_modifier(self):
        f = parse_formula("1d8-1")
        assert f.rolls == [(1, 8)]
        assert f.modifier == -1

    def test_bare_modifier_only(self):
        # un tiro che e' solo un numero fisso, senza dadi
        f = parse_formula("5")
        assert f.rolls == []
        assert f.modifier == 5

    def test_multiple_dice_groups(self):
        # es. un'arma magica: 1d8 tagliente + 1d6 da fuoco
        f = parse_formula("1d8+1d6+2")
        assert f.rolls == [(1, 8), (1, 6)]
        assert f.modifier == 2

    def test_whitespace_is_tolerated(self):
        f = parse_formula(" 2d6 + 3 ")
        assert f.rolls == [(2, 6)]
        assert f.modifier == 3

    def test_case_insensitive_d(self):
        assert parse_formula("1D20").rolls == [(1, 20)]

    def test_implicit_single_die_count(self):
        # "d20" senza il numero davanti == "1d20"
        assert parse_formula("d20").rolls == [(1, 20)]

    @pytest.mark.parametrize("bad", ["", "   ", "abc", "2d", "d", "2x6", "1d0", "0d6", "1d-4"])
    def test_invalid_input_raises(self, bad):
        with pytest.raises(DiceError):
            parse_formula(bad)

    def test_error_message_mentions_the_input(self):
        # il messaggio deve essere diagnostico, non generico
        with pytest.raises(DiceError) as exc:
            parse_formula("banana")
        assert "banana" in str(exc.value)


# ───────────────────── normalizzazione dato SRD ─────────────────────

class TestNormalizeSrdDice:
    """I JSON SRD danno i dadi in forme diverse; vanno ricondotti a NdS+M."""

    def test_already_canonical_string(self):
        assert normalize_srd_dice("1d8") == "1d8"

    def test_structured_count_value(self):
        assert normalize_srd_dice({"dice_count": 2, "dice_value": 6}) == "2d6"

    def test_structured_with_alt_keys(self):
        # alcune varianti SRD usano 'number'/'faces'
        assert normalize_srd_dice({"number": 3, "faces": 4}) == "3d4"

    def test_empty_or_none_yields_empty_string(self):
        assert normalize_srd_dice(None) == ""
        assert normalize_srd_dice("") == ""
        assert normalize_srd_dice({}) == ""

    def test_normalized_output_is_parseable(self):
        # contratto: cio' che normalize produce, parse_formula lo accetta
        out = normalize_srd_dice({"dice_count": 2, "dice_value": 8})
        assert parse_formula(out).rolls == [(2, 8)]


# ───────────────────────────── rolling ─────────────────────────────

class FakeRandom:
    """RNG deterministico: restituisce in sequenza i valori dati."""
    def __init__(self, values):
        self._values = list(values)
        self._i = 0

    def randint(self, a, b):
        v = self._values[self._i]
        self._i += 1
        assert a <= v <= b, f"valore fittizio {v} fuori range [{a},{b}]"
        return v


class TestRoll:
    def test_deterministic_single_die(self):
        result = roll("1d20", rng=FakeRandom([14]))
        assert result.total == 14
        assert result.formula == "1d20"

    def test_applies_modifier(self):
        result = roll("1d20+5", rng=FakeRandom([14]))
        assert result.total == 19

    def test_sums_multiple_dice(self):
        result = roll("3d6", rng=FakeRandom([2, 5, 6]))
        assert result.total == 13

    def test_negative_modifier_can_be_applied(self):
        result = roll("1d4-1", rng=FakeRandom([1]))
        assert result.total == 0

    def test_bare_modifier_does_not_touch_rng(self):
        # "5" non ha dadi: non deve chiamare l'RNG
        result = roll("5", rng=FakeRandom([]))
        assert result.total == 5

    def test_real_rng_stays_in_bounds(self):
        # smoke test con RNG vero: 1d6 sta sempre in [1,6]
        for _ in range(200):
            assert 1 <= roll("1d6", rng=random.Random()).total <= 6


class TestAdvantage:
    def test_advantage_keeps_higher_d20(self):
        result = roll("1d20+3", rng=FakeRandom([8, 17]), advantage=Advantage.ADVANTAGE)
        assert result.total == 20  # 17 + 3

    def test_disadvantage_keeps_lower_d20(self):
        result = roll("1d20+3", rng=FakeRandom([8, 17]), advantage=Advantage.DISADVANTAGE)
        assert result.total == 11  # 8 + 3

    def test_normal_rolls_d20_once(self):
        result = roll("1d20", rng=FakeRandom([12]), advantage=Advantage.NORMAL)
        assert result.total == 12

    def test_advantage_only_valid_on_single_d20(self):
        # adv/dis ha senso solo su 1d20; su altro deve essere rifiutato
        with pytest.raises(DiceError):
            roll("2d6", rng=FakeRandom([1, 1]), advantage=Advantage.ADVANTAGE)

    def test_advantage_default_is_normal(self):
        result = roll("1d20", rng=FakeRandom([9]))
        assert result.total == 9


# ───────────────────────────── breakdown ─────────────────────────────

class TestBreakdown:
    """Il breakdown alimenta il feed live del master: dev'essere leggibile."""

    def test_breakdown_shows_individual_dice(self):
        result = roll("3d6", rng=FakeRandom([2, 5, 6]))
        assert "2" in result.breakdown and "5" in result.breakdown and "6" in result.breakdown

    def test_breakdown_shows_modifier(self):
        result = roll("1d20+5", rng=FakeRandom([10]))
        assert "+5" in result.breakdown

    def test_breakdown_shows_both_d20_under_advantage(self):
        result = roll("1d20", rng=FakeRandom([8, 17]), advantage=Advantage.ADVANTAGE)
        # entrambi i tiri visibili, piu' indicazione di quale e' stato tenuto
        assert "8" in result.breakdown and "17" in result.breakdown

    def test_breakdown_of_bare_modifier(self):
        result = roll("7", rng=FakeRandom([]))
        assert "7" in result.breakdown
