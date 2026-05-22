# pocket-dnd

Companion app per D&D 5e one-shot al tavolo — pensato per la partita
improvvisata al pub. Schede personaggio sul telefono di ciascuno, consolle
per il master con griglia di combattimento, dadi e stato sincronizzati in
tempo reale.

**Non è un VTT.** La griglia è il "feltro coi tappi di bottiglia": mostra chi
è dove, non misura né arbitra. Il master resta l'arbitro.

## Stato

In sviluppo. Step 6/9 completati (backend completo, frontend con scheda
giocatore e consolle master). 154 test backend verdi.
Per lo stato corrente vedi `STATE.md`; per riprendere lo sviluppo `HANDOFF.md`.

## Avvio rapido

Backend:
```bash
cd backend
pip install -r requirements-dev.txt --break-system-packages
python3 scripts/seed_srd.py pocket-dnd.db   # dati SRD, una tantum
python3 main.py --db pocket-dnd.db          # server su :8000
```

Frontend:
```bash
cd frontend
npm install
npm run dev          # :5173, in sviluppo proxa /api e /ws verso :8000
```

Test:
```bash
cd backend && python3 -m pytest tests/ -q
```

## Documentazione

Da leggere in quest'ordine:
- `CLAUDE.md` — cos'è il progetto, come è fatto.
- `STATE.md` — stato corrente del lavoro.
- `HANDOFF.md` — mini-spec per riprendere lo sviluppo.
- `ARCHITECTURE.md` — panoramica dell'architettura.
- `DECISIONS.md` — decisioni architetturali, con le alternative scartate.
- `CONTEXT.md` — vocabolario D&D e mappatura SRD → modello dati.
- `ANTIPATTERNS.md` — cosa non fare.
- `FAILURES.md` — approcci falliti sul campo.
- `TESTING.md` — mappa della suite di test.
- `docs/FORMAT.md` — formato JSON di scambio personaggio.
- `docs/ATTRIBUTION.md` — attribuzione SRD.

## Licenze e attribuzione

This work includes material taken from the System Reference Document 5.1
("SRD 5.1") by Wizards of the Coast LLC and available at
https://dnd.wizards.com/resources/systems-reference-document. The SRD 5.1 is
licensed under the Creative Commons Attribution 4.0 International License,
available at https://creativecommons.org/licenses/by/4.0/legalcode.

I dati 5e sono importati da [5e-bits/5e-database](https://github.com/5e-bits/5e-database)
(licenza MIT sul formato). Vedi `docs/ATTRIBUTION.md`.
