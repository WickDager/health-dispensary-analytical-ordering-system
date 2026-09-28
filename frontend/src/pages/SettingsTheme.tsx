import { useState, useEffect, useCallback } from 'react'
import { useTheme } from '../hooks/useTheme'
import { useRoleAccess } from '../hooks/useRoleAccess'
import api from '../api/client'
import Card from '../components/ui/Card'
import LoadingSpinner from '../components/ui/LoadingSpinner'
import ErrorBoundary from '../components/ui/ErrorBoundary'

type ThemeMode = 'light' | 'dark' | 'system'
type Density = 'comfortable' | 'compact'
type FontSize = 'small' | 'medium' | 'large'

interface ThemePreferences {
  theme: ThemeMode
  accent: string
  density: Density
  font_size: FontSize
}

const ACCENT_COLORS = [
  { name: 'teal', hex: '#0E8C7F', cssVar: 'var(--accent)' },
  { name: 'blue', hex: '#2563EB' },
  { name: 'green', hex: '#16A34A' },
  { name: 'purple', hex: '#7C3AED' },
  { name: 'orange', hex: '#EA580C' },
  { name: 'red', hex: '#DC2626' },
  { name: 'pink', hex: '#DB2777' },
  { name: 'amber', hex: '#D97706' },
]

const DENSITY_OPTIONS: { value: Density; label: string; description: string }[] = [
  { value: 'comfortable', label: 'Comfortable', description: 'More spacing, easier reading' },
  { value: 'compact', label: 'Compact', description: 'Tighter spacing, more content visible' },
]

const FONT_SIZE_OPTIONS: { value: FontSize; label: string; sample: string }[] = [
  { value: 'small', label: 'Small', sample: '14px base' },
  { value: 'medium', label: 'Medium', sample: '16px base' },
  { value: 'large', label: 'Large', sample: '18px base' },
]

