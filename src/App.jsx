import { useEffect, useRef, useState } from 'react'
import './App.css'

const API_BASE = `${import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'}/api`
const defaultStats = { total_scenes: 0, total_tiles: 0, detected_changes: 0, pending_reviews: 0, high_confidence_changes: 0 }
const navItems = [
  ['dashboard', 'Dashboard'],
  ['semantic-search', 'Semantic search'],
  ['image-search', 'Image search'],
  ['datasets', 'Data sources'],
  ['change-analysis', 'Change analysis'],
  ['similar-sites', 'Similar sites'],
  ['review', 'Review queue'],
  ['provenance', 'Provenance'],
  ['evaluation', 'Evaluation'],
]
const roleNavigation = {
  ANALYST: navItems,
  RESEARCHER: [['dashboard', 'Research dashboard'], ['datasets', 'Datasets'], ['evaluation', 'Experiments'], ['provenance', 'Provenance'], ['profile', 'Profile']],
  ADMIN: [['dashboard', 'Admin dashboard'], ['admin-users', 'Users'], ['datasets', 'Data sources'], ['image-search', 'Data ingestion'], ['evaluation', 'Evaluation'], ['provenance', 'System provenance'], ['profile', 'Profile']],
}

function App() {
  const [user, setUser] = useState(null)
  const [authReady, setAuthReady] = useState(false)
  const [activeView, setActiveView] = useState('dashboard')
  const [helpOpen, setHelpOpen] = useState(false)
  const [health, setHealth] = useState({ status: 'offline', database: 'Unavailable', model: 'Local baseline' })
  const [stats, setStats] = useState(defaultStats)
  const [changes, setChanges] = useState([])
  const [reviewQueue, setReviewQueue] = useState([])
  const [statusMessage, setStatusMessage] = useState('System ready for analysis')
  const [query, setQuery] = useState('newly built structures near a river')
  const [results, setResults] = useState([])
  const [searchFilterOptions, setSearchFilterOptions] = useState({ sensors: [], aois: [] })
  const [dateRange, setDateRange] = useState('')
  const [sensorFilter, setSensorFilter] = useState('')
  const [cloudFilter, setCloudFilter] = useState('')
  const [aoiFilter, setAoiFilter] = useState('')
  const [selectedFile, setSelectedFile] = useState(null)
  const [beforeId, setBeforeId] = useState('')
  const [afterId, setAfterId] = useState('')
  const [analysisResult, setAnalysisResult] = useState(null)
  const [busy, setBusy] = useState(false)
  const [reviewStates, setReviewStates] = useState({})
  const [provenanceSceneId, setProvenanceSceneId] = useState('')

  useEffect(() => {
    const token = window.localStorage.getItem('geowatch_session')
    if (!token) {
      const readyTimer = window.setTimeout(() => setAuthReady(true), 0)
      return () => window.clearTimeout(readyTimer)
    }
    fetch(`${API_BASE}/auth/me`, { headers: { Authorization: `Bearer ${token}` } })
      .then((response) => response.ok ? response.json() : Promise.reject(new Error('Session expired')))
      .then((payload) => setUser(payload.user))
      .catch(() => window.localStorage.removeItem('geowatch_session'))
      .finally(() => setAuthReady(true))
    return undefined
  }, [])

  const refreshData = async () => {
    try {
      const responses = await Promise.all([
        fetch(`${API_BASE}/health`),
        fetch(`${API_BASE}/stats`),
        fetch(`${API_BASE}/change`),
        fetch(`${API_BASE}/review/queue`),
      ])
      const [healthData, statsData, changeData, reviewData] = await Promise.all(responses.map((response) => response.json()))
      const queue = Array.isArray(reviewData.queue) ? reviewData.queue : []
      setHealth(healthData)
      setStats(statsData)
      setChanges(changeData.changes || [])
      setReviewQueue(Array.from(new Map(queue.map((item) => [item.id, item])).values()))
    } catch {
      setHealth({ status: 'offline', database: 'Unavailable', model: 'Local baseline' })
      setStatusMessage('Backend unavailable. Start FastAPI on port 8000.')
    }
  }

  useEffect(() => {
    if (!user) return undefined
    const initialLoad = window.setTimeout(refreshData, 0)
    const timer = window.setInterval(refreshData, 15000)
    return () => {
      window.clearTimeout(initialLoad)
      window.clearInterval(timer)
    }
  }, [user])

  useEffect(() => {
    if (!user) return undefined
    let cancelled = false
    fetch(`${API_BASE}/search/filters`)
      .then((response) => response.ok ? response.json() : Promise.reject(new Error('Filter options unavailable')))
      .then((options) => {
        if (!cancelled) setSearchFilterOptions({ sensors: options.sensors || [], aois: options.aois || [] })
      })
      .catch(() => {
        if (!cancelled) setSearchFilterOptions({ sensors: [], aois: [] })
      })
    return () => { cancelled = true }
  }, [user])

  const authenticate = async (mode, values) => {
    const endpoint = mode === 'signin' ? 'signin' : 'signup'
    const response = await fetch(`${API_BASE}/auth/${endpoint}`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(values) })
    const payload = await response.json()
    if (!response.ok) throw new Error(payload.detail || 'Authentication request failed')
    if (mode === 'signup') return payload.message
    window.localStorage.setItem('geowatch_session', payload.token)
    setUser(payload.user)
    return `Welcome, ${payload.user.full_name}`
  }

  const logout = async () => {
    const token = window.localStorage.getItem('geowatch_session')
    await fetch(`${API_BASE}/auth/logout`, { method: 'POST', headers: { Authorization: `Bearer ${token}` } }).catch(() => undefined)
    window.localStorage.removeItem('geowatch_session')
    setUser(null)
  }

  if (!authReady) return <div className="auth-loading">Loading secure workspace...</div>
  if (!user) return <AuthScreen onAuthenticate={authenticate} />

  const runSearch = async (event) => {
    event.preventDefault()
    if (!query.trim()) return
    setBusy(true)
    try {
      const dateFrom = dateRange ? new Date(Date.now() - Number(dateRange) * 24 * 60 * 60 * 1000).toISOString() : null
      const response = await fetch(`${API_BASE}/search/semantic`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          query,
          date_from: dateFrom,
          sensor: sensorFilter || null,
          max_cloud_cover: cloudFilter === '' ? null : Number(cloudFilter),
          aoi: aoiFilter || null,
        }),
      })
      const payload = await response.json()
      if (!response.ok) throw new Error(payload.detail || 'Search failed')
      setResults(payload.results || [])
      setStatusMessage(`Baseline search complete: ${payload.results?.length || 0} eligible observations`)
    } catch (error) {
      setStatusMessage(error.message)
    } finally {
      setBusy(false)
    }
  }

  const uploadScene = async (searchSimilarSites = false) => {
    if (!selectedFile) return setStatusMessage('Choose a satellite image first.')
    setBusy(true)
    const formData = new FormData()
    formData.append('files', selectedFile)
    try {
      const response = await fetch(`${API_BASE}/ingestion`, { method: 'POST', body: formData })
      const payload = await response.json()
      if (!response.ok) throw new Error(payload.detail || 'Upload failed')
      const tileId = payload.files?.[0]?.tile_id
      if (tileId) {
        const searchUrl = searchSimilarSites ? `${API_BASE}/sites/similar/${encodeURIComponent(tileId)}` : `${API_BASE}/search/image`
        const requestOptions = searchSimilarSites ? undefined : { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ tile_id: tileId }) }
        const similarityResponse = await fetch(searchUrl, requestOptions)
        const similarityPayload = await similarityResponse.json()
        if (!similarityResponse.ok) throw new Error(similarityPayload.detail || 'Similarity search failed')
        setResults(similarityPayload.results || [])
        setStatusMessage(`Found ${similarityPayload.results?.length || 0} similar ${searchSimilarSites ? 'sites' : 'locations'} for ${selectedFile.name}`)
      } else {
        setStatusMessage(`Indexed ${selectedFile.name}; no tile was available for similarity search.`)
      }
      setSelectedFile(null)
      await refreshData()
    } catch (error) {
      setStatusMessage(error.message)
    } finally {
      setBusy(false)
    }
  }

  const runAnalysis = async (event) => {
    event.preventDefault()
    if (!beforeId || !afterId) return setStatusMessage('Select both before and after scene IDs.')
    setBusy(true)
    try {
      const response = await fetch(`${API_BASE}/change/analyze`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ scene_a_id: beforeId, scene_b_id: afterId }) })
      const payload = await response.json()
      if (!response.ok) throw new Error(payload.detail || 'Analysis failed')
      setAnalysisResult(payload.result)
      setStatusMessage('Change analysis completed with provenance recorded.')
      await refreshData()
    } catch (error) {
      setStatusMessage(error.message)
    } finally {
      setBusy(false)
    }
  }

  const decideReview = async (changeId, decision) => {
    setReviewStates((previous) => ({ ...previous, [changeId]: 'saving' }))
    try {
      const action = decision === 'confirm' ? 'confirm' : 'reject'
      const response = await fetch(`${API_BASE}/review/${changeId}/${action}`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ decision, reason: decision === 'confirm' ? 'Confirmed by analyst.' : 'Rejected as false alarm.', reviewer: 'analyst' }) })
      const payload = await response.json()
      if (!response.ok) throw new Error(payload.detail || 'Review failed')
      setStatusMessage(`Detection ${changeId.slice(0, 8)} marked ${decision}.`)
      await refreshData()
    } catch (error) {
      setStatusMessage(error.message)
    } finally {
      setReviewStates((previous) => ({ ...previous, [changeId]: 'idle' }))
    }
  }

  const visibleNavigation = roleNavigation[user.role] || navItems
  const title = visibleNavigation.find(([key]) => key === activeView)?.[1] || 'Mission overview'
  const openProvenance = (sceneId) => {
    setProvenanceSceneId(sceneId)
    setActiveView('provenance')
  }
  return (
    <div className="app-shell intelligence-shell">
      <aside className="side-rail">
        <div className="brand-lockup"><span className="brand-mark">GW</span><div><strong>GeoWatch</strong><small>DGIS intelligence</small></div></div>
        <div className="rail-status"><i />Platform online</div>
        <nav>{visibleNavigation.map(([key, label]) => <button className={activeView === key ? 'rail-link active' : 'rail-link'} type="button" onClick={() => { if (key === 'similar-sites') setResults([]); setActiveView(key) }} key={key}><b>{label.slice(0, 1)}</b>{label}</button>)}</nav>
        <div className="rail-user"><span className="avatar">{user.full_name.slice(0, 2).toUpperCase()}</span><div><strong>{user.full_name}</strong><small>{user.role} · {user.status}</small></div><button type="button" onClick={logout} aria-label="Log out">↪</button></div>
      </aside>
      <main className="main-canvas">
        <header className="console-header"><div><span className="breadcrumb">Operations / {activeView.replace('-', ' ')}</span><h1>{title}</h1></div><div className="header-actions"><span className="sync-label"><i />Live sync</span><button className="icon-button" type="button" aria-label="Open workspace help" title="Help" onClick={() => setHelpOpen(true)}>?</button><button className="profile-button" type="button">AR</button></div></header>
        <div className="notice-bar"><span>{statusMessage}</span><small>Local-first processing - audit logging enabled</small></div>
        {activeView === 'dashboard' && <Dashboard stats={stats} changes={changes} onSearch={() => setActiveView('semantic-search')} />}
        {activeView === 'semantic-search' && <SearchView query={query} setQuery={setQuery} runSearch={runSearch} busy={busy} results={results} filterOptions={searchFilterOptions} dateRange={dateRange} setDateRange={setDateRange} sensorFilter={sensorFilter} setSensorFilter={setSensorFilter} cloudFilter={cloudFilter} setCloudFilter={setCloudFilter} aoiFilter={aoiFilter} setAoiFilter={setAoiFilter} />}
        {activeView === 'image-search' && <ImageView selectedFile={selectedFile} setSelectedFile={setSelectedFile} uploadScene={uploadScene} busy={busy} health={health} results={results} onViewProvenance={openProvenance} />}
        {activeView === 'change-analysis' && <ChangeView changes={changes} beforeId={beforeId} afterId={afterId} setBeforeId={setBeforeId} setAfterId={setAfterId} runAnalysis={runAnalysis} busy={busy} result={analysisResult} />}
        {activeView === 'review' && <ReviewView queue={reviewQueue} reviewStates={reviewStates} decideReview={decideReview} stats={stats} />}
        {activeView === 'similar-sites' && <ImageView selectedFile={selectedFile} setSelectedFile={setSelectedFile} uploadScene={uploadScene} busy={busy} health={health} results={results} onViewProvenance={openProvenance} searchSimilarSites title="Find related sites" kicker="Similar-site retrieval" description="Upload an image to find the closest matching indexed satellite tiles." actionLabel="Index image and find similar sites" />}
        {activeView === 'provenance' && <ProvenanceView selectedSceneId={provenanceSceneId} setSelectedSceneId={setProvenanceSceneId} />}
        {activeView === 'evaluation' && <EvaluationView />}
        {activeView === 'datasets' && <DatasetView />}
        {activeView === 'admin-users' && <AdminUsersView currentUserId={user?.id} />}
        {activeView === 'profile' && <ProfileView user={user} onLogout={logout} />}
        {helpOpen && <HelpDialog onClose={() => setHelpOpen(false)} onNavigate={(view) => { setHelpOpen(false); setActiveView(view) }} />}
      </main>
    </div>
  )
}

