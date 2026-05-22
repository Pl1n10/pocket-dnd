"""Test del repository personaggi: CRUD su SQLite + serializzazione.

Ogni test gira su un DB SQLite in-memory fresco (fixture `repo`).
Copre:
  - create / read / update / delete
  - calcoli derivati esposti dal modello (modificatori, proficiency)
  - export verso il JSON di docs/FORMAT.md (blocchi computed / declared)
  - import dal JSON, incluse le regole di robustezza
"""
import json
from pathlib import Path

import pytest

from app.characters import CharacterRepo, CharacterNotFound, ImportError as CharImportError


SCHEMA = Path(__file__).resolve().parent.parent / "app" / "schema.sql"


@pytest.fixture
def repo():
    r = CharacterRepo(":memory:")
    r.init_schema(SCHEMA.read_text(encoding="utf-8"))
    return r


def _sample_character():
    """Un personaggio valido di esempio (solo il nucleo + un'azione)."""
    return {
        "name": "Brannor",
        "player_name": "Marco",
        "class": "fighter",
        "race": "human",
        "level": 3,
        "str": 16, "dex": 13, "con": 14, "int": 10, "wis": 12, "cha": 8,
        "max_hp": 28, "current_hp": 28, "armor_class": 16, "speed": 30,
        "skill_proficiencies": ["athletics", "intimidation"],
        "actions": [
            {"name": "Longsword", "srd_ref": "longsword", "to_hit_mod": 5,
             "damage_dice": "1d8+3", "damage_type": "slashing",
             "description": "Versatile (1d10)."}
        ],
    }


# ───────────────────────────── create / read ─────────────────────────────

class TestCreateRead:
    def test_create_returns_id(self, repo):
        cid = repo.create(_sample_character())
        assert isinstance(cid, int) and cid > 0

    def test_read_back_preserves_fields(self, repo):
        cid = repo.create(_sample_character())
        c = repo.get(cid)
        assert c["name"] == "Brannor"
        assert c["class"] == "fighter"
        assert c["level"] == 3
        assert c["str"] == 16

    def test_actions_survive_round_trip(self, repo):
        cid = repo.create(_sample_character())
        c = repo.get(cid)
        assert len(c["actions"]) == 1
        assert c["actions"][0]["name"] == "Longsword"
        assert c["actions"][0]["damage_dice"] == "1d8+3"

    def test_skill_proficiencies_survive_round_trip(self, repo):
        cid = repo.create(_sample_character())
        c = repo.get(cid)
        assert c["skill_proficiencies"] == ["athletics", "intimidation"]

    def test_get_unknown_id_raises(self, repo):
        with pytest.raises(CharacterNotFound):
            repo.get(9999)

    def test_proficiency_bonus_computed_on_create(self, repo):
        # livello 3 -> proficiency +2, calcolato dal repo, non passato a mano
        cid = repo.create(_sample_character())
        assert repo.get(cid)["proficiency_bonus"] == 2

    def test_defaults_for_minimal_character(self, repo):
        # un personaggio creato col minimo indispensabile
        cid = repo.create({"name": "Pippo"})
        c = repo.get(cid)
        assert c["level"] == 1
        assert c["str"] == 10
        assert c["proficiency_bonus"] == 2

    def test_create_rejects_missing_name(self, repo):
        with pytest.raises(ValueError):
            repo.create({"class": "wizard"})


# ───────────────────────────── list ─────────────────────────────

class TestList:
    def test_list_empty(self, repo):
        assert repo.list_all() == []

    def test_list_returns_all(self, repo):
        repo.create(_sample_character())
        repo.create({"name": "Elwing"})
        assert len(repo.list_all()) == 2


# ───────────────────────────── update ─────────────────────────────

class TestUpdate:
    def test_update_changes_field(self, repo):
        cid = repo.create(_sample_character())
        repo.update(cid, {"current_hp": 12})
        assert repo.get(cid)["current_hp"] == 12

    def test_update_recomputes_proficiency_on_level_change(self, repo):
        cid = repo.create(_sample_character())   # liv 3 -> +2
        repo.update(cid, {"level": 5})           # liv 5 -> +3
        assert repo.get(cid)["proficiency_bonus"] == 3

    def test_update_unknown_id_raises(self, repo):
        with pytest.raises(CharacterNotFound):
            repo.update(9999, {"current_hp": 1})

    def test_update_touches_updated_at(self, repo):
        cid = repo.create(_sample_character())
        before = repo.get(cid)["updated_at"]
        repo.update(cid, {"current_hp": 1})
        assert repo.get(cid)["updated_at"] >= before


# ───────────────────────────── delete ─────────────────────────────

