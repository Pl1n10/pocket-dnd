# STATE.md — pocket-dnd

> Stato temporale del lavoro. Aggiornare a ogni sessione.
> Per le decisioni stabili vedi `DECISIONS.md`; questo file e' volatile.

## Ultimo aggiornamento
2026-05-22 — fine Step 6.

## Dove siamo

**Step 1 — Scaffolding + schema + seed SRD: COMPLETATO.**
- Struttura repo, documenti di metodo (`CLAUDE.md`, `DECISIONS.md` D1-D11,
  `CONTEXT.md`, `ANTIPATTERNS.md`, `docs/`).
- `schema.sql` — 11 tabelle, verificato su SQLite vuoto.
- `seed_srd.py` — verificato sul dato reale: 18 skill, 37 armi, 15 condizioni,
  319 spell, 12 classi, 334 mostri. JSON SRD in `backend/data/5e-database/`.

**Step 2 — Motore dadi: COMPLETATO.**
- `backend/app/dice.py` — parser + roller puri, nessun DB/rete.
  `parse_formula` → `DiceFormula`; `normalize_srd_dice`; `roll` → `RollResult`;
  `Advantage` come parametro del tiro, valido solo su 1d20.
- `backend/tests/test_dice.py` — 38 test verdi.

**Step 3 — CRUD personaggi: COMPLETATO.**
- `backend/app/rules.py` — calcoli 5e puri: `ability_modifier`,
  `proficiency_bonus`, `skill_bonus`, `level_up_hp_gain`. 35 test verdi.
- `backend/app/characters.py` — `CharacterRepo`: CRUD su SQLite + serializzazione.
  - nucleo come colonne, guscio in `extended` JSON (D8).
  - proficiency ricalcolata a ogni write (mai presa a fiducia).
  - `export_character()` / `import_character()` conformi a `docs/FORMAT.md`.
  - import robusto: schema sconosciuto / `computed` mancante → rifiuto;
    `declared` mancante → `{}`; campo extra in `computed` → ignorato e procede;
    campo extra in `declared` → conservato.
  - 28 test verdi.
- Round-trip export/import verificato dal vivo.
- **Suite totale: 101 test verdi.**

**Step 4 — WebSocket + room: COMPLETATO.**
- `backend/app/rooms.py` — logica room pura (no rete): `Room` (fonte
  autoritativa, snapshot versionato), `RoomManager`, applicazione eventi
  (hp_change, condition_add/remove, initiative_set, roll). 22 test verdi.
- `backend/app/server.py` — app FastAPI: REST personaggi + WebSocket
  `/ws/session/{id}`. Ogni evento applicato → ri-broadcast dello snapshot
  intero a tutti i device (no delta — reconnect banale, D5/AP6). 23 test verdi.
- `backend/main.py` — entrypoint; `--host 0.0.0.0` per la modalita' pub.
- Bug threading SQLite scoperto dal TDD e risolto (D12, FAILURES.md F1).
- Server verificato dal vivo sotto uvicorn: health + CRUD ok.
- **Suite totale: 139 test verdi.**

**Step 5 — Frontend scheda giocatore: COMPLETATO.**
- Backend: nuovo evento `roll_request` — il client manda l'intento, il server
  tira con dice.py (D13). `_resolve_roll()` in server.py. 5 test verdi nuovi.
- `frontend/` — scaffolding Vite + React, mobile-first, palette "tavern-dark".
  - `useSession.js` — hook WebSocket con reconnect automatico + backoff;
    ogni snapshot sostituisce lo stato intero (D5/AP6).
  - `PlayerSheet.jsx` — scheda `/player/:id`: HP, attributi, azioni tap-to-roll,
    feed dei tiri. Carica la scheda via REST, stato live via WebSocket.
  - `index.css` — stile globale tavern-dark.
- Build di produzione verificata (vite build pulito).
- Flusso end-to-end verificato dal vivo: roll_request -> server tira ->
  risultato nel feed, con vantaggio.
- **Suite backend: 144 test verdi.**

**Step 6 — Consolle master + griglia: COMPLETATO.**
- Backend: `rooms.py` riscritto sul modello a TOKEN (`_Token` con `token_id`
  stringa: `pc:<id>` per i PG, `enemy:<n>` per i nemici). Eventi nuovi:
  `move_token`, `enemy_add`, `enemy_remove`. `hp_change`/condizioni ora
  accettano sia `token_id` sia `character_id` (retro-compatibile).
  Snapshot espone `grid_size`, `participants`, `enemies`. 32 test room verdi.
- `frontend/src/Grid.jsx` — griglia 8x8 muta (D14), pedine a iniziale puntata,
  riusabile da master e giocatore.
- `frontend/src/MasterConsole.jsx` — consolle `/master`: griglia, lista eroi
  e nemici con HP +/- modificabili, aggiunta/rimozione nemici, feed tiri.
- `PlayerSheet` — aggiunta la griglia (il giocatore muove solo la propria pedina).
- Build di produzione verificata. Flusso end-to-end verificato dal vivo:
  enemy_add -> move_token -> hp_change -> rimozione, broadcast master/giocatore.
- **Suite backend: 154 test verdi.**

## DEBITO TECNICO aperto

**Manca l'evento `add_participant` sul WebSocket.** La `Room` ha il metodo
Python ma non è esposto come evento, quindi una room nasce senza PG e dal
frontend non c'è modo di aggiungerli. Va saldato all'inizio dello Step 7
(l'iniziativa non ha senso senza PG in sessione). Dettagli completi nel
`HANDOFF.md`, sezione "DEBITO TECNICO".

## NOTA DI CHIUSURA SESSIONE (2026-05-22)

Sessione conclusa per esaurimento contesto a fine Step 6. Tutto il lavoro è
documentato. Per riprendere: leggere `HANDOFF.md` — contiene la mini-spec
completa dello Step 7 (iniziativa & turni) e il debito da saldare.
Nessun codice lasciato a metà; la suite è verde, il frontend builda.


## Prossimo: Step 7 — Iniziativa & turni

## Piano completo (riferimento)

1. ✅ Scaffolding + schema + seed SRD
2. ✅ Motore dadi
3. ✅ CRUD personaggi (+ import/export JSON di FORMAT.md)
4. ✅ WebSocket + room (reconnect, stato autoritativo)
5. ✅ Frontend scheda giocatore (mobile, tap-to-roll)
6. ✅ Frontend consolle master (PG, HP, griglia, feed live)
7. ⬜ Iniziativa & turni
8. ⬜ Level-up assistito
9. ⬜ PWA + deploy duale

v0 giocabile davvero = fine Step 7.

## Note aperte / da decidere più avanti

- I file JSON SRD (~2.3 MB) sono committati in `backend/data/`: rendono il setup
  offline-friendly. Alternativa: scaricarli via Makefile. Per ora committati.
- SRD 5.1 (set 2014) vs 5.2 (set 2024): si parte con 5.1.
