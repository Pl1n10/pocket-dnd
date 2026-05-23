"""Test della logica delle room — stato live in memoria, SENZA rete.

La Room e' la fonte autoritativa dello stato di una sessione (DECISIONS.md D5).
Qui si testa tutta la logica di stato in isolamento: niente FastAPI, niente
WebSocket. Il trasporto si testa separatamente in test_server.py.

Copre:
  - creazione/recupero room
  - snapshot dello stato (cio' che un client ri-scarica al reconnect)
  - applicazione di eventi (HP, condizioni, iniziativa, tiri)
  - versionamento dello stato (ogni mutazione incrementa la versione)
"""
import pytest

from app.rooms import Room, RoomManager, RoomEvent, UnknownEvent


# ───────────────────────────── RoomManager ─────────────────────────────

class TestRoomManager:
    def test_create_room_returns_room(self):
        mgr = RoomManager()
        room = mgr.create(session_id=1)
        assert isinstance(room, Room)
        assert room.session_id == 1

    def test_get_existing_room(self):
        mgr = RoomManager()
        created = mgr.create(session_id=7)
        assert mgr.get(7) is created

    def test_get_unknown_room_returns_none(self):
        assert RoomManager().get(999) is None

    def test_get_or_create_is_idempotent(self):
        mgr = RoomManager()
        first = mgr.get_or_create(session_id=3)
        second = mgr.get_or_create(session_id=3)
        assert first is second

    def test_close_room_removes_it(self):
        mgr = RoomManager()
        mgr.create(session_id=5)
        mgr.close(5)
        assert mgr.get(5) is None


# ───────────────────────────── snapshot ─────────────────────────────

class TestSnapshot:
    """Lo snapshot e' cio' che un client ri-scarica integralmente al reconnect."""

    def test_fresh_room_snapshot_has_version_zero(self):
        room = Room(session_id=1)
        assert room.snapshot()["version"] == 0

    def test_snapshot_includes_participants(self):
        room = Room(session_id=1)
        room.add_participant(character_id=10, name="Brannor", current_hp=28, max_hp=28)
        snap = room.snapshot()
        assert len(snap["participants"]) == 1
        assert snap["participants"][0]["name"] == "Brannor"

    def test_snapshot_is_json_serializable(self):
        import json
        room = Room(session_id=1)
        room.add_participant(character_id=10, name="Brannor", current_hp=28, max_hp=28)
        json.dumps(room.snapshot())   # non deve sollevare

    def test_snapshot_includes_recent_rolls(self):
        room = Room(session_id=1)
        room.apply(RoomEvent("roll", {"character_id": 10, "label": "Attacco",
                                      "formula": "1d20+5", "result": 18,
                                      "breakdown": "[13] +5"}))
        snap = room.snapshot()
        assert len(snap["roll_feed"]) == 1
        assert snap["roll_feed"][0]["result"] == 18


# ───────────────────────────── versionamento ─────────────────────────────

class TestVersioning:
    """Ogni mutazione incrementa la versione: il client la usa per capire
    se ha perso aggiornamenti e deve ri-sincronizzarsi."""

    def test_version_increments_on_mutation(self):
        room = Room(session_id=1)
        v0 = room.snapshot()["version"]
        room.add_participant(character_id=1, name="X", current_hp=10, max_hp=10)
        assert room.snapshot()["version"] == v0 + 1

    def test_version_increments_per_event(self):
        room = Room(session_id=1)
        room.add_participant(character_id=1, name="X", current_hp=10, max_hp=10)
        room.apply(RoomEvent("hp_change", {"character_id": 1, "current_hp": 7}))
        room.apply(RoomEvent("hp_change", {"character_id": 1, "current_hp": 4}))
        assert room.snapshot()["version"] == 3


# ───────────────────────────── eventi ─────────────────────────────

class TestHpEvents:
    def test_hp_change_updates_participant(self):
        room = Room(session_id=1)
        room.add_participant(character_id=1, name="X", current_hp=10, max_hp=10)
        room.apply(RoomEvent("hp_change", {"character_id": 1, "current_hp": 6}))
        assert room.snapshot()["participants"][0]["current_hp"] == 6

    def test_hp_change_on_unknown_participant_is_ignored(self):
        # un evento per un personaggio non in sessione non deve far crashare
        room = Room(session_id=1)
        room.apply(RoomEvent("hp_change", {"character_id": 999, "current_hp": 1}))
        assert room.snapshot()["participants"] == []


