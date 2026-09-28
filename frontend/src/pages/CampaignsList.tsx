import { useState, useEffect, useCallback } from 'react'
import { Megaphone, Plus, Info } from 'lucide-react'
import api, { extractResults } from '../api/client'
import { formatDate, formatDateTime } from '../lib/utils'
import Card from '../components/ui/Card'
import Badge from '../components/ui/Badge'
import DataTable, { type Column } from '../components/ui/DataTable'
import Modal from '../components/ui/Modal'
import EmptyState from '../components/ui/EmptyState'
import LoadingSpinner from '../components/ui/LoadingSpinner'
import ErrorBoundary from '../components/ui/ErrorBoundary'

interface Campaign {
  id: number
  name: string
  campaign_type: string
  target_tags: string[]
  scheduled_at: string
  sent_count: number
  status: string
  created_at: string
}

const emptyCampaign = () => ({
  name: '',
  campaign_type: 'email',
  target_tags: '',
  scheduled_at: '',
})

export default function CampaignsList() {
  const [campaigns, setCampaigns] = useState<Campaign[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState('')
  const [addOpen, setAddOpen] = useState(false)
  const [form, setForm] = useState(emptyCampaign())
  const [saving, setSaving] = useState(false)

  const fetchCampaigns = useCallback(async () => {
    setIsLoading(true)
    setError('')
    try {
      const data = await api.get<Campaign[]>('/crm/campaigns/')
      setCampaigns(extractResults(data))
    } catch {
      setError('Failed to load campaigns.')
      setCampaigns([])
    } finally { setIsLoading(false) }
  }, [])

  useEffect(() => { fetchCampaigns() }, [fetchCampaigns])

  const handleSave = async () => {
    if (!form.name.trim()) return
    setSaving(true)
    try {
      await api.post('/crm/campaigns/', {
        ...form,
        target_tags: form.target_tags.split(',').map((t) => t.trim()).filter(Boolean),
      })
      setAddOpen(false)
      setForm(emptyCampaign())
      fetchCampaigns()
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to create campaign.')
    } finally { setSaving(false) }
  }

  const columns: Column<Campaign>[] = [
    { key: 'name', header: 'Name', sortable: true, render: (c) => <span style={{ fontWeight: 500 }}>{c.name}</span> },
    {
      key: 'campaign_type',
      header: 'Type',
      sortable: true,
      render: (c) => <Badge variant="accent">{c.campaign_type}</Badge>,
    },
    {
      key: 'target_tags',
      header: 'Target Tags',
      render: (c) => (
        <div style={{ display: 'flex', gap: '4px', flexWrap: 'wrap' }}>
          {c.target_tags?.map((t: string) => <Badge key={t} variant="info" size="sm">{t}</Badge>) || '—'}
        </div>
      ),
    },
    {
      key: 'scheduled_at',
      header: 'Scheduled',
      sortable: true,
      render: (c) => c.scheduled_at ? formatDateTime(c.scheduled_at) : <Badge variant="warn">Draft</Badge>,
    },
    { key: 'sent_count', header: 'Sent Count', sortable: true },
    {
      key: 'status',
      header: 'Status',
      render: (c) => <Badge variant={c.status === 'sent' ? 'ok' : c.status === 'sending' ? 'warn' : 'info'}>{c.status}</Badge>,
    },
  ]

  return (
    <ErrorBoundary>
      <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '12px' }}>
          <div>
            <h1 style={{ fontSize: '1.5rem', fontWeight: 700, color: 'var(--text)' }}>Campaigns</h1>
            <p style={{ fontSize: '0.85rem', color: 'var(--text-muted)', marginTop: '2px' }}>
              {campaigns.length} campaign{campaigns.length !== 1 ? 's' : ''}
            </p>
          </div>
          <button onClick={() => setAddOpen(true)} style={priBtnStyle}>
            <Plus size={16} /> Create Campaign
          </button>
        </div>

        {/* Consent gate notice */}
        <div style={{
          display: 'flex', alignItems: 'flex-start', gap: '8px',
          padding: '10px 14px',
          backgroundColor: 'color-mix(in srgb, var(--accent) 8%, transparent)',
          border: '1px solid color-mix(in srgb, var(--accent) 15%, transparent)',
          borderRadius: 'var(--radius-md)',
          fontSize: '0.8rem', color: 'var(--accent)',
        }}>
          <Info size={14} style={{ marginTop: '1px', flexShrink: 0 }} />
          <span>Only contacts with <strong>consent_marketing=true</strong> will be targeted.</span>
        </div>

        {error && <div style={errorBannerStyle}>{error}</div>}

        {isLoading ? (
          <LoadingSpinner message="Loading campaigns..." />
        ) : campaigns.length === 0 ? (
          <EmptyState
            icon={<Megaphone size={48} />}
            title="No campaigns"
            description="Create your first marketing campaign."
            action={<button onClick={() => setAddOpen(true)} style={priBtnStyle}><Plus size={16} /> Create Campaign</button>}
          />
        ) : (
          <DataTable columns={columns} data={campaigns} keyExtractor={(c) => c.id} pageSize={20} />
        )}

        {/* Create Campaign Modal */}
        <Modal open={addOpen} onClose={() => setAddOpen(false)} title="Create Campaign" maxWidth="500px">
          <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
            <Field label="Campaign Name" value={form.name} onChange={(v) => setForm((p) => ({ ...p, name: v }))} />
            <div>
              <label style={labelStyle}>Type</label>
              <select value={form.campaign_type} onChange={(e) => setForm((p) => ({ ...p, campaign_type: e.target.value }))} style={selectStyle}>
                <option value="email">Email</option>
                <option value="sms">SMS</option>
                <option value="newsletter">Newsletter</option>
              </select>
            </div>
            <Field label="Target Tags (comma-separated)" value={form.target_tags} onChange={(v) => setForm((p) => ({ ...p, target_tags: v }))}
              placeholder="e.g. premium, diabetes" />
            <Field label="Schedule (optional)" value={form.scheduled_at} onChange={(v) => setForm((p) => ({ ...p, scheduled_at: v }))} type="datetime-local" />

            <div style={{
              padding: '10px 12px',
              backgroundColor: 'color-mix(in srgb, var(--warn) 8%, transparent)',
              borderRadius: 'var(--radius-md)',
              fontSize: '0.78rem',
              color: 'var(--warn)',
            }}>
              <Info size={12} style={{ marginRight: '6px', display: 'inline' }} />
              Only contacts with marketing consent will receive this campaign.
            </div>

            <div style={{ display: 'flex', gap: '10px', justifyContent: 'flex-end', marginTop: '8px' }}>
              <button onClick={() => setAddOpen(false)} style={secBtnStyle}>Cancel</button>
              <button onClick={handleSave} disabled={saving || !form.name.trim()} style={priBtnStyle}>
                {saving ? 'Creating...' : 'Create'}
              </button>
            </div>
          </div>
        </Modal>
      </div>
    </ErrorBoundary>
  )
}

