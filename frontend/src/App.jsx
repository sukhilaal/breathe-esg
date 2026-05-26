import { useEffect, useMemo, useState } from 'react'
import './App.css'

const API_BASE = import.meta.env.VITE_API_BASE ?? 'http://localhost:8000/api'

const INGEST_ENDPOINTS = {
  sap: 'ingest/sap/',
  utility: 'ingest/utility/',
  travel: 'ingest/travel/',
}

async function api(path, options = {}) {
  const response = await fetch(`${API_BASE}/${path}`, options)
  if (!response.ok) {
    const message = await response.text()
    throw new Error(message || `HTTP ${response.status}`)
  }
  return response.json()
}

function scopeLabel(scope) {
  return scope?.replace('_', ' ').toUpperCase() ?? '-'
}

function formatNumber(value, digits = 2) {
  if (value === null || value === undefined || value === '') return '-'
  return Number(value).toLocaleString(undefined, {
    maximumFractionDigits: digits,
    minimumFractionDigits: 0,
  })
}

function App() {
  const [tenantSlug, setTenantSlug] = useState('acme-enterprise')
  const [summary, setSummary] = useState(null)
  const [activities, setActivities] = useState([])
  const [selected, setSelected] = useState(null)
  const [audit, setAudit] = useState({ revisions: [], actions: [] })
  const [files, setFiles] = useState({ sap: null, utility: null, travel: null })
  const [filters, setFilters] = useState({
    source_system: '',
    state: '',
    suspicious: '',
  })
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  const summaryCards = useMemo(() => {
    if (!summary) return []
    return [
      { label: 'Pending', value: summary.state_counts?.pending ?? 0 },
      { label: 'Approved', value: summary.state_counts?.approved ?? 0 },
      { label: 'Rejected', value: summary.state_counts?.rejected ?? 0 },
      { label: 'Locked', value: summary.state_counts?.locked ?? 0 },
      { label: 'Suspicious', value: summary.suspicious_count ?? 0 },
      {
        label: 'Total CO2e (kg)',
        value: formatNumber(summary.emissions_total_kgco2e, 0),
      },
    ]
  }, [summary])

  async function loadSummary() {
    const data = await api(`dashboard/summary/?tenant_slug=${tenantSlug}`)
    setSummary(data)
  }

  async function loadActivities() {
    const params = new URLSearchParams({ tenant_slug: tenantSlug, limit: '300' })
    if (filters.source_system) params.append('source_system', filters.source_system)
    if (filters.state) params.append('state', filters.state)
    if (filters.suspicious) params.append('suspicious', filters.suspicious)
    const data = await api(`activities/?${params.toString()}`)
    setActivities(data.results ?? [])
  }

  async function refreshAll() {
    setBusy(true)
    setError('')
    try {
      await Promise.all([loadSummary(), loadActivities()])
    } catch (err) {
      setError(String(err.message ?? err))
    } finally {
      setBusy(false)
    }
  }

  useEffect(() => {
    let cancelled = false
    // eslint-disable-next-line react-hooks/set-state-in-effect
    Promise.all([loadSummary(), loadActivities()]).catch((err) => {
      if (!cancelled) {
        setError(String(err.message ?? err))
      }
    })
    return () => {
      cancelled = true
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tenantSlug, filters.source_system, filters.state, filters.suspicious])

  async function upload(sourceKey) {
    if (!files[sourceKey]) return
    setBusy(true)
    setError('')
    try {
      const form = new FormData()
      form.append('tenant_slug', tenantSlug)
      form.append('file', files[sourceKey])
      await api(INGEST_ENDPOINTS[sourceKey], { method: 'POST', body: form })
      setFiles((prev) => ({ ...prev, [sourceKey]: null }))
      await refreshAll()
    } catch (err) {
      setError(String(err.message ?? err))
    } finally {
      setBusy(false)
    }
  }

  async function runAction(id, action) {
    setBusy(true)
    setError('')
    try {
      await api(`activities/${id}/action/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action, actor: 'analyst@breatheesg.local' }),
      })
      await refreshAll()
      if (selected?.id === id) {
        const [updated, auditTrail] = await Promise.all([
          api(`activities/${id}/`),
          api(`activities/${id}/audit/`),
        ])
        setSelected(updated)
        setAudit(auditTrail)
      }
    } catch (err) {
      setError(String(err.message ?? err))
    } finally {
      setBusy(false)
    }
  }

  async function selectActivity(activity) {
    setSelected(activity)
    try {
      const auditTrail = await api(`activities/${activity.id}/audit/`)
      setAudit(auditTrail)
    } catch (err) {
      setAudit({ revisions: [], actions: [] })
      setError(String(err.message ?? err))
    }
  }

  return (
    <div className="page">
      <header className="hero">
        <div>
          <p className="eyebrow">Breathe ESG Prototype</p>
          <h1>Ingestion and Analyst Review Console</h1>
          <p className="subtitle">
            Multi-source intake for SAP, utility bills, and travel records with row-level review before audit lock.
          </p>
        </div>
        <div className="tenant-box">
          <label htmlFor="tenant">Tenant slug</label>
          <input
            id="tenant"
            value={tenantSlug}
            onChange={(event) => setTenantSlug(event.target.value)}
            placeholder="acme-enterprise"
          />
          <button type="button" onClick={refreshAll} disabled={busy}>
            Refresh
          </button>
        </div>
      </header>

      {error ? <div className="error-banner">{error}</div> : null}

      <section className="ingestion-grid">
        {['sap', 'utility', 'travel'].map((sourceKey) => (
          <article key={sourceKey} className="card">
            <h2>{sourceKey.toUpperCase()} Ingestion</h2>
            <p className="hint">
              Upload {sourceKey === 'travel' ? 'JSON' : 'CSV'} extracted from the source system.
            </p>
            <input
              type="file"
              accept={sourceKey === 'travel' ? '.json' : '.csv'}
              onChange={(event) =>
                setFiles((prev) => ({ ...prev, [sourceKey]: event.target.files?.[0] ?? null }))
              }
            />
            <button type="button" onClick={() => upload(sourceKey)} disabled={!files[sourceKey] || busy}>
              Upload
            </button>
          </article>
        ))}
      </section>

      <section className="metrics-grid">
        {summaryCards.map((card) => (
          <article key={card.label} className="metric">
            <p>{card.label}</p>
            <strong>{card.value}</strong>
          </article>
        ))}
      </section>

      <section className="filters card">
        <h2>Filters</h2>
        <div className="filter-row">
          <select
            value={filters.source_system}
            onChange={(event) =>
              setFilters((prev) => ({ ...prev, source_system: event.target.value }))
            }
          >
            <option value="">All sources</option>
            <option value="sap">SAP</option>
            <option value="utility">Utility</option>
            <option value="travel">Travel</option>
          </select>
          <select value={filters.state} onChange={(event) => setFilters((prev) => ({ ...prev, state: event.target.value }))}>
            <option value="">All states</option>
            <option value="pending">Pending</option>
            <option value="approved">Approved</option>
            <option value="rejected">Rejected</option>
            <option value="locked">Locked</option>
          </select>
          <select
            value={filters.suspicious}
            onChange={(event) => setFilters((prev) => ({ ...prev, suspicious: event.target.value }))}
          >
            <option value="">All quality</option>
            <option value="true">Suspicious only</option>
            <option value="false">Non-suspicious only</option>
          </select>
        </div>
      </section>

      <section className="workspace-grid">
        <article className="card table-card">
          <h2>Activity Records ({activities.length})</h2>
          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  <th>ID</th>
                  <th>Source</th>
                  <th>Scope</th>
                  <th>Category</th>
                  <th>Period</th>
                  <th>Qty</th>
                  <th>CO2e (kg)</th>
                  <th>State</th>
                  <th>Quality</th>
                  <th>Action</th>
                </tr>
              </thead>
              <tbody>
                {activities.map((row) => (
                  <tr key={row.id} onClick={() => selectActivity(row)} className={selected?.id === row.id ? 'selected' : ''}>
                    <td>{row.id}</td>
                    <td>{row.source_system}</td>
                    <td>{scopeLabel(row.scope)}</td>
                    <td>{row.category}</td>
                    <td>{row.activity_start} to {row.activity_end}</td>
                    <td>{formatNumber(row.quantity_normalized)} {row.unit_normalized}</td>
                    <td>{formatNumber(row.emissions_kgco2e)}</td>
                    <td>{row.state}</td>
                    <td>{row.suspicious ? 'Needs review' : 'Clean'}</td>
                    <td>
                      <div className="action-row">
                        <button type="button" onClick={(event) => { event.stopPropagation(); runAction(row.id, 'approve') }}>
                          Approve
                        </button>
                        <button type="button" onClick={(event) => { event.stopPropagation(); runAction(row.id, 'reject') }}>
                          Reject
                        </button>
                        <button type="button" onClick={(event) => { event.stopPropagation(); runAction(row.id, 'lock') }}>
                          Lock
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </article>

        <aside className="card details">
          <h2>Selected Record</h2>
          {!selected ? <p className="hint">Select a row to inspect payload and audit trail.</p> : null}
          {selected ? (
            <>
              <dl>
                <dt>Record ID</dt>
                <dd>{selected.source_record_id}</dd>
                <dt>Scope / Category</dt>
                <dd>{scopeLabel(selected.scope)} / {selected.category}</dd>
                <dt>Status</dt>
                <dd>{selected.state}</dd>
                <dt>Suspicion reasons</dt>
                <dd>{selected.suspicion_reasons?.length ? selected.suspicion_reasons.join('; ') : 'None'}</dd>
              </dl>
              <h3>Raw source payload</h3>
              <pre>{JSON.stringify(selected.source_payload, null, 2)}</pre>
              <h3>Audit actions</h3>
              <ul className="audit-list">
                {(audit.actions ?? []).map((action) => (
                  <li key={action.id}>
                    <strong>{action.action}</strong> by {action.actor} on {action.created_at}
                  </li>
                ))}
              </ul>
            </>
          ) : null}
        </aside>
      </section>
    </div>
  )
}

export default App