class TestConditionEvents:
    def test_add_condition(self):
        room = Room(session_id=1)
        room.add_participant(character_id=1, name="X", current_hp=10, max_hp=10)
        room.apply(RoomEvent("condition_add", {"character_id": 1, "condition": "poisoned"}))
        assert "poisoned" in room.snapshot()["participants"][0]["conditions"]

    def test_remove_condition(self):
        room = Room(session_id=1)
        room.add_participant(character_id=1, name="X", current_hp=10, max_hp=10)
        room.apply(RoomEvent("condition_add", {"character_id": 1, "condition": "prone"}))
        room.apply(RoomEvent("condition_remove", {"character_id": 1, "condition": "prone"}))
        assert room.snapshot()["participants"][0]["conditions"] == []

    def test_duplicate_condition_not_added_twice(self):
        room = Room(session_id=1)
        room.add_participant(character_id=1, name="X", current_hp=10, max_hp=10)
        room.apply(RoomEvent("condition_add", {"character_id": 1, "condition": "blinded"}))
        room.apply(RoomEvent("condition_add", {"character_id": 1, "condition": "blinded"}))
        assert room.snapshot()["participants"][0]["conditions"] == ["blinded"]


class TestInitiativeEvents:
    def test_set_initiative(self):
        room = Room(session_id=1)
        room.add_participant(character_id=1, name="X", current_hp=10, max_hp=10)
        room.apply(RoomEvent("initiative_set", {"character_id": 1, "initiative": 17}))
        assert room.snapshot()["participants"][0]["initiative"] == 17

    def test_participants_sorted_by_initiative_desc(self):
        room = Room(session_id=1)
        room.add_participant(character_id=1, name="Lento", current_hp=10, max_hp=10)
        room.add_participant(character_id=2, name="Svelto", current_hp=10, max_hp=10)
        room.apply(RoomEvent("initiative_set", {"character_id": 1, "initiative": 5}))
        room.apply(RoomEvent("initiative_set", {"character_id": 2, "initiative": 20}))
        names = [p["name"] for p in room.snapshot()["participants"]]
        assert names == ["Svelto", "Lento"]


class TestRollFeed:
    def test_roll_appended_to_feed(self):
        room = Room(session_id=1)
        room.apply(RoomEvent("roll", {"character_id": 1, "label": "Salvezza",
                                      "formula": "1d20+2", "result": 14,
                                      "breakdown": "[12] +2"}))
        assert room.snapshot()["roll_feed"][0]["label"] == "Salvezza"

    def test_roll_feed_is_capped(self):
        # il feed non cresce all'infinito: tiene solo gli ultimi N
        room = Room(session_id=1)
        for i in range(60):
            room.apply(RoomEvent("roll", {"character_id": 1, "label": f"r{i}",
                                          "formula": "1d6", "result": 3,
                                          "breakdown": "[3]"}))
        feed = room.snapshot()["roll_feed"]
        assert len(feed) <= 50
        # gli ultimi tiri sono quelli conservati
        assert feed[-1]["label"] == "r59"


class TestUnknownEvent:
    def test_unknown_event_type_raises(self):
        room = Room(session_id=1)
        with pytest.raises(UnknownEvent):
            room.apply(RoomEvent("teleport", {}))

    def test_unknown_event_does_not_bump_version(self):
        room = Room(session_id=1)
        try:
            room.apply(RoomEvent("teleport", {}))
        except UnknownEvent:
            pass
        assert room.snapshot()["version"] == 0


