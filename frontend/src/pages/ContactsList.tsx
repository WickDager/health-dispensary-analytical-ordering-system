import { useState, useEffect, useCallback } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { Users, Search, Plus, X } from 'lucide-react'
import api, { extractResults, extractCount, type PaginatedResponse } from '../api/client'
import { formatDate } from '../lib/utils'
import Card from '../components/ui/Card'
import Badge from '../components/ui/Badge'
import DataTable, { type Column } from '../components/ui/DataTable'
import EmptyState from '../components/ui/EmptyState'
import LoadingSpinner from '../components/ui/LoadingSpinner'
import ErrorBoundary from '../components/ui/ErrorBoundary'

interface ContactTag {
  id: string
  name: string
  color: string
}

interface Contact {
  id: string
  first_name: string
  last_name: string
  contact_type: 'PATIENT' | 'PRESCRIBER' | 'BUYER'
  email: string
  phone: string
  account_name: string | null
  tags: ContactTag[]
  mrn: string
  consent_marketing: boolean
  created_at: string
}

const TYPE_BADGE: Record<string, 'accent' | 'info' | 'ok'> = {
  PATIENT: 'accent',
  PRESCRIBER: 'info',
  BUYER: 'ok',
}

const TYPE_FILTERS = ['all', 'PATIENT', 'PRESCRIBER', 'BUYER'] as const

const CONTACT_TYPE_OPTIONS = ['PATIENT', 'PRESCRIBER', 'BUYER']

