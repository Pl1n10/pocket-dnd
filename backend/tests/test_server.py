"""Test del server FastAPI: endpoint HTTP REST + WebSocket.

Usa TestClient di Starlette, che gestisce sia HTTP sia WebSocket in modo
sincrono e deterministico — niente server reale, niente porte.

ATTENZIONE (vedi nota allo Step 4): questi test coprono la LOGICA del
trasporto. Il comportamento reale al pub — standby dei telefoni, socket che
cadono — si collauda solo sul campo. Qui si verifica che il protocollo sia
corretto, non che la rete del pub regga.

Copre:
  - health check
  - CRUD personaggi via REST (sopra CharacterRepo gia' testato)
  - WebSocket: connessione, snapshot iniziale, broadcast, reconnect
"""
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.server import create_app


SCHEMA = Path(__file__).resolve().parent.parent / "app" / "schema.sql"


@pytest.fixture
def client():
    # ogni test: app fresca con DB in-memory condiviso per quel test
    app = create_app(db_path=":memory:", schema_sql=SCHEMA.read_text(encoding="utf-8"))
    return TestClient(app)


def _make_character(client, name="Brannor"):
    resp = client.post("/api/characters", json={
        "name": name, "class": "fighter", "level": 3,
        "str": 16, "dex": 13, "con": 14, "max_hp": 28, "current_hp": 28,
        "armor_class": 16,
    })
    assert resp.status_code == 201
    return resp.json()["id"]


# ───────────────────────────── HTTP ─────────────────────────────

