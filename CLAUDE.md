# CLAUDE.md — pocket-dnd

> Documento di orientamento per qualsiasi sessione (umana o agente) che mette mano al repo.
> Leggere questo per primo, poi `DECISIONS.md` e `STATE.md`.

## Cos'è

`pocket-dnd` è un **companion app** per giocare a D&D 5e one-shot al tavolo
(tipicamente: al pub, con gli amici, scenario improvvisato).

NON è un VTT. Niente mappe, niente griglia, niente token, niente line-of-sight.
Si gioca *theatre-of-the-mind*. L'app serve a togliere attrito, non ad arbitrare.

## A cosa serve davvero

Il punto debole della one-shot improvvisata non è il dado — quello funziona già.
È che lo *stato* (HP, condizioni, iniziativa, da dove viene quel +2) vive solo
nella testa del DM e su foglietti. `pocket-dnd` tiene quello stato **condiviso,
visibile e sincronizzato in tempo reale**.

## Le tre viste

- **Consolle Master** (`/master`): vista d'insieme — tutti i PG, HP, condizioni,
  ordine di iniziativa, feed live dei tiri.
- **Scheda Giocatore** (`/player/:id`): ognuno vede solo la propria scheda,
  tira i dadi da lì (tap su un'azione → tira già i dadi giusti).
- Il tiro di un giocatore appare nel feed del master in tempo reale.

## Come si gioca fisicamente

Tutti col proprio telefono. Quindi: **frontend mobile-first vero** (~380px,
verticale, tap target grossi — si gioca al buio di un pub).

## Stack

- **Backend**: FastAPI, processo singolo. WebSocket per il real-time.
  Stato live in memoria (dict per room). SQLite per la persistenza.
- **Frontend**: React + Vite, PWA, mobile-first.
- **Deploy duale**:
  - *Modalità casa*: container su `urano`/`gaia`, Cloudflare Tunnel → sottodominio.
  - *Modalità pub*: stesso container sul laptop, hotspot dal telefono,
    i device si collegano in LAN locale. Zero dipendenza da internet.

SQLite (non Postgres) è una scelta deliberata: un file solo → lo stesso identico
backend gira sul cluster e sul laptop senza modifiche. Vedi `DECISIONS.md`.

## Regola d'oro del progetto

> L'app può **salvare ed esportare** qualsiasi campo di un personaggio.
> Può **calcolare e garantire la correttezza** solo del *nucleo vivo*.
> Tutto il resto è guscio inerte: conservato, esportato, mai interpretato.

L'app NON è un motore di regole 5e. È una calcolatrice di tiri + un tracker di
stato condiviso. Il DM resta l'arbitro. Vedi `DECISIONS.md` e `ANTIPATTERNS.md`.

## Fonte dati 5e

SRD 5.1 (Creative Commons CC-BY-4.0), importata una tantum da `5e-bits/5e-database`
(MIT). Vedi `CONTEXT.md` per la mappatura SRD → modello e `docs/ATTRIBUTION.md`
per il testo di attribuzione obbligatorio.

## Documenti del repo

Da leggere in quest'ordine per orientarsi:
- `CLAUDE.md` — questo file: cos'è il progetto, come è fatto.
- `STATE.md` — stato corrente del lavoro (volatile, aggiornato a ogni sessione).
- `HANDOFF.md` — mini-spec del prossimo step, per riprendere da dove si è lasciato.
- `ARCHITECTURE.md` — panoramica d'insieme dell'architettura.
- `DECISIONS.md` — decisioni architetturali e di dominio, con alternative scartate.
- `CONTEXT.md` — vocabolario D&D e mappatura SRD → modello dati.
- `ANTIPATTERNS.md` — cosa NON fare e perché.
- `FAILURES.md` — approcci falliti sul campo, con causa e rimedio.
- `TESTING.md` — mappa della suite di test.
- `docs/FORMAT.md` — contratto del JSON di scambio personaggio.
- `docs/ATTRIBUTION.md` — attribuzione SRD obbligatoria.
