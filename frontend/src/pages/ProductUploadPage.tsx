import { useEffect, useRef, useState, type FormEvent } from 'react'
import { Link } from 'react-router-dom'
import { apiErrorMessage } from '../api/client'
import { listProducts, productImagePath, uploadProduct, type Product } from '../api/products'
import AuthenticatedImage from '../components/AuthenticatedImage'
import { CheckMark, FlagMark, RuleArrow } from '../components/Icon'

const ALLOWED_TYPES = new Set(['image/jpeg', 'image/png'])
const MAX_SIZE_BYTES = 10 * 1024 * 1024

function ProductUploadPage() {
  const [products, setProducts] = useState<Product[]>([])
  const [loadingProducts, setLoadingProducts] = useState(true)

  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [category, setCategory] = useState('')
  const [brand, setBrand] = useState('')
  const [brandingDetails, setBrandingDetails] = useState('')
  const [file, setFile] = useState<File | null>(null)
  const [validationError, setValidationError] = useState<string | null>(null)
  const [submitError, setSubmitError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)
  const [justUploaded, setJustUploaded] = useState<Product | null>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)

  function refreshProducts() {
    setLoadingProducts(true)
    listProducts()
      .then(setProducts)
      .catch(() => setProducts([]))
      .finally(() => setLoadingProducts(false))
  }

  useEffect(refreshProducts, [])

  function handleFileChange(selected: File | null) {
    setValidationError(null)
    setFile(null)
    if (!selected) return

    if (!ALLOWED_TYPES.has(selected.type)) {
      setValidationError('That file is not a JPEG or PNG. Export the photo as one of those and try again.')
      return
    }
    if (selected.size > MAX_SIZE_BYTES) {
      setValidationError(
        `That image is ${(selected.size / 1024 / 1024).toFixed(1)}MB. The limit is 10MB — save it at a smaller size and try again.`,
      )
      return
    }
    if (selected.size === 0) {
      setValidationError('That file is empty. Pick the photo again.')
      return
    }
    setFile(selected)
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    setSubmitError(null)
    if (!file) {
      setValidationError('Choose a product photo before uploading.')
      return
    }

    setSubmitting(true)
    try {
      const product = await uploadProduct({
        name,
        description,
        category,
        brand: brand || undefined,
        brandingDetails: brandingDetails || undefined,
        image: file,
      })
      setJustUploaded(product)
      setName('')
      setDescription('')
      setCategory('')
      setBrand('')
      setBrandingDetails('')
      setFile(null)
      if (fileInputRef.current) fileInputRef.current.value = ''
      refreshProducts()
    } catch (err) {
      setSubmitError(apiErrorMessage(err))
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div>
      <section className="card">
        <h1>Upload a product</h1>
        <p className="prose muted">
          The photo you upload is what every design option is rendered from, so a clear shot of the product on a
          plain background gives the most usable variants. The simulated customers are grounded in a footwear
          review corpus — results outside footwear are not meaningful yet.
        </p>
        <form onSubmit={handleSubmit}>
          <div className="form-field">
            <label htmlFor="name">Name</label>
            <input id="name" required value={name} onChange={(e) => setName(e.target.value)} />
          </div>
          <div className="form-field">
            <label htmlFor="description">Description</label>
            <textarea
              id="description"
              required
              rows={3}
              value={description}
              onChange={(e) => setDescription(e.target.value)}
            />
          </div>
          <div className="field-grid">
            <div className="form-field">
              <label htmlFor="category">Category</label>
              <input id="category" required value={category} onChange={(e) => setCategory(e.target.value)} />
            </div>
            <div className="form-field">
              <label htmlFor="brand">Brand (optional)</label>
              <input id="brand" value={brand} onChange={(e) => setBrand(e.target.value)} />
            </div>
          </div>
          <div className="form-field">
            <label htmlFor="brandingDetails">Branding details (optional)</label>
            <textarea
              id="brandingDetails"
              rows={2}
              value={brandingDetails}
              onChange={(e) => setBrandingDetails(e.target.value)}
            />
          </div>
          <div className="form-field">
            <label htmlFor="image">Product photo</label>
            <input
              id="image"
              type="file"
              accept="image/jpeg,image/png"
              ref={fileInputRef}
              onChange={(e) => handleFileChange(e.target.files?.[0] ?? null)}
              aria-invalid={validationError ? true : undefined}
            />
            <span className="form-hint">JPEG or PNG, up to 10MB.</span>
          </div>
          {validationError && (
            <p className="error-text">
              <FlagMark /> {validationError}
            </p>
          )}
          {submitError && (
            <p className="error-text">
              <FlagMark /> {submitError}
            </p>
          )}
          <button type="submit" disabled={submitting}>
            {submitting ? 'Uploading…' : 'Upload product'}
          </button>
        </form>
      </section>

      {justUploaded && (
        <section className="card notice">
          <p className="success-text" style={{ marginTop: 0 }}>
            <CheckMark /> “{justUploaded.name}” uploaded.
          </p>
          <div className="actions">
            <Link to="/simulations/new" state={{ productId: justUploaded.id }}>
              <button type="button">
                Configure a launch scenario <RuleArrow />
              </button>
            </Link>
          </div>
        </section>
      )}

      <section className="card">
        <h2>Your products</h2>
        {loadingProducts && <p className="loading">Loading your products…</p>}
        {!loadingProducts && products.length === 0 && (
          <div className="empty">
            <div className="empty-body">
              <h3>Nothing uploaded yet</h3>
              <p className="muted">
                Products you upload appear here with their photo, ready to run a launch scenario against.
              </p>
            </div>
          </div>
        )}
        {products.length > 0 && (
          <ul className="option-grid product-list">
            {products.map((product) => (
              <li key={product.id} className="product-item">
                <AuthenticatedImage path={productImagePath(product.id)} alt={product.name} className="thumb" />
                <div className="product-item-body">
                  <h3>{product.name}</h3>
                  <p className="muted">{product.category}</p>
                  <Link to="/simulations/new" state={{ productId: product.id }}>
                    Run a simulation
                  </Link>
                </div>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  )
}

export default ProductUploadPage
