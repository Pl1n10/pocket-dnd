import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import { useSession } from './useSession.js'
import Grid from './Grid.jsx'

// Scheda del giocatore: vista mobile del proprio personaggio.
// Mostra il NUCLEO VIVO (DECISIONS.md D8) — attributi, HP, azioni — non il
// guscio inerte. Ogni azione manda un `roll_request`: il dado lo tira il
// server (D13) e il risultato torna nel feed via snapshot.

// v0: una sola sessione di gioco, id fisso. Il multi-sessione arriva dopo.
const SESSION_ID = 1

// modificatore di un attributo: floor((score - 10) / 2)
function abilityMod(score) {
  return Math.floor((score - 10) / 2)
}
function fmtMod(m) {
  return m >= 0 ? `+${m}` : `${m}`
}

export default function PlayerSheet() {
  const { characterId } = useParams()
  const [char, setChar] = useState(null)
  const [loadError, setLoadError] = useState(null)
  const { state, status, sendEvent, lastError } = useSession(SESSION_ID)

  // carica la scheda persistente via REST (una volta)
  useEffect(() => {
    let alive = true
    fetch(`/api/characters/${characterId}`)
      .then((r) => {
        if (!r.ok) throw new Error(`personaggio non trovato (${r.status})`)
        return r.json()
      })
      .then((data) => { if (alive) setChar(data) })
      .catch((e) => { if (alive) setLoadError(e.message) })
    return () => { alive = false }
  }, [characterId])

  // lo stato di sessione del proprio personaggio (HP correnti, condizioni)
  // arriva dal WebSocket; se non c'e' ancora, si ripiega sui dati persistenti
  const liveSelf = state?.participants?.find(
    (p) => String(p.character_id) === String(characterId)
  )

  function rollAction(action) {
    sendEvent('roll_request', {
      character_id: Number(characterId),
      label: action.label,
      formula: action.formula,
    })
  }

  if (loadError) {
    return (
      <div className="screen">
        <ConnBar status={status} />
        <div className="center muted">{loadError}</div>
      </div>
    )
  }
  if (!char) {
    return (
      <div className="screen">
        <ConnBar status={status} />
        <div className="center muted">Carico la scheda…</div>
      </div>
    )
  }

  const hp = liveSelf ? liveSelf.current_hp : char.current_hp
  const maxHp = liveSelf ? liveSelf.max_hp : char.max_hp
  const conditions = liveSelf?.conditions ?? []
  const myTokenId = `pc:${characterId}`
  const isMyTurn = state?.active_token_id === myTokenId

  // le azioni "tirabili": gli attacchi della scheda + i tiri base
  const actions = buildActions(char)

  return (
    <div className="screen">
      <ConnBar status={status} />

      <header style={{ marginBottom: 16 }}>
        <h1 style={{ fontSize: 26, color: 'var(--candle)' }}>{char.name}</h1>
        <div className="muted" style={{ fontSize: 14 }}>
          {capitalize(char.race)} {capitalize(char.class)} · livello {char.level}
        </div>
      </header>

      {isMyTurn && (
        <div className="card" style={{
          background: '#f4c95d22', border: '1px solid #f4c95d',
          color: '#f4c95d', fontFamily: 'Cinzel, serif',
          textAlign: 'center', padding: '8px 12px', fontSize: 15,
        }}>
          ▶ Tocca a te
        </div>
      )}

      <HpBar hp={hp} maxHp={maxHp} />

      {conditions.length > 0 && (
        <div className="card" style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
          {conditions.map((c) => (
            <span key={c} style={{
              background: 'var(--bg-card-2)', border: '1px solid var(--blood)',
              borderRadius: 6, padding: '4px 10px', fontSize: 13,
            }}>{c}</span>
          ))}
        </div>
      )}

      <AbilityGrid char={char} />

      <BattleGrid state={state} characterId={characterId} sendEvent={sendEvent} />

      <h3 style={{ fontSize: 15, margin: '18px 0 10px', color: 'var(--ink-dim)' }}>
        Azioni
      </h3>
      {actions.map((a) => (
        <button key={a.label} className="btn" onClick={() => rollAction(a)}
                style={{ marginBottom: 8 }}>
          {a.label}
          <span style={{ float: 'right', color: 'var(--ink-faint)' }}>
            {a.formula}
          </span>
        </button>
      ))}

      {lastError && (
        <div className="card" style={{ borderColor: 'var(--blood)', marginTop: 12 }}>
          <span className="muted">Errore: {lastError}</span>
        </div>
      )}

      <RollFeed feed={state?.roll_feed ?? []} />
    </div>
  )
}

// ─────────────────────────── sotto-componenti ───────────────────────────

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

