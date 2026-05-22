# CONTEXT.md — pocket-dnd

> Vocabolario di dominio D&D 5e e mappatura esatta tra la fonte SRD e il
> modello dati di pocket-dnd. Utile per chiunque rimetta mano al repo tra mesi.

## Vocabolario minimo D&D 5e

- **Attributo / Ability score** — uno dei sei: Forza (STR), Destrezza (DEX),
  Costituzione (CON), Intelligenza (INT), Saggezza (WIS), Carisma (CHA).
  Valore grezzo, tipicamente 3–20.
- **Modificatore** — derivato dall'attributo: `floor((score - 10) / 2)`.
  È quello che si somma ai tiri. NON si salva, si calcola.
- **Proficiency bonus** — bonus da competenza, dipende dal livello del PG.
  Liv 1–4 → +2, 5–8 → +3, 9–12 → +4, 13–16 → +5, 17–20 → +6.
- **Skill** — abilità (Furtività, Persuasione…). Ognuna è legata a un attributo.
  Se il PG è "competente" in una skill, il tiro è `d20 + mod_attributo + proficiency`.
- **CA / Armor Class** — il numero da superare per colpire il PG.
- **HP / Hit Points** — punti ferita. `max_hp` (persistente) vs `current_hp`.
- **Iniziativa** — tiro `d20 + mod_DEX` a inizio combattimento; ordina i turni.
- **Tiro per colpire / to-hit** — `d20 + bonus`. Confrontato con la CA del bersaglio.
- **Tiro di danno** — dadi specifici dell'arma/incantesimo, es. spada lunga `1d8`.
- **Tiro salvezza / saving throw** — `d20 + mod` per resistere a un effetto.
- **Condizione** — stato (avvelenato, prono, accecato…). In pocket-dnd è un
  semplice FLAG: l'app la mostra, NON ne applica gli effetti meccanici (D2).
- **Vantaggio / Svantaggio** — si tirano due d20, si tiene il più alto / più basso.
- **Dado vita / Hit Die** — il dado per gli HP guadagnati al level-up,
  dipende dalla classe (Barbaro d12, Guerriero d10, Chierico d8, Mago d6…).

## Notazione dadi

Forma canonica interna: `NdS+M` (es. `2d6+3`, `1d20`, `1d8-1`).
Lo step "motore dadi" deve normalizzare verso questa forma qualsiasi input,
inclusa la forma strutturata `{dice_count, dice_value}` dei JSON SRD.

## Fonte: 5e-bits/5e-database

Repo: https://github.com/5e-bits/5e-database (licenza MIT sul formato; il
contenuto è SRD 5.1 CC-BY-4.0). I JSON sono strutturati per "endpoint".

NON si usa l'API Node+MongoDB di 5e-bits. Si scaricano solo i JSON e si importano
una tantum in tabelle SQLite di sola lettura via `scripts/seed_srd.py`.

## Mappatura SRD → modello pocket-dnd

Cosa importare, cosa NO (applicazione di D2 al dato concreto):

| JSON SRD          | In v0? | Uso in pocket-dnd                                          |
|-------------------|--------|------------------------------------------------------------|
| `ability-scores`  | SÌ     | I 6 attributi (riferimento, minuscolo).                    |
| `skills`          | SÌ     | Mappa skill → attributo, per calcolare i tiri di skill.    |
| `proficiencies`   | SÌ     | Supporto a skill/competenze.                               |
| `equipment`       | SÌ*    | *Solo il sottoinsieme "weapons": dadi di danno delle armi. |
| `conditions`      | SÌ*    | *Solo nome + descrizione testuale. Mostrate come flag.     |
| `spells`          | SÌ*    | *Catalogo consultabile: nome, livello, scuola, testo, e    |
|                   |        |  i dadi se l'incantesimo fa danno. NON simulati.           |
| `classes`         | SÌ*    | *Parziale: dado vita per classe + proficiency iniziali,    |
|                   |        |  per il level-up assistito.                                |
| `monsters`        | SÌ     | Statblock pronti per il DM (HP/CA/attacchi). Formato SRD.  |
| `races`           | NO     | Tana del coniglio "ricostruisco D&D Beyond".               |
| `subclasses`      | NO     | Come sopra. Semmai dopo, come testo, mai come logica.      |
| `features`        | NO     | Le feature di classe livello-per-livello sono testo da     |
|                   |        |  leggere dal manuale; l'app non le applica.                |
| `levels`          | NO     | Idem.                                                      |

## Trappola nota: dadi di danno nelle armi

Nei JSON SRD i dadi di danno arma sono talora strutturati
(`damage.damage_dice` come stringa, oppure `{dice_count, dice_value}` a seconda
del file/versione). Il parser dello step "motore dadi" deve normalizzare TUTTO
verso `NdS+M`. È puro → da scrivere in TDD.

## Vocabolario della board (introdotto allo Step 6)

- **Pedina / token** — una figura sulla griglia. In `pocket-dnd` ogni pedina è
  un `_Token` con un `token_id` stringa. Due famiglie:
  - PG → `token_id` = `pc:<character_id>`, collegato a un personaggio vero.
  - Nemico → `token_id` = `enemy:<n>`, pedina generica senza personaggio dietro.
- **Griglia** — il reticolo 8×8 su cui stanno le pedine. È una *superficie muta*
  (DECISIONS.md D14): conserva la posizione, non calcola nulla.
- **Posizione** — coppia `(x, y)` con origine in alto a sinistra, oppure `None`
  se la pedina è fuori dalla griglia.
- **Iniziativa** — già definita sopra; dallo Step 7 determina anche l'ordine
  dei turni, che gira su tutte le pedine (PG e nemici insieme).

Cosa la griglia di `pocket-dnd` NON sa, di proposito: distanza in piedi/caselle,
portata delle armi, linea di vista, area degli incantesimi, attacchi di
opportunità. Tutto questo lo arbitra il DM a occhio, come col feltro di cartone.
