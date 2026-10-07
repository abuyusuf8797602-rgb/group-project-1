import { useEffect, useState } from 'react'

const API = '/api'

export default function App() {
  const [items, setItems] = useState([])
  const [title, setTitle] = useState('')
  const [description, setDescription] = useState('')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  async function load() {
    try {
      const res = await fetch(`${API}/items`)
      if (!res.ok) throw new Error(`Request failed (${res.status})`)
      setItems(await res.json())
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

  async function addItem(event) {
    event.preventDefault()
    if (!title.trim()) return

    const res = await fetch(`${API}/items`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ title: title.trim(), description: description.trim() }),
    })

    if (!res.ok) {
      setError(`Could not add item (${res.status})`)
      return
    }

    setTitle('')
    setDescription('')
    await load()
  }

  async function removeItem(id) {
    const res = await fetch(`${API}/items/${id}`, { method: 'DELETE' })
    if (!res.ok) {
      setError(`Could not delete item (${res.status})`)
      return
    }
    await load()
  }

  return (
    <div className="page">
      <header>
        <h1>Group Project 1</h1>
        <p className="subtitle">React frontend · FastAPI backend · PostgreSQL</p>
      </header>

      <form className="card form" onSubmit={addItem}>
        <input
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          placeholder="Title"
          maxLength={200}
          aria-label="Title"
        />
        <input
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          placeholder="Description (optional)"
          maxLength={2000}
          aria-label="Description"
        />
        <button type="submit" disabled={!title.trim()}>
          Add item
        </button>
      </form>

      {error && <p className="error">{error}</p>}

      <section className="card">
        <div className="list-header">
          <h2>Items</h2>
          <span className="count">{items.length}</span>
        </div>

        {loading ? (
          <p className="muted">Loading…</p>
        ) : items.length === 0 ? (
          <p className="muted">No items yet — add one above.</p>
        ) : (
          <ul className="list">
            {items.map((item) => (
              <li key={item.id}>
                <div>
                  <p className="item-title">{item.title}</p>
                  {item.description && <p className="item-desc">{item.description}</p>}
                </div>
                <button className="delete" onClick={() => removeItem(item.id)} aria-label={`Delete ${item.title}`}>
                  Delete
                </button>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  )
}
