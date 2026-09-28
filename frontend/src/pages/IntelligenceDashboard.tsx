import { useState, useEffect, useCallback } from 'react'
import {
  Brain,
  BarChart3,
  TrendingUp,
  TrendingDown,
  AlertTriangle,
  Zap,
  Activity,
  Users,
  Package,
  Truck,
  Shield,
  Play,
  RotateCw,
  Sparkles,
  CheckCircle,
  XCircle,
  Clock,
  AlertOctagon,
} from 'lucide-react'
import api from '../api/client'
import KpiCard from '../components/ui/KpiCard'
import Badge from '../components/ui/Badge'
import DataTable, { type Column } from '../components/ui/DataTable'
import { ThemedBarChart } from '../components/charts/ThemedChart'

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface KpiData {
  active_models: number
  total_predictions_30d: number
  avg_accuracy: number | null
  unresolved_anomalies: number
}

interface ModelPerf {
  model_type: string
  model_type_display: string
  version: string
  is_active: boolean
  accuracy: number | null
  total_predictions: number
  recent_predictions_30d: number
  needs_retraining: boolean
  last_trained: string | null
}

interface ForecastRow {
  id: string
  product: string
  product_name: string
  product_sku: string
  forecast_date: string
  predicted_quantity: number
  confidence_low: number
  confidence_high: number
  method: string
}

interface SupplierRow {
  id: string
  supplier: string
  supplier_name: string
  overall_score: number
  cost_score: number
  reliability_score: number
  quality_score: number
  speed_score: number
  trend: string
  analysis_json: Record<string, unknown>
  calculated_at: string
}

interface AnomalyRow {
  id: string
  anomaly_type: string
  anomaly_type_display: string
  severity: string
  subject_type: string
  subject_id: string
  title: string
  description: string
  data_snapshot: Record<string, unknown>
  resolved: boolean
  created_at: string
  resolved_by_name: string | null
}

interface ExpiryRiskRow {
  id: string
  lot: string
  lot_batch_number: string
  lot_product_name: string
  risk_level: string
  risk_score: number
  estimated_exhaustion_date: string | null
  days_of_stock_remaining: number | null
  daily_consumption_rate: number
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function formatAccuracy(val: number | null): string {
  if (val == null) return '--'
  return `${(val * 100).toFixed(1)}%`
}

function formatTrend(trend: string): { icon: React.ReactNode; color: string } {
  switch (trend) {
    case 'rising':
    case 'improving':
      return { icon: <TrendingUp size={14} />, color: 'var(--ok)' }
    case 'falling':
    case 'declining':
      return { icon: <TrendingDown size={14} />, color: 'var(--danger)' }
    default:
      return { icon: <Activity size={14} />, color: 'var(--text-muted)' }
  }
}

const severityBadge: Record<string, 'danger' | 'warn' | 'info'> = {
  critical: 'danger',
  high: 'warn',
  medium: 'info',
  low: 'info',
}

const riskLevelBadge: Record<string, 'danger' | 'warn' | 'info'> = {
  critical: 'danger',
  high: 'warn',
  medium: 'info',
  low: 'info',
}

function formatDate(iso: string | null): string {
  if (!iso) return '--'
  return new Date(iso).toLocaleDateString()
}

function formatDateTime(iso: string): string {
  return new Date(iso).toLocaleString()
}

function ScoreBar({ value, max = 100, color }: { value: number; max?: number; color?: string }) {
  const pct = Math.min(100, Math.max(0, (value / max) * 100))
  const barColor = color ?? (pct >= 70 ? 'var(--ok)' : pct >= 40 ? 'var(--warn)' : 'var(--danger)')

  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: '8px', minWidth: '120px' }}>
      <div
        style={{
          flex: 1,
          height: '8px',
          backgroundColor: 'var(--surface-2)',
          borderRadius: '4px',
          overflow: 'hidden',
        }}
      >
        <div
          style={{
            width: `${pct}%`,
            height: '100%',
            backgroundColor: barColor,
            borderRadius: '4px',
            transition: 'width 400ms ease',
          }}
        />
      </div>
      <span style={{ fontSize: '0.8rem', fontWeight: 600, color: 'var(--text)', minWidth: '40px', textAlign: 'right' }}>
        {value.toFixed(0)}
      </span>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Main Component
// ---------------------------------------------------------------------------

