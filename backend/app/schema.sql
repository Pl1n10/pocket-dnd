-- schema.sql — pocket-dnd — schema SQLite v1
--
-- Due famiglie di tabelle:
--   1. APPLICATIVE  — dati creati dall'app (personaggi, sessioni, tiri).
--   2. SRD          — riferimento di sola lettura, popolate da seed_srd.py.
--
-- Convenzioni:
--   - Il NUCLEO VIVO del personaggio = colonne vere (query + calcoli).
--   - Il GUSCIO INERTE = colonna JSON `extended` (conservato, mai interpretato).
--   - I modificatori NON si salvano: si calcolano da floor((score-10)/2).
-- Vedi DECISIONS.md D8 e ANTIPATTERNS.md AP7.

PRAGMA foreign_keys = ON;

-- ───────────────────────────── APPLICATIVE ─────────────────────────────

-- Personaggi: persistenti, sopravvivono alle sessioni (D3).
CREATE TABLE IF NOT EXISTS characters (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    name                TEXT    NOT NULL,
    player_name         TEXT    NOT NULL DEFAULT '',
    class               TEXT    NOT NULL DEFAULT '',   -- ID SRD minuscolo
    race                TEXT    NOT NULL DEFAULT '',   -- ID SRD minuscolo
    level               INTEGER NOT NULL DEFAULT 1 CHECK (level BETWEEN 1 AND 20),

    -- Nucleo vivo: i 6 attributi grezzi.
    str                 INTEGER NOT NULL DEFAULT 10,
    dex                 INTEGER NOT NULL DEFAULT 10,
    con                 INTEGER NOT NULL DEFAULT 10,
    int                 INTEGER NOT NULL DEFAULT 10,
    wis                 INTEGER NOT NULL DEFAULT 10,
    cha                 INTEGER NOT NULL DEFAULT 10,

    -- Nucleo vivo: combattimento.
    max_hp              INTEGER NOT NULL DEFAULT 1,
    current_hp          INTEGER NOT NULL DEFAULT 1,     -- HP "base" del PG
    armor_class         INTEGER NOT NULL DEFAULT 10,
    speed               INTEGER NOT NULL DEFAULT 30,
    proficiency_bonus   INTEGER NOT NULL DEFAULT 2,     -- cache; derivabile dal livello

    -- Nucleo vivo: liste serializzate (piccole, niente tabelle dedicate in v0).
    skill_proficiencies TEXT    NOT NULL DEFAULT '[]',  -- JSON: ["stealth", ...]
    actions             TEXT    NOT NULL DEFAULT '[]',  -- JSON: vedi docs/FORMAT.md
    inventory           TEXT    NOT NULL DEFAULT '[]',  -- JSON: [{name, description?}]

    -- Guscio inerte: tutto ciò che l'app conserva ma NON interpreta (D8, AP7).
    extended            TEXT    NOT NULL DEFAULT '{}',  -- JSON opaco

    created_at          TEXT    NOT NULL DEFAULT (datetime('now')),
    updated_at          TEXT    NOT NULL DEFAULT (datetime('now'))
);

-- Sessioni: una one-shot.
CREATE TABLE IF NOT EXISTS sessions (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    title       TEXT    NOT NULL DEFAULT 'Senza titolo',
    dm_notes    TEXT    NOT NULL DEFAULT '',
    status      TEXT    NOT NULL DEFAULT 'active'      -- active | closed
                CHECK (status IN ('active', 'closed')),
    created_at  TEXT    NOT NULL DEFAULT (datetime('now'))
);

-- Partecipanti: collega un personaggio a una sessione, con lo stato DI SESSIONE.
-- current_hp_override / conditions vivono qui: non sporcano il PG persistente.
CREATE TABLE IF NOT EXISTS session_participants (
    session_id          INTEGER NOT NULL REFERENCES sessions(id)   ON DELETE CASCADE,
    character_id        INTEGER NOT NULL REFERENCES characters(id) ON DELETE CASCADE,
    initiative          INTEGER,                         -- NULL = non tirata
    current_hp_override INTEGER,                         -- NULL = usa characters.current_hp
    conditions          TEXT    NOT NULL DEFAULT '[]',   -- JSON: ["poisoned", ...]
    joined_at           TEXT    NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (session_id, character_id)
);

