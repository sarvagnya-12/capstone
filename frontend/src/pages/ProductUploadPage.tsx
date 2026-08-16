import { useEffect, useRef, useState, type FormEvent } from 'react'
import { Link } from 'react-router-dom'
import { apiErrorMessage } from '../api/client'
import { listProducts, productImagePath, uploadProduct, type Product } from '../api/products'
import AuthenticatedImage from '../components/AuthenticatedImage'

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
      setValidationError('Only JPEG or PNG images are supported.')
      return
    }
    if (selected.size > MAX_SIZE_BYTES) {
      setValidationError(`File too large (${(selected.size / 1024 / 1024).toFixed(1)}MB) -- max 10MB.`)
      return
    }
    if (selected.size === 0) {
      setValidationError('Selected file is empty.')
      return
    }
    setFile(selected)
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    setSubmitError(null)
    if (!file) {
      setValidationError('Please select a product image.')
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
      <div className="card">
        <h1>Upload a product</h1>
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
          <div className="form-field">
            <label htmlFor="category">Category</label>
            <input id="category" required value={category} onChange={(e) => setCategory(e.target.value)} />
          </div>
          <div className="form-field">
            <label htmlFor="brand">Brand (optional)</label>
            <input id="brand" value={brand} onChange={(e) => setBrand(e.target.value)} />
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
            <label htmlFor="image">Product image (JPEG/PNG, max 10MB)</label>
            <input
              id="image"
              type="file"
              accept="image/jpeg,image/png"
              ref={fileInputRef}
              onChange={(e) => handleFileChange(e.target.files?.[0] ?? null)}
            />
          </div>
          {validationError && <p className="error-text">{validationError}</p>}
          {submitError && <p className="error-text">{submitError}</p>}
          <button type="submit" disabled={submitting}>
            {submitting ? 'Uploading…' : 'Upload product'}
          </button>
        </form>
      </div>

      {justUploaded && (
        <div className="card">
          <p className="success-text">"{justUploaded.name}" uploaded successfully.</p>
          <Link to="/simulations/new" state={{ productId: justUploaded.id }}>
            Configure a launch scenario for this product →
          </Link>
        </div>
      )}

      <div className="card">
        <h2>Your products</h2>
        {loadingProducts && <p className="muted">Loading…</p>}
        {!loadingProducts && products.length === 0 && <p className="muted">No products uploaded yet.</p>}
        <div className="grid">
          {products.map((product) => (
            <div key={product.id} className="card">
              <AuthenticatedImage
                path={productImagePath(product.id)}
                alt={product.name}
                className="thumb"
              />
              <h3>{product.name}</h3>
              <p className="muted">{product.category}</p>
              <Link to="/simulations/new" state={{ productId: product.id }}>
                Run a simulation →
              </Link>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

export default ProductUploadPage