export default function IntelligenceDashboard() {
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [pipelineRunning, setPipelineRunning] = useState(false)

  const [kpis, setKpis] = useState<KpiData>({
    active_models: 0,
    total_predictions_30d: 0,
    avg_accuracy: null,
    unresolved_anomalies: 0,
  })
  const [modelPerf, setModelPerf] = useState<ModelPerf[]>([])
  const [forecasts, setForecasts] = useState<ForecastRow[]>([])
  const [suppliers, setSuppliers] = useState<SupplierRow[]>([])
  const [anomalies, setAnomalies] = useState<AnomalyRow[]>([])
  const [expiryRisks, setExpiryRisks] = useState<ExpiryRiskRow[]>([])
  const [insightText, setInsightText] = useState<string | null>(null)
  const [insightLoading, setInsightLoading] = useState(false)
  const [explainingAnomaly, setExplainingAnomaly] = useState<string | null>(null)
  const [anomalyExplanations, setAnomalyExplanations] = useState<Record<string, string>>({})

  // ------------------------------------------------------------------
  // Fetch all dashboard data
  // ------------------------------------------------------------------

  const fetchDashboard = useCallback(async () => {
    try {
      setError(null)

      const [perfData, forecastData, supplierData, anomalyData, expiryData] =
        await Promise.all([
          api.get<{ kpis: KpiData; models: ModelPerf[] }>(
            '/intelligence/dashboard/performance/'
          ),
          api.get<ForecastRow[]>('/intelligence/dashboard/top_forecasts/?limit=10'),
          api.get<SupplierRow[]>('/intelligence/dashboard/top_suppliers/?limit=10'),
          api.get<AnomalyRow[]>('/intelligence/dashboard/recent_anomalies/?limit=20'),
          api.get<ExpiryRiskRow[]>('/intelligence/dashboard/expiry_risks/?limit=12'),
        ])

      if (perfData.kpis) setKpis(perfData.kpis)
      if (perfData.models) setModelPerf(perfData.models)
      setForecasts(forecastData)
      setSuppliers(supplierData)
      setAnomalies(anomalyData)
      setExpiryRisks(expiryData)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load dashboard data')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchDashboard()
  }, [fetchDashboard])

  // ------------------------------------------------------------------
  // Run full pipeline
  // ------------------------------------------------------------------

  const runPipeline = async () => {
    setPipelineRunning(true)
    try {
      await api.post('/intelligence/dashboard/run_pipeline/')
      await fetchDashboard()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Pipeline execution failed')
    } finally {
      setPipelineRunning(false)
    }
  }

  // ------------------------------------------------------------------
  // LLM Insights
  // ------------------------------------------------------------------

  const fetchInsight = async (type: string) => {
    setInsightLoading(true)
    setInsightText(null)
    try {
      const res = await api.post<{ insight_type: string; result: string }>(
        '/intelligence/dashboard/insights/',
        { insight_type: type }
      )
      setInsightText(res.result)
    } catch (err) {
      setInsightText(`Error: ${err instanceof Error ? err.message : 'Insight generation failed'}`)
    } finally {
      setInsightLoading(false)
    }
  }

  // ------------------------------------------------------------------
  // Explain anomaly
  // ------------------------------------------------------------------

  const explainAnomaly = async (anomalyId: string) => {
    setExplainingAnomaly(anomalyId)
    try {
      const res = await api.post<{ anomaly_id: string; explanation: string }>(
        `/intelligence/anomalies/${anomalyId}/explain/`
      )
      setAnomalyExplanations((prev) => ({ ...prev, [anomalyId]: res.explanation }))
    } catch (err) {
      setAnomalyExplanations((prev) => ({
        ...prev,
        [anomalyId]: `Error: ${err instanceof Error ? err.message : 'Explanation failed'}`,
      }))
    } finally {
      setExplainingAnomaly(null)
    }
  }

  // ------------------------------------------------------------------
  // Resolve anomaly
  // ------------------------------------------------------------------

  const resolveAnomaly = async (anomalyId: string) => {
    try {
      await api.post(`/intelligence/anomalies/${anomalyId}/resolve/`)
      setAnomalies((prev) => prev.filter((a) => a.id !== anomalyId))
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to resolve anomaly')
    }
  }

  // ------------------------------------------------------------------
  // Table columns
  // ------------------------------------------------------------------

  const forecastColumns: Column<ForecastRow>[] = [
    {
      key: 'product_name',
      header: 'Product',
      sortable: true,
      render: (row) => (
        <div>
          <div style={{ fontWeight: 600 }}>{row.product_name}</div>
          <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>{row.product_sku}</div>
        </div>
      ),
    },
    {
      key: 'predicted_quantity',
      header: 'Forecast Qty',
      sortable: true,
      render: (row) => (
        <span style={{ fontWeight: 600 }}>{row.predicted_quantity.toLocaleString()}</span>
      ),
    },
    {
      key: 'forecast_date',
      header: 'Forecast Date',
      sortable: true,
      render: (row) => formatDate(row.forecast_date),
    },
    {
      key: 'confidence_low',
      header: 'Range',
      render: (row) => (
        <span style={{ fontSize: '0.82rem', color: 'var(--text-muted)' }}>
          {row.confidence_low} - {row.confidence_high}
        </span>
      ),
    },
    {
      key: 'method',
      header: 'Method',
      render: (row) => (
        <Badge variant="info" size="sm">{row.method}</Badge>
      ),
    },
  ]

  const supplierColumns: Column<SupplierRow>[] = [
    {
      key: 'supplier_name',
      header: 'Supplier',
      sortable: true,
      render: (row) => (
        <div>
          <div style={{ fontWeight: 600 }}>{row.supplier_name}</div>
        </div>
      ),
    },
    {
      key: 'overall_score',
      header: 'Overall',
      sortable: true,
      render: (row) => <ScoreBar value={row.overall_score} />,
    },
    {
      key: 'cost_score',
      header: 'Cost',
      sortable: true,
      render: (row) => (
        <span style={{ fontSize: '0.85rem', color: 'var(--text)' }}>
          {row.cost_score.toFixed(0)}/100
        </span>
      ),
    },
    {
      key: 'reliability_score',
      header: 'Reliability',
      sortable: true,
      render: (row) => (
        <span style={{ fontSize: '0.85rem', color: 'var(--text)' }}>
          {row.reliability_score.toFixed(0)}/100
        </span>
      ),
    },
    {
      key: 'speed_score',
      header: 'Speed',
      sortable: true,
      render: (row) => (
        <span style={{ fontSize: '0.85rem', color: 'var(--text)' }}>
          {row.speed_score.toFixed(0)}/100
        </span>
      ),
    },
    {
      key: 'trend',
      header: 'Trend',
      render: (row) => {
        const t = formatTrend(row.trend)
        return (
          <span style={{ display: 'flex', alignItems: 'center', gap: '4px', color: t.color }}>
            {t.icon}
          </span>
        )
      },
    },
  ]

  // ------------------------------------------------------------------
  // Loading state
  // ------------------------------------------------------------------

  if (loading) {
    return (
      <div style={containerStyle}>
        <div style={loadingStyle}>
          <RotateCw size={32} style={{ animation: 'spin 1s linear infinite', color: 'var(--accent)' }} />
          <p style={{ color: 'var(--text-muted)', marginTop: '12px' }}>Loading intelligence dashboard...</p>
        </div>
        <style>{`@keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }`}</style>
      </div>
    )
  }

  // ------------------------------------------------------------------
  // Render
  // ------------------------------------------------------------------

  return (
    <div style={containerStyle}>
      {/* Header */}
      <div style={headerStyle}>
        <div>
          <h1 style={titleStyle}>
            <Brain size={28} style={{ color: 'var(--accent)' }} />
            AI Intelligence
          </h1>
          <p style={{ color: 'var(--text-muted)', fontSize: '0.9rem', margin: 0 }}>
            Model performance, demand forecasts, supplier scores, and anomaly detection.
          </p>
        </div>
        <div style={{ display: 'flex', gap: '8px' }}>
          <button onClick={() => fetchInsight('dashboard_summary')} disabled={insightLoading} style={secondaryBtnStyle}>
            <Sparkles size={16} />
            {insightLoading ? 'Generating...' : 'AI Summary'}
          </button>
          <button onClick={runPipeline} disabled={pipelineRunning} style={primaryBtnStyle}>
            {pipelineRunning ? (
              <RotateCw size={16} style={{ animation: 'spin 1s linear infinite' }} />
            ) : (
              <Play size={16} />
            )}
            {pipelineRunning ? 'Running...' : 'Run Full Pipeline'}
          </button>
        </div>
      </div>

      {error && (
        <div style={errorBarStyle}>
          <AlertOctagon size={16} />
          {error}
          <button onClick={() => setError(null)} style={dismissBtnStyle}>
            <XCircle size={14} />
          </button>
        </div>
      )}

      {insightText && (
        <div style={insightBoxStyle}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '8px' }}>
            <Sparkles size={16} style={{ color: 'var(--accent)' }} />
            <strong style={{ color: 'var(--text)' }}>AI Insight</strong>
          </div>
          <p style={{ margin: 0, color: 'var(--text)', fontSize: '0.9rem', lineHeight: 1.6 }}>{insightText}</p>
          <button onClick={() => setInsightText(null)} style={{ ...dismissBtnStyle, position: 'absolute', top: '12px', right: '12px' }}>
            <XCircle size={14} />
          </button>
        </div>
      )}

      {/* KPI Row */}
      <div style={kpiGridStyle}>
        <KpiCard icon={<Brain size={22} />} label="Active Models" value={kpis.active_models} />
        <KpiCard icon={<BarChart3 size={22} />} label="Predictions (30d)" value={kpis.total_predictions_30d.toLocaleString()} />
        <KpiCard
          icon={<Zap size={22} />}
          label="Avg Accuracy"
          value={formatAccuracy(kpis.avg_accuracy)}
          trend={
            kpis.avg_accuracy != null
              ? { direction: kpis.avg_accuracy >= 0.7 ? 'up' : 'down', value: formatAccuracy(kpis.avg_accuracy) }
              : undefined
          }
        />
        <KpiCard
          icon={<AlertTriangle size={22} />}
          label="Unresolved Anomalies"
          value={kpis.unresolved_anomalies}
          trend={
            kpis.unresolved_anomalies > 0
              ? { direction: 'up', value: `${kpis.unresolved_anomalies} open` }
              : { direction: 'down', value: 'All clear' }
          }
        />
      </div>

      {/* Two-column: Model Performance + Demand Forecasts */}
      <div style={twoColGridStyle}>
        <div style={cardStyle}>
          <h3 style={cardTitleStyle}><BarChart3 size={18} />Model Performance</h3>
          {modelPerf.length > 0 ? (
            <ThemedBarChart
              data={modelPerf.map((m) => ({
                name: m.model_type_display ?? m.model_type,
                accuracy: m.accuracy != null ? +(m.accuracy * 100).toFixed(1) : 0,
              }))}
              dataKey="accuracy"
              nameKey="name"
              height={280}
              bars={[{ key: 'accuracy', label: 'Accuracy %', color: 'var(--accent)' }]}
            />
          ) : (
            <p style={{ color: 'var(--text-muted)', textAlign: 'center', padding: '40px 0' }}>
              No model performance data yet. Run the pipeline to generate results.
            </p>
          )}
        </div>

        <div style={cardStyle}>
          <h3 style={cardTitleStyle}><Package size={18} />Top Demand Forecasts</h3>
          <DataTable
            columns={forecastColumns}
            data={forecasts}
            keyExtractor={(r) => r.id}
            emptyMessage="No demand forecasts available. Run the pipeline to generate forecasts."
            pageSize={5}
          />
        </div>
      </div>

      {/* Two-column: Supplier Rankings + Expiry Risk */}
      <div style={twoColGridStyle}>
        <div style={cardStyle}>
          <h3 style={cardTitleStyle}><Truck size={18} />Supplier Rankings</h3>
          <DataTable
            columns={supplierColumns}
            data={suppliers}
            keyExtractor={(r) => r.id}
            emptyMessage="No supplier scores available. Run the pipeline to generate scores."
            pageSize={5}
          />
        </div>

        <div style={cardStyle}>
          <h3 style={cardTitleStyle}><Shield size={18} />Expiry Risk Alerts</h3>
          {expiryRisks.length > 0 ? (
            <div style={expiryGridStyle}>
              {expiryRisks.map((risk) => (
                <div key={risk.id} style={expiryCardStyle}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                    <div>
                      <div style={{ fontWeight: 600, fontSize: '0.85rem', color: 'var(--text)' }}>
                        {risk.lot_product_name || risk.lot_batch_number}
                      </div>
                      <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)', marginTop: '2px' }}>
                        Batch: {risk.lot_batch_number}
                      </div>
                    </div>
                    <Badge variant={riskLevelBadge[risk.risk_level] ?? 'info'} size="sm">
                      {risk.risk_level}
                    </Badge>
                  </div>
                  <div style={{ marginTop: '8px', display: 'flex', gap: '16px' }}>
                    <div>
                      <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>Days Stock</div>
                      <div style={{
                        fontWeight: 700,
                        fontSize: '1.1rem',
                        color: (risk.days_of_stock_remaining ?? 999) <= 30 ? 'var(--danger)' : 'var(--warn)',
                      }}>
                        {risk.days_of_stock_remaining ?? '--'}
                      </div>
                    </div>
                    <div>
                      <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>Risk Score</div>
                      <div style={{ fontWeight: 700, fontSize: '1.1rem', color: 'var(--text)' }}>
                        {risk.risk_score.toFixed(0)}/100
                      </div>
                    </div>
                    <div>
                      <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>Daily Rate</div>
                      <div style={{ fontWeight: 700, fontSize: '1.1rem', color: 'var(--text)' }}>
                        {risk.daily_consumption_rate.toFixed(1)}
                      </div>
                    </div>
                  </div>
                  {risk.estimated_exhaustion_date && (
                    <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', marginTop: '6px' }}>
                      Est. exhaustion: {formatDate(risk.estimated_exhaustion_date)}
                    </div>
                  )}
                </div>
              ))}
            </div>
          ) : (
            <p style={{ color: 'var(--text-muted)', textAlign: 'center', padding: '40px 0' }}>
              No high-risk expiry items detected.
            </p>
          )}
        </div>
      </div>

      {/* Full-width: Anomaly Feed */}
      <div style={cardStyle}>
        <h3 style={cardTitleStyle}><AlertTriangle size={18} />Anomaly Feed</h3>
        {anomalies.length > 0 ? (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
            {anomalies.map((a) => (
              <div key={a.id} style={anomalyItemStyle}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '10px', flex: 1, minWidth: 0 }}>
                  <Badge variant={severityBadge[a.severity] ?? 'info'} size="sm" dot>
                    {a.severity}
                  </Badge>
                  <div style={{ minWidth: 0 }}>
                    <div style={{ fontWeight: 600, fontSize: '0.85rem', color: 'var(--text)' }}>
                      {a.title}
                    </div>
                    <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)', marginTop: '2px' }}>
                      {a.anomaly_type_display} in {a.subject_type} · {a.description}
                    </div>
                    <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', marginTop: '2px', display: 'flex', alignItems: 'center', gap: '4px' }}>
                      <Clock size={12} />
                      {formatDateTime(a.created_at)}
                    </div>
                    {anomalyExplanations[a.id] && (
                      <div style={{
                        marginTop: '8px',
                        padding: '10px',
                        backgroundColor: 'var(--surface-2)',
                        borderRadius: 'var(--radius-md)',
                        fontSize: '0.82rem',
                        color: 'var(--text)',
                        lineHeight: 1.5,
                        border: '1px solid var(--border)',
                      }}>
                        <Sparkles size={14} style={{ color: 'var(--accent)', marginRight: '6px', verticalAlign: 'middle' }} />
                        {anomalyExplanations[a.id]}
                      </div>
                    )}
                  </div>
                </div>
                <div style={{ display: 'flex', gap: '6px', flexShrink: 0 }}>
                  <button
                    onClick={() => explainAnomaly(a.id)}
                    disabled={explainingAnomaly === a.id}
                    style={smallSecondaryBtnStyle}
                    title="Explain with AI"
                  >
                    {explainingAnomaly === a.id ? (
                      <RotateCw size={14} style={{ animation: 'spin 1s linear infinite' }} />
                    ) : (
                      <Sparkles size={14} />
                    )}
                    AI
                  </button>
                  <button onClick={() => resolveAnomaly(a.id)} style={smallPrimaryBtnStyle} title="Resolve">
                    <CheckCircle size={14} />
                    Resolve
                  </button>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <p style={{ color: 'var(--text-muted)', textAlign: 'center', padding: '40px 0' }}>
            No unresolved anomalies. All systems operating normally.
          </p>
        )}
      </div>

      <style>{`@keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }`}</style>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Styles
