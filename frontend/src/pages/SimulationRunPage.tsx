import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import {
  getSimulationStatus,
  SIMULATION_STAGE_LABELS,
  type Simulation,
  type SimulationStatus,
} from '../api/simulations'

const POLL_INTERVAL_MS = 4000
const STAGE_ORDER: SimulationStatus[] = [
  'pending',
  'generating',
  'simulating',
  'evaluating',
  'optimizing',
  'completed',
]

function SimulationRunPage() {
  const { id } = useParams<{ id: string }>()
  const [simulation, setSimulation] = useState<Simulation | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!id) return
    let cancelled = false

    async function poll() {
      try {
        const result = await getSimulationStatus(id!)
        if (cancelled) return
        setSimulation(result)
        if (result.status !== 'completed' && result.status !== 'failed') {
          setTimeout(poll, POLL_INTERVAL_MS)
        }
      } catch {
        if (!cancelled) setError('Could not load this simulation.')
      }
    }
    poll()

    return () => {
      cancelled = true
    }
  }, [id])

  if (error) return <p className="error-text">{error}</p>
  if (!simulation) return <p className="muted">Loading…</p>

  const stageIndex = STAGE_ORDER.indexOf(simulation.status)

  return (
    <div className="card">
      <h1>Simulation progress</h1>
      <p className="muted">
        Round {simulation.iteration_count} of up to {simulation.max_iterations}
      </p>

      {simulation.status === 'failed' ? (
        <p className="error-text">The simulation failed. Check the server logs for details.</p>
      ) : (
        <ul style={{ listStyle: 'none', padding: 0 }}>
          {STAGE_ORDER.map((stage, i) => (
            <li key={stage} style={{ opacity: i <= stageIndex ? 1 : 0.4, padding: '0.25rem 0' }}>
              {i < stageIndex ? '✓' : i === stageIndex ? '→' : '·'} {SIMULATION_STAGE_LABELS[stage]}
            </li>
          ))}
        </ul>
      )}

      {simulation.status === 'completed' && (
        <Link to={`/dashboard/${simulation.id}`}>
          <button type="button">View results →</button>
        </Link>
      )}
    </div>
  )
}

export default SimulationRunPage
