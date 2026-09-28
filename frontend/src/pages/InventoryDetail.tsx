import { useState, useEffect, useCallback } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { Edit, Package, AlertTriangle, Box } from 'lucide-react'
import api, { extractResults, type PaginatedResponse } from '../api/client'
import { useRoleAccess } from '../hooks/useRoleAccess'
import { formatCurrency, formatDate, cn } from '../lib/utils'
import Card from '../components/ui/Card'
import Badge from '../components/ui/Badge'
import KpiCard from '../components/ui/KpiCard'
import DataTable, { type Column } from '../components/ui/DataTable'
import Modal from '../components/ui/Modal'
import LoadingSpinner from '../components/ui/LoadingSpinner'
import ErrorBoundary from '../components/ui/ErrorBoundary'
import Breadcrumbs from '../components/ui/Breadcrumbs'

// ---------------------------------------------------------------------------
// Types matching backend serializers EXACTLY
// ---------------------------------------------------------------------------
interface Product {
  id: string // UUID
  name: string
  api: string // NOT api_name
  strength: string
  supplier_name: string | null
  supplier: string | null // UUID
  soh: number // NOT stock_on_hand
  min_stock: number
  max_stock: number
  reorder_point: number
  unit_cost: number
  pack_size: number
  stock_status: 'HEALTHY' | 'LOW' | 'CRITICAL' | 'STOCKOUT' // UPPERCASE
  description?: string
  category_name?: string
  created_at?: string
}

