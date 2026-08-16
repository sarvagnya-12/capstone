import { Link, Outlet, useNavigate } from 'react-router-dom'
import { AuthProvider, useAuth } from './state/AuthContext'

function Nav() {
  const { isAuthenticated, isAdmin, user, logout } = useAuth()
  const navigate = useNavigate()

  function handleLogout() {
    logout()
    navigate('/login')
  }

  return (
    <header className="app-header">
      <Link to="/" className="brand">
        DryRunAI
      </Link>
      {isAuthenticated && (
        <nav className="app-nav">
          <Link to="/products/new">Upload Product</Link>
          <Link to="/simulations/new">New Simulation</Link>
          <Link to="/dashboard">Dashboard</Link>
          {isAdmin && <Link to="/admin">Admin</Link>}
          <span className="app-nav-user">{user?.email}</span>
          <button type="button" onClick={handleLogout}>
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
      <div>
        <Nav />
        <main className="app-main">
          <Outlet />
        </main>
      </div>
    </AuthProvider>
  )
}

export default App
