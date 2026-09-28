import { useState, useEffect, useCallback } from 'react'
import { Boxes, Search } from 'lucide-react'
import api, { extractResults } from '../api/client'
import { formatDate, cn } from '../lib/utils'
import Card from '../components/ui/Card'
import Badge from '../components/ui/Badge'
import DataTable, { type Column } from '../components/ui/DataTable'
import EmptyState from '../components/ui/EmptyState'
import LoadingSpinner from '../components/ui/LoadingSpinner'
import ErrorBoundary from '../components/ui/ErrorBoundary'

// Matches apps/lots/serializers.py LotSerializer exactly.
interface Lot {
  id: string
  product: string
  product_name: string
  batch_number: string
  manufacture_date: string | null
  expiry_date: string
  quantity: number
  is_locked: boolean
  days_to_expiry: number | null
  expiry_tier: 'OK' | 'INFO' | 'WARN' | 'CRITICAL' | 'EXPIRED'
  created_at: string
}

type BadgeVariant = 'ok' | 'warn' | 'danger'

function tierVariant(tier: string): BadgeVariant {
  if (tier === 'EXPIRED' || tier === 'CRITICAL') return 'danger'
  if (tier === 'WARN') return 'warn'
  return 'ok'
}

function getDaysBadge(lot: Lot): { variant: BadgeVariant; label: string } {
  if (lot.days_to_expiry === null) return { variant: 'ok', label: '—' }
  if (lot.days_to_expiry < 0) return { variant: 'danger', label: 'Expired' }
  return { variant: tierVariant(lot.expiry_tier), label: `${lot.days_to_expiry}d` }
}

function getRowBackground(tier: string, isLocked: boolean): string {
  if (isLocked || tier === 'EXPIRED' || tier === 'CRITICAL') return 'color-mix(in srgb, var(--danger) 6%, transparent)'
  if (tier === 'WARN') return 'color-mix(in srgb, var(--warn) 6%, transparent)'
  return 'transparent'
}

