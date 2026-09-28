import { useState, useEffect, useCallback } from 'react'
import { Truck, Plus, Edit } from 'lucide-react'
import api, { extractResults } from '../api/client'
import { useRoleAccess } from '../hooks/useRoleAccess'
import { formatCurrency } from '../lib/utils'
import Card from '../components/ui/Card'
import Badge from '../components/ui/Badge'
import DataTable, { type Column } from '../components/ui/DataTable'
import Modal from '../components/ui/Modal'
import EmptyState from '../components/ui/EmptyState'
import LoadingSpinner from '../components/ui/LoadingSpinner'
import ErrorBoundary from '../components/ui/ErrorBoundary'

interface Supplier {
  id: number
  name: string
  email: string
  phone: string
  lead_time_days: number
  min_order_value: string
  rating: number
  product_count: number
  is_active: boolean
  notes: string
}

const emptySupplier = (): Partial<Supplier> => ({
  name: '',
  email: '',
  phone: '',
  lead_time_days: 7,
  min_order_value: '0',
  notes: '',
})

export default function Suppliers() {
  const { isProcurement } = useRoleAccess()
  const [suppliers, setSuppliers] = useState<Supplier[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState('')
  const [modalOpen, setModalOpen] = useState(false)
  const [editing, setEditing] = useState<Partial<Supplier> | null>(null)
  const [saving, setSaving] = useState(false)

  const fetchSuppliers = useCallback(async () => {
    setIsLoading(true)
    setError('')
    try {
      const data = await api.get<Supplier[]>('/suppliers/')
      setSuppliers(extractResults(data))
    } catch {
      setError('Failed to load suppliers.')
      setSuppliers([])
    } finally {
      setIsLoading(false)
    }
  }, [])

  useEffect(() => { fetchSuppliers() }, [fetchSuppliers])

  const handleSave = async () => {
    if (!editing?.name?.trim()) return
    setSaving(true)
    setError('')
    try {
      if (editing.id) {
        const updated = await api.patch<Supplier>(`/suppliers/${editing.id}/`, editing)
        setSuppliers((prev) => prev.map((s) => (s.id === updated.id ? updated : s)))
      } else {
        const created = await api.post<Supplier>('/suppliers/', editing)
        setSuppliers((prev) => [...prev, created])
      }
      setModalOpen(false)
      setEditing(null)
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Save failed.'
      setError(msg)
    } finally {
      setSaving(false)
    }
  }

  const openAdd = () => {
    setEditing(emptySupplier())
    setModalOpen(true)
  }

  const openEdit = (s: Supplier) => {
    setEditing({ ...s })
    setModalOpen(true)
  }

  const canEdit = isProcurement

  const columns: Column<Supplier>[] = [
    { key: 'name', header: 'Name', sortable: true, render: (s) => <span style={{ fontWeight: 500 }}>{s.name}</span> },
    { key: 'email', header: 'Email', sortable: true },
    { key: 'lead_time_days', header: 'Lead Time (days)', sortable: true },
    {
      key: 'min_order_value',
      header: 'Min Order',
      sortable: true,
      render: (s) => formatCurrency(parseFloat(s.min_order_value || '0')),
    },
    {
      key: 'rating',
      header: 'Rating',
      sortable: true,
      render: (s) => {
        const stars = Math.round(s.rating || 0)
        return (
          <span style={{ display: 'inline-flex', gap: '2px' }}>
            {'★'.repeat(stars)}{'☆'.repeat(5 - stars)}
          </span>
        )
      },
    },
    {
      key: 'product_count',
      header: 'Products',
      sortable: true,
    },
  ]

  return (
    <ErrorBoundary>
      <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '12px' }}>
          <div>
            <h1 style={{ fontSize: '1.5rem', fontWeight: 700, color: 'var(--text)' }}>Suppliers</h1>
            <p style={{ fontSize: '0.85rem', color: 'var(--text-muted)', marginTop: '2px' }}>
              {suppliers.length} supplier{suppliers.length !== 1 ? 's' : ''}
            </p>
          </div>
          {canEdit && (
            <button onClick={openAdd} style={priBtnStyle}>
              <Plus size={16} /> Add Supplier
            </button>
          )}
        </div>

        {error && (
          <div style={errorBannerStyle}>{error}</div>
        )}

        {isLoading ? (
          <LoadingSpinner message="Loading suppliers..." />
        ) : suppliers.length === 0 ? (
          <EmptyState
            icon={<Truck size={48} />}
            title="No suppliers"
            description="Add your first supplier to get started."
            action={canEdit ? (
              <button onClick={openAdd} style={priBtnStyle}>
                <Plus size={16} /> Add Supplier
              </button>
            ) : undefined}
          />
        ) : (
          <DataTable
            columns={columns}
            data={suppliers}
            keyExtractor={(s) => s.id}
            pageSize={15}
          />
        )}

        {/* Add/Edit Modal */}
        <Modal
          open={modalOpen}
          onClose={() => { setModalOpen(false); setEditing(null) }}
          title={editing?.id ? 'Edit Supplier' : 'Add Supplier'}
          maxWidth="550px"
        >
          {editing && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
              <Field label="Name" value={editing.name || ''} onChange={(v) => setEditing((p) => ({ ...p, name: v }))} />
              <Field label="Email" value={editing.email || ''} onChange={(v) => setEditing((p) => ({ ...p, email: v }))} type="email" />
              <Field label="Phone" value={editing.phone || ''} onChange={(v) => setEditing((p) => ({ ...p, phone: v }))} />
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
                <Field label="Lead Time (days)" value={String(editing.lead_time_days || '')} onChange={(v) => setEditing((p) => ({ ...p, lead_time_days: Number(v) }))} type="number" />
                <Field label="Min Order Value" value={editing.min_order_value || ''} onChange={(v) => setEditing((p) => ({ ...p, min_order_value: v }))} type="number" />
              </div>
              <Field label="Notes" value={editing.notes || ''} onChange={(v) => setEditing((p) => ({ ...p, notes: v }))} />
              <div style={{ display: 'flex', gap: '10px', justifyContent: 'flex-end', marginTop: '8px' }}>
                <button onClick={() => { setModalOpen(false); setEditing(null) }} style={secBtnStyle}>
                  Cancel
                </button>
                <button onClick={handleSave} disabled={saving || !editing.name?.trim()} style={priBtnStyle}>
                  {saving ? 'Saving...' : 'Save'}
                </button>
              </div>
            </div>
          )}
        </Modal>
      </div>
    </ErrorBoundary>
  )
}

