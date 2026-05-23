# DECISIONS.md — pocket-dnd

> Decisioni prese, con le alternative scartate e il perché.
> Formato: ogni voce è una decisione, NON un diario. Se una decisione viene
> ribaltata, non si cancella: si aggiunge una voce nuova che la supera.

---

## D1 — È un companion app, non un VTT

**Decisione.** Niente mappe, griglia, token, line-of-sight. Theatre-of-the-mind.

**Perché.** Il caso d'uso è la one-shot improvvisata al pub. Un VTT (Foundry,
Roll20) è pensato per campagne con setup di mappe. Qui il setup deve essere zero.

**Scartato.** Adottare/forkare un VTT esistente — risolverebbe il problema
sbagliato e porterebbe un peso enorme di feature inutili.

---

## D2 — L'app non è un motore di regole 5e

**Decisione.** L'app è una **calcolatrice di tiri + tracker di stato condiviso**.
Il DM resta l'arbitro.

L'app CONOSCE: i 6 attributi, il modificatore derivato, il proficiency bonus,
HP, CA, iniziativa, le condizioni come *flag* (senza applicarne gli effetti).

L'app CALCOLA: i tiri (tap su un'azione → `d20+mod`, con vantaggio/svantaggio;
tap su danno → tira i dadi giusti).

L'app NON conosce: copertura, reazioni, attacchi di opportunità,
condizioni-come-effetti-meccanici, incantesimi-come-logica. Gli incantesimi sono
voci di lista con descrizione testuale e (se tirano) un bottone-dado.

**Perché.** Ricostruire un motore di regole 5e completo è settimane di lavoro e
il risultato sarebbe una versione monca e frustrante di D&D Beyond. Tagliando il
motore si elimina l'80% del lavoro e il 100% di quel rischio.

**Livello di automazione richiesto dall'utente: "3 ma semplificato"** — cioè
combattimento + iniziativa + HP tracking automatici, ma con le semplificazioni
qui sopra. È facile complicare in seguito; è difficile semplificare dopo.

---

## D3 — Personaggi persistenti che crescono

**Decisione.** I personaggi sopravvivono alle sessioni e crescono di livello.
Tabella `characters` separata da `sessions`.

Il **level-up è assistito, non automatico**: a fine sessione si preme "Level up",
l'app aumenta proficiency/HP secondo formula e apre i campi da riempire a mano
(nuovo incantesimo, scelte di classe).

**Perché.** Le scelte di build sono decisioni del giocatore, non dell'app.
Automatizzarle del tutto rientrerebbe nell'antipattern "motore di regole".

---

## D4 — SQLite, non Postgres

**Decisione.** Persistenza su SQLite (un file).

**Perché.** I dati di una sessione D&D sono minuscoli (5 schede = pochi KB).
Il collo di bottiglia è il real-time, non i dati. SQLite è un file singolo →
lo stesso identico backend gira sul cluster `urano`/`gaia` E sul laptop al pub
senza modifiche. La persistenza viaggia col file.

**Scartato.** Postgres — costringerebbe ad avere un servizio separato attivo,
inutile per questo carico, e complicherebbe la "modalità pub" sul laptop.

---

## D5 — Real-time via WebSocket, stato live in memoria

**Decisione.** WebSocket per il sync. Lo stato live della sessione vive in un
`dict` in memoria del processo (`room_id → {connections, game_state}`).
SQLite si usa per la *persistenza* tra sessioni, non per lo stato live.

**Conseguenza obbligatoria.** I telefoni al pub vanno in standby di continuo e la
socket cade. Il client DEVE avere **reconnect automatico con re-fetch dello stato
completo** alla riconnessione. Stato autoritativo sul server; il client non si
fida dei delta, richiede lo stato intero quando si riconnette.

---

## D6 — Fonte dati: SRD 5.1 da 5e-bits/5e-database

**Decisione.** Si attinge dalla SRD 5.1 (CC-BY-4.0). Import una tantum dei JSON
del repo `5e-bits/5e-database` (licenza MIT sul formato) in tabelle SQLite di
sola lettura, via uno script di seed che gira una volta.

