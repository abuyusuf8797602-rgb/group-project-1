const API = '/api'

async function handle(res) {
  if (!res.ok) {
    let message = `Request failed (${res.status})`
    try {
      const body = await res.json()
      if (body?.detail) {
        message = typeof body.detail === 'string' ? body.detail : JSON.stringify(body.detail)
      }
    } catch {
      // keep the generic message
    }
    throw new Error(message)
  }
  return res.status === 204 ? null : res.json()
}

export const api = {
  listDocuments: () => fetch(`${API}/documents`).then(handle),

  uploadDocument: (file) => {
    const form = new FormData()
    form.append('file', file)
    return fetch(`${API}/documents`, { method: 'POST', body: form }).then(handle)
  },

  getDocument: (token) => fetch(`${API}/documents/${token}`).then(handle),

  signDocument: (token, payload) =>
    fetch(`${API}/documents/${token}/sign`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    }).then(handle),

  createKeyExchange: (token, payload) =>
    fetch(`${API}/documents/${token}/key-exchange`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    }).then(handle),

  verifyDocument: (file) => {
    const form = new FormData()
    form.append('file', file)
    return fetch(`${API}/verify`, { method: 'POST', body: form }).then(handle)
  },

  downloadUrl: (token) => `${API}/documents/${token}/download`,

  ciphertextUrl: (token) => `${API}/documents/${token}/ciphertext`,
}

export function formatBytes(bytes) {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

// Backend timestamps are naive UTC; show them plainly rather than guessing a zone.
export function formatTimestamp(value) {
  return `${value.replace('T', ' ').slice(0, 19)} UTC`
}
