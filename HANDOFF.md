# HANDOFF.md — pocket-dnd

> Documento di passaggio di consegne. Leggere DOPO `CLAUDE.md` e `STATE.md`.

## Stato al passaggio di consegne

**v0 completato.** Tutti i 9 step del piano chiusi. 192 test backend verdi.
Frontend builda pulito + PWA installabile. Container Docker buildato e
smoke-testato dal vivo (un processo, una porta, SPA + REST + WS).

Il prossimo passo NON e' uno step di sviluppo, e' un **deploy reale e un
playtest al tavolo**. Vedi sotto.

## Come deployare

Tutti i dettagli operativi in `docs/DEPLOY.md`. In sintesi:

```bash
docker compose up -d --build
docker compose exec pocket-dnd python3 scripts/seed_srd.py /data/pocket-dnd.db
# apri http://<ip>:8000
```

Modalita' pub: gira sul laptop, hotspot dal telefono, i device in LAN.
Modalita' casa: Cloudflare Tunnel verso sottodominio (vedi DEPLOY.md).

## Cosa serve dopo il primo playtest

Note da raccogliere durante il primo uso reale, *prima* di scrivere altro
codice:

1. **Frizioni di interazione al pub.** Tap target troppo piccoli, contrasto
   in penombra, pulsanti che spariscono sotto la tastiera del telefono,
   conditions che servirebbero come tap rapido e oggi non ci sono.
2. **Cose che il DM ha dovuto tracciare a mano.** Quel particolare campo
   che manca, quella nota che e' finita su un foglietto. Sono i candidati
   per estendere il "nucleo vivo" (con cautela — vedi D8).
3. **Bug di reconnect.** I telefoni vanno in standby di continuo: c'e' uno
   stato che si perde davvero? Lo snapshot intero al reconnect dovrebbe
   coprire tutto, ma vale verificarlo dal vivo.
4. **Performance percepita.** Tempo di tap -> tiro mostrato a tutti i
   device. Su LAN dovrebbe essere impercettibile; su Cloudflare Tunnel
   c'e' un round-trip in piu' che potrebbe valere la pena misurare.

## Idee non urgenti (v1+, da rivalutare dopo il playtest)

- **Multi-sessione.** Oggi tutti vanno sulla sessione `1`. Schermata di
  scelta/creazione sessione, route che includano `session_id`.
- **Conditions toggle rapido.** Click su una condizione per add/remove
  invece che solo lettura.
- **Vantaggio/svantaggio nel UI.** Il backend gia' lo supporta (D11), il
  PlayerSheet ancora no: serve un toggle prima del tap-to-roll.
- **Import/export di un PG dalla UI.** Il backend ha l'endpoint
  (FORMAT.md / D9), manca il pulsante.
- **Statblock mostri sulla consolle.** D7: la SRD ha 334 mostri seedati,
  ma il master oggi aggiunge solo "Goblin + HP". Potrebbe scegliere da
  catalogo SRD ed avere HP/AC/attacchi pre-compilati.
- **Riposo breve/lungo come azioni esplicite.** Oggi la cura passa solo
  dal level-up (D16) o dal +/- manuale. Un "riposo lungo" che azzera
  current_hp -> max_hp per tutti sarebbe utile.

## Convenzioni di lavoro consolidate (NON re-litigare)

- TDD: i test PRIMA del codice. Vale per ogni step.
- Ogni step finisce con: suite verde, `STATE.md` aggiornato, eventuali
  nuove voci in `DECISIONS.md`/`FAILURES.md`.
- Il dado lo tira sempre il SERVER (D13). Vale per ogni nuovo tiro.
- La `Room` resta PURA: niente DB, niente rete. Tutto cio' che ha bisogno
  del CharacterRepo si intercetta nel server (come `add_participant`,
  `roll_initiative`).
- Lingua: italiano per dialoghi e commenti, inglese per nomi di codice.
- `next_turn` (D15): non costruire mai una lista di ordine congelata, si
  ricalcola sempre dallo snapshot corrente.
- Il dado vita si guarda nella SRD, non si replica sul PG (D17).

## Come far girare il progetto (per verifica)

Backend (dev):
```
cd backend
pip install -r requirements-dev.txt --break-system-packages
python3 -m pytest tests/ -q          # 192 test, devono essere verdi
python3 main.py --db pocket-dnd.db   # avvia il server su :8000 (solo API)
```

Frontend (dev):
```
cd frontend
npm install
npm run dev      # :5173, proxa /api e /ws verso :8000
npm run build    # build di produzione in dist/
```

Container (prod):
```
docker compose up -d --build
docker compose exec pocket-dnd python3 scripts/seed_srd.py /data/pocket-dnd.db
# http://localhost:8000
```

Seed dei dati SRD (dev, una tantum):
```
cd backend && python3 scripts/seed_srd.py pocket-dnd.db
```
