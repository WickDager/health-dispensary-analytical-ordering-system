import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import {
  Package,
  AlertTriangle,
  XCircle,
  Clock,
  CheckCheck,
  DollarSign,
} from 'lucide-react'
import api, { extractResults, extractCount, type PaginatedResponse } from '../api/client'
import KpiCard from '../components/ui/KpiCard'
import Card from '../components/ui/Card'
import LoadingSpinner from '../components/ui/LoadingSpinner'
import { ThemedPieChart, ThemedBarChart } from '../components/charts/ThemedChart'
import { formatCurrency } from '../lib/utils'

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------
interface Product {
  id: string
  stock_status: 'HEALTHY' | 'LOW' | 'CRITICAL' | 'STOCKOUT'
}

interface Lot {
  id: string
  expiry_date: string
  is_locked: boolean
}

interface DashboardSummary {
  total_products: number
  healthy_products: number
  low_stock_products: number
  critical_stock_products: number
  stockout_products: number
  expiring_30d: number
  expiring_60d: number
  expiring_90d: number
  pending_approvals: number
  total_contacts: number
  pipeline_value: number
}

interface DashboardStats {
  total_products: number
  healthy_products: number
  low_stock_products: number
  critical_stock_products: number
  stockout_products: number
  expiring_30d: number
  pending_approvals: number
  pipeline_value: number
  total_contacts: number
}

interface ExpiryBucket {
  name: string
  within_30d: number
  within_60d: number
  within_90d: number
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------
function countExpiringWithinDays(lots: Lot[], days: number): number {
  const now = Date.now()
  const cutoff = now + days * 24 * 60 * 60 * 1000
  return lots.filter((l) => {
    if (l.is_locked) return false
    const exp = new Date(l.expiry_date).getTime()
    return exp > now && exp <= cutoff
  }).length
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------
export default function Dashboard() {
  const [stats, setStats] = useState<DashboardStats | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    let cancelled = false

    async function fetchData() {
      setError('')

      // Try the dedicated summary endpoint first
      try {
        const summary = await api.get<DashboardSummary>('/dashboard/summary/')
        if (!cancelled && summary) {
          setStats({
            total_products: summary.total_products ?? 0,
            healthy_products: summary.healthy_products ?? 0,
            low_stock_products: summary.low_stock_products ?? 0,
            critical_stock_products: summary.critical_stock_products ?? 0,
            stockout_products: summary.stockout_products ?? 0,
            expiring_30d: summary.expiring_30d ?? 0,
            pending_approvals: summary.pending_approvals ?? 0,
            pipeline_value: summary.pipeline_value ?? 0,
            total_contacts: summary.total_contacts ?? 0,
          })
          setIsLoading(false)
          return
        }
      } catch {
        // Fall through to manual aggregation
      }

      // -- Fallback: fetch individual endpoints and compute stats -----------------
      try {
        const results = await Promise.allSettled([
          api.get<PaginatedResponse<Product>>('/products/'),           // products
          api.get<PaginatedResponse<Lot>>('/lots/'),                   // lots
          api.get<PaginatedResponse<{ id: string }>>('/crm/contacts/'), // contacts
          api.get<PaginatedResponse<{ id: string }>>('/approvals/?status=PENDING'), // approvals
        ])

        // Products
        let products: Product[] = []
        let totalProducts = 0
        if (results[0].status === 'fulfilled') {
          products = extractResults<Product>(results[0].value)
          totalProducts = extractCount<Product>(results[0].value)
        }

        // Lots (for expiry)
        let lots: Lot[] = []
        if (results[1].status === 'fulfilled') {
          lots = extractResults<Lot>(results[1].value)
        }

        // Contacts
        let contactCount = 0
        if (results[2].status === 'fulfilled') {
          contactCount = extractCount<{ id: string }>(results[2].value)
        }

        // Approvals
        let pendingApprovals = 0
        if (results[3].status === 'fulfilled') {
          pendingApprovals = extractCount<{ id: string }>(results[3].value)
        }

        if (!cancelled) {
          setStats({
            total_products: totalProducts,
            healthy_products: products.filter((p) => p.stock_status === 'HEALTHY').length,
            low_stock_products: products.filter((p) => p.stock_status === 'LOW').length,
            critical_stock_products: products.filter((p) => p.stock_status === 'CRITICAL').length,
            stockout_products: products.filter((p) => p.stock_status === 'STOCKOUT').length,
            expiring_30d: countExpiringWithinDays(lots, 30),
            pending_approvals: pendingApprovals,
            pipeline_value: 0, // Requires CRM opportunities endpoint with aggregation
            total_contacts: contactCount,
          })
        }
      } catch {
        if (!cancelled) setError('Failed to load dashboard data.')
      } finally {
        if (!cancelled) setIsLoading(false)
      }
    }

    fetchData()
    return () => { cancelled = true }
  }, [])

  // -------------------------------------------------------------------
  // Loading
  // -------------------------------------------------------------------
  if (isLoading) {
    return <LoadingSpinner message="Loading dashboard..." />
  }

  // -------------------------------------------------------------------
  // Display stats (real or zero-fallback)
  // -------------------------------------------------------------------
  const displayStats: DashboardStats = stats ?? {
    total_products: 0,
    healthy_products: 0,
    low_stock_products: 0,
    critical_stock_products: 0,
    stockout_products: 0,
    expiring_30d: 0,
    pending_approvals: 0,
    pipeline_value: 0,
    total_contacts: 0,
  }

