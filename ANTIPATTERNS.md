# ANTIPATTERNS.md — pocket-dnd

> Cose già valutate e scartate. Rileggere prima di "avere una bella idea".
> Se un antipattern viene riproposto e ri-respinto sul campo, annotarlo in
> `FAILURES.md` con il contesto concreto.

---

## AP1 — Ricostruire il motore di regole 5e completo

L'app NON applica le regole. Niente effetti meccanici delle condizioni, niente
risoluzione di copertura/reazioni/opportunità, niente logica degli incantesimi.
Il risultato sarebbe un D&D Beyond monco e frustrante. Il DM arbitra. Vedi D2.

**Variante subdola.** "Il modello completo, solo non lo mostro" → se l'app
*mantiene coerenti e validati* i campi del guscio, ha ricomprato il motore dalla
porta sul retro. Il guscio è **inerte**: conservato ed esportato, mai
interpretato. Vedi D8.

---

## AP2 — Compatibilità bit-a-bit col formato D&D Beyond / Foundry

Non è uno standard aperto specificato, cambia, ed è pieno di campi che D2 dice di
non modellare. Inseguirlo = reintrodurre AP1. Il formato di scambio è un JSON
nostro, versionato, che riusa gli ID SRD. I convertitori sono adattatori esterni
futuri. Vedi D7.

---

## AP3 — Un LLM nel loop critico di gioco

Tentazione concreta (c'è Ollama sul 5070, c'è devbox-bridge). Ma il valore
dell'app è *togliere attrito*: un LLM aggiunge latenza e imprevedibilità proprio
mentre serve scorrere veloce al tavolo. Un eventuale "DM assistant" (nomi di
taverne, PNG al volo) è una feature on-demand di una v0.4+, MAI nel loop critico.

---

## AP4 — Sync automatico cluster ↔ laptop in v0

La persistenza è un file SQLite. "Modalità pub" lo modifica sul laptop;
"modalità casa" sul cluster. In v0 il sync è banale: è un file, lo si copia.
Automatizzarlo ora è un problema da non risolvere — risolverlo dopo, se davvero
diventa fastidioso.

---

## AP5 — Postgres / servizi esterni "perché un domani"

SQLite è la scelta giusta per questo carico (D4). Niente Postgres, niente
MongoDB, niente Redis "per scalare". Il carico massimo realistico è ~6 device in
una stanza. Lo stato live in memoria basta e avanza (D5).

---

## AP6 — Fidarsi dei delta WebSocket

I telefoni vanno in standby, la socket cade in continuazione. Il client non deve
MAI assumere di aver ricevuto tutti gli aggiornamenti. Stato autoritativo sul
server; alla riconnessione il client ri-scarica lo stato intero. Vedi D5.

---

## AP7 — Sparpagliare il guscio inerte in colonne SQL

I campi del guscio (background, feat, tratti, note…) vanno in UN'unica colonna
JSON `extended`. Venti colonne nullable sarebbero peso morto nello schema su cui
non si fanno mai query. Vedi D8.

---

## AP8 — Desktop-first ristretto al mobile

"Tutti col proprio telefone" → il frontend è mobile-first *vero*: ~380px,
verticale, tap target grossi (si gioca al buio, mani occupate). Non è un layout
desktop schiacciato. Vedi CLAUDE.md.

---

## AP9 — La griglia che diventa un motore di regole

La griglia di combattimento (Step 6, D14) è una *superficie muta*: conserva
dove sta ogni pedina, nient'altro. La tentazione, una volta disegnato un
reticolo, è farlo "lavorare": contare le caselle fra due pedine, conoscere le
portate delle armi, calcolare le distanze, segnalare gli attacchi di
opportunità. Ognuna di queste, presa da sola, sembra una piccola comodità.

Insieme sono Foundry — e ribaltano D1. Il momento in cui il software conta le
caselle è il momento in cui ha smesso di essere "il feltro coi tappi" ed è
diventato un VTT con un motore di regole (vedi anche AP1). Al tavolo nessuno
misura col righello: la griglia di cartone non fa nulla, il conteggio è l'occhio
del DM. La versione digitale deve restare altrettanto stupida.

Regola operativa: la griglia può *mostrare* posizioni, può *evidenziare* la
pedina di turno. Non può *misurare* né *dedurre* conseguenze di regole.
