import { apiFetch } from './client'

export interface Product {
  id: string
  user_id: string
  name: string
  description: string
  brand: string | null
  category: string
  branding_details: string | null
  original_image_path: string
  preprocessed_image_path: string | null
  created_at: string
}

export function listProducts(): Promise<Product[]> {
  return apiFetch<Product[]>('/api/v1/products')
}

export function getProduct(productId: string): Promise<Product> {
  return apiFetch<Product>(`/api/v1/products/${productId}`)
}

export interface UploadProductInput {
  name: string
  description: string
  category: string
  brand?: string
  brandingDetails?: string
  image: File
}

export function uploadProduct(input: UploadProductInput): Promise<Product> {
  const formData = new FormData()
  formData.set('name', input.name)
  formData.set('description', input.description)
  formData.set('category', input.category)
  if (input.brand) formData.set('brand', input.brand)
  if (input.brandingDetails) formData.set('branding_details', input.brandingDetails)
  formData.set('image', input.image)

  return apiFetch<Product>('/api/v1/products', { method: 'POST', body: formData })
}

export function productImagePath(productId: string, kind: 'original' | 'preprocessed' = 'original'): string {
  return `/api/v1/products/${productId}/image?kind=${kind}`
}
