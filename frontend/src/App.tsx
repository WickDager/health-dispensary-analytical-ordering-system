import { lazy, Suspense } from 'react'
import { Routes, Route, Navigate, useLocation } from 'react-router-dom'
import { useAuth } from './hooks/useAuth'
import AppLayout from './components/layout/AppLayout'
import LoadingSpinner from './components/ui/LoadingSpinner'

// Lazy-loaded pages
const Login = lazy(() => import('./pages/Login'))
const Register = lazy(() => import('./pages/Register'))
const Dashboard = lazy(() => import('./pages/Dashboard'))
const NotFound = lazy(() => import('./pages/NotFound'))

// Operations
const InventoryList = lazy(() => import('./pages/InventoryList'))
const InventoryDetail = lazy(() => import('./pages/InventoryDetail'))
const Dispense = lazy(() => import('./pages/Dispense'))
const LotsLedger = lazy(() => import('./pages/LotsLedger'))
const AIIngest = lazy(() => import('./pages/AIIngest'))
const IntelligenceDashboard = lazy(() => import('./pages/IntelligenceDashboard'))

// Procurement
const Suppliers = lazy(() => import('./pages/Suppliers'))
const Procurement = lazy(() => import('./pages/Procurement'))
const OrdersList = lazy(() => import('./pages/OrdersList'))

// CRM
const ContactsList = lazy(() => import('./pages/ContactsList'))
const ContactDetail = lazy(() => import('./pages/ContactDetail'))
const AccountsList = lazy(() => import('./pages/AccountsList'))
const AccountDetail = lazy(() => import('./pages/AccountDetail'))
const LeadsList = lazy(() => import('./pages/LeadsList'))
const Pipeline = lazy(() => import('./pages/Pipeline'))
const ActivitiesList = lazy(() => import('./pages/ActivitiesList'))
const CampaignsList = lazy(() => import('./pages/CampaignsList'))

// Administration
const Approvals = lazy(() => import('./pages/Approvals'))
const SettingsLayout = lazy(() => import('./pages/SettingsLayout'))
const SettingsProviders = lazy(() => import('./pages/SettingsProviders'))
const SettingsTheme = lazy(() => import('./pages/SettingsTheme'))
const SettingsAI = lazy(() => import('./pages/SettingsAI'))
const SettingsNotifications = lazy(() => import('./pages/SettingsNotifications'))
const SettingsUsers = lazy(() => import('./pages/SettingsUsers'))
const AuditLog = lazy(() => import('./pages/AuditLog'))
const NotificationCenter = lazy(() => import('./pages/NotificationCenter'))

interface ProtectedRouteProps {
  children: React.ReactNode
  allowedRoles?: string[]
}

function ProtectedRoute({ children, allowedRoles }: ProtectedRouteProps) {
  const { user, isLoading } = useAuth()
  const location = useLocation()

  if (isLoading) {
    return <LoadingSpinner fullPage />
  }

  if (!user) {
    return <Navigate to="/login" state={{ from: location }} replace />
  }

  if (allowedRoles && !allowedRoles.includes(user.role)) {
    return <Navigate to="/" replace />
  }

  return <>{children}</>
}

function App() {
  return (
    <Suspense fallback={<LoadingSpinner fullPage />}>
      <Routes>
        {/* Public routes */}
        <Route path="/login" element={<Login />} />
        <Route path="/register" element={<Register />} />

        {/* Protected routes */}
        <Route
          element={
            <ProtectedRoute>
              <AppLayout />
            </ProtectedRoute>
          }
        >
          <Route path="/" element={<Navigate to="/dashboard" replace />} />
          <Route path="/dashboard" element={<Dashboard />} />

          {/* Operations */}
          <Route path="/inventory" element={<InventoryList />} />
          <Route path="/inventory/:id" element={<InventoryDetail />} />
          <Route path="/dispense" element={<Dispense />} />
          <Route path="/lots" element={<LotsLedger />} />
          <Route path="/ingest" element={<AIIngest />} />
          <Route path="/intelligence" element={<IntelligenceDashboard />} />

          {/* Procurement */}
          <Route path="/suppliers" element={<Suppliers />} />
          <Route path="/procurement" element={<Procurement />} />
          <Route path="/orders" element={<OrdersList />} />

          {/* CRM */}
          <Route path="/crm/contacts" element={<ContactsList />} />
          <Route path="/crm/contacts/:id" element={<ContactDetail />} />
          <Route path="/crm/accounts" element={<AccountsList />} />
          <Route path="/crm/accounts/:id" element={<AccountDetail />} />
          <Route path="/crm/leads" element={<LeadsList />} />
          <Route path="/crm/pipeline" element={<Pipeline />} />
          <Route path="/crm/activities" element={<ActivitiesList />} />
          <Route path="/crm/campaigns" element={<CampaignsList />} />

          {/* Administration (role-gated: admin only for settings, pharmacist+ for approvals) */}
          <Route path="/approvals" element={<Approvals />} />
          <Route path="/settings" element={<SettingsLayout />}>
            <Route path="providers" element={<SettingsProviders />} />
            <Route path="theme" element={<SettingsTheme />} />
            <Route path="ai" element={<SettingsAI />} />
            <Route path="notifications" element={<SettingsNotifications />} />
            <Route path="users" element={<SettingsUsers />} />
            <Route index element={<Navigate to="providers" replace />} />
          </Route>
          <Route path="/audit" element={<AuditLog />} />
          <Route path="/notifications" element={<NotificationCenter />} />

          {/* 404 */}
          <Route path="*" element={<NotFound />} />
        </Route>
      </Routes>
    </Suspense>
  )
}

export default App
