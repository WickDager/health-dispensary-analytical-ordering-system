import { useState, useEffect, useCallback } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import {
  ArrowLeft, User, Mail, Phone, Building2, Tag, Check, X,
  Clock, Pill, DollarSign, MessageSquare, PhoneCall, Calendar,
  Activity, FileText, UserCheck, RefreshCw, ToggleLeft, ToggleRight,
} from 'lucide-react'
import api, { extractResults } from '../api/client'
import { formatDate, formatDateTime, formatCurrency } from '../lib/utils'
import Card from '../components/ui/Card'
import Badge from '../components/ui/Badge'
import LoadingSpinner from '../components/ui/LoadingSpinner'
import ErrorBoundary from '../components/ui/ErrorBoundary'

interface ContactData {
  id: number
  first_name: string
  last_name: string
  contact_type: 'patient' | 'prescriber' | 'buyer'
  email: string
  phone: string
  mrn: string
  account_name: string
  account_id: number | null
  tags: string[]
  consent_marketing: boolean
  consent_data_processing: boolean
  is_active: boolean
  notes: string
  created_at: string
}

interface TimelineEvent {
  id: number
  event_type: string
  subject: string
  body: string
  related_to_type: string
  related_to_name: string
  created_by_name: string
  created_at: string
}

interface Deal {
  id: number
  name: string
  stage: string
  amount: string
  probability: number
  close_date: string
}

interface RefillReminder {
  id: number
  product_name: string
  interval_days: number
  next_due_date: string
  is_active: boolean
}

const TYPE_BADGE: Record<string, 'accent' | 'info' | 'ok'> = {
  patient: 'accent',
  prescriber: 'info',
  buyer: 'ok',
}

const EVENT_ICONS: Record<string, React.ReactNode> = {
  call: <PhoneCall size={14} />,
  meeting: <Calendar size={14} />,
  email: <MessageSquare size={14} />,
  note: <FileText size={14} />,
  task: <Check size={14} />,
  deal: <DollarSign size={14} />,
  refill: <Pill size={14} />,
  activity: <Activity size={14} />,
}

type TabKey = 'overview' | 'timeline' | 'deals' | 'refills'
const TABS: { key: TabKey; label: string }[] = [
  { key: 'overview', label: 'Overview' },
  { key: 'timeline', label: 'Timeline' },
  { key: 'deals', label: 'Deals' },
  { key: 'refills', label: 'Refills' },
]

