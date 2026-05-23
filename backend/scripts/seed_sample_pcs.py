"""Inserisce 5 PG di esempio pronti, archetipi 5e classici a livello 3.

Per cominciare una one-shot senza dover creare schede a mano. Sono PG
distinti per ruolo: tank, picchiatore, healer, archere, caster — un
gruppo standard da pub.

Esecuzione (host):
    python3 scripts/seed_sample_pcs.py pocket-dnd.db

Esecuzione (container):
    docker compose exec pocket-dnd python3 scripts/seed_sample_pcs.py /data/pocket-dnd.db

Idempotente: se un PG con lo stesso nome esiste gia', viene saltato.
"""
from __future__ import annotations

import sys
from pathlib import Path

# permetti import di app.* anche eseguendo lo script dalla CWD
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.characters import CharacterRepo


SAMPLES = [
    {
        "name": "Korr",
        "player_name": "—",
        "class": "barbarian",
        "race": "dwarf",
        "level": 3,
        "str": 17, "dex": 13, "con": 16, "int": 8, "wis": 12, "cha": 9,
        "max_hp": 34, "current_hp": 34, "armor_class": 14, "speed": 25,
        "skill_proficiencies": ["athletics", "intimidation"],
        "actions": [
            {"name": "Greataxe", "to_hit_mod": 5,
             "damage_dice": "1d12+3", "damage_type": "slashing",
             "description": "Due mani, pesante."},
            {"name": "Handaxe (lancio)", "to_hit_mod": 5,
             "damage_dice": "1d6+3", "damage_type": "slashing",
             "description": "Gittata 20/60 ft."},
            {"name": "Rabbia", "to_hit_mod": None,
             "damage_dice": "", "damage_type": "",
             "description": "Vantaggio su prove e tiri salvezza di Forza; +2 ai danni in mischia."},
        ],
        "extended": {
            "background": "Outlander",
            "subclass": "Path of the Berserker",
            "notes": "Scure ereditata dal padre."
        },
    },
    {
        "name": "Veska",
        "player_name": "—",
        "class": "bard",
        "race": "half-elf",
        "level": 3,
        "str": 10, "dex": 14, "con": 12, "int": 11, "wis": 12, "cha": 17,
        "max_hp": 21, "current_hp": 21, "armor_class": 14, "speed": 30,
        "skill_proficiencies": ["performance", "persuasion", "deception", "insight"],
        "actions": [
            {"name": "Stocco (rapier)", "to_hit_mod": 4,
             "damage_dice": "1d8+2", "damage_type": "piercing",
             "description": "Finesse."},
            {"name": "Vicious Mockery", "to_hit_mod": None,
             "damage_dice": "1d4", "damage_type": "psychic",
             "description": "Cantrip. Salvezza Saggezza CD 13 o svantaggio al prossimo attacco."},
            {"name": "Healing Word", "to_hit_mod": None,
             "damage_dice": "1d4+3", "damage_type": "guarigione",
             "description": "Liv 1, bonus action, gittata 60 ft."},
            {"name": "Ispirazione bardica", "to_hit_mod": None,
             "damage_dice": "", "damage_type": "",
             "description": "Bonus action. d6 da spendere su attacco/prova/salvezza entro 10 min."},
        ],
        "extended": {
            "background": "Entertainer",
            "subclass": "College of Lore",
            "notes": "Suona il liuto, mai senza."
        },
    },
    {
        "name": "Talindra",
        "player_name": "—",
        "class": "cleric",
        "race": "half-elf",
        "level": 3,
        "str": 14, "dex": 10, "con": 14, "int": 11, "wis": 16, "cha": 13,
        "max_hp": 24, "current_hp": 24, "armor_class": 18, "speed": 30,
        "skill_proficiencies": ["religion", "medicine", "insight"],
        "actions": [
            {"name": "Mazza (mace)", "to_hit_mod": 4,
             "damage_dice": "1d6+2", "damage_type": "bludgeoning",
             "description": "Una mano."},
            {"name": "Sacred Flame", "to_hit_mod": None,
             "damage_dice": "2d8", "damage_type": "radiant",
             "description": "Cantrip. Salvezza Destrezza CD 13."},
            {"name": "Cure Wounds", "to_hit_mod": None,
             "damage_dice": "1d8+3", "damage_type": "guarigione",
             "description": "Liv 1, contatto."},
            {"name": "Bless", "to_hit_mod": None,
             "damage_dice": "", "damage_type": "",
             "description": "Liv 1, conc. 1 min. Fino a 3 alleati: +1d4 a tiri per colpire e salvezze."},
            {"name": "Channel Divinity", "to_hit_mod": None,
             "damage_dice": "", "damage_type": "",
             "description": "Turn Undead: salvezza Saggezza CD 13 o fuga per 1 min."},
        ],
        "extended": {
            "background": "Acolyte",
            "subclass": "Life Domain",
            "notes": "Armatura completa + scudo. Simbolo sacro al collo."
        },
    },
    {
        "name": "Galadran",
        "player_name": "—",
        "class": "ranger",
        "race": "elf",
        "level": 3,
        "str": 12, "dex": 17, "con": 14, "int": 10, "wis": 14, "cha": 8,
        "max_hp": 27, "current_hp": 27, "armor_class": 15, "speed": 30,
        "skill_proficiencies": ["stealth", "survival", "perception", "athletics"],
        "actions": [
            {"name": "Arco lungo (longbow)", "to_hit_mod": 5,
             "damage_dice": "1d8+3", "damage_type": "piercing",
             "description": "Gittata 150/600 ft."},
            {"name": "Spada corta (shortsword)", "to_hit_mod": 5,
             "damage_dice": "1d6+3", "damage_type": "piercing",
             "description": "Finesse, leggera."},
            {"name": "Hunter's Mark", "to_hit_mod": None,
             "damage_dice": "1d6", "damage_type": "extra (marchio)",
             "description": "Liv 1, conc. 1 ora. +1d6 contro il bersaglio marcato."},
            {"name": "Cure Wounds", "to_hit_mod": None,
             "damage_dice": "1d8+2", "damage_type": "guarigione",
             "description": "Liv 1, contatto."},
        ],
        "extended": {
            "background": "Outlander",
            "subclass": "Hunter (Colossus Slayer)",
            "favored_enemy": "Goblinoidi",
            "notes": "Compagno animale: lupo (opzionale, dopo)."
        },
    },
    {
        "name": "Pip",
        "player_name": "—",
        "class": "sorcerer",
        "race": "halfling",
        "level": 3,
        "str": 8, "dex": 16, "con": 14, "int": 12, "wis": 11, "cha": 17,
        "max_hp": 20, "current_hp": 20, "armor_class": 13, "speed": 25,
        "skill_proficiencies": ["arcana", "persuasion"],
        "actions": [
            {"name": "Pugnale (dagger)", "to_hit_mod": 5,
             "damage_dice": "1d4+3", "damage_type": "piercing",
             "description": "Finesse, lancio 20/60 ft."},
            {"name": "Fire Bolt", "to_hit_mod": 5,
             "damage_dice": "2d10", "damage_type": "fire",
             "description": "Cantrip, gittata 120 ft."},
            {"name": "Magic Missile", "to_hit_mod": None,
             "damage_dice": "3d4+3", "damage_type": "force",
             "description": "Liv 1. Tre dardi, +1 ciascuno. Mai mancano."},
            {"name": "Burning Hands", "to_hit_mod": None,
             "damage_dice": "3d6", "damage_type": "fire",
             "description": "Liv 1, cono 15 ft. Salvezza Destrezza CD 13 dimezza."},
            {"name": "Shield (reaction)", "to_hit_mod": None,
             "damage_dice": "", "damage_type": "",
             "description": "Liv 1, +5 CA fino al prossimo turno; nega Magic Missile."},
        ],
        "extended": {
            "background": "Charlatan",
            "subclass": "Wild Magic",
            "notes": "Sorcery Points: 3. Lucky (talento razziale)."
        },
    },
]


def main(db_path: str) -> None:
    repo = CharacterRepo(db_path)
    existing = {c["name"] for c in repo.list_all()}

    added, skipped = [], []
    for pc in SAMPLES:
        if pc["name"] in existing:
            skipped.append(pc["name"])
            continue
        cid = repo.create(pc)
        added.append(f"{pc['name']} (id={cid}, {pc['race']} {pc['class']})")

    print("Seed PG di esempio:")
    if added:
        print("  AGGIUNTI:")
        for line in added:
            print(f"    + {line}")
    if skipped:
        print("  GIA' PRESENTI (saltati):")
        for n in skipped:
            print(f"    · {n}")
    if not added and not skipped:
        print("  nessun PG processato (lista vuota?)")


if __name__ == "__main__":
    db = sys.argv[1] if len(sys.argv) > 1 else "pocket-dnd.db"
    main(db)
