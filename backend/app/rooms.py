"""Logica delle room: lo stato live di una sessione di gioco.

La Room e' la FONTE AUTORITATIVA dello stato (DECISIONS.md D5). Vive in memoria.
Questo modulo e' puro: nessuna dipendenza da FastAPI o WebSocket.

Concetti:
  - RoomEvent  -> una mutazione richiesta (tipo + payload).
  - Token      -> una pedina sulla griglia: un PG o un nemico. Ha un token_id
                  stringa ("pc:<id>" per i personaggi, "enemy:<id>" per i
                  nemici) e una posizione opzionale (x, y) o None se fuori griglia.
  - Room       -> stato di una sessione; applica eventi, produce snapshot.
  - RoomManager-> registro delle room attive, indicizzate per session_id.

La griglia (DECISIONS.md D14) e' una superficie muta: conserva DOVE sta ogni
pedina, niente altro. Niente distanze, niente portate, niente regole.

Versionamento: ogni mutazione andata a buon fine incrementa `version`.
"""
from __future__ import annotations

from dataclasses import dataclass, field

# quanti tiri tenere nel feed: oltre, i piu' vecchi vengono scartati
_ROLL_FEED_CAP = 50
# dimensione della griglia in v0 (8x8 — DECISIONS.md D14)
_GRID_SIZE = 8


class UnknownEvent(ValueError):
    """Tipo di evento non riconosciuto."""


@dataclass
class RoomEvent:
    """Una mutazione richiesta allo stato di una room."""
    type: str
    payload: dict = field(default_factory=dict)


@dataclass
class _Token:
    """Una pedina sulla griglia: PG o nemico.

    token_id: identificatore stringa, "pc:<character_id>" o "enemy:<n>".
    character_id: valorizzato solo per i PG; None per i nemici.
    """
    token_id: str
    name: str
    current_hp: int
    max_hp: int
    is_enemy: bool
    character_id: int | None = None
    initiative: int | None = None
    conditions: list[str] = field(default_factory=list)
    x: int | None = None
    y: int | None = None

    def as_dict(self) -> dict:
        position = None if self.x is None or self.y is None else {"x": self.x, "y": self.y}
        d = {
            "token_id": self.token_id,
            "name": self.name,
            "current_hp": self.current_hp,
            "max_hp": self.max_hp,
            "initiative": self.initiative,
            "conditions": list(self.conditions),
            "position": position,
        }
        if not self.is_enemy:
            d["character_id"] = self.character_id
        return d


