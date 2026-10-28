import { Link, NavLink, Outlet, useNavigate } from 'react-router-dom'
import { AuthProvider, useAuth } from './state/AuthContext'
import { RunIdentityProvider, useRunIdentity } from './state/RunIdentityContext'

function Nav() {
  const { isAuthenticated, isAdmin, user, logout } = useAuth()
  const { identity } = useRunIdentity()
  const navigate = useNavigate()

  function handleLogout() {
    logout()
    navigate('/login')
  }

  return (
    <header className="app-header">
      <div className="app-nav">
        <Link to="/" className="brand">
          DryRunAI
        </Link>
        {identity && <span className="code run-id">{identity}</span>}
      </div>
      {isAuthenticated && (
        <nav className="app-nav">
          <NavLink to="/products/new">Products</NavLink>
          <NavLink to="/simulations/new">New simulation</NavLink>
          <NavLink to="/dashboard" end>
            Simulations
          </NavLink>
          {isAdmin && <NavLink to="/admin">Admin</NavLink>}
          <span className="app-nav-user">{user?.email}</span>
          <button type="button" className="secondary" onClick={handleLogout}>
            Log out
          </button>
        </nav>
      )}
    </header>
  )
}

function App() {
  return (
    <AuthProvider>
      <RunIdentityProvider>
        <Nav />
        <main className="app-main">
          <Outlet />
        </main>
      </RunIdentityProvider>
    </AuthProvider>
  )
}

export default App