function AppDialog({ children, className = '', onClose }) {
  const dialogRef = useRef(null)

  useEffect(() => {
    if (dialogRef.current && !dialogRef.current.open) dialogRef.current.showModal()
  }, [])

  return <dialog ref={dialogRef} className={`app-dialog ${className}`} onClose={onClose} onClick={(event) => { if (event.target === event.currentTarget) onClose() }}>{children}</dialog>
}

function HelpDialog({ onClose, onNavigate }) {
  return <AppDialog className="help-dialog" onClose={onClose}>
    <div className="dialog-heading"><div><span className="section-kicker">Workspace support</span><h2>Help</h2></div><button className="dialog-close" type="button" onClick={onClose} aria-label="Close help">Close</button></div>
    <p className="help-dialog-copy">Open a workspace area or review the current data limitations.</p>
    <div className="help-links"><button type="button" onClick={() => onNavigate('image-search')}><strong>Image search</strong><span>View available satellite previews and location metadata.</span></button><button type="button" onClick={() => onNavigate('provenance')}><strong>System provenance</strong><span>Inspect source files, checksums, and processing records.</span></button><button type="button" onClick={() => onNavigate('evaluation')}><strong>Evaluation</strong><span>Run coverage checks and review staged label counts.</span></button></div>
    <p className="help-dialog-note">Model-quality scores require labeled evaluation examples. Synthetic fixtures do not have real map coordinates.</p>
  </AppDialog>
}

