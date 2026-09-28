import { useState, useEffect, useCallback } from 'react'
import {
  Users,
  Check,
  X,
  UserX,
  Search,
  Filter,
  Clock,
  Activity,
  Shield,
  Eye,
  ChevronRight,
} from 'lucide-react'
import api, { extractResults } from '../api/client'
import { useRoleAccess } from '../hooks/useRoleAccess'
import { formatDate, formatDateTime } from '../lib/utils'
import Card from '../components/ui/Card'
import Badge from '../components/ui/Badge'
import DataTable, { type Column } from '../components/ui/DataTable'
import LoadingSpinner from '../components/ui/LoadingSpinner'
import EmptyState from '../components/ui/EmptyState'
import Modal from '../components/ui/Modal'
import ErrorBoundary from '../components/ui/ErrorBoundary'

type UserRole = 'admin' | 'pharmacist' | 'logistics' | 'procurement' | 'sales'

interface HdaosUser {
  id: number
  username: string
  email: string
  first_name: string
  last_name: string
  role: UserRole
  is_active: boolean
  date_joined: string
  last_login: string | null
}

interface UserActivity {
  id: number
  action: string
  description: string
  timestamp: string
  ip_address: string | null
}

const ROLE_VARIANT: Record<string, 'accent' | 'ok' | 'warn' | 'info'> = {
  admin: 'accent',
  pharmacist: 'ok',
  logistics: 'warn',
  procurement: 'info',
  sales: 'info',
}

const ROLES: UserRole[] = ['admin', 'pharmacist', 'logistics', 'procurement', 'sales']

