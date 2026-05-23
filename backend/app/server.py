"""Server FastAPI di pocket-dnd: REST per i personaggi + WebSocket per il live.

Architettura (DECISIONS.md D5):
  - REST  -> CRUD personaggi, sopra CharacterRepo (persistenza SQLite).
  - WS    -> una connessione per device, raggruppate per sessione in una Room.
            La Room e' la fonte autoritativa; ogni evento applicato fa
            ri-broadcast dello snapshot intero a tutti i device della sessione.

Perche' si ri-manda lo snapshot intero e non un delta: i telefoni vanno in
standby e le socket cadono di continuo (AP6). Mandare sempre lo stato completo
rende il reconnect banale — il client non deve ricostruire nulla, gli basta
sostituire il proprio stato con l'ultimo snapshot ricevuto.

Lo stato live NON e' persistito: vive nel RoomManager in memoria finche' il
processo e' vivo. SQLite serve solo alla persistenza tra sessioni.
"""
from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.characters import (
    CharacterRepo,
    CharacterNotFound,
    ImportError as CharImportError,
)
from app.dice import roll, Advantage, DiceError
from app.rooms import RoomManager, RoomEvent, UnknownEvent
from app.rules import ability_modifier


def _find_token(snapshot: dict, token_id: str | None) -> dict | None:
    """Cerca un token (PG o nemico) nello snapshot per token_id."""
    if token_id is None:
        return None
    for t in (*snapshot["participants"], *snapshot["enemies"]):
        if t["token_id"] == token_id:
            return t
    return None


def _apply_initiative_roll(room, repo: CharacterRepo, token: dict) -> None:
    """Tira l'iniziativa per UNA pedina e applica gli effetti sulla room.

    Per i PG il modificatore e' mod_DEX (letto dal repo); per i nemici e' 0
    (non hanno scheda). Il tiro va anche nel feed: il master vede chi ha
    tirato cosa, come per ogni altro tiro fatto dal server (D13).
    """
    cid = token.get("character_id")
    if cid is not None:
        try:
            character = repo.get(cid)
            mod = ability_modifier(character["dex"])
        except (CharacterNotFound, ValueError):
            mod = 0
    else:
        mod = 0

    sign = "+" if mod >= 0 else "-"
    formula = f"1d20{sign}{abs(mod)}" if mod else "1d20"
    result = roll(formula)
    room.apply(RoomEvent("initiative_set", {
        "token_id": token["token_id"], "initiative": result.total}))
    room.apply(RoomEvent("roll", {
        "character_id": cid,
        "label": f"Iniziativa ({token['name']})",
        "formula": formula,
        "result": result.total,
        "breakdown": result.breakdown,
    }))


def _resolve_roll(payload: dict) -> "RoomEvent":
    """Trasforma un `roll_request` (intento) in un evento `roll` (risultato).

    Il dado lo tira il server (D13): cosi' il risultato e' unico e visibile
    identico a tutti. Solleva DiceError se la formula e' malformata.
    """
    formula = payload.get("formula", "")
    adv_raw = payload.get("advantage", "normal")
    try:
        advantage = Advantage(adv_raw)
    except ValueError:
        advantage = Advantage.NORMAL

    result = roll(formula, advantage=advantage)
    return RoomEvent("roll", {
        "character_id": payload.get("character_id"),
        "label": payload.get("label", ""),
        "formula": formula,
        "result": result.total,
        "breakdown": result.breakdown,
    })