class Room:
    """Stato live di una sessione di gioco."""

    def __init__(self, session_id: int):
        self.session_id = session_id
        self._version = 0
        # tutte le pedine, PG e nemici, indicizzate per token_id
        self._tokens: dict[str, _Token] = {}
        self._roll_feed: list[dict] = []
        # pedina di turno (None = combattimento non iniziato)
        self._active_token_id: str | None = None

    # ─────────────────────────── snapshot ───────────────────────────

    def snapshot(self) -> dict:
        """Stato completo, JSON-serializzabile. E' cio' che un client
        ri-scarica integralmente quando si (ri)connette."""
        pcs = [t for t in self._tokens.values() if not t.is_enemy]
        enemies = [t for t in self._tokens.values() if t.is_enemy]

        def by_initiative(tokens):
            return sorted(
                (t.as_dict() for t in tokens),
                key=lambda t: (t["initiative"] is not None, t["initiative"] or 0),
                reverse=True,
            )

        return {
            "session_id": self.session_id,
            "version": self._version,
            "grid_size": _GRID_SIZE,
            "participants": by_initiative(pcs),
            "enemies": by_initiative(enemies),
            "roll_feed": list(self._roll_feed),
            "active_token_id": self._active_token_id,
        }

    def _first_free_cell(self) -> tuple[int, int] | None:
        """Prima cella libera della griglia (scan riga per riga). None se
        tutte e 64 sono occupate (improbabile, ma gestito)."""
        occupied = {(t.x, t.y) for t in self._tokens.values()
                    if t.x is not None and t.y is not None}
        for y in range(_GRID_SIZE):
            for x in range(_GRID_SIZE):
                if (x, y) not in occupied:
                    return (x, y)
        return None

    def _initiative_order(self) -> list[str]:
        """Ordine d'iniziativa corrente: PG + nemici, initiative desc.
        Token senza iniziativa vanno in fondo. Stesso criterio dello snapshot."""
        return sorted(
            self._tokens.keys(),
            key=lambda tid: (
                self._tokens[tid].initiative is not None,
                self._tokens[tid].initiative or 0,
            ),
            reverse=True,
        )

    # ─────────────────────── mutazioni dirette ───────────────────────

    def sync_participant_from(self, character: dict) -> bool:
        """Aggiorna i dati live di una pedina PG dal DB (nome, max_hp,
        current_hp). No-op se la pedina non e' in sessione.

        Usato dal server dopo PATCH/level-up/setup iniziale: la Room non
        sa del DB, ma il server le passa la scheda fresca cosi' i client
        vedono i valori aggiornati anche senza ri-aggiungere il PG.

        Restituisce True se qualcosa e' stato sincronizzato (per decidere
        se fare broadcast)."""
        tid = f"pc:{character['id']}"
        t = self._tokens.get(tid)
        if t is None:
            return False
        t.name = character["name"]
        t.max_hp = character["max_hp"]
        t.current_hp = character["current_hp"]
        self._version += 1
        return True

    def add_participant(self, character_id: int, name: str,
                         current_hp: int, max_hp: int) -> None:
        """Aggiunge un personaggio alla sessione. Auto-posiziona la pedina
        nella prima cella libera (vedi `_first_free_cell`)."""
        token_id = f"pc:{character_id}"
        cell = self._first_free_cell()
        self._tokens[token_id] = _Token(
            token_id=token_id, name=name,
            current_hp=current_hp, max_hp=max_hp,
            is_enemy=False, character_id=character_id,
            x=cell[0] if cell else None,
            y=cell[1] if cell else None,
        )
        self._version += 1

    # ─────────────────────── applicazione eventi ───────────────────────

    def apply(self, event: RoomEvent) -> None:
        """Applica un evento. Solleva UnknownEvent se il tipo e' ignoto;
        in tal caso la versione NON viene incrementata.

        Un evento che riguarda una pedina inesistente viene ignorato
        silenziosamente ma conta comunque come applicato (no-op valido)."""
        handler = self._HANDLERS.get(event.type)
        if handler is None:
            raise UnknownEvent(f"tipo di evento sconosciuto: {event.type!r}")
        handler(self, event.payload)
        self._version += 1

    def _token_from_payload(self, payload: dict) -> _Token | None:
        """Risolve la pedina riferita da un payload. Accetta sia `token_id`
        sia `character_id` (per retro-compatibilita' con gli eventi vecchi)."""
        tid = payload.get("token_id")
        if tid is None and "character_id" in payload:
            tid = f"pc:{payload['character_id']}"
        if tid is None:
            return None
        return self._tokens.get(tid)

    def _on_hp_change(self, payload: dict) -> None:
        t = self._token_from_payload(payload)
        if t is not None:
            t.current_hp = payload["current_hp"]

    def _on_condition_add(self, payload: dict) -> None:
        t = self._token_from_payload(payload)
        if t is not None and payload["condition"] not in t.conditions:
            t.conditions.append(payload["condition"])

    def _on_condition_remove(self, payload: dict) -> None:
        t = self._token_from_payload(payload)
        if t is not None and payload["condition"] in t.conditions:
            t.conditions.remove(payload["condition"])

    def _on_initiative_set(self, payload: dict) -> None:
        t = self._token_from_payload(payload)
        if t is not None:
            t.initiative = payload["initiative"]

    def _on_move_token(self, payload: dict) -> None:
        t = self._token_from_payload(payload)
        if t is not None:
            # x/y None = pedina tolta dalla griglia
            t.x = payload.get("x")
            t.y = payload.get("y")

    def _on_enemy_add(self, payload: dict) -> None:
        tid = payload["token_id"]
        max_hp = payload.get("max_hp", 1)
        cell = self._first_free_cell()
        self._tokens[tid] = _Token(
            token_id=tid, name=payload.get("name", "Nemico"),
            current_hp=payload.get("current_hp", max_hp), max_hp=max_hp,
            is_enemy=True,
            x=cell[0] if cell else None,
            y=cell[1] if cell else None,
        )

    def _on_enemy_remove(self, payload: dict) -> None:
        self._tokens.pop(payload["token_id"], None)

    def _on_remove_participant(self, payload: dict) -> None:
        """Toglie un PG dalla sessione (simmetrico di add_participant).
        Accetta sia token_id sia character_id. NON tocca il DB: il PG resta
        nel roster e puo' essere ri-aggiunto."""
        tid = payload.get("token_id")
        if tid is None and "character_id" in payload:
            tid = f"pc:{payload['character_id']}"
        if tid is not None:
            self._tokens.pop(tid, None)

    def _on_next_turn(self, payload: dict) -> None:
        """Avanza la pedina di turno (D15): ricalcola sempre l'ordine dallo
        stato corrente. Se la pedina attiva non c'e' piu' (rimossa, oppure
        prima chiamata in assoluto), il turno parte dal primo nell'ordine."""
        order = self._initiative_order()
        if not order:
            self._active_token_id = None
            return
        if self._active_token_id not in order:
            self._active_token_id = order[0]
            return
        idx = order.index(self._active_token_id)
        self._active_token_id = order[(idx + 1) % len(order)]

    def _on_roll(self, payload: dict) -> None:
        self._roll_feed.append({
            "character_id": payload.get("character_id"),
            "label": payload.get("label", ""),
            "formula": payload.get("formula", ""),
            "result": payload.get("result"),
            "breakdown": payload.get("breakdown", ""),
        })
        if len(self._roll_feed) > _ROLL_FEED_CAP:
            self._roll_feed = self._roll_feed[-_ROLL_FEED_CAP:]

    # mappa tipo-evento -> handler. Aggiungere qui i nuovi tipi.
    _HANDLERS = {
        "hp_change": _on_hp_change,
        "condition_add": _on_condition_add,
        "condition_remove": _on_condition_remove,
        "initiative_set": _on_initiative_set,
        "move_token": _on_move_token,
        "enemy_add": _on_enemy_add,
        "enemy_remove": _on_enemy_remove,
        "remove_participant": _on_remove_participant,
        "next_turn": _on_next_turn,
        "roll": _on_roll,
    }


class RoomManager:
    """Registro delle room attive, una per sessione."""

    def __init__(self):
        self._rooms: dict[int, Room] = {}

    def create(self, session_id: int) -> Room:
        room = Room(session_id=session_id)
        self._rooms[session_id] = room
        return room

    def get(self, session_id: int) -> Room | None:
        return self._rooms.get(session_id)

    def get_or_create(self, session_id: int) -> Room:
        room = self._rooms.get(session_id)
        if room is None:
            room = self.create(session_id)
        return room

    def close(self, session_id: int) -> None:
        self._rooms.pop(session_id, None)

    def all_rooms(self) -> list[tuple[int, Room]]:
        """Iteratore (session_id, room) sulle room aperte."""
        return list(self._rooms.items())
