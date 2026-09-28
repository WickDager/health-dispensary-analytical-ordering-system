import { useState, type FormEvent } from 'react'
import { Link } from 'react-router-dom'
import { useAuth } from '../hooks/useAuth'
import { ApiError } from '../api/client'
import type { RegisterData } from '../context/AuthContext'

export default function Register() {
  const { register, isAuthenticated } = useAuth()
  const [form, setForm] = useState<RegisterData>({
    username: '',
    email: '',
    password: '',
    first_name: '',
    last_name: '',
    role: 'sales',
  })
  const [confirmPassword, setConfirmPassword] = useState('')
  const [error, setError] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [success, setSuccess] = useState(false)

  const update = (field: keyof RegisterData, value: string) => {
    setForm((prev) => ({ ...prev, [field]: value }))
  }

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault()
    setError('')

    if (!form.username.trim() || !form.email.trim() || !form.password.trim()) {
      setError('Please fill in all required fields.')
      return
    }

    if (form.password !== confirmPassword) {
      setError('Passwords do not match.')
      return
    }

    if (form.password.length < 8) {
      setError('Password must be at least 8 characters.')
      return
    }

    setSubmitting(true)
    try {
      await register(form)
      setSuccess(true)
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.message || 'Registration failed.')
      } else {
        setError('An unexpected error occurred.')
      }
    } finally {
      setSubmitting(false)
    }
  }

  if (isAuthenticated) {
    return null
  }

  if (success) {
    return (
      <div
        style={{
          minHeight: '100vh',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          backgroundColor: 'var(--bg)',
          padding: '20px',
        }}
      >
        <div
          style={{
            width: '100%',
            maxWidth: '440px',
            backgroundColor: 'var(--surface)',
            border: '1px solid var(--border)',
            borderRadius: 'var(--radius-lg)',
            boxShadow: 'var(--shadow-md)',
            padding: '40px',
            textAlign: 'center',
          }}
        >
          <div
            style={{
              width: '56px',
              height: '56px',
              borderRadius: '50%',
              backgroundColor: 'color-mix(in srgb, var(--ok) 15%, transparent)',
              color: 'var(--ok)',
              display: 'inline-flex',
              alignItems: 'center',
              justifyContent: 'center',
              fontSize: '1.5rem',
              marginBottom: '16px',
            }}
          >
            &#10003;
          </div>
          <h2 style={{ fontSize: '1.2rem', fontWeight: 600, color: 'var(--text)', marginBottom: '8px' }}>
            Registration Submitted
          </h2>
          <p style={{ fontSize: '0.85rem', color: 'var(--text-muted)', lineHeight: 1.6 }}>
            Your account request has been submitted for review. An administrator will approve
            your account shortly. You will be notified once your account is active.
          </p>
          <Link
            to="/login"
            style={{
              display: 'inline-block',
              marginTop: '24px',
              color: 'var(--accent)',
              fontWeight: 600,
              fontSize: '0.9rem',
            }}
          >
            Return to login
          </Link>
        </div>
      </div>
    )
  }

  const inputStyle = {
    width: '100%',
    padding: '10px 12px',
    backgroundColor: 'var(--surface-2)',
    border: '1px solid var(--border)',
    borderRadius: 'var(--radius-md)',
    color: 'var(--text)',
    fontSize: '0.9rem',
    outline: 'none',
    boxSizing: 'border-box' as const,
  }

  const labelStyle = {
    display: 'block',
    fontSize: '0.85rem',
    fontWeight: 500,
    color: 'var(--text)',
    marginBottom: '6px',
  }

  return (
    <div
      style={{
        minHeight: '100vh',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        backgroundColor: 'var(--bg)',
        padding: '20px',
      }}
    >
      <div
        style={{
          width: '100%',
          maxWidth: '480px',
          backgroundColor: 'var(--surface)',
          border: '1px solid var(--border)',
          borderRadius: 'var(--radius-lg)',
          boxShadow: 'var(--shadow-md)',
          padding: '40px',
        }}
      >
        <div style={{ textAlign: 'center', marginBottom: '28px' }}>
          <div
            style={{
              width: '48px',
              height: '48px',
              borderRadius: 'var(--radius-md)',
              backgroundColor: 'var(--accent)',
              display: 'inline-flex',
              alignItems: 'center',
              justifyContent: 'center',
              fontSize: '1.3rem',
              fontWeight: 700,
              color: '#fff',
              marginBottom: '12px',
            }}
          >
            H
          </div>
          <h1 style={{ fontSize: '1.3rem', fontWeight: 700, color: 'var(--text)' }}>
            Request Access
          </h1>
          <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginTop: '4px' }}>
            Create an account to access HDAOS
          </p>
        </div>

        {error && (
          <div
            style={{
              backgroundColor: 'color-mix(in srgb, var(--danger) 12%, transparent)',
              color: 'var(--danger)',
              padding: '10px 14px',
              borderRadius: 'var(--radius-md)',
              fontSize: '0.85rem',
              marginBottom: '16px',
              border: '1px solid color-mix(in srgb, var(--danger) 25%, transparent)',
            }}
          >
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit}>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px', marginBottom: '12px' }}>
            <div>
              <label htmlFor="first_name" style={labelStyle}>First Name *</label>
              <input id="first_name" type="text" value={form.first_name} onChange={(e) => update('first_name', e.target.value)} style={inputStyle} required />
            </div>
            <div>
              <label htmlFor="last_name" style={labelStyle}>Last Name *</label>
              <input id="last_name" type="text" value={form.last_name} onChange={(e) => update('last_name', e.target.value)} style={inputStyle} required />
            </div>
          </div>

          <div style={{ marginBottom: '12px' }}>
            <label htmlFor="username" style={labelStyle}>Username *</label>
            <input id="username" type="text" value={form.username} onChange={(e) => update('username', e.target.value)} style={inputStyle} autoComplete="username" required />
          </div>

          <div style={{ marginBottom: '12px' }}>
            <label htmlFor="email" style={labelStyle}>Email *</label>
            <input id="email" type="email" value={form.email} onChange={(e) => update('email', e.target.value)} style={inputStyle} autoComplete="email" required />
          </div>

          <div style={{ marginBottom: '12px' }}>
            <label htmlFor="role" style={labelStyle}>Role</label>
            <select
              id="role"
              value={form.role}
              onChange={(e) => update('role', e.target.value)}
              style={inputStyle}
            >
              <option value="sales">Sales</option>
              <option value="procurement">Procurement</option>
              <option value="logistics">Logistics</option>
              <option value="pharmacist">Pharmacist</option>
            </select>
          </div>

          <div style={{ marginBottom: '12px' }}>
            <label htmlFor="password" style={labelStyle}>Password *</label>
            <input id="password" type="password" value={form.password} onChange={(e) => update('password', e.target.value)} style={inputStyle} autoComplete="new-password" required />
          </div>

          <div style={{ marginBottom: '20px' }}>
            <label htmlFor="confirm_password" style={labelStyle}>Confirm Password *</label>
            <input id="confirm_password" type="password" value={confirmPassword} onChange={(e) => setConfirmPassword(e.target.value)} style={inputStyle} autoComplete="new-password" required />
          </div>

          <button
            type="submit"
            disabled={submitting}
            style={{
              width: '100%',
              padding: '10px',
              backgroundColor: 'var(--accent)',
              color: '#fff',
              border: 'none',
              borderRadius: 'var(--radius-md)',
              fontSize: '0.9rem',
              fontWeight: 600,
              cursor: submitting ? 'wait' : 'pointer',
              opacity: submitting ? 0.7 : 1,
            }}
          >
            {submitting ? 'Submitting...' : 'Request Access'}
          </button>
        </form>

        <p style={{ textAlign: 'center', marginTop: '20px', fontSize: '0.85rem', color: 'var(--text-muted)' }}>
          Already have an account?{' '}
          <Link to="/login" style={{ color: 'var(--accent)', fontWeight: 500 }}>
            Sign in
          </Link>
        </p>
      </div>
    </div>
  )
}