function Field({ label, value, onChange, type = 'text' }: { label: string; value: string; onChange: (v: string) => void; type?: string }) {
  return (
    <div>
      <label style={{ display: 'block', fontSize: '0.8rem', fontWeight: 500, color: 'var(--text)', marginBottom: '4px' }}>{label}</label>
      <input
        type={type}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        style={inputStyle}
        onFocus={(e) => { e.currentTarget.style.borderColor = 'var(--accent)' }}
        onBlur={(e) => { e.currentTarget.style.borderColor = 'var(--border)' }}
      />
    </div>
  )
}

const inputStyle: React.CSSProperties = {
  width: '100%',
  padding: '8px 10px',
  backgroundColor: 'var(--surface-2)',
  border: '1px solid var(--border)',
  borderRadius: 'var(--radius-md)',
  color: 'var(--text)',
  fontSize: '0.85rem',
  outline: 'none',
  boxSizing: 'border-box',
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
  padding: '8px 16px',
  backgroundColor: 'transparent',
  color: 'var(--text-muted)',
  border: '1px solid var(--border)',
  borderRadius: 'var(--radius-md)',
  fontSize: '0.85rem',
  cursor: 'pointer',
}

const errorBannerStyle: React.CSSProperties = {
  backgroundColor: 'color-mix(in srgb, var(--danger) 12%, transparent)',
  color: 'var(--danger)',
  padding: '10px 16px',
  borderRadius: 'var(--radius-md)',
  fontSize: '0.85rem',
  border: '1px solid color-mix(in srgb, var(--danger) 25%, transparent)',
}
