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


# ───────────────────────────── level up ─────────────────────────────

def _seed_classes(repo):
    """Popola srd_classes con i dadi vita standard. Senza questa tabella il
    level-up non puo' conoscere il dado vita del PG (D2 — l'app non inventa)."""
    with repo._lock:
        repo._conn.executemany(
            "INSERT INTO srd_classes (slug, name, hit_die) VALUES (?, ?, ?)",
            [("fighter", "Fighter", 10), ("wizard", "Wizard", 6),
             ("rogue", "Rogue", 8), ("barbarian", "Barbarian", 12)],
        )
        repo._conn.commit()


class TestLevelUp:
    """Level-up assistito (D3): livello +1, proficiency ricalcolata, HP a
    valore medio del dado vita + mod_COS, cura completa (D16). Le scelte di
    build (sottoclasse, feat, nuovo incantesimo) restano del giocatore e
    arrivano via un patch testuale che viene mergiato nel guscio `extended`."""

    def test_level_up_increments_level(self, repo):
        _seed_classes(repo)
        cid = repo.create(_sample_character())   # liv 3
        repo.level_up(cid)
        assert repo.get(cid)["level"] == 4

    def test_level_up_recomputes_proficiency_at_milestone(self, repo):
        _seed_classes(repo)
        char = _sample_character()
        char["level"] = 4    # liv 4 -> +2, prossimo (5) -> +3
        cid = repo.create(char)
        repo.level_up(cid)
        assert repo.get(cid)["proficiency_bonus"] == 3

    def test_level_up_adds_hp_average_plus_con_mod(self, repo):
        # fighter -> d10 (media 6); con 14 -> mod +2; gain = 8
        _seed_classes(repo)
        cid = repo.create(_sample_character())   # max_hp=28
        repo.level_up(cid)
        c = repo.get(cid)
        assert c["max_hp"] == 28 + 8

    def test_level_up_full_heals(self, repo):
        # D16: il level-up cura completamente (fine sessione = respiro lungo)
        _seed_classes(repo)
        char = _sample_character()
        char["current_hp"] = 5
        cid = repo.create(char)
        repo.level_up(cid)
        c = repo.get(cid)
        assert c["current_hp"] == c["max_hp"]

    def test_level_up_minimum_gain_is_one(self, repo):
        # con CON molto basso (mod -5), gain = max(1, 5 + (-5)) = 1
        _seed_classes(repo)
        char = _sample_character()
        char["con"] = 1   # mod -5
        cid = repo.create(char)
        repo.level_up(cid)
        c = repo.get(cid)
        assert c["max_hp"] == 28 + 1

    def test_level_up_at_max_raises(self, repo):
        _seed_classes(repo)
        char = _sample_character()
        char["level"] = 20
        cid = repo.create(char)
        with pytest.raises(ValueError):
            repo.level_up(cid)

    def test_level_up_unknown_class_raises(self, repo):
        # nessuna srd_classes seedata: la classe del PG non e' conosciuta
        char = _sample_character()
        cid = repo.create(char)
        with pytest.raises(ValueError):
            repo.level_up(cid)

    def test_level_up_unknown_character_raises(self, repo):
        _seed_classes(repo)
        with pytest.raises(CharacterNotFound):
            repo.level_up(9999)

    def test_level_up_merges_extended_patch(self, repo):
        _seed_classes(repo)
        char = _sample_character()
        char["extended"] = {"background": "Soldier", "notes": "Vecchio"}
        cid = repo.create(char)
        repo.level_up(cid, extended_patch={"notes": "Nuovo", "feat": "Lucky"})
        ext = repo.get(cid)["extended"]
        # campo preesistente non toccato resta, patch sovrascrive solo le sue chiavi
        assert ext["background"] == "Soldier"
        assert ext["notes"] == "Nuovo"
        assert ext["feat"] == "Lucky"

    def test_level_up_returns_summary(self, repo):
        _seed_classes(repo)
        cid = repo.create(_sample_character())
        summary = repo.level_up(cid)
        assert summary["old_level"] == 3
        assert summary["new_level"] == 4
        assert summary["hp_gained"] == 8
        assert summary["hit_die"] == 10


# ───────────────────────────── inventario ─────────────────────────────