-- Log dei tiri: alimenta il feed live della consolle master.
CREATE TABLE IF NOT EXISTS roll_log (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id   INTEGER NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    character_id INTEGER REFERENCES characters(id) ON DELETE SET NULL, -- NULL = tiro del DM
    label        TEXT    NOT NULL DEFAULT '',            -- es. "Longsword to-hit"
    formula      TEXT    NOT NULL,                       -- es. "1d20+5"
    result       INTEGER NOT NULL,
    breakdown    TEXT    NOT NULL DEFAULT '',            -- es. "[14]+5", o "adv [8,17]->17 +5"
    created_at   TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_roll_log_session ON roll_log(session_id, created_at);
CREATE INDEX IF NOT EXISTS idx_participants_session ON session_participants(session_id);

-- ───────────────────────────── SRD (sola lettura) ──────────────────────────
-- Popolate una tantum da scripts/seed_srd.py a partire dai JSON di
-- 5e-bits/5e-database. NON modificate a runtime. Vedi CONTEXT.md.

-- Mappa skill -> attributo. Per calcolare i tiri di skill.
CREATE TABLE IF NOT EXISTS srd_skills (
    slug         TEXT PRIMARY KEY,        -- es. "stealth"
    name         TEXT NOT NULL,           -- es. "Stealth"
    ability      TEXT NOT NULL            -- es. "dex"
);

-- Armi: il sottoinsieme "weapons" di equipment. Per i dadi di danno.
CREATE TABLE IF NOT EXISTS srd_weapons (
    slug         TEXT PRIMARY KEY,        -- es. "longsword"
    name         TEXT NOT NULL,
    damage_dice  TEXT NOT NULL DEFAULT '',-- forma canonica "NdS", normalizzata
    damage_type  TEXT NOT NULL DEFAULT '',
    properties   TEXT NOT NULL DEFAULT '[]'  -- JSON: ["versatile", "finesse", ...]
);

-- Condizioni: nome + testo. Mostrate come flag, NON applicate (D2).
CREATE TABLE IF NOT EXISTS srd_conditions (
    slug         TEXT PRIMARY KEY,        -- es. "poisoned"
    name         TEXT NOT NULL,
    description  TEXT NOT NULL DEFAULT ''
);

-- Incantesimi: catalogo consultabile. Tirati solo se hanno dadi (D2).
CREATE TABLE IF NOT EXISTS srd_spells (
    slug         TEXT PRIMARY KEY,
    name         TEXT NOT NULL,
    level        INTEGER NOT NULL DEFAULT 0,  -- 0 = cantrip
    school       TEXT NOT NULL DEFAULT '',
    casting_time TEXT NOT NULL DEFAULT '',
    spell_range  TEXT NOT NULL DEFAULT '',
    description  TEXT NOT NULL DEFAULT '',
    damage_dice  TEXT NOT NULL DEFAULT ''     -- forma "NdS" se l'incantesimo fa danno, else ''
);

-- Classi: solo dado vita + proficiency iniziali, per il level-up assistito.
CREATE TABLE IF NOT EXISTS srd_classes (
    slug         TEXT PRIMARY KEY,        -- es. "fighter"
    name         TEXT NOT NULL,
    hit_die      INTEGER NOT NULL DEFAULT 8   -- es. 10 per fighter
);

-- Mostri: statblock pronti per il DM, formato SRD (D7).
CREATE TABLE IF NOT EXISTS srd_monsters (
    slug         TEXT PRIMARY KEY,
    name         TEXT NOT NULL,
    armor_class  INTEGER NOT NULL DEFAULT 10,
    hit_points   INTEGER NOT NULL DEFAULT 1,
    challenge    TEXT NOT NULL DEFAULT '0',
    statblock    TEXT NOT NULL DEFAULT '{}'   -- JSON: statblock completo formato SRD
);

-- Metadati del seed: tracciano fonte e versione del dato importato.
CREATE TABLE IF NOT EXISTS srd_meta (
    key          TEXT PRIMARY KEY,
    value        TEXT NOT NULL
);