interface Lot {
  id: string // UUID
  batch_number: string
  manufacture_date: string // NOT mfg_date
  expiry_date: string
  quantity: number
  is_locked: boolean
  created_at?: string
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------
const STATUS_VARIANT: Record<string, 'ok' | 'warn' | 'danger'> = {
  HEALTHY: 'ok',
  LOW: 'warn',
  CRITICAL: 'danger',
  STOCKOUT: 'danger',
}

function getExpiryBadge(
  expiryDate: string,
): { variant: 'ok' | 'warn' | 'danger'; label: string } {
  const now = new Date()
  const exp = new Date(expiryDate)
  const diffMs = exp.getTime() - now.getTime()
  const diffDays = diffMs / (1000 * 60 * 60 * 24)
  if (diffMs < 0) return { variant: 'danger', label: 'Expired' }
  if (diffDays <= 60) return { variant: 'warn', label: `${Math.ceil(diffDays)}d` }
  return { variant: 'ok', label: `${Math.ceil(diffDays)}d` }
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------
export default function InventoryDetail() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const { isAdmin } = useRoleAccess()

  const [product, setProduct] = useState<Product | null>(null)
  const [lots, setLots] = useState<Lot[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState('')
  const [editOpen, setEditOpen] = useState(false)
  const [editForm, setEditForm] = useState<Partial<Product>>({})
  const [saving, setSaving] = useState(false)

  const fetchProduct = useCallback(async () => {
    setIsLoading(true)
    setError('')
    try {
      const [prodData, lotData] = await Promise.all([
        api.get<Product>(`/products/${id}/`).catch(() => null),
        api.get<Lot[] | PaginatedResponse<Lot>>(`/lots/?product=${id}`).catch(() => null),
      ])
      setProduct(prodData)
      if (lotData) {
        setLots(extractResults<Lot>(lotData))
      } else {
        setLots([])
      }
    } catch {
      setError('Failed to load product details.')
      setProduct(null)
    } finally {
      setIsLoading(false)
    }
  }, [id])

  useEffect(() => {
    if (id) fetchProduct()
  }, [id, fetchProduct])

  const handleEdit = async () => {
    setSaving(true)
    setError('')
    try {
      const body: Record<string, unknown> = {}
      if (editForm.name !== undefined) body.name = editForm.name
      if (editForm.api !== undefined) body.api = editForm.api
      if (editForm.strength !== undefined) body.strength = editForm.strength
      if (editForm.min_stock !== undefined) body.min_stock = editForm.min_stock
      if (editForm.max_stock !== undefined) body.max_stock = editForm.max_stock
      if (editForm.reorder_point !== undefined) body.reorder_point = editForm.reorder_point
      if (editForm.unit_cost !== undefined) body.unit_cost = editForm.unit_cost
      if (editForm.description !== undefined) body.description = editForm.description

      const updated = await api.patch<Product>(`/products/${id}/`, body)
      setProduct(updated)
      setEditOpen(false)
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to save changes.'
      setError(msg)
    } finally {
      setSaving(false)
    }
  }

  const lotColumns: Column<Lot>[] = [
    { key: 'batch_number', header: 'Batch #', sortable: true },
    {
      key: 'expiry_date',
      header: 'Expiry Date',
      sortable: true,
      render: (l) => {
        const b = getExpiryBadge(l.expiry_date)
        return (
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <span>{formatDate(l.expiry_date)}</span>
            <Badge variant={b.variant}>{b.label}</Badge>
          </div>
        )
      },
    },
    { key: 'quantity', header: 'Quantity', sortable: true },
    {
      key: 'is_locked',
      header: 'Locked',
      sortable: true,
      render: (l) =>
        l.is_locked ? (
          <Badge variant="danger" dot>
            Locked
          </Badge>
        ) : (
          <Badge variant="ok" dot>
            Open
          </Badge>
        ),
    },
    {
      key: 'manufacture_date',
      header: 'Mfg Date',
      sortable: true,
      render: (l) => formatDate(l.manufacture_date),
    },
  ]

  // -------------------------------------------------------------------
  // Loading / Error / Not Found
  // -------------------------------------------------------------------
  if (isLoading) return <LoadingSpinner message="Loading product details..." />

  if (!product && !isLoading) {
    return (
      <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
        <BackButton onClick={() => navigate('/inventory')} />
        <div
          style={{
            backgroundColor: 'color-mix(in srgb, var(--danger) 12%, transparent)',
            color: 'var(--danger)',
            padding: '16px',
            borderRadius: 'var(--radius-md)',
            textAlign: 'center',
          }}
        >
          {error || 'Product not found.'}
        </div>
      </div>
    )
  }

  // -------------------------------------------------------------------
  // Render
  // -------------------------------------------------------------------
  return (
    <ErrorBoundary>
      <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
        {/* Header */}
        <div
          style={{
            display: 'flex',
            alignItems: 'flex-start',
            justifyContent: 'space-between',
            flexWrap: 'wrap',
            gap: '12px',
          }}
        >
          <div>
            <BackButton onClick={() => navigate('/inventory')} productName={product?.name} />
            <h1 style={{ fontSize: '1.5rem', fontWeight: 700, color: 'var(--text)' }}>
              {product!.name}
            </h1>
            <div style={{ display: 'flex', gap: '10px', alignItems: 'center', marginTop: '4px' }}>
              <span style={{ fontSize: '0.85rem', color: 'var(--text-muted)' }}>
                {product!.api} {product!.strength}
              </span>
              <Badge variant={STATUS_VARIANT[product!.stock_status] || 'info'} dot>
                {product!.stock_status.charAt(0) +
                  product!.stock_status.slice(1).toLowerCase()}
              </Badge>
              {product!.supplier_name && (
                <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
                  via {product!.supplier_name}
                </span>
              )}
            </div>
          </div>
          {isAdmin && (
            <button
              onClick={() => {
                setEditForm({
                  name: product!.name,
                  api: product!.api,
                  strength: product!.strength,
                  min_stock: product!.min_stock,
                  max_stock: product!.max_stock,
                  reorder_point: product!.reorder_point,
                  unit_cost: product!.unit_cost,
                  description: product!.description,
                })
                setEditOpen(true)
              }}
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: '6px',
                padding: '8px 16px',
                backgroundColor: 'color-mix(in srgb, var(--accent) 10%, transparent)',
                color: 'var(--accent)',
                border: '1px solid var(--border)',
                borderRadius: 'var(--radius-md)',
                fontSize: '0.85rem',
                fontWeight: 600,
                cursor: 'pointer',
              }}
            >
              <Edit size={16} /> Edit
            </button>
          )}
        </div>

        {/* Error banner */}
        {error && (
          <div
            style={{
              backgroundColor: 'color-mix(in srgb, var(--danger) 12%, transparent)',
              color: 'var(--danger)',
              padding: '10px 16px',
              borderRadius: 'var(--radius-md)',
              fontSize: '0.85rem',
              border: '1px solid color-mix(in srgb, var(--danger) 25%, transparent)',
            }}
          >
            {error}
          </div>
        )}

        {/* KPI Cards */}
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fill, minmax(180px, 1fr))',
            gap: '12px',
          }}
        >
          <KpiCard icon={<Package size={20} />} label="Stock On Hand" value={product!.soh} />
          <KpiCard
            icon={<Box size={20} />}
            label="Min / Max Stock"
            value={`${product!.min_stock} / ${product!.max_stock}`}
          />
          <KpiCard
            icon={<AlertTriangle size={20} />}
            label="Reorder Point"
            value={product!.reorder_point}
          />
          <KpiCard
            icon={<Package size={20} />}
            label="Unit Cost"
            value={formatCurrency(product!.unit_cost || 0)}
          />
        </div>

        {/* Description */}
        {product!.description && (
          <Card title="Description">
            <p style={{ color: 'var(--text)', fontSize: '0.9rem', lineHeight: 1.6 }}>
              {product!.description}
            </p>
          </Card>
        )}

        {/* Lots Table */}
        <Card title={`Lots (${lots.length})`}>
          {lots.length === 0 ? (
            <div
              style={{
                textAlign: 'center',
                padding: '20px',
                color: 'var(--text-muted)',
                fontSize: '0.85rem',
              }}
            >
              No lots recorded for this product.
            </div>
          ) : (
            <DataTable
              columns={lotColumns}
              data={lots}
              keyExtractor={(l) => l.id}
              pageSize={10}
              emptyMessage="No lots found."
            />
          )}
        </Card>

        {/* Edit Modal */}
        <Modal open={editOpen} onClose={() => setEditOpen(false)} title="Edit Product" maxWidth="600px">
          <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
            <Field
              label="Name"
              value={editForm.name || ''}
              onChange={(v) => setEditForm((p) => ({ ...p, name: v }))}
            />
            <Field
              label="API"
              value={editForm.api || ''}
              onChange={(v) => setEditForm((p) => ({ ...p, api: v }))}
            />
            <Field
              label="Strength"
              value={editForm.strength || ''}
              onChange={(v) => setEditForm((p) => ({ ...p, strength: v }))}
            />
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
              <Field
                label="Min Stock"
                type="number"
                value={String(editForm.min_stock ?? '')}
                onChange={(v) => setEditForm((p) => ({ ...p, min_stock: Number(v) || 0 }))}
              />
              <Field
                label="Max Stock"
                type="number"
                value={String(editForm.max_stock ?? '')}
                onChange={(v) => setEditForm((p) => ({ ...p, max_stock: Number(v) || 0 }))}
              />
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
              <Field
                label="Reorder Point"
                type="number"
                value={String(editForm.reorder_point ?? '')}
                onChange={(v) => setEditForm((p) => ({ ...p, reorder_point: Number(v) || 0 }))}
              />
              <Field
                label="Unit Cost"
                type="number"
                value={String(editForm.unit_cost ?? '')}
                onChange={(v) => setEditForm((p) => ({ ...p, unit_cost: Number(v) || 0 }))}
              />
            </div>
            <Field
              label="Description"
              value={editForm.description || ''}
              onChange={(v) => setEditForm((p) => ({ ...p, description: v }))}
            />
            <div style={{ display: 'flex', gap: '10px', justifyContent: 'flex-end', marginTop: '8px' }}>
              <button
                onClick={() => setEditOpen(false)}
                style={{
                  padding: '8px 16px',
                  backgroundColor: 'transparent',
                  color: 'var(--text-muted)',
                  border: '1px solid var(--border)',
                  borderRadius: 'var(--radius-md)',
                  fontSize: '0.85rem',
                  cursor: 'pointer',
                }}
              >
                Cancel
              </button>
              <button
                onClick={handleEdit}
                disabled={saving}
                style={{
                  padding: '8px 16px',
                  backgroundColor: 'var(--accent)',
                  color: '#fff',
                  border: 'none',
                  borderRadius: 'var(--radius-md)',
                  fontSize: '0.85rem',
                  fontWeight: 600,
                  cursor: saving ? 'wait' : 'pointer',
                  opacity: saving ? 0.7 : 1,
                }}
              >
                {saving ? 'Saving...' : 'Save Changes'}
              </button>
            </div>
          </div>
        </Modal>
      </div>
    </ErrorBoundary>
  )
}