export default function LotsLedger() {
  const [lots, setLots] = useState<Lot[]>([])
  const [products, setProducts] = useState<{ id: string; name: string }[]>([])
  const [selectedProduct, setSelectedProduct] = useState<string>('')
  const [search, setSearch] = useState('')
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState('')

  const fetchLots = useCallback(async () => {
    setIsLoading(true)
    setError('')
    try {
      const params = new URLSearchParams()
      if (selectedProduct) params.set('product', selectedProduct)
      if (search.trim()) params.set('search', search.trim())
      const qs = params.toString()
      const data = await api.get<Lot[]>(`/lots/${qs ? `?${qs}` : ''}`)
      setLots(extractResults(data))
    } catch {
      setError('Failed to load lots.')
      setLots([])
    } finally {
      setIsLoading(false)
    }
  }, [selectedProduct, search])

  useEffect(() => {
    fetchLots()
  }, [fetchLots])

  useEffect(() => {
    api.get<{ id: string; name: string }[]>('/products/')
      .then((d) => setProducts(extractResults(d)))
      .catch(() => {})
  }, [])

  // FEFO: the unlocked lot with the earliest expiry (positive days) comes first.
  const fefoCandidates = lots
    .filter((l) => !l.is_locked && l.days_to_expiry !== null && l.days_to_expiry >= 0)
    .sort((a, b) => (a.days_to_expiry ?? Infinity) - (b.days_to_expiry ?? Infinity))
  const fefoIds = new Set(fefoCandidates.length > 0 ? [fefoCandidates[0].id] : [])

  const columns: Column<Lot>[] = [
    { key: 'product_name', header: 'Product', sortable: true },
    { key: 'batch_number', header: 'Batch #', sortable: true },
    {
      key: 'manufacture_date',
      header: 'Mfg Date',
      sortable: true,
      render: (l) => l.manufacture_date ? formatDate(l.manufacture_date) : '—',
    },
    {
      key: 'expiry_date',
      header: 'Expiry Date',
      sortable: true,
      render: (l) => formatDate(l.expiry_date),
    },
    { key: 'quantity', header: 'Qty', sortable: true },
    {
      key: 'days_to_expiry',
      header: 'Days to Expiry',
      sortable: true,
      render: (l) => {
        const b = getDaysBadge(l)
        return <Badge variant={b.variant} dot>{b.label}</Badge>
      },
    },
    {
      key: 'expiry_tier',
      header: 'Expiry Tier',
      sortable: true,
      render: (l) => (
        <Badge variant={tierVariant(l.expiry_tier)} dot>{l.expiry_tier}</Badge>
      ),
    },
    {
      key: 'is_locked',
      header: 'Locked',
      render: (l) =>
        l.is_locked ? <Badge variant="danger" dot>Locked</Badge> : <Badge variant="ok" dot>Open</Badge>,
    },
  ]

  return (
    <ErrorBoundary>
      <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
        <div>
          <h1 style={{ fontSize: '1.5rem', fontWeight: 700, color: 'var(--text)' }}>Lots Ledger</h1>
          <p style={{ fontSize: '0.85rem', color: 'var(--text-muted)', marginTop: '2px' }}>
            FEFO-based lot management with expiry tracking
          </p>
        </div>

        {/* Filters */}
        <Card padding="16px 20px">
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '12px', alignItems: 'center' }}>
            <div style={{ position: 'relative', flex: '1 1 250px' }}>
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
                placeholder="Search by batch or product..."
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
                onFocus={(e) => { e.currentTarget.style.borderColor = 'var(--accent)' }}
                onBlur={(e) => { e.currentTarget.style.borderColor = 'var(--border)' }}
              />
            </div>
            <select
              value={selectedProduct}
              onChange={(e) => setSelectedProduct(e.target.value)}
              style={{
                padding: '8px 12px',
                backgroundColor: 'var(--surface-2)',
                border: '1px solid var(--border)',
                borderRadius: 'var(--radius-md)',
                color: 'var(--text)',
                fontSize: '0.85rem',
                outline: 'none',
                minWidth: '200px',
              }}
            >
              <option value="">All Products</option>
              {products.map((p) => (
                <option key={p.id} value={p.id}>{p.name}</option>
              ))}
            </select>
          </div>
        </Card>

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

        {isLoading ? (
          <LoadingSpinner message="Loading lots..." />
        ) : lots.length === 0 ? (
          <EmptyState
            icon={<Boxes size={48} />}
            title="No lots found"
            description={search || selectedProduct
              ? 'Try adjusting your search or product filter.'
              : 'No lot data available.'}
          />
        ) : (
          <div
            style={{
              backgroundColor: 'var(--surface)',
              border: '1px solid var(--border)',
              borderRadius: 'var(--radius-lg)',
              overflow: 'hidden',
            }}
          >
            <div style={{ overflowX: 'auto' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                <thead>
                  <tr style={{ borderBottom: '1px solid var(--border)' }}>
                    {columns.map((col) => (
                      <th key={col.key} style={{
                        padding: '10px 16px',
                        textAlign: 'left',
                        fontSize: '0.75rem',
                        fontWeight: 600,
                        color: 'var(--text-muted)',
                        textTransform: 'uppercase',
                        letterSpacing: '0.03em',
                        whiteSpace: 'nowrap',
                      }}>
                        {col.header}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {lots.map((lot) => (
                    <tr
                      key={lot.id}
                      style={{
                        borderBottom: '1px solid var(--border)',
                        backgroundColor: getRowBackground(lot.expiry_tier, lot.is_locked),
                        outline: fefoIds.has(lot.id) ? '2px solid var(--accent)' : 'none',
                        outlineOffset: '-2px',
                      }}
                    >
                      {columns.map((col) => (
                        <td key={col.key} style={{
                          padding: '10px 16px',
                          fontSize: '0.85rem',
                          color: 'var(--text)',
                          whiteSpace: 'nowrap',
                        }}>
                          {col.render
                            ? col.render(lot)
                            : String((lot as unknown as Record<string, unknown>)[col.key] ?? '')}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {/* Legend */}
            <div style={{
              display: 'flex',
              gap: '16px',
              padding: '10px 16px',
              borderTop: '1px solid var(--border)',
              fontSize: '0.75rem',
              color: 'var(--text-muted)',
              flexWrap: 'wrap',
            }}>
              <LegendItem color="var(--ok)" label="OK / Info (≤180 days)" />
              <LegendItem color="var(--warn)" label="Warn (≤90 days)" />
              <LegendItem color="var(--danger)" label="Critical (≤30 days) / Expired" />
              <LegendItem color="var(--accent)" label="Outline = FEFO first" />
            </div>
          </div>
        )}
      </div>
    </ErrorBoundary>
  )
}

function LegendItem({ color, label }: { color: string; label: string }) {
  return (
    <span style={{ display: 'inline-flex', alignItems: 'center', gap: '6px' }}>
      <span style={{ width: '10px', height: '10px', borderRadius: '2px', backgroundColor: color, display: 'inline-block' }} />
      {label}
    </span>
  )
}
