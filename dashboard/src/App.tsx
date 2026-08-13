import { Link, Route, Routes, useLocation } from 'react-router-dom'
import LibraryPage from './pages/LibraryPage'
import NewDeckPage from './pages/NewDeckPage'
import OutlinePage from './pages/OutlinePage'
import DeckPage from './pages/DeckPage'
import ChalkPage from './pages/ChalkPage'

export default function App() {
  const location = useLocation()
  // DeckPage (present mode) and ChalkPage own the whole viewport — no shell.
  const bare = /^\/decks\/[^/]+$/.test(location.pathname) || location.pathname === '/chalk'

  if (bare) {
    return (
      <Routes>
        <Route path="/decks/:id" element={<DeckPage />} />
        <Route path="/chalk" element={<ChalkPage />} />
      </Routes>
    )
  }

  return (
    <div className="shell">
      <header className="topbar">
        <Link to="/" className="wordmark">
          Lantern<span className="ember">.</span>
        </Link>
        <span className="topbar-actions">
          <Link to="/chalk">
            <button className="ghost">Chalk — chat</button>
          </Link>
          <Link to="/new">
            <button className="primary">New deck</button>
          </Link>
        </span>
      </header>
      <Routes>
        <Route path="/" element={<LibraryPage />} />
        <Route path="/new" element={<NewDeckPage />} />
        <Route path="/decks/:id/outline" element={<OutlinePage />} />
      </Routes>
    </div>
  )
}
