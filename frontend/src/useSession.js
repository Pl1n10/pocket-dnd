import { useEffect, useRef, useState, useCallback } from 'react'

// Hook per la connessione WebSocket a una sessione pocket-dnd.
//
// Responsabilita' chiave (DECISIONS.md D5 / ANTIPATTERNS.md AP6):
//   - il server e' la fonte autoritativa: ad ogni messaggio `snapshot`
//     sostituiamo lo stato locale per intero, non applichiamo delta.
//   - i telefoni vanno in standby e la socket cade: il reconnect e'
//     automatico, con backoff, e alla riconnessione il server rimanda
//     da solo lo snapshot completo. Il client non ricostruisce nulla.
//
// Ritorna: { state, status, sendEvent, lastError }
//   state    -> ultimo snapshot ricevuto (null finche' non arriva il primo)
//   status   -> 'connecting' | 'open' | 'reconnecting'
//   sendEvent(type, payload) -> invia un evento; se la socket e' giu', no-op
//   lastError-> ultimo messaggio d'errore dal server (o null)
//
// Opzioni:
//   onCharacterUpdated(payload) -> chiamato quando il server emette il
//     messaggio `character_updated` (es. dopo level-up o loot dal master).
//     payload = { character_id, character }

const MAX_BACKOFF_MS = 5000

export function useSession(sessionId, options = {}) {
  const [state, setState] = useState(null)
  const [status, setStatus] = useState('connecting')
  const [lastError, setLastError] = useState(null)

  const wsRef = useRef(null)
  const backoffRef = useRef(500)
  const closedByUs = useRef(false)
  const reconnectTimer = useRef(null)
  // tieni in un ref la callback per evitare reconnect a ogni render
  const onCharacterUpdatedRef = useRef(options.onCharacterUpdated)
  onCharacterUpdatedRef.current = options.onCharacterUpdated

  const connect = useCallback(() => {
    const proto = window.location.protocol === 'https:' ? 'wss' : 'ws'
    const url = `${proto}://${window.location.host}/ws/session/${sessionId}`
    const ws = new WebSocket(url)
    wsRef.current = ws

    ws.onopen = () => {
      setStatus('open')
      backoffRef.current = 500 // reset del backoff a connessione riuscita
    }

    ws.onmessage = (ev) => {
      let msg
      try {
        msg = JSON.parse(ev.data)
      } catch {
        return // messaggio non-JSON: ignorato
      }
      if (msg.type === 'snapshot') {
        // sostituzione integrale: lo snapshot E' lo stato (D5)
        setState(msg.state)
        setLastError(null)
      } else if (msg.type === 'error') {
        setLastError(msg.detail || 'errore sconosciuto')
      } else if (msg.type === 'character_updated') {
        const cb = onCharacterUpdatedRef.current
        if (cb) cb({ character_id: msg.character_id, character: msg.character })
      }
    }

    ws.onclose = () => {
      if (closedByUs.current) return
      // socket caduta: si ritenta con backoff esponenziale
      setStatus('reconnecting')
      const delay = backoffRef.current
      backoffRef.current = Math.min(delay * 2, MAX_BACKOFF_MS)
      reconnectTimer.current = setTimeout(connect, delay)
    }

    ws.onerror = () => {
      // onclose seguira' e gestira' il reconnect; qui niente da fare
    }
  }, [sessionId])

  useEffect(() => {
    closedByUs.current = false
    connect()
    return () => {
      closedByUs.current = true
      if (reconnectTimer.current) clearTimeout(reconnectTimer.current)
      if (wsRef.current) wsRef.current.close()
    }
  }, [connect])

  const sendEvent = useCallback((type, payload = {}) => {
    const ws = wsRef.current
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ type, payload }))
    }
    // se la socket e' giu' l'evento si perde: e' accettabile, lo stato
    // autoritativo e' sul server e al reconnect arriva lo snapshot fresco.
  }, [])

  return { state, status, sendEvent, lastError }
}
