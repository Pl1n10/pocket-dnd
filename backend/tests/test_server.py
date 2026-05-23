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


class TestLevelUpEndpoint:
    """POST /api/characters/{id}/level-up — endpoint del level-up assistito."""

    def _seed_classes(self, client):
        # popola srd_classes via la stessa connessione del repo dell'app
        repo = client.app.state.repo
        with repo._lock:
            repo._conn.execute(
                "INSERT INTO srd_classes (slug, name, hit_die) "
                "VALUES ('fighter', 'Fighter', 10)"
            )
            repo._conn.commit()

    def test_level_up_returns_summary_and_updated_character(self, client):
        self._seed_classes(client)
        cid = _make_character(client)   # liv 3, con 14
        resp = client.post(f"/api/characters/{cid}/level-up", json={})
        assert resp.status_code == 200
        data = resp.json()
        assert data["summary"]["old_level"] == 3
        assert data["summary"]["new_level"] == 4
        assert data["character"]["level"] == 4

    def test_level_up_unknown_character_returns_404(self, client):
        resp = client.post("/api/characters/9999/level-up", json={})
        assert resp.status_code == 404

    def test_level_up_at_max_returns_422(self, client):
        self._seed_classes(client)
        cid = _make_character(client)
        client.patch(f"/api/characters/{cid}", json={"level": 20})
        resp = client.post(f"/api/characters/{cid}/level-up", json={})
        assert resp.status_code == 422

    def test_level_up_unknown_class_returns_422(self, client):
        # niente seed di srd_classes: la classe del PG non e' nota
        cid = _make_character(client)
        resp = client.post(f"/api/characters/{cid}/level-up", json={})
        assert resp.status_code == 422

    def test_level_up_merges_extended_patch_from_body(self, client):
        self._seed_classes(client)
        cid = _make_character(client)
        resp = client.post(f"/api/characters/{cid}/level-up",
                            json={"extended": {"feat": "Lucky"}})
        assert resp.status_code == 200
        assert resp.json()["character"]["extended"]["feat"] == "Lucky"


class TestGiveItemEndpoint:
    """POST /api/characters/{id}/inventory/give — il master da' loot a un PG."""

    def test_give_item_appends_and_returns_inventory(self, client):
        cid = _make_character(client)
        resp = client.post(f"/api/characters/{cid}/inventory/give",
                            json={"name": "Pozione di guarigione"})
        assert resp.status_code == 200
        assert resp.json()["inventory"][0]["name"] == "Pozione di guarigione"

    def test_give_item_with_description(self, client):
        cid = _make_character(client)
        resp = client.post(f"/api/characters/{cid}/inventory/give",
                            json={"name": "Anello", "description": "Brilla."})
        assert resp.json()["inventory"][0]["description"] == "Brilla."

    def test_give_item_to_unknown_returns_404(self, client):
        resp = client.post("/api/characters/9999/inventory/give",
                            json={"name": "X"})
        assert resp.status_code == 404

    def test_give_item_empty_name_returns_422(self, client):
        cid = _make_character(client)
        resp = client.post(f"/api/characters/{cid}/inventory/give",
                            json={"name": ""})
        assert resp.status_code == 422

    def test_give_item_broadcasts_character_updated_to_ws(self, client):
        # PG in sessione; un WS connesso riceve character_updated
        cid = _make_character(client)
        with client.websocket_connect("/ws/session/1") as ws:
            ws.receive_json()   # snapshot iniziale
            resp = client.post(f"/api/characters/{cid}/inventory/give",
                                json={"name": "Mappa"})
            assert resp.status_code == 200
            msg = ws.receive_json()
            assert msg["type"] == "character_updated"
            assert msg["character_id"] == cid
            assert msg["character"]["inventory"][0]["name"] == "Mappa"


