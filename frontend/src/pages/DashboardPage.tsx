import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { apiErrorMessage } from '../api/client'
import { downloadReport, getSimulationAnalytics, type SimulationAnalytics } from '../api/dashboard'
import { listSimulations, type Simulation } from '../api/simulations'
import VariantCard from '../components/VariantCard'

function SimulationListView() {
  const [simulations, setSimulations] = useState<Simulation[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    listSimulations()
      .then(setSimulations)
      .catch(() => setSimulations([]))
      .finally(() => setLoading(false))
  }, [])

  return (
    <div className="card">
      <h1>Your simulations</h1>
      {loading && <p className="muted">Loading…</p>}
      {!loading && simulations.length === 0 && (
        <p className="muted">
          No simulations yet. <Link to="/products/new">Upload a product</Link> to get started.
        </p>
      )}
      {simulations.length > 0 && (
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
                <td>
                  {sim.status === 'completed' ? (
                    <Link to={`/dashboard/${sim.id}`}>View results</Link>
                  ) : sim.status === 'failed' ? (
                    <span className="error-text">Failed</span>
                  ) : (
                    <Link to={`/simulations/${sim.id}`}>View progress</Link>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  )
}

function SimulationAnalyticsView({ simulationId }: { simulationId: string }) {
  const [analytics, setAnalytics] = useState<SimulationAnalytics | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [downloading, setDownloading] = useState<'csv' | 'pdf' | null>(null)

  useEffect(() => {
    getSimulationAnalytics(simulationId)
      .then(setAnalytics)
      .catch((err) => setError(apiErrorMessage(err)))
  }, [simulationId])

  async function handleDownload(format: 'csv' | 'pdf') {
    setDownloading(format)
    try {
      await downloadReport(simulationId, format)
    } catch (err) {
      setError(apiErrorMessage(err))
    } finally {
      setDownloading(null)
    }
  }

  if (error) return <p className="error-text">{error}</p>
  if (!analytics) return <p className="muted">Loading…</p>

  return (
    <div>
      <div className="card">
        <h1>Simulation results</h1>
        <p>{analytics.summary_text}</p>
        <div style={{ display: 'flex', gap: '0.5rem' }}>
          <button type="button" onClick={() => handleDownload('csv')} disabled={downloading !== null}>
            {downloading === 'csv' ? 'Downloading…' : 'Download CSV'}
          </button>
          <button type="button" onClick={() => handleDownload('pdf')} disabled={downloading !== null}>
            {downloading === 'pdf' ? 'Downloading…' : 'Download PDF'}
          </button>
        </div>
      </div>

      <div className="grid">
        {analytics.variants.map((variant) => (
          <VariantCard key={variant.variant_id} simulationId={simulationId} variant={variant} />
        ))}
      </div>
    </div>
  )
}

function DashboardPage() {
  const { id } = useParams<{ id?: string }>()
  return id ? <SimulationAnalyticsView simulationId={id} /> : <SimulationListView />
}

export default DashboardPage
