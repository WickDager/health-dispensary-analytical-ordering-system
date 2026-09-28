import { useState, useEffect, useCallback } from 'react'
import { Target, Plus, RefreshCw } from 'lucide-react'
import api, { extractResults } from '../api/client'
import { formatCurrency, formatDate } from '../lib/utils'
import Card from '../components/ui/Card'
import Badge from '../components/ui/Badge'
import DataTable, { type Column } from '../components/ui/DataTable'
import Modal from '../components/ui/Modal'
import EmptyState from '../components/ui/EmptyState'
import LoadingSpinner from '../components/ui/LoadingSpinner'
import ErrorBoundary from '../components/ui/ErrorBoundary'

interface Lead {
  id: number
  first_name: string
  last_name: string
  source: string
  status: 'new' | 'contacted' | 'qualified' | 'converted' | 'disqualified'
  estimated_value: string
  owner_name: string
  created_at: string
}

const STATUS_FILTERS = ['all', 'new', 'contacted', 'qualified', 'converted', 'disqualified'] as const

const STATUS_VARIANT: Record<string, 'accent' | 'ok' | 'warn' | 'danger' | 'info'> = {
  new: 'accent',
  contacted: 'info',
  qualified: 'warn',
  converted: 'ok',
  disqualified: 'danger',
}

const emptyLead = () => ({
  first_name: '',
  last_name: '',
  source: 'website',
  status: 'new' as const,
  estimated_value: '',
  notes: '',
})

interface ConvertForm {
  account_name: string
  contact_first: string
  contact_last: string
}