function AuthScreen({ onAuthenticate }) {
  const [mode, setMode] = useState('signin')
  const [values, setValues] = useState({ email: '', password: '', full_name: '', organization: '', role: 'ANALYST' })
  const [message, setMessage] = useState('')
  const [busy, setBusy] = useState(false)

  const submit = async (event) => {
    event.preventDefault()
    setBusy(true)
    setMessage('')
    try {
      const result = await onAuthenticate(mode, values)
      setMessage(result)
      if (mode === 'signup') setMode('signin')
    } catch (error) {
      setMessage(error.message)
    } finally {
      setBusy(false)
    }
  }

  return <main className="auth-screen"><section className="auth-brief"><span className="brand-mark">GW</span><span className="section-kicker">SIH26227 / authorized platform</span><h1>Satellite intelligence, made accountable.</h1><p>Search the archive, compare observations across time, and turn AI detections into traceable analyst decisions.</p><div className="auth-capabilities"><span>Semantic retrieval</span><span>Change analysis</span><span>Evidence provenance</span></div></section><section className="auth-card"><div className="auth-card-header"><span className="auth-overline">DGIS intelligence console</span><h2>{mode === 'signin' ? 'Sign in' : 'Request access'}</h2><p>{mode === 'signin' ? 'Use your authorized workspace account.' : 'Analyst and researcher accounts require administrator approval.'}</p></div><form onSubmit={submit}>{mode === 'signup' && <><label>Full name<input required value={values.full_name} onChange={(event) => setValues({ ...values, full_name: event.target.value })} /></label><label>Organization<input required value={values.organization} onChange={(event) => setValues({ ...values, organization: event.target.value })} /></label><label>Role<select value={values.role} onChange={(event) => setValues({ ...values, role: event.target.value })}><option value="ANALYST">Analyst</option><option value="RESEARCHER">Researcher</option></select></label></>}<label>Email<input type="email" autoComplete="username" required value={values.email} onChange={(event) => setValues({ ...values, email: event.target.value })} /></label><PasswordField value={values.password} onChange={(event) => setValues({ ...values, password: event.target.value })} /><button className="auth-submit" type="submit" disabled={busy}>{busy ? 'Checking access...' : mode === 'signin' ? 'Sign in to workspace' : 'Create pending account'}</button></form>{message && <p className="auth-message">{message}</p>}<button className="auth-switch" type="button" onClick={() => { setMode(mode === 'signin' ? 'signup' : 'signin'); setMessage('') }}>{mode === 'signin' ? "Don't have an account? Request access" : 'Already authorized? Sign in'}</button><small className="auth-security">Session protected · credentials are never exposed to the client</small></section></main>
}