**Perché 5e-database** e non le alternative:
- *Open5e API*: include contenuti di terze parti (Kobold Press) → rumore.
- *nick-aschenbach/dnd-data*: ~5800 spell, gonfio di materiale non-SRD.
- *vorpalhex/srd_spells*: dichiaratamente non più aggiornato.
- *5e-database*: solo SRD, strutturato per endpoint, mantenuto, MIT. Giusto.

**Nota.** NON si tira su l'API di 5e-bits (è Node+MongoDB — fuori dal nostro
stack). Si prendono solo i file JSON e si importano. Nessuna dipendenza runtime.

**Obbligo legale.** Attribuzione SRD richiesta da CC-BY-4.0 → in README, nella
schermata "info" dell'app, e in `docs/ATTRIBUTION.md`.

---

## D7 — Conformità 5e: gratis; interoperabilità: adattatore, non vincolo

**Decisione.** Due intenzioni distinte, trattate diversamente:

- *Conformità alle regole 5e* — il personaggio "è" 5e per costruzione, perché
  la fonte è la SRD. Nessun lavoro extra.
- *Interoperabilità dei dati* — il personaggio si può esportare/importare via
  un **JSON proprietario, versionato, human-readable**, che riusa gli
  identificatori SRD (`"stealth"`, `"longsword"`, …). NON è il formato D&D Beyond.

**Scartato.** Compatibilità bit-a-bit col formato D&D Beyond / Foundry —
quel formato non è uno standard aperto specificato, cambia, ed è pieno di campi
(sottoclassi, feat, varianti) che D2 ci dice di non modellare. Inseguirlo
reintrodurrebbe il motore di regole dalla porta sul retro.

**Convertitori** verso altri tool = adattatori esterni *futuri*, fuori dal core.
NON v0.

**Statblock mostri**: conformi alla struttura SRD → compatibilità in ingresso
reale (si possono incollare creature da tooling esterno). Questo SÌ in v0,
costa poco perché i `monsters` arrivano già in quel formato da 5e-database.

---

## D8 — Modello = nucleo vivo + guscio inerte

**Decisione.** Il modello del personaggio NON è "una scheda 5e completa".
È un contenitore con due parti:

- **Nucleo vivo** — i campi che l'app calcola, tira e tiene sincronizzati:
  6 attributi, modificatori, HP, CA, proficiency, `actions` coi loro dadi,
  condizioni-flag. È ciò che la vista mobile mostra e di cui l'app è responsabile.
  → colonne vere nella tabella `characters` (ci si fanno query e calcoli).

- **Guscio inerte** — tutti gli altri campi di un personaggio 5e completo:
  background, sottoclasse, feat, tratti, equipaggiamento non-arma, spell come
  lista, note libere. L'app li **conserva ed esporta fedelmente, ma non li
  interpreta**. Sono testo opaco.
  → un'unica colonna JSON `extended` (NON sparpagliati in 20 colonne morte).

**La vista mobile proietta solo il nucleo.** La "scheda completa" è una
schermata secondaria a bassa priorità, fuori dal flusso da pub.

**Perché.** Permette l'export ricco senza ricomprare il motore di regole. Il
costo di una regola non è mostrarla, è mantenerla corretta: l'app garantisce la
correttezza solo di ciò che possiede (il nucleo).

**Onestà dell'export.** Il JSON di scambio marca la provenienza: blocco
`computed` (l'app garantisce) vs `declared` (inserito a mano, l'app riporta e
basta). Chi importa altrove sa di cosa fidarsi. Vedi `docs/FORMAT.md`.

**Avvertenza di prodotto.** "Modello completo pronto all'export" non significa
"export ricco". L'export è ricco solo quanto qualcuno ha compilato la schermata
secondaria. In v0 il guscio resterà probabilmente magro — scelta consapevole.

---

## D9 — Persistenza disaccoppiata dal formato di scambio

**Decisione.** Il modello interno (tabelle SQLite) e il formato di scambio
(JSON di `docs/FORMAT.md`) sono due cose separate, con un layer di
serializzazione dedicato (`export_character()` / `import_character()`).

**Perché.** Il giorno che servirà un convertitore verso Foundry o PDF, sarà uno
script esterno isolato che non tocca il core (vedi D7). La compatibilità è un
adattatore opzionale, non un vincolo che zavorra ogni decisione.

---

## D10 — La formula dadi è un valore parsato, non una stringa

