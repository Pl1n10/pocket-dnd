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