function Field({ label, value, onChange, type = 'text', placeholder }: { label: string; value: string; onChange: (v: string) => void; type?: string; placeholder?: string }) {
  return (
    <div>
      <label style={labelStyle}>{label}</label>
      <input type={type} value={value} onChange={(e) => onChange(e.target.value)} placeholder={placeholder} style={inputStyle}
        onFocus={(e) => { e.currentTarget.style.borderColor = 'var(--accent)' }}
        onBlur={(e) => { e.currentTarget.style.borderColor = 'var(--border)' }}
      />
    </div>
  )
}

const labelStyle: React.CSSProperties = { display: 'block', fontSize: '0.8rem', fontWeight: 500, color: 'var(--text)', marginBottom: '4px' }
const inputStyle: React.CSSProperties = { width: '100%', padding: '8px 10px', backgroundColor: 'var(--surface-2)', border: '1px solid var(--border)', borderRadius: 'var(--radius-md)', color: 'var(--text)', fontSize: '0.85rem', outline: 'none', boxSizing: 'border-box' }
const selectStyle: React.CSSProperties = { ...inputStyle }
const priBtnStyle: React.CSSProperties = { display: 'inline-flex', alignItems: 'center', gap: '6px', padding: '8px 16px', backgroundColor: 'var(--accent)', color: '#fff', border: 'none', borderRadius: 'var(--radius-md)', fontSize: '0.85rem', fontWeight: 600, cursor: 'pointer' }
const secBtnStyle: React.CSSProperties = { padding: '8px 16px', backgroundColor: 'transparent', color: 'var(--text-muted)', border: '1px solid var(--border)', borderRadius: 'var(--radius-md)', fontSize: '0.85rem', cursor: 'pointer' }
const errorBannerStyle: React.CSSProperties = { backgroundColor: 'color-mix(in srgb, var(--danger) 12%, transparent)', color: 'var(--danger)', padding: '10px 16px', borderRadius: 'var(--radius-md)', fontSize: '0.85rem', border: '1px solid color-mix(in srgb, var(--danger) 25%, transparent)' }
