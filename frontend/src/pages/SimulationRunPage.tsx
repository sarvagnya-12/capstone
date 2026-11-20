import { useEffect, useRef, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import {
  getSimulationStatus,
  SIMULATION_STAGE_LABELS,
  type Simulation,
  type SimulationStatus,
} from '../api/simulations'
import { CheckMark, EmptyBox, FlagMark, RuleArrow } from '../components/Icon'
import { runCode, usePublishRunIdentity } from '../state/RunIdentityContext'

const POLL_INTERVAL_MS = 4000
const STAGE_ORDER: SimulationStatus[] = [
  'pending',
  'generating',
  'simulating',
  'evaluating',
  'optimizing',
  'completed',
]

/** What each stage is actually doing, so a reader watching the run can tell
 * whether a long pause is expected work or a stall. */
const STAGE_DETAIL: Partial<Record<SimulationStatus, string>> = {
  generating: 'Rendering each design option from your product photo, then upscaling it',
  simulating: 'Showing every option to each customer profile and recording what they say',
  evaluating: 'Classifying the tone of each reaction and checking for risk patterns',
  optimizing: 'Scoring the options and deciding whether another round is worth running',
}

/** Real wall-clock duration: how long the run has been going, or how long
 * it took once it finished. Nothing here is estimated -- both ends come
 * from the simulation row. */
function elapsedText(from: string, to: string | null): string {
  const end = to ? new Date(to).getTime() : Date.now()
  const seconds = Math.max(0, Math.floor((end - new Date(from).getTime()) / 1000))
  const minutes = Math.floor(seconds / 60)
  return minutes > 0 ? `${minutes}m ${String(seconds % 60).padStart(2, '0')}s` : `${seconds}s`
}

function SimulationRunPage() {
  const { id } = useParams<{ id: string }>()
  const [simulation, setSimulation] = useState<Simulation | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [, setTick] = useState(0)
  /** How far the run had already got when this page opened. */
  const firstSeenIndexRef = useRef<number | null>(null)

  usePublishRunIdentity(id ? runCode(id) : null)

  useEffect(() => {
    if (!id) return
    let cancelled = false

    async function poll() {
      try {
        const result = await getSimulationStatus(id!)
        if (cancelled) return
        if (firstSeenIndexRef.current === null) {
          firstSeenIndexRef.current = STAGE_ORDER.indexOf(result.status)
        }
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

  /** The elapsed figure has to keep moving while the run is working, or a
   * reader cannot tell a slow stage from a frozen page. */
  const running = simulation !== null && simulation.status !== 'completed' && simulation.status !== 'failed'
  useEffect(() => {
    if (!running) return
    const timer = setInterval(() => setTick((t) => t + 1), 1000)
    return () => clearInterval(timer)
  }, [running])

  /** The travelling rule on the working stage is the only loop in the app.
   * It reports that something is happening, so it has no reason to run
   * while the tab is in the background. */
  const [pageHidden, setPageHidden] = useState(() => document.visibilityState === 'hidden')
  useEffect(() => {
    const onChange = () => setPageHidden(document.visibilityState === 'hidden')
    document.addEventListener('visibilitychange', onChange)
    return () => document.removeEventListener('visibilitychange', onChange)
  }, [])

  if (error) {
    return (
      <div className="card notice alert">
        <p className="error-text">
          <FlagMark /> {error}
        </p>
        <p className="muted">
          <Link to="/dashboard">Back to your simulations</Link>
        </p>
      </div>
    )
  }

  if (!simulation) return <p className="loading">Loading this run…</p>

  const stageIndex = STAGE_ORDER.indexOf(simulation.status)
  const failed = simulation.status === 'failed'
  const done = simulation.status === 'completed'
  /** Stages already finished when this page opened are ruled off without
   * being drawn; only the ones that complete under the reader's eye
   * animate. `null` until the first status lands, so the opening render
   * never replays the run's history. */
  const firstSeenIndex = firstSeenIndexRef.current
  const justCompleted = (i: number) => firstSeenIndex !== null && i >= firstSeenIndex && i < stageIndex

  return (
    <section className="card">
      <h1>{done ? 'Run complete' : failed ? 'Run stopped' : 'Run in progress'}</h1>

      <dl className="facts">
        <dt>Round</dt>
        <dd>
          <span className="quantity">{simulation.iteration_count}</span> of up to{' '}
          <span className="quantity">{simulation.max_iterations}</span>
        </dd>
        <dt>{done ? 'Took' : 'Elapsed'}</dt>
        <dd>
          <span className="quantity">{elapsedText(simulation.created_at, simulation.completed_at)}</span>
          {!done && !failed && <span className="muted"> · still working</span>}
        </dd>
      </dl>

      {failed ? (
        <div className="notice alert" style={{ marginTop: '1rem' }}>
          <p className="error-text" style={{ marginTop: 0 }}>
            <FlagMark /> This run stopped before it finished, so there are no results for it.
          </p>
          <p className="muted">
            The reason is in the backend log for this run. Nothing from a stopped run is reported as a result —
            partial reactions are not scored. Configure the scenario again to retry it.
          </p>
          <div className="actions" style={{ marginTop: '0.75rem' }}>
            <Link to="/simulations/new">
              <button type="button">Configure a new run</button>
            </Link>
            <Link to="/dashboard">
              <button type="button" className="secondary">
                Back to simulations
              </button>
            </Link>
          </div>
        </div>
      ) : (
        <>
          <h2 style={{ marginTop: '1.25rem' }}>Stages</h2>
          <ul className="stages" data-page-hidden={pageHidden}>
            {STAGE_ORDER.map((stage, i) => {
              const state = i < stageIndex ? 'done' : i === stageIndex ? 'active' : 'pending'
              const drawn = state === 'done' && justCompleted(i) ? ' just-done' : ''
              return (
                <li key={stage} className={`stage ${state}${drawn}`}>
                  <span className="stage-mark">
                    {state === 'done' ? <CheckMark /> : state === 'active' ? <RuleArrow /> : <EmptyBox />}
                  </span>
                  <span>
                    {SIMULATION_STAGE_LABELS[stage]}
                    {state === 'active' && STAGE_DETAIL[stage] && (
                      <span className="muted" style={{ display: 'block', fontSize: '0.875rem' }}>
                        {STAGE_DETAIL[stage]}
                      </span>
                    )}
                  </span>
                  <span className="legend">{state === 'active' ? 'working' : state}</span>
                </li>
              )
            })}
          </ul>
        </>
      )}

      {done && (
        <div className="actions" style={{ marginTop: '1.25rem' }}>
          <Link to={`/dashboard/${simulation.id}`}>
            <button type="button">
              View results <RuleArrow />
            </button>
          </Link>
        </div>
      )}
    </section>
  )
}

export default SimulationRunPage
