import { useState, useEffect, useCallback } from 'react'
import {
  ClipboardList, CheckSquare, Plus, Check, PhoneCall, Calendar,
  MessageSquare, FileText, Activity,
} from 'lucide-react'
import api from '../api/client'
import { formatDateTime, formatDate } from '../lib/utils'
import Card from '../components/ui/Card'
import Badge from '../components/ui/Badge'
import DataTable, { type Column } from '../components/ui/DataTable'
import Modal from '../components/ui/Modal'
import EmptyState from '../components/ui/EmptyState'
import LoadingSpinner from '../components/ui/LoadingSpinner'
import ErrorBoundary from '../components/ui/ErrorBoundary'

interface ActivityItem {
  id: number
  activity_type: string
  subject: string
  body: string
  related_to_type: string
  related_to_name: string
  created_by_name: string
  created_at: string
}

interface TaskItem {
  id: number
  title: string
  due_date: string
  status: 'pending' | 'in_progress' | 'done'
  assignee_name: string
  related_to_type: string
  related_to_name: string
}

type TabKey = 'activities' | 'tasks'

const ACTIVITY_ICONS: Record<string, React.ReactNode> = {
  call: <PhoneCall size={14} />,
  meeting: <Calendar size={14} />,
  email: <MessageSquare size={14} />,
  note: <FileText size={14} />,
  task: <CheckSquare size={14} />,
}

const TASK_STATUS_VARIANT: Record<string, 'ok' | 'warn' | 'info'> = {
  done: 'ok',
  in_progress: 'warn',
  pending: 'info',
}

const emptyActivity = () => ({ activity_type: 'note', subject: '', body: '' })

const emptyTask = () => ({ title: '', due_date: '', assignee_id: '' })

