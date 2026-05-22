#!/usr/bin/env python3
"""seed_srd.py — popola le tabelle srd_* da 5e-bits/5e-database.

Esecuzione UNA TANTUM al setup. Non e' una dipendenza runtime.

Sorgente: i JSON di https://github.com/5e-bits/5e-database (set "2014" = SRD 5.1).
I file vengono presi da backend/data/5e-database/ se presenti, altrimenti
scaricati da raw.githubusercontent.com.

Vedi CONTEXT.md per la mappatura SRD -> modello e DECISIONS.md D6.

NOTA: questo script normalizza i dadi di danno verso la forma canonica "NdS".
La normalizzazione completa (con modificatori, vantaggio, ecc.) e' compito del
motore dadi dello step 2 — qui ci si limita a estrarre count/value puliti.
"""
from __future__ import annotations

import json
import sqlite3
import sys
import urllib.request
from pathlib import Path

# Set "2014/en" del repo 5e-database = SRD 5.1 in inglese.
RAW_BASE = "https://raw.githubusercontent.com/5e-bits/5e-database/main/src/2014/en"
LOCAL_DIR = Path(__file__).resolve().parent.parent / "data" / "5e-database"

# file JSON -> nome logico usato qui sotto
FILES = {
    "skills": "5e-SRD-Skills.json",
    "equipment": "5e-SRD-Equipment.json",
    "conditions": "5e-SRD-Conditions.json",
    "spells": "5e-SRD-Spells.json",
    "classes": "5e-SRD-Classes.json",
    "monsters": "5e-SRD-Monsters.json",
}


def load_json(logical_name: str, filename: str) -> list:
    """Carica un JSON SRD: prima da disco locale, poi da rete come fallback."""
    local = LOCAL_DIR / filename
    if local.exists():
        print(f"  [{logical_name}] da locale: {local}")
        return json.loads(local.read_text(encoding="utf-8"))
    url = f"{RAW_BASE}/{filename}"
    print(f"  [{logical_name}] download: {url}")
    with urllib.request.urlopen(url, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def normalize_dice(count, value) -> str:
    """(2, 6) -> '2d6'. Input mancante/zero -> ''."""
    try:
        c, v = int(count), int(value)
    except (TypeError, ValueError):
        return ""
    if c <= 0 or v <= 0:
        return ""
    return f"{c}d{v}"


def seed_skills(db, rows):
    for r in rows:
        # nello schema SRD l'attributo della skill e' in ability_score.index
        ability = (r.get("ability_score") or {}).get("index", "")
        db.execute(
            "INSERT OR REPLACE INTO srd_skills (slug, name, ability) VALUES (?,?,?)",
            (r["index"], r["name"], ability),
        )
    return len(rows)


def seed_weapons(db, equipment_rows):
    """Dal file equipment estrae SOLO le armi (equipment_category == Weapon)."""
    n = 0
    for r in equipment_rows:
        cat = (r.get("equipment_category") or {}).get("index", "")
        if cat != "weapon":
            continue
        dmg = r.get("damage") or {}
        dice = (dmg.get("damage_dice") or "")  # gia' in forma "1d8" nello schema 2014
        dtype = (dmg.get("damage_type") or {}).get("index", "")
        props = [p.get("index", "") for p in (r.get("properties") or [])]
        db.execute(
            "INSERT OR REPLACE INTO srd_weapons "
            "(slug, name, damage_dice, damage_type, properties) VALUES (?,?,?,?,?)",
            (r["index"], r["name"], dice, dtype, json.dumps(props)),
        )
        n += 1
    return n


def seed_conditions(db, rows):
    for r in rows:
        desc = " ".join(r.get("desc") or [])
        db.execute(
            "INSERT OR REPLACE INTO srd_conditions (slug, name, description) VALUES (?,?,?)",
            (r["index"], r["name"], desc),
        )
    return len(rows)


def seed_spells(db, rows):
    for r in rows:
        desc = " ".join(r.get("desc") or [])
        dmg = r.get("damage") or {}
        # i dadi spell sono spesso scalati per livello; in v0 prendiamo, se c'e',
        # il damage_at_slot_level / damage_at_character_level piu' basso.
        dice = ""
        at_slot = dmg.get("damage_at_slot_level") or {}
        at_char = dmg.get("damage_at_character_level") or {}
        table = at_slot or at_char
        if table:
            lowest = sorted(table.keys(), key=lambda k: int(k))[0]
            dice = table[lowest]
        db.execute(
            "INSERT OR REPLACE INTO srd_spells "
            "(slug, name, level, school, casting_time, spell_range, description, damage_dice) "
            "VALUES (?,?,?,?,?,?,?,?)",
            (
                r["index"], r["name"], r.get("level", 0),
                (r.get("school") or {}).get("name", ""),
                r.get("casting_time", ""), r.get("range", ""),
                desc, dice,
            ),
        )
    return len(rows)


def seed_classes(db, rows):
    for r in rows:
        db.execute(
            "INSERT OR REPLACE INTO srd_classes (slug, name, hit_die) VALUES (?,?,?)",
            (r["index"], r["name"], r.get("hit_die", 8)),
        )
    return len(rows)


def seed_monsters(db, rows):
    for r in rows:
        ac = r.get("armor_class")
        # armor_class nello schema 2014 e' una lista di oggetti {value, type}
        if isinstance(ac, list) and ac:
            ac_val = ac[0].get("value", 10)
        elif isinstance(ac, int):
            ac_val = ac
        else:
            ac_val = 10
        db.execute(
            "INSERT OR REPLACE INTO srd_monsters "
            "(slug, name, armor_class, hit_points, challenge, statblock) VALUES (?,?,?,?,?,?)",
            (
                r["index"], r["name"], ac_val,
                r.get("hit_points", 1),
                str(r.get("challenge_rating", "0")),
                json.dumps(r),  # statblock completo conservato verbatim
            ),
        )
    return len(rows)


def main():
    if len(sys.argv) != 2:
        print("uso: seed_srd.py <percorso_db_sqlite>")
        sys.exit(1)

    db_path = sys.argv[1]
    db = sqlite3.connect(db_path)
    db.execute("PRAGMA foreign_keys = ON")

    schema = Path(__file__).resolve().parent.parent / "app" / "schema.sql"
    db.executescript(schema.read_text(encoding="utf-8"))

    print("Seed SRD in corso...")
    data = {name: load_json(name, fn) for name, fn in FILES.items()}

    counts = {
        "skills": seed_skills(db, data["skills"]),
        "weapons": seed_weapons(db, data["equipment"]),
        "conditions": seed_conditions(db, data["conditions"]),
        "spells": seed_spells(db, data["spells"]),
        "classes": seed_classes(db, data["classes"]),
        "monsters": seed_monsters(db, data["monsters"]),
    }

    db.execute(
        "INSERT OR REPLACE INTO srd_meta (key, value) VALUES (?,?)",
        ("source", "5e-bits/5e-database (SRD 5.1, set 2014)"),
    )
    db.execute(
        "INSERT OR REPLACE INTO srd_meta (key, value) VALUES (?,?)",
        ("compat", "5e-srd-5.1"),
    )
    db.commit()
    db.close()

    print("\nSeed completato:")
    for k, v in counts.items():
        print(f"  {k:12s} {v:5d}")


if __name__ == "__main__":
    main()
