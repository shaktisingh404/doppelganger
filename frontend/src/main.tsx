import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.tsx'
import { PublicChat } from './components/PublicChat.tsx'

// No router library — the app otherwise switches views via plain state
// (App.tsx), but a shareable link has to work as a real bookmarkable URL
// a fresh browser can open directly, which that state approach can't do.
// This is the one path that needs it, so it's the only one that gets it.
const shareMatch = window.location.pathname.match(/^\/share\/([^/]+)/)

createRoot(document.getElementById('root')!).render(
  <StrictMode>{shareMatch ? <PublicChat shareToken={shareMatch[1]} /> : <App />}</StrictMode>,
)