class TestDelete:
    def test_delete_removes_character(self, repo):
        cid = repo.create(_sample_character())
        repo.delete(cid)
        with pytest.raises(CharacterNotFound):
            repo.get(cid)

    def test_delete_unknown_id_raises(self, repo):
        with pytest.raises(CharacterNotFound):
            repo.delete(9999)


# ───────────────────────────── export ─────────────────────────────

class TestExport:
    def test_export_has_schema_version(self, repo):
        cid = repo.create(_sample_character())
        data = repo.export_character(cid)
        assert data["schema_version"] == "pocket-dnd/1"
        assert data["compat"] == "5e-srd-5.1"

    def test_export_identity_block(self, repo):
        cid = repo.create(_sample_character())
        ident = repo.export_character(cid)["identity"]
        assert ident["name"] == "Brannor"
        assert ident["class"] == "fighter"
        assert ident["level"] == 3

    def test_export_computed_block(self, repo):
        cid = repo.create(_sample_character())
        comp = repo.export_character(cid)["computed"]
        assert comp["abilities"]["str"] == 16
        assert comp["max_hp"] == 28
        assert comp["proficiency_bonus"] == 2
        assert comp["skill_proficiencies"] == ["athletics", "intimidation"]
        assert comp["actions"][0]["name"] == "Longsword"

    def test_export_declared_block_present_even_if_empty(self, repo):
        cid = repo.create(_sample_character())
        data = repo.export_character(cid)
        assert "declared" in data
        assert isinstance(data["declared"], dict)

    def test_export_preserves_declared_content(self, repo):
        char = _sample_character()
        char["extended"] = {"background": "Soldier", "notes": "Blunt."}
        cid = repo.create(char)
        declared = repo.export_character(cid)["declared"]
        assert declared["background"] == "Soldier"
        assert declared["notes"] == "Blunt."

    def test_export_is_json_serializable(self, repo):
        cid = repo.create(_sample_character())
        # non deve sollevare
        json.dumps(repo.export_character(cid))


# ───────────────────────────── import ─────────────────────────────

class TestImport:
    def test_import_round_trip(self, repo):
        cid = repo.create(_sample_character())
        exported = repo.export_character(cid)
        new_id = repo.import_character(exported)
        reimported = repo.export_character(new_id)
        # identita' e nucleo devono coincidere
        assert reimported["identity"] == exported["identity"]
        assert reimported["computed"] == exported["computed"]

    def test_import_rejects_unknown_schema_version(self, repo):
        bad = {"schema_version": "pocket-dnd/999", "identity": {"name": "X"},
               "computed": {}, "declared": {}}
        with pytest.raises(CharImportError):
            repo.import_character(bad)

    def test_import_rejects_missing_computed(self, repo):
        bad = {"schema_version": "pocket-dnd/1", "identity": {"name": "X"},
               "declared": {}}
        with pytest.raises(CharImportError):
            repo.import_character(bad)

    def test_import_tolerates_missing_declared(self, repo):
        ok = {"schema_version": "pocket-dnd/1",
              "identity": {"name": "Solo", "class": "rogue", "level": 1},
              "computed": {"abilities": {"str": 10, "dex": 14, "con": 12,
                                         "int": 10, "wis": 10, "cha": 10},
                           "max_hp": 8, "armor_class": 12}}
        cid = repo.import_character(ok)   # non deve sollevare
        assert repo.get(cid)["name"] == "Solo"

    def test_import_ignores_unknown_field_in_computed(self, repo):
        # FORMAT.md: campo extra in computed -> ignorato, import procede (D8)
        data = {"schema_version": "pocket-dnd/1",
                "identity": {"name": "Ghost", "level": 1},
                "computed": {"abilities": {"str": 10, "dex": 10, "con": 10,
                                           "int": 10, "wis": 10, "cha": 10},
                             "max_hp": 10, "armor_class": 10,
                             "telepathy_range": 60},   # campo inventato
                "declared": {}}
        cid = repo.import_character(data)   # non deve sollevare
        assert repo.get(cid)["name"] == "Ghost"

    def test_import_preserves_extra_field_in_declared(self, repo):
        data = {"schema_version": "pocket-dnd/1",
                "identity": {"name": "Keeper", "level": 1},
                "computed": {"abilities": {"str": 10, "dex": 10, "con": 10,
                                           "int": 10, "wis": 10, "cha": 10},
                             "max_hp": 10, "armor_class": 10},
                "declared": {"custom_lore": "tiene un segreto"}}
        cid = repo.import_character(data)
        assert repo.get(cid)["extended"]["custom_lore"] == "tiene un segreto"
