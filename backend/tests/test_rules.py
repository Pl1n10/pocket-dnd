"""Test dei calcoli di regole 5e — puri, nessun DB.

Copre i pochi calcoli che l'app GARANTISCE (nucleo vivo, vedi DECISIONS.md D2/D8):
  - modificatore da ability score
  - proficiency bonus dal livello
  - bonus di un tiro di skill (con/senza competenza)
  - HP guadagnati al level-up
"""
import pytest

from app.rules import (
    ability_modifier,
    proficiency_bonus,
    skill_bonus,
    level_up_hp_gain,
)


class TestAbilityModifier:
    @pytest.mark.parametrize("score,expected", [
        (10, 0), (11, 0),      # 10-11 -> +0
        (12, 1), (13, 1),      # arrotonda verso il basso
        (8, -1), (9, -1),      # punteggi bassi -> modificatore negativo
        (1, -5), (20, 5),      # estremi tipici
        (3, -4), (16, 3),
    ])
    def test_modifier(self, score, expected):
        assert ability_modifier(score) == expected

    def test_rejects_non_positive_score(self):
        with pytest.raises(ValueError):
            ability_modifier(0)


class TestProficiencyBonus:
    @pytest.mark.parametrize("level,expected", [
        (1, 2), (4, 2),        # 1-4   -> +2
        (5, 3), (8, 3),        # 5-8   -> +3
        (9, 4), (12, 4),       # 9-12  -> +4
        (13, 5), (16, 5),      # 13-16 -> +5
        (17, 6), (20, 6),      # 17-20 -> +6
    ])
    def test_bonus(self, level, expected):
        assert proficiency_bonus(level) == expected

    @pytest.mark.parametrize("bad", [0, -1, 21, 100])
    def test_rejects_out_of_range_level(self, bad):
        with pytest.raises(ValueError):
            proficiency_bonus(bad)


class TestSkillBonus:
    def test_proficient_skill_adds_proficiency(self):
        # DEX 16 (+3), livello 1 (prof +2), competente -> +5
        assert skill_bonus(ability_score=16, level=1, proficient=True) == 5

    def test_non_proficient_skill_is_just_the_modifier(self):
        # DEX 16 (+3), non competente -> +3
        assert skill_bonus(ability_score=16, level=1, proficient=False) == 3

    def test_proficiency_scales_with_level(self):
        # STR 14 (+2), livello 9 (prof +4), competente -> +6
        assert skill_bonus(ability_score=14, level=9, proficient=True) == 6

    def test_negative_modifier_skill(self):
        # CHA 8 (-1), non competente -> -1
        assert skill_bonus(ability_score=8, level=1, proficient=False) == -1


class TestLevelUpHpGain:
    """Al level-up gli HP crescono di: tiro del dado vita + mod CON.

    Politica pocket-dnd: usiamo il VALORE FISSO del dado vita (regola "media"
    di 5e: d6->4, d8->5, d10->6, d12->7), non un tiro casuale. Il level-up e'
    assistito e deterministico; chi vuole tirare lo fa a mano e corregge.
    """
    @pytest.mark.parametrize("hit_die,con_mod,expected", [
        (10, 2, 8),    # fighter d10 -> media 6, +2 CON
        (6, 0, 4),     # wizard d6 -> media 4, +0 CON
        (12, 3, 10),   # barbarian d12 -> media 7, +3 CON
        (8, -1, 4),    # d8 -> media 5, -1 CON
    ])
    def test_hp_gain(self, hit_die, con_mod, expected):
        assert level_up_hp_gain(hit_die=hit_die, con_modifier=con_mod) == expected

    def test_minimum_one_hp_per_level(self):
        # anche con CON molto negativa, si guadagna almeno 1 HP
        assert level_up_hp_gain(hit_die=6, con_modifier=-5) >= 1

    def test_rejects_unknown_hit_die(self):
        with pytest.raises(ValueError):
            level_up_hp_gain(hit_die=7, con_modifier=0)
