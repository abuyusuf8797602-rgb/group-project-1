import Home from './pages/Home.jsx'
import SignPage from './pages/SignPage.jsx'
import VerifyPage from './pages/VerifyPage.jsx'

function Layout({ children }) {
  return (
    <div className="page">
      <header className="app-header">
        <a className="brand" href="/">
          Document Signing
        </a>
        <nav>
          <a href="/">Documents</a>
          <a href="/verify">Verify</a>
        </nav>
      </header>
      {children}
    </div>
  )
}

export default function App() {
  const path = window.location.pathname

  if (path.startsWith('/sign/')) {
    return (
      <Layout>
        <SignPage token={decodeURIComponent(path.slice('/sign/'.length))} />
      </Layout>
    )
  }

  if (path === '/verify') {
    return (
      <Layout>
        <VerifyPage />
      </Layout>
    )
  }

  return (
    <Layout>
      <Home />
    </Layout>
  )
}