**Decisione.** Una formula (`"2d6+3"`) si parsa UNA volta in un `DiceFormula`
(`rolls=[(2,6)], modifier=3`). Da lì in poi si lavora sulla struttura. Il roller
non vede mai stringhe.

**Perché.** Separa nettamente il *parsing* (fragile, deve gestire l'input sporco
dei JSON SRD) dal *rolling* (puro, deterministico con RNG iniettabile). Due
responsabilità, due funzioni, due gruppi di test. `normalize_srd_dice()` fa da
ponte: qualunque forma SRD → stringa canonica → `parse_formula()`.

---

## D11 — Vantaggio/svantaggio è un parametro del tiro, non parte della formula

**Decisione.** `roll(formula, advantage=...)`. Non si supportano notazioni tipo
`2d20kh1` dentro la formula. Adv/dis è applicabile SOLO a un singolo `1d20`;
su qualsiasi altra formula è un errore esplicito.

**Perché.** In 5e vantaggio/svantaggio tocca solo il d20 del tiro per colpire o
del tiro salvezza, ed è una decisione *del momento* del DM ("hai vantaggio"),
non una proprietà dell'azione. Tenerlo fuori dalla formula impedisce che adv/dis
finisca per errore su un tiro di danno.

---

## D12 — Connessione SQLite cross-thread con lock serializzante

**Decisione.** La connessione SQLite di `CharacterRepo` è aperta con
`check_same_thread=False` e ogni operazione SQL è protetta da un `threading.RLock`.

**Perché.** FastAPI esegue gli endpoint sincroni in un threadpool: la stessa
connessione viene toccata da thread diversi, e SQLite di default lo vieta. Le
opzioni erano: (a) una connessione per richiesta, (b) una connessione condivisa
+ lock. Scelta (b): il carico di pocket-dnd è minimo (una stanza, poche
scritture) e una connessione sola è più semplice da gestire del pooling. Il
lock è `RLock` e non `Lock` perché `update()` chiama `get()` — un `Lock`
semplice darebbe deadlock.

**Scoperto da.** Il TDD: i test del server hanno fatto emergere il
`ProgrammingError` di SQLite prima che il problema arrivasse in produzione.
Vedi `FAILURES.md`.

---

## D13 — Il dado lo tira il server, non il client

