import { useEffect, useState, type FormEvent } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { apiErrorMessage } from '../api/client'
import { listProducts, type Product } from '../api/products'
import { createSimulation, type PricingTierInput } from '../api/simulations'
import { FlagMark, PlusRule, StrikeRule } from '../components/Icon'

function ScenarioConfigPage() {
  const navigate = useNavigate()
  const location = useLocation()
  const preselectedProductId = (location.state as { productId?: string } | null)?.productId

  const [products, setProducts] = useState<Product[]>([])
  const [loadingProducts, setLoadingProducts] = useState(true)
  const [productId, setProductId] = useState(preselectedProductId ?? '')
  const [tiers, setTiers] = useState<PricingTierInput[]>([{ tier_name: 'standard', price: 0 }])
  const [ageMin, setAgeMin] = useState('')
  const [ageMax, setAgeMax] = useState('')
  const [gender, setGender] = useState('')
  const [incomeSegment, setIncomeSegment] = useState('')
  const [region, setRegion] = useState('')
  const [lifestyle, setLifestyle] = useState('')
  const [promotionalMessaging, setPromotionalMessaging] = useState('')
  const [variantCount, setVariantCount] = useState(4)
  const [maxIterations, setMaxIterations] = useState<number | ''>('')
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)

  useEffect(() => {
    listProducts()
      .then(setProducts)
      .catch(() => setProducts([]))
      .finally(() => setLoadingProducts(false))
  }, [])

  function updateTier(index: number, patch: Partial<PricingTierInput>) {
    setTiers((prev) => prev.map((t, i) => (i === index ? { ...t, ...patch } : t)))
  }

  function addTier() {
    setTiers((prev) => [...prev, { tier_name: '', price: 0 }])
  }

  function removeTier(index: number) {
    setTiers((prev) => prev.filter((_, i) => i !== index))
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    setError(null)

    if (!productId) {
      setError('Choose which product this scenario is for.')
      return
    }
    if (tiers.length === 0 || tiers.some((t) => !t.tier_name || t.price <= 0)) {
      setError('Every pricing tier needs a name and a price above 0.')
      return
    }

    setSubmitting(true)
    try {
      const simulation = await createSimulation({
        product_id: productId,
        pricing_strategy: tiers,
        target_demographic: {
          age_min: ageMin ? Number(ageMin) : undefined,
          age_max: ageMax ? Number(ageMax) : undefined,
          gender: gender || undefined,
          income_segment: incomeSegment || undefined,
          region: region || undefined,
          lifestyle: lifestyle || undefined,
        },
        promotional_messaging: promotionalMessaging || undefined,
        variant_count: variantCount,
        max_iterations: maxIterations === '' ? undefined : maxIterations,
      })
      navigate(`/simulations/${simulation.id}`)
    } catch (err) {
      setError(apiErrorMessage(err))
    } finally {
      setSubmitting(false)
    }
  }

  if (!loadingProducts && products.length === 0) {
    return (
      <section className="card">
        <h1>Configure a launch scenario</h1>
        <div className="empty">
          <div className="empty-body">
            <h3>No product to test yet</h3>
            <p className="muted">
              A scenario is a price, an audience and a message tested against one product's photo. Upload the
              product first and it will be selectable here.
            </p>
            <div className="actions" style={{ marginTop: '0.75rem' }}>
              <Link to="/products/new">
                <button type="button">Upload a product</button>
              </Link>
            </div>
          </div>
        </div>
      </section>
    )
  }

  return (
    <section className="card">
      <h1>Configure a launch scenario</h1>
      <p className="prose muted">
        Every option generated from this product is shown to each simulated customer profile under the scenario you
        set here. More options and more rounds mean a longer run.
      </p>

      <form onSubmit={handleSubmit}>
        <h2 style={{ marginTop: '1.25rem' }}>Product</h2>
        <div className="form-field">
          <label htmlFor="product">Product to test</label>
          <select id="product" required value={productId} onChange={(e) => setProductId(e.target.value)}>
            <option value="">Select a product…</option>
            {products.map((p) => (
              <option key={p.id} value={p.id}>
                {p.name}
              </option>
            ))}
          </select>
        </div>

        <h2 style={{ marginTop: '1.5rem' }}>Pricing</h2>
        <div className="form-field">
          <label>Pricing tiers</label>
          {tiers.map((tier, i) => (
            <div key={i} className="tier-row">
              <input
                placeholder="Tier name"
                aria-label={`Tier ${i + 1} name`}
                value={tier.tier_name}
                onChange={(e) => updateTier(i, { tier_name: e.target.value })}
                required
              />
              <input
                type="number"
                min="0.01"
                step="0.01"
                placeholder="Price"
                aria-label={`Tier ${i + 1} price`}
                value={tier.price || ''}
                onChange={(e) => updateTier(i, { price: Number(e.target.value) })}
                required
              />
              {tiers.length > 1 && (
                <button
                  type="button"
                  className="quiet"
                  onClick={() => removeTier(i)}
                  aria-label={`Remove tier ${i + 1}`}
                >
                  <StrikeRule />
                </button>
              )}
            </div>
          ))}
          <div className="actions" style={{ marginTop: '0.5rem' }}>
            <button type="button" className="quiet" onClick={addTier}>
              <PlusRule /> Add tier
            </button>
          </div>
        </div>

        <h2 style={{ marginTop: '1.5rem' }}>Target customers</h2>
        <p className="form-hint" style={{ marginBottom: '0.75rem' }}>
          All optional. Anything left blank is not narrowed, and the persona library is used as seeded.
        </p>
        <div className="field-grid">
          <div className="form-field">
            <label htmlFor="ageMin">Age from</label>
            <input id="ageMin" type="number" value={ageMin} onChange={(e) => setAgeMin(e.target.value)} />
          </div>
          <div className="form-field">
            <label htmlFor="ageMax">Age to</label>
            <input id="ageMax" type="number" value={ageMax} onChange={(e) => setAgeMax(e.target.value)} />
          </div>
          <div className="form-field">
            <label htmlFor="gender">Gender</label>
            <input id="gender" value={gender} onChange={(e) => setGender(e.target.value)} />
          </div>
          <div className="form-field">
            <label htmlFor="incomeSegment">Income segment</label>
            <input
              id="incomeSegment"
              value={incomeSegment}
              onChange={(e) => setIncomeSegment(e.target.value)}
            />
          </div>
          <div className="form-field">
            <label htmlFor="region">Region</label>
            <input id="region" value={region} onChange={(e) => setRegion(e.target.value)} />
          </div>
          <div className="form-field">
            <label htmlFor="lifestyle">Lifestyle</label>
            <input id="lifestyle" value={lifestyle} onChange={(e) => setLifestyle(e.target.value)} />
          </div>
        </div>

        <h2 style={{ marginTop: '1.5rem' }}>Message and run size</h2>
        <div className="form-field">
          <label htmlFor="promo">Marketing message (optional)</label>
          <textarea
            id="promo"
            rows={2}
            value={promotionalMessaging}
            onChange={(e) => setPromotionalMessaging(e.target.value)}
          />
          <span className="form-hint">Each customer profile reacts to the design with this message in mind.</span>
        </div>
        <div className="field-grid">
          <div className="form-field">
            <label htmlFor="variantCount">Options per round</label>
            <input
              id="variantCount"
              type="number"
              min={1}
              max={20}
              value={variantCount}
              onChange={(e) => setVariantCount(Number(e.target.value))}
            />
            <span className="form-hint">1 to 20.</span>
          </div>
          <div className="form-field">
            <label htmlFor="maxIterations">Maximum rounds</label>
            <input
              id="maxIterations"
              type="number"
              min={1}
              max={10}
              value={maxIterations}
              onChange={(e) => setMaxIterations(e.target.value === '' ? '' : Number(e.target.value))}
            />
            <span className="form-hint">1 to 10. Left blank, the run uses 3.</span>
          </div>
        </div>

        {error && (
          <p className="error-text">
            <FlagMark /> {error}
          </p>
        )}
        <div className="actions" style={{ marginTop: '1rem' }}>
          <button type="submit" disabled={submitting}>
            {submitting ? 'Starting the run…' : 'Run simulation'}
          </button>
        </div>
      </form>
    </section>
  )
}

export default ScenarioConfigPage