class TestGridTokens:
    """La griglia e' una superficie muta (DECISIONS.md D14): conserva la
    posizione di ogni pedina, niente altro. Niente distanze, niente regole."""

    def test_participant_starts_with_no_position(self):
        # un PG appena aggiunto non e' ancora sulla griglia
        room = Room(session_id=1)
        room.add_participant(character_id=1, name="Brannor",
                             current_hp=28, max_hp=28)
        p = room.snapshot()["participants"][0]
        assert p["position"] is None

    def test_move_token_sets_position(self):
        room = Room(session_id=1)
        room.add_participant(character_id=1, name="Brannor",
                             current_hp=28, max_hp=28)
        room.apply(RoomEvent("move_token", {"token_id": "pc:1", "x": 3, "y": 4}))
        p = room.snapshot()["participants"][0]
        assert p["position"] == {"x": 3, "y": 4}

    def test_move_token_can_update_position(self):
        room = Room(session_id=1)
        room.add_participant(character_id=1, name="X", current_hp=10, max_hp=10)
        room.apply(RoomEvent("move_token", {"token_id": "pc:1", "x": 1, "y": 1}))
        room.apply(RoomEvent("move_token", {"token_id": "pc:1", "x": 6, "y": 2}))
        assert room.snapshot()["participants"][0]["position"] == {"x": 6, "y": 2}

    def test_move_token_off_grid_clears_position(self):
        # coordinate null = pedina tolta dalla griglia
        room = Room(session_id=1)
        room.add_participant(character_id=1, name="X", current_hp=10, max_hp=10)
        room.apply(RoomEvent("move_token", {"token_id": "pc:1", "x": 2, "y": 2}))
        room.apply(RoomEvent("move_token", {"token_id": "pc:1", "x": None, "y": None}))
        assert room.snapshot()["participants"][0]["position"] is None

    def test_move_unknown_token_is_ignored(self):
        # spostare una pedina inesistente non deve far crashare
        room = Room(session_id=1)
        room.apply(RoomEvent("move_token", {"token_id": "pc:999", "x": 1, "y": 1}))
        assert room.snapshot()["participants"] == []

    def test_grid_size_in_snapshot(self):
        # lo snapshot espone la dimensione della griglia (8x8 in v0)
        room = Room(session_id=1)
        assert room.snapshot()["grid_size"] == 8


class TestEnemyTokens:
    """I nemici sono pedine generiche che il master aggiunge: nome + HP,
    nessuno statblock. Stanno sulla griglia come i PG ma non sono personaggi."""

    def test_add_enemy_appears_in_snapshot(self):
        room = Room(session_id=1)
        room.apply(RoomEvent("enemy_add", {"token_id": "enemy:1",
                                           "name": "Goblin", "max_hp": 7}))
        enemies = room.snapshot()["enemies"]
        assert len(enemies) == 1
        assert enemies[0]["name"] == "Goblin"
        assert enemies[0]["current_hp"] == 7

    def test_enemy_can_be_moved_on_grid(self):
        room = Room(session_id=1)
        room.apply(RoomEvent("enemy_add", {"token_id": "enemy:1",
                                           "name": "Goblin", "max_hp": 7}))
        room.apply(RoomEvent("move_token", {"token_id": "enemy:1", "x": 5, "y": 5}))
        assert room.snapshot()["enemies"][0]["position"] == {"x": 5, "y": 5}

    def test_enemy_hp_can_change(self):
        room = Room(session_id=1)
        room.apply(RoomEvent("enemy_add", {"token_id": "enemy:1",
                                           "name": "Goblin", "max_hp": 7}))
        room.apply(RoomEvent("hp_change", {"token_id": "enemy:1", "current_hp": 3}))
        assert room.snapshot()["enemies"][0]["current_hp"] == 3

    def test_enemy_can_be_removed(self):
        room = Room(session_id=1)
        room.apply(RoomEvent("enemy_add", {"token_id": "enemy:1",
                                           "name": "Goblin", "max_hp": 7}))
        room.apply(RoomEvent("enemy_remove", {"token_id": "enemy:1"}))
        assert room.snapshot()["enemies"] == []