function DatasetView() {
  const datasets = [
    ['Copernicus Sentinel-1 and Sentinel-2', 'European Union / Copernicus', 'Optical and SAR', 'https://dataspace.copernicus.eu/', 'Global'],
    ['USGS Landsat Collection 2', 'USGS / NASA', 'Multispectral and thermal', 'https://www.usgs.gov/landsat-missions/landsat-collection-2', 'Global'],
    ['NRSC / ISRO Bhuvan Earth Observation', 'National Remote Sensing Centre, ISRO', 'Earth observation imagery', 'https://bhuvan.nrsc.gov.in/', 'India'],
  ]

  return <section className="feature-view"><FeatureIntro kicker="Approved data sources" title="Build the archive from open Earth observation data" text="Imagery must be publicly accessible under applicable licences or provided by the organisers. This workspace keeps source, provider, coverage, and access terms visible before ingestion." /><div className="dataset-policy"><strong>Public-data policy</strong><span>No classified, operational, or service-generated data is used in this platform.</span></div><div className="dataset-grid">{datasets.map(([name, provider, kind, url, coverage]) => <article className="dataset-card" key={name}><div className="dataset-card-head"><span>{coverage}</span><b>PUBLIC</b></div><h3>{name}</h3><p>{provider}</p><small>{kind}</small><a href={url} target="_blank" rel="noreferrer">Open official source -&gt;</a></article>)}</div><div className="ingest-note"><span>Next step</span><strong>Download or connect through the provider's public access workflow, then ingest only validated imagery with its licence and source metadata.</strong></div></section>
}

function AdminUsersView({ currentUserId }) {
  const [users, setUsers] = useState([])
  const [message, setMessage] = useState('Loading user directory...')
  const [form, setForm] = useState({ full_name: '', email: '', organization: '', password: '', role: 'ANALYST', status: 'ACTIVE' })
  const [busy, setBusy] = useState(false)
  const [busyUserId, setBusyUserId] = useState('')
  const [query, setQuery] = useState('')
  const [roleFilter, setRoleFilter] = useState('ALL')

  const loadUsers = async () => {
    const token = window.localStorage.getItem('geowatch_session')
    const response = await fetch(`${API_BASE}/auth/admin/users`, { headers: { Authorization: `Bearer ${token}` } })
    const payload = await response.json()
    if (!response.ok) throw new Error(payload.detail || 'Unable to load users')
    setUsers(payload.users || [])
    setMessage('User directory is current.')
  }

  useEffect(() => {
    const timer = window.setTimeout(() => loadUsers().catch((error) => setMessage(error.message)), 0)
    return () => window.clearTimeout(timer)
  }, [])

  const createUser = async (event) => {
    event.preventDefault()
    setBusy(true)
    try {
      const token = window.localStorage.getItem('geowatch_session')
      const response = await fetch(`${API_BASE}/auth/admin/users`, { method: 'POST', headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` }, body: JSON.stringify(form) })
      const payload = await response.json()
      if (!response.ok) throw new Error(payload.detail || 'Unable to create user')
      setForm({ full_name: '', email: '', organization: '', password: '', role: 'ANALYST', status: 'ACTIVE' })
      setMessage(`${payload.user.full_name} was created and can sign in immediately.`)
      await loadUsers()
    } catch (error) {
      setMessage(error.message)
    } finally {
      setBusy(false)
    }
  }

  const updateStatus = async (item, status) => {
    setBusyUserId(item.id)
    try {
      const token = window.localStorage.getItem('geowatch_session')
      const response = await fetch(`${API_BASE}/auth/admin/users/${item.id}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify({ status }),
      })
      const payload = await response.json()
      if (!response.ok) throw new Error(payload.detail || 'Unable to update account status')
      setUsers((currentUsers) => currentUsers.map((userItem) => userItem.id === item.id ? payload.user : userItem))
      setMessage(`${item.full_name}'s access is now ${payload.user.status.toLowerCase()}.`)
    } catch (error) {
      setMessage(error.message)
    } finally {
      setBusyUserId('')
    }
  }

  const normalizedQuery = query.trim().toLowerCase()
  const visibleUsers = users.filter((item) => {
    const matchesQuery = [item.full_name, item.email, item.organization].some((value) => value.toLowerCase().includes(normalizedQuery))
    return matchesQuery && (roleFilter === 'ALL' || item.role === roleFilter)
  })
  const activeCount = users.filter((item) => item.status === 'ACTIVE').length
  const pendingCount = users.filter((item) => item.status === 'PENDING').length

  return <section className="feature-view admin-users-view">
    <FeatureIntro kicker="Administrator / access control" title="Create and manage users" text="Create accounts with the right role, find people in the directory, and control sign-in access. Passwords are stored as hashes." />
    <div className="admin-user-summary" aria-label="Account totals">
      <div><span>Total accounts</span><strong>{users.length}</strong></div>
      <div><span>Active</span><strong>{activeCount}</strong></div>
      <div><span>Pending approval</span><strong>{pendingCount}</strong></div>
    </div>
    <div className="admin-user-layout">
      <form className="admin-create-form" onSubmit={createUser}>
        <div className="panel-header"><span className="panel-label">Add user</span><span className="panel-action">New account</span></div>
        <p className="admin-form-copy">Set identity, role, and initial sign-in access.</p>
        <label>Full name<input autoComplete="name" required value={form.full_name} onChange={(event) => setForm({ ...form, full_name: event.target.value })} /></label>
        <label>Email<input autoComplete="email" required type="email" value={form.email} onChange={(event) => setForm({ ...form, email: event.target.value })} /></label>
        <label>Organization<input autoComplete="organization" required value={form.organization} onChange={(event) => setForm({ ...form, organization: event.target.value })} /></label>
        <PasswordField label="Temporary password" autoComplete="new-password" value={form.password} onChange={(event) => setForm({ ...form, password: event.target.value })} />
        <div className="admin-form-row">
          <label>Role<select value={form.role} onChange={(event) => setForm({ ...form, role: event.target.value })}><option value="ANALYST">Analyst</option><option value="RESEARCHER">Researcher</option><option value="ADMIN">Administrator</option></select></label>
          <label>Initial status<select value={form.status} onChange={(event) => setForm({ ...form, status: event.target.value })}><option value="ACTIVE">Active</option><option value="PENDING">Pending</option></select></label>
        </div>
        <button className="add-button" type="submit" disabled={busy}>{busy ? 'Creating account...' : 'Add user'}</button>
        <p className="admin-message" role="status" aria-live="polite">{message}</p>
      </form>
      <div className="user-directory">
        <div className="panel-header"><span className="panel-label">User directory</span><span className="panel-action">{visibleUsers.length} of {users.length}</span></div>
        <div className="admin-directory-tools">
          <label>Search accounts<input type="search" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Name, email, or organization" /></label>
          <label>Role<select value={roleFilter} onChange={(event) => setRoleFilter(event.target.value)}><option value="ALL">All roles</option><option value="ANALYST">Analyst</option><option value="RESEARCHER">Researcher</option><option value="ADMIN">Administrator</option></select></label>
        </div>
        <div className="admin-user-list">
          {visibleUsers.map((item) => <div className="user-row" key={item.id}>
            <span className="avatar small">{item.full_name.slice(0, 2).toUpperCase()}</span>
            <div className="user-identity"><strong>{item.full_name}</strong><small>{item.email} · {item.organization}</small><small>{item.last_login ? `Last sign-in ${new Date(item.last_login).toLocaleDateString()}` : 'Never signed in'}</small></div>
            <span className="user-role">{item.role}</span>
            <label className="user-status-control">
              <span className="sr-only">Access status for {item.full_name}</span>
              <select aria-label={`Access status for ${item.full_name}`} value={item.status} disabled={busyUserId === item.id || item.id === currentUserId} title={item.id === currentUserId ? 'Your administrator account cannot be suspended here.' : 'Change account access'} onChange={(event) => updateStatus(item, event.target.value)}>
                {item.status === 'PENDING' && <option value="PENDING" disabled>Pending</option>}
                <option value="ACTIVE">Active</option><option value="SUSPENDED">Suspended</option><option value="REJECTED">Rejected</option>
              </select>
            </label>
          </div>)}
          {visibleUsers.length === 0 && <p className="admin-empty">{users.length ? 'No accounts match these filters.' : 'No accounts found.'}</p>}
        </div>
      </div>
    </div>
  </section>
}

