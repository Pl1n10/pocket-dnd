# FORMAT.md — contratto del JSON di scambio personaggio

> Formato di import/export di un personaggio pocket-dnd.
> JSON proprietario, versionato, human-readable. NON è il formato D&D Beyond
> e non aspira ad esserlo (vedi `DECISIONS.md` D7).

## Principi

1. **Versionato** — ogni file dichiara `schema_version`. Un importatore che non
   riconosce la versione rifiuta esplicitamente, non indovina.
2. **Human-readable** — leggibile e ricostruibile a mano. Si passa via Telegram,
   si committa, si backuppa.
3. **Identificatori SRD** — dove esiste un ID nella SRD, si usa quello
   (`"stealth"`, `"longsword"`, `"poisoned"`), non un id arbitrario.
4. **Onesto sulla provenienza** — i campi che l'app calcola e garantisce stanno
   in `computed`; quelli inseriti a mano e solo conservati stanno in `declared`.
   Chi importa altrove sa di cosa fidarsi (vedi `DECISIONS.md` D8).

## Struttura

```json
{
  "schema_version": "pocket-dnd/1",
  "compat": "5e-srd-5.1",
  "exported_at": "2026-05-22T15:30:00Z",

  "identity": {
    "name": "Brannor",
    "player_name": "Marco",
    "class": "fighter",
    "level": 3,
    "race": "human"
  },

  "computed": {
    "abilities": { "str": 16, "dex": 13, "con": 14,
                   "int": 10, "wis": 12, "cha": 8 },
    "max_hp": 28,
    "armor_class": 16,
    "speed": 30,
    "proficiency_bonus": 2,
    "skill_proficiencies": ["athletics", "intimidation"],
    "actions": [
      {
        "name": "Longsword",
        "srd_ref": "longsword",
        "to_hit_mod": 5,
        "damage_dice": "1d8+3",
        "damage_type": "slashing",
        "description": "Versatile (1d10)."
      }
    ]
  },

  "declared": {
    "background": "Soldier",
    "subclass": "Champion",
    "feats": [],
    "traits": "Disciplined, blunt.",
    "equipment": ["chain mail", "shield", "explorer's pack"],
    "known_spells": [],
    "notes": "Free-text. L'app non interpreta nulla qui dentro."
  }
}
```

## Regole di campo

### `schema_version` (obbligatorio)
Stringa `pocket-dnd/N`. Versione **1** = questo documento.

### `compat` (obbligatorio)
Versione SRD a cui gli identificatori fanno riferimento. v0: `"5e-srd-5.1"`.

### `identity` (obbligatorio)
Anagrafica. `class` e `race` usano gli ID SRD minuscoli.

### `computed` (obbligatorio)
Il **nucleo vivo**. Mappa 1:1 con le colonne vere della tabella `characters`.
L'app garantisce che questi numeri siano internamente coerenti.
- `abilities` — i 6 score grezzi. I modificatori NON si esportano: si ricavano.
- `proficiency_bonus` — esportato per comodità anche se derivabile dal livello.
- `actions` — lista. Ogni voce: `name`, `srd_ref` (opzionale, ID SRD se l'azione
  viene da un'arma/spell SRD), `to_hit_mod`, `damage_dice` (forma `NdS+M`),
  `damage_type`, `description`. Vale per attacchi E incantesimi-che-tirano.

### `declared` (opzionale ma sempre presente come oggetto)
Il **guscio inerte**. L'app lo conserva e lo riesporta verbatim. NON lo valida,
NON lo interpreta. Può essere interamente vuoto: in v0 spesso lo sarà.

## Import: regole di robustezza

- `schema_version` non riconosciuta → rifiuto esplicito con messaggio.
- `computed` mancante o malformato → rifiuto (il nucleo è obbligatorio).
- `declared` mancante → si assume oggetto vuoto, import procede.
- Campi extra dentro `declared` → conservati così come sono.
- Campi extra dentro `computed` → ignorati con warning (non sono garantiti).