class TestInventory:
    """Inventario: lista semplice di item dati dal master come loot.
    Solo nome (+ descrizione opzionale): l'app non interpreta gli effetti."""

    def test_new_character_has_empty_inventory(self, repo):
        cid = repo.create(_sample_character())
        assert repo.get(cid)["inventory"] == []

    def test_give_item_appends_to_inventory(self, repo):
        cid = repo.create(_sample_character())
        repo.give_item(cid, "Pozione di guarigione")
        inv = repo.get(cid)["inventory"]
        assert len(inv) == 1
        assert inv[0]["name"] == "Pozione di guarigione"

    def test_give_item_stores_description_when_passed(self, repo):
        cid = repo.create(_sample_character())
        repo.give_item(cid, "Mantello sospetto", "Sembra muoversi da solo.")
        item = repo.get(cid)["inventory"][0]
        assert item["description"] == "Sembra muoversi da solo."

    def test_give_item_omits_description_when_empty(self, repo):
        cid = repo.create(_sample_character())
        repo.give_item(cid, "Sasso")
        assert "description" not in repo.get(cid)["inventory"][0]

    def test_give_item_preserves_existing_items(self, repo):
        cid = repo.create(_sample_character())
        repo.give_item(cid, "Sacca di sale")
        repo.give_item(cid, "Corda da 50 piedi")
        names = [it["name"] for it in repo.get(cid)["inventory"]]
        assert names == ["Sacca di sale", "Corda da 50 piedi"]

    def test_give_item_returns_updated_inventory(self, repo):
        cid = repo.create(_sample_character())
        inv = repo.give_item(cid, "Daga argentata")
        assert isinstance(inv, list) and inv[-1]["name"] == "Daga argentata"

    def test_give_item_rejects_empty_name(self, repo):
        cid = repo.create(_sample_character())
        with pytest.raises(ValueError):
            repo.give_item(cid, "")

    def test_give_item_to_unknown_character_raises(self, repo):
        with pytest.raises(CharacterNotFound):
            repo.give_item(9999, "X")


# ─────────────────────── migration in-place ───────────────────────

class TestMigrationInventory:
    """init_schema deve aggiungere la colonna `inventory` anche su DB
    pre-esistenti creati prima che la colonna fosse introdotta."""

    def test_migrates_old_db_without_inventory_column(self, tmp_path):
        import sqlite3
        db = tmp_path / "old.db"
        # schema "vecchio" (senza inventory): solo i campi necessari per
        # simulare il caso. NOT NULL minimi.
        conn = sqlite3.connect(db)
        conn.executescript("""
            CREATE TABLE characters (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                player_name TEXT NOT NULL DEFAULT '',
                class TEXT NOT NULL DEFAULT '',
                race TEXT NOT NULL DEFAULT '',
                level INTEGER NOT NULL DEFAULT 1,
                str INTEGER NOT NULL DEFAULT 10,
                dex INTEGER NOT NULL DEFAULT 10,
                con INTEGER NOT NULL DEFAULT 10,
                int INTEGER NOT NULL DEFAULT 10,
                wis INTEGER NOT NULL DEFAULT 10,
                cha INTEGER NOT NULL DEFAULT 10,
                max_hp INTEGER NOT NULL DEFAULT 1,
                current_hp INTEGER NOT NULL DEFAULT 1,
                armor_class INTEGER NOT NULL DEFAULT 10,
                speed INTEGER NOT NULL DEFAULT 30,
                proficiency_bonus INTEGER NOT NULL DEFAULT 2,
                skill_proficiencies TEXT NOT NULL DEFAULT '[]',
                actions TEXT NOT NULL DEFAULT '[]',
                extended TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                updated_at TEXT NOT NULL DEFAULT (datetime('now'))
            );
        """)
        conn.execute("INSERT INTO characters (name) VALUES ('Vecchio Eroe')")
        conn.commit()
        conn.close()

        # ora apriamo col CharacterRepo: la migration deve scattare
        r = CharacterRepo(str(db))
        r.init_schema(SCHEMA.read_text(encoding="utf-8"))
        char = r.list_all()[0]
        assert char["name"] == "Vecchio Eroe"
        # inventory ora c'e' (vuoto, default)
        assert char["inventory"] == []
        # e si puo' aggiungere loot anche al PG pre-esistente
        r.give_item(char["id"], "Pozione")
        assert r.get(char["id"])["inventory"][0]["name"] == "Pozione"
