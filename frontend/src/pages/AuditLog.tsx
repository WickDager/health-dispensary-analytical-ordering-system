import { useState, useEffect, useCallback } from 'react'
import { FileText, Search } from 'lucide-react'
import api, { extractResults } from '../api/client'
import { formatDateTime } from '../lib/utils'
import Card from '../components/ui/Card'
import Badge from '../components/ui/Badge'
import DataTable, { type Column } from '../components/ui/DataTable'
import EmptyState from '../components/ui/EmptyState'
import LoadingSpinner from '../components/ui/LoadingSpinner'
import ErrorBoundary from '../components/ui/ErrorBoundary'

interface AuditEntry {
  id: number
  timestamp: string
  user_name: string
  action: string
  category: string
  details: Record<string, unknown>
}

export default function AuditLog() {
  const [entries, setEntries] = useState<AuditEntry[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState('')
  const [search, setSearch] = useState('')

  const fetchEntries = useCallback(async () => {
    setIsLoading(true)
    setError('')
    try {
      const params = new URLSearchParams()
      if (search.trim()) params.set('search', search.trim())
      const qs = params.toString()
      const data = await api.get<AuditEntry[]>(`/audit/${qs ? `?${qs}` : ''}`)
      setEntries(extractResults(data))
    } catch {
      setError('Failed to load audit log.')
      setEntries([])
    } finally { setIsLoading(false) }
  }, [search])

  useEffect(() => { fetchEntries() }, [fetchEntries])

  const columns: Column<AuditEntry>[] = [
    {
      key: 'timestamp',
      header: 'Timestamp',
      sortable: true,
      render: (e) => formatDateTime(e.timestamp),
    },
    { key: 'user_name', header: 'User', sortable: true },
    {
      key: 'action',
      header: 'Action',
      sortable: true,
      render: (e) => <Badge variant="info">{e.action}</Badge>,
    },
    {
      key: 'category',
      header: 'Category',
      sortable: true,
    },
    {
      key: 'details',
      header: 'Details',
      render: (e) => {
        const json = JSON.stringify(e.details)
        const truncated = json.length > 80 ? json.slice(0, 80) + '...' : json
        return (
          <code style={{
            fontSize: '0.72rem',
            backgroundColor: 'var(--surface-2)',
            padding: '2px 6px',
            borderRadius: 'var(--radius-sm)',
            fontFamily: 'monospace',
            maxWidth: '300px',
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            whiteSpace: 'nowrap',
            display: 'inline-block',
          }}>
            {truncated}
          </code>
        )
      },
    },
  ]

  return (
    <ErrorBoundary>
      <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
        <div>
          <h1 style={{ fontSize: '1.5rem', fontWeight: 700, color: 'var(--text)' }}>Audit Log</h1>
          <p style={{ fontSize: '0.85rem', color: 'var(--text-muted)', marginTop: '2px' }}>
            {entries.length} audit entr{entries.length !== 1 ? 'ies' : 'y'}
          </p>
        </div>

        <Card padding="16px 20px">
          <div style={{ position: 'relative', maxWidth: '400px' }}>
            <Search size={16} style={{ position: 'absolute', left: '10px', top: '50%', transform: 'translateY(-50%)', color: 'var(--text-muted)' }} />
            <input
              type="text"
              placeholder="Search by user, action, or category..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              style={{
                width: '100%', padding: '8px 12px 8px 34px',
                backgroundColor: 'var(--surface-2)',
                border: '1px solid var(--border)',
                borderRadius: 'var(--radius-md)',
                color: 'var(--text)', fontSize: '0.85rem',
                outline: 'none', boxSizing: 'border-box',
              }}
              onFocus={(e) => { e.currentTarget.style.borderColor = 'var(--accent)' }}
              onBlur={(e) => { e.currentTarget.style.borderColor = 'var(--border)' }}
            />
          </div>
        </Card>

        {error && <div style={errorBannerStyle}>{error}</div>}

        {isLoading ? (
          <LoadingSpinner message="Loading audit log..." />
        ) : entries.length === 0 ? (
          <EmptyState
            icon={<FileText size={48} />}
            title="No audit entries"
            description={search ? 'Try adjusting your search.' : 'No audit log entries recorded yet.'}
          />
        ) : (
          <DataTable columns={columns} data={entries} keyExtractor={(e) => e.id} pageSize={25} />
        )}
      </div>
    </ErrorBoundary>
  )
}

const errorBannerStyle: React.CSSProperties = {
  backgroundColor: 'color-mix(in srgb, var(--danger) 12%, transparent)',
  color: 'var(--danger)', padding: '10px 16px', borderRadius: 'var(--radius-md)',
  fontSize: '0.85rem', border: '1px solid color-mix(in srgb, var(--danger) 25%, transparent)',
}