export default function SettingsUsers() {
  const { isAdmin } = useRoleAccess()
  const [users, setUsers] = useState<HdaosUser[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')
  const [searchQuery, setSearchQuery] = useState('')
  const [roleFilter, setRoleFilter] = useState<string>('all')
  const [approvingId, setApprovingId] = useState<number | null>(null)
  const [deactivatingId, setDeactivatingId] = useState<number | null>(null)

  // User detail modal
  const [selectedUser, setSelectedUser] = useState<HdaosUser | null>(null)
  const [userActivity, setUserActivity] = useState<UserActivity[]>([])
  const [activityLoading, setActivityLoading] = useState(false)

  // Confirmation modal
  const [confirmAction, setConfirmAction] = useState<{
    user: HdaosUser
    action: 'approve' | 'deactivate'
  } | null>(null)

  // Role change
  const [changingRoleId, setChangingRoleId] = useState<number | null>(null)

  const fetchUsers = useCallback(async () => {
    setIsLoading(true)
    setError('')
    try {
      const data = await api.get<HdaosUser[]>('/settings/users/')
      setUsers(extractResults(data))
    } catch {
      setError('Failed to load users.')
    } finally {
      setIsLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchUsers()
  }, [fetchUsers])

  // Fetch user activity log
  const fetchUserActivity = async (userId: number) => {
    setActivityLoading(true)
    try {
      const data = await api.get<UserActivity[]>(`/settings/users/${userId}/activity/`)
      setUserActivity(extractResults(data).slice(0, 20))
    } catch {
      setUserActivity([])
    } finally {
      setActivityLoading(false)
    }
  }

  const openUserDetail = (u: HdaosUser) => {
    setSelectedUser(u)
    fetchUserActivity(u.id)
  }

  const closeUserDetail = () => {
    setSelectedUser(null)
    setUserActivity([])
  }

  const handleApprove = async (u: HdaosUser) => {
    setApprovingId(u.id)
    try {
      await api.patch(`/settings/users/${u.id}/`, { is_active: true })
      setUsers((prev) =>
        prev.map((uu) => (uu.id === u.id ? { ...uu, is_active: true } : uu)),
      )
      setSuccess(`User "${u.username}" has been approved.`)
      setConfirmAction(null)
    } catch {
      setError('Failed to approve user.')
    } finally {
      setApprovingId(null)
    }
  }

  const handleDeactivate = async (u: HdaosUser) => {
    setDeactivatingId(u.id)
    try {
      await api.patch(`/settings/users/${u.id}/`, { is_active: false })
      setUsers((prev) =>
        prev.map((uu) => (uu.id === u.id ? { ...uu, is_active: false } : uu)),
      )
      setSuccess(`User "${u.username}" has been deactivated.`)
      setConfirmAction(null)
    } catch {
      setError('Failed to deactivate user.')
    } finally {
      setDeactivatingId(null)
    }
  }

  const handleRoleChange = async (u: HdaosUser, newRole: UserRole) => {
    setChangingRoleId(u.id)
    try {
      await api.patch(`/settings/users/${u.id}/`, { role: newRole })
      setUsers((prev) =>
        prev.map((uu) => (uu.id === u.id ? { ...uu, role: newRole } : uu)),
      )
      setSuccess(`Role for "${u.username}" updated to ${newRole}.`)
    } catch {
      setError('Failed to update role.')
    } finally {
      setChangingRoleId(null)
    }
  }

  // Filter and search
  const filteredUsers = users.filter((u) => {
    const matchesRole = roleFilter === 'all' || u.role === roleFilter
    const query = searchQuery.toLowerCase()
    const matchesSearch =
      !query ||
      u.username.toLowerCase().includes(query) ||
      u.email.toLowerCase().includes(query) ||
      u.first_name.toLowerCase().includes(query) ||
      u.last_name.toLowerCase().includes(query)
    return matchesRole && matchesSearch
  })

  if (!isAdmin) {
    return (
      <div style={{ textAlign: 'center', padding: '40px', color: 'var(--text-muted)' }}>
        <h2 style={{ fontSize: '1.1rem', fontWeight: 600, color: 'var(--text)' }}>Access Denied</h2>
        <p style={{ fontSize: '0.85rem', marginTop: '4px' }}>Only administrators can manage users.</p>
      </div>
    )
  }

  const columns: Column<HdaosUser>[] = [
    {
      key: 'username',
      header: 'User',
      sortable: true,
      render: (u) => (
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <div
            style={{
              width: '32px',
              height: '32px',
              borderRadius: '50%',
              backgroundColor: 'var(--surface-2)',
              border: '1px solid var(--border)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              fontSize: '0.75rem',
              fontWeight: 700,
              color: 'var(--text-muted)',
              flexShrink: 0,
            }}
          >
            {u.first_name?.charAt(0)?.toUpperCase() || ''}
            {u.last_name?.charAt(0)?.toUpperCase() || ''}
          </div>
          <div>
            <div
              style={{
                fontWeight: 500,
                color: 'var(--accent)',
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                gap: '4px',
              }}
              onClick={() => openUserDetail(u)}
            >
              {u.username}
              <ChevronRight size={12} style={{ opacity: 0.5 }} />
            </div>
            <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>
              {u.first_name} {u.last_name}
            </div>
          </div>
        </div>
      ),
    },
    {
      key: 'email',
      header: 'Email',
      sortable: true,
      render: (u) => (
        <span style={{ fontSize: '0.82rem' }}>{u.email}</span>
      ),
    },
    {
      key: 'role',
      header: 'Role',
      sortable: true,
      render: (u) => (
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <Badge variant={ROLE_VARIANT[u.role] || 'info'}>{u.role}</Badge>
          {/* Role change dropdown */}
          <select
            value={u.role}
            onChange={(e) => handleRoleChange(u, e.target.value as UserRole)}
            disabled={changingRoleId === u.id}
            style={{
              padding: '2px 4px',
              fontSize: '0.68rem',
              backgroundColor: 'var(--surface-2)',
              border: '1px solid var(--border)',
              borderRadius: 'var(--radius-sm)',
              color: 'var(--text-muted)',
              cursor: 'pointer',
              opacity: changingRoleId === u.id ? 0.5 : 1,
            }}
            title="Change role"
          >
            {ROLES.map((r) => (
              <option key={r} value={r}>
                {r}
              </option>
            ))}
          </select>
        </div>
      ),
    },
    {
      key: 'is_active',
      header: 'Status',
      sortable: true,
      render: (u) => (
        <Badge variant={u.is_active ? 'ok' : 'warn'} dot>
          {u.is_active ? 'Active' : 'Inactive'}
        </Badge>
      ),
    },
    {
      key: 'date_joined',
      header: 'Date Joined',
      sortable: true,
      render: (u) => (
        <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
          {formatDate(u.date_joined)}
        </span>
      ),
    },
    {
      key: 'actions',
      header: 'Actions',
      render: (u) => (
        <div style={{ display: 'flex', gap: '6px', alignItems: 'center' }}>
          <button
            onClick={() => openUserDetail(u)}
            style={actionIconBtnStyle}
            title="View details"
          >
            <Eye size={14} />
          </button>
          {!u.is_active ? (
            <button
              onClick={() => setConfirmAction({ user: u, action: 'approve' })}
              disabled={approvingId === u.id}
              style={approveBtnStyle}
            >
              <Check size={12} />
              {approvingId === u.id ? 'Approving...' : 'Approve'}
            </button>
          ) : (
            <button
              onClick={() => setConfirmAction({ user: u, action: 'deactivate' })}
              disabled={deactivatingId === u.id}
              style={deactivateBtnStyle}
            >
              <UserX size={12} />
              {deactivatingId === u.id ? 'Deactivating...' : 'Deactivate'}
            </button>
          )}
        </div>
      ),
    },
  ]

  return (
    <ErrorBoundary>
      <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
        {error && <div style={errorBannerStyle}>{error}</div>}
        {success && <div style={successBannerStyle}>{success}</div>}

        {/* Filters Bar */}
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '12px',
            flexWrap: 'wrap',
            padding: '12px 16px',
            backgroundColor: 'var(--surface)',
            borderRadius: 'var(--radius-lg)',
            border: '1px solid var(--border)',
          }}
        >
          {/* Search */}
          <div style={{ position: 'relative', flex: '1 1 240px' }}>
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
              placeholder="Search users..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              style={{
                width: '100%',
                padding: '7px 10px 7px 32px',
                backgroundColor: 'var(--surface-2)',
                border: '1px solid var(--border)',
                borderRadius: 'var(--radius-sm)',
                color: 'var(--text)',
                fontSize: '0.85rem',
                outline: 'none',
                boxSizing: 'border-box',
              }}
            />
          </div>

          {/* Role Filter */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <Filter size={14} style={{ color: 'var(--text-muted)' }} />
            <select
              value={roleFilter}
              onChange={(e) => setRoleFilter(e.target.value)}
              style={filterSelectStyle}
            >
              <option value="all">All Roles</option>
              {ROLES.map((r) => (
                <option key={r} value={r}>
                  {r.charAt(0).toUpperCase() + r.slice(1)}
                </option>
              ))}
            </select>
          </div>

          {/* User count */}
          <div
            style={{
              fontSize: '0.78rem',
              color: 'var(--text-muted)',
              whiteSpace: 'nowrap',
              marginLeft: 'auto',
            }}
          >
            {filteredUsers.length} user{filteredUsers.length !== 1 ? 's' : ''}
          </div>
        </div>

        {/* Users Table */}
        {isLoading ? (
          <LoadingSpinner message="Loading users..." />
        ) : filteredUsers.length === 0 ? (
          users.length === 0 ? (
            <EmptyState
              icon={<Users size={48} />}
              title="No users registered"
              description="New users will appear here once they register or are created."
            />
          ) : (
            <EmptyState
              icon={<Search size={48} />}
              title="No matching users"
              description="No users match your current search or filter criteria."
              action={
                <button
                  onClick={() => {
                    setSearchQuery('')
                    setRoleFilter('all')
                  }}
                  style={{
                    padding: '6px 14px',
                    backgroundColor: 'var(--surface-2)',
                    border: '1px solid var(--border)',
                    borderRadius: 'var(--radius-md)',
                    color: 'var(--text)',
                    fontSize: '0.85rem',
                    cursor: 'pointer',
                    fontWeight: 500,
                  }}
                >
                  Clear Filters
                </button>
              }
            />
          )
        ) : (
          <DataTable
            columns={columns}
            data={filteredUsers}
            keyExtractor={(u) => u.id}
            pageSize={15}
          />
        )}

        {/* Confirmation Modal */}
        <Modal
          open={confirmAction !== null}
          onClose={() => setConfirmAction(null)}
          title={confirmAction?.action === 'approve' ? 'Approve User' : 'Deactivate User'}
          maxWidth="420px"
        >
          {confirmAction && (
            <div>
              <p style={{ fontSize: '0.9rem', color: 'var(--text)', marginBottom: '8px' }}>
                {confirmAction.action === 'approve'
                  ? `Are you sure you want to approve "${confirmAction.user.username}"?`
                  : `Are you sure you want to deactivate "${confirmAction.user.username}"?`}
              </p>
              <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginBottom: '20px' }}>
                {confirmAction.action === 'approve'
                  ? 'This user will be able to log in and access the system.'
                  : 'This user will no longer be able to log in until re-approved.'}
              </p>
              <div style={{ display: 'flex', gap: '10px', justifyContent: 'flex-end' }}>
                <button
                  onClick={() => setConfirmAction(null)}
                  style={modalCancelBtnStyle}
                >
                  Cancel
                </button>
                <button
                  onClick={() => {
                    if (confirmAction.action === 'approve') {
                      handleApprove(confirmAction.user)
                    } else {
                      handleDeactivate(confirmAction.user)
                    }
                  }}
                  style={{
                    ...modalConfirmBtnStyle,
                    backgroundColor:
                      confirmAction.action === 'approve' ? 'var(--ok)' : 'var(--danger)',
                  }}
                >
                  {confirmAction.action === 'approve' ? 'Approve User' : 'Deactivate User'}
                </button>
              </div>
            </div>
          )}
        </Modal>

        {/* User Detail Modal */}
        <Modal
          open={selectedUser !== null}
          onClose={closeUserDetail}
          title="User Details"
          maxWidth="560px"
        >
          {selectedUser && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
              {/* User Info */}
              <div style={{ display: 'flex', gap: '14px', alignItems: 'center' }}>
                <div
                  style={{
                    width: '56px',
                    height: '56px',
                    borderRadius: '50%',
                    backgroundColor: 'var(--surface-2)',
                    border: '2px solid var(--border)',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    fontSize: '1.2rem',
                    fontWeight: 700,
                    color: 'var(--accent)',
                    flexShrink: 0,
                  }}
                >
                  {selectedUser.first_name?.charAt(0)?.toUpperCase() || ''}
                  {selectedUser.last_name?.charAt(0)?.toUpperCase() || ''}
                </div>
                <div>
                  <div style={{ fontWeight: 700, fontSize: '1.05rem', color: 'var(--text)' }}>
                    {selectedUser.first_name} {selectedUser.last_name}
                  </div>
                  <div style={{ fontSize: '0.85rem', color: 'var(--text-muted)' }}>
                    @{selectedUser.username}
                  </div>
                  <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
                    {selectedUser.email}
                  </div>
                </div>
              </div>

              {/* Info Grid */}
              <div
                style={{
                  display: 'grid',
                  gridTemplateColumns: '1fr 1fr',
                  gap: '12px',
                  padding: '14px',
                  borderRadius: 'var(--radius-md)',
                  backgroundColor: 'var(--surface-2)',
                }}
              >
                <InfoItem label="Role" value={selectedUser.role} />
                <InfoItem
                  label="Status"
                  value={selectedUser.is_active ? 'Active' : 'Inactive'}
                  valueColor={selectedUser.is_active ? 'var(--ok)' : 'var(--warn)'}
                />
                <InfoItem label="Joined" value={formatDate(selectedUser.date_joined)} />
                <InfoItem
                  label="Last Login"
                  value={
                    selectedUser.last_login
                      ? formatDateTime(selectedUser.last_login)
                      : 'Never'
                  }
                />
              </div>

              {/* Activity Log */}
              <div>
                <div
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: '8px',
                    marginBottom: '10px',
                  }}
                >
                  <Activity size={16} style={{ color: 'var(--text-muted)' }} />
                  <h4 style={{ fontSize: '0.9rem', fontWeight: 600, color: 'var(--text)' }}>
                    Recent Activity
                  </h4>
                </div>
                {activityLoading ? (
                  <LoadingSpinner size={20} message="Loading activity..." />
                ) : userActivity.length === 0 ? (
                  <div
                    style={{
                      textAlign: 'center',
                      padding: '20px',
                      color: 'var(--text-muted)',
                      fontSize: '0.82rem',
                    }}
                  >
                    No recent activity recorded.
                  </div>
                ) : (
                  <div
                    style={{
                      maxHeight: '220px',
                      overflowY: 'auto',
                      display: 'flex',
                      flexDirection: 'column',
                      gap: '6px',
                    }}
                  >
                    {userActivity.map((act) => (
                      <div
                        key={act.id}
                        style={{
                          display: 'flex',
                          alignItems: 'flex-start',
                          gap: '10px',
                          padding: '8px 10px',
                          borderRadius: 'var(--radius-sm)',
                          backgroundColor: 'var(--surface-2)',
                          fontSize: '0.8rem',
                        }}
                      >
                        <Clock
                          size={12}
                          style={{
                            color: 'var(--text-muted)',
                            flexShrink: 0,
                            marginTop: '2px',
                          }}
                        />
                        <div style={{ flex: 1 }}>
                          <div style={{ fontWeight: 500, color: 'var(--text)' }}>
                            {act.action}
                          </div>
                          <div style={{ color: 'var(--text-muted)', fontSize: '0.72rem' }}>
                            {act.description}
                          </div>
                          <div
                            style={{
                              color: 'var(--text-muted)',
                              fontSize: '0.68rem',
                              marginTop: '2px',
                            }}
                          >
                            {formatDateTime(act.timestamp)}
                            {act.ip_address && ` - IP: ${act.ip_address}`}
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          )}
        </Modal>
      </div>
    </ErrorBoundary>
  )
}

function InfoItem({
  label,
  value,
  valueColor,
}: {
  label: string
  value: string
  valueColor?: string
}) {
  return (
    <div>
      <div style={{ fontSize: '0.7rem', fontWeight: 500, color: 'var(--text-muted)', marginBottom: '2px' }}>
        {label}
      </div>
      <div
        style={{
          fontSize: '0.85rem',
          fontWeight: 600,
          color: valueColor || 'var(--text)',
          textTransform: 'capitalize',
        }}
      >
        {value}
      </div>
    </div>
  )
}

const actionIconBtnStyle: React.CSSProperties = {
  display: 'inline-flex',
  alignItems: 'center',
  justifyContent: 'center',
  width: '28px',
  height: '28px',
  borderRadius: 'var(--radius-sm)',
  border: '1px solid var(--border)',
  backgroundColor: 'transparent',
  color: 'var(--text-muted)',
  cursor: 'pointer',
}

const approveBtnStyle: React.CSSProperties = {
  display: 'inline-flex',
  alignItems: 'center',
  gap: '4px',
  padding: '4px 10px',
  backgroundColor: 'var(--ok)',
  color: '#fff',
  border: 'none',
  borderRadius: 'var(--radius-sm)',
  fontSize: '0.75rem',
  fontWeight: 600,
  cursor: 'pointer',
  whiteSpace: 'nowrap',
}

const deactivateBtnStyle: React.CSSProperties = {
  display: 'inline-flex',
  alignItems: 'center',
  gap: '4px',
  padding: '4px 10px',
  backgroundColor: 'color-mix(in srgb, var(--danger) 15%, transparent)',
  color: 'var(--danger)',
  border: '1px solid color-mix(in srgb, var(--danger) 30%, transparent)',
  borderRadius: 'var(--radius-sm)',
  fontSize: '0.75rem',
  fontWeight: 600,
  cursor: 'pointer',
  whiteSpace: 'nowrap',
}

const filterSelectStyle: React.CSSProperties = {
  padding: '6px 8px',
  backgroundColor: 'var(--surface-2)',
  border: '1px solid var(--border)',
  borderRadius: 'var(--radius-sm)',
  color: 'var(--text)',
  fontSize: '0.8rem',
  outline: 'none',
  cursor: 'pointer',
}

const modalCancelBtnStyle: React.CSSProperties = {
  padding: '8px 18px',
  backgroundColor: 'var(--surface-2)',
  color: 'var(--text)',
  border: '1px solid var(--border)',
  borderRadius: 'var(--radius-md)',
  fontSize: '0.85rem',
  fontWeight: 500,
  cursor: 'pointer',
}

const modalConfirmBtnStyle: React.CSSProperties = {
  padding: '8px 18px',
  color: '#fff',
  border: 'none',
  borderRadius: 'var(--radius-md)',
  fontSize: '0.85rem',
  fontWeight: 600,
  cursor: 'pointer',
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
