import { useState, useEffect } from 'react'
import { NavLink, useLocation } from 'react-router-dom'
import { useRoleAccess } from '../../hooks/useRoleAccess'
import { cn } from '../../lib/utils'
import {
  LayoutDashboard,
  Package,
  Syringe,
  BarChart3,
  Boxes,
  FileText,
  Truck,
  ClipboardList,
  ShoppingCart,
  Users,
  Building2,
  Target,
  PhoneCall,
  Megaphone,
  CheckCheck,
  Settings,
  Brain,
  Bell,
  ChevronLeft,
  ChevronRight,
} from 'lucide-react'
import type { Role } from '../../hooks/useRoleAccess'

const SITE_NAME_KEY = 'hdaos_site_name'
const DEFAULT_SITE_NAME = 'HDAOS'

interface NavCluster {
  label: string
  roles: Role[]
  items: { to: string; label: string; icon: React.ReactNode; end?: boolean }[]
}

function getClusters(isAdmin: boolean, isPharmacist: boolean, isLogistics: boolean, isProcurement: boolean, isSales: boolean): NavCluster[] {
  const clusters: NavCluster[] = [
    {
      label: 'Operations',
      roles: ['admin', 'pharmacist', 'logistics'] as Role[],
      items: [
        { to: '/dashboard', label: 'Dashboard', icon: <LayoutDashboard size={20} />, end: true },
        { to: '/inventory', label: 'Inventory', icon: <Package size={20} /> },
        { to: '/dispense', label: 'Dispense', icon: <Syringe size={20} /> },
        { to: '/lots', label: 'Lots', icon: <Boxes size={20} /> },
        { to: '/ingest', label: 'AI Ingest', icon: <FileText size={20} /> },
        { to: '/intelligence', label: 'AI Intelligence', icon: <Brain size={20} /> },
      ],
    },
    {
      label: 'Procurement',
      roles: ['admin', 'pharmacist', 'logistics', 'procurement'] as Role[],
      items: [
        { to: '/suppliers', label: 'Suppliers', icon: <Truck size={20} /> },
        { to: '/procurement', label: 'Procurement', icon: <ClipboardList size={20} /> },
        { to: '/orders', label: 'Orders', icon: <ShoppingCart size={20} /> },
      ],
    },
    {
      label: 'CRM',
      roles: ['admin', 'pharmacist', 'sales'] as Role[],
      items: [
        { to: '/crm/contacts', label: 'Contacts', icon: <Users size={20} /> },
        { to: '/crm/accounts', label: 'Accounts', icon: <Building2 size={20} /> },
        { to: '/crm/leads', label: 'Leads', icon: <Target size={20} /> },
        { to: '/crm/pipeline', label: 'Pipeline', icon: <PhoneCall size={20} /> },
        { to: '/crm/activities', label: 'Activities', icon: <ClipboardList size={20} /> },
        { to: '/crm/campaigns', label: 'Campaigns', icon: <Megaphone size={20} /> },
      ],
    },
    {
      label: 'Administration',
      roles: ['admin', 'pharmacist'] as Role[],
      items: [
        { to: '/approvals', label: 'Approvals', icon: <CheckCheck size={20} /> },
        { to: '/settings/providers', label: 'Settings', icon: <Settings size={20} /> },
        { to: '/notifications', label: 'Notifications', icon: <Bell size={20} /> },
      ],
    },
  ]

  const roleLevels: Record<Role, number> = {
    admin: 100,
    pharmacist: 80,
    logistics: 60,
    procurement: 50,
    sales: 40,
    viewer: 10,
  }

  return clusters.filter((cluster) => {
    return cluster.roles.some((r) => {
      switch (r) {
        case 'admin': return isAdmin
        case 'pharmacist': return isPharmacist
        case 'logistics': return isLogistics
        case 'procurement': return isProcurement
        case 'sales': return isSales
        default: return false
      }
    })
  })
}

interface SidebarProps {
  collapsed: boolean
  onToggle: () => void
}

