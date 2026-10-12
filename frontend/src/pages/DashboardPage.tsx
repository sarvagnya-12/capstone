import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { apiErrorMessage } from '../api/client'
import { downloadReport, getSimulationAnalytics, type SimulationAnalytics } from '../api/dashboard'
import { listSimulations, type Simulation } from '../api/simulations'
import { INTEREST_COLOR } from '../components/interest'
import VariantCard from '../components/VariantCard'

const STATUS_TEXT: Record<string, string> = {
  completed: 'Results ready',
  failed: 'Did not complete',
  pending: 'Queued',
  generating: 'Creating designs',
  simulating: 'Gathering customer reactions',
  evaluating: 'Analysing reactions',
  optimizing: 'Refining designs',
}

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
              <th></th>
            </tr>
          </thead>
          <tbody>
            {simulations.map((sim) => (
              <tr key={sim.id}>
                <td>{new Date(sim.created_at).toLocaleString()}</td>
                <td>{STATUS_TEXT[sim.status] ?? sim.status}</td>
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

  const ins = analytics.insights
  const best = ins.options[0]
  const product = [ins.product_brand, ins.product_name].filter(Boolean).join(' ')

  return (
    <div>
      <div className="card verdict-card" style={{ borderLeftColor: INTEREST_COLOR[best.interest_level] }}>
        <span className="muted">
          Launch readiness · {product}
          {ins.product_category ? ` · ${ins.product_category}` : ''}
        </span>
        <h1 style={{ color: INTEREST_COLOR[best.interest_level] }}>{ins.verdict}</h1>
        <p>{ins.bottom_line}</p>
        <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
          <button type="button" onClick={() => handleDownload('pdf')} disabled={downloading !== null}>
            {downloading === 'pdf' ? 'Preparing…' : 'Download report (PDF)'}
          </button>
          <button type="button" className="secondary" onClick={() => handleDownload('csv')} disabled={downloading !== null}>
            {downloading === 'csv' ? 'Preparing…' : 'Download data (spreadsheet)'}
          </button>
        </div>
      </div>

      <div className="card">
        <h2>What we tested</h2>
        <dl className="facts">
          <dt>Price tested</dt>
          <dd>{ins.price_text}</dd>
          <dt>Target customers</dt>
          <dd>{ins.audience_text}</dd>
          {ins.messaging && (
            <>
              <dt>Marketing message</dt>
              <dd>“{ins.messaging}”</dd>
            </>
          )}
          <dt>Customer profiles</dt>
          <dd>{ins.profiles_tested} simulated customer types, each reacting to every design</dd>
          <dt>Design options</dt>
          <dd>{ins.options_tested} generated designs compared</dd>
        </dl>
      </div>

      <div className="card">
        <h2>How the options compared</h2>
        <table>
          <thead>
            <tr>
              <th>Option</th>
              <th>Colourway</th>
              <th>Avg. purchase likelihood</th>
              <th>Would likely buy</th>
              <th>Tone of comments</th>
            </tr>
          </thead>
          <tbody>
            {ins.options.map((o) => (
              <tr key={o.variant_id} className={o.is_recommended ? 'row-recommended' : undefined}>
                <td>
                  <strong>{o.label}</strong>
                  {o.is_recommended && <div className="success-text">Recommended</div>}
                </td>
                <td>{o.colourway}</td>
                <td>
                  <div className="meter">
                    <div style={{ width: `${o.purchase_intent_pct}%`, background: INTEREST_COLOR[o.interest_level] }} />
                  </div>
                  {o.purchase_intent_pct}% <span className="muted">· {o.interest_level.toLowerCase()} interest</span>
                </td>
                <td>
                  {o.likely_buyers} of {o.profiles}
                </td>
                <td>{o.reception}</td>
              </tr>
            ))}
          </tbody>
        </table>
        <p className="muted" style={{ fontSize: '0.8rem' }}>
          Purchase likelihood is the average chance of buying that the customer profiles gave each design. “Would likely
          buy” counts profiles at 60% or more.
        </p>
      </div>

      <div className="grid">
        {ins.options.map((option) => (
          <VariantCard key={option.variant_id} simulationId={simulationId} option={option} />
        ))}
      </div>

      <div className="card">
        <h2>Recommended next steps</h2>
        <ol>
          {ins.next_steps.map((step) => (
            <li key={step}>{step}</li>
          ))}
        </ol>
        <p className="muted" style={{ fontSize: '0.8rem' }}>
          {ins.disclaimer}
        </p>
      </div>
    </div>
  )
}

function DashboardPage() {
  const { id } = useParams<{ id?: string }>()
  return id ? <SimulationAnalyticsView simulationId={id} /> : <SimulationListView />
}

export default DashboardPage
