import { useRef, useState } from 'react'

import { api } from '../api.js'

export default function VerifyPage() {
  const [result, setResult] = useState(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)
  const fileRef = useRef(null)

  async function verify(event) {
    event.preventDefault()
    const file = fileRef.current?.files?.[0]
    if (!file) return

    setBusy(true)
    setError(null)
    setResult(null)
    try {
      setResult(await api.verifyDocument(file))
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <>
      <h1>Verify a document</h1>
      <p className="subtitle">
        Upload a file to check whether it matches a signed document and whether its signature is
        still valid.
      </p>

      <form className="card form" onSubmit={verify}>
        <label className="field">
          <span className="label">File to verify</span>
          <input ref={fileRef} type="file" aria-label="File to verify" />
        </label>
        <button type="submit" disabled={busy}>
          {busy ? 'Verifying…' : 'Verify'}
        </button>
      </form>

      {error && <p className="error">{error}</p>}

      {result && (
        <section className="card">
          <div className={`banner ${result.matched && result.verified ? 'ok' : 'no'}`}>
            {!result.matched
              ? 'No signature found for this file — it does not match any signed document.'
              : result.verified
                ? 'Signature valid — this file matches a signed document.'
                : 'A signed document was found, but one or more checks failed.'}
          </div>

          <p className="mono hint">Uploaded SHA-256 {result.file_sha256}</p>

          {result.matched && (
            <>
              <dl className="meta">
                <div>
                  <dt>Signed by</dt>
                  <dd>
                    {result.signature.signer_name} &lt;{result.signature.signer_email}&gt;
                  </dd>
                </div>
                <div>
                  <dt>Document</dt>
                  <dd>{result.document.filename}</dd>
                </div>
              </dl>

              <ul className="checks">
                {result.checks.map((check) => (
                  <li key={check.name} className={check.passed ? 'pass' : 'fail'}>
                    <span className="mark" aria-hidden="true">
                      {check.passed ? '✓' : '✕'}
                    </span>
                    <span>
                      <strong>{check.name}</strong> — {check.detail}
                    </span>
                  </li>
                ))}
              </ul>
            </>
          )}
        </section>
      )}
    </>
  )
}
