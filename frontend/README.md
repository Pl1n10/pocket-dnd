# pocket-dnd — frontend

React + Vite, mobile-first. Direzione estetica: "tavern-dark" (vedi index.css).

## Sviluppo

```bash
npm install
npm run dev          # http://localhost:5173, proxa /api e /ws al backend :8000
```

Serve il backend acceso in parallelo (`cd ../backend && python3 main.py`).

## Build

```bash
npm run build        # genera dist/ — file statici serviti poi dal backend
```

## Struttura

- `src/main.jsx`       — entry + routing
- `src/PlayerSheet.jsx`— scheda del giocatore (vista mobile)
- `src/useSession.js`  — hook WebSocket con reconnect automatico
- `src/index.css`      — stile globale, palette tavern-dark

## Note

- v0: sessione di gioco con id fisso (1). Multi-sessione: step futuro.
- Il dado lo tira il server (DECISIONS.md D13): il client manda `roll_request`.
- La consolle master (`/master`) arriva allo Step 6.
