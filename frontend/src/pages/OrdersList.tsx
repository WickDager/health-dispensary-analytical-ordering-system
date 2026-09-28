import { useState, useEffect, useCallback } from 'react'
import { ShoppingCart, ChevronDown, ChevronUp } from 'lucide-react'
import api, { extractResults } from '../api/client'
import { formatCurrency, formatDate } from '../lib/utils'
import Card from '../components/ui/Card'
import Badge from '../components/ui/Badge'
import DataTable, { type Column } from '../components/ui/DataTable'
import EmptyState from '../components/ui/EmptyState'
import LoadingSpinner from '../components/ui/LoadingSpinner'
import ErrorBoundary from '../components/ui/ErrorBoundary'

// Matches apps/orders/serializers.py OrderSerializer exactly.
interface OrderItem {
  id: string
  product: string
  product_name: string
  quantity: number
  unit_cost: number
}

interface Order {
  id: string
  supplier: string
  supplier_name: string
  status: 'PENDING' | 'SENT' | 'COMPLETED' | 'CANCELLED'
  total_cost: number
  order_date: string
  expected_delivery: string | null
  items: OrderItem[]
}

const STATUS_VARIANT: Record<string, 'ok' | 'warn' | 'danger' | 'info' | 'accent'> = {
  PENDING: 'warn',
  SENT: 'accent',
  COMPLETED: 'ok',
  CANCELLED: 'danger',
}

const STATUS_FILTERS = ['all', 'PENDING', 'SENT', 'COMPLETED', 'CANCELLED'] as const

export default function OrdersList() {
  const [orders, setOrders] = useState<Order[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState('')
  const [statusFilter, setStatusFilter] = useState<string>('all')
  const [expandedId, setExpandedId] = useState<string | null>(null)

  const fetchOrders = useCallback(async () => {
    setIsLoading(true)
    setError('')
    try {
      const params = new URLSearchParams()
      if (statusFilter !== 'all') params.set('status', statusFilter)
      const qs = params.toString()
      const data = await api.get<Order[]>(`/orders/${qs ? `?${qs}` : ''}`)
      setOrders(extractResults(data))
    } catch {
      setError('Failed to load orders.')
      setOrders([])
    } finally {
      setIsLoading(false)
    }
  }, [statusFilter])

  useEffect(() => { fetchOrders() }, [fetchOrders])

  const columns: Column<Order>[] = [
    {
      key: 'expand',
      header: '',
      render: (o) => (
        <button
          onClick={() => setExpandedId(expandedId === o.id ? null : o.id)}
          style={{
            background: 'none',
            border: 'none',
            cursor: 'pointer',
            color: 'var(--text-muted)',
            padding: '2px',
          }}
        >
          {expandedId === o.id ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
        </button>
      ),
    },
    { key: 'id', header: 'Order', sortable: true, render: (o) => <span style={{ fontWeight: 600 }}>{o.id.slice(0, 8)}</span> },
    { key: 'supplier_name', header: 'Supplier', sortable: true },
    {
      key: 'status',
      header: 'Status',
      sortable: true,
      render: (o) => (
        <Badge variant={STATUS_VARIANT[o.status] || 'info'} dot>
          {o.status.charAt(0).toUpperCase() + o.status.slice(1)}
        </Badge>
      ),
    },
    {
      key: 'total_cost',
      header: 'Total',
      sortable: true,
      render: (o) => formatCurrency(o.total_cost),
    },
    {
      key: 'order_date',
      header: 'Date',
      sortable: true,
      render: (o) => formatDate(o.order_date),
    },
    {
      key: 'expected_delivery',
      header: 'Expected Delivery',
      sortable: true,
      render: (o) => o.expected_delivery ? formatDate(o.expected_delivery) : '—',
    },
  ]

  return (
    <ErrorBoundary>
      <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
        <div>
          <h1 style={{ fontSize: '1.5rem', fontWeight: 700, color: 'var(--text)' }}>Orders</h1>
          <p style={{ fontSize: '0.85rem', color: 'var(--text-muted)', marginTop: '2px' }}>
            {orders.length} order{orders.length !== 1 ? 's' : ''}
          </p>
        </div>

        {/* Status filter */}
        <Card padding="16px 20px">
          <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap', alignItems: 'center' }}>
            {STATUS_FILTERS.map((s) => (
              <button
                key={s}
                onClick={() => setStatusFilter(s)}
                style={{
                  padding: '6px 14px',
                  borderRadius: 'var(--radius-sm)',
                  fontSize: '0.78rem',
                  fontWeight: statusFilter === s ? 600 : 400,
                  border: statusFilter === s ? '1px solid var(--accent)' : '1px solid var(--border)',
                  backgroundColor: statusFilter === s
                    ? 'color-mix(in srgb, var(--accent) 12%, transparent)'
                    : 'var(--surface-2)',
                  color: statusFilter === s ? 'var(--accent)' : 'var(--text-muted)',
                  cursor: 'pointer',
                  textTransform: 'capitalize',
                }}
              >
                {s}
              </button>
            ))}
          </div>
        </Card>

        {error && (
          <div style={errorBannerStyle}>{error}</div>
        )}

        {isLoading ? (
          <LoadingSpinner message="Loading orders..." />
        ) : orders.length === 0 ? (
          <EmptyState
            icon={<ShoppingCart size={48} />}
            title="No orders found"
            description={statusFilter !== 'all'
              ? `No orders with status "${statusFilter}".`
              : 'Create a purchase order from the Procurement page.'}
          />
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
            <DataTable
              columns={columns}
              data={orders}
              keyExtractor={(o) => o.id}
              pageSize={15}
            />

            {/* Expanded items */}
            {orders.map((order) => (
              expandedId === order.id && order.items && order.items.length > 0 && (
                <Card key={`items-${order.id}`} title={`Order ${order.id.slice(0, 8)} — Items`}>
                  <div style={{ overflowX: 'auto' }}>
                    <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                      <thead>
                        <tr style={{ borderBottom: '1px solid var(--border)' }}>
                          <th style={thStyle}>Product</th>
                          <th style={thStyle}>Quantity</th>
                          <th style={thStyle}>Unit Price</th>
                          <th style={thStyle}>Line Total</th>
                        </tr>
                      </thead>
                      <tbody>
                        {order.items.map((item) => (
                          <tr key={item.id} style={{ borderBottom: '1px solid var(--border)' }}>
                            <td style={tdStyle}>{item.product_name}</td>
                            <td style={tdStyle}>{item.quantity}</td>
                            <td style={tdStyle}>{formatCurrency(item.unit_cost)}</td>
                            <td style={tdStyle}>{formatCurrency(item.unit_cost * item.quantity)}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </Card>
              )
            ))}
          </div>
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
}

const tdStyle: React.CSSProperties = {
  padding: '10px 14px',
  fontSize: '0.85rem',
  color: 'var(--text)',
}

const errorBannerStyle: React.CSSProperties = {
  backgroundColor: 'color-mix(in srgb, var(--danger) 12%, transparent)',
  color: 'var(--danger)',
  padding: '10px 16px',
  borderRadius: 'var(--radius-md)',
  fontSize: '0.85rem',
  border: '1px solid color-mix(in srgb, var(--danger) 25%, transparent)',
}
