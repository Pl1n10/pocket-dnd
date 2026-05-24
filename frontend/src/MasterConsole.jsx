import { useEffect, useState } from 'react'
import { QRCodeSVG } from 'qrcode.react'
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
  // url del PG di cui stiamo mostrando il QR (null = chiuso)
  const [qrUrl, setQrUrl] = useState(null)

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
  // Flusso: il master fissa solo nome e livello. Il PG nasce "vuoto"
  // (classe vuota = scheda da completare) e viene aggiunto subito alla
  // sessione, poi si apre il QR del link da passare al giocatore: l'amico
  // sceglie classe, attributi e HP dal proprio telefono nella scheda.
  async function newPlayer() {
    const name = window.prompt('Nome del personaggio?', '')
    if (!name || !name.trim()) return
    const level = Number(window.prompt('Livello?', '1')) || 1
    const resp = await fetch('/api/characters', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        name: name.trim(), level,
        // class vuota = trigger del setup-form lato PlayerSheet
        class: '',
        // valori segnaposto: l'amico li reimposta dal setup
        max_hp: 1, current_hp: 1, armor_class: 10,
      }),
    })
    if (!resp.ok) {
      window.alert(`Errore creando il PG (${resp.status})`)
      return
    }
    const { id } = await resp.json()
    await reloadRoster()
    sendEvent('add_participant', { character_id: id })
    // apri subito il QR con il link da passare al giocatore
    setQrUrl(playerUrl(id))
  }

  async function reloadRoster() {
    const list = await fetch('/api/characters').then((r) => r.json())
    setRoster(list)
  }

  async function deletePc(c) {
    if (!window.confirm(`Eliminare ${c.name} dal database? Operazione irreversibile.`)) return
    const resp = await fetch(`/api/characters/${c.id}`, { method: 'DELETE' })
    if (!resp.ok && resp.status !== 204) {
      window.alert(`Errore eliminando il PG (${resp.status})`)
      return
    }
    reloadRoster()
  }

  async function levelUpPc(token) {
    const notes = window.prompt(
      `Scelte di build per il livello ${(rosterFind(roster, token.character_id)?.level || 0) + 1} ` +
      `di ${token.name}: incantesimo, feat, sottoclasse… ` +
      `(vuoto per saltare)`, '')
    const body = notes && notes.trim()
      ? { extended: { [`level_up_notes_${Date.now()}`]: notes.trim() } }
      : {}
    const resp = await fetch(`/api/characters/${token.character_id}/level-up`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    })
    if (!resp.ok) {
      const err = await resp.json().catch(() => ({}))
      window.alert(`Errore: ${err.detail || resp.statusText}`)
      return
    }
    const data = await resp.json()
    reloadRoster()
    window.alert(`${token.name} sale a livello ${data.summary.new_level} ` +
                 `(+${data.summary.hp_gained} HP, cura completa).`)
  }

  async function giveLoot(token) {
    const name = window.prompt(`Loot per ${token.name} — nome dell'oggetto?`, '')
    if (!name || !name.trim()) return
    const description = window.prompt(
      `Descrizione (opzionale, testo libero):`, '') || ''
    const resp = await fetch(
      `/api/characters/${token.character_id}/inventory/give`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: name.trim(), description: description.trim() }),
      })
    if (!resp.ok) {
      const err = await resp.json().catch(() => ({}))
      window.alert(`Errore: ${err.detail || resp.statusText}`)
    }
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
                  isActive={p.token_id === activeId}
                  linkUrl={playerUrl(p.character_id)}
                  onShowLink={() => setQrUrl(playerUrl(p.character_id))}
                  onLevelUp={() => levelUpPc(p)}
                  onLoot={() => giveLoot(p)}
                  onRemove={() => sendEvent('remove_participant',
                                             { token_id: p.token_id })} />
      ))}
      {availableToAdd.length > 0 && (
        <div style={{ marginTop: 10 }}>
          <div className="muted" style={{ fontSize: 12, marginBottom: 6 }}>
            Aggiungi alla sessione:
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
            {availableToAdd.map((c) => (
              <div key={c.id} style={{ display: 'flex', gap: 4 }}>
                <button onClick={() => sendEvent('add_participant',
                                                  { character_id: c.id })}
                        style={{ ...pillBtn, flex: 1, textAlign: 'left' }}>
                  + {c.name} <span className="muted" style={{ fontSize: 11 }}>
                    ({c.race || '?'} {c.class || '?'} liv {c.level})
                  </span>
                </button>
                <button onClick={() => deletePc(c)}
                        title="Elimina dal database"
                        style={{ ...pillBtn, color: 'var(--blood)',
                                  borderColor: 'var(--blood)', minWidth: 32 }}>
                  ×
                </button>
              </div>
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

      {qrUrl && <QrModal url={qrUrl} onClose={() => setQrUrl(null)} />}
    </div>
  )
}

// URL della scheda del PG sulla stessa origin: usa il link "vero" che il
// giocatore puo' aprire dal suo telefono nella LAN. window.location.origin
// e' gia' "http://<ip-laptop>:8000" o il sottodominio Cloudflare, indifferente.
function playerUrl(characterId) {
  return `${window.location.origin}/player/${characterId}`
}

// Modal QR: il master mostra al giocatore un QR + l'URL; il giocatore
// scansiona col telefono e l'app si apre direttamente sulla sua scheda.
// Funziona offline (la libreria QR e' inclusa nel bundle).
function QrModal({ url, onClose }) {
  function copyToClipboard() {
    if (navigator.clipboard) navigator.clipboard.writeText(url).catch(() => {})
  }
  return (
    <div onClick={onClose} style={{
      position: 'fixed', inset: 0, background: '#000000cc',
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      zIndex: 100, padding: 20,
    }}>
      <div onClick={(e) => e.stopPropagation()} className="card" style={{
        maxWidth: 320, textAlign: 'center', padding: 20,
      }}>
        <div className="muted" style={{ fontSize: 12, marginBottom: 12 }}>
          Scansiona col telefono per aprire la scheda
        </div>
        <div style={{ background: '#1c1813', padding: 12, borderRadius: 8,
                       display: 'inline-block' }}>
          <QRCodeSVG value={url} size={220}
                     bgColor="#1c1813" fgColor="#e0a23a"
                     level="M" />
        </div>
        <div style={{ marginTop: 12, fontSize: 12,
                       fontFamily: 'monospace', wordBreak: 'break-all',
                       color: 'var(--ink-dim)' }}>
          {url}
        </div>
        <div style={{ display: 'flex', gap: 8, marginTop: 12 }}>
          <button onClick={copyToClipboard} style={{ ...pillBtn, flex: 1 }}>
            Copia link
          </button>
          <button onClick={onClose} style={{ ...pillBtn, flex: 1 }}>
            Chiudi
          </button>
        </div>
      </div>
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

function rosterFind(roster, characterId) {
  return roster.find((c) => c.id === characterId)
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
// linkUrl/onShowLink (solo per i PG): mostrano un QR per il giocatore.
// onLevelUp / onLoot (solo per i PG): azioni che il master fa al volo.
function TokenRow({ token, onHp, onRemove, isActive = false,
                    linkUrl, onShowLink, onLevelUp, onLoot }) {
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
          {linkUrl && onShowLink && (
            <button onClick={onShowLink} title={`QR + link: ${linkUrl}`}
                    style={{
                      marginLeft: 8, background: 'transparent',
                      border: '1px solid var(--line)', borderRadius: 4,
                      color: 'var(--ink-dim)', fontSize: 11,
                      padding: '1px 6px', cursor: 'pointer',
                    }}>
              🔗 link
            </button>
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
      {(onLevelUp || onLoot) && (
        <div style={{ display: 'flex', gap: 6, marginTop: 8 }}>
          {onLoot && (
            <button onClick={onLoot} style={pillBtn}>🎁 loot</button>
          )}
          {onLevelUp && (
            <button onClick={onLevelUp} style={pillBtn}>↑ liv</button>
          )}
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