export default function SettingsTheme() {
  const { theme, setTheme } = useTheme()
  const { isAdmin } = useRoleAccess()
  const [prefs, setPrefs] = useState<ThemePreferences>({
    theme: 'system',
    accent: 'teal',
    density: 'comfortable',
    font_size: 'medium',
  })
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')
  const [isSaving, setIsSaving] = useState(false)

  const fetchPrefs = useCallback(async () => {
    setIsLoading(true)
    setError('')
    try {
      const data = await api.get<ThemePreferences>('/settings/theme/')
      if (data) setPrefs(data)
    } catch {
      setError('Failed to load theme preferences. Using local settings.')
    } finally {
      setIsLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchPrefs()
  }, [fetchPrefs])

  const updateTheme = (t: ThemeMode) => {
    setTheme(t)
    setPrefs((prev) => ({ ...prev, theme: t }))
  }

  const updateAccent = (name: string) => {
    setPrefs((prev) => ({ ...prev, accent: name }))
  }

  const updateDensity = (d: Density) => {
    setPrefs((prev) => ({ ...prev, density: d }))
  }

  const updateFontSize = (fs: FontSize) => {
    setPrefs((prev) => ({ ...prev, font_size: fs }))
  }

  const handleSave = async () => {
    setIsSaving(true)
    setError('')
    setSuccess('')
    try {
      await api.patch('/settings/theme/', prefs)
      setSuccess('Theme preferences saved successfully.')

      // Apply accent color dynamically
      const accentHex = ACCENT_COLORS.find((c) => c.name === prefs.accent)?.hex
      if (accentHex) {
        document.documentElement.style.setProperty('--accent', accentHex)
      }

      // Apply font size
      const fontSizeMap: Record<FontSize, string> = {
        small: '14px',
        medium: '16px',
        large: '18px',
      }
      document.documentElement.style.fontSize = fontSizeMap[prefs.font_size]

      // Apply density
      const densityMap: Record<Density, string> = {
        comfortable: '1.6',
        compact: '1.35',
      }
      document.body.style.lineHeight = densityMap[prefs.density]
    } catch {
      setError('Failed to save theme preferences.')
    } finally {
      setIsSaving(false)
    }
  }

  if (!isAdmin) {
    return (
      <div style={{ textAlign: 'center', padding: '40px', color: 'var(--text-muted)' }}>
        <h2 style={{ fontSize: '1.1rem', fontWeight: 600, color: 'var(--text)' }}>Access Denied</h2>
        <p style={{ fontSize: '0.85rem', marginTop: '4px' }}>Only administrators can manage settings.</p>
      </div>
    )
  }

  if (isLoading) {
    return <LoadingSpinner message="Loading theme preferences..." />
  }

  return (
    <ErrorBoundary>
      <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
        {error && <div style={errorBannerStyle}>{error}</div>}
        {success && <div style={successBannerStyle}>{success}</div>}

        {/* Theme Mode */}
        <Card title="Theme Mode">
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: '12px' }}>
            {(['light', 'dark', 'system'] as ThemeMode[]).map((mode) => (
              <button
                key={mode}
                onClick={() => updateTheme(mode)}
                style={{
                  ...modeCardStyle,
                  borderColor: prefs.theme === mode ? 'var(--accent)' : 'var(--border)',
                  backgroundColor: prefs.theme === mode
                    ? 'color-mix(in srgb, var(--accent) 8%, var(--surface))'
                    : 'var(--surface)',
                  boxShadow: prefs.theme === mode ? '0 0 0 1px var(--accent)' : 'var(--shadow-sm)',
                }}
              >
                <div
                  style={{
                    height: '64px',
                    borderRadius: 'var(--radius-md)',
                    marginBottom: '10px',
                    border: '1px solid var(--border)',
                    overflow: 'hidden',
                    display: 'flex',
                    flexDirection: 'column',
                  }}
                >
                  <div
                    style={{
                      height: '12px',
                      backgroundColor: mode === 'dark' ? '#161B22' : '#FFFFFF',
                      borderBottom: '1px solid',
                      borderColor: mode === 'dark' ? '#2A3340' : '#DDE3EA',
                    }}
                  />
                  <div
                    style={{
                      flex: 1,
                      display: 'flex',
                      backgroundColor: mode === 'dark' ? '#0E1116' : '#F7F9FB',
                    }}
                  >
                    <div
                      style={{
                        width: '30%',
                        backgroundColor: mode === 'dark' ? '#161B22' : '#FFFFFF',
                        borderRight: '1px solid',
                        borderColor: mode === 'dark' ? '#2A3340' : '#DDE3EA',
                      }}
                    />
                    <div style={{ flex: 1, padding: '6px' }}>
                      <div
                        style={{
                          height: '6px',
                          width: '60%',
                          borderRadius: '3px',
                          backgroundColor: mode === 'dark' ? '#3FB6A8' : '#0E8C7F',
                          marginBottom: '4px',
                        }}
                      />
                      <div
                        style={{
                          height: '4px',
                          width: '40%',
                          borderRadius: '2px',
                          backgroundColor: mode === 'dark' ? '#8B98A9' : '#5B6875',
                        }}
                      />
                    </div>
                  </div>
                </div>
                <span style={{ fontWeight: 600, fontSize: '0.85rem', color: 'var(--text)' }}>
                  {mode.charAt(0).toUpperCase() + mode.slice(1)}
                </span>
                <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)', marginTop: '2px' }}>
                  {mode === 'system' ? 'Follows OS' : mode === 'dark' ? 'Dark colors' : 'Light colors'}
                </span>
              </button>
            ))}
          </div>
        </Card>

        {/* Accent Color */}
        <Card title="Accent Color">
          <div style={{ display: 'flex', gap: '10px', flexWrap: 'wrap' }}>
            {ACCENT_COLORS.map((color) => (
              <button
                key={color.name}
                onClick={() => updateAccent(color.name)}
                title={color.name}
                style={{
                  width: '40px',
                  height: '40px',
                  borderRadius: '50%',
                  backgroundColor: color.hex,
                  border: prefs.accent === color.name ? '3px solid var(--text)' : '3px solid transparent',
                  cursor: 'pointer',
                  transition: 'transform 150ms ease, box-shadow 150ms ease',
                  boxShadow: prefs.accent === color.name
                    ? '0 0 0 2px var(--bg), 0 0 0 5px ' + color.hex
                    : 'none',
                  outline: 'none',
                }}
              />
            ))}
          </div>
          <div
            style={{
              marginTop: '12px',
              display: 'flex',
              alignItems: 'center',
              gap: '8px',
            }}
          >
            <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>Preview:</span>
            <span
              style={{
                padding: '4px 12px',
                borderRadius: 'var(--radius-md)',
                backgroundColor: ACCENT_COLORS.find((c) => c.name === prefs.accent)?.hex || 'var(--accent)',
                color: '#fff',
                fontSize: '0.8rem',
                fontWeight: 600,
              }}
            >
              Accent Button
            </span>
          </div>
        </Card>

        {/* Density */}
        <Card title="Density">
          <div style={{ display: 'flex', gap: '12px', flexWrap: 'wrap' }}>
            {DENSITY_OPTIONS.map((opt) => (
              <button
                key={opt.value}
                onClick={() => updateDensity(opt.value)}
                style={{
                  flex: '1 1 200px',
                  padding: '16px',
                  borderRadius: 'var(--radius-md)',
                  border: prefs.density === opt.value
                    ? '2px solid var(--accent)'
                    : '1px solid var(--border)',
                  backgroundColor: prefs.density === opt.value
                    ? 'color-mix(in srgb, var(--accent) 8%, var(--surface))'
                    : 'var(--surface)',
                  cursor: 'pointer',
                  textAlign: 'left',
                  transition: 'all 150ms ease',
                }}
              >
                <div style={{ fontWeight: 600, fontSize: '0.9rem', color: 'var(--text)' }}>{opt.label}</div>
                <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: '4px' }}>
                  {opt.description}
                </div>
                <div
                  style={{
                    marginTop: '10px',
                    padding: '8px',
                    borderRadius: 'var(--radius-sm)',
                    backgroundColor: 'var(--surface-2)',
                    border: '1px solid var(--border)',
                    lineHeight: opt.value === 'comfortable' ? '1.6' : '1.35',
                    fontSize: '0.8rem',
                    color: 'var(--text-muted)',
                  }}
                >
                  <div style={{ fontWeight: 500, color: 'var(--text)', marginBottom: '2px' }}>Sample content</div>
                  This text shows how {opt.value} density looks in practice.
                </div>
              </button>
            ))}
          </div>
        </Card>

        {/* Font Size */}
        <Card title="Font Size">
          <div style={{ display: 'flex', gap: '12px', flexWrap: 'wrap' }}>
            {FONT_SIZE_OPTIONS.map((opt) => (
              <button
                key={opt.value}
                onClick={() => updateFontSize(opt.value)}
                style={{
                  flex: '1 1 150px',
                  padding: '16px',
                  borderRadius: 'var(--radius-md)',
                  border: prefs.font_size === opt.value
                    ? '2px solid var(--accent)'
                    : '1px solid var(--border)',
                  backgroundColor: prefs.font_size === opt.value
                    ? 'color-mix(in srgb, var(--accent) 8%, var(--surface))'
                    : 'var(--surface)',
                  cursor: 'pointer',
                  textAlign: 'center',
                  transition: 'all 150ms ease',
                }}
              >
                <div style={{ fontWeight: 600, fontSize: '0.9rem', color: 'var(--text)' }}>{opt.label}</div>
                <div
                  style={{
                    marginTop: '8px',
                    fontSize: opt.value === 'small' ? '0.78rem' : opt.value === 'large' ? '1rem' : '0.88rem',
                    color: 'var(--text)',
                  }}
                >
                  {opt.sample}
                </div>
                <div
                  style={{
                    marginTop: '4px',
                    fontSize: opt.value === 'small' ? '0.65rem' : opt.value === 'large' ? '0.82rem' : '0.72rem',
                    color: 'var(--text-muted)',
                  }}
                >
                  Secondary text
                </div>
              </button>
            ))}
          </div>
        </Card>

        {/* Live Preview */}
        <Card title="Live Preview">
          <div
            style={{
              padding: '24px',
              borderRadius: 'var(--radius-md)',
              backgroundColor: 'var(--bg)',
              border: '1px solid var(--border)',
              display: 'flex',
              flexDirection: 'column',
              gap: '16px',
            }}
          >
            <div style={{ display: 'flex', gap: '12px', alignItems: 'center' }}>
              <div
                style={{
                  width: '48px',
                  height: '48px',
                  borderRadius: 'var(--radius-md)',
                  backgroundColor: ACCENT_COLORS.find((c) => c.name === prefs.accent)?.hex || 'var(--accent)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  color: '#fff',
                  fontWeight: 700,
                  fontSize: '1.2rem',
                }}
              >
                H
              </div>
              <div>
                <div style={{ fontWeight: 600, color: 'var(--text)', fontSize: '0.95rem' }}>
                  Welcome to HDAOS
                </div>
                <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
                  Health Dispensary Analytical Ordering System
                </div>
              </div>
            </div>
            <div
              style={{
                display: 'flex',
                gap: '8px',
                flexWrap: 'wrap',
              }}
            >
              <span
                style={{
                  padding: '3px 10px',
                  borderRadius: 'var(--radius-sm)',
                  backgroundColor: 'color-mix(in srgb, var(--ok) 15%, transparent)',
                  color: 'var(--ok)',
                  fontSize: '0.78rem',
                  fontWeight: 600,
                }}
              >
                Active
              </span>
              <span
                style={{
                  padding: '3px 10px',
                  borderRadius: 'var(--radius-sm)',
                  backgroundColor: 'color-mix(in srgb, var(--warn) 15%, transparent)',
                  color: 'var(--warn)',
                  fontSize: '0.78rem',
                  fontWeight: 600,
                }}
              >
                Pending
              </span>
              <span
                style={{
                  padding: '3px 10px',
                  borderRadius: 'var(--radius-sm)',
                  backgroundColor: 'color-mix(in srgb, var(--danger) 15%, transparent)',
                  color: 'var(--danger)',
                  fontSize: '0.78rem',
                  fontWeight: 600,
                }}
              >
                Expired
              </span>
            </div>
            <table style={{ width: '100%', borderCollapse: 'collapse' }}>
              <thead>
                <tr style={{ borderBottom: '1px solid var(--border)' }}>
                  <th style={{ ...previewThStyle, textAlign: 'left' }}>Item</th>
                  <th style={{ ...previewThStyle, textAlign: 'left' }}>Status</th>
                  <th style={{ ...previewThStyle, textAlign: 'right' }}>Qty</th>
                </tr>
              </thead>
              <tbody>
                <tr style={{ borderBottom: '1px solid var(--border)' }}>
                  <td style={previewTdStyle}>Paracetamol 500mg</td>
                  <td style={previewTdStyle}>
                    <span style={{ color: 'var(--ok)', fontWeight: 500 }}>In Stock</span>
                  </td>
                  <td style={{ ...previewTdStyle, textAlign: 'right' }}>1,250</td>
                </tr>
                <tr style={{ borderBottom: '1px solid var(--border)' }}>
                  <td style={previewTdStyle}>Amoxicillin 250mg</td>
                  <td style={previewTdStyle}>
                    <span style={{ color: 'var(--warn)', fontWeight: 500 }}>Low Stock</span>
                  </td>
                  <td style={{ ...previewTdStyle, textAlign: 'right' }}>42</td>
                </tr>
              </tbody>
            </table>
            <div style={{ display: 'flex', gap: '8px' }}>
              <div
                style={{
                  padding: '6px 14px',
                  borderRadius: 'var(--radius-md)',
                  backgroundColor: ACCENT_COLORS.find((c) => c.name === prefs.accent)?.hex || 'var(--accent)',
                  color: '#fff',
                  fontSize: '0.85rem',
                  fontWeight: 600,
                  cursor: 'pointer',
                }}
              >
                Primary Button
              </div>
              <div
                style={{
                  padding: '6px 14px',
                  borderRadius: 'var(--radius-md)',
                  backgroundColor: 'transparent',
                  border: '1px solid var(--border)',
                  color: 'var(--text)',
                  fontSize: '0.85rem',
                  fontWeight: 500,
                }}
              >
                Secondary
              </div>
            </div>
          </div>
        </Card>

        {/* Save Button */}
        <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
          <button
            onClick={handleSave}
            disabled={isSaving}
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '8px',
              padding: '10px 24px',
              backgroundColor: ACCENT_COLORS.find((c) => c.name === prefs.accent)?.hex || 'var(--accent)',
              color: '#fff',
              border: 'none',
              borderRadius: 'var(--radius-md)',
              fontSize: '0.9rem',
              fontWeight: 600,
              cursor: isSaving ? 'default' : 'pointer',
              opacity: isSaving ? 0.7 : 1,
              transition: 'all 150ms ease',
            }}
          >
            {isSaving ? 'Saving...' : 'Save Theme Preferences'}
          </button>
        </div>
      </div>
    </ErrorBoundary>
  )
}

