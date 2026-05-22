import { useState } from 'react'
import { useSession } from './useSession.js'
import Grid from './Grid.jsx'

// Consolle del master: vista d'insieme di tutta la sessione.
// Mostra tutte le pedine (PG + nemici), gli HP modificabili, la griglia di
// combattimento, l'ordine d'iniziativa e il feed dei tiri.
//
// Interazione griglia: il master tappa una pedina per selezionarla, poi tappa
// una cella per spostarcela. Il master puo' muovere TUTTE le pedine.

const SESSION_ID = 1

export default function MasterConsole() {
  const { state, status, sendEvent, lastError } = useSession(SESSION_ID)
  const [selectedToken, setSelectedToken] = useState(null)

  if (!state) {
    return (
      <div className="screen">
        <ConnBar status={status} />
        <div className="center muted">In attesa della sessione…</div>
      </div>
    )
  }

  const participants = state.participants || []
  const enemies = state.enemies || []
  const allTokens = [...participants, ...enemies]

  function moveSelectedTo(x, y) {
    if (!selectedToken) return
    sendEvent('move_token', { token_id: selectedToken, x, y })
    setSelectedToken(null)
  }

  function changeHp(token, delta) {
    const next = Math.max(0, Math.min(token.max_hp, token.current_hp + delta))
    sendEvent('hp_change', { token_id: token.token_id, current_hp: next })
  }

  function addEnemy() {
    const name = window.prompt('Nome del nemico?', 'Goblin')
    if (!name) return
    const hp = Number(window.prompt('Punti ferita?', '7')) || 1
    // token_id univoco basato sul tempo: i nemici non hanno un id persistente
    const tokenId = `enemy:${Date.now()}`
    sendEvent('enemy_add', { token_id: tokenId, name, max_hp: hp })
  }

  return (
    <div className="screen">
      <ConnBar status={status} />
      <h1 style={{ fontSize: 22, color: 'var(--candle)', marginBottom: 4 }}>
        Consolle del Master
      </h1>
      <div className="muted" style={{ fontSize: 13, marginBottom: 16 }}>
        {participants.length} eroi · {enemies.length} nemici
      </div>

      <h3 style={sectionTitle}>Griglia</h3>
      {selectedToken && (
        <div className="muted" style={{ fontSize: 13, marginBottom: 8 }}>
          Pedina selezionata — tocca una cella per spostarla.
        </div>
      )}
      <div style={{ marginBottom: 16 }}>
        <Grid
          tokens={allTokens}
          gridSize={state.grid_size || 8}
          selectedId={selectedToken}
          onTokenTap={(id) => setSelectedToken(id === selectedToken ? null : id)}
          onCellTap={moveSelectedTo}
        />
      </div>

      <h3 style={sectionTitle}>Eroi</h3>
      {participants.map((p) => (
        <TokenRow key={p.token_id} token={p} onHp={changeHp} />
      ))}

      <div style={{ display: 'flex', justifyContent: 'space-between',
                    alignItems: 'center', margin: '18px 0 10px' }}>
        <h3 style={{ ...sectionTitle, margin: 0 }}>Nemici</h3>
        <button onClick={addEnemy} style={{
          background: 'var(--bg-card-2)', color: 'var(--candle)',
          border: '1px solid var(--candle-dim)', borderRadius: 8,
          padding: '6px 12px', fontFamily: 'Cinzel, serif', fontSize: 13,
          cursor: 'pointer',
        }}>+ aggiungi</button>
      </div>
      {enemies.length === 0 && (
        <div className="muted" style={{ fontSize: 13, marginBottom: 12 }}>
          Nessun nemico sulla board.
        </div>
      )}
      {enemies.map((e) => (
        <TokenRow key={e.token_id} token={e}
                  onHp={changeHp}
                  onRemove={() => sendEvent('enemy_remove', { token_id: e.token_id })} />
      ))}

      {lastError && (
        <div className="card" style={{ borderColor: 'var(--blood)', marginTop: 12 }}>
          <span className="muted">Errore: {lastError}</span>
        </div>
      )}

      <RollFeed feed={state.roll_feed || []} />
    </div>
  )
}

// ─────────────────────────── sotto-componenti ───────────────────────────

const sectionTitle = {
  fontSize: 15, margin: '18px 0 10px', color: 'var(--ink-dim)',
}

function ConnBar({ status }) {
  const label = { open: 'connesso', connecting: 'connessione…',
                   reconnecting: 'riconnessione…' }[status] || status
  return (
    <div className={`conn ${status}`}>
      <span className="dot" />
      <span>{label}</span>
    </div>
  )
}

// Riga di una pedina nella lista: nome, HP con +/-, eventuale rimozione.
function TokenRow({ token, onHp, onRemove }) {
  const pct = token.max_hp > 0
    ? Math.max(0, Math.min(100, (token.current_hp / token.max_hp) * 100))
    : 0
  return (
    <div className="card" style={{ padding: '10px 12px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between',
                    alignItems: 'center', marginBottom: 8 }}>
        <span style={{ fontFamily: 'Cinzel, serif', fontSize: 15 }}>
          {token.name}
        </span>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <HpStepBtn label="−" onClick={() => onHp(token, -1)} />
          <span style={{ color: 'var(--candle)', minWidth: 56,
                         textAlign: 'center', fontSize: 14 }}>
            {token.current_hp}/{token.max_hp}
          </span>
          <HpStepBtn label="+" onClick={() => onHp(token, +1)} />
          {onRemove && (
            <button onClick={onRemove} style={{
              background: 'transparent', border: 'none',
              color: 'var(--ink-faint)', fontSize: 18, cursor: 'pointer',
              padding: '0 4px',
            }}>×</button>
          )}
        </div>
      </div>
      <div style={{ height: 6, background: 'var(--bg)', borderRadius: 3 }}>
        <div style={{
          height: '100%', width: `${pct}%`, borderRadius: 3,
          background: pct > 30 ? 'var(--moss)' : 'var(--blood)',
          transition: 'width 0.3s',
        }} />
      </div>
      {token.conditions && token.conditions.length > 0 && (
        <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginTop: 8 }}>
          {token.conditions.map((c) => (
            <span key={c} style={{
              background: 'var(--bg-card-2)', border: '1px solid var(--blood)',
              borderRadius: 5, padding: '2px 8px', fontSize: 11,
            }}>{c}</span>
          ))}
        </div>
      )}
    </div>
  )
}

function HpStepBtn({ label, onClick }) {
  return (
    <button onClick={onClick} style={{
      width: 34, height: 34, borderRadius: 8,
      background: 'var(--bg-card-2)', border: '1px solid var(--line)',
      color: 'var(--ink)', fontSize: 18, cursor: 'pointer',
      display: 'flex', alignItems: 'center', justifyContent: 'center',
    }}>{label}</button>
  )
}

function RollFeed({ feed }) {
  if (feed.length === 0) return null
  const recent = [...feed].slice(-8).reverse()
  return (
    <>
      <h3 style={sectionTitle}>Tiri della sessione</h3>
      {recent.map((r, i) => (
        <div key={i} className="card" style={{
          display: 'flex', justifyContent: 'space-between',
          alignItems: 'center', padding: '8px 14px', marginBottom: 6,
        }}>
          <div>
            <div style={{ fontFamily: 'Cinzel, serif', fontSize: 13 }}>{r.label}</div>
            <div className="muted" style={{ fontSize: 11 }}>{r.breakdown}</div>
          </div>
          <div style={{ fontSize: 20, fontFamily: 'Cinzel, serif',
                         color: 'var(--candle)' }}>{r.result}</div>
        </div>
      ))}
    </>
  )
}
