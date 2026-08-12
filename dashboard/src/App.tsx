import { Link, Route, Routes, useLocation } from 'react-router-dom'
import LibraryPage from './pages/LibraryPage'
import NewDeckPage from './pages/NewDeckPage'
import OutlinePage from './pages/OutlinePage'
import DeckPage from './pages/DeckPage'

export default function App() {
  const location = useLocation()
  // DeckPage owns the whole viewport in present mode — no shell chrome there.
  const bare = /^\/decks\/[^/]+$/.test(location.pathname)

  if (bare) {
    return (
      <Routes>
        <Route path="/decks/:id" element={<DeckPage />} />
      </Routes>
    )
  }

  return (
    <div className="shell">
      <header className="topbar">
        <Link to="/" className="wordmark">
          Lantern<span className="ember">.</span>
        </Link>
        <Link to="/new">
          <button className="primary">New deck</button>
        </Link>
      </header>
      <Routes>
        <Route path="/" element={<LibraryPage />} />
        <Route path="/new" element={<NewDeckPage />} />
        <Route path="/decks/:id/outline" element={<OutlinePage />} />
      </Routes>
    </div>
  )
}