def create_app(db_path: str, schema_sql: str,
               static_dir: str | None = None) -> FastAPI:
    """Costruisce l'app. db_path e schema sono iniettati per i test
    (':memory:' in test, un file vero in produzione).

    static_dir: se valorizzato e la dir esiste, il backend serve anche la
    SPA buildata da li' — un binario, una porta (modalita' pub e container).
    Se None o dir inesistente, il backend e' solo REST+WS (modalita' dev
    col Vite dev server che proxa).
    """
    app = FastAPI(title="pocket-dnd")

    repo = CharacterRepo(db_path)
    repo.init_schema(schema_sql)

    rooms = RoomManager()
    # connessioni WebSocket attive, raggruppate per session_id
    connections: dict[int, set[WebSocket]] = {}

    # ─────────────────────────── health ───────────────────────────

    @app.get("/health")
    def health():
        return {"status": "ok"}

    # ─────────────────────── REST personaggi ───────────────────────

    @app.get("/api/characters")
    def list_characters():
        return repo.list_all()

    @app.post("/api/characters", status_code=201)
    def create_character(data: dict):
        try:
            cid = repo.create(data)
        except ValueError as e:
            raise HTTPException(status_code=422, detail=str(e))
        return {"id": cid}

    @app.get("/api/characters/{character_id}")
    def get_character(character_id: int):
        try:
            return repo.get(character_id)
        except CharacterNotFound:
            raise HTTPException(status_code=404, detail="personaggio inesistente")

    @app.patch("/api/characters/{character_id}")
    def update_character(character_id: int, changes: dict):
        try:
            repo.update(character_id, changes)
        except CharacterNotFound:
            raise HTTPException(status_code=404, detail="personaggio inesistente")
        return repo.get(character_id)

    @app.delete("/api/characters/{character_id}", status_code=204)
    def delete_character(character_id: int):
        try:
            repo.delete(character_id)
        except CharacterNotFound:
            raise HTTPException(status_code=404, detail="personaggio inesistente")

    @app.get("/api/characters/{character_id}/export")
    def export_character(character_id: int):
        try:
            return repo.export_character(character_id)
        except CharacterNotFound:
            raise HTTPException(status_code=404, detail="personaggio inesistente")

    @app.post("/api/characters/{character_id}/level-up")
    def level_up_character(character_id: int, body: dict | None = None):
        """Level-up assistito (D3, D16). Payload opzionale:
            { "extended": { ...campi liberi del giocatore... } }
        I campi vengono mergiati nel guscio inerte."""
        patch = (body or {}).get("extended")
        try:
            summary = repo.level_up(character_id, extended_patch=patch)
        except CharacterNotFound:
            raise HTTPException(status_code=404, detail="personaggio inesistente")
        except ValueError as e:
            raise HTTPException(status_code=422, detail=str(e))
        return {"summary": summary, "character": repo.get(character_id)}

    @app.post("/api/characters/import", status_code=201)
    def import_character(payload: dict):
        try:
            cid = repo.import_character(payload)
        except CharImportError as e:
            raise HTTPException(status_code=422, detail=str(e))
        return {"id": cid}

    # ─────────────────────── WebSocket live ───────────────────────

    async def _broadcast(session_id: int, room) -> None:
        """Manda lo snapshot corrente a tutti i device della sessione.

        I device morti vengono rimossi: una send fallita significa socket
        chiusa. Non e' un errore — e' il telefono che e' andato in standby.
        """
        message = {"type": "snapshot", "state": room.snapshot()}
        dead: list[WebSocket] = []
        for ws in connections.get(session_id, set()):
            try:
                await ws.send_json(message)
            except Exception:
                dead.append(ws)
        for ws in dead:
            connections[session_id].discard(ws)

    @app.websocket("/ws/session/{session_id}")
    async def session_socket(websocket: WebSocket, session_id: int):
        await websocket.accept()
        room = rooms.get_or_create(session_id)
        connections.setdefault(session_id, set()).add(websocket)

        # appena connesso: lo snapshot intero. Vale sia per la prima
        # connessione sia per ogni reconnect (D5 / AP6).
        await websocket.send_json({"type": "snapshot", "state": room.snapshot()})

        try:
            while True:
                raw = await websocket.receive_json()
                msg_type = raw.get("type", "")
                payload = raw.get("payload", {})

                # roll_request: il client manda l'intento, il SERVER tira
                # il dado (D13) e lo trasforma in un evento `roll` normale.
                if msg_type == "roll_request":
                    try:
                        event = _resolve_roll(payload)
                    except DiceError as e:
                        await websocket.send_json({"type": "error", "detail": str(e)})
                        continue
                # add_participant: bisogna leggere dal CharacterRepo,
                # cosa che la Room pura non puo' fare. Si applica qui,
                # non passando da room.apply().
                elif msg_type == "add_participant":
                    cid = payload.get("character_id")
                    try:
                        character = repo.get(cid)
                    except CharacterNotFound as e:
                        await websocket.send_json({"type": "error", "detail": str(e)})
                        continue
                    room.add_participant(
                        character_id=character["id"],
                        name=character["name"],
                        current_hp=character["current_hp"],
                        max_hp=character["max_hp"],
                    )
                    await _broadcast(session_id, room)
                    continue
                # roll_initiative: il server tira 1d20 + mod_DEX (PG) o 1d20
                # (nemici). Applica initiative_set + log nel feed.
                elif msg_type == "roll_initiative":
                    tid = payload.get("token_id")
                    snap = room.snapshot()
                    tok = _find_token(snap, tid)
                    if tok is None:
                        await websocket.send_json({"type": "error",
                            "detail": f"pedina inesistente: {tid!r}"})
                        continue
                    _apply_initiative_roll(room, repo, tok)
                    await _broadcast(session_id, room)
                    continue
                # roll_all_initiative: comodita' per il master, tira per ogni
                # pedina (PG e nemici) e fa un solo broadcast finale.
                elif msg_type == "roll_all_initiative":
                    snap = room.snapshot()
                    for tok in (*snap["participants"], *snap["enemies"]):
                        _apply_initiative_roll(room, repo, tok)
                    await _broadcast(session_id, room)
                    continue
                else:
                    event = RoomEvent(type=msg_type, payload=payload)

                try:
                    room.apply(event)
                except UnknownEvent as e:
                    # evento ignoto: si segnala l'errore SOLO al mittente,
                    # senza chiudere la socket e senza toccare lo stato.
                    await websocket.send_json({"type": "error", "detail": str(e)})
                    continue
                # evento valido: ri-broadcast a tutti
                await _broadcast(session_id, room)
        except WebSocketDisconnect:
            connections[session_id].discard(websocket)

    # ────────────────── SPA statica (modalita' container/pub) ──────────────────
    # Va montata DOPO le route API/WS cosi' il catch-all non le intercetta.
    if static_dir:
        static_path = Path(static_dir)
        if static_path.is_dir():
            assets_dir = static_path / "assets"
            if assets_dir.is_dir():
                app.mount("/assets", StaticFiles(directory=assets_dir),
                          name="assets")
            index_html = static_path / "index.html"

            @app.get("/{full_path:path}")
            def spa_fallback(full_path: str):
                # rotte non-API: serviamo l'index della SPA. Il router del
                # client (react-router) si occupa di mostrare la pagina giusta.
                # /assets/* e' gia' montato sopra e non passa di qua.
                candidate = static_path / full_path
                if full_path and candidate.is_file():
                    return FileResponse(candidate)
                return FileResponse(index_html)

    # repo accessibile ai test che ne avessero bisogno
    app.state.repo = repo
    app.state.rooms = rooms
    return app