// ---------------------------------------------------------------------------

const containerStyle: React.CSSProperties = {
  padding: '24px',
  maxWidth: '1440px',
  margin: '0 auto',
  display: 'flex',
  flexDirection: 'column',
  gap: '20px',
}

const loadingStyle: React.CSSProperties = {
  display: 'flex',
  flexDirection: 'column',
  alignItems: 'center',
  justifyContent: 'center',
  minHeight: '400px',
}

const headerStyle: React.CSSProperties = {
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'space-between',
  flexWrap: 'wrap',
  gap: '12px',
}

const titleStyle: React.CSSProperties = {
  fontSize: '1.5rem',
  fontWeight: 700,
  color: 'var(--text)',
  margin: 0,
  display: 'flex',
  alignItems: 'center',
  gap: '10px',
}

const kpiGridStyle: React.CSSProperties = {
  display: 'grid',
  gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))',
  gap: '16px',
}

const twoColGridStyle: React.CSSProperties = {
  display: 'grid',
  gridTemplateColumns: 'repeat(auto-fit, minmax(480px, 1fr))',
  gap: '20px',
}

const cardStyle: React.CSSProperties = {
  backgroundColor: 'var(--surface)',
  border: '1px solid var(--border)',
  borderRadius: 'var(--radius-lg)',
  padding: '20px',
  overflow: 'hidden',
}

