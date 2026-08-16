import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { listAllSimulations, listAllUsers } from '../api/admin'
import type { User } from '../api/auth'
import type { Simulation } from '../api/simulations'

function AdminPage() {
  const [users, setUsers] = useState<User[]>([])
  const [simulations, setSimulations] = useState<Simulation[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    Promise.all([listAllUsers(), listAllSimulations()])
      .then(([u, s]) => {
        setUsers(u)
        setSimulations(s)
      })
      .finally(() => setLoading(false))
  }, [])

  if (loading) return <p className="muted">Loading…</p>

  return (
    <div>
      <div className="card">
        <h1>Users ({users.length})</h1>
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
                <td>{u.role}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="card">
        <h1>All simulations ({simulations.length})</h1>
        <table>
          <thead>
            <tr>
              <th>Created</th>
              <th>Status</th>
              <th>Round</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {simulations.map((sim) => (
              <tr key={sim.id}>
                <td>{new Date(sim.created_at).toLocaleString()}</td>
                <td>{sim.status}</td>
                <td>
                  {sim.iteration_count}/{sim.max_iterations}
                </td>
                <td>{sim.status === 'completed' && <Link to={`/dashboard/${sim.id}`}>View results</Link>}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

export default AdminPage