function PasswordField({ value, onChange, label = 'Password', autoComplete = 'current-password' }) {
  const [visible, setVisible] = useState(false)

  return <label>{label}<div className="password-field"><input type={visible ? 'text' : 'password'} autoComplete={autoComplete} required minLength="10" value={value} onChange={onChange} /><button type="button" className="password-toggle" onClick={() => setVisible((previous) => !previous)} aria-label={visible ? 'Hide password' : 'Show password'} aria-pressed={visible}>{visible ? 'Hide' : 'Show'}</button></div></label>
}

function Dashboard({ stats, changes, onSearch }) {
  return <><section className="workspace-hero"><div><span className="section-kicker">Analyst workspace / live intelligence</span><h2>Understand what changed.</h2><p>Search, compare, and review satellite observations in one auditable workspace.</p></div><button className="primary-button hero-action" type="button" onClick={onSearch}>Start semantic search <span>-&gt;</span></button></section><section className="metric-strip"><Metric label="Scenes indexed" value={stats.total_scenes} detail="Active collections" /><Metric label="Tiles searchable" value={stats.total_tiles} detail="Embedding coverage" /><Metric label="Pending review" value={stats.pending_reviews} detail="Needs decision" /><Metric label="High confidence" value={stats.high_confidence_changes} detail="Confidence >= 0.80" accent /></section><div className="content-grid"><section className="panel map-panel"><PanelTitle label="Operational map" action="Recent analysis" /><div className="map-surface"><span className="map-label north">N</span><span className="map-line line-one" /><span className="map-line line-two" /><span className="map-point point-one" /><span className="map-point point-two" /><span className="map-point point-three" /><div className="map-legend"><span><i className="legend-dot teal" />Active analysis</span><span><i className="legend-dot blue" />Indexed scene</span></div></div></section><section className="panel activity-panel"><PanelTitle label="Recent activity" action="My activity" />{changes.slice(0, 4).map((item) => <div className="activity-row" key={item.id}><span className="activity-icon">+</span><div><strong>{item.change_type || 'Change detection'}</strong><small>{item.scene_a_id?.slice(0, 12)} -&gt; {item.scene_b_id?.slice(0, 12)}</small></div><b>{Math.round((item.confidence || 0) * 100)}%</b></div>)}{changes.length === 0 && <Empty text="Run a change analysis to populate activity." />}</section></div><section className="panel workflow-panel"><PanelTitle label="Core workflow" action="Four stages" /><div className="workflow-steps"><WorkflowStep number="01" title="Find" text="Retrieve relevant observations using language or imagery." /><WorkflowStep number="02" title="Compare" text="Align the same area across dates and inspect evidence." /><WorkflowStep number="03" title="Detect" text="Suppress cloud, shadow, seasonal, and registration noise." /><WorkflowStep number="04" title="Decide" text="Confirm or reject the AI finding with an audit trail." /></div></section></>
}

