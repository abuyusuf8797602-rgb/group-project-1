import { useEffect, useState } from 'react'

import { api, formatBytes, formatTimestamp } from '../api.js'

function SignatureSummary({ signature, token }) {
  return (
    <div className="banner ok">
      This document was signed by {signature.signer_name} &lt;{signature.signer_email}&gt; at{' '}
      {formatTimestamp(signature.signed_at)}.
      <p className="mono hint">Signer signature: {signature.hmac_signature.slice(0, 32)}…</p>
      <p>
        <a href={api.downloadUrl(token)}>Download document</a>
      </p>
    </div>
  )
}

export default function SignPage({ token }) {
  const [document, setDocument] = useState(null)
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)
  const [name, setName] = useState('')
  const [email, setEmail] = useState('')

  async function load() {
    try {
      setDocument(await api.getDocument(token))
      setError(null)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    load()
  }, [token])

  async function sign(event) {
    event.preventDefault()
    setBusy(true)
    setError(null)
    try {
      await api.signDocument(token, { name: name.trim(), email: email.trim() })
      await load()
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  if (loading) return <p className="muted">Loading…</p>
  if (!document) return <p className="error">{error ?? 'Document not found'}</p>

  return (
    <>
      <h1>Sign document</h1>
      <p className="subtitle">You have been asked to sign the document below.</p>

      <section className="card">
        <div className="doc-head">
          <div>
            <p className="item-title">{document.filename}</p>
            <p className="item-desc">
              {formatBytes(document.size)} · uploaded {formatTimestamp(document.created_at)}
            </p>
          </div>
          <span className={`badge ${document.signature ? 'ok' : 'pending'}`}>
            {document.signature ? 'Signed' : 'Awaiting signature'}
          </span>
        </div>
        <p className="mono hint">SHA-256 {document.sha256}</p>
        <p>
          <a href={api.downloadUrl(token)}>Download and review the document</a>
        </p>
      </section>

      {error && <p className="error">{error}</p>}

      {document.signature ? (
        <SignatureSummary signature={document.signature} token={token} />
      ) : (
        <form className="card form" onSubmit={sign}>
          <label className="field">
            <span className="label">Full name</span>
            <input
              value={name}
              onChange={(e) => setName(e.target.value)}
              aria-label="Full name"
              maxLength={200}
              placeholder="Ada Lovelace"
            />
          </label>
          <label className="field">
            <span className="label">Email</span>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              aria-label="Email"
              placeholder="ada@example.com"
            />
          </label>
          <button type="submit" disabled={busy || !name.trim() || !email.trim()}>
            {busy ? 'Signing…' : 'Sign document'}
          </button>
        </form>
      )}
    </>
  )
}
