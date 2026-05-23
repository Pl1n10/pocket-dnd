import { useEffect, useState } from 'react'
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
  const [roster, setRoster] = useState([])

  // catalogo dei PG persistenti, per la sezione "Aggiungi alla sessione"
  useEffect(() => {
    fetch('/api/characters')
      .then((r) => (r.ok ? r.json() : []))
      .then(setRoster)
      .catch(() => setRoster([]))
  }, [])

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
  const activeId = state.active_token_id
  // PG persistenti che NON sono ancora stati portati in sessione
  const inSessionIds = new Set(participants.map((p) => p.character_id))
  const availableToAdd = roster.filter((c) => !inSessionIds.has(c.id))

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

  // Crea un PG nuovo al volo (per il giocatore che arriva al tavolo dopo)
  // e lo aggiunge subito alla sessione. Solo i campi minimi: il resto si
  // edita poi dalla scheda /player/:id o ricaricando lo script di seed.
  async function newPlayer() {
    const name = window.prompt('Nome del personaggio?', '')
    if (!name || !name.trim()) return
    const cls = (window.prompt(
      'Classe SRD? (fighter, wizard, rogue, cleric, bard, ranger, ' +
      'barbarian, sorcerer, paladin, monk, druid, warlock)',
      'fighter') || 'fighter').toLowerCase().trim()
    const level = Number(window.prompt('Livello?', '1')) || 1
    const maxHp = Number(window.prompt('Punti ferita massimi?', '10')) || 10
    const resp = await fetch('/api/characters', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        name: name.trim(), class: cls, level,
        max_hp: maxHp, current_hp: maxHp,
        armor_class: 12,
      }),
    })
    if (!resp.ok) {
      window.alert(`Errore creando il PG (${resp.status})`)
      return
    }
    const { id } = await resp.json()
    // ricarica la lista PG e mette subito in sessione il nuovo arrivato
    const list = await fetch('/api/characters').then((r) => r.json())
    setRoster(list)
    sendEvent('add_participant', { character_id: id })
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

      <h3 style={sectionTitle}>Combattimento</h3>
      <div style={{ display: 'flex', gap: 8, marginBottom: 12 }}>
        <button onClick={() => sendEvent('roll_all_initiative', {})}
                style={actionBtn}>
          Tira iniziativa
        </button>
        <button onClick={() => sendEvent('next_turn', {})}
                style={{ ...actionBtn, background: 'var(--candle-dim)',
                          color: 'var(--bg)' }}>
          Turno successivo →
        </button>
      </div>
      {activeId && (
        <div className="muted" style={{ fontSize: 13, marginBottom: 12 }}>
          Tocca a: <strong style={{ color: 'var(--candle)' }}>
            {tokenLabel(allTokens, activeId)}
          </strong>
        </div>
      )}

      <DmDice activeName={activeId ? tokenLabel(allTokens, activeId) : null}
              sendEvent={sendEvent} />

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
          activeId={activeId}
          onTokenTap={(id) => setSelectedToken(id === selectedToken ? null : id)}
          onCellTap={moveSelectedTo}
        />
      </div>

      <div style={{ display: 'flex', justifyContent: 'space-between',
                    alignItems: 'center', margin: '18px 0 10px' }}>
        <h3 style={{ ...sectionTitle, margin: 0 }}>Eroi</h3>
        <button onClick={newPlayer} style={{
          background: 'var(--bg-card-2)', color: 'var(--candle)',
          border: '1px solid var(--candle-dim)', borderRadius: 8,
          padding: '6px 12px', fontFamily: 'Cinzel, serif', fontSize: 13,
          cursor: 'pointer',
        }}>+ nuovo PG</button>
      </div>
      {participants.length === 0 && (
        <div className="muted" style={{ fontSize: 13, marginBottom: 8 }}>
          Nessun eroe in sessione. Aggiungine uno qui sotto.
        </div>
      )}
      {participants.map((p) => (
        <TokenRow key={p.token_id} token={p} onHp={changeHp}
                  isActive={p.token_id === activeId} />
      ))}
      {availableToAdd.length > 0 && (
        <div style={{ marginTop: 10 }}>
          <div className="muted" style={{ fontSize: 12, marginBottom: 6 }}>
            Aggiungi alla sessione:
          </div>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
            {availableToAdd.map((c) => (
              <button key={c.id}
                      onClick={() => sendEvent('add_participant',
                                                { character_id: c.id })}
                      style={pillBtn}>
                + {c.name}
              </button>
            ))}
          </div>
        </div>
      )}

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
                  isActive={e.token_id === activeId}
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