**Decisione.** Quando un giocatore tappa un'azione, il client manda un evento
`roll_request` con la *formula* (l'intento). Il server tira con `dice.py` e fa
broadcast del risultato come evento `roll`. Il client non tira mai.

**Perché.**
- *Risultato unico* — un solo tiro, visto identico da tutti i device. Se
  tirasse il client, due device potrebbero mostrare numeri diversi.
- *Feed del master gratis* — i tiri dei giocatori finiscono nel feed del
  master senza codice dedicato: sono già eventi `roll` come gli altri.
- *Anti-cheat di base* — il dado non passa mai dal telefono del giocatore.
- Il costo è un round-trip, ~5ms su LAN: impercettibile.

**Conseguenza tecnica.** Il server intercetta `roll_request` *prima* di
passarlo alla room: `_resolve_roll()` tira e produce un evento `roll` normale.
La `Room` resta pura e ignara dei dadi — `_on_roll` registra un tiro già
fatto. La logica dadi vive in un posto solo (`dice.py`).

---

## D14 — La griglia di combattimento è una superficie muta

**Decisione.** La consolle master (e la scheda giocatore) mostrano una griglia
8×8 su cui si posano le pedine. La griglia conserva solo *dove* sta ogni
pedina — una coppia `(x, y)` o `None` se fuori griglia.

La griglia NON conta le caselle, NON conosce le portate delle armi, NON calcola
distanze, NON segnala attacchi di opportunità.

**Perché.** È la versione digitale del feltro di cartone coi tappi di bottiglia.
Al tavolo nessuno misura col righello: si guardano i tappi e si conta a occhio.
La griglia di cartone non *fa* niente — è solo un reticolo, l'intelligenza è il
DM. Il rischio di replicarla in digitale è che il software si metta a fare il
conteggio: misure, portate, opportunità. Quel momento è quando si è ricomprato
Foundry e ribaltato D1. La regola che taglia il rischio: **griglia come
superficie muta sì, griglia come motore di regole no.** Il conteggio delle
caselle resta all'occhio del DM, come coi tappi.

**Scartato.** Una board "a zone semantiche" (mischia / tiro / retrovie) — più
astratta ma introduceva un modello di posizione che l'utente non ha chiesto;
i tappi stanno su una griglia, non in zone.

**Modello.** Ogni pedina è un `_Token` con un `token_id` stringa:
`pc:<character_id>` per i personaggi, `enemy:<n>` per i nemici. I PG sono i
partecipanti della room (identità e HP già lì); i nemici sono pedine generiche
che il master aggiunge al volo (nome + HP, nessuno statblock). Eventi nuovi:
`move_token`, `enemy_add`, `enemy_remove`. Il master muove tutte le pedine,
ogni giocatore solo la propria.

---

## D15 — `next_turn` ricalcola sempre l'ordine, non lo congela

**Decisione.** La `Room` espone un `active_token_id` (la pedina di turno) e un
evento `next_turn`. L'handler NON tiene una lista d'iniziativa congelata a
inizio combattimento: ad ogni chiamata ricalcola l'ordine dallo stato corrente
(`_initiative_order()`), trova la pedina attiva e passa alla successiva.

Se l'`active_token_id` non è più nell'ordine (pedina rimossa) o non era mai
stato impostato, il turno parte dal primo. Wrap-around dall'ultimo al primo.

**Perché.** Al pub succede di tutto: un nemico muore, un nuovo arriva, un
giocatore tira tardi l'iniziativa. Una lista congelata richiederebbe codice di
rebalance ad ogni mutazione (aggiunta, rimozione, cambio iniziativa) e
introdurrebbe stati incoerenti tra la lista e la realtà. Ricalcolare ogni volta
dallo snapshot è O(n) su n=10-15 pedine — costo trascurabile — ed elimina
intere classi di bug.

**Conseguenza.** Cambiare l'iniziativa di una pedina a metà combattimento è
sicuro: la posizione nel giro si sistema da sé al prossimo `next_turn`. Stessa
cosa per `enemy_add`/`enemy_remove`. La pedina attiva resta "logicamente" tale
finché non si chiama `next_turn`, anche se nel frattempo è stata rimossa —
l'inconsistenza si auto-sana al passaggio di turno.

---

## D16 — Il level-up cura completamente

**Decisione.** Quando un PG sale di livello, `current_hp` viene riportato a
`max_hp` (dopo che `max_hp` ha già incluso il gain del nuovo livello).

**Perché.** Il caso d'uso del level-up è "fine sessione al pub": il gruppo
chiude l'avventura, decide chi è salito di livello, e si saluta. In fiction
questo è anche il momento del riposo lungo narrativo — non avrebbe senso
ripartire la sessione successiva mezzi feriti perché l'app ha contabilizzato
solo il gain del dado vita. Tenere separati "level-up" e "cura completa"
costringerebbe il giocatore a un secondo tap su "ripara HP" che farebbe sempre,
ogni volta — l'esempio canonico di feature che non aggiunge informazione.

**Scartato.** "Solo +gain HP, niente cura" — più aderente a una lettura
stretta di 5e, ma scollegata dal nostro caso d'uso (D1 — companion per il pub,
non simulatore).

---

## D17 — Il dado vita si guarda nella SRD, non si replica sul PG

**Decisione.** Il level-up non duplica il `hit_die` sul personaggio: lo legge
al volo dalla tabella `srd_classes` via lookup sullo slug `class` del PG. Se
la classe non è in SRD, il level-up fallisce con un errore esplicito.

**Perché.** Il dado vita è una proprietà *della classe*, non del personaggio.
Duplicarlo su `characters` introdurrebbe un secondo posto in cui può andare
fuori sincronia col seed SRD. La nostra "regola d'oro" è "l'app conserva ed
esporta tutto, ma garantisce la correttezza solo del nucleo": la SRD è la
fonte autoritativa di ciò che è SRD, e il level-up — che usa una regola SRD —
deve attingere lì.

**Conseguenza.** PG homebrew (classe inventata, non nella SRD) non possono
fare level-up assistito. Coerente con D2: l'app non inventa, il DM fa a mano
e aggiorna i campi nel guscio `extended`.