class TestTurnOrder:
    """Il turno corrente vive nella Room. `next_turn` ricalcola sempre l'ordine
    dallo snapshot attuale (DECISIONS.md D15): se la pedina di turno e' stata
    rimossa o l'iniziativa e' cambiata, il giro si auto-aggiusta."""

    def test_fresh_room_has_no_active_token(self):
        assert Room(session_id=1).snapshot()["active_token_id"] is None

    def test_next_turn_on_empty_room_is_noop(self):
        # nessuna pedina: nessun turno da attivare, ma l'evento e' valido
        room = Room(session_id=1)
        room.apply(RoomEvent("next_turn", {}))
        snap = room.snapshot()
        assert snap["active_token_id"] is None
        assert snap["version"] == 1

    def test_next_turn_activates_first_token(self):
        room = Room(session_id=1)
        room.add_participant(character_id=1, name="A", current_hp=10, max_hp=10)
        room.apply(RoomEvent("next_turn", {}))
        assert room.snapshot()["active_token_id"] == "pc:1"

    def test_next_turn_follows_initiative_order(self):
        # ordine: chi ha iniziativa piu' alta gioca prima
        room = Room(session_id=1)
        room.add_participant(character_id=1, name="Lento", current_hp=10, max_hp=10)
        room.add_participant(character_id=2, name="Svelto", current_hp=10, max_hp=10)
        room.apply(RoomEvent("initiative_set", {"character_id": 1, "initiative": 5}))
        room.apply(RoomEvent("initiative_set", {"character_id": 2, "initiative": 20}))
        room.apply(RoomEvent("next_turn", {}))
        assert room.snapshot()["active_token_id"] == "pc:2"
        room.apply(RoomEvent("next_turn", {}))
        assert room.snapshot()["active_token_id"] == "pc:1"

    def test_next_turn_wraps_around(self):
        room = Room(session_id=1)
        room.add_participant(character_id=1, name="A", current_hp=10, max_hp=10)
        room.add_participant(character_id=2, name="B", current_hp=10, max_hp=10)
        room.apply(RoomEvent("next_turn", {}))   # primo turno (qualcuno)
        room.apply(RoomEvent("next_turn", {}))   # secondo turno (l'altro)
        first = room.snapshot()["active_token_id"]
        room.apply(RoomEvent("next_turn", {}))   # giro nuovo: torna al primo
        last = room.snapshot()["active_token_id"]
        # dopo il wrap il turno e' tornato a chi era primo nell'ordine
        # (non sappiamo chi e' il primo ma sappiamo che e' il "two ago")
        # equivalentemente: 3 next_turn su 2 pedine = stesso turno del primo
        assert last != first

    def test_next_turn_includes_enemies(self):
        # il giro gira sulle pedine, PG E nemici insieme
        room = Room(session_id=1)
        room.add_participant(character_id=1, name="PG", current_hp=10, max_hp=10)
        room.apply(RoomEvent("enemy_add", {"token_id": "enemy:1",
                                           "name": "Goblin", "max_hp": 7}))
        room.apply(RoomEvent("initiative_set", {"character_id": 1, "initiative": 10}))
        room.apply(RoomEvent("initiative_set", {"token_id": "enemy:1", "initiative": 18}))
        room.apply(RoomEvent("next_turn", {}))
        assert room.snapshot()["active_token_id"] == "enemy:1"
        room.apply(RoomEvent("next_turn", {}))
        assert room.snapshot()["active_token_id"] == "pc:1"

    def test_next_turn_restarts_if_active_token_was_removed(self):
        # se la pedina attiva viene rimossa, il prossimo next_turn riparte
        # dal primo nell'ordine corrente (D15)
        room = Room(session_id=1)
        room.apply(RoomEvent("enemy_add", {"token_id": "enemy:1",
                                           "name": "G1", "max_hp": 7}))
        room.apply(RoomEvent("enemy_add", {"token_id": "enemy:2",
                                           "name": "G2", "max_hp": 7}))
        room.apply(RoomEvent("initiative_set", {"token_id": "enemy:1", "initiative": 15}))
        room.apply(RoomEvent("initiative_set", {"token_id": "enemy:2", "initiative": 10}))
        room.apply(RoomEvent("next_turn", {}))
        assert room.snapshot()["active_token_id"] == "enemy:1"
        # tolgo la pedina attiva: l'active_token_id non e' piu' valido
        room.apply(RoomEvent("enemy_remove", {"token_id": "enemy:1"}))
        # prossimo turno: riparte dal primo dell'ordine corrente
        room.apply(RoomEvent("next_turn", {}))
        assert room.snapshot()["active_token_id"] == "enemy:2"

    def test_active_token_id_in_snapshot(self):
        room = Room(session_id=1)
        room.add_participant(character_id=1, name="A", current_hp=10, max_hp=10)
        room.apply(RoomEvent("next_turn", {}))
        assert "active_token_id" in room.snapshot()
