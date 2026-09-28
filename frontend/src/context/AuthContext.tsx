import { createContext, useState, useEffect, useCallback, type ReactNode } from 'react'
import api from '../api/client'

export type UserRole = 'admin' | 'pharmacist' | 'logistics' | 'procurement' | 'sales' | 'viewer'

export interface User {
  id: string
  username: string
  email: string
  first_name: string
  last_name: string
  role: UserRole
  theme_preference: 'light' | 'dark' | 'system'
  is_active: boolean
}

export interface AuthState {
  user: User | null
  isLoading: boolean
  isAuthenticated: boolean
}

interface AuthContextType extends AuthState {
  login: (username: string, password: string) => Promise<void>
  logout: () => Promise<void>
  register: (data: RegisterData) => Promise<void>
  updatePreferences: (theme: string) => Promise<void>
}

export interface RegisterData {
  username: string
  email: string
  password: string
  first_name: string
  last_name: string
  role?: string
}

export const AuthContext = createContext<AuthContextType | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<AuthState>({
    user: null,
    isLoading: true,
    isAuthenticated: false,
  })

  const fetchMe = useCallback(async () => {
    try {
      const raw = await api.get<any>('/auth/me/')
      // Normalize backend UPPERCASE roles to lowercase for frontend consistency
      const user: User = {
        ...raw,
        role: raw.role?.toLowerCase() || 'viewer',
      }
      setState({ user, isLoading: false, isAuthenticated: true })
    } catch {
      setState({ user: null, isLoading: false, isAuthenticated: false })
    }
  }, [])

  // Auto-fetch on mount
  useEffect(() => {
    fetchMe()
  }, [fetchMe])

  const login = useCallback(async (username: string, password: string) => {
    await api.post('/auth/login/', { username, password })
    await fetchMe()
  }, [fetchMe])

  const logout = useCallback(async () => {
    try {
      await api.post('/auth/logout/')
    } catch {
      // Logout even if the server call fails
    }
    setState({ user: null, isLoading: false, isAuthenticated: false })
  }, [])

  const register = useCallback(async (data: RegisterData) => {
    await api.post('/auth/register/', data)
    // Don't auto-login — account may require approval
  }, [])

  const updatePreferences = useCallback(async (theme: string) => {
    await api.patch('/auth/me/preferences/', { theme_preference: theme })
    if (state.user) {
      setState((prev) => ({
        ...prev,
        user: { ...prev.user!, theme_preference: theme as User['theme_preference'] },
      }))
    }
  }, [state.user])

  return (
    <AuthContext.Provider
      value={{
        ...state,
        login,
        logout,
        register,
        updatePreferences,
      }}
    >
      {children}
    </AuthContext.Provider>
  )
}
