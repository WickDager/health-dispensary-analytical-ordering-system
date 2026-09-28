import { useState, useEffect, useCallback } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { Search, Plus, Package } from 'lucide-react'
import api, { extractResults, extractCount, type PaginatedResponse } from '../api/client'
import { useRoleAccess } from '../hooks/useRoleAccess'
import { cn, formatCurrency } from '../lib/utils'
import Card from '../components/ui/Card'
import Badge from '../components/ui/Badge'
import DataTable, { type Column } from '../components/ui/DataTable'
import EmptyState from '../components/ui/EmptyState'
import LoadingSpinner from '../components/ui/LoadingSpinner'
import ErrorBoundary from '../components/ui/ErrorBoundary'
import Modal from '../components/ui/Modal'

// ---------------------------------------------------------------------------
// Types matching the backend ProductSerializer EXACTLY
// ---------------------------------------------------------------------------
interface Product {
  id: string // UUID
  name: string
  api: string // NOT api_name
  strength: string
  soh: number // NOT stock_on_hand
  min_stock: number
  max_stock: number
  unit_cost: number
  pack_size: number
  reorder_point: number
  supplier: string | null // UUID of supplier FK
  supplier_name: string | null
  stock_status: 'HEALTHY' | 'LOW' | 'CRITICAL' | 'STOCKOUT' // UPPERCASE
}

interface Supplier {
  id: string
  name: string
}

type StockFilter = 'all' | 'HEALTHY' | 'LOW' | 'CRITICAL' | 'STOCKOUT'

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------
const FILTERS: { key: StockFilter; label: string; dotColor: string }[] = [
  { key: 'all', label: 'All', dotColor: 'var(--text-muted)' },
  { key: 'HEALTHY', label: 'Healthy', dotColor: 'var(--ok)' },
  { key: 'LOW', label: 'Low', dotColor: 'var(--warn)' },
  { key: 'CRITICAL', label: 'Critical', dotColor: 'var(--danger)' },
  { key: 'STOCKOUT', label: 'Stockout', dotColor: 'var(--danger)' },
]

const STATUS_VARIANT: Record<string, 'ok' | 'warn' | 'danger'> = {
  HEALTHY: 'ok',
  LOW: 'warn',
  CRITICAL: 'danger',
  STOCKOUT: 'danger',
}

