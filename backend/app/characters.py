"""Repository personaggi: CRUD su SQLite + serializzazione import/export.

Due responsabilita' nello stesso modulo ma distinte (vedi DECISIONS.md D9):
  - CRUD          -> persistenza del modello su SQLite.
  - export/import -> traduzione da/verso il JSON di docs/FORMAT.md.

Il modello personaggio: nucleo vivo come colonne vere, guscio inerte in una
colonna JSON `extended` (DECISIONS.md D8). I calcoli derivati (proficiency)
non si salvano "a fiducia": si ricalcolano da rules.py a ogni write.
"""
from __future__ import annotations

import json
import sqlite3
import threading

from app.rules import ability_modifier, level_up_hp_gain, proficiency_bonus

SCHEMA_VERSION = "pocket-dnd/1"
COMPAT = "5e-srd-5.1"

# I sei attributi, nell'ordine canonico.
_ABILITIES = ("str", "dex", "con", "int", "wis", "cha")

# Colonne del nucleo che un update puo' toccare direttamente.
_UPDATABLE = {
    "name", "player_name", "class", "race", "level",
    *_ABILITIES,
    "max_hp", "current_hp", "armor_class", "speed",
}
# Colonne serializzate come JSON (liste/dict) nel DB.
_JSON_COLUMNS = {"skill_proficiencies", "actions", "extended"}


class CharacterNotFound(LookupError):
    """Nessun personaggio con l'id richiesto."""


class ImportError(ValueError):
    """JSON di import malformato o incompatibile."""