function SearchView({ query, setQuery, runSearch, busy, results, filterOptions, dateRange, setDateRange, sensorFilter, setSensorFilter, cloudFilter, setCloudFilter, aoiFilter, setAoiFilter }) {
  return <section className="feature-view">
    <FeatureIntro kicker="Experimental local retrieval" title="Search imagery in plain language" text="This offline fallback compares keyword weights with image color histograms; it is not a trained text-image model. Results are exploratory, not semantic matches or confidence scores. Synthetic fixtures and missing files are excluded." />
    <form className="search-form" onSubmit={runSearch}>
      <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="e.g. large vehicle concentrations on open ground" />
      <button className="primary-button" type="submit" disabled={busy}>{busy ? 'Searching...' : 'Search index'}</button>
    </form>
    <div className="filter-row">
      <span>Filters</span>
      <label className="search-filter">Date<select value={dateRange} onChange={(event) => setDateRange(event.target.value)}><option value="">Any date</option><option value="30">Past 30 days</option><option value="365">Past year</option></select></label>
      <label className="search-filter">Sensor<select value={sensorFilter} onChange={(event) => setSensorFilter(event.target.value)}><option value="">All sensors</option>{filterOptions.sensors.map((sensor) => <option value={sensor} key={sensor}>{sensor}</option>)}</select></label>
      <label className="search-filter">Cloud cover<select value={cloudFilter} onChange={(event) => setCloudFilter(event.target.value)}><option value="">Any</option><option value="0.2">20% or less</option></select></label>
      <label className="search-filter">AOI<select value={aoiFilter} onChange={(event) => setAoiFilter(event.target.value)}><option value="">Global</option>{filterOptions.aois.map((aoi) => <option value={aoi.id} key={aoi.id}>{aoi.name}</option>)}</select></label>
    </div>
    <ResultTable results={results} emptyText="No eligible observations match this search and its filters." />
  </section>
}
function ImageView({ selectedFile, setSelectedFile, uploadScene, busy, health, results, onViewProvenance, searchSimilarSites = false, title = 'Find visually similar locations', kicker = 'Image retrieval', description = 'Upload a tile to discover similar sites across the indexed collection.', actionLabel = 'Index and find similar' }) {
  const handleUpload = () => uploadScene(searchSimilarSites)
  return <section className="feature-view"><FeatureIntro kicker={kicker} title={title} text={description} /><p className="image-search-help">{selectedFile ? <><strong>{selectedFile.name}</strong> is ready. Click the button to retrieve similar tiles.</> : "Choose a GeoTIFF, COG, PNG, or JPEG file to begin image-to-image search."}</p><div className="split-tool"><label className="drop-zone"><input type="file" accept=".tif,.tiff,.png,.jpg,.jpeg" onChange={(event) => setSelectedFile(event.target.files?.[0] || null)} /><span className="drop-symbol">+</span><strong>{selectedFile ? selectedFile.name : 'Drop a satellite image here'}</strong><small>GeoTIFF, COG, PNG or JPEG</small></label><div className="tool-notes"><div><b>Embedding model</b><span>{health.model || 'Local baseline encoder'}</span></div><div><b>Index status</b><span className="status-text"><i />{health.status === 'ok' ? 'Ready' : 'Offline'}</span></div><button className="primary-button" type="button" onClick={handleUpload} disabled={!selectedFile || busy}>{busy ? 'Indexing...' : actionLabel}</button></div></div><ResultTable results={results} onViewProvenance={onViewProvenance} /></section>
}
function ChangeView({ changes, beforeId, afterId, setBeforeId, setAfterId, runAnalysis, busy, result }) { return <section className="feature-view"><FeatureIntro kicker="Multi-temporal analysis" title="Compare the same area across time" text="Alignment, quality masking, normalization, noise filtering, and classification run as one traceable pipeline." /><form className="analysis-form" onSubmit={runAnalysis}><div className="form-field"><label>Before scene ID</label><select value={beforeId} onChange={(event) => setBeforeId(event.target.value)}><option value="">Select scene</option>{changes.map((item) => <option value={item.scene_a_id} key={`a-${item.id}`}>{item.scene_a_id}</option>)}</select></div><div className="form-field"><label>After scene ID</label><select value={afterId} onChange={(event) => setAfterId(event.target.value)}><option value="">Select scene</option>{changes.map((item) => <option value={item.scene_b_id} key={`b-${item.id}`}>{item.scene_b_id}</option>)}</select></div><button className="primary-button" type="submit" disabled={busy}>{busy ? 'Processing...' : 'Run change analysis'}</button></form><div className="comparison-stage"><div className="image-placeholder"><span>BEFORE</span><b>Earlier observation</b></div><div className="image-placeholder"><span>AFTER</span><b>Later observation</b></div><div className="comparison-tools"><button type="button">Swipe compare</button><button type="button">Zoom</button><button type="button">Coordinates</button></div></div>{result && <div className="result-callout"><span>Latest result</span><strong>{result.change_type}</strong><b>{Math.round(result.confidence * 100)}% confidence</b><small>Earliest observation: {result.earliest_supporting_observation}</small></div>}<div className="pipeline-row">{['Align', 'Quality mask', 'Normalize', 'Suppress noise', 'Classify'].map((step, index) => <span key={step}><i>{index + 1}</i>{step}</span>)}</div></section> }
function ReviewView({ queue, reviewStates, decideReview, stats }) { return <section className="feature-view"><FeatureIntro kicker="Analyst review" title="Turn model output into trusted intelligence" text="Review evidence, record a decision, and keep the result traceable to its source scenes and processing chain." /><div className="review-summary"><Metric label="Awaiting decision" value={queue.filter((item) => !item.decision).length} detail="Requires action" /><Metric label="Detected changes" value={stats.detected_changes} detail="All processing runs" /><Metric label="Precision priority" value="HIGH" detail="False alarms suppressed" accent /></div><div className="review-cards">{queue.slice(0, 8).map((item) => { const state = reviewStates[item.id] || 'idle'; return <article className="review-card" key={item.id}><div className="review-card-head"><span className={`decision-badge ${item.decision || 'pending'}`}>{item.decision || 'pending'}</span><small>{item.id}</small></div><h3>{item.change_type || 'Change detected'}</h3><p>{item.scene_a_id?.slice(0, 14)} -&gt; {item.scene_b_id?.slice(0, 14)}</p><div className="confidence-bar"><span style={{ width: `${Math.round((item.confidence || 0) * 100)}%` }} /></div><div className="review-card-foot"><b>{Math.round((item.confidence || 0) * 100)}% confidence</b><div><button className="review-btn accept" type="button" disabled={state === 'saving'} onClick={() => decideReview(item.id, 'confirm')}>Confirm</button><button className="review-btn reject" type="button" disabled={state === 'saving'} onClick={() => decideReview(item.id, 'reject')}>Reject</button></div></div></article> })}</div>{queue.length === 0 && <Empty text="No detections are waiting for review." />}</section> }
function Metric({ label, value, detail, accent = false }) { return <article className={accent ? 'metric-card accent' : 'metric-card'}><span>{label}</span><strong>{value}</strong><small>{detail}</small></article> }
function PanelTitle({ label, action }) { return <div className="panel-header"><span className="panel-label">{label}</span><span className="panel-action">{action}</span></div> }
function FeatureIntro({ kicker, title, text }) { return <div className="feature-intro"><span className="section-kicker">{kicker}</span><h2>{title}</h2><p>{text}</p></div> }
function WorkflowStep({ number, title, text }) { return <div className="workflow-step"><span>{number}</span><div><strong>{title}</strong><p>{text}</p></div></div> }
function ResultTable({ results, onViewProvenance, emptyText = 'No observations available.' }) {
  return <div className="results-panel"><div className="panel-header"><span className="panel-label">Ranked observations</span><span className="panel-action">Experimental baseline order</span></div>{results.length ? results.map((result, index) => {
    const isLegacyFixture = result.sensor === 'synthetic' || result.source === 'synthetic-test-data'
    const hasLocation = result.location && result.location !== '0,0'
    const location = hasLocation ? `${result.location}${result.crs ? ` · ${result.crs}` : ''}` : 'Location metadata unavailable'
    const date = isLegacyFixture ? 'Unverified test acquisition date' : result.date || result.acquisition_date || 'Acquisition date unavailable'
    const sensor = isLegacyFixture ? 'Legacy test fixture' : result.sensor || 'Sensor metadata unavailable'
    const source = isLegacyFixture ? 'Legacy test fixture' : result.source || 'Source metadata unavailable'
    return <div className="result-row" key={result.tile_id || result.id || index}><div className="result-preview"><TilePreview tileId={result.tile_id} /></div><div className="result-content"><strong>Tile {result.tile_id?.slice(0, 12) || 'unidentified'}</strong><small>{location}</small><small>{sensor} · {source}</small><small>{date}</small></div><div className="result-actions"><b>Rank {index + 1}</b>{onViewProvenance && result.scene_id && <button type="button" onClick={() => onViewProvenance(result.scene_id)}>Provenance</button>}</div></div>
  }) : <Empty text={emptyText} />}</div>
}