export default function LeadsList() {
  const [leads, setLeads] = useState<Lead[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState('')
  const [statusFilter, setStatusFilter] = useState<string>('all')
  const [addOpen, setAddOpen] = useState(false)
  const [newLead, setNewLead] = useState(emptyLead())
  const [saving, setSaving] = useState(false)
  const [convertOpen, setConvertOpen] = useState<number | null>(null)
  const [convertForm, setConvertForm] = useState<ConvertForm>({ account_name: '', contact_first: '', contact_last: '' })
  const [converting, setConverting] = useState(false)

  const fetchLeads = useCallback(async () => {
    setIsLoading(true)
    setError('')
    try {
      const params = new URLSearchParams()
      if (statusFilter !== 'all') params.set('status', statusFilter)
      const qs = params.toString()
      const data = await api.get<Lead[]>(`/crm/leads/${qs ? `?${qs}` : ''}`)
      setLeads(extractResults(data))
    } catch {
      setError('Failed to load leads.')
      setLeads([])
    } finally {
      setIsLoading(false)
    }
  }, [statusFilter])

  useEffect(() => { fetchLeads() }, [fetchLeads])

  const handleAdd = async () => {
    if (!newLead.first_name.trim() || !newLead.last_name.trim()) return
    setSaving(true)
    try {
      await api.post('/crm/leads/', newLead)
      setAddOpen(false)
      setNewLead(emptyLead())
      fetchLeads()
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to add lead.')
    } finally { setSaving(false) }
  }

  const handleConvert = async () => {
    if (!convertOpen || !convertForm.account_name.trim()) return
    setConverting(true)
    try {
      await api.post(`/crm/leads/${convertOpen}/convert/`, convertForm)
      setConvertOpen(null)
      setConvertForm({ account_name: '', contact_first: '', contact_last: '' })
      fetchLeads()
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Conversion failed.')
    } finally { setConverting(false) }
  }

  const columns: Column<Lead>[] = [
    {
      key: 'name',
      header: 'Name',
      sortable: true,
      render: (l) => <span style={{ fontWeight: 500 }}>{l.first_name} {l.last_name}</span>,
    },
    { key: 'source', header: 'Source', sortable: true },
    {
      key: 'status',
      header: 'Status',
      sortable: true,
      render: (l) => <Badge variant={STATUS_VARIANT[l.status] || 'info'} dot>{l.status}</Badge>,
    },
    {
      key: 'estimated_value',
      header: 'Est Value',
      sortable: true,
      render: (l) => l.estimated_value ? formatCurrency(parseFloat(l.estimated_value)) : '—',
    },
    { key: 'owner_name', header: 'Owner' },
    {
      key: 'created_at',
      header: 'Created',
      sortable: true,
      render: (l) => formatDate(l.created_at),
    },
    {
      key: 'actions',
      header: 'Actions',
      render: (l) => (
        l.status !== 'converted' && l.status !== 'disqualified' ? (
          <button
            onClick={() => {
              setConvertForm({
                account_name: '',
                contact_first: l.first_name,
                contact_last: l.last_name,
              })
              setConvertOpen(l.id)
            }}
            style={actionBtnStyle}
          >
            <RefreshCw size={12} /> Convert
          </button>
        ) : null
      ),
    },
  ]

  return (
    <ErrorBoundary>
      <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '12px' }}>
          <div>
            <h1 style={{ fontSize: '1.5rem', fontWeight: 700, color: 'var(--text)' }}>Leads</h1>
            <p style={{ fontSize: '0.85rem', color: 'var(--text-muted)', marginTop: '2px' }}>
              {leads.length} lead{leads.length !== 1 ? 's' : ''}
            </p>
          </div>
          <button onClick={() => setAddOpen(true)} style={priBtnStyle}>
            <Plus size={16} /> Add Lead
          </button>
        </div>

        {/* Status filter */}
        <Card padding="12px 16px">
          <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap' }}>
            {STATUS_FILTERS.map((s) => (
              <button key={s} onClick={() => setStatusFilter(s)} style={{
                padding: '6px 14px',
                borderRadius: 'var(--radius-sm)',
                fontSize: '0.78rem',
                fontWeight: statusFilter === s ? 600 : 400,
                border: statusFilter === s ? '1px solid var(--accent)' : '1px solid var(--border)',
                backgroundColor: statusFilter === s ? 'color-mix(in srgb, var(--accent) 12%, transparent)' : 'var(--surface-2)',
                color: statusFilter === s ? 'var(--accent)' : 'var(--text-muted)',
                cursor: 'pointer',
                textTransform: 'capitalize',
              }}>
                {s}
              </button>
            ))}
          </div>
        </Card>

        {error && <div style={errorBannerStyle}>{error}</div>}

        {isLoading ? (
          <LoadingSpinner message="Loading leads..." />
        ) : leads.length === 0 ? (
          <EmptyState
            icon={<Target size={48} />}
            title="No leads found"
            description={statusFilter !== 'all' ? `No leads with status "${statusFilter}".` : 'Add your first lead.'}
            action={<button onClick={() => setAddOpen(true)} style={priBtnStyle}><Plus size={16} /> Add Lead</button>}
          />
        ) : (
          <DataTable columns={columns} data={leads} keyExtractor={(l) => l.id} pageSize={20} />
        )}

        {/* Add Lead Modal */}
        <Modal open={addOpen} onClose={() => setAddOpen(false)} title="Add Lead" maxWidth="500px">
          <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
            <Field label="First Name" value={newLead.first_name} onChange={(v) => setNewLead((p) => ({ ...p, first_name: v }))} />
            <Field label="Last Name" value={newLead.last_name} onChange={(v) => setNewLead((p) => ({ ...p, last_name: v }))} />
            <div>
              <label style={labelStyle}>Source</label>
              <select
                value={newLead.source}
                onChange={(e) => setNewLead((p) => ({ ...p, source: e.target.value }))}
                style={selectStyle}
              >
                <option value="website">Website</option>
                <option value="referral">Referral</option>
                <option value="event">Event</option>
                <option value="email">Email</option>
                <option value="phone">Phone</option>
                <option value="other">Other</option>
              </select>
            </div>
            <Field label="Estimated Value" value={newLead.estimated_value} onChange={(v) => setNewLead((p) => ({ ...p, estimated_value: v }))} type="number" />
            <div style={{ display: 'flex', gap: '10px', justifyContent: 'flex-end', marginTop: '8px' }}>
              <button onClick={() => setAddOpen(false)} style={secBtnStyle}>Cancel</button>
              <button onClick={handleAdd} disabled={saving || !newLead.first_name.trim()} style={priBtnStyle}>
                {saving ? 'Saving...' : 'Save'}
              </button>
            </div>
          </div>
        </Modal>

        {/* Convert Modal */}
        <Modal open={convertOpen !== null} onClose={() => setConvertOpen(null)} title="Convert Lead" maxWidth="500px">
          <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
            <p style={{ fontSize: '0.85rem', color: 'var(--text-muted)' }}>
              Convert this lead into an account and contact.
            </p>
            <Field label="Account Name" value={convertForm.account_name} onChange={(v) => setConvertForm((p) => ({ ...p, account_name: v }))} />
            <Field label="Contact First Name" value={convertForm.contact_first} onChange={(v) => setConvertForm((p) => ({ ...p, contact_first: v }))} />
            <Field label="Contact Last Name" value={convertForm.contact_last} onChange={(v) => setConvertForm((p) => ({ ...p, contact_last: v }))} />
            <div style={{ display: 'flex', gap: '10px', justifyContent: 'flex-end', marginTop: '8px' }}>
              <button onClick={() => setConvertOpen(null)} style={secBtnStyle}>Cancel</button>
              <button onClick={handleConvert} disabled={converting || !convertForm.account_name.trim()} style={priBtnStyle}>
                {converting ? 'Converting...' : 'Convert'}
              </button>
            </div>
          </div>
        </Modal>
      </div>
    </ErrorBoundary>
  )
}