const modeCardStyle: React.CSSProperties = {
  display: 'flex',
  flexDirection: 'column',
  padding: '14px',
  borderRadius: 'var(--radius-md)',
  border: '1px solid var(--border)',
  cursor: 'pointer',
  transition: 'all 150ms ease',
  textAlign: 'center',
}

const errorBannerStyle: React.CSSProperties = {
  backgroundColor: 'color-mix(in srgb, var(--danger) 12%, transparent)',
  color: 'var(--danger)',
  padding: '10px 16px',
  borderRadius: 'var(--radius-md)',
  fontSize: '0.85rem',
  border: '1px solid color-mix(in srgb, var(--danger) 25%, transparent)',
}

const successBannerStyle: React.CSSProperties = {
  backgroundColor: 'color-mix(in srgb, var(--ok) 12%, transparent)',
  color: 'var(--ok)',
  padding: '10px 16px',
  borderRadius: 'var(--radius-md)',
  fontSize: '0.85rem',
  border: '1px solid color-mix(in srgb, var(--ok) 25%, transparent)',
}

const previewThStyle: React.CSSProperties = {
  padding: '8px 12px',
  fontSize: '0.72rem',
  fontWeight: 600,
  color: 'var(--text-muted)',
  textTransform: 'uppercase',
  letterSpacing: '0.03em',
}

const previewTdStyle: React.CSSProperties = {
  padding: '8px 12px',
  fontSize: '0.82rem',
  color: 'var(--text)',
}
