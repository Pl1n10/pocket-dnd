# HANDOFF.md — pocket-dnd

> Documento di passaggio di consegne. Leggere DOPO `CLAUDE.md` e `STATE.md`.
> Scopo: permettere a una nuova sessione di riprendere lo Step 7 senza
> ricostruire il contesto. Quando lo Step 7 è chiuso, questo file va riscritto
> con la mini-spec dello Step 8.

## Stato al passaggio di consegne

Step 1-6 completati. 154 test backend verdi. Frontend builda pulito.
Il prodotto NON è ancora giocabile end-to-end: manca lo Step 7 (vedi sotto)
e soprattutto manca il modo di mettere gli eroi in sessione (vedi "Debito").

## DEBITO TECNICO da saldare PRIMA o DURANTE lo Step 7

**Manca l'evento `add_participant` sul WebSocket.**
La `Room` ha il metodo Python `add_participant(character_id, name, current_hp,
max_hp)` ma NON è esposto come evento WebSocket. Conseguenza: una room nasce
vuota di personaggi e non c'è modo, dal frontend, di metterceli.
Nei test end-to-end finora questo è stato aggirato usando solo nemici.

Questo va saldato all'inizio dello Step 7, perché l'iniziativa non ha senso
finché i PG non sono in sessione. Vedi il punto 1 del piano qui sotto.

## STEP 7 — Iniziativa & turni — mini-spec

Obiettivo: gestire l'ordine di combattimento. Le pedine si ordinano per
iniziativa (lo snapshot già lo fa); manca evidenziare DI CHI È IL TURNO e
far avanzare il turno. Più il debito `add_participant`.

### 1. Evento `add_participant` (debito — farlo per primo)
- Nuovo handler nel server (NON in `rooms.py`: serve leggere il CharacterRepo).
- Payload: `{character_id}`. Il server legge il personaggio dal repo
  (`repo.get(character_id)`), ne ricava nome/current_hp/max_hp, e chiama
  `room.add_participant(...)`.
- Va intercettato nel server come si fa già con `roll_request` — perché ha
  bisogno del repo, che la `Room` pura non ha.
- Errore se il personaggio non esiste → messaggio d'errore al mittente,
  socket viva (stesso pattern di `roll_request` con formula malformata).
- Test: aggiungere a `test_server.py` una classe `TestAddParticipant`.

### 2. Tiro d'iniziativa
- L'iniziativa è `1d20 + mod_DEX`. Il modificatore sta in `rules.py`
  (`ability_modifier`). Il tiro lo fa il SERVER (coerente con D13).
- Opzione A: un evento `initiative_roll` per singolo personaggio.
- Opzione B: un evento `roll_all_initiative` che tira per tutti i partecipanti
  in un colpo (più comodo per il master a inizio combattimento).
  → Suggerito: B, con A come fallback manuale. Decidere a inizio step.
- L'evento `initiative_set` esiste già in `rooms.py` e funziona: imposta
  l'iniziativa di una pedina. Il tiro automatico ci si appoggia.
- Lo snapshot ordina GIÀ participants ed enemies per iniziativa decrescente.

### 3. Turno corrente
- La `Room` deve sapere DI CHI È IL TURNO. Proposta: un campo
  `_active_token_id` + nello snapshot `active_token_id`.
- Evento nuovo `next_turn`: avanza al prossimo nell'ordine d'iniziativa;
  dall'ultimo torna al primo (il giro successivo).
- Caso limite da gestire: cosa succede se la pedina di turno viene rimossa,
  o se cambia l'iniziativa a metà combattimento. Decisione suggerita: `next_turn`
  ricalcola sempre l'ordine dallo snapshot corrente, non tiene una lista
  congelata. Documentare la scelta come nuova voce in DECISIONS.md.
- I nemici sono nell'ordine d'iniziativa quanto i PG: il turno gira su TUTTE
  le pedine, non solo sui PG.

### 4. Frontend
- `MasterConsole`: evidenziare la pedina di turno (bordo/sfondo distinto sia
  nella lista sia sulla griglia), pulsante "Turno successivo".
- `Grid.jsx`: accetta una prop `activeId` e disegna quella pedina evidenziata
  (diverso dalla selezione: la selezione è oro, il turno potrebbe essere un
  alone o un anello — scegliere qualcosa che non si confonda).
- `PlayerSheet`: mostrare al giocatore se è il suo turno (è il momento "tocca
  a te" — va reso evidente).
- Pulsante "Tira iniziativa per tutti" sulla consolle master.

### 5. Test
- `test_rooms.py`: classe `TestTurnOrder` — next_turn avanza, wrappa, gestisce
  rimozione della pedina attiva.
- `test_server.py`: `TestAddParticipant`, `TestInitiative`.
- Frontend: smoke check come negli step precedenti (non c'è un test runner JS).

## Convenzioni di lavoro consolidate (NON re-litigare)

- TDD: i test PRIMA del codice. Vale per ogni step.
- Ogni step finisce con: suite verde, `STATE.md` aggiornato, eventuali nuove
  voci in `DECISIONS.md`/`FAILURES.md`, tarball in /mnt/user-data/outputs.
- Il tarball NON include `frontend/node_modules` (si rigenera con `npm install`).
- Il dado lo tira sempre il SERVER (D13). Vale anche per l'iniziativa.
- La `Room` resta PURA: niente DB, niente rete. Tutto ciò che ha bisogno del
  CharacterRepo (come `add_participant`) si intercetta nel server.
- Lingua: italiano per dialoghi e commenti, inglese per nomi di codice.

## Come far girare il progetto (per verifica)

Backend:
```
cd backend
pip install -r requirements-dev.txt --break-system-packages
python3 -m pytest tests/ -q          # 154 test, devono essere verdi
python3 main.py --db pocket-dnd.db   # avvia il server su :8000
```

Frontend:
```
cd frontend
npm install
npm run dev      # :5173, proxa /api e /ws verso :8000
npm run build    # build di produzione in dist/
```

Seed dei dati SRD (una tantum):
```
cd backend && python3 scripts/seed_srd.py pocket-dnd.db
```

## Piano residuo dopo lo Step 7

8. Level-up assistito — bottone, formula HP (`level_up_hp_gain` esiste già in
   rules.py), campi manuali per le scelte di build.
9. PWA + deploy duale — manifest, service worker, Docker, prova modalità pub
   (laptop + hotspot). Il backend serve i file statici buildati del frontend.

v0 giocabile davvero = fine Step 7. Gli step 8-9 sono rifinitura e packaging.
