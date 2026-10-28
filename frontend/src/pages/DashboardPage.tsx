import { useEffect, useMemo, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { apiErrorMessage } from '../api/client'
import { downloadReport, getSimulationAnalytics, type SimulationAnalytics } from '../api/dashboard'
import { listSimulations, type Simulation } from '../api/simulations'
import ColourwayChips from '../components/ColourwayChips'
import { FlagMark, SheetDown } from '../components/Icon'
import { INTEREST_COLOR } from '../components/interest'
import VariantCard from '../components/VariantCard'
import { runCode, usePublishRunIdentity } from '../state/RunIdentityContext'

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
    <section className="card">
      <h1>Your simulations</h1>
      {loading && <p className="loading">Loading your simulations…</p>}

      {!loading && simulations.length === 0 && (
        <div className="empty">
          <div className="empty-body">
            <h3>No simulations run yet</h3>
            <p className="muted">
              A simulation needs a product photo and a launch scenario. Upload a product first, then set the price,
              the customers you are aiming at, and your marketing message.
            </p>
            <p className="muted">
              The reference corpus behind the simulated customers is footwear only, so results are meaningful for
              shoes and not yet for other categories.
            </p>
            <div className="actions" style={{ marginTop: '0.75rem' }}>
              <Link to="/products/new">
                <button type="button">Upload a product</button>
              </Link>
            </div>
          </div>
        </div>
      )}

      {simulations.length > 0 && (
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
                      <span className="error-text">
                        <FlagMark /> Did not complete
                      </span>
                    ) : (
                      (STATUS_TEXT[sim.status] ?? sim.status)
                    )}
                  </td>
                  <td className="num">
                    <span className="quantity">{sim.iteration_count}</span> of {sim.max_iterations}
                  </td>
                  <td>
                    {sim.status === 'completed' ? (
                      <Link to={`/dashboard/${sim.id}`}>View results</Link>
                    ) : sim.status === 'failed' ? (
                      <span className="muted">No results</span>
                    ) : (
                      <Link to={`/simulations/${sim.id}`}>View progress</Link>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  )
}

function SimulationAnalyticsView({ simulationId }: { simulationId: string }) {
  const [analytics, setAnalytics] = useState<SimulationAnalytics | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [downloading, setDownloading] = useState<'csv' | 'pdf' | null>(null)
  const [selectedId, setSelectedId] = useState<string | null>(null)
  /** Counts deliberate scope changes. Stays 0 through the first render, so
   * the sheet arrives without an entrance and only acknowledges scoping
   * once the reader has actually scoped it. */
  const [scopeTick, setScopeTick] = useState(0)

  function handleSelect(variantId: string | null) {
    setSelectedId(variantId)
    setScopeTick((t) => t + 1)
  }

  usePublishRunIdentity(runCode(simulationId))

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

  const ins = analytics?.insights
  const shownOptions = useMemo(() => {
    if (!ins) return []
    return selectedId ? ins.options.filter((o) => o.variant_id === selectedId) : ins.options
  }, [ins, selectedId])

  if (error) {
    return (
      <div className="card notice alert">
        <p className="error-text">
          <FlagMark /> {error}
        </p>
        <p className="muted">
          The results for this run could not be loaded. <Link to="/dashboard">Back to your simulations</Link>
        </p>
      </div>
    )
  }

  if (!ins) return <p className="loading">Loading results for {runCode(simulationId)}…</p>

  const best = ins.options[0]
  const unmeasured = ins.options.filter((o) => o.colourway_hex === null).length

  return (
    <div>
      <section className="card finding">
        <div className="finding-head">
          <div>
            <h1 style={{ color: INTEREST_COLOR[best.interest_level] }}>{ins.verdict}</h1>
            <p className="finding-line">{ins.bottom_line}</p>
          </div>
          <div className="actions">
            <button type="button" onClick={() => handleDownload('pdf')} disabled={downloading !== null}>
              <SheetDown /> {downloading === 'pdf' ? 'Preparing…' : 'Report (PDF)'}
            </button>
            <button
              type="button"
              className="secondary"
              onClick={() => handleDownload('csv')}
              disabled={downloading !== null}
            >
              <SheetDown /> {downloading === 'csv' ? 'Preparing…' : 'Data (CSV)'}
            </button>
          </div>
        </div>
      </section>

      <section className="card">
        <h2>Design options generated</h2>
        <ColourwayChips options={ins.options} selectedId={selectedId} onSelect={handleSelect} />
        <p className="table-note">
          Each chip is the colour measured from that option's generated image, not the colour the pipeline asked
          for. Select one to read it on its own.
          {unmeasured > 0 &&
            ` ${unmeasured} of ${ins.options.length} could not be measured and are shown hatched.`}
        </p>
      </section>

      <section className="card">
        <h2>What we tested</h2>
        <dl className="facts">
          <dt>Product</dt>
          <dd>
            {[ins.product_brand, ins.product_name].filter(Boolean).join(' ')}
            {ins.product_category ? <span className="muted"> · {ins.product_category}</span> : null}
          </dd>
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
          <dd>
            <span className="quantity">{ins.profiles_tested}</span> simulated customer types, each reacting to every
            design
          </dd>
          <dt>Design options</dt>
          <dd>
            <span className="quantity">{ins.options_tested}</span> generated designs compared over{' '}
            <span className="quantity">{ins.rounds_run}</span> round{ins.rounds_run === 1 ? '' : 's'}
          </dd>
        </dl>
      </section>

      <section className="card">
        <h2>How the options compared</h2>
        <div className="table-scroll">
          <table>
            <thead>
              <tr>
                <th>Option</th>
                <th>Colourway</th>
                <th className="num">Avg. would buy</th>
                <th className="num">Would likely buy</th>
                <th>Tone of comments</th>
              </tr>
            </thead>
            <tbody>
              {ins.options.map((o) => (
                <tr key={o.variant_id} className={o.is_recommended ? 'row-recommended' : undefined}>
                  <td>
                    <span className="code">{o.label}</span>
                    {o.is_recommended && (
                      <div>
                        <span className="badge recommended">Recommended</span>
                      </div>
                    )}
                  </td>
                  <td>{o.colourway}</td>
                  <td className="num">
                    <div className="bar" style={{ marginLeft: 'auto' }}>
                      <span
                        style={{
                          width: `${o.purchase_intent_pct}%`,
                          background: INTEREST_COLOR[o.interest_level],
                        }}
                      />
                    </div>
                    <span className="quantity">{o.purchase_intent_pct}%</span>{' '}
                    <span className="muted">{o.interest_level.toLowerCase()}</span>
                  </td>
                  <td className="num">
                    <span className="quantity">{o.likely_buyers}</span> of {o.profiles}
                  </td>
                  <td>{o.reception}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="table-note">
          Average would-buy is the mean chance of buying that the customer profiles gave each design. “Would likely
          buy” counts profiles at 60% or more. Bar lengths are the figures themselves, to scale.
        </p>
      </section>

      <section>
        <h2 style={{ marginBottom: '0.75rem' }}>
          {selectedId ? `${shownOptions[0]?.label ?? 'Option'} in detail` : 'Every option in detail'}
        </h2>
        {selectedId && (
          <div className="actions" style={{ marginBottom: '0.75rem' }}>
            <button type="button" className="quiet" onClick={() => handleSelect(null)}>
              Show all {ins.options.length} options
            </button>
          </div>
        )}
        <div
          key={scopeTick}
          className={`option-grid${scopeTick > 0 ? ' scope-change' : ''}`}
        >
          {shownOptions.map((option) => (
            <VariantCard key={option.variant_id} simulationId={simulationId} option={option} />
          ))}
        </div>
      </section>

      <section className="card">
        <h2>Recommended next steps</h2>
        <ol className="prose">
          {ins.next_steps.map((step) => (
            <li key={step}>{step}</li>
          ))}
        </ol>
        <p className="table-note">{ins.disclaimer}</p>
      </section>
    </div>
  )
}

function DashboardPage() {
  const { id } = useParams<{ id?: string }>()
  return id ? <SimulationAnalyticsView simulationId={id} /> : <SimulationListView />
}

export default DashboardPage