const cardTitleStyle: React.CSSProperties = {
  fontSize: '1rem',
  fontWeight: 600,
  color: 'var(--text)',
  margin: '0 0 16px 0',
  display: 'flex',
  alignItems: 'center',
  gap: '8px',
}

const primaryBtnStyle: React.CSSProperties = {
  display: 'inline-flex',
  alignItems: 'center',
  gap: '6px',
  padding: '10px 20px',
  backgroundColor: 'var(--accent)',
  color: '#fff',
  border: 'none',
  borderRadius: 'var(--radius-md)',
  fontSize: '0.85rem',
  fontWeight: 600,
  cursor: 'pointer',
}

const secondaryBtnStyle: React.CSSProperties = {
  display: 'inline-flex',
  alignItems: 'center',
  gap: '6px',
  padding: '10px 20px',
  backgroundColor: 'transparent',
  color: 'var(--accent)',
  border: '1px solid var(--accent)',
  borderRadius: 'var(--radius-md)',
  fontSize: '0.85rem',
  fontWeight: 600,
  cursor: 'pointer',
}

const smallPrimaryBtnStyle: React.CSSProperties = {
  display: 'inline-flex',
  alignItems: 'center',
  gap: '4px',
  padding: '5px 10px',
  backgroundColor: 'var(--ok)',
  color: '#fff',
  border: 'none',
  borderRadius: 'var(--radius-sm)',
  fontSize: '0.75rem',
  fontWeight: 600,
  cursor: 'pointer',
}

