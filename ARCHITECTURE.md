# ARCHITECTURE.md — pocket-dnd

> Panoramica d'insieme dell'architettura. Per il *perché* di ogni scelta vedi
> `DECISIONS.md`; questo file descrive il *cosa* e il *come*.

## Quadro generale

```
   TELEFONO GIOCATORE          TELEFONO MASTER
   /player/:id                 /master
        │                           │
        │   WebSocket  /ws/session/{id}
        └─────────────┬─────────────┘
                      │
              ┌───────▼────────┐
              │  server.py     │   FastAPI: REST + WebSocket
              │  (un processo) │
              └───┬────────┬───┘
                  │        │
        ┌─────────▼──┐  ┌──▼──────────────┐
        │ RoomManager│  │ CharacterRepo   │
        │ (memoria)  │  │ (SQLite, file)  │
        │ stato live │  │ persistenza     │
        └────────────┘  └─────────────────┘
```

Un solo processo backend. Lo stato live (una sessione di gioco in corso) vive
in memoria nel `RoomManager`; la persistenza (i personaggi, che sopravvivono
alle sessioni) sta in un file SQLite. Vedi DECISIONS.md D4, D5.

## Backend — moduli

Tutto sotto `backend/app/`. Ordine di dipendenza dal basso verso l'alto:

| Modulo          | Responsabilità                                  | Dipende da |
|-----------------|--------------------------------------------------|------------|
| `dice.py`       | parsing e tiro dei dadi. Puro.                   | —          |
| `rules.py`      | calcoli 5e (modificatori, proficiency…). Puro.   | —          |
| `rooms.py`      | stato live di una sessione. Puro (no DB/rete).   | —          |
| `characters.py` | persistenza personaggi su SQLite + serializz.    | `rules`    |
| `server.py`     | app FastAPI: REST + WebSocket. Collega tutto.    | tutti      |
| `schema.sql`    | schema del database (non è codice Python).       | —          |

"Puro" = nessuna dipendenza da DB, rete o framework. Testabile in isolamento.
È il motivo per cui la suite gira in <1 secondo.

`main.py` (in `backend/`, non in `app/`) è solo l'entrypoint che avvia uvicorn.

## Il flusso di un tiro di dado (esempio completo)

Illustra come i pezzi collaborano. Un giocatore tappa "Spada lunga — danno":

1. `PlayerSheet` (frontend) chiama `sendEvent('roll_request', {formula:'1d8+3', …})`.
2. Il messaggio arriva al `server.py`, handler WebSocket `/ws/session/{id}`.
3. Il server riconosce `roll_request` e chiama `_resolve_roll()`, che usa
   `dice.py` per tirare davvero. Il dado lo tira il SERVER (D13).
4. Il risultato diventa un evento `roll`, applicato alla `Room` via `room.apply()`.
5. La `Room` lo registra nel `roll_feed` e incrementa `version`.
6. Il server fa `_broadcast()`: manda lo snapshot intero a TUTTI i device
   della sessione — il giocatore che ha tirato E il master.
7. Ogni frontend riceve il messaggio `snapshot` e sostituisce il proprio stato.

Nessun delta: si manda sempre lo stato completo (D5/AP6).

## Lo stato di una room — modello a token

Dallo Step 6, ogni pedina (PG o nemico) è un `_Token` con:
- `token_id` — stringa: `pc:<character_id>` per i PG, `enemy:<n>` per i nemici.
- `name`, `current_hp`, `max_hp`, `initiative`, `conditions`.
- `x`, `y` — posizione sulla griglia, oppure `None` se fuori griglia.
- `character_id` — valorizzato solo per i PG (i nemici non sono personaggi).

Lo `snapshot()` espone: `version`, `grid_size`, `participants` (i PG), `enemies`
(i nemici), `roll_feed`. Participants ed enemies sono ordinati per iniziativa
decrescente.

## Gli eventi WebSocket

Messaggi client → server: `{type, payload}`. Tipi gestiti:

| Tipo               | Effetto                                          | Intercettato da |
|--------------------|--------------------------------------------------|-----------------|
| `roll_request`     | il server tira, produce un evento `roll`         | server.py       |
| `roll`             | registra un tiro nel feed                        | rooms.py        |
| `hp_change`        | cambia gli HP di una pedina                      | rooms.py        |
| `condition_add`    | aggiunge una condizione (flag)                   | rooms.py        |
| `condition_remove` | rimuove una condizione                           | rooms.py        |
| `initiative_set`   | imposta l'iniziativa di una pedina               | rooms.py        |
| `move_token`       | sposta una pedina sulla griglia (o la toglie)    | rooms.py        |
| `enemy_add`        | aggiunge una pedina nemica                       | rooms.py        |
| `enemy_remove`     | rimuove una pedina nemica                        | rooms.py        |

Messaggi server → client: `{type:'snapshot', state:{…}}` (lo stato completo)
oppure `{type:'error', detail:'…'}` (errore, solo al mittente).

NB: la maggior parte degli eventi è gestita dentro `rooms.py` (logica pura).
Solo quelli che hanno bisogno di servizi esterni — finora solo `roll_request`,
che usa il motore dadi — vengono intercettati nel `server.py` prima di
raggiungere la room. Lo stesso pattern servirà per `add_participant` (Step 7),
che ha bisogno del CharacterRepo.

## Frontend — struttura

Tutto sotto `frontend/src/`. React + Vite, mobile-first.

| File               | Ruolo                                              |
|--------------------|----------------------------------------------------|
| `main.jsx`         | entry + routing (`/player/:id`, `/master`)         |
| `useSession.js`    | hook WebSocket: connessione, reconnect, snapshot   |
| `PlayerSheet.jsx`  | vista giocatore: scheda + griglia + azioni         |
| `Grid.jsx`         | componente griglia 8×8, riusato da player e master |
| `MasterConsole.jsx`| vista master: griglia + liste + feed               |
| `index.css`        | stile globale, palette "tavern-dark"               |

`useSession` è il cuore: ogni `snapshot` ricevuto sostituisce lo stato per
intero; se la socket cade, reconnect automatico con backoff e al ritorno il
server rimanda lo snapshot completo. Il client non ricostruisce mai nulla.

## Persistenza vs stato live — la distinzione

- **Persistente** (SQLite, sopravvive a tutto): i personaggi. Tabella
  `characters`. Crescono di livello, si esportano/importano.
- **Live** (memoria, dura quanto il processo): la sessione in corso. Chi è in
  sessione, gli HP correnti, le condizioni, le posizioni sulla griglia, il feed.
  Se il processo si riavvia, lo stato live si perde — ma i personaggi no.

In v0 va bene così: una one-shot dura una serata, il processo resta su. La
persistenza dello stato di sessione, se mai servisse, è un problema futuro.

## Deploy (previsto — Step 9)

- *Modalità casa*: container su un nodo del cluster, Cloudflare Tunnel.
- *Modalità pub*: stesso container sul laptop, `--host 0.0.0.0`, hotspot dal
  telefono. I device si collegano in LAN. Zero dipendenza da internet.
Il backend, in produzione, servirà anche i file statici del frontend buildato.