// ---------------------------------------------------------------------------
// Reusable components
// ---------------------------------------------------------------------------
function BackButton({ onClick, productName }: { onClick: () => void; productName?: string }) {
  return (
    <button
      onClick={onClick}
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: '6px',
        background: 'none',
        border: 'none',
        color: 'var(--accent)',
        cursor: 'pointer',
        fontSize: '0.85rem',
        fontWeight: 500,
        padding: 0,
        marginBottom: '8px',
        width: 'fit-content',
      }}
    >
      <Breadcrumbs
        items={[
          { label: 'Inventory', to: '/inventory' },
          { label: productName || 'Product Details' },
        ]}
        backTo={{ to: '/inventory', label: 'Inventory' }}
      />
    </button>
  )
}

function Field({
  label,
  value,
  onChange,
  type = 'text',
}: {
  label: string
  value: string
  onChange: (v: string) => void
  type?: string
}) {
  return (
    <div>
      <label
        style={{
          display: 'block',
          fontSize: '0.8rem',
          fontWeight: 500,
          color: 'var(--text)',
          marginBottom: '4px',
        }}
      >
        {label}
      </label>
      <input
        type={type}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        style={{
          width: '100%',
          padding: '8px 10px',
          backgroundColor: 'var(--surface-2)',
          border: '1px solid var(--border)',
          borderRadius: 'var(--radius-md)',
          color: 'var(--text)',
          fontSize: '0.85rem',
          outline: 'none',
          boxSizing: 'border-box',
        }}
        onFocus={(e) => {
          e.currentTarget.style.borderColor = 'var(--accent)'
        }}
        onBlur={(e) => {
          e.currentTarget.style.borderColor = 'var(--border)'
        }}
      />
    </div>
  )
}