export default function ActivitiesList() {
  const [activeTab, setActiveTab] = useState<TabKey>('activities')
  const [activities, setActivities] = useState<ActivityItem[]>([])
  const [tasks, setTasks] = useState<TaskItem[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState('')
  const [addActivityOpen, setAddActivityOpen] = useState(false)
  const [addTaskOpen, setAddTaskOpen] = useState(false)
  const [newActivity, setNewActivity] = useState(emptyActivity())
  const [newTask, setNewTask] = useState(emptyTask())
  const [saving, setSaving] = useState(false)

  const fetchData = useCallback(async () => {
    setIsLoading(true)
    setError('')
    try {
      const [acts, tsk] = await Promise.all([
        api.get<ActivityItem[]>('/crm/activities/?limit=200'),
        api.get<TaskItem[]>('/crm/tasks/?limit=200'),
      ])
      setActivities(Array.isArray(acts) ? acts : [])
      setTasks(Array.isArray(tsk) ? tsk : [])
    } catch {
      setError('Failed to load data.')
    } finally { setIsLoading(false) }
  }, [])

  useEffect(() => { fetchData() }, [fetchData])

  const handleAddActivity = async () => {
    if (!newActivity.subject.trim()) return
    setSaving(true)
    try {
      await api.post('/crm/activities/', newActivity)
      setAddActivityOpen(false)
      setNewActivity(emptyActivity())
      fetchData()
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to add activity.')
    } finally { setSaving(false) }
  }

  const handleAddTask = async () => {
    if (!newTask.title.trim()) return
    setSaving(true)
    try {
      await api.post('/crm/tasks/', newTask)
      setAddTaskOpen(false)
      setNewTask(emptyTask())
      fetchData()
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to add task.')
    } finally { setSaving(false) }
  }

  const handleToggleTask = async (task: TaskItem) => {
    const newStatus = task.status === 'done' ? 'pending' : 'done'
    try {
      await api.patch(`/crm/tasks/${task.id}/`, { status: newStatus })
      setTasks((prev) => prev.map((t) => (t.id === task.id ? { ...t, status: newStatus } : t)))
    } catch { /* ignore */ }
  }

  const activityColumns: Column<ActivityItem>[] = [
    {
      key: 'activity_type',
      header: 'Type',
      render: (a) => (
        <span style={{ display: 'inline-flex', alignItems: 'center', gap: '6px', color: 'var(--accent)' }}>
          {ACTIVITY_ICONS[a.activity_type] || <Activity size={14} />}
          {a.activity_type}
        </span>
      ),
    },
    { key: 'subject', header: 'Subject', render: (a) => <span style={{ fontWeight: 500 }}>{a.subject}</span> },
    {
      key: 'body',
      header: 'Body',
      render: (a) => (
        <span style={{ maxWidth: '250px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', display: 'inline-block' }}>
          {a.body || '—'}
        </span>
      ),
    },
    {
      key: 'related_to_name',
      header: 'Related To',
      render: (a) => a.related_to_name ? (
        <span style={{ fontSize: '0.8rem' }}>
          <span style={{ color: 'var(--text-muted)' }}>{a.related_to_type}: </span>
          {a.related_to_name}
        </span>
      ) : '—',
    },
    { key: 'created_by_name', header: 'Created By' },
    {
      key: 'created_at',
      header: 'Date',
      sortable: true,
      render: (a) => formatDateTime(a.created_at),
    },
  ]

  const taskColumns: Column<TaskItem>[] = [
    {
      key: 'checkbox',
      header: '',
      render: (t) => (
        <button
          onClick={() => handleToggleTask(t)}
          style={{
            background: 'none',
            border: `2px solid ${t.status === 'done' ? 'var(--ok)' : 'var(--border)'}`,
            borderRadius: '3px',
            width: '18px',
            height: '18px',
            cursor: 'pointer',
            padding: 0,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            backgroundColor: t.status === 'done' ? 'var(--ok)' : 'transparent',
            color: '#fff',
          }}
        >
          {t.status === 'done' && <Check size={12} />}
        </button>
      ),
    },
    { key: 'title', header: 'Title', render: (t) => <span style={{ fontWeight: 500, textDecoration: t.status === 'done' ? 'line-through' : 'none', opacity: t.status === 'done' ? 0.6 : 1 }}>{t.title}</span> },
    {
      key: 'due_date',
      header: 'Due Date',
      sortable: true,
      render: (t) => t.due_date ? formatDate(t.due_date) : '—',
    },
    {
      key: 'status',
      header: 'Status',
      sortable: true,
      render: (t) => <Badge variant={TASK_STATUS_VARIANT[t.status] || 'info'} dot>{t.status.replace('_', ' ')}</Badge>,
    },
    { key: 'assignee_name', header: 'Assignee' },
    {
      key: 'related_to_name',
      header: 'Related To',
      render: (t) => t.related_to_name || '—',
    },
  ]

  return (
    <ErrorBoundary>
      <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '12px' }}>
          <div>
            <h1 style={{ fontSize: '1.5rem', fontWeight: 700, color: 'var(--text)' }}>Activities</h1>
            <p style={{ fontSize: '0.85rem', color: 'var(--text-muted)', marginTop: '2px' }}>
              {activeTab === 'activities' ? activities.length : tasks.length} {activeTab === 'activities' ? 'activities' : 'tasks'}
            </p>
          </div>
          <button
            onClick={() => activeTab === 'activities' ? setAddActivityOpen(true) : setAddTaskOpen(true)}
            style={priBtnStyle}
          >
            <Plus size={16} /> Add {activeTab === 'activities' ? 'Activity' : 'Task'}
          </button>
        </div>

        {/* Tab bar */}
        <div style={{ display: 'flex', gap: '0', borderBottom: '1px solid var(--border)' }}>
          {(['activities', 'tasks'] as TabKey[]).map((tab) => (
            <button
              key={tab}
              onClick={() => setActiveTab(tab)}
              style={{
                padding: '10px 20px',
                background: 'none',
                border: 'none',
                borderBottom: activeTab === tab ? '2px solid var(--accent)' : '2px solid transparent',
                color: activeTab === tab ? 'var(--accent)' : 'var(--text-muted)',
                fontSize: '0.85rem',
                fontWeight: activeTab === tab ? 600 : 400,
                cursor: 'pointer',
                textTransform: 'capitalize',
              }}
            >
              {tab}
            </button>
          ))}
        </div>

        {error && <div style={errorBannerStyle}>{error}</div>}

        {isLoading ? (
          <LoadingSpinner message={`Loading ${activeTab}...`} />
        ) : activeTab === 'activities' ? (
          activities.length === 0 ? (
            <EmptyState
              icon={<ClipboardList size={48} />}
              title="No activities"
              description="Log your first activity."
              action={<button onClick={() => setAddActivityOpen(true)} style={priBtnStyle}><Plus size={16} /> Add Activity</button>}
            />
          ) : (
            <DataTable columns={activityColumns} data={activities} keyExtractor={(a) => a.id} pageSize={20} />
          )
        ) : (
          tasks.length === 0 ? (
            <EmptyState
              icon={<CheckSquare size={48} />}
              title="No tasks"
              description="Create your first task."
              action={<button onClick={() => setAddTaskOpen(true)} style={priBtnStyle}><Plus size={16} /> Add Task</button>}
            />
          ) : (
            <DataTable columns={taskColumns} data={tasks} keyExtractor={(t) => t.id} pageSize={20} />
          )
        )}

        {/* Add Activity Modal */}
        <Modal open={addActivityOpen} onClose={() => setAddActivityOpen(false)} title="Add Activity" maxWidth="500px">
          <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
            <div>
              <label style={labelStyle}>Type</label>
              <select value={newActivity.activity_type} onChange={(e) => setNewActivity((p) => ({ ...p, activity_type: e.target.value }))} style={selectStyle}>
                <option value="note">Note</option>
                <option value="call">Call</option>
                <option value="meeting">Meeting</option>
                <option value="email">Email</option>
              </select>
            </div>
            <Field label="Subject" value={newActivity.subject} onChange={(v) => setNewActivity((p) => ({ ...p, subject: v }))} />
            <div>
              <label style={labelStyle}>Body</label>
              <textarea
                value={newActivity.body}
                onChange={(e) => setNewActivity((p) => ({ ...p, body: e.target.value }))}
                rows={3}
                style={{ ...inputStyle, resize: 'vertical' } as React.CSSProperties}
              />
            </div>
            <div style={{ display: 'flex', gap: '10px', justifyContent: 'flex-end', marginTop: '8px' }}>
              <button onClick={() => setAddActivityOpen(false)} style={secBtnStyle}>Cancel</button>
              <button onClick={handleAddActivity} disabled={saving || !newActivity.subject.trim()} style={priBtnStyle}>
                {saving ? 'Saving...' : 'Save'}
              </button>
            </div>
          </div>
        </Modal>

        {/* Add Task Modal */}
        <Modal open={addTaskOpen} onClose={() => setAddTaskOpen(false)} title="Add Task" maxWidth="500px">
          <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
            <Field label="Title" value={newTask.title} onChange={(v) => setNewTask((p) => ({ ...p, title: v }))} />
            <Field label="Due Date" value={newTask.due_date} onChange={(v) => setNewTask((p) => ({ ...p, due_date: v }))} type="date" />
            <Field label="Assignee ID" value={newTask.assignee_id} onChange={(v) => setNewTask((p) => ({ ...p, assignee_id: v }))} type="number" />
            <div style={{ display: 'flex', gap: '10px', justifyContent: 'flex-end', marginTop: '8px' }}>
              <button onClick={() => setAddTaskOpen(false)} style={secBtnStyle}>Cancel</button>
              <button onClick={handleAddTask} disabled={saving || !newTask.title.trim()} style={priBtnStyle}>
                {saving ? 'Saving...' : 'Save'}
              </button>
            </div>
          </div>
        </Modal>
      </div>
    </ErrorBoundary>
  )
}

function Field({ label, value, onChange, type = 'text' }: { label: string; value: string; onChange: (v: string) => void; type?: string }) {
  return (
    <div>
      <label style={labelStyle}>{label}</label>
      <input type={type} value={value} onChange={(e) => onChange(e.target.value)} style={inputStyle}
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
