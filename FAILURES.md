# FAILURES.md — pocket-dnd

> Approcci che sono stati provati e hanno fallito sul campo, con la causa e la
> soluzione adottata. Scopo: non ri-sbattere contro lo stesso muro.
> Il documento piu' sottovalutato del repo — tenerlo aggiornato.

---

## F1 — Connessione SQLite condivisa senza accorgimenti cross-thread

**Step.** 4 (server FastAPI + WebSocket).

**Cosa è stato provato.** `CharacterRepo` apriva la connessione SQLite con un
semplice `sqlite3.connect(db_path)` e la usava direttamente negli endpoint.

**Come è fallito.** I test del server (`test_server.py`) hanno sollevato
`sqlite3.ProgrammingError: SQLite objects created in a thread can only be used
in that same thread`. Causa: FastAPI esegue gli endpoint sincroni in un
threadpool — la connessione, creata nel thread di startup, veniva toccata da
thread diversi a ogni richiesta. NON era un artefatto dei test: sarebbe
successo identico sotto uvicorn in produzione.

**Soluzione adottata.** `check_same_thread=False` sulla connessione +
`threading.RLock` attorno a ogni operazione SQL. `RLock` e non `Lock` perche'
`update()` chiama internamente `get()`: con un `Lock` semplice il secondo
acquire darebbe deadlock. Vedi DECISIONS.md D12.

**Lezione.** Un test che gira gli endpoint in un threadpool (come fa
`TestClient`) e' piu' fedele alla produzione di un test che chiama il repo
direttamente. Il bug e' emerso solo perche' i test del trasporto esistevano.