export default function ContactsList() {
  const navigate = useNavigate()
  const [searchParams, setSearchParams] = useSearchParams()
  const activeType = searchParams.get('type') || 'all'

  const [contacts, setContacts] = useState<Contact[]>([])
  const [totalCount, setTotalCount] = useState(0)
  const [search, setSearch] = useState('')
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState('')
  const [showAddModal, setShowAddModal] = useState(false)
  const [saving, setSaving] = useState(false)
  const [saveError, setSaveError] = useState('')

  // Add form state
  const [form, setForm] = useState({
    contact_type: 'PATIENT',
    first_name: '',
    last_name: '',
    email: '',
    phone: '',
    mrn: '',
    consent_marketing: false,
  })

  const fetchContacts = useCallback(async () => {
    setIsLoading(true)
    setError('')
    try {
      const params = new URLSearchParams()
      if (activeType !== 'all') params.set('contact_type', activeType)
      if (search.trim()) params.set('search', search.trim())
      const qs = params.toString()
      const data = await api.get<PaginatedResponse<Contact>>(`/crm/contacts/${qs ? `?${qs}` : ''}`)
      // Handles both paginated and array responses
      setContacts(extractResults(data))
      setTotalCount(extractCount(data))
    } catch {
      setError('Failed to load contacts.')
      setContacts([])
    } finally {
      setIsLoading(false)
    }
  }, [activeType, search])

  useEffect(() => { fetchContacts() }, [fetchContacts])

  const handleFilter = (t: string) => {
    const next = new URLSearchParams(searchParams)
    if (t === 'all') next.delete('type')
    else next.set('type', t)
    setSearchParams(next)
  }

  const handleAdd = async (e: React.FormEvent) => {
    e.preventDefault()
    setSaveError('')
    if (!form.first_name.trim() || !form.last_name.trim()) {
      setSaveError('First and last name are required.')
      return
    }
    setSaving(true)
    try {
      await api.post('/crm/contacts/', {
        contact_type: form.contact_type,
        first_name: form.first_name.trim(),
        last_name: form.last_name.trim(),
        email: form.email.trim() || undefined,
        phone: form.phone.trim() || undefined,
        mrn: form.mrn.trim() || undefined,
        consent_marketing: form.consent_marketing,
      })
      setShowAddModal(false)
      setForm({ contact_type: 'PATIENT', first_name: '', last_name: '', email: '', phone: '', mrn: '', consent_marketing: false })
      fetchContacts()
    } catch (err: any) {
      setSaveError(err?.message || 'Failed to create contact.')
    } finally {
      setSaving(false)
    }
  }

  const columns: Column<Contact>[] = [
    {
      key: 'name',
      header: 'Name',
      sortable: true,
      render: (c) => (
        <span
          style={{ fontWeight: 500, color: 'var(--accent)', cursor: 'pointer' }}
          onClick={() => navigate(`/crm/contacts/${c.id}`)}
        >
          {c.first_name} {c.last_name}
        </span>
      ),
    },
    {
      key: 'contact_type',
      header: 'Type',
      sortable: true,
      render: (c) => (
        <Badge variant={TYPE_BADGE[c.contact_type] || 'info'}>
          {c.contact_type.charAt(0) + c.contact_type.slice(1).toLowerCase()}
        </Badge>
      ),
    },
    { key: 'email', header: 'Email', sortable: true, render: (c) => c.email || '—' },
    { key: 'phone', header: 'Phone', render: (c) => c.phone || '—' },
    { key: 'account_name', header: 'Account', sortable: true, render: (c) => c.account_name || '—' },
    {
      key: 'tags',
      header: 'Tags',
      render: (c) => (
        <div style={{ display: 'flex', gap: '4px', flexWrap: 'wrap', maxWidth: '200px' }}>
          {c.tags?.length > 0
            ? c.tags.map((t) => <Badge key={t.id} variant="info" size="sm">{t.name}</Badge>)
            : '—'}
        </div>
      ),
    },
  ]

  return (
    <ErrorBoundary>
      <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '12px' }}>
          <div>
            <h1 style={{ fontSize: '1.5rem', fontWeight: 700, color: 'var(--text)' }}>Contacts</h1>
            <p style={{ fontSize: '0.85rem', color: 'var(--text-muted)', marginTop: '2px' }}>
              {totalCount} contact{totalCount !== 1 ? 's' : ''}
            </p>
          </div>
          <button onClick={() => setShowAddModal(true)} style={priBtnStyle}>
            <Plus size={16} /> Add Contact
          </button>
        </div>

        <Card padding="16px 20px">
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '12px', alignItems: 'center' }}>
            <div style={{ position: 'relative', flex: '1 1 250px' }}>
              <Search size={16} style={{ position: 'absolute', left: '10px', top: '50%', transform: 'translateY(-50%)', color: 'var(--text-muted)' }} />
              <input
                type="text"
                placeholder="Search by name, email, or tag..."
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                style={searchInputStyle}
                onFocus={(e) => { e.currentTarget.style.borderColor = 'var(--accent)' }}
                onBlur={(e) => { e.currentTarget.style.borderColor = 'var(--border)' }}
              />
            </div>
            <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap' }}>
              {TYPE_FILTERS.map((t) => (
                <button
                  key={t}
                  onClick={() => handleFilter(t)}
                  style={{
                    padding: '6px 14px',
                    borderRadius: 'var(--radius-sm)',
                    fontSize: '0.78rem',
                    fontWeight: activeType === t ? 600 : 400,
                    border: activeType === t ? '1px solid var(--accent)' : '1px solid var(--border)',
                    backgroundColor: activeType === t ? 'color-mix(in srgb, var(--accent) 12%, transparent)' : 'var(--surface-2)',
                    color: activeType === t ? 'var(--accent)' : 'var(--text-muted)',
                    cursor: 'pointer',
                    textTransform: 'capitalize',
                  }}
                >
                  {t === 'all' ? 'All' : t.charAt(0) + t.slice(1).toLowerCase()}
                </button>
              ))}
            </div>
          </div>
        </Card>

        {error && (
          <div style={errorBannerStyle}>{error}</div>
        )}

        {isLoading ? (
          <LoadingSpinner message="Loading contacts..." />
        ) : contacts.length === 0 ? (
          <EmptyState
            icon={<Users size={48} />}
            title="No contacts found"
            description={search || activeType !== 'all' ? 'Try adjusting your search or filters.' : 'Add your first contact to get started.'}
            action={
              <button onClick={() => setShowAddModal(true)} style={priBtnStyle}>
                <Plus size={16} /> Add Contact
              </button>
            }
          />
        ) : (
          <DataTable
            columns={columns}
            data={contacts}
            keyExtractor={(c) => c.id}
            pageSize={20}
          />
        )}

        {/* Add Contact Modal */}
        {showAddModal && (
          <div
            style={{
              position: 'fixed', inset: 0, zIndex: 100,
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              backgroundColor: 'rgba(0,0,0,0.5)',
            }}
            onClick={(e) => { if (e.target === e.currentTarget) setShowAddModal(false) }}
          >
            <div
              style={{
                backgroundColor: 'var(--surface)',
                borderRadius: 'var(--radius-lg)',
                border: '1px solid var(--border)',
                width: '100%', maxWidth: '480px', maxHeight: '90vh', overflowY: 'auto',
                padding: '24px',
              }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
                <h2 style={{ fontSize: '1.1rem', fontWeight: 700, color: 'var(--text)' }}>Add Contact</h2>
                <button onClick={() => setShowAddModal(false)} style={{ background: 'none', border: 'none', color: 'var(--text-muted)', cursor: 'pointer', padding: '4px' }}>
                  <X size={20} />
                </button>
              </div>

              {saveError && <div style={errorBannerStyle}>{saveError}</div>}

              <form onSubmit={handleAdd}>
                <div style={{ marginBottom: '12px' }}>
                  <label style={labelStyle}>Type</label>
                  <select value={form.contact_type} onChange={(e) => setForm({ ...form, contact_type: e.target.value })} style={inputStyle}>
                    {CONTACT_TYPE_OPTIONS.map((t) => (
                      <option key={t} value={t}>{t.charAt(0) + t.slice(1).toLowerCase()}</option>
                    ))}
                  </select>
                </div>

                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
                  <div>
                    <label style={labelStyle}>First Name *</label>
                    <input type="text" value={form.first_name} onChange={(e) => setForm({ ...form, first_name: e.target.value })} style={inputStyle} required />
                  </div>
                  <div>
                    <label style={labelStyle}>Last Name *</label>
                    <input type="text" value={form.last_name} onChange={(e) => setForm({ ...form, last_name: e.target.value })} style={inputStyle} required />
                  </div>
                </div>

                <div style={{ marginTop: '12px' }}>
                  <label style={labelStyle}>Email</label>
                  <input type="email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} style={inputStyle} />
                </div>

                <div style={{ marginTop: '12px' }}>
                  <label style={labelStyle}>Phone</label>
                  <input type="text" value={form.phone} onChange={(e) => setForm({ ...form, phone: e.target.value })} style={inputStyle} />
                </div>

                <div style={{ marginTop: '12px' }}>
                  <label style={labelStyle}>MRN (Medical Record Number)</label>
                  <input type="text" value={form.mrn} onChange={(e) => setForm({ ...form, mrn: e.target.value })} style={inputStyle} />
                </div>

                <div style={{ marginTop: '12px', display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <input
                    type="checkbox"
                    id="consent"
                    checked={form.consent_marketing}
                    onChange={(e) => setForm({ ...form, consent_marketing: e.target.checked })}
                  />
                  <label htmlFor="consent" style={{ fontSize: '0.85rem', color: 'var(--text)', cursor: 'pointer' }}>
                    Marketing consent
                  </label>
                </div>

                <div style={{ marginTop: '20px', display: 'flex', gap: '8px', justifyContent: 'flex-end' }}>
                  <button type="button" onClick={() => setShowAddModal(false)} style={secBtnStyle}>Cancel</button>
                  <button type="submit" disabled={saving} style={priBtnStyle}>
                    {saving ? 'Saving...' : 'Save Contact'}
                  </button>
                </div>
              </form>
            </div>
          </div>
        )}
      </div>
    </ErrorBoundary>
  )
}

const labelStyle: React.CSSProperties = {
  display: 'block',
  fontSize: '0.8rem',
  fontWeight: 500,
  color: 'var(--text-muted)',
  marginBottom: '4px',
}

const inputStyle: React.CSSProperties = {
  width: '100%',
  padding: '8px 12px',
  backgroundColor: 'var(--surface-2)',
  border: '1px solid var(--border)',
  borderRadius: 'var(--radius-md)',
  color: 'var(--text)',
  fontSize: '0.85rem',
  outline: 'none',
  boxSizing: 'border-box' as const,
}

const searchInputStyle: React.CSSProperties = {
  width: '100%',
  padding: '8px 12px 8px 34px',
  backgroundColor: 'var(--surface-2)',
  border: '1px solid var(--border)',
  borderRadius: 'var(--radius-md)',
  color: 'var(--text)',
  fontSize: '0.85rem',
  outline: 'none',
  boxSizing: 'border-box' as const,
}

const priBtnStyle: React.CSSProperties = {
  display: 'inline-flex',
  alignItems: 'center',
  gap: '6px',
  padding: '8px 16px',
  backgroundColor: 'var(--accent)',
  color: '#fff',
  border: 'none',
  borderRadius: 'var(--radius-md)',
  fontSize: '0.85rem',
  fontWeight: 600,
  cursor: 'pointer',
}

const secBtnStyle: React.CSSProperties = {
  display: 'inline-flex',
  alignItems: 'center',
  gap: '6px',
  padding: '8px 16px',
  backgroundColor: 'var(--surface-2)',
  color: 'var(--text)',
  border: '1px solid var(--border)',
  borderRadius: 'var(--radius-md)',
  fontSize: '0.85rem',
  fontWeight: 500,
  cursor: 'pointer',
}

const errorBannerStyle: React.CSSProperties = {
  backgroundColor: 'color-mix(in srgb, var(--danger) 12%, transparent)',
  color: 'var(--danger)',
  padding: '10px 16px',
  borderRadius: 'var(--radius-md)',
  fontSize: '0.85rem',
  border: '1px solid color-mix(in srgb, var(--danger) 25%, transparent)',
  marginBottom: '12px',
}
