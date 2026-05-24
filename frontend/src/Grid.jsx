// Griglia di combattimento — il "feltro di cartone" (DECISIONS.md D14).
//
// Superficie muta: disegna una griglia gridSize x gridSize e ci posa sopra le
// pedine. NON conosce distanze, portate, regole. Conta solo "dove" sta una
// pedina. Il conteggio delle caselle lo fa l'occhio del DM.
//
// Pedine = iniziale puntata. Verde i PG, rosso i nemici.
//
// Props:
//   tokens   -> [{ token_id, name, position:{x,y}|null, is_enemy }]
//   gridSize -> intero (8 in v0)
//   onCellTap(x, y) -> chiamato al tap su una cella; usato per spostare
//                      la pedina selezionata. Se assente, griglia in sola lettura.
//   selectedId -> token_id della pedina selezionata (bordo oro)
//   activeId   -> token_id della pedina di TURNO (alone giallo lampeggiante);
//                 distinto dalla selezione per non confondere i due stati.
//   onTokenTap(token_id) -> chiamato al tap su una pedina (per selezionarla)
//   canMove(token_id) -> ritorna true se quella pedina e' spostabile
//                        (il master puo' tutte, il giocatore solo la propria)

function tokenInitial(name) {
  return (name || '?').trim().charAt(0).toUpperCase()
}

export default function Grid({
  tokens = [],
  gridSize = 8,
  onCellTap,
  selectedId = null,
  activeId = null,
  onTokenTap,
  canMove = () => true,
}) {
  // mappa "x,y" -> token, per sapere cosa c'e' su ogni cella
  const byCell = {}
  for (const t of tokens) {
    if (t.position) byCell[`${t.position.x},${t.position.y}`] = t
  }

  const cells = []
  for (let y = 0; y < gridSize; y++) {
    for (let x = 0; x < gridSize; x++) {
      const token = byCell[`${x},${y}`]
      // scacchiera: due tonalita' di legno alternate
      const dark = (x + y) % 2 === 0
      cells.push(
        <div
          key={`${x},${y}`}
          onClick={() => onCellTap && onCellTap(x, y)}
          style={{
            aspectRatio: '1',
            background: dark ? '#1c1813' : '#211c16',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            cursor: onCellTap ? 'pointer' : 'default',
          }}
        >
          {token && (
            <TokenChip
              token={token}
              selected={token.token_id === selectedId}
              active={token.token_id === activeId}
              movable={canMove(token.token_id)}
              onTap={() => onTokenTap && onTokenTap(token.token_id)}
            />
          )}
        </div>
      )
    }
  }

  return (
    <div style={{
      display: 'grid',
      gridTemplateColumns: `repeat(${gridSize}, 1fr)`,
      gap: 2, background: '#3a3225', border: '1px solid #3a3225',
      borderRadius: 8, padding: 2,
    }}>
      {cells}
    </div>
  )
}

// Palette delle pedine: il colore arriva dal backend (token.color).
// Fallback su green/red in base a is_enemy per snapshot vecchi.
const TOKEN_PALETTE = {
  green: { bg: '#3a4a2e', border: '#5f7d4a', text: '#cfe0bb' },
  red:   { bg: '#4a2e26', border: '#a3372e', text: '#e8b5ad' },
  blue:  { bg: '#2e3a4a', border: '#4a6a8a', text: '#b5c8e8' },
}
export function tokenPalette(token) {
  const key = token.color || (token.is_enemy ? 'red' : 'green')
  return TOKEN_PALETTE[key] || TOKEN_PALETTE.green
}

function TokenChip({ token, selected, active, movable, onTap }) {
  const palette = tokenPalette(token)
  return (
    <div
      onClick={(e) => { e.stopPropagation(); onTap && onTap() }}
      title={token.name}
      style={{
        width: '80%', height: '80%', borderRadius: '50%',
        background: palette.bg,
        border: `${selected ? 2.5 : 1.5}px solid ${
          selected ? '#e0a23a' : palette.border}`,
        // alone giallo per la pedina di turno (distinto dal bordo oro
        // pieno della selezione: l'alone "respira" attorno alla pedina)
        boxShadow: active ? '0 0 0 3px #f4c95d, 0 0 8px 2px #f4c95daa' : 'none',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        fontSize: 12, fontWeight: 700,
        color: palette.text,
        fontFamily: 'Cinzel, serif',
        cursor: movable ? 'pointer' : 'default',
        opacity: movable ? 1 : 0.75,
      }}
    >
      {tokenInitial(token.name)}
    </div>
  )
}
