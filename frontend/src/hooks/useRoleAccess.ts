import { useMemo } from 'react'
import { useAuth } from './useAuth'

export type Role = 'admin' | 'pharmacist' | 'logistics' | 'procurement' | 'sales' | 'viewer'

const ROLE_HIERARCHY: Record<Role, number> = {
  admin: 100,
  pharmacist: 80,
  logistics: 60,
  procurement: 50,
  sales: 40,
  viewer: 10,
}

export function useRoleAccess() {
  const { user } = useAuth()

  return useMemo(() => {
    const role = (user?.role as Role) || null
    const level = role ? ROLE_HIERARCHY[role] : 0

    return {
      isAdmin: role === 'admin',
      isPharmacist: role === 'pharmacist' || role === 'admin',
      isLogistics: level >= ROLE_HIERARCHY['logistics'],
      isProcurement: level >= ROLE_HIERARCHY['procurement'],
      isSales: level >= ROLE_HIERARCHY['sales'],
      canAccess: (roles: Role[]) => {
        if (!role) return false
        return roles.includes(role)
      },
      role,
    }
  }, [user])
}