function HpBar({ hp, maxHp }) {
  const pct = maxHp > 0 ? Math.max(0, Math.min(100, (hp / maxHp) * 100)) : 0
  return (
    <div className="card">
      <div style={{ display: 'flex', justifyContent: 'space-between',
                    fontFamily: 'Cinzel, serif', marginBottom: 8 }}>
        <span>Punti ferita</span>
        <span style={{ color: 'var(--candle)' }}>{hp} / {maxHp}</span>
      </div>
      <div style={{ height: 10, background: 'var(--bg)', borderRadius: 5 }}>
        <div style={{
          height: '100%', width: `${pct}%`, borderRadius: 5,
          background: pct > 30 ? 'var(--moss)' : 'var(--blood)',
          transition: 'width 0.3s',
        }} />
      </div>
    </div>
  )
}

// La griglia vista dal giocatore: vede tutte le pedine ma puo' muovere solo
// la propria. Tap sulla propria pedina -> selezione; tap su una cella -> sposta.
function BattleGrid({ state, characterId, sendEvent }) {
  const [selected, setSelected] = useState(null)
  if (!state) return null

  const myTokenId = `pc:${characterId}`
  const allTokens = [...(state.participants || []), ...(state.enemies || [])]

  function moveTo(x, y) {
    if (selected !== myTokenId) return  // muove solo la propria
    sendEvent('move_token', { token_id: myTokenId, x, y })
    setSelected(null)
  }

  return (
    <div style={{ marginTop: 16 }}>
      <h3 style={{ fontSize: 15, margin: '0 0 10px', color: 'var(--ink-dim)' }}>
        Griglia
      </h3>
      {selected === myTokenId && (
        <div className="muted" style={{ fontSize: 13, marginBottom: 8 }}>
          Tocca una cella per spostare la tua pedina.
        </div>
      )}
      <Grid
        tokens={allTokens}
        gridSize={state.grid_size || 8}
        selectedId={selected}
        activeId={state.active_token_id}
        canMove={(id) => id === myTokenId}
        onTokenTap={(id) => {
          // selezionabile solo la propria pedina
          if (id === myTokenId) setSelected(id === selected ? null : id)
        }}
        onCellTap={moveTo}
      />
    </div>
  )
}

function AbilityGrid({ char }) {
  const abilities = [
    ['FOR', char.str], ['DES', char.dex], ['COS', char.con],
    ['INT', char.int], ['SAG', char.wis], ['CAR', char.cha],
  ]
  return (
    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)',
                  gap: 8 }}>
      {abilities.map(([name, score]) => (
        <div key={name} className="card" style={{ textAlign: 'center',
              padding: '10px 4px', margin: 0 }}>
          <div style={{ fontSize: 11, letterSpacing: '0.1em',
                        color: 'var(--ink-faint)' }}>{name}</div>
          <div style={{ fontSize: 22, fontFamily: 'Cinzel, serif',
                        color: 'var(--candle)' }}>{fmtMod(abilityMod(score))}</div>
          <div style={{ fontSize: 12, color: 'var(--ink-dim)' }}>{score}</div>
        </div>
      ))}
    </div>
  )
}

function RollFeed({ feed }) {
  if (feed.length === 0) return null
  // gli ultimi tiri in cima
  const recent = [...feed].slice(-6).reverse()
  return (
    <>
      <h3 style={{ fontSize: 15, margin: '18px 0 10px', color: 'var(--ink-dim)' }}>
        Ultimi tiri
      </h3>
      {recent.map((r, i) => (
        <div key={i} className="card" style={{
          display: 'flex', justifyContent: 'space-between',
          alignItems: 'center', padding: '10px 14px',
        }}>
          <div>
            <div style={{ fontFamily: 'Cinzel, serif', fontSize: 14 }}>{r.label}</div>
            <div className="muted" style={{ fontSize: 12 }}>{r.breakdown}</div>
          </div>
          <div style={{ fontSize: 24, fontFamily: 'Cinzel, serif',
                         color: 'var(--candle)' }}>{r.result}</div>
        </div>
      ))}
    </>
  )
}

// ─────────────────────────── helper ───────────────────────────

function capitalize(s) {
  if (!s) return ''
  return s.charAt(0).toUpperCase() + s.slice(1)
}

// Costruisce la lista di azioni tirabili da una scheda personaggio.
// Sempre presenti: i tiri base (per colpire generico, salvezza...). In piu':
// un'azione per ogni attacco nelle `actions` della scheda.
function buildActions(char) {
  const list = []
  // attacchi dalla scheda
  for (const a of char.actions || []) {
    if (a.to_hit_mod != null) {
      list.push({
        label: `${a.name} — colpire`,
        formula: `1d20${fmtMod(a.to_hit_mod)}`,
      })
    }
    if (a.damage_dice) {
      list.push({ label: `${a.name} — danno`, formula: a.damage_dice })
    }
  }
  // tiro base sempre disponibile
  list.push({ label: 'Tiro di prova (d20)', formula: '1d20' })
  return list
}
