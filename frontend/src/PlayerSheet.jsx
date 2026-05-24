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

  // Quando il master modifica la scheda (level-up, loot, ...) il server
  // emette un messaggio WS `character_updated`: aggiorniamo char senza
  // dover ri-fetchare via REST.
  const { state, status, sendEvent, lastError } = useSession(SESSION_ID, {
    onCharacterUpdated: (payload) => {
      if (payload && String(payload.character_id) === String(characterId)) {
        setChar(payload.character)
      }
    },
  })

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

  // Scheda incompleta: il master ha creato il PG con solo nome+livello,
  // tocca al giocatore scegliere classe/HP/attributi dal proprio telefono.
  const needsSetup = !char.class

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

      {needsSetup && <SheetSetup char={char} characterId={characterId} />}

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

      <Inventory items={char.inventory || []} />

      <RollFeed feed={state?.roll_feed ?? []} />
    </div>
  )
}

// 12 classi SRD (slug minuscoli, gli stessi della tabella srd_classes).
// Hardcoded perche' l'insieme cambia raramente; il backend resta la fonte
// autoritativa per il dado vita via lookup (D17).
const SRD_CLASSES = [
  'barbarian', 'bard', 'cleric', 'druid', 'fighter', 'monk',
  'paladin', 'ranger', 'rogue', 'sorcerer', 'warlock', 'wizard',
]

// Setup iniziale di una scheda creata dal master con solo nome + livello.
// Il giocatore sceglie classe / razza / attributi / HP / AC e fa Submit:
// PATCH al backend, character_updated propaga, il banner sparisce e la
// scheda diventa giocabile.
function SheetSetup({ char, characterId }) {
  const [draft, setDraft] = useState(() => ({
    class: 'fighter',
    race: '',
    str: 10, dex: 10, con: 10, int: 10, wis: 10, cha: 10,
    max_hp: 10,
    armor_class: 10,
  }))
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState(null)

  function set(field, value) {
    setDraft((d) => ({ ...d, [field]: value }))
  }
  function setNum(field, value, min = 1, max = 30) {
    const n = Math.max(min, Math.min(max, Number(value) || 0))
    set(field, n)
  }

  async function submit() {
    setSaving(true); setError(null)
    const resp = await fetch(`/api/characters/${characterId}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        ...draft,
        // alla creazione partiamo pieni di HP
        current_hp: draft.max_hp,
      }),
    })
    setSaving(false)
    if (!resp.ok) {
      setError(`Errore salvataggio (${resp.status})`)
      return
    }
    // il character_updated WS aggiornera' `char` da solo, niente da fare
  }

  return (
    <div className="card" style={{
      borderColor: 'var(--candle)', padding: 14, marginBottom: 16,
    }}>
      <div style={{ fontFamily: 'Cinzel, serif', fontSize: 16,
                     color: 'var(--candle)', marginBottom: 6 }}>
        Completa la tua scheda
      </div>
      <div className="muted" style={{ fontSize: 12, marginBottom: 12 }}>
        Il DM ha creato {char.name} di livello {char.level}. Scegli classe,
        attributi e punti ferita.
      </div>

      <SetupRow label="Classe">
        <select value={draft.class}
                onChange={(e) => set('class', e.target.value)}
                style={inputStyle}>
          {SRD_CLASSES.map((c) => (
            <option key={c} value={c}>{c}</option>
          ))}
        </select>
      </SetupRow>

      <SetupRow label="Razza (libera)">
        <input value={draft.race}
                onChange={(e) => set('race', e.target.value)}
                placeholder="es. elf, halfling, human..."
                style={inputStyle} />
      </SetupRow>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)',
                    gap: 6, margin: '8px 0' }}>
        {[['FOR','str'], ['DES','dex'], ['COS','con'],
          ['INT','int'], ['SAG','wis'], ['CAR','cha']].map(([n, f]) => (
          <div key={f} style={{ textAlign: 'center' }}>
            <div style={{ fontSize: 11, color: 'var(--ink-faint)' }}>{n}</div>
            <input type="number" value={draft[f]} min={1} max={30}
                    onChange={(e) => setNum(f, e.target.value, 1, 30)}
                    style={{ ...inputStyle, textAlign: 'center', padding: 4 }} />
            <div className="muted" style={{ fontSize: 10 }}>
              mod {fmtMod(abilityMod(draft[f]))}
            </div>
          </div>
        ))}
      </div>

      <div style={{ display: 'flex', gap: 8 }}>
        <SetupRow label="HP max" style={{ flex: 1 }}>
          <input type="number" value={draft.max_hp} min={1} max={999}
                  onChange={(e) => setNum('max_hp', e.target.value, 1, 999)}
                  style={inputStyle} />
        </SetupRow>
        <SetupRow label="CA" style={{ flex: 1 }}>
          <input type="number" value={draft.armor_class} min={1} max={30}
                  onChange={(e) => setNum('armor_class', e.target.value, 1, 30)}
                  style={inputStyle} />
        </SetupRow>
      </div>

      <button onClick={submit} disabled={saving} style={{
        width: '100%', marginTop: 10,
        background: 'var(--candle-dim)', color: 'var(--bg)',
        border: 'none', borderRadius: 8, padding: '10px 12px',
        fontFamily: 'Cinzel, serif', fontSize: 14,
        cursor: saving ? 'wait' : 'pointer',
      }}>
        {saving ? 'Salvo…' : 'Salva e gioca'}
      </button>
      {error && (
        <div className="muted" style={{ fontSize: 12, marginTop: 8,
                                         color: 'var(--blood)' }}>
          {error}
        </div>
      )}
    </div>
  )
}

function SetupRow({ label, children, style }) {
  return (
    <div style={{ marginBottom: 8, ...style }}>
      <div className="muted" style={{ fontSize: 11, marginBottom: 2 }}>
        {label}
      </div>
      {children}
    </div>
  )
}

const inputStyle = {
  width: '100%', boxSizing: 'border-box',
  background: 'var(--bg)', color: 'var(--ink)',
  border: '1px solid var(--line)', borderRadius: 6,
  padding: '6px 8px', fontSize: 14,
}

// Inventario: lista semplice di item ricevuti dal master come loot.
// Solo nome (+ descrizione opzionale): non e' un motore di regole (D2),
// gli effetti meccanici li arbitra il DM.
function Inventory({ items }) {
  if (!items || items.length === 0) {
    return (
      <>
        <h3 style={{ fontSize: 15, margin: '18px 0 10px',
                      color: 'var(--ink-dim)' }}>
          Inventario
        </h3>
        <div className="muted" style={{ fontSize: 13 }}>
          Vuoto. Quando il DM ti darà del bottino comparirà qui.
        </div>
      </>
    )
  }
  return (
    <>
      <h3 style={{ fontSize: 15, margin: '18px 0 10px',
                    color: 'var(--ink-dim)' }}>
        Inventario
      </h3>
      {items.map((it, i) => (
        <div key={i} className="card" style={{ padding: '8px 12px' }}>
          <div style={{ fontFamily: 'Cinzel, serif', fontSize: 14,
                         color: 'var(--candle)' }}>
            {it.name}
          </div>
          {it.description && (
            <div className="muted" style={{ fontSize: 12, marginTop: 4 }}>
              {it.description}
            </div>
          )}
        </div>
      ))}
    </>
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
