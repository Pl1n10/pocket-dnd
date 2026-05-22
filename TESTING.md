# TESTING.md — pocket-dnd

> Mappa della suite di test. 154 test backend al passaggio di consegne Step 6.

## Eseguire i test

```
cd backend
python3 -m pytest tests/ -q          # tutta la suite
python3 -m pytest tests/test_dice.py -v   # un singolo file, verboso
```

`conftest.py` aggiunge `backend/` al path, così `from app.x import y` funziona.

## Filosofia

TDD: i test si scrivono PRIMA del codice. Ogni step nuovo comincia dai test.
La suite gira in meno di un secondo perché il grosso del codice è *puro* —
niente DB, niente rete, niente attese. I moduli che toccano DB o rete
(`characters`, `server`) si testano con SQLite in-memory e il TestClient di
Starlette: sempre deterministici, nessuna porta reale, nessun server vero.

## Mappa dei file di test

| File                  | Copre                  | Note |
|-----------------------|------------------------|------|
| `test_dice.py`        | motore dadi            | 38 test. RNG fittizio deterministico. |
| `test_rules.py`       | calcoli 5e             | 35 test. Tutto puro. |
| `test_characters.py`  | repository personaggi  | 28 test. DB SQLite in-memory per test. |
| `test_rooms.py`       | logica room + griglia  | 32 test. Pura, nessuna rete. |
| `test_server.py`      | REST + WebSocket       | 21 test. TestClient di Starlette. |

## Pattern utili già in uso

- **RNG iniettabile** (`test_dice.py`): `roll()` accetta un `rng`; nei test si
  passa un `FakeRandom` che restituisce valori predefiniti → tiri deterministici.
- **DB in-memory** (`test_characters.py`, `test_server.py`): ogni test ha la sua
  fixture con `:memory:` e schema fresco → isolamento totale fra test.
- **TestClient WebSocket** (`test_server.py`): `client.websocket_connect(...)`
  apre una socket sincrona e deterministica. Permette di testare il broadcast
  connettendo due client e verificando che l'evento di uno raggiunga l'altro.

## Cosa i test NON coprono (limiti noti — onestà)

- **Il frontend non ha un test runner.** Solo smoke check manuali della logica
  pura (es. `abilityMod`). Una resa visiva sbagliata o un bug di rendering React
  NON viene intercettato dai test — va visto a occhio nel browser.
- **La fisica della rete reale.** I test del WebSocket verificano il *protocollo*
  (connetti, broadcast, reconnect logico). NON verificano cosa succede con un
  telefono che va davvero in standby o un WiFi del pub instabile. Quello si
  collauda solo sul campo.
- **Il seed SRD.** `seed_srd.py` è stato verificato a mano sul dato reale ma non
  ha test automatici (importa dati esterni, poco adatto allo unit test).

## Quando aggiungere test

Ogni nuovo evento WebSocket → un test in `test_rooms.py` (se logica pura) o
`test_server.py` (se tocca il trasporto/repo). Ogni nuovo calcolo di regole →
`test_rules.py`. La regola: se è codice che può sbagliare un numero o uno stato,
ha un test prima di esistere.
