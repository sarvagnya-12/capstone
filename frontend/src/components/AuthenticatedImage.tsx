import { useEffect, useState } from 'react'
import { apiFetchBlob } from '../api/client'

/** Renders an image served from an authenticated API endpoint. A plain
 * <img src="..."> can't attach an Authorization header, and every image
 * route in this app is ownership-scoped (Step 34/36) rather than a public
 * static mount -- so the image bytes are fetched via apiFetchBlob and
 * turned into an object URL instead. */
export default function AuthenticatedImage({
  path,
  alt,
  className,
}: {
  path: string
  alt: string
  className?: string
}) {
  const [objectUrl, setObjectUrl] = useState<string | null>(null)
  const [failed, setFailed] = useState(false)

  useEffect(() => {
    let currentUrl: string | null = null
    let cancelled = false

    setFailed(false)
    apiFetchBlob(path)
      .then((blob) => {
        if (cancelled) return
        currentUrl = URL.createObjectURL(blob)
        setObjectUrl(currentUrl)
      })
      .catch(() => {
        if (!cancelled) setFailed(true)
      })

    return () => {
      cancelled = true
      if (currentUrl) URL.revokeObjectURL(currentUrl)
    }
  }, [path])

  if (failed) {
    return (
      <div className={className} style={{ display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <span className="muted">Image unavailable</span>
      </div>
    )
  }

  if (!objectUrl) {
    return <div className={className} aria-busy="true" />
  }

  return <img src={objectUrl} alt={alt} className={className} />
}