const actionBtn = {
  flex: 1,
  background: 'var(--bg-card-2)', color: 'var(--candle)',
  border: '1px solid var(--candle-dim)', borderRadius: 8,
  padding: '10px 12px', fontFamily: 'Cinzel, serif', fontSize: 14,
  cursor: 'pointer',
}

const pillBtn = {
  background: 'var(--bg-card-2)', color: 'var(--ink)',
  border: '1px solid var(--line)', borderRadius: 16,
  padding: '4px 12px', fontSize: 12, cursor: 'pointer',
}

function tokenLabel(tokens, id) {
  const t = tokens.find((x) => x.token_id === id)
  return t ? t.name : id
}

// Dadi del DM: tiri rapidi (d20 con vantaggio/svantaggio, dadi base per i
// danni dei mostri) + una formula libera. Il dado lo tira il server (D13),
// quindi qui mandiamo solo l'intento via roll_request. Il risultato finisce
// nel feed visibile a tutti, esattamente come i tiri dei giocatori.
function DmDice({ activeName, sendEvent }) {
  const [formula, setFormula] = useState('')
  // se c'e' una pedina di turno (di solito un mostro quando tocca al DM),
  // l'etichetta del tiro la prefissa col suo nome — cosi' il feed dice
  // "Goblin · d20" invece di "DM · d20"
  const who = activeName || 'DM'

  function tira(f, suffix = '') {
    sendEvent('roll_request', {
      label: `${who} · ${suffix || f}`,
      formula: f,
    })
  }
  function tiraD20(adv) {
    sendEvent('roll_request', {
      label: `${who} · d20${adv === 'advantage' ? ' ↑' : adv === 'disadvantage' ? ' ↓' : ''}`,
      formula: '1d20',
      advantage: adv,
    })
  }
  function tiraCustom() {
    const f = formula.trim()
    if (!f) return
    tira(f)
    setFormula('')
  }

  return (
    <div className="card" style={{ padding: 10, marginBottom: 12 }}>
      <div className="muted" style={{ fontSize: 12, marginBottom: 8 }}>
        Dadi del DM {activeName && `— per ${activeName}`}
      </div>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginBottom: 8 }}>
        <button style={dieBtn} onClick={() => tiraD20('normal')}>d20</button>
        <button style={dieBtn} onClick={() => tiraD20('advantage')}>d20 ↑</button>
        <button style={dieBtn} onClick={() => tiraD20('disadvantage')}>d20 ↓</button>
        <span style={{ width: 8 }} />
        {[4, 6, 8, 10, 12].map((n) => (
          <button key={n} style={dieBtn} onClick={() => tira(`1d${n}`)}>d{n}</button>
        ))}
      </div>
      <div style={{ display: 'flex', gap: 6 }}>
        <input value={formula}
               onChange={(e) => setFormula(e.target.value)}
               onKeyDown={(e) => { if (e.key === 'Enter') tiraCustom() }}
               placeholder="es. 2d6+3"
               style={{
                 flex: 1,
                 background: 'var(--bg)', color: 'var(--ink)',
                 border: '1px solid var(--line)', borderRadius: 6,
                 padding: '6px 10px', fontFamily: 'monospace', fontSize: 13,
               }} />
        <button onClick={tiraCustom} style={{ ...dieBtn, minWidth: 60 }}>
          Tira
        </button>
      </div>
    </div>
  )
}

const dieBtn = {
  background: 'var(--bg-card-2)', color: 'var(--ink)',
  border: '1px solid var(--line)', borderRadius: 6,
  padding: '6px 12px', fontFamily: 'Cinzel, serif', fontSize: 13,
  cursor: 'pointer',
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
// isActive evidenzia chi sta giocando il proprio turno.
function TokenRow({ token, onHp, onRemove, isActive = false }) {
  const pct = token.max_hp > 0
    ? Math.max(0, Math.min(100, (token.current_hp / token.max_hp) * 100))
    : 0
  return (
    <div className="card" style={{
      padding: '10px 12px',
      border: isActive ? '1px solid #f4c95d' : undefined,
      boxShadow: isActive ? '0 0 8px #f4c95d55' : undefined,
    }}>
      <div style={{ display: 'flex', justifyContent: 'space-between',
                    alignItems: 'center', marginBottom: 8 }}>
        <span style={{ fontFamily: 'Cinzel, serif', fontSize: 15 }}>
          {isActive && <span style={{ marginRight: 6 }}>▶</span>}
          {token.name}
          {token.initiative != null && (
            <span className="muted" style={{ fontSize: 12, marginLeft: 8 }}>
              ini {token.initiative}
            </span>
          )}
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
