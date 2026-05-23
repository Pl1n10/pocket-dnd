import React from 'react'
import ReactDOM from 'react-dom/client'
import { createBrowserRouter, RouterProvider, Navigate } from 'react-router-dom'
import './index.css'
import PlayerSheet from './PlayerSheet.jsx'
import MasterConsole from './MasterConsole.jsx'

// Routing minimale.
const router = createBrowserRouter([
  { path: '/player/:characterId', element: <PlayerSheet /> },
  { path: '/master', element: <MasterConsole /> },
  { path: '*', element: <Navigate to="/player/1" replace /> },
])

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <RouterProvider router={router} />
  </React.StrictMode>
)

// Registrazione del Service Worker (PWA). Silenzioso in caso di errore:
// in dev (Vite) il /sw.js non c'e' e va bene cosi'.
if ('serviceWorker' in navigator) {
  window.addEventListener('load', () => {
    navigator.serviceWorker.register('/sw.js').catch(() => {})
  })
}
