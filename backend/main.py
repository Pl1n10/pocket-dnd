"""Entrypoint di pocket-dnd.

Avvia il server FastAPI con un database SQLite su file.

  python3 main.py                       # default: pocket-dnd.db, porta 8000
  python3 main.py --port 9000           # porta custom
  python3 main.py --host 0.0.0.0        # esposto sulla LAN (modalita' pub)
  python3 main.py --static ../frontend/dist
                                        # serve anche la SPA buildata
                                        # (binario unico, container/pub)

Per la "modalita' pub" (laptop + hotspot, vedi CLAUDE.md) usare
--host 0.0.0.0 cosi' i telefoni in LAN possono collegarsi. In container
e' settato POCKETDND_STATIC=/app/dist via env.
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path

import uvicorn

from app.server import create_app

_DEFAULT_DB = "pocket-dnd.db"
_SCHEMA = Path(__file__).resolve().parent / "app" / "schema.sql"


def build():
    """Costruisce l'app con il DB di default — usato anche da uvicorn --reload."""
    return create_app(
        db_path=_DEFAULT_DB,
        schema_sql=_SCHEMA.read_text(encoding="utf-8"),
        static_dir=os.environ.get("POCKETDND_STATIC"),
    )


def main():
    parser = argparse.ArgumentParser(description="pocket-dnd server")
    parser.add_argument("--host", default="127.0.0.1",
                        help="indirizzo di ascolto (0.0.0.0 per la LAN)")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--db", default=_DEFAULT_DB, help="percorso del database SQLite")
    parser.add_argument("--static", default=os.environ.get("POCKETDND_STATIC"),
                        help="dir con la SPA buildata (es. ../frontend/dist); "
                              "se assente, il backend e' solo REST+WS")
    args = parser.parse_args()

    app = create_app(
        db_path=args.db,
        schema_sql=_SCHEMA.read_text(encoding="utf-8"),
        static_dir=args.static,
    )
    uvicorn.run(app, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
