import { useState, useEffect, useCallback } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { ArrowLeft, Building2, Users, DollarSign, Clock, Plus } from 'lucide-react'
import api from '../api/client'
import { formatDate, formatCurrency, formatDateTime } from '../lib/utils'
import Card from '../components/ui/Card'
import Badge from '../components/ui/Badge'
import KpiCard from '../components/ui/KpiCard'
import DataTable, { type Column } from '../components/ui/DataTable'
import LoadingSpinner from '../components/ui/LoadingSpinner'
import ErrorBoundary from '../components/ui/ErrorBoundary'

interface AccountData {
  id: number
  name: string
  account_type: string
  website: string
  phone: string
  address: string
  notes: string
  created_at: string
  contact_count: number
  open_opportunities: number
  total_pipeline_value: string
}

interface AccountContact {
  id: number
  first_name: string
  last_name: string
  contact_type: string
  email: string
}

interface Opportunity {
  id: number
  name: string
  stage: string
  amount: string
  probability: number
  close_date: string
  owner_name: string
}

interface RecentActivity {
  id: number
  activity_type: string
  subject: string
  created_by_name: string
  created_at: string
}

export default function AccountDetail() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()

  const [account, setAccount] = useState<AccountData | null>(null)
  const [contacts, setContacts] = useState<AccountContact[]>([])
  const [opportunities, setOpportunities] = useState<Opportunity[]>([])
  const [activities, setActivities] = useState<RecentActivity[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState('')

  const fetchData = useCallback(async () => {
    setIsLoading(true)
    setError('')
    try {
      const [acc, con, opp, act] = await Promise.all([
        api.get<AccountData>(`/crm/accounts/${id}/`),
        api.get<AccountContact[]>(`/crm/accounts/${id}/contacts/`).catch(() => []),
        api.get<Opportunity[]>(`/crm/accounts/${id}/opportunities/`).catch(() => []),
        api.get<RecentActivity[]>(`/crm/accounts/${id}/activities/`).catch(() => []),
      ])
      setAccount(acc)
      setContacts(Array.isArray(con) ? con : [])
      setOpportunities(Array.isArray(opp) ? opp : [])
      setActivities(Array.isArray(act) ? act : [])
    } catch {
      setError('Failed to load account.')
    } finally {
      setIsLoading(false)
    }
  }, [id])

  useEffect(() => { if (id) fetchData() }, [fetchData])

  const contactColumns: Column<AccountContact>[] = [
    {
      key: 'name',
      header: 'Name',
      render: (c) => (
        <span style={{ color: 'var(--accent)', cursor: 'pointer', fontWeight: 500 }}
              onClick={() => navigate(`/crm/contacts/${c.id}`)}>
          {c.first_name} {c.last_name}
        </span>
      ),
    },
    {
      key: 'contact_type',
      header: 'Type',
      render: (c) => <Badge variant="info">{c.contact_type}</Badge>,
    },
    { key: 'email', header: 'Email' },
  ]

  const oppColumns: Column<Opportunity>[] = [
    {
      key: 'name',
      header: 'Name',
      render: (o) => (
        <span style={{ fontWeight: 500, color: 'var(--accent)', cursor: 'pointer' }}
              onClick={() => navigate(`/crm/pipeline?opp=${o.id}`)}>
          {o.name}
        </span>
      ),
    },
    { key: 'stage', header: 'Stage', render: (o) => <Badge variant="info">{o.stage}</Badge> },
    { key: 'amount', header: 'Amount', render: (o) => formatCurrency(parseFloat(o.amount || '0')) },
    { key: 'probability', header: 'Prob', render: (o) => `${o.probability}%` },
    { key: 'close_date', header: 'Close Date', render: (o) => formatDate(o.close_date) },
    { key: 'owner_name', header: 'Owner' },
  ]

  if (isLoading) return <LoadingSpinner message="Loading account..." />

  if (!account) {
    return (
      <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
        <button onClick={() => navigate('/crm/accounts')} style={backBtnStyle}>
          <ArrowLeft size={16} /> Back to Accounts
        </button>
        <div style={{ textAlign: 'center', padding: '40px', color: 'var(--danger)' }}>
          {error || 'Account not found.'}
        </div>
      </div>
    )
  }

  return (
    <ErrorBoundary>
      <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '12px' }}>
          <div>
            <button onClick={() => navigate('/crm/accounts')} style={backBtnStyle}>
              <ArrowLeft size={16} /> Back to Accounts
            </button>
            <h1 style={{ fontSize: '1.5rem', fontWeight: 700, color: 'var(--text)', marginTop: '4px' }}>
              {account.name}
            </h1>
            <div style={{ display: 'flex', gap: '8px', marginTop: '4px' }}>
              <Badge variant="info">{account.account_type}</Badge>
            </div>
          </div>
        </div>

        {/* KPI cards */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(180px, 1fr))', gap: '12px' }}>
          <KpiCard icon={<Users size={20} />} label="Contacts" value={account.contact_count} />
          <KpiCard icon={<DollarSign size={20} />} label="Open Opportunities" value={account.open_opportunities} />
          <KpiCard icon={<DollarSign size={20} />} label="Pipeline Value" value={formatCurrency(parseFloat(account.total_pipeline_value || '0'))} />
          <KpiCard icon={<Clock size={20} />} label="Created" value={formatDate(account.created_at)} />
        </div>

        {/* Account Info */}
        <Card title="Account Information">
          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
            <DetailRow label="Name" value={account.name} />
            <DetailRow label="Type" value={account.account_type} />
            <DetailRow label="Website" value={account.website || '—'} />
            <DetailRow label="Phone" value={account.phone || '—'} />
            <DetailRow label="Address" value={account.address || '—'} />
            {account.notes && <DetailRow label="Notes" value={account.notes} />}
          </div>
        </Card>

        {/* Contacts */}
        <Card
          title={`Contacts (${contacts.length})`}
          action={
            <button onClick={() => navigate('/crm/contacts/new')}
                    style={{ ...priBtnStyle, fontSize: '0.75rem', padding: '4px 10px' }}>
              <Plus size={12} /> Add
            </button>
          }
        >
          {contacts.length === 0 ? (
            <div style={{ textAlign: 'center', padding: '16px', color: 'var(--text-muted)', fontSize: '0.85rem' }}>
              No contacts linked to this account.
            </div>
          ) : (
            <DataTable columns={contactColumns} data={contacts} keyExtractor={(c) => c.id} pageSize={10} />
          )}
        </Card>

        {/* Opportunities */}
        <Card title={`Opportunities (${opportunities.length})`}>
          {opportunities.length === 0 ? (
            <div style={{ textAlign: 'center', padding: '16px', color: 'var(--text-muted)', fontSize: '0.85rem' }}>
              No opportunities linked.
            </div>
          ) : (
            <DataTable columns={oppColumns} data={opportunities} keyExtractor={(o) => o.id} pageSize={10} />
          )}
        </Card>

        {/* Recent Activities */}
        <Card title="Recent Activities">
          {activities.length === 0 ? (
            <div style={{ textAlign: 'center', padding: '16px', color: 'var(--text-muted)', fontSize: '0.85rem' }}>
              No recent activities.
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
              {activities.slice(0, 10).map((a) => (
                <div key={a.id} style={{
                  padding: '10px',
                  backgroundColor: 'var(--surface-2)',
                  borderRadius: 'var(--radius-md)',
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                  flexWrap: 'wrap',
                  gap: '8px',
                }}>
                  <div>
                    <div style={{ fontWeight: 500, fontSize: '0.85rem', color: 'var(--text)' }}>{a.subject}</div>
                    <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                      {a.activity_type} by {a.created_by_name}
                    </div>
                  </div>
                  <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                    {formatDateTime(a.created_at)}
                  </span>
                </div>
              ))}
            </div>
          )}
        </Card>
      </div>
    </ErrorBoundary>
  )
}

function DetailRow({ label, value }: { label: string; value: string }) {
  return (
    <div style={{ display: 'flex', gap: '12px', padding: '4px 0' }}>
      <span style={{ fontSize: '0.82rem', color: 'var(--text-muted)', minWidth: '100px' }}>{label}</span>
      <span style={{ fontSize: '0.85rem', color: 'var(--text)', fontWeight: 500 }}>{value}</span>
    </div>
  )
}

const backBtnStyle: React.CSSProperties = {
  display: 'inline-flex', alignItems: 'center', gap: '6px',
  background: 'none', border: 'none', color: 'var(--accent)',
  cursor: 'pointer', fontSize: '0.85rem', fontWeight: 500, padding: 0, width: 'fit-content',
}

const priBtnStyle: React.CSSProperties = {
  display: 'inline-flex', alignItems: 'center', gap: '6px',
  padding: '8px 16px', backgroundColor: 'var(--accent)', color: '#fff',
  border: 'none', borderRadius: 'var(--radius-md)', fontSize: '0.85rem', fontWeight: 600, cursor: 'pointer',
}