export default function Sidebar({ collapsed, onToggle }: SidebarProps) {
  const { isAdmin, isPharmacist, isLogistics, isProcurement, isSales } = useRoleAccess()
  const location = useLocation()
  const [siteName, setSiteName] = useState(() => {
    try {
      return localStorage.getItem(SITE_NAME_KEY) || DEFAULT_SITE_NAME
    } catch {
      return DEFAULT_SITE_NAME
    }
  })
  const [editing, setEditing] = useState(false)
  const [editValue, setEditValue] = useState(siteName)

  useEffect(() => {
    try {
      localStorage.setItem(SITE_NAME_KEY, siteName)
    } catch {
      // ignore
    }
  }, [siteName])

  const clusters = getClusters(isAdmin, isPharmacist, isLogistics, isProcurement, isSales)

  const saveSiteName = () => {
    const trimmed = editValue.trim()
    if (trimmed) {
      setSiteName(trimmed)
    } else {
      setEditValue(siteName)
    }
    setEditing(false)
  }

  return (
    <aside
      style={{
        position: 'fixed',
        top: 0,
        left: 0,
        bottom: 0,
        width: collapsed ? 'var(--sidebar-collapsed-width)' : 'var(--sidebar-width)',
        backgroundColor: 'var(--surface)',
        borderRight: '1px solid var(--border)',
        display: 'flex',
        flexDirection: 'column',
        transition: 'width 200ms ease',
        zIndex: 30,
        overflowX: 'hidden',
      }}
    >
      {/* Site Name */}
      <div
        style={{
          height: 'var(--navbar-height)',
          display: 'flex',
          alignItems: 'center',
          padding: collapsed ? '0 10px' : '0 16px',
          borderBottom: '1px solid var(--border)',
          gap: '8px',
          justifyContent: collapsed ? 'center' : 'flex-start',
        }}
      >
        <div
          style={{
            width: '28px',
            height: '28px',
            borderRadius: 'var(--radius-sm)',
            backgroundColor: 'var(--accent)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            color: '#fff',
            fontWeight: 700,
            fontSize: '14px',
            flexShrink: 0,
          }}
        >
          H
        </div>
        {!collapsed && (
          editing ? (
            <input
              value={editValue}
              onChange={(e) => setEditValue(e.target.value)}
              onBlur={saveSiteName}
              onKeyDown={(e) => {
                if (e.key === 'Enter') saveSiteName()
                if (e.key === 'Escape') {
                  setEditValue(siteName)
                  setEditing(false)
                }
              }}
              autoFocus
              style={{
                background: 'var(--surface-2)',
                border: '1px solid var(--border)',
                borderRadius: 'var(--radius-sm)',
                padding: '2px 8px',
                color: 'var(--text)',
                fontSize: '0.9rem',
                fontWeight: 600,
                width: '100%',
              }}
            />
          ) : (
            <span
              onClick={() => {
                setEditValue(siteName)
                setEditing(true)
              }}
              style={{
                fontWeight: 700,
                fontSize: '0.95rem',
                color: 'var(--text)',
                cursor: 'pointer',
                whiteSpace: 'nowrap',
                overflow: 'hidden',
                textOverflow: 'ellipsis',
              }}
              title="Click to edit site name"
            >
              {siteName}
            </span>
          )
        )}
      </div>

      {/* Nav Clusters */}
      <nav style={{ flex: 1, overflowY: 'auto', padding: '8px 0' }}>
        {clusters.map((cluster) => (
          <div key={cluster.label} style={{ marginBottom: '4px' }}>
            {!collapsed && (
              <div
                style={{
                  padding: '8px 16px 4px',
                  fontSize: '0.65rem',
                  fontWeight: 600,
                  textTransform: 'uppercase',
                  letterSpacing: '0.05em',
                  color: 'var(--text-muted)',
                }}
              >
                {cluster.label}
              </div>
            )}
            {cluster.items.map((item) => {
              // NavLink only exposes `isActive` via the render-prop form; hover handlers
              // can't access it, so derive it from the current location instead.
              const isActive = item.end
                ? location.pathname === item.to
                : location.pathname === item.to || location.pathname.startsWith(`${item.to}/`)
              return (
              <NavLink
                key={item.to}
                to={item.to}
                end={item.end}
                style={() => ({
                  display: 'flex',
                  alignItems: 'center',
                  gap: '12px',
                  padding: collapsed ? '12px 0' : '12px 16px',
                  margin: collapsed ? '2px 8px' : '2px 8px',
                  borderRadius: 'var(--radius-md)',
                  color: isActive ? 'var(--accent)' : 'var(--text-muted)',
                  backgroundColor: isActive ? 'color-mix(in srgb, var(--accent) 12%, transparent)' : 'transparent',
                  textDecoration: 'none',
                  fontSize: '0.85rem',
                  fontWeight: isActive ? 600 : 400,
                  transition: 'all 150ms ease',
                  justifyContent: collapsed ? 'center' : 'flex-start',
                  whiteSpace: 'nowrap',
                  minHeight: '44px',
                  outline: 'none',
                })}
                onMouseEnter={(e) => {
                  if (!isActive) e.currentTarget.style.backgroundColor = 'var(--surface-2)'
                }}
                onMouseLeave={(e) => {
                  if (!isActive) e.currentTarget.style.backgroundColor = 'transparent'
                }}
                onFocus={(e) => {
                  e.currentTarget.style.boxShadow = '0 0 0 2px var(--accent)'
                }}
                onBlur={(e) => {
                  e.currentTarget.style.boxShadow = 'none'
                }}
              >
                <span style={{ flexShrink: 0, display: 'flex', alignItems: 'center' }}>{item.icon}</span>
                {!collapsed && <span>{item.label}</span>}
              </NavLink>
              )
            })}
          </div>
        ))}
      </nav>

      {/* Collapse Toggle */}
      <div
        style={{
          padding: '8px',
          borderTop: '1px solid var(--border)',
          display: 'flex',
          justifyContent: collapsed ? 'center' : 'flex-end',
        }}
      >
        <button
          onClick={onToggle}
          style={{
            background: 'none',
            border: 'none',
            color: 'var(--text-muted)',
            cursor: 'pointer',
            padding: '6px',
            borderRadius: 'var(--radius-sm)',
            display: 'flex',
            alignItems: 'center',
          }}
          title={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
        >
          {collapsed ? <ChevronRight size={18} /> : <ChevronLeft size={18} />}
        </button>
      </div>
    </aside>
  )
}
