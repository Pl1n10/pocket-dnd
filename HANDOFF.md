# HANDOFF.md — pocket-dnd

> Documento di passaggio di consegne. Leggere DOPO `CLAUDE.md` e `STATE.md`.
> Scopo: permettere a una nuova sessione di riprendere lo Step 8 senza
> ricostruire il contesto. Quando lo Step 8 e' chiuso, questo file va riscritto
> con la mini-spec dello Step 9.

## Stato al passaggio di consegne

Step 1-7 completati. 172 test backend verdi. Frontend builda pulito.
**v0 giocabile end-to-end raggiunto.** Step 8-9 sono rifinitura e packaging.

## STEP 8 — Level-up assistito — mini-spec

Obiettivo: a fine sessione, il giocatore (o il master) tappa "Level up" e
l'app: aumenta il livello, ricalcola proficiency, aggiunge HP fissi secondo
formula (`level_up_hp_gain` in `rules.py`, gia' implementato), apre i campi
manuali per le scelte di build (D3 — l'app NON sceglie sottoclasse, feat,
incantesimi nuovi: lo decide il giocatore).

### Backend

1. **HP fissi vs HP a dado.** `level_up_hp_gain(hit_die, con_modifier)` usa
   gia' la regola opzionale 5e "valore medio del dado vita". Verificare che
   il personaggio abbia un campo `hit_die` (o derivarlo dalla classe — la
   classe e' in `extended`? in colonna `class`? controllare `characters.py`
   e lo schema). Se manca, va aggiunto: la mappatura classe -> dado vita
   sta nella SRD seedata; alternativa: campo `hit_die` esplicito sul PG.
2. **Endpoint REST `POST /api/characters/{id}/level-up`.** Payload opzionale
   con scelte manuali (es. nuovo incantesimo, feat) che vanno in `extended`.
   Il server:
   - incrementa `level` (con guardia max 20)
   - ricalcola `proficiency_bonus` (gia' fatto da `update()` quando passa il
     nuovo livello)
   - calcola HP guadagnati: `level_up_hp_gain(hit_die, ability_modifier(con))`
   - aggiorna `max_hp += gain` e `current_hp += gain` (curiamo anche il
     ferito? decisione: si — passare di livello al pub e' anche un "respiro
     lungo narrativo". Documentare in DECISIONS.md come D16 se confermato.)
   - merge dei campi `extended` passati nel payload
3. **Test in `test_characters.py` o un nuovo file** — almeno: livello sale,
   HP crescono della giusta quantita', proficiency cambia ai livelli giusti
   (5, 9, 13, 17), max 20 rispettato, extended si merge senza perdere campi
   pre-esistenti.

### Frontend

1. **PlayerSheet** — pulsante "Level up" in una sezione "Fine sessione" a
   bassa priorita' visiva (non e' nel flusso da pub). Dopo la POST, ri-fetch
   della scheda.
2. **MasterConsole** — opzionale: link/lista per fare level-up dei PG anche
   dal master. Probabilmente non necessario in v0 — il giocatore lo fa da
   solo dalla propria scheda.
3. **Form per le scelte manuali** — modal o expander con campi liberi (nuovo
   spell, feat, note). Tutto va in `extended` come testo opaco (D8). NON
   creare schermate strutturate per sottoclassi/feat/spell selection: e' il
   motore di regole che D2 vieta.

### Test

- Backend: come sopra.
- Frontend: smoke test (build pulito), prova manuale dal vivo.

## Convenzioni di lavoro consolidate (NON re-litigare)

- TDD: i test PRIMA del codice. Vale per ogni step.
- Ogni step finisce con: suite verde, `STATE.md` aggiornato, eventuali nuove
  voci in `DECISIONS.md`/`FAILURES.md`.
- Il dado lo tira sempre il SERVER (D13). Vale per ogni nuovo tiro.
- La `Room` resta PURA: niente DB, niente rete. Tutto cio' che ha bisogno del
  CharacterRepo si intercetta nel server (come `add_participant`,
  `roll_initiative`).
- Lingua: italiano per dialoghi e commenti, inglese per nomi di codice.
- `next_turn` (D15): non costruire mai una lista di ordine congelata, si
  ricalcola sempre dallo snapshot corrente.

## Come far girare il progetto (per verifica)

Backend:
```
cd backend
pip install -r requirements-dev.txt --break-system-packages
python3 -m pytest tests/ -q          # 172 test, devono essere verdi
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

## Piano residuo dopo lo Step 8

9. PWA + deploy duale — manifest, service worker, Docker, prova modalita' pub
   (laptop + hotspot). Il backend serve i file statici buildati del frontend.