function TilePreview({ tileId }) {
  const [available, setAvailable] = useState(Boolean(tileId))
  const [zoomed, setZoomed] = useState(false)
  if (!available || !tileId) return <span className="preview-unavailable">Preview unavailable</span>
  const imageUrl = `${API_BASE}/tiles/${encodeURIComponent(tileId)}/image`
  return <>
    <button className="image-zoom-button" type="button" onClick={() => setZoomed(true)} aria-label={`Zoom satellite image for tile ${tileId}`}><img src={imageUrl} alt={`Satellite image for tile ${tileId}`} onError={() => setAvailable(false)} /></button>
    {zoomed && <AppDialog className="image-dialog" onClose={() => setZoomed(false)}><div className="dialog-heading"><strong>Tile {tileId}</strong><button className="dialog-close" type="button" onClick={() => setZoomed(false)} aria-label="Close enlarged image">Close</button></div><img className="enlarged-satellite-image" src={imageUrl} alt={`Enlarged satellite image for tile ${tileId}`} /></AppDialog>}
  </>
}
function ProvenanceView({ selectedSceneId, setSelectedSceneId }) {
  const [scenes, setScenes] = useState([])
  const [record, setRecord] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    let current = true
    fetch(`${API_BASE}/scenes`).then(async (response) => {
      const payload = await response.json()
      if (!response.ok) throw new Error(payload.detail || 'Could not load indexed scenes')
      return payload
    }).then((payload) => {
      if (!current) return
      const availableScenes = Array.isArray(payload) ? payload : []
      setScenes(availableScenes)
      setSelectedSceneId((selected) => selected || availableScenes[0]?.id || '')
    }).catch((requestError) => { if (current) setError(requestError.message) }).finally(() => { if (current) setLoading(false) })
    return () => { current = false }
  }, [setSelectedSceneId])

  useEffect(() => {
    if (!selectedSceneId) return undefined
    let current = true
    fetch(`${API_BASE}/provenance/${encodeURIComponent(selectedSceneId)}`).then(async (response) => {
      const payload = await response.json()
      if (!response.ok) throw new Error(payload.detail || 'No provenance record for this scene')
      return payload.provenance
    }).then((payload) => { if (current) { setRecord(payload); setError('') } }).catch((requestError) => { if (current) { setRecord(null); setError(requestError.message) } })
    return () => { current = false }
  }, [selectedSceneId])

  const selectedScene = scenes.find((scene) => scene.id === selectedSceneId)
  const isSyntheticScene = selectedScene?.source === 'synthetic-test-data' || selectedScene?.sensor === 'synthetic'
  const acquisitionDate = isSyntheticScene ? 'Unverified (synthetic fixture)' : selectedScene?.acquisition_datetime || 'Unverified'
  const inputFiles = parseRecordValue(record?.input_files, []).map((path) => String(path).split(/[\\/]/).pop())
  const checksums = parseRecordValue(record?.input_checksums, [])
  const steps = parseRecordValue(record?.steps, [])
  const parameters = parseRecordValue(record?.parameters, {})

  return <section className="feature-view"><FeatureIntro kicker="Audit trail" title="System provenance" text="Inspect source scenes, checksums, model details, and processing steps recorded during ingestion." /><div className="provenance-toolbar"><label htmlFor="provenance-scene">Indexed scene</label><select id="provenance-scene" value={selectedSceneId} onChange={(event) => setSelectedSceneId(event.target.value)} disabled={loading || scenes.length === 0}><option value="">{loading ? 'Loading scenes...' : 'Select a scene'}</option>{scenes.map((scene) => <option value={scene.id} key={scene.id}>{scene.source || 'Unknown source'} · {scene.sensor || 'Unknown sensor'} · {scene.id.slice(0, 8)}</option>)}</select></div>
    {error && <div className="evaluation-notice" role="status">{error}</div>}
    {record && <><div className="provenance-summary"><div><span>Source</span><strong>{selectedScene?.source || 'Unknown'}</strong></div><div><span>Sensor</span><strong>{selectedScene?.sensor || 'Unknown'}</strong></div><div><span>Acquisition</span><strong>{acquisitionDate}</strong></div><div><span>Recorded</span><strong>{record.timestamp || 'Unknown'}</strong></div></div><div className="provenance-grid"><section className="provenance-section"><h3>Model and runtime</h3><dl><dt>Model</dt><dd>{record.model_name} · {record.model_version}</dd><dt>Model source</dt><dd>{record.model_source || 'Not recorded'}</dd><dt>License</dt><dd>{record.model_license || 'Not recorded'}</dd><dt>Software</dt><dd>{record.software_version || 'Not recorded'}</dd><dt>Hardware</dt><dd>{record.hardware || 'Not recorded'}</dd></dl></section><section className="provenance-section"><h3>Input files</h3>{inputFiles.length ? inputFiles.map((file) => <div className="provenance-value" key={file}>{file}</div>) : <p>No input file recorded.</p>}<h3>Checksums</h3>{checksums.length ? checksums.map((checksum) => <code className="checksum-value" key={checksum}>{checksum}</code>) : <p>No checksum recorded.</p>}</section><section className="provenance-section"><h3>Processing steps</h3>{steps.length ? <ol>{steps.map((step, index) => <li key={`${step}-${index}`}>{step}</li>)}</ol> : <p>No processing steps recorded.</p>}</section><section className="provenance-section"><h3>Parameters</h3><pre>{JSON.stringify(parameters, null, 2)}</pre></section></div></>}
  </section>
}

