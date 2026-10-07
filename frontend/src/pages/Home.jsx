import { useEffect, useRef, useState } from 'react'

import { api, formatBytes, formatTimestamp } from '../api.js'

function signingLink(token) {
  return `${window.location.origin}/sign/${token}`
}

function SigningLink({ token }) {
  const [copied, setCopied] = useState(false)
  const link = signingLink(token)

  async function copy() {
    try {
      await navigator.clipboard.writeText(link)
      setCopied(true)
      setTimeout(() => setCopied(false), 1500)
    } catch {
      setCopied(false)
    }
  }

  return (
    <div className="link-row">
      <input readOnly value={link} aria-label="Signing link" onFocus={(e) => e.target.select()} />
      <button type="button" className="ghost" onClick={copy}>
        {copied ? 'Copied' : 'Copy'}
      </button>
    </div>
  )
}

export default function Home() {
  const [documents, setDocuments] = useState([])
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)
  const fileRef = useRef(null)

  async function load() {
    try {
      setDocuments(await api.listDocuments())
      setError(null)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    load()
  }, [])

  async function upload(event) {
    event.preventDefault()
    const file = fileRef.current?.files?.[0]
    if (!file) return

    setBusy(true)
    setError(null)
    try {
      await api.uploadDocument(file)
      if (fileRef.current) fileRef.current.value = ''
      await load()
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <>
      <h1>Documents</h1>
      <p className="subtitle">
        Upload a document to create a signing link, then send that link to the signer.
      </p>

      <form className="card form" onSubmit={upload}>
        <label className="field">
          <span className="label">Document</span>
          <input ref={fileRef} type="file" aria-label="Document to sign" />
        </label>
        <button type="submit" disabled={busy}>
          {busy ? 'Uploading…' : 'Create signing link'}
        </button>
      </form>

      {error && <p className="error">{error}</p>}

      <section className="card">
        <div className="list-header">
          <h2>Uploaded</h2>
          <span className="count">{documents.length}</span>
        </div>

        {loading ? (
          <p className="muted">Loading…</p>
        ) : documents.length === 0 ? (
          <p className="muted">No documents yet — upload one above.</p>
        ) : (
          <ul className="list">
            {documents.map((doc) => (
              <li key={doc.id} className="doc">
                <div className="doc-head">
                  <div>
                    <p className="item-title">{doc.filename}</p>
                    <p className="item-desc">
                      {formatBytes(doc.size)} · uploaded {formatTimestamp(doc.created_at)}
                    </p>
                  </div>
                  <span className={`badge ${doc.signature ? 'ok' : 'pending'}`}>
                    {doc.signature ? 'Signed' : 'Awaiting signature'}
                  </span>
                </div>

                {doc.signature && (
                  <p className="item-desc">
                    Signed by {doc.signature.signer_name} &lt;{doc.signature.signer_email}&gt; at{' '}
                    {formatTimestamp(doc.signature.signed_at)}
                  </p>
                )}

                <SigningLink token={doc.token} />

                <p className="mono hint">SHA-256 {doc.sha256}</p>
              </li>
            ))}
          </ul>
        )}
      </section>
    </>
  )
}
