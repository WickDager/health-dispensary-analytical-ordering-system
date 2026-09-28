import { useState, useEffect, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { Building2, Plus } from 'lucide-react'
import api, { extractResults } from '../api/client'
import Badge from '../components/ui/Badge'
import DataTable, { type Column } from '../components/ui/DataTable'
import EmptyState from '../components/ui/EmptyState'
import LoadingSpinner from '../components/ui/LoadingSpinner'
import ErrorBoundary from '../components/ui/ErrorBoundary'

interface Account {
  id: number
  name: string
  account_type: string
  contact_count: number
  open_opportunities: number
  created_at: string
}

export default function AccountsList() {
  const navigate = useNavigate()
  const [accounts, setAccounts] = useState<Account[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState('')

  const fetchAccounts = useCallback(async () => {
    setIsLoading(true)
    setError('')
    try {
      const data = await api.get<Account[]>('/crm/accounts/')
      setAccounts(extractResults(data))
    } catch {
      setError('Failed to load accounts.')
      setAccounts([])
    } finally {
      setIsLoading(false)
    }
  }, [])

  useEffect(() => { fetchAccounts() }, [fetchAccounts])

  const columns: Column<Account>[] = [
    {
      key: 'name',
      header: 'Name',
      sortable: true,
      render: (a) => (
        <span style={{ fontWeight: 500, color: 'var(--accent)', cursor: 'pointer' }}
              onClick={() => navigate(`/crm/accounts/${a.id}`)}>
          {a.name}
        </span>
      ),
    },
    {
      key: 'account_type',
      header: 'Type',
      sortable: true,
      render: (a) => <Badge variant="info">{a.account_type}</Badge>,
    },
    { key: 'contact_count', header: 'Contacts', sortable: true },
    {
      key: 'open_opportunities',
      header: 'Open Opportunities',
      sortable: true,
      render: (a) => (
        <span style={{ fontWeight: 600, color: a.open_opportunities > 0 ? 'var(--accent)' : 'var(--text)' }}>
          {a.open_opportunities}
        </span>
      ),
    },
  ]

  return (
    <ErrorBoundary>
      <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '12px' }}>
          <div>
            <h1 style={{ fontSize: '1.5rem', fontWeight: 700, color: 'var(--text)' }}>Accounts</h1>
            <p style={{ fontSize: '0.85rem', color: 'var(--text-muted)', marginTop: '2px' }}>
              {accounts.length} account{accounts.length !== 1 ? 's' : ''}
            </p>
          </div>
          <button onClick={() => navigate('/crm/accounts/new')} style={priBtnStyle}>
            <Plus size={16} /> Add Account
          </button>
        </div>

        {error && <div style={errorBannerStyle}>{error}</div>}

        {isLoading ? (
          <LoadingSpinner message="Loading accounts..." />
        ) : accounts.length === 0 ? (
          <EmptyState
            icon={<Building2 size={48} />}
            title="No accounts"
            description="Add your first account to get started."
            action={
              <button onClick={() => navigate('/crm/accounts/new')} style={priBtnStyle}>
                <Plus size={16} /> Add Account
              </button>
            }
          />
        ) : (
          <DataTable columns={columns} data={accounts} keyExtractor={(a) => a.id} pageSize={20} />
        )}
      </div>
    </ErrorBoundary>
  )
}

const priBtnStyle: React.CSSProperties = {
  display: 'inline-flex', alignItems: 'center', gap: '6px',
  padding: '8px 16px', backgroundColor: 'var(--accent)', color: '#fff',
  border: 'none', borderRadius: 'var(--radius-md)', fontSize: '0.85rem', fontWeight: 600, cursor: 'pointer',
}

const errorBannerStyle: React.CSSProperties = {
  backgroundColor: 'color-mix(in srgb, var(--danger) 12%, transparent)',
  color: 'var(--danger)', padding: '10px 16px', borderRadius: 'var(--radius-md)',
  fontSize: '0.85rem', border: '1px solid color-mix(in srgb, var(--danger) 25%, transparent)',
}
