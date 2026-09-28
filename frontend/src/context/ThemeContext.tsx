import { createContext, useState, useEffect, useCallback, type ReactNode } from 'react'

export type Theme = 'light' | 'dark' | 'system'
type ResolvedTheme = 'light' | 'dark'

interface ThemeContextType {
  theme: Theme
  resolved: ResolvedTheme
  setTheme: (t: Theme) => void
}

export const ThemeContext = createContext<ThemeContextType | null>(null)

const STORAGE_KEY = 'hdaos_theme'

function getStoredTheme(): Theme {
  try {
    const stored = localStorage.getItem(STORAGE_KEY)
    if (stored === 'light' || stored === 'dark' || stored === 'system') {
      return stored
    }
  } catch {
    // localStorage unavailable
  }
  return 'system'
}

function getSystemPreference(): ResolvedTheme {
  if (window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches) {
    return 'dark'
  }
  return 'light'
}

function applyTheme(theme: Theme, resolved: ResolvedTheme) {
  document.documentElement.setAttribute('data-theme', theme)
  // Also set a resolved attribute for CSS that checks the actual mode
  document.documentElement.setAttribute('data-resolved-theme', resolved)
}

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [theme, setThemeState] = useState<Theme>(getStoredTheme)
  const [resolved, setResolved] = useState<ResolvedTheme>(() => {
    const stored = getStoredTheme()
    return stored === 'system' ? getSystemPreference() : stored
  })

  // Listen for system theme changes
  useEffect(() => {
    const mq = window.matchMedia('(prefers-color-scheme: dark)')
    const handler = (e: MediaQueryListEvent) => {
      if (theme === 'system') {
        const newResolved: ResolvedTheme = e.matches ? 'dark' : 'light'
        setResolved(newResolved)
        applyTheme('system', newResolved)
      }
    }
    mq.addEventListener('change', handler)
    return () => mq.removeEventListener('change', handler)
  }, [theme])

  const setTheme = useCallback((t: Theme) => {
    setThemeState(t)
    try {
      localStorage.setItem(STORAGE_KEY, t)
    } catch {
      // localStorage unavailable
    }
    const newResolved: ResolvedTheme = t === 'system' ? getSystemPreference() : t
    setResolved(newResolved)
    applyTheme(t, newResolved)
  }, [])

  // Apply on mount
  useEffect(() => {
    applyTheme(theme, resolved)
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <ThemeContext.Provider value={{ theme, resolved, setTheme }}>
      {children}
    </ThemeContext.Provider>
  )
}