const INITIAL_FORM = {
  name: '',
  api: '',
  strength: '',
  min_stock: 100,
  max_stock: 1000,
  reorder_point: 200,
  unit_cost: 0,
  pack_size: 1,
  supplier: '',
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------
export default function InventoryList() {
  const navigate = useNavigate()
  const [searchParams, setSearchParams] = useSearchParams()
  const { isAdmin } = useRoleAccess()

  const activeFilter = (searchParams.get('stock_status') as StockFilter) || 'all'
  const [search, setSearch] = useState('')
  const [products, setProducts] = useState<Product[]>([])
  const [totalCount, setTotalCount] = useState(0)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState('')

  // -- Add Product modal
  const [addOpen, setAddOpen] = useState(false)
  const [addForm, setAddForm] = useState({ ...INITIAL_FORM })
  const [adding, setAdding] = useState(false)
  const [addError, setAddError] = useState('')
  const [suppliers, setSuppliers] = useState<Supplier[]>([])

  const fetchProducts = useCallback(async () => {
    setIsLoading(true)
    setError('')
    try {
      const params = new URLSearchParams()
      if (activeFilter !== 'all') params.set('stock_status', activeFilter)
      if (search.trim()) params.set('search', search.trim())
      const qs = params.toString()
      const url = `/products/${qs ? `?${qs}` : ''}`

      const data = await api.get<PaginatedResponse<Product> | Product[]>(url)
      setProducts(extractResults(data))
      setTotalCount(extractCount(data))
    } catch {
      setError('Failed to load inventory. Please try again.')
      setProducts([])
      setTotalCount(0)
    } finally {
      setIsLoading(false)
    }
  }, [activeFilter, search])

  useEffect(() => {
    fetchProducts()
  }, [fetchProducts])

  // Load suppliers for the add form
  const loadSuppliers = useCallback(async () => {
    try {
      const data = await api.get<Supplier[] | PaginatedResponse<Supplier>>('/suppliers/')
      setSuppliers(extractResults(data))
    } catch {
      // Non-critical
    }
  }, [])

  const openAddModal = () => {
    setAddForm({ ...INITIAL_FORM })
    setAddError('')
    setAddOpen(true)
    loadSuppliers()
  }

  const handleAddProduct = async () => {
    if (!addForm.name.trim() || !addForm.api.trim() || !addForm.strength.trim()) {
      setAddError('Name, API, and Strength are required.')
      return
    }
    setAdding(true)
    setAddError('')
    try {
      const body: Record<string, unknown> = {
        name: addForm.name.trim(),
        api: addForm.api.trim(),
        strength: addForm.strength.trim(),
        min_stock: addForm.min_stock,
        max_stock: addForm.max_stock,
        reorder_point: addForm.reorder_point,
        unit_cost: addForm.unit_cost,
        pack_size: addForm.pack_size,
      }
      if (addForm.supplier) {
        body.supplier = addForm.supplier
      }
      await api.post<Product>('/products/', body)
      setAddOpen(false)
      fetchProducts()
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to create product.'
      setAddError(msg)
    } finally {
      setAdding(false)
    }
  }

  const handleFilterChange = (key: StockFilter) => {
    const next = new URLSearchParams(searchParams)
    if (key === 'all') {
      next.delete('stock_status')
    } else {
      next.set('stock_status', key)
    }
    setSearchParams(next)
  }

  const columns: Column<Product>[] = [
    {
      key: 'name',
      header: 'Name',
      sortable: true,
      render: (p) => (
        <span
          style={{ fontWeight: 500, color: 'var(--accent)', cursor: 'pointer' }}
          onClick={() => navigate(`/inventory/${p.id}`)}
        >
          {p.name}
        </span>
      ),
    },
    { key: 'api', header: 'API', sortable: true },
    { key: 'strength', header: 'Strength', sortable: true },
    {
      key: 'soh',
      header: 'SOH',
      sortable: true,
      render: (p) => <span style={{ fontWeight: 600 }}>{p.soh}</span>,
    },
    { key: 'min_stock', header: 'Min Stock', sortable: true },
    { key: 'supplier_name', header: 'Supplier', sortable: true },
    {
      key: 'stock_status',
      header: 'Status',
      sortable: true,
      render: (p) => (
        <Badge variant={STATUS_VARIANT[p.stock_status] || 'info'} dot>
          {p.stock_status.charAt(0) + p.stock_status.slice(1).toLowerCase()}
        </Badge>
      ),
    },
  ]

  // -- Render ---------------------------------------------------------------
  return (
    <ErrorBoundary>
      <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
        {/* Header */}
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            flexWrap: 'wrap',
            gap: '12px',
          }}
        >
          <div>
            <h1 style={{ fontSize: '1.5rem', fontWeight: 700, color: 'var(--text)' }}>
              Inventory
            </h1>
            <p style={{ fontSize: '0.85rem', color: 'var(--text-muted)', marginTop: '2px' }}>
              {totalCount} product{totalCount !== 1 ? 's' : ''}
            </p>
          </div>
          {isAdmin && (
            <button
              onClick={openAddModal}
              style={{
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
              }}
            >
              <Plus size={16} /> Add Product
            </button>
          )}
        </div>

        {/* Search + Filters */}
        <Card padding="16px 20px">
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '12px', alignItems: 'center' }}>
            <div style={{ position: 'relative', flex: '1 1 300px' }}>
              <Search
                size={16}
                style={{
                  position: 'absolute',
                  left: '10px',
                  top: '50%',
                  transform: 'translateY(-50%)',
                  color: 'var(--text-muted)',
                }}
              />
              <input
                type="text"
                placeholder="Search by name, API, or supplier..."
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                style={{
                  width: '100%',
                  padding: '8px 12px 8px 34px',
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
            <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap' }}>
              {FILTERS.map((f) => (
                <button
                  key={f.key}
                  onClick={() => handleFilterChange(f.key)}
                  style={{
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: '5px',
                    padding: '6px 12px',
                    borderRadius: 'var(--radius-sm)',
                    fontSize: '0.78rem',
                    fontWeight: activeFilter === f.key ? 600 : 400,
                    border:
                      activeFilter === f.key
                        ? '1px solid var(--accent)'
                        : '1px solid var(--border)',
                    backgroundColor:
                      activeFilter === f.key
                        ? 'color-mix(in srgb, var(--accent) 12%, transparent)'
                        : 'var(--surface-2)',
                    color: activeFilter === f.key ? 'var(--accent)' : 'var(--text-muted)',
                    cursor: 'pointer',
                    transition: 'all 150ms ease',
                  }}
                >
                  <span
                    style={{
                      width: '6px',
                      height: '6px',
                      borderRadius: '50%',
                      backgroundColor: f.dotColor,
                      flexShrink: 0,
                    }}
                  />
                  {f.label}
                </button>
              ))}
            </div>
          </div>
        </Card>

        {/* Error */}
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

        {/* Content */}
        {isLoading ? (
          <LoadingSpinner message="Loading inventory..." />
        ) : products.length === 0 ? (
          <EmptyState
            icon={<Package size={48} />}
            title="No products found"
            description={
              search || activeFilter !== 'all'
                ? 'Try adjusting your search or filters.'
                : 'Get started by adding your first product.'
            }
            action={
              isAdmin ? (
                <button
                  onClick={openAddModal}
                  style={{
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
                  }}
                >
                  <Plus size={16} /> Add Product
                </button>
              ) : undefined
            }
          />
        ) : (
          <DataTable
            columns={columns}
            data={products}
            keyExtractor={(p) => p.id}
            pageSize={20}
            emptyMessage="No products found."
          />
        )}

        {/* Add Product Modal */}
        <Modal open={addOpen} onClose={() => setAddOpen(false)} title="Add Product" maxWidth="600px">
          <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
            {addError && (
              <div
                style={{
                  backgroundColor: 'color-mix(in srgb, var(--danger) 12%, transparent)',
                  color: 'var(--danger)',
                  padding: '8px 12px',
                  borderRadius: 'var(--radius-md)',
                  fontSize: '0.82rem',
                  border: '1px solid color-mix(in srgb, var(--danger) 25%, transparent)',
                }}
              >
                {addError}
              </div>
            )}

            <Field label="Product Name *" value={addForm.name} onChange={(v) => setAddForm((p) => ({ ...p, name: v }))} />
            <Field label="API *" value={addForm.api} onChange={(v) => setAddForm((p) => ({ ...p, api: v }))} />
            <Field label="Strength *" value={addForm.strength} onChange={(v) => setAddForm((p) => ({ ...p, strength: v }))} />

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
              <Field
                label="Min Stock"
                type="number"
                value={String(addForm.min_stock)}
                onChange={(v) => setAddForm((p) => ({ ...p, min_stock: Number(v) || 0 }))}
              />
              <Field
                label="Max Stock"
                type="number"
                value={String(addForm.max_stock)}
                onChange={(v) => setAddForm((p) => ({ ...p, max_stock: Number(v) || 0 }))}
              />
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
              <Field
                label="Reorder Point"
                type="number"
                value={String(addForm.reorder_point)}
                onChange={(v) => setAddForm((p) => ({ ...p, reorder_point: Number(v) || 0 }))}
              />
              <Field
                label="Pack Size"
                type="number"
                value={String(addForm.pack_size)}
                onChange={(v) => setAddForm((p) => ({ ...p, pack_size: Number(v) || 1 }))}
              />
            </div>
            <Field
              label="Unit Cost"
              type="number"
              value={String(addForm.unit_cost)}
              onChange={(v) => setAddForm((p) => ({ ...p, unit_cost: Number(v) || 0 }))}
            />

            {/* Supplier select */}
            <div>
              <label style={{ display: 'block', fontSize: '0.8rem', fontWeight: 500, color: 'var(--text)', marginBottom: '4px' }}>
                Supplier
              </label>
              <select
                value={addForm.supplier}
                onChange={(e) => setAddForm((p) => ({ ...p, supplier: e.target.value }))}
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
              >
                <option value="">-- None --</option>
                {suppliers.map((s) => (
                  <option key={s.id} value={s.id}>
                    {s.name}
                  </option>
                ))}
              </select>
            </div>

            <div style={{ display: 'flex', gap: '10px', justifyContent: 'flex-end', marginTop: '8px' }}>
              <button
                onClick={() => setAddOpen(false)}
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
                onClick={handleAddProduct}
                disabled={adding}
                style={{
                  padding: '8px 16px',
                  backgroundColor: 'var(--accent)',
                  color: '#fff',
                  border: 'none',
                  borderRadius: 'var(--radius-md)',
                  fontSize: '0.85rem',
                  fontWeight: 600,
                  cursor: adding ? 'wait' : 'pointer',
                  opacity: adding ? 0.7 : 1,
                }}
              >
                {adding ? 'Adding...' : 'Add Product'}
              </button>
            </div>
          </div>
        </Modal>
      </div>
    </ErrorBoundary>
  )
}

// ---------------------------------------------------------------------------
// Reusable field for the modal
// ---------------------------------------------------------------------------
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