class TestStaticSpa:
    """Modalita' container: il backend serve anche la SPA buildata. Le route
    API/WS hanno priorita'; le altre cadono sull'index della SPA."""

    @pytest.fixture
    def static_client(self, tmp_path):
        # fake dist: index.html + assets/app.js
        (tmp_path / "assets").mkdir()
        (tmp_path / "assets" / "app.js").write_text("console.log('app')")
        (tmp_path / "index.html").write_text("<!doctype html><h1>Pocket D&amp;D</h1>")
        app = create_app(
            db_path=":memory:",
            schema_sql=SCHEMA.read_text(encoding="utf-8"),
            static_dir=str(tmp_path),
        )
        return TestClient(app)

    def test_root_serves_index_html(self, static_client):
        resp = static_client.get("/")
        assert resp.status_code == 200
        assert "Pocket D" in resp.text

    def test_assets_are_served(self, static_client):
        resp = static_client.get("/assets/app.js")
        assert resp.status_code == 200
        assert "console.log" in resp.text

    def test_spa_route_falls_back_to_index(self, static_client):
        # /master e /player/123 sono route del client router: il server
        # rimanda l'index e React decide cosa mostrare.
        for path in ("/master", "/player/42"):
            resp = static_client.get(path)
            assert resp.status_code == 200, path
            assert "Pocket D" in resp.text

    def test_api_routes_still_work_with_static_mounted(self, static_client):
        # le rotte API non devono essere intercettate dal fallback SPA
        resp = static_client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"
        resp2 = static_client.get("/api/characters")
        assert resp2.status_code == 200

    def test_static_dir_optional_falls_back_to_no_spa(self, client):
        # senza static_dir: GET /random_path -> 404 (nessun fallback)
        assert client.get("/unmapped").status_code == 404


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


class TestAddParticipant:
    """Saldo del debito: il client puo' mettere PG in sessione via WS.

    L'evento `add_participant` ha bisogno del CharacterRepo per leggere il
    personaggio (nome, HP), quindi va intercettato nel server come
    `roll_request` — la `Room` pura non ha accesso al repo.
    """

    def test_add_participant_puts_character_in_room(self, client):
        cid = _make_character(client, name="Brannor")
        with client.websocket_connect("/ws/session/1") as ws:
            ws.receive_json()
            ws.send_json({"type": "add_participant",
                          "payload": {"character_id": cid}})
            snap = ws.receive_json()
            assert snap["type"] == "snapshot"
            pcs = snap["state"]["participants"]
            assert len(pcs) == 1
            assert pcs[0]["name"] == "Brannor"
            assert pcs[0]["character_id"] == cid

    def test_add_participant_uses_repo_hp_values(self, client):
        # il server legge HP correnti e massimi DAL repo, non dal payload
        cid = _make_character(client, name="Brannor")
        client.patch(f"/api/characters/{cid}", json={"current_hp": 7})
        with client.websocket_connect("/ws/session/1") as ws:
            ws.receive_json()
            ws.send_json({"type": "add_participant",
                          "payload": {"character_id": cid}})
            pc = ws.receive_json()["state"]["participants"][0]
            assert pc["current_hp"] == 7
            assert pc["max_hp"] == 28

    def test_add_unknown_character_returns_error(self, client):
        # PG inesistente: errore al mittente, socket viva, stato invariato
        with client.websocket_connect("/ws/session/1") as ws:
            ws.receive_json()
            ws.send_json({"type": "add_participant",
                          "payload": {"character_id": 9999}})
            err = ws.receive_json()
            assert err["type"] == "error"
            # la socket regge: un evento valido continua a funzionare
            cid = _make_character(client, name="Altro")
            ws.send_json({"type": "add_participant",
                          "payload": {"character_id": cid}})
            ok = ws.receive_json()
            assert ok["type"] == "snapshot"
            assert len(ok["state"]["participants"]) == 1

    def test_add_participant_is_broadcast(self, client):
        # come gli altri eventi, raggiunge tutti i device in sessione
        cid = _make_character(client, name="Brannor")
        with client.websocket_connect("/ws/session/1") as ws_a, \
             client.websocket_connect("/ws/session/1") as ws_b:
            ws_a.receive_json()
            ws_b.receive_json()
            ws_a.send_json({"type": "add_participant",
                            "payload": {"character_id": cid}})
            ws_a.receive_json()
            update_b = ws_b.receive_json()
            assert update_b["state"]["participants"][0]["name"] == "Brannor"