class TestHealth:
    def test_health_ok(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"


class TestCharacterApi:
    def test_create_character_returns_id(self, client):
        cid = _make_character(client)
        assert isinstance(cid, int)

    def test_get_character(self, client):
        cid = _make_character(client)
        resp = client.get(f"/api/characters/{cid}")
        assert resp.status_code == 200
        assert resp.json()["name"] == "Brannor"

    def test_get_unknown_character_404(self, client):
        assert client.get("/api/characters/9999").status_code == 404

    def test_list_characters(self, client):
        _make_character(client, "A")
        _make_character(client, "B")
        resp = client.get("/api/characters")
        assert resp.status_code == 200
        assert len(resp.json()) == 2

    def test_update_character(self, client):
        cid = _make_character(client)
        resp = client.patch(f"/api/characters/{cid}", json={"current_hp": 12})
        assert resp.status_code == 200
        assert client.get(f"/api/characters/{cid}").json()["current_hp"] == 12

    def test_delete_character(self, client):
        cid = _make_character(client)
        assert client.delete(f"/api/characters/{cid}").status_code == 204
        assert client.get(f"/api/characters/{cid}").status_code == 404

    def test_export_character(self, client):
        cid = _make_character(client)
        resp = client.get(f"/api/characters/{cid}/export")
        assert resp.status_code == 200
        assert resp.json()["schema_version"] == "pocket-dnd/1"

    def test_import_character(self, client):
        cid = _make_character(client)
        exported = client.get(f"/api/characters/{cid}/export").json()
        resp = client.post("/api/characters/import", json=exported)
        assert resp.status_code == 201

    def test_import_bad_schema_rejected(self, client):
        resp = client.post("/api/characters/import",
                            json={"schema_version": "bogus/1", "computed": {}})
        assert resp.status_code == 422


# ───────────────────────────── WebSocket ─────────────────────────────

class TestWebSocket:
    def test_connect_receives_snapshot(self, client):
        # appena connesso, il client riceve subito lo snapshot completo
        with client.websocket_connect("/ws/session/1") as ws:
            msg = ws.receive_json()
            assert msg["type"] == "snapshot"
            assert msg["state"]["session_id"] == 1
            assert msg["state"]["version"] == 0

    def test_event_is_broadcast_to_all_clients(self, client):
        # due client sulla stessa sessione: un evento di uno arriva all'altro
        with client.websocket_connect("/ws/session/1") as ws_a, \
             client.websocket_connect("/ws/session/1") as ws_b:
            ws_a.receive_json()   # snapshot iniziale A
            ws_b.receive_json()   # snapshot iniziale B

            ws_a.send_json({"type": "roll", "payload": {
                "character_id": 1, "label": "Attacco",
                "formula": "1d20+5", "result": 18, "breakdown": "[13] +5"}})

            # entrambi ricevono l'aggiornamento
            update_a = ws_a.receive_json()
            update_b = ws_b.receive_json()
            assert update_a["type"] == "snapshot"
            assert update_b["type"] == "snapshot"
            assert update_b["state"]["roll_feed"][0]["result"] == 18

    def test_version_advances_after_event(self, client):
        with client.websocket_connect("/ws/session/2") as ws:
            first = ws.receive_json()
            assert first["state"]["version"] == 0
            ws.send_json({"type": "roll", "payload": {
                "character_id": 1, "label": "x", "formula": "1d6",
                "result": 3, "breakdown": "[3]"}})
            after = ws.receive_json()
            assert after["state"]["version"] == 1

    def test_reconnect_gets_current_state_not_stale(self, client):
        # un client che si disconnette e riconnette riceve lo stato AGGIORNATO,
        # non quello di quando si era connesso la prima volta (D5 / AP6)
        with client.websocket_connect("/ws/session/3") as ws:
            ws.receive_json()
            ws.send_json({"type": "roll", "payload": {
                "character_id": 1, "label": "x", "formula": "1d6",
                "result": 3, "breakdown": "[3]"}})
            ws.receive_json()
        # nuova connessione alla stessa sessione
        with client.websocket_connect("/ws/session/3") as ws2:
            snap = ws2.receive_json()
            # lo stato sopravvive alla disconnessione: versione gia' a 1
            assert snap["state"]["version"] == 1
            assert len(snap["state"]["roll_feed"]) == 1

    def test_unknown_event_returns_error_without_breaking(self, client):
        # un evento ignoto produce un messaggio d'errore ma non chiude la socket
        with client.websocket_connect("/ws/session/4") as ws:
            ws.receive_json()
            ws.send_json({"type": "teleport", "payload": {}})
            err = ws.receive_json()
            assert err["type"] == "error"
            # la connessione regge: un evento valido funziona ancora
            ws.send_json({"type": "roll", "payload": {
                "character_id": 1, "label": "x", "formula": "1d6",
                "result": 3, "breakdown": "[3]"}})
            ok = ws.receive_json()
            assert ok["type"] == "snapshot"

    def test_separate_sessions_are_isolated(self, client):
        # un evento nella sessione 10 non raggiunge la sessione 11
        with client.websocket_connect("/ws/session/10") as ws10, \
             client.websocket_connect("/ws/session/11") as ws11:
            ws10.receive_json()
            ws11.receive_json()
            ws10.send_json({"type": "roll", "payload": {
                "character_id": 1, "label": "x", "formula": "1d6",
                "result": 3, "breakdown": "[3]"}})
            ws10.receive_json()   # ws10 riceve il proprio aggiornamento
            # ws11 non deve aver ricevuto nulla: la sua versione resta 0
            # (lo verifichiamo riconnettendo e controllando lo stato)
        with client.websocket_connect("/ws/session/11") as ws11b:
            assert ws11b.receive_json()["state"]["version"] == 0


class TestRollRequest:
    """Il dado lo tira il SERVER (DECISIONS.md D13).

    Il client manda l'intento (`roll_request` con la formula); il server
    tira con dice.py e fa broadcast del risultato come tiro nel feed.
    """

    def test_roll_request_produces_a_roll_in_the_feed(self, client):
        with client.websocket_connect("/ws/session/1") as ws:
            ws.receive_json()
            ws.send_json({"type": "roll_request", "payload": {
                "character_id": 1, "label": "Spada lunga", "formula": "1d20+5"}})
            snap = ws.receive_json()
            assert snap["type"] == "snapshot"
            feed = snap["state"]["roll_feed"]
            assert len(feed) == 1
            assert feed[0]["label"] == "Spada lunga"

    def test_server_computed_result_is_within_bounds(self, client):
        # il risultato e' calcolato dal server: 1d20+5 sta in [6, 25]
        with client.websocket_connect("/ws/session/1") as ws:
            ws.receive_json()
            ws.send_json({"type": "roll_request", "payload": {
                "character_id": 1, "label": "x", "formula": "1d20+5"}})
            roll = ws.receive_json()["state"]["roll_feed"][0]
            assert 6 <= roll["result"] <= 25
            assert roll["breakdown"]   # il breakdown e' valorizzato

    def test_roll_request_is_broadcast_to_master(self, client):
        # il tiro di un giocatore arriva anche al master, senza codice extra
        with client.websocket_connect("/ws/session/1") as player, \
             client.websocket_connect("/ws/session/1") as master:
            player.receive_json()
            master.receive_json()
            player.send_json({"type": "roll_request", "payload": {
                "character_id": 7, "label": "Furtivita'", "formula": "1d20+3"}})
            player.receive_json()
            master_view = master.receive_json()
            assert master_view["state"]["roll_feed"][0]["label"] == "Furtivita'"

    def test_bad_formula_returns_error_without_breaking(self, client):
        # una formula malformata: errore al mittente, socket viva
        with client.websocket_connect("/ws/session/1") as ws:
            ws.receive_json()
            ws.send_json({"type": "roll_request", "payload": {
                "character_id": 1, "label": "x", "formula": "banana"}})
            err = ws.receive_json()
            assert err["type"] == "error"
            # la socket regge: una formula valida funziona ancora
            ws.send_json({"type": "roll_request", "payload": {
                "character_id": 1, "label": "ok", "formula": "1d6"}})
            assert ws.receive_json()["type"] == "snapshot"

    def test_roll_request_supports_advantage(self, client):
        with client.websocket_connect("/ws/session/1") as ws:
            ws.receive_json()
            ws.send_json({"type": "roll_request", "payload": {
                "character_id": 1, "label": "Attacco",
                "formula": "1d20+5", "advantage": "advantage"}})
            roll = ws.receive_json()["state"]["roll_feed"][0]
            # con vantaggio il breakdown menziona entrambi i d20
            assert "vantaggio" in roll["breakdown"]
