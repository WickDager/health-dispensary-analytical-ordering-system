import { useState, useEffect, useCallback } from 'react'
import { ShoppingCart, AlertTriangle, DollarSign, Package } from 'lucide-react'
import api from '../api/client'
import { formatCurrency } from '../lib/utils'
import Card from '../components/ui/Card'
import Badge from '../components/ui/Badge'
import KpiCard from '../components/ui/KpiCard'
import LoadingSpinner from '../components/ui/LoadingSpinner'
import EmptyState from '../components/ui/EmptyState'
import ErrorBoundary from '../components/ui/ErrorBoundary'

/** One product row of the backend's /orders/procurement-suggestions/ response. */
interface ReorderSuggestion {
  product_id: string
  product_name: string
  api: string
  strength: string
  current_soh: number
  min_stock: number
  reorder_point: number
  max_stock: number
  recommended_qty: number
  unit_cost: number
  line_total: number
}

/** One supplier group of the backend's /orders/procurement-suggestions/ response. */
interface SupplierSuggestionGroup {
  supplier_id: string
  supplier_name: string
  items: ReorderSuggestion[]
  estimated_total: number
}

interface GroupedSupplier {
  supplier_id: string
  supplier_name: string
  items: ReorderSuggestion[]
  total_value: number
}

export default function Procurement() {
  const [groups, setGroups] = useState<GroupedSupplier[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState('')
  const [generating, setGenerating] = useState(false)
  const [poResult, setPoResult] = useState('')

  const fetchData = useCallback(async () => {
    setIsLoading(true)
    setError('')
    setPoResult('')
    try {
      const data = await api.get<SupplierSuggestionGroup[]>(
        '/orders/procurement-suggestions/?min_stock_only=false'
      )
      const rows = Array.isArray(data) ? data : []
      setGroups(rows.map((g) => ({
        supplier_id: g.supplier_id,
        supplier_name: g.supplier_name,
        items: g.items || [],
        total_value: g.estimated_total ?? 0,
      })))
    } catch {
      setError('Failed to load procurement data.')
      setGroups([])
    } finally {
      setIsLoading(false)
    }
  }, [])

  useEffect(() => { fetchData() }, [fetchData])

  const totalReorderValue = groups.reduce((sum, g) => sum + g.total_value, 0)
  const productsBelowReorder = groups.reduce((sum, g) => sum + g.items.length, 0)

  // Create one PENDING purchase order per supplier, then submit each for
  // approval (the ORDER_SUBMIT approval is what actually sends it).
  const handleGeneratePO = async () => {
    setGenerating(true)
    setPoResult('')
    setError('')
    try {
      const created: string[] = []
      for (const group of groups) {
        if (group.items.length === 0) continue
        const order = await api.post<{ id: string }>('/orders/', {
          supplier: group.supplier_id,
          status: 'PENDING',
          total_cost: group.total_value,
          items: group.items.map((i) => ({
            product: i.product_id,
            quantity: i.recommended_qty,
            unit_cost: i.unit_cost,
          })),
        })
        await api.post(`/orders/${order.id}/submit/`)
        created.push(group.supplier_name)
      }
      setPoResult(
        created.length > 0
          ? `${created.length} purchase order(s) created and submitted for approval: ${created.join(', ')}.`
          : 'No suggestions to order.'
      )
      fetchData()
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to generate PO.'
      setError(msg)
    } finally {
      setGenerating(false)
    }
  }

  return (
    <ErrorBoundary>
      <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '12px' }}>
          <div>
            <h1 style={{ fontSize: '1.5rem', fontWeight: 700, color: 'var(--text)' }}>Procurement</h1>
            <p style={{ fontSize: '0.85rem', color: 'var(--text-muted)', marginTop: '2px' }}>
              Reorder suggestions and purchase-order generation
            </p>
          </div>
          {groups.length > 0 && (
            <button
              onClick={handleGeneratePO}
              disabled={generating}
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
                cursor: generating ? 'wait' : 'pointer',
                opacity: generating ? 0.7 : 1,
              }}
            >
              <ShoppingCart size={16} />
              {generating ? 'Generating...' : 'Generate POs'}
            </button>
          )}
        </div>

        {error && (
          <div style={{
            backgroundColor: 'color-mix(in srgb, var(--danger) 12%, transparent)',
            color: 'var(--danger)',
            padding: '10px 16px',
            borderRadius: 'var(--radius-md)',
            fontSize: '0.85rem',
            border: '1px solid color-mix(in srgb, var(--danger) 25%, transparent)',
          }}>
            {error}
          </div>
        )}

        {poResult && (
          <div style={{
            backgroundColor: 'color-mix(in srgb, var(--ok) 12%, transparent)',
            color: 'var(--ok)',
            padding: '10px 16px',
            borderRadius: 'var(--radius-md)',
            fontSize: '0.85rem',
            border: '1px solid color-mix(in srgb, var(--ok) 25%, transparent)',
          }}>
            {poResult}
          </div>
        )}

        {/* KPI Cards */}
        <div style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fill, minmax(220px, 1fr))',
          gap: '12px',
        }}>
          <KpiCard
            icon={<DollarSign size={20} />}
            label="Total Reorder Value"
            value={formatCurrency(totalReorderValue)}
          />
          <KpiCard
            icon={<AlertTriangle size={20} />}
            label="Products Below Reorder Point"
            value={productsBelowReorder}
          />
          <KpiCard
            icon={<Package size={20} />}
            label="Suppliers To Order From"
            value={groups.length}
          />
        </div>

        {isLoading ? (
          <LoadingSpinner message="Loading procurement suggestions..." />
        ) : groups.length === 0 ? (
          <EmptyState
            icon={<Package size={48} />}
            title="No reorder suggestions"
            description="All products are above their reorder points. Check back later."
          />
        ) : (
          groups.map((group) => (
            <Card
              key={group.supplier_id}
              title={group.supplier_name}
              action={
                <Badge variant="accent">{formatCurrency(group.total_value)}</Badge>
              }
            >
              <div style={{ overflowX: 'auto' }}>
                <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                  <thead>
                    <tr style={{ borderBottom: '1px solid var(--border)' }}>
                      <th style={thStyle}>Product</th>
                      <th style={thStyle}>Current Stock</th>
                      <th style={thStyle}>Min Stock</th>
                      <th style={thStyle}>Reorder Point</th>
                      <th style={thStyle}>Suggested Qty</th>
                      <th style={thStyle}>Total Cost</th>
                    </tr>
                  </thead>
                  <tbody>
                    {group.items.map((item) => (
                      <tr key={item.product_id} style={{ borderBottom: '1px solid var(--border)' }}>
                        <td style={tdStyle}>
                          <div style={{ fontWeight: 500 }}>{item.product_name}</div>
                          <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                            {item.api} {item.strength}
                          </div>
                        </td>
                        <td style={tdStyle}>{item.current_soh}</td>
                        <td style={tdStyle}>{item.min_stock}</td>
                        <td style={tdStyle}>{item.reorder_point}</td>
                        <td style={{ ...tdStyle, fontWeight: 600, color: 'var(--accent)' }}>
                          {item.recommended_qty}
                        </td>
                        <td style={tdStyle}>
                          {formatCurrency(item.line_total)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </Card>
          ))
        )}
      </div>
    </ErrorBoundary>
  )
}

const thStyle: React.CSSProperties = {
  padding: '10px 14px',
  textAlign: 'left',
  fontSize: '0.75rem',
  fontWeight: 600,
  color: 'var(--text-muted)',
  textTransform: 'uppercase',
  letterSpacing: '0.03em',
  whiteSpace: 'nowrap',
}

const tdStyle: React.CSSProperties = {
  padding: '10px 14px',
  fontSize: '0.85rem',
  color: 'var(--text)',
  whiteSpace: 'nowrap',
}