function Field({ label, value, onChange, type = 'text' }: { label: string; value: string; onChange: (v: string) => void; type?: string }) {
  return (
    <div>
      <label style={labelStyle}>{label}</label>
      <input type={type} value={value} onChange={(e) => onChange(e.target.value)} style={inputStyle}
        onFocus={(e) => { e.currentTarget.style.borderColor = 'var(--accent)' }}
        onBlur={(e) => { e.currentTarget.style.borderColor = 'var(--border)' }}
      />
    </div>
  )
}

const labelStyle: React.CSSProperties = { display: 'block', fontSize: '0.8rem', fontWeight: 500, color: 'var(--text)', marginBottom: '4px' }

const inputStyle: React.CSSProperties = {
  width: '100%', padding: '8px 10px', backgroundColor: 'var(--surface-2)',
  border: '1px solid var(--border)', borderRadius: 'var(--radius-md)', color: 'var(--text)',
  fontSize: '0.85rem', outline: 'none', boxSizing: 'border-box',
}

const selectStyle: React.CSSProperties = {
  ...inputStyle,
}

const priBtnStyle: React.CSSProperties = {
  display: 'inline-flex', alignItems: 'center', gap: '6px',
  padding: '8px 16px', backgroundColor: 'var(--accent)', color: '#fff',
  border: 'none', borderRadius: 'var(--radius-md)', fontSize: '0.85rem', fontWeight: 600, cursor: 'pointer',
}

const secBtnStyle: React.CSSProperties = {
  padding: '8px 16px', backgroundColor: 'transparent', color: 'var(--text-muted)',
  border: '1px solid var(--border)', borderRadius: 'var(--radius-md)', fontSize: '0.85rem', cursor: 'pointer',
}

const actionBtnStyle: React.CSSProperties = {
  display: 'inline-flex', alignItems: 'center', gap: '4px',
  padding: '4px 10px', backgroundColor: 'color-mix(in srgb, var(--accent) 12%, transparent)',
  color: 'var(--accent)', border: '1px solid var(--border)', borderRadius: 'var(--radius-sm)',
  fontSize: '0.75rem', fontWeight: 500, cursor: 'pointer',
}

const errorBannerStyle: React.CSSProperties = {
  backgroundColor: 'color-mix(in srgb, var(--danger) 12%, transparent)',
  color: 'var(--danger)', padding: '10px 16px', borderRadius: 'var(--radius-md)',
  fontSize: '0.85rem', border: '1px solid color-mix(in srgb, var(--danger) 25%, transparent)',
}