class TestInitiative:
    """Tiro d'iniziativa: lo fa il SERVER (D13). 1d20 + mod_DEX per i PG,
    1d20 per i nemici (non hanno scheda). Il tiro appare anche nel feed."""

    def test_roll_initiative_sets_participant_initiative(self, client):
        cid = _make_character(client, name="Brannor")   # dex=13 -> mod +1
        with client.websocket_connect("/ws/session/1") as ws:
            ws.receive_json()
            ws.send_json({"type": "add_participant",
                          "payload": {"character_id": cid}})
            ws.receive_json()
            ws.send_json({"type": "roll_initiative",
                          "payload": {"token_id": f"pc:{cid}"}})
            snap = ws.receive_json()
            init = snap["state"]["participants"][0]["initiative"]
            # 1d20 + mod_dex(+1): range [2, 21]
            assert init is not None
            assert 2 <= init <= 21

    def test_roll_initiative_appears_in_feed(self, client):
        cid = _make_character(client, name="Brannor")
        with client.websocket_connect("/ws/session/1") as ws:
            ws.receive_json()
            ws.send_json({"type": "add_participant",
                          "payload": {"character_id": cid}})
            ws.receive_json()
            ws.send_json({"type": "roll_initiative",
                          "payload": {"token_id": f"pc:{cid}"}})
            feed = ws.receive_json()["state"]["roll_feed"]
            assert len(feed) == 1
            assert "niziativa" in feed[0]["label"]

    def test_roll_initiative_for_enemy_uses_zero_modifier(self, client):
        # un nemico non ha scheda: mod = 0, range [1, 20]
        with client.websocket_connect("/ws/session/1") as ws:
            ws.receive_json()
            ws.send_json({"type": "enemy_add", "payload": {
                "token_id": "enemy:1", "name": "Goblin", "max_hp": 7}})
            ws.receive_json()
            ws.send_json({"type": "roll_initiative",
                          "payload": {"token_id": "enemy:1"}})
            snap = ws.receive_json()
            init = snap["state"]["enemies"][0]["initiative"]
            assert init is not None
            assert 1 <= init <= 20

    def test_roll_initiative_unknown_token_returns_error(self, client):
        with client.websocket_connect("/ws/session/1") as ws:
            ws.receive_json()
            ws.send_json({"type": "roll_initiative",
                          "payload": {"token_id": "pc:9999"}})
            err = ws.receive_json()
            assert err["type"] == "error"

    def test_roll_all_initiative_rolls_for_everyone(self, client):
        # tira per ogni token in sessione: PG e nemici
        a = _make_character(client, name="A")
        b = _make_character(client, name="B")
        with client.websocket_connect("/ws/session/1") as ws:
            ws.receive_json()
            for cid in (a, b):
                ws.send_json({"type": "add_participant",
                              "payload": {"character_id": cid}})
                ws.receive_json()
            ws.send_json({"type": "enemy_add", "payload": {
                "token_id": "enemy:1", "name": "Goblin", "max_hp": 7}})
            ws.receive_json()

            ws.send_json({"type": "roll_all_initiative", "payload": {}})
            snap = ws.receive_json()
            pcs = snap["state"]["participants"]
            enemies = snap["state"]["enemies"]
            assert all(p["initiative"] is not None for p in pcs)
            assert all(e["initiative"] is not None for e in enemies)
            # feed contiene un tiro per ciascuno (2 PG + 1 nemico)
            assert len(snap["state"]["roll_feed"]) == 3

    def test_roll_all_initiative_on_empty_room_is_noop(self, client):
        # nessun token: il broadcast deve comunque arrivare, niente errori
        with client.websocket_connect("/ws/session/1") as ws:
            ws.receive_json()
            ws.send_json({"type": "roll_all_initiative", "payload": {}})
            snap = ws.receive_json()
            assert snap["type"] == "snapshot"
            assert snap["state"]["participants"] == []
            assert snap["state"]["enemies"] == []