  // Pie chart: stock status distribution
  const pieData = [
    { name: 'Healthy', count: displayStats.healthy_products },
    { name: 'Low', count: displayStats.low_stock_products },
    { name: 'Critical', count: displayStats.critical_stock_products },
    { name: 'Stockout', count: displayStats.stockout_products },
  ].filter((d) => d.count > 0)

  // Bar chart: estimated expiry buckets (placeholder when no dedicated endpoint)
  const barData: ExpiryBucket[] = [
    { name: 'Expiry', within_30d: displayStats.expiring_30d, within_60d: 0, within_90d: 0 },
  ]

  // -------------------------------------------------------------------
  // Render
  // -------------------------------------------------------------------
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      {/* Page Header */}
      <div>
        <h1 style={{ fontSize: '1.5rem', fontWeight: 700, color: 'var(--text)' }}>
          Dashboard
        </h1>
        <p style={{ fontSize: '0.85rem', color: 'var(--text-muted)', marginTop: '2px' }}>
          Overview of your pharmacy operations
        </p>
      </div>

      {error && (
        <div
          style={{
            backgroundColor: 'color-mix(in srgb, var(--warn) 12%, transparent)',
            color: 'var(--warn)',
            padding: '10px 16px',
            borderRadius: 'var(--radius-md)',
            fontSize: '0.85rem',
            border: '1px solid color-mix(in srgb, var(--warn) 25%, transparent)',
          }}
        >
          {error} — showing available data.
        </div>
      )}

      {/* KPI Grid */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fill, minmax(220px, 1fr))',
          gap: '16px',
        }}
      >
        <KpiCard
          icon={<Package size={22} />}
          label="Total Products"
          value={displayStats.total_products}
          linkTo="/inventory"
        />
        <KpiCard
          icon={<Package size={22} />}
          label="Healthy Products"
          value={displayStats.healthy_products}
          linkTo="/inventory"
        />
        <KpiCard
          icon={<AlertTriangle size={22} />}
          label="Low Stock"
          value={displayStats.low_stock_products}
          linkTo="/inventory?stock_status=LOW"
        />
        <KpiCard
          icon={<XCircle size={22} />}
          label="Critical / Stockout"
          value={`${displayStats.critical_stock_products} / ${displayStats.stockout_products}`}
          linkTo="/inventory?stock_status=CRITICAL"
        />
        <KpiCard
          icon={<Clock size={22} />}
          label="Expiring 30 Days"
          value={displayStats.expiring_30d}
          linkTo="/lots"
        />
        <KpiCard
          icon={<CheckCheck size={22} />}
          label="Pending Approvals"
          value={displayStats.pending_approvals}
          linkTo="/approvals"
        />
        <KpiCard
          icon={<DollarSign size={22} />}
          label="Pipeline Value"
          value={displayStats.pipeline_value > 0 ? formatCurrency(displayStats.pipeline_value) : '—'}
          linkTo="/crm/pipeline"
        />
      </div>

      {/* Charts Row */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(400px, 1fr))',
          gap: '16px',
        }}
      >
        <Card title="Product Distribution by Stock Status">
          {pieData.length > 0 ? (
            <ThemedPieChart
              data={pieData}
              dataKey="count"
              nameKey="name"
              height={320}
            />
          ) : (
            <div
              style={{
                padding: '40px',
                textAlign: 'center',
                color: 'var(--text-muted)',
                fontSize: '0.85rem',
              }}
            >
              No product data available.
            </div>
          )}
        </Card>

        <Card title="Expiry Overview (30 Days)">
          <ThemedBarChart
            data={barData}
            dataKey="within_30d"
            nameKey="name"
            height={320}
            bars={[
              { key: 'within_30d', label: 'Within 30 Days' },
              { key: 'within_60d', label: '30-60 Days' },
              { key: 'within_90d', label: '60-90 Days' },
            ]}
          />
        </Card>
      </div>

      {/* Quick Actions */}
      <Card title="Quick Actions">
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '12px' }}>
          <QuickActionButton to="/inventory" label="View Inventory" />
          <QuickActionButton to="/dispense" label="Dispense" />
          <QuickActionButton to="/ingest" label="AI Ingest" />
          <QuickActionButton to="/orders" label="Create Order" />
          <QuickActionButton to="/lots" label="Lot Management" />
          <QuickActionButton to="/crm/contacts" label="CRM Contacts" />
        </div>
      </Card>
    </div>
  )
}

// ---------------------------------------------------------------------------
// QuickAction button
// ---------------------------------------------------------------------------
function QuickActionButton({ to, label }: { to: string; label: string }) {
  return (
    <Link
      to={to}
      style={{
        display: 'inline-block',
        padding: '8px 16px',
        backgroundColor: 'color-mix(in srgb, var(--accent) 10%, transparent)',
        color: 'var(--accent)',
        borderRadius: 'var(--radius-md)',
        fontSize: '0.85rem',
        fontWeight: 500,
        textDecoration: 'none',
        transition: 'background-color 150ms ease',
        border: '1px solid color-mix(in srgb, var(--accent) 20%, transparent)',
      }}
      onMouseEnter={(e) => {
        ;(e.currentTarget as HTMLElement).style.backgroundColor =
          'color-mix(in srgb, var(--accent) 18%, transparent)'
      }}
      onMouseLeave={(e) => {
        ;(e.currentTarget as HTMLElement).style.backgroundColor =
          'color-mix(in srgb, var(--accent) 10%, transparent)'
      }}
    >
      {label}
    </Link>
  )
}
