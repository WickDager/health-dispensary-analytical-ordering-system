import { useMemo } from 'react'
import {
  PieChart,
  Pie,
  BarChart,
  Bar,
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  Cell,
} from 'recharts'
import { useTheme } from '../../hooks/useTheme'

// Read CSS custom properties from the document
function getCSSVar(name: string, fallback: string): string {
  if (typeof window === 'undefined') return fallback
  const styles = getComputedStyle(document.documentElement)
  return styles.getPropertyValue(name).trim() || fallback
}

const DEFAULT_PALETTE = [
  '#3FB6A8', // accent
  '#4ADE80', // ok
  '#F5B34A', // warn
  '#F0616D', // danger
  '#6B8AFF', // blue
  '#C084FC', // purple
  '#FB923C', // orange
  '#38BDF8', // sky
]

function useChartPalette(): string[] {
  const { resolved } = useTheme()

  return useMemo(() => {
    if (resolved === 'dark') {
      return [
        getCSSVar('--accent', '#3FB6A8'),
        getCSSVar('--ok', '#4ADE80'),
        getCSSVar('--warn', '#F5B34A'),
        getCSSVar('--danger', '#F0616D'),
        '#6B8AFF',
        '#C084FC',
        '#FB923C',
        '#38BDF8',
      ]
    }
    return [
      getCSSVar('--accent', '#0E8C7F'),
      getCSSVar('--ok', '#1E9E54'),
      getCSSVar('--warn', '#C77D12'),
      getCSSVar('--danger', '#C8323F'),
      '#5B6FE8',
      '#9B5CF6',
      '#EA7C2A',
      '#2DAFDF',
    ]
  }, [resolved])
}

function useChartColors() {
  const { resolved } = useTheme()
  return useMemo(() => ({
    text: getCSSVar('--text', resolved === 'dark' ? '#E6EDF3' : '#1A2027'),
    textMuted: getCSSVar('--text-muted', resolved === 'dark' ? '#8B98A9' : '#5B6875'),
    border: getCSSVar('--border', resolved === 'dark' ? '#2A3340' : '#DDE3EA'),
    surface: getCSSVar('--surface', resolved === 'dark' ? '#161B22' : '#FFFFFF'),
  }), [resolved])
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
interface CommonChartProps {
  data: Record<string, any>[]
  dataKey: string
  nameKey?: string
  height?: number
  showLegend?: boolean
}

// ── ThemedPieChart ──────────────────────────────────────────

interface PieChartProps extends CommonChartProps {
  colorMap?: Record<string, string>
}

export function ThemedPieChart({
  data,
  dataKey,
  nameKey = 'name',
  height = 300,
  showLegend = true,
  colorMap,
}: PieChartProps) {
  const palette = useChartPalette()
  const colors = useChartColors()

  return (
    <ResponsiveContainer width="100%" height={height} minWidth={1} minHeight={1}>
      <PieChart>
        <Pie
          data={data}
          dataKey={dataKey}
          nameKey={nameKey}
          cx="50%"
          cy="50%"
          outerRadius={height * 0.35}
          innerRadius={height * 0.2}
          paddingAngle={2}
          stroke={colors.surface}
          strokeWidth={2}
        >
          {data.map((entry, idx) => {
            const name = String(entry[nameKey] ?? '')
            const color = colorMap?.[name] ?? palette[idx % palette.length]
            return <Cell key={idx} fill={color} />
          })}
        </Pie>
        <Tooltip
          contentStyle={{
            backgroundColor: colors.surface,
            border: `1px solid ${colors.border}`,
            borderRadius: '8px',
            fontSize: '0.8rem',
            color: colors.text,
          }}
        />
        {showLegend && (
          <Legend
            wrapperStyle={{ fontSize: '0.75rem', color: colors.textMuted }}
          />
        )}
      </PieChart>
    </ResponsiveContainer>
  )
}

// ── ThemedBarChart ──────────────────────────────────────────

interface BarChartProps extends CommonChartProps {
  bars?: { key: string; label: string; color?: string }[]
  stacked?: boolean
}

export function ThemedBarChart({
  data,
  dataKey,
  nameKey = 'name',
  height = 300,
  showLegend = true,
  bars,
  stacked = false,
}: BarChartProps) {
  const palette = useChartPalette()
  const colors = useChartColors()

  const barDefs = bars ?? [{ key: dataKey, label: dataKey }]

  return (
    <ResponsiveContainer width="100%" height={height} minWidth={1} minHeight={1}>
      <BarChart data={data}>
        <CartesianGrid strokeDasharray="3 3" stroke={colors.border} />
        <XAxis
          dataKey={nameKey}
          tick={{ fontSize: 12, fill: colors.textMuted }}
          axisLine={{ stroke: colors.border }}
          tickLine={false}
        />
        <YAxis
          tick={{ fontSize: 12, fill: colors.textMuted }}
          axisLine={{ stroke: colors.border }}
          tickLine={false}
        />
        <Tooltip
          contentStyle={{
            backgroundColor: colors.surface,
            border: `1px solid ${colors.border}`,
            borderRadius: '8px',
            fontSize: '0.8rem',
            color: colors.text,
          }}
        />
        {showLegend && (
          <Legend
            wrapperStyle={{ fontSize: '0.75rem', color: colors.textMuted }}
          />
        )}
        {barDefs.map((bar, idx) => (
          <Bar
            key={bar.key}
            dataKey={bar.key}
            name={bar.label}
            fill={bar.color ?? palette[idx % palette.length]}
            radius={[4, 4, 0, 0]}
            stackId={stacked ? 'stack' : undefined}
          />
        ))}
      </BarChart>
    </ResponsiveContainer>
  )
}

// ── ThemedLineChart ─────────────────────────────────────────

interface LineChartProps extends CommonChartProps {
  lines?: { key: string; label: string; color?: string }[]
}

export function ThemedLineChart({
  data,
  dataKey,
  nameKey = 'name',
  height = 300,
  showLegend = true,
  lines,
}: LineChartProps) {
  const palette = useChartPalette()
  const colors = useChartColors()

  const lineDefs = lines ?? [{ key: dataKey, label: dataKey }]

  return (
    <ResponsiveContainer width="100%" height={height} minWidth={1} minHeight={1}>
      <LineChart data={data}>
        <CartesianGrid strokeDasharray="3 3" stroke={colors.border} />
        <XAxis
          dataKey={nameKey}
          tick={{ fontSize: 12, fill: colors.textMuted }}
          axisLine={{ stroke: colors.border }}
          tickLine={false}
        />
        <YAxis
          tick={{ fontSize: 12, fill: colors.textMuted }}
          axisLine={{ stroke: colors.border }}
          tickLine={false}
        />
        <Tooltip
          contentStyle={{
            backgroundColor: colors.surface,
            border: `1px solid ${colors.border}`,
            borderRadius: '8px',
            fontSize: '0.8rem',
            color: colors.text,
          }}
        />
        {showLegend && (
          <Legend
            wrapperStyle={{ fontSize: '0.75rem', color: colors.textMuted }}
          />
        )}
        {lineDefs.map((line, idx) => (
          <Line
            key={line.key}
            type="monotone"
            dataKey={line.key}
            name={line.label}
            stroke={line.color ?? palette[idx % palette.length]}
            strokeWidth={2}
            dot={{ r: 3, strokeWidth: 1 }}
            activeDot={{ r: 5 }}
          />
        ))}
      </LineChart>
    </ResponsiveContainer>
  )
}