function EvaluationView() {
  const [report, setReport] = useState(null)
  const [loading, setLoading] = useState(true)
  const [running, setRunning] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    let current = true
    fetch(`${API_BASE}/evaluation/results`).then(async (response) => {
      const payload = await response.json()
      if (!response.ok) throw new Error(payload.detail || 'Could not load evaluation results')
      return payload.results
    }).then((result) => { if (current && result?.status !== 'No evaluation run yet') setReport(result) }).catch((requestError) => { if (current) setError(requestError.message) }).finally(() => { if (current) setLoading(false) })
    return () => { current = false }
  }, [])

  const runEvaluation = async () => {
    setRunning(true)
    setError('')
    try {
      const response = await fetch(`${API_BASE}/evaluation/run`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ limit: 10 }) })
      const payload = await response.json()
      if (!response.ok) throw new Error(payload.detail || 'Evaluation run failed')
      setReport(payload.evaluation)
    } catch (requestError) { setError(requestError.message) } finally { setRunning(false) }
  }

  return <section className="feature-view"><FeatureIntro kicker="Model and data readiness" title="Evaluation lab" text="Run a coverage check for indexed imagery, georeferencing, and provenance. Quality scores require labeled evaluation examples." /><div className="evaluation-toolbar"><span>{report ? 'Latest coverage run' : loading ? 'Checking for previous runs...' : 'No evaluation run yet'}</span><button className="primary-button" type="button" onClick={runEvaluation} disabled={running}>{running ? 'Evaluating...' : 'Run evaluation'}</button></div>
    {error && <div className="evaluation-notice" role="alert">{error}</div>}
    {report && <><div className="coverage-grid"><CoverageCard label="Images available" data={report.coverage.images} /><CoverageCard label="Locations georeferenced" data={report.coverage.locations} /><CoverageCard label="Scenes with provenance" data={report.coverage.provenance} /></div><div className="evaluation-notice"><strong>Model quality: not scored.</strong> {report.message}</div><section className="evaluation-labels"><h3>Staged ground-truth labels</h3><span>Retrieval queries <b>{report.ground_truth.retrieval_queries}</b></span><span>Change labels <b>{report.ground_truth.change_labels}</b></span><span>Quality labels <b>{report.ground_truth.quality_labels}</b></span></section><div className="evaluation-facts"><span>{report.scene_count} scenes</span><span>{report.tile_count} tiles</span><span>{report.change_count} change detections</span></div></>}
    {!report && !loading && !error && <Empty text="Run evaluation to inspect data coverage and label readiness." />}
  </section>
}

function CoverageCard({ label, data }) {
  const percentage = data.total ? Math.round((data.available / data.total) * 100) : null
  return <article className="coverage-card"><span>{label}</span><strong>{percentage === null ? '—' : `${percentage}%`}</strong><small>{data.available} of {data.total} indexed records</small></article>
}

function parseRecordValue(value, fallback) {
  if (!value) return fallback
  try { return JSON.parse(value) } catch { return fallback }
}

function Empty({ text }) { return <div className="empty-state-card"><span>o</span><p>{text}</p></div> }
function ProfileView({ user, onLogout }) {
  const fields = [
    ['Name', user.full_name],
    ['Email', user.email],
    ['Organization', user.organization || 'Not provided'],
    ['Role', user.role],
    ['Account status', user.status],
    ['Last sign-in', user.last_login || 'No previous sign-in recorded'],
  ]

  return <section className="feature-view"><FeatureIntro kicker="Account" title="Workspace profile" text="Your authorized workspace identity and access status." /><div className="profile-panel"><dl>{fields.map(([label, value]) => <div key={label}><dt>{label}</dt><dd>{value}</dd></div>)}</dl><button className="review-btn reject" type="button" onClick={onLogout}>Sign out</button></div></section>
}

export default App