export default function ContactDetail() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()

  const [contact, setContact] = useState<ContactData | null>(null)
  const [timeline, setTimeline] = useState<TimelineEvent[]>([])
  const [deals, setDeals] = useState<Deal[]>([])
  const [refills, setRefills] = useState<RefillReminder[]>([])
  const [activeTab, setActiveTab] = useState<TabKey>('overview')
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState('')
  const [timelineLoading, setTimelineLoading] = useState(false)

  const fetchContact = useCallback(async () => {
    setIsLoading(true)
    setError('')
    try {
      const data = await api.get<ContactData>(`/crm/contacts/${id}/`)
      setContact(data)
    } catch {
      setError('Failed to load contact.')
      setContact(null)
    } finally {
      setIsLoading(false)
    }
  }, [id])

  const fetchTimeline = async () => {
    setTimelineLoading(true)
    try {
      const data = await api.get<TimelineEvent[]>(`/crm/contacts/${id}/timeline/`)
      setTimeline(extractResults(data))
    } catch { setTimeline([]) }
    finally { setTimelineLoading(false) }
  }

  const fetchDeals = async () => {
    try {
      const data = await api.get<Deal[]>(`/crm/contacts/${id}/opportunities/`)
      setDeals(extractResults(data))
    } catch { setDeals([]) }
  }

  const fetchRefills = async () => {
    try {
      const data = await api.get<RefillReminder[]>(`/crm/contacts/${id}/refills/`)
      setRefills(extractResults(data))
    } catch { setRefills([]) }
  }

  useEffect(() => { if (id) fetchContact() }, [fetchContact])

  useEffect(() => {
    if (!contact) return
    if (activeTab === 'timeline') fetchTimeline()
    else if (activeTab === 'deals') fetchDeals()
    else if (activeTab === 'refills') fetchRefills()
  }, [activeTab, contact])

  const toggleRefill = async (refillId: number, currentActive: boolean) => {
    try {
      await api.patch(`/crm/refills/${refillId}/`, { is_active: !currentActive })
      setRefills((prev) => prev.map((r) => (r.id === refillId ? { ...r, is_active: !currentActive } : r)))
    } catch { /* ignore */ }
  }

  if (isLoading) return <LoadingSpinner message="Loading contact..." />

  if (!contact) {
    return (
      <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
        <button onClick={() => navigate('/crm/contacts')} style={backBtnStyle}>
          <ArrowLeft size={16} /> Back to Contacts
        </button>
        <div style={{ textAlign: 'center', padding: '40px', color: 'var(--danger)' }}>
          {error || 'Contact not found.'}
        </div>
      </div>
    )
  }

  const fullName = `${contact.first_name} ${contact.last_name}`

  return (
    <ErrorBoundary>
      <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
        <button onClick={() => navigate('/crm/contacts')} style={backBtnStyle}>
          <ArrowLeft size={16} /> Back to Contacts
        </button>

        <div style={{ display: 'grid', gridTemplateColumns: '280px 1fr', gap: '24px', alignItems: 'start' }}>
          {/* Left Panel - Identity */}
          <div style={{
            backgroundColor: 'var(--surface)',
            border: '1px solid var(--border)',
            borderRadius: 'var(--radius-lg)',
            padding: '24px',
            display: 'flex',
            flexDirection: 'column',
            gap: '16px',
          }}>
            <div style={{
              width: '64px',
              height: '64px',
              borderRadius: '50%',
              backgroundColor: 'color-mix(in srgb, var(--accent) 15%, transparent)',
              color: 'var(--accent)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              fontSize: '1.5rem',
              fontWeight: 700,
            }}>
              {contact.first_name?.charAt(0)}{contact.last_name?.charAt(0)}
            </div>
            <div>
              <h2 style={{ fontSize: '1.2rem', fontWeight: 700, color: 'var(--text)' }}>{fullName}</h2>
              <Badge variant={TYPE_BADGE[contact.contact_type] || 'info'}>
                {contact.contact_type.charAt(0).toUpperCase() + contact.contact_type.slice(1)}
              </Badge>
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
              <InfoRow icon={<Mail size={14} />} label="Email" value={contact.email || '—'} />
              <InfoRow icon={<Phone size={14} />} label="Phone" value={contact.phone || '—'} />
              {contact.mrn && <InfoRow icon={<User size={14} />} label="MRN" value={contact.mrn} />}
              <InfoRow
                icon={<Building2 size={14} />}
                label="Account"
                value={contact.account_name || '—'}
                link={contact.account_id ? `/crm/accounts/${contact.account_id}` : undefined}
              />
            </div>

            {/* Tags */}
            <div>
              <div style={{ fontSize: '0.75rem', fontWeight: 600, color: 'var(--text-muted)', marginBottom: '6px', textTransform: 'uppercase' }}>
                Tags
              </div>
              <div style={{ display: 'flex', gap: '4px', flexWrap: 'wrap' }}>
                {contact.tags?.length > 0 ? contact.tags.map((t: string) => (
                  <Badge key={t} variant="info" size="sm">{t}</Badge>
                )) : <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>No tags</span>}
              </div>
            </div>

            {/* Consent flags */}
            <div>
              <div style={{ fontSize: '0.75rem', fontWeight: 600, color: 'var(--text-muted)', marginBottom: '6px', textTransform: 'uppercase' }}>
                Consent
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '4px', fontSize: '0.8rem' }}>
                <ConsentBadge granted={contact.consent_marketing} label="Marketing" />
                <ConsentBadge granted={contact.consent_data_processing} label="Data Processing" />
              </div>
            </div>
          </div>

          {/* Right Panel - Tabs */}
          <div style={{
            backgroundColor: 'var(--surface)',
            border: '1px solid var(--border)',
            borderRadius: 'var(--radius-lg)',
            overflow: 'hidden',
          }}>
            {/* Tab bar */}
            <div style={{
              display: 'flex',
              borderBottom: '1px solid var(--border)',
              overflowX: 'auto',
            }}>
              {TABS.map((tab) => (
                <button
                  key={tab.key}
                  onClick={() => setActiveTab(tab.key)}
                  style={{
                    padding: '12px 20px',
                    background: 'none',
                    border: 'none',
                    borderBottom: activeTab === tab.key ? '2px solid var(--accent)' : '2px solid transparent',
                    color: activeTab === tab.key ? 'var(--accent)' : 'var(--text-muted)',
                    fontSize: '0.85rem',
                    fontWeight: activeTab === tab.key ? 600 : 400,
                    cursor: 'pointer',
                    whiteSpace: 'nowrap',
                    transition: 'all 150ms ease',
                  }}
                >
                  {tab.label}
                </button>
              ))}
            </div>

            {/* Tab content */}
            <div style={{ padding: '20px' }}>
              {activeTab === 'overview' && (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                  <DetailRow label="Full Name" value={fullName} />
                  <DetailRow label="Type" value={contact.contact_type} />
                  <DetailRow label="Email" value={contact.email || '—'} />
                  <DetailRow label="Phone" value={contact.phone || '—'} />
                  {contact.mrn && <DetailRow label="MRN" value={contact.mrn} />}
                  <DetailRow label="Account" value={contact.account_name || '—'} />
                  <DetailRow label="Active" value={contact.is_active ? 'Yes' : 'No'} />
                  <DetailRow label="Created" value={formatDate(contact.created_at)} />
                  {contact.notes && (
                    <div>
                      <div style={{ fontSize: '0.8rem', fontWeight: 600, color: 'var(--text-muted)', marginBottom: '4px' }}>Notes</div>
                      <p style={{ fontSize: '0.85rem', color: 'var(--text)', lineHeight: 1.5 }}>{contact.notes}</p>
                    </div>
                  )}
                </div>
              )}

              {activeTab === 'timeline' && (
                <div>
                  {timelineLoading ? (
                    <LoadingSpinner message="Loading timeline..." />
                  ) : timeline.length === 0 ? (
                    <div style={{ textAlign: 'center', padding: '20px', color: 'var(--text-muted)', fontSize: '0.85rem' }}>
                      No timeline events yet.
                    </div>
                  ) : (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '0' }}>
                      {timeline.map((event, idx) => (
                        <div
                          key={event.id}
                          style={{
                            display: 'flex',
                            gap: '14px',
                            paddingLeft: '8px',
                            position: 'relative',
                          }}
                        >
                          {/* Timeline line */}
                          <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', minWidth: '24px' }}>
                            <div style={{
                              width: '28px',
                              height: '28px',
                              borderRadius: '50%',
                              backgroundColor: 'color-mix(in srgb, var(--accent) 12%, transparent)',
                              display: 'flex',
                              alignItems: 'center',
                              justifyContent: 'center',
                              color: 'var(--accent)',
                              flexShrink: 0,
                            }}>
                              {EVENT_ICONS[event.event_type] || <FileText size={14} />}
                            </div>
                            {idx < timeline.length - 1 && (
                              <div style={{
                                width: '2px',
                                flex: 1,
                                backgroundColor: 'var(--border)',
                                marginTop: '4px',
                              }} />
                            )}
                          </div>
                          <div style={{ paddingBottom: '20px', flex: 1 }}>
                            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
                              <span style={{ fontWeight: 600, fontSize: '0.85rem', color: 'var(--text)' }}>
                                {event.subject}
                              </span>
                              <Badge variant="info" size="sm">{event.event_type}</Badge>
                            </div>
                            {event.body && (
                              <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginTop: '2px', lineHeight: 1.4 }}>
                                {event.body.length > 120 ? event.body.slice(0, 120) + '...' : event.body}
                              </p>
                            )}
                            <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)', marginTop: '4px', display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
                              <span>by {event.created_by_name}</span>
                              {event.related_to_name && <span>re: {event.related_to_name}</span>}
                              <span>{formatDateTime(event.created_at)}</span>
                            </div>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}

              {activeTab === 'deals' && (
                <div>
                  {deals.length === 0 ? (
                    <div style={{ textAlign: 'center', padding: '20px', color: 'var(--text-muted)', fontSize: '0.85rem' }}>
                      No deals associated with this contact.
                    </div>
                  ) : (
                    <div style={{ overflowX: 'auto' }}>
                      <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                        <thead>
                          <tr style={{ borderBottom: '1px solid var(--border)' }}>
                            <th style={thStyle}>Name</th>
                            <th style={thStyle}>Stage</th>
                            <th style={thStyle}>Amount</th>
                            <th style={thStyle}>Probability</th>
                            <th style={thStyle}>Close Date</th>
                          </tr>
                        </thead>
                        <tbody>
                          {deals.map((d) => (
                            <tr key={d.id} style={{ borderBottom: '1px solid var(--border)' }}>
                              <td style={tdStyle}>
                                <span
                                  style={{ color: 'var(--accent)', cursor: 'pointer', fontWeight: 500 }}
                                  onClick={() => navigate(`/crm/pipeline?opp=${d.id}`)}
                                >
                                  {d.name}
                                </span>
                              </td>
                              <td style={tdStyle}><Badge variant="info">{d.stage}</Badge></td>
                              <td style={tdStyle}>{formatCurrency(parseFloat(d.amount || '0'))}</td>
                              <td style={tdStyle}>{d.probability}%</td>
                              <td style={tdStyle}>{formatDate(d.close_date)}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}
                </div>
              )}

              {activeTab === 'refills' && (
                <div>
                  {refills.length === 0 ? (
                    <div style={{ textAlign: 'center', padding: '20px', color: 'var(--text-muted)', fontSize: '0.85rem' }}>
                      No refill reminders set up.
                    </div>
                  ) : (
                    <div style={{ overflowX: 'auto' }}>
                      <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                        <thead>
                          <tr style={{ borderBottom: '1px solid var(--border)' }}>
                            <th style={thStyle}>Product</th>
                            <th style={thStyle}>Interval (days)</th>
                            <th style={thStyle}>Next Due</th>
                            <th style={thStyle}>Active</th>
                          </tr>
                        </thead>
                        <tbody>
                          {refills.map((r) => (
                            <tr key={r.id} style={{ borderBottom: '1px solid var(--border)' }}>
                              <td style={tdStyle}><span style={{ fontWeight: 500 }}>{r.product_name}</span></td>
                              <td style={tdStyle}>{r.interval_days}</td>
                              <td style={tdStyle}>{formatDate(r.next_due_date)}</td>
                              <td style={tdStyle}>
                                <button
                                  onClick={() => toggleRefill(r.id, r.is_active)}
                                  style={{ background: 'none', border: 'none', cursor: 'pointer', padding: 0 }}
                                >
                                  {r.is_active
                                    ? <ToggleRight size={22} style={{ color: 'var(--ok)' }} />
                                    : <ToggleLeft size={22} style={{ color: 'var(--text-muted)' }} />
                                  }
                                </button>
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </ErrorBoundary>
  )
}

function InfoRow({ icon, label, value, link }: { icon: React.ReactNode; label: string; value: string; link?: string }) {
  const navigate = useNavigate()
  const content = (
    <div style={{ display: 'flex', gap: '8px', fontSize: '0.82rem' }}>
      <span style={{ color: 'var(--text-muted)', marginTop: '1px' }}>{icon}</span>
      <div>
        <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', textTransform: 'uppercase' }}>{label}</div>
        <div style={{ color: 'var(--text)', fontWeight: 500 }}>{value}</div>
      </div>
    </div>
  )
  if (link) {
    return (
      <span onClick={() => navigate(link)} style={{ cursor: 'pointer' }}>
        {content}
      </span>
    )
  }
  return content
}

function ConsentBadge({ granted, label }: { granted: boolean; label: string }) {
  return (
    <span style={{ display: 'inline-flex', alignItems: 'center', gap: '6px' }}>
      {granted
        ? <Check size={12} style={{ color: 'var(--ok)' }} />
        : <X size={12} style={{ color: 'var(--danger)' }} />
      }
      <span style={{ color: 'var(--text)' }}>{label}</span>
    </span>
  )
}

function DetailRow({ label, value }: { label: string; value: string }) {
  return (
    <div style={{ display: 'flex', gap: '12px', padding: '4px 0' }}>
      <span style={{ fontSize: '0.82rem', color: 'var(--text-muted)', minWidth: '100px' }}>{label}</span>
      <span style={{ fontSize: '0.85rem', color: 'var(--text)', fontWeight: 500 }}>{value}</span>
    </div>
  )
}

const backBtnStyle: React.CSSProperties = {
  display: 'inline-flex',
  alignItems: 'center',
  gap: '6px',
  background: 'none',
  border: 'none',
  color: 'var(--accent)',
  cursor: 'pointer',
  fontSize: '0.85rem',
  fontWeight: 500,
  padding: 0,
  width: 'fit-content',
}

const thStyle: React.CSSProperties = {
  padding: '10px 14px',
  textAlign: 'left',
  fontSize: '0.75rem',
  fontWeight: 600,
  color: 'var(--text-muted)',
  textTransform: 'uppercase',
  letterSpacing: '0.03em',
}

const tdStyle: React.CSSProperties = {
  padding: '10px 14px',
  fontSize: '0.85rem',
  color: 'var(--text)',
}
