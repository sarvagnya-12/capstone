import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { listAllSimulations, listAllUsers } from '../api/admin'
import type { User } from '../api/auth'
import type { Simulation } from '../api/simulations'
import { FlagMark } from '../components/Icon'
import { runCode } from '../state/RunIdentityContext'

function AdminPage() {
  const [users, setUsers] = useState<User[]>([])
  const [simulations, setSimulations] = useState<Simulation[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    Promise.all([listAllUsers(), listAllSimulations()])
      .then(([u, s]) => {
        setUsers(u)
        setSimulations(s)
      })
      .catch(() => setError('Could not load the admin lists.'))
      .finally(() => setLoading(false))
  }, [])

  if (loading) return <p className="loading">Loading accounts and runs…</p>

  if (error) {
    return (
      <div className="card notice alert">
        <p className="error-text" style={{ marginTop: 0 }}>
          <FlagMark /> {error}
        </p>
        <p className="muted">Admin lists need an account with the admin role.</p>
      </div>
    )
  }

  return (
    <div>
      <section className="card">
        <h1>
          Accounts <span className="quantity muted">{users.length}</span>
        </h1>
        <div className="table-scroll">
          <table>
            <thead>
              <tr>
                <th>Email</th>
                <th>Organization</th>
                <th>Role</th>
              </tr>
            </thead>
            <tbody>
              {users.map((u) => (
                <tr key={u.id}>
                  <td>{u.email}</td>
                  <td>{u.org_name}</td>
                  <td>
                    <span className={`badge ${u.role === 'admin' ? 'positive' : 'neutral'}`}>{u.role}</span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section className="card">
        <h1>
          All runs <span className="quantity muted">{simulations.length}</span>
        </h1>
        <div className="table-scroll">
          <table>
            <thead>
              <tr>
                <th>Run</th>
                <th>Started</th>
                <th>Status</th>
                <th className="num">Round</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {simulations.map((sim) => (
                <tr key={sim.id}>
                  <td>
                    <span className="code">{runCode(sim.id)}</span>
                  </td>
                  <td>{new Date(sim.created_at).toLocaleString()}</td>
                  <td>
                    {sim.status === 'failed' ? (
                      <span className="badge negative">failed</span>
                    ) : sim.status === 'completed' ? (
                      <span className="badge positive">completed</span>
                    ) : (
                      <span className="badge neutral">{sim.status}</span>
                    )}
                  </td>
                  <td className="num">
                    <span className="quantity">{sim.iteration_count}</span> of {sim.max_iterations}
                  </td>
                  <td>
                    {sim.status === 'completed' ? (
                      <Link to={`/dashboard/${sim.id}`}>View results</Link>
                    ) : (
                      <span className="muted">—</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  )
}

export default AdminPage