class CharacterRepo:
    """Accesso ai personaggi su un database SQLite."""

    def __init__(self, db_path: str):
        # check_same_thread=False: il server esegue gli endpoint sincroni in un
        # threadpool, quindi la connessione e' usata da thread diversi. Lo si
        # consente, ma ogni accesso e' serializzato dal lock qui sotto: SQLite
        # gestisce un solo writer alla volta e il carico di pocket-dnd e'
        # minimo (poche scritture, una stanza). Vedi DECISIONS.md D4.
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA foreign_keys = ON")
        self._lock = threading.RLock()

    # ─────────────────────────── setup ───────────────────────────

    def init_schema(self, schema_sql: str) -> None:
        """Applica lo schema (idempotente: lo schema usa IF NOT EXISTS)."""
        self._conn.executescript(schema_sql)
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()

    # ─────────────────────────── CRUD ───────────────────────────

    def create(self, data: dict) -> int:
        """Inserisce un personaggio. `data` usa le chiavi del modello (non FORMAT.md)."""
        name = (data.get("name") or "").strip()
        if not name:
            raise ValueError("il personaggio deve avere un nome")

        row = self._with_defaults(data)
        row["proficiency_bonus"] = proficiency_bonus(row["level"])

        cols = list(row.keys())
        placeholders = ", ".join("?" for _ in cols)
        values = [self._encode(c, row[c]) for c in cols]

        with self._lock:
            cur = self._conn.execute(
                f"INSERT INTO characters ({', '.join(cols)}) VALUES ({placeholders})",
                values,
            )
            self._conn.commit()
        return cur.lastrowid

    def get(self, character_id: int) -> dict:
        """Restituisce un personaggio come dict del modello. Solleva se assente."""
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM characters WHERE id = ?", (character_id,)
            ).fetchone()
        if row is None:
            raise CharacterNotFound(f"personaggio {character_id} inesistente")
        return self._decode_row(row)

    def list_all(self) -> list[dict]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM characters ORDER BY name"
            ).fetchall()
        return [self._decode_row(r) for r in rows]

    def update(self, character_id: int, changes: dict) -> None:
        """Aggiorna i campi indicati. Ricalcola la proficiency se cambia il livello."""
        existing = self.get(character_id)   # solleva se assente

        fields = {k: v for k, v in changes.items()
                  if k in _UPDATABLE or k in _JSON_COLUMNS}
        if not fields:
            return

        # se cambia il livello, la proficiency va ricalcolata, mai presa a fiducia
        new_level = fields.get("level", existing["level"])
        fields["proficiency_bonus"] = proficiency_bonus(new_level)

        assignments = ", ".join(f"{c} = ?" for c in fields)
        values = [self._encode(c, v) for c, v in fields.items()]
        values.append(character_id)

        with self._lock:
            self._conn.execute(
                f"UPDATE characters SET {assignments}, updated_at = datetime('now') "
                f"WHERE id = ?",
                values,
            )
            self._conn.commit()

    def delete(self, character_id: int) -> None:
        with self._lock:
            cur = self._conn.execute(
                "DELETE FROM characters WHERE id = ?", (character_id,)
            )
            if cur.rowcount == 0:
                raise CharacterNotFound(f"personaggio {character_id} inesistente")
            self._conn.commit()

    def level_up(self, character_id: int,
                 extended_patch: dict | None = None) -> dict:
        """Sale di un livello in modo assistito (D3, D16).

        - livello +1 (errore se gia' 20)
        - proficiency ricalcolata da rules.proficiency_bonus
        - HP guadagnati = valore medio del dado vita + mod_COS (min 1)
        - cura completa: current_hp = nuovo max_hp (D16)
        - extended_patch: merge superficiale nel guscio; le scelte di build
          restano del giocatore, l'app le conserva e basta (D8)

        Restituisce un riassunto: vecchio/nuovo livello, gain HP, dado vita.
        """
        char = self.get(character_id)   # solleva CharacterNotFound
        old_level = char["level"]
        if old_level >= 20:
            raise ValueError(f"livello gia' al massimo (20)")

        hit_die = self._hit_die_for_class(char["class"])
        gain = level_up_hp_gain(hit_die, ability_modifier(char["con"]))
        new_max = char["max_hp"] + gain
        new_level = old_level + 1

        merged_extended = {**(char.get("extended") or {}),
                           **(extended_patch or {})}

        self.update(character_id, {
            "level": new_level,
            "max_hp": new_max,
            "current_hp": new_max,        # D16: cura completa
            "extended": merged_extended,
        })
        return {
            "old_level": old_level,
            "new_level": new_level,
            "hp_gained": gain,
            "hit_die": hit_die,
            "max_hp": new_max,
        }

    def _hit_die_for_class(self, class_slug: str) -> int:
        """Lookup classe -> dado vita dalla SRD seedata. Solleva se la classe
        non e' nota: l'app NON inventa (D2), il DM puo' fare a mano."""
        with self._lock:
            row = self._conn.execute(
                "SELECT hit_die FROM srd_classes WHERE slug = ?",
                (class_slug or "",),
            ).fetchone()
        if row is None:
            raise ValueError(
                f"classe sconosciuta: {class_slug!r} — dado vita non determinabile"
            )
        return int(row["hit_die"])

    # ─────────────────────── serializzazione ───────────────────────

    def export_character(self, character_id: int) -> dict:
        """Esporta nel formato JSON di docs/FORMAT.md (computed / declared)."""
        c = self.get(character_id)
        return {
            "schema_version": SCHEMA_VERSION,
            "compat": COMPAT,
            "identity": {
                "name": c["name"],
                "player_name": c["player_name"],
                "class": c["class"],
                "race": c["race"],
                "level": c["level"],
            },
            "computed": {
                "abilities": {a: c[a] for a in _ABILITIES},
                "max_hp": c["max_hp"],
                "current_hp": c["current_hp"],
                "armor_class": c["armor_class"],
                "speed": c["speed"],
                "proficiency_bonus": c["proficiency_bonus"],
                "skill_proficiencies": c["skill_proficiencies"],
                "actions": c["actions"],
            },
            # guscio inerte: riesportato verbatim
            "declared": c["extended"],
        }

    def import_character(self, payload: dict) -> int:
        """Crea un personaggio da un JSON in formato docs/FORMAT.md.

        Robustezza (FORMAT.md): schema sconosciuto -> rifiuto; computed
        mancante -> rifiuto; declared mancante -> oggetto vuoto; campo extra
        in computed -> ignorato; campo extra in declared -> conservato.
        """
        version = payload.get("schema_version")
        if version != SCHEMA_VERSION:
            raise ImportError(
                f"schema_version non supportata: {version!r} "
                f"(atteso {SCHEMA_VERSION!r})"
            )

        computed = payload.get("computed")
        if not isinstance(computed, dict):
            raise ImportError("blocco 'computed' mancante o malformato")

        identity = payload.get("identity") or {}
        declared = payload.get("declared")
        if not isinstance(declared, dict):
            declared = {}

        abilities = computed.get("abilities") or {}

        model = {
            "name": identity.get("name", ""),
            "player_name": identity.get("player_name", ""),
            "class": identity.get("class", ""),
            "race": identity.get("race", ""),
            "level": identity.get("level", 1),
            "max_hp": computed.get("max_hp", 1),
            "current_hp": computed.get("current_hp", computed.get("max_hp", 1)),
            "armor_class": computed.get("armor_class", 10),
            "speed": computed.get("speed", 30),
            "skill_proficiencies": computed.get("skill_proficiencies", []),
            "actions": computed.get("actions", []),
            "extended": declared,
        }
        for a in _ABILITIES:
            model[a] = abilities.get(a, 10)

        # eventuali campi extra in computed sono semplicemente non mappati:
        # ignorati implicitamente, l'import procede (FORMAT.md / D8).
        return self.create(model)

    # ─────────────────────────── interni ───────────────────────────

    @staticmethod
    def _with_defaults(data: dict) -> dict:
        """Completa un dict del modello coi default mancanti."""
        row = {
            "name": data["name"].strip(),
            "player_name": data.get("player_name", ""),
            "class": data.get("class", ""),
            "race": data.get("race", ""),
            "level": data.get("level", 1),
            "max_hp": data.get("max_hp", 1),
            "current_hp": data.get("current_hp", data.get("max_hp", 1)),
            "armor_class": data.get("armor_class", 10),
            "speed": data.get("speed", 30),
            "skill_proficiencies": data.get("skill_proficiencies", []),
            "actions": data.get("actions", []),
            "extended": data.get("extended", {}),
        }
        for a in _ABILITIES:
            row[a] = data.get(a, 10)
        return row

    @staticmethod
    def _encode(column: str, value):
        """Serializza per SQLite: le colonne JSON diventano stringhe."""
        if column in _JSON_COLUMNS:
            return json.dumps(value if value is not None else
                              ([] if column != "extended" else {}))
        return value

    @staticmethod
    def _decode_row(row: sqlite3.Row) -> dict:
        """Trasforma una Row in un dict del modello, deserializzando il JSON."""
        d = dict(row)
        for col in _JSON_COLUMNS:
            if col in d and isinstance(d[col], str):
                d[col] = json.loads(d[col])
        return d