const smallSecondaryBtnStyle: React.CSSProperties = {
  display: 'inline-flex',
  alignItems: 'center',
  gap: '4px',
  padding: '5px 10px',
  backgroundColor: 'transparent',
  color: 'var(--accent)',
  border: '1px solid var(--accent)',
  borderRadius: 'var(--radius-sm)',
  fontSize: '0.75rem',
  fontWeight: 600,
  cursor: 'pointer',
}

const errorBarStyle: React.CSSProperties = {
  display: 'flex',
  alignItems: 'center',
  gap: '8px',
  padding: '12px 16px',
  backgroundColor: 'color-mix(in srgb, var(--danger) 12%, transparent)',
  border: '1px solid var(--danger)',
  borderRadius: 'var(--radius-md)',
  color: 'var(--danger)',
  fontSize: '0.85rem',
}

const dismissBtnStyle: React.CSSProperties = {
  background: 'none',
  border: 'none',
  color: 'inherit',
  cursor: 'pointer',
  padding: '2px',
  display: 'flex',
  alignItems: 'center',
  marginLeft: 'auto',
}

const insightBoxStyle: React.CSSProperties = {
  position: 'relative',
  padding: '16px',
  backgroundColor: 'color-mix(in srgb, var(--accent) 8%, transparent)',
  border: '1px solid var(--accent)',
  borderRadius: 'var(--radius-md)',
  fontSize: '0.9rem',
}

const expiryGridStyle: React.CSSProperties = {
  display: 'grid',
  gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))',
  gap: '10px',
  maxHeight: '360px',
  overflowY: 'auto',
}

const expiryCardStyle: React.CSSProperties = {
  padding: '12px',
  backgroundColor: 'var(--surface-2)',
  borderRadius: 'var(--radius-md)',
  border: '1px solid var(--border)',
}

const anomalyItemStyle: React.CSSProperties = {
  display: 'flex',
  alignItems: 'flex-start',
  justifyContent: 'space-between',
  gap: '12px',
  padding: '12px',
  backgroundColor: 'var(--surface-2)',
  borderRadius: 'var(--radius-md)',
  border: '1px solid var(--border)',
  flexWrap: 'wrap',
}
