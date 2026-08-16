import { useEffect, useState, type FormEvent } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { apiErrorMessage } from '../api/client'
import { listProducts, type Product } from '../api/products'
import { createSimulation, type PricingTierInput } from '../api/simulations'

function ScenarioConfigPage() {
  const navigate = useNavigate()
  const location = useLocation()
  const preselectedProductId = (location.state as { productId?: string } | null)?.productId

  const [products, setProducts] = useState<Product[]>([])
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
    listProducts().then(setProducts).catch(() => setProducts([]))
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
      setError('Select a product first.')
      return
    }
    if (tiers.length === 0 || tiers.some((t) => !t.tier_name || t.price <= 0)) {
      setError('Every pricing tier needs a name and a price greater than 0.')
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

  return (
    <div className="card">
      <h1>Configure a launch scenario</h1>
      <form onSubmit={handleSubmit}>
        <div className="form-field">
          <label htmlFor="product">Product</label>
          <select id="product" required value={productId} onChange={(e) => setProductId(e.target.value)}>
            <option value="">Select a product…</option>
            {products.map((p) => (
              <option key={p.id} value={p.id}>
                {p.name}
              </option>
            ))}
          </select>
        </div>

        <div className="form-field">
          <label>Pricing tiers</label>
          {tiers.map((tier, i) => (
            <div key={i} style={{ display: 'flex', gap: '0.5rem', marginBottom: '0.4rem' }}>
              <input
                placeholder="Tier name"
                value={tier.tier_name}
                onChange={(e) => updateTier(i, { tier_name: e.target.value })}
                required
              />
              <input
                type="number"
                min="0.01"
                step="0.01"
                placeholder="Price"
                value={tier.price || ''}
                onChange={(e) => updateTier(i, { price: Number(e.target.value) })}
                required
              />
              {tiers.length > 1 && (
                <button type="button" className="secondary" onClick={() => removeTier(i)}>
                  Remove
                </button>
              )}
            </div>
          ))}
          <button type="button" className="secondary" onClick={addTier}>
            + Add tier
          </button>
        </div>

        <div className="form-field">
          <label>Target demographic (optional)</label>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.5rem' }}>
            <input placeholder="Age min" type="number" value={ageMin} onChange={(e) => setAgeMin(e.target.value)} />
            <input placeholder="Age max" type="number" value={ageMax} onChange={(e) => setAgeMax(e.target.value)} />
            <input placeholder="Gender" value={gender} onChange={(e) => setGender(e.target.value)} />
            <input
              placeholder="Income segment"
              value={incomeSegment}
              onChange={(e) => setIncomeSegment(e.target.value)}
            />
            <input placeholder="Region" value={region} onChange={(e) => setRegion(e.target.value)} />
            <input placeholder="Lifestyle" value={lifestyle} onChange={(e) => setLifestyle(e.target.value)} />
          </div>
        </div>

        <div className="form-field">
          <label htmlFor="promo">Promotional messaging (optional)</label>
          <textarea
            id="promo"
            rows={2}
            value={promotionalMessaging}
            onChange={(e) => setPromotionalMessaging(e.target.value)}
          />
        </div>

        <div className="form-field">
          <label htmlFor="variantCount">Variants per round (1-20)</label>
          <input
            id="variantCount"
            type="number"
            min={1}
            max={20}
            value={variantCount}
            onChange={(e) => setVariantCount(Number(e.target.value))}
          />
        </div>

        <div className="form-field">
          <label htmlFor="maxIterations">Max iterations (optional, 1-10, default 3)</label>
          <input
            id="maxIterations"
            type="number"
            min={1}
            max={10}
            value={maxIterations}
            onChange={(e) => setMaxIterations(e.target.value === '' ? '' : Number(e.target.value))}
          />
        </div>

        {error && <p className="error-text">{error}</p>}
        <button type="submit" disabled={submitting}>
          {submitting ? 'Starting simulation…' : 'Run simulation'}
        </button>
      </form>
    </div>
  )
}

export default ScenarioConfigPage
