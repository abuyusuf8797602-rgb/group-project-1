import { useState } from 'react'

import { api } from '../api.js'

function CopyButton({ value, label = 'Copy' }) {
  const [copied, setCopied] = useState(false)

  async function copy() {
    try {
      await navigator.clipboard.writeText(value)
      setCopied(true)
      setTimeout(() => setCopied(false), 1500)
    } catch {
      setCopied(false)
    }
  }

  return (
    <button type="button" className="ghost" onClick={copy}>
      {copied ? 'Copied' : label}
    </button>
  )
}

function decryptCommand(token) {
  return `python -m app.cli decrypt --token ${token} --private-key recipient.key --out document`
}

function SharedDetails({ doc }) {
  const exchange = doc.key_exchange
  const command = decryptCommand(doc.token)

  return (
    <>
      <p className="item-desc">
        Key wrapped for {exchange.recipient_name} &lt;{exchange.recipient_email}&gt; by X25519 key
        exchange.
      </p>
      <p className="mono hint">recipient key fingerprint {exchange.recipient_fingerprint}</p>

      <details className="envelope">
        <summary>Envelope details</summary>
        <dl className="envelope-list">
          <dt>ephemeral public key</dt>
          <dd className="mono">{exchange.ephemeral_public_key.trim()}</dd>
          <dt>HKDF salt</dt>
          <dd className="mono">{exchange.salt}</dd>
          <dt>wrapped data key</dt>
          <dd className="mono">{exchange.wrapped_key}</dd>
        </dl>
      </details>

      <p className="label">Recipient decrypts locally (private key never uploaded)</p>
      <div className="link-row">
        <input readOnly value={command} aria-label="Decrypt command" onFocus={(e) => e.target.select()} />
        <CopyButton value={command} />
      </div>
    </>
  )
}

export default function KeyExchangePanel({ doc, onShared }) {
  const [name, setName] = useState('')
  const [email, setEmail] = useState('')
  const [publicKey, setPublicKey] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)

  async function submit(event) {
    event.preventDefault()
    setBusy(true)
    setError(null)
    try {
      await api.createKeyExchange(doc.token, {
        recipient_name: name,
        recipient_email: email,
        recipient_public_key: publicKey,
      })
      setName('')
      setEmail('')
      setPublicKey('')
      await onShared()
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="share">
      <p className="label">Secure sharing</p>
      {doc.key_exchange ? (
        <SharedDetails doc={doc} />
      ) : (
        <form className="form" onSubmit={submit}>
          <p className="item-desc">
            Generate a keypair with <code>python -m app.cli keygen</code> and paste the public key
            here. The document key is wrapped for that key, so only the recipient can decrypt the
            file.
          </p>
          <div className="field-row">
            <label className="field">
              <span className="label">Recipient name</span>
              <input value={name} required onChange={(e) => setName(e.target.value)} />
            </label>
            <label className="field">
              <span className="label">Recipient email</span>
              <input type="email" value={email} required onChange={(e) => setEmail(e.target.value)} />
            </label>
          </div>
          <label className="field">
            <span className="label">Recipient public key (PEM)</span>
            <textarea
              rows={4}
              value={publicKey}
              required
              placeholder="-----BEGIN PUBLIC KEY-----&#10;…&#10;-----END PUBLIC KEY-----"
              onChange={(e) => setPublicKey(e.target.value)}
            />
          </label>
          <button type="submit" disabled={busy}>
            {busy ? 'Wrapping key…' : 'Share encrypted copy'}
          </button>
        </form>
      )}
      {error && <p className="error">{error}</p>}
    </div>
  )
}
