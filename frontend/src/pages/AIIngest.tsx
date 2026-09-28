import { useState, useRef, useCallback } from 'react'
import { Upload, FileText, Check, X, XCircle, AlertTriangle, Loader2, ArrowLeftRight } from 'lucide-react'
import api from '../api/client'
import { formatCurrency, cn } from '../lib/utils'
import Card from '../components/ui/Card'
import Badge from '../components/ui/Badge'
import ErrorBoundary from '../components/ui/ErrorBoundary'

interface IngestStatus {
  task_id: string
  status: 'pending' | 'processing' | 'completed' | 'failed'
  progress: number
  provider?: string
  model?: string
  extracted_data?: Record<string, unknown>[]
  error_message?: string
  is_high_value: boolean
}

type DocType = 'supplier_invoice' | 'supplier_receipt' | 'client_receipt'

const DOC_TYPE_LABELS: Record<DocType, string> = {
  supplier_invoice: 'Supplier Invoice',
  supplier_receipt: 'Supplier Receipt / Delivery Note',
  client_receipt: 'Client / Patient Receipt',
}

const POLL_INTERVAL_MS = 2000

export default function AIIngest() {
  const [dragOver, setDragOver] = useState(false)
  const [file, setFile] = useState<File | null>(null)
  const [docType, setDocType] = useState<DocType>('supplier_invoice')
  const [uploading, setUploading] = useState(false)
  const [status, setStatus] = useState<IngestStatus | null>(null)
  const [editableData, setEditableData] = useState<Record<string, unknown>[]>([])
  const [documentInfo, setDocumentInfo] = useState<Record<string, unknown> | null>(null)
  const [auditId, setAuditId] = useState<string | null>(null)
  const [committing, setCommitting] = useState(false)
  const [commitResult, setCommitResult] = useState<string>('')
  const [error, setError] = useState('')
  const fileInputRef = useRef<HTMLInputElement>(null)

  const handleFile = useCallback(async (f: File) => {
    if (!['application/pdf', 'image/jpeg', 'image/png', 'image/jpg'].includes(f.type)) {
      setError('Please upload a PDF or JPG/PNG image file.')
      return
    }
    setFile(f)
    setError('')
    setUploading(true)
    setStatus(null)
    setCommitResult('')

    try {
      const formData = new FormData()
      formData.append('file', f)
      formData.append('doc_type', docType)
      const result = await api.post<IngestStatus>('/ingest/', formData)
      setStatus(result)

      // Apply one status snapshot; returns true when processing is finished.
      const processStatus = async (s: IngestStatus): Promise<boolean> => {
        setStatus(s)
        if (s.status === 'completed') {
          // Backend nests the audit payload inside a `data` wrapper
          const extracted = (s as any).data?.extracted_data || s.extracted_data
          const statusData = (s as any).data
          if (statusData?.id) setAuditId(statusData.id)
          // Separate header info from line items
          if (extracted && extracted.line_items) {
            const { line_items, ...header } = extracted
            setDocumentInfo(header)
            setEditableData(line_items || [])
          } else {
            setDocumentInfo(null)
            setEditableData(extracted || [])
          }
          return true
        }
        if (s.status === 'failed') {
          const errMsg = (s as any).data?.error_message || s.error_message || 'AI processing failed.'
          setError(errMsg)
          return true
        }
        return false
      }

      if (!result.task_id && result.status === 'completed') {
        // Broker unavailable: the backend processed the document synchronously
        // and returned no task id — fetch the audit result directly.
        const s = await api.get<IngestStatus>('/ingest/status/')
        await processStatus(s)
      } else if (result.task_id) {
        // Start polling
        const poll = setInterval(async () => {
          try {
            const s = await api.get<IngestStatus>(`/ingest/${result.task_id}/status/`)
            if (await processStatus(s)) clearInterval(poll)
          } catch {
            clearInterval(poll)
            setError('Failed to check ingestion status.')
          }
        }, POLL_INTERVAL_MS)
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Upload failed.'
      setError(msg)
    } finally {
      setUploading(false)
    }
  }, [])

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault()
      setDragOver(false)
      const f = e.dataTransfer.files?.[0]
      if (f) handleFile(f)
    },
    [handleFile],
  )

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault()
    setDragOver(true)
  }

  const handleDragLeave = () => setDragOver(false)

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0]
    if (f) handleFile(f)
  }

  const handleCellEdit = (rowIdx: number, key: string, value: string) => {
    setEditableData((prev) => {
      const next = [...prev]
      next[rowIdx] = { ...next[rowIdx], [key]: value }
      return next
    })
  }

  const handleCommit = async () => {
    if (!auditId) {
      setError('No audit record found. Cannot commit.')
      return
    }
    setCommitting(true)
    setError('')
    try {
      const result = await api.post<{ message: string }>('/ingest/commit/', {
        audit_id: auditId,
      })
      setCommitResult(result.message || 'Data committed successfully.')
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Commit failed.'
      setError(msg)
    } finally {
      setCommitting(false)
    }
  }

  const reset = () => {
    setFile(null)
    setStatus(null)
    setEditableData([])
    setDocumentInfo(null)
    setAuditId(null)
    setCommitResult('')
    setError('')
  }

  return (
    <ErrorBoundary>
      <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
        <div>
          <h1 style={{ fontSize: '1.5rem', fontWeight: 700, color: 'var(--text)' }}>AI Document Ingest</h1>
          <p style={{ fontSize: '0.85rem', color: 'var(--text-muted)', marginTop: '2px' }}>
            Upload supplier invoices, receipts, or client/patient receipts — AI extracts and validates the data
          </p>
        </div>

        {/* Document type toggle */}
        <Card padding="16px">
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px', flexWrap: 'wrap' }}>
            <span style={{ fontSize: '0.8rem', fontWeight: 600, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
              <ArrowLeftRight size={14} style={{ marginRight: '4px', verticalAlign: 'middle' }} />
              Document Type
            </span>
            {(['supplier_invoice', 'supplier_receipt', 'client_receipt'] as DocType[]).map((dt) => (
              <button
                key={dt}
                onClick={() => setDocType(dt)}
                style={{
                  padding: '8px 16px',
                  borderRadius: 'var(--radius-md)',
                  fontSize: '0.82rem',
                  fontWeight: docType === dt ? 600 : 400,
                  border: docType === dt ? '2px solid var(--accent)' : '1px solid var(--border)',
                  backgroundColor: docType === dt ? 'color-mix(in srgb, var(--accent) 12%, transparent)' : 'var(--surface-2)',
                  color: docType === dt ? 'var(--accent)' : 'var(--text-muted)',
                  cursor: 'pointer',
                  transition: 'all 150ms ease',
                }}
              >
                {dt === 'supplier_invoice' && <FileText size={14} style={{ marginRight: '4px', verticalAlign: 'middle' }} />}
                {DOC_TYPE_LABELS[dt]}
              </button>
            ))}
          </div>
          <p style={{ fontSize: '0.72rem', color: 'var(--text-muted)', marginTop: '8px' }}>
            {docType === 'supplier_invoice'
              ? 'LLM will extract: supplier name, invoice date, line items with quantities and costs.'
              : docType === 'supplier_receipt'
              ? 'LLM will extract: supplier name, delivery date, order reference, batch numbers, expiry dates.'
              : 'LLM will extract: customer name, receipt date, items purchased, payment method, total.'}
          </p>
        </Card>

        {error && (
          <div style={{
            backgroundColor: 'color-mix(in srgb, var(--danger) 12%, transparent)',
            color: 'var(--danger)',
            padding: '10px 16px',
            borderRadius: 'var(--radius-md)',
            fontSize: '0.85rem',
            border: '1px solid color-mix(in srgb, var(--danger) 25%, transparent)',
          }}>
            {error}
          </div>
        )}

        {commitResult && (
          <div style={{
            backgroundColor: 'color-mix(in srgb, var(--ok) 12%, transparent)',
            color: 'var(--ok)',
            padding: '10px 16px',
            borderRadius: 'var(--radius-md)',
            fontSize: '0.85rem',
            border: '1px solid color-mix(in srgb, var(--ok) 25%, transparent)',
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
          }}>
            <Check size={16} />
            {commitResult}
          </div>
        )}

        {/* Drop zone */}
        {!status && !file && (
          <Card>
            <div
              onDrop={handleDrop}
              onDragOver={handleDragOver}
              onDragLeave={handleDragLeave}
              onClick={() => fileInputRef.current?.click()}
              style={{
                border: `2px dashed ${dragOver ? 'var(--accent)' : 'var(--border)'}`,
                borderRadius: 'var(--radius-lg)',
                padding: '60px 20px',
                textAlign: 'center',
                cursor: 'pointer',
                backgroundColor: dragOver ? 'color-mix(in srgb, var(--accent) 5%, transparent)' : 'var(--surface-2)',
                transition: 'all 200ms ease',
              }}
            >
              <Upload size={40} style={{ color: 'var(--text-muted)', marginBottom: '12px' }} />
              <h3 style={{ fontSize: '1rem', fontWeight: 600, color: 'var(--text)', marginBottom: '4px' }}>
                Drop {docType === 'client_receipt' ? 'client receipt' : 'supplier document'} here
              </h3>
              <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
                PDF, JPG, or PNG (max 10 MB) — data will be editable before saving
              </p>
              <input
                ref={fileInputRef}
                type="file"
                accept=".pdf,.jpg,.jpeg,.png"
                onChange={handleFileChange}
                style={{ display: 'none' }}
              />
            </div>
          </Card>
        )}

        {/* Uploading / Processing */}
        {uploading && (
          <Card title="Uploading...">
            <div style={{ display: 'flex', alignItems: 'center', gap: '12px', padding: '20px' }}>
              <Loader2 size={24} style={{ animation: 'hdaos-spin 0.7s linear infinite', color: 'var(--accent)' }} />
              <span style={{ color: 'var(--text)' }}>Uploading {file?.name}...</span>
              <style>{`@keyframes hdaos-spin { to { transform: rotate(360deg); } }`}</style>
            </div>
          </Card>
        )}

        {/* Processing status */}
        {status && (status.status === 'pending' || status.status === 'processing') && (
          <Card title="AI Processing">
            <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <Loader2 size={18} style={{ animation: 'hdaos-spin 0.7s linear infinite', color: 'var(--accent)' }} />
                <span style={{ color: 'var(--text)', fontSize: '0.9rem' }}>
                  {status.status === 'pending' ? 'Queued...' : 'Extracting invoice data...'}
                </span>
              </div>
              {/* Progress bar */}
              <div style={{
                width: '100%',
                height: '6px',
                backgroundColor: 'var(--surface-2)',
                borderRadius: '3px',
                overflow: 'hidden',
              }}>
                <div
                  style={{
                    height: '100%',
                    width: `${status.progress}%`,
                    backgroundColor: 'var(--accent)',
                    borderRadius: '3px',
                    transition: 'width 300ms ease',
                  }}
                />
              </div>
              <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                {status.progress}%
              </span>
            </div>
          </Card>
        )}

        {/* Failed */}
        {status?.status === 'failed' && (
          <Card title="Processing Failed">
            <div style={{ display: 'flex', alignItems: 'center', gap: '12px', padding: '16px' }}>
              <XCircle size={24} style={{ color: 'var(--danger)' }} />
              <span style={{ color: 'var(--danger)' }}>{status.error_message || 'Unknown error'}</span>
            </div>
            <button onClick={reset} style={{
              marginTop: '12px',
              padding: '8px 16px',
              backgroundColor: 'var(--accent)',
              color: '#fff',
              border: 'none',
              borderRadius: 'var(--radius-md)',
              fontSize: '0.85rem',
              fontWeight: 600,
              cursor: 'pointer',
            }}>
              Try Again
            </button>
          </Card>
        )}

        {/* Completed - editable table */}
        {status?.status === 'completed' && (editableData.length > 0 || documentInfo) && (
          <Card
            title="Extracted Data"
            action={
              <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
                {status.provider && <Badge variant="accent">{status.provider}</Badge>}
                {status.model && <Badge variant="info">{status.model}</Badge>}
                {auditId && <Badge variant="ok" size="sm">Audit #{auditId.slice(0,8)}</Badge>}
              </div>
            }
          >
            {/* High value warning */}
            {status.is_high_value && (
              <div style={{
                display: 'flex',
                alignItems: 'center',
                gap: '8px',
                padding: '10px 14px',
                backgroundColor: 'color-mix(in srgb, var(--warn) 10%, transparent)',
                border: '1px solid color-mix(in srgb, var(--warn) 20%, transparent)',
                borderRadius: 'var(--radius-md)',
                marginBottom: '12px',
                fontSize: '0.85rem',
              }}>
                <AlertTriangle size={16} style={{ color: 'var(--warn)' }} />
                <span style={{ color: 'var(--warn)' }}>
                  High value invoice detected. This will require approval before being committed.
                </span>
              </div>
            )}

            {/* Document header info (supplier, invoice #, totals) — editable */}
            {documentInfo && (
              <div style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
                gap: '12px',
                padding: '14px',
                backgroundColor: 'var(--surface-2)',
                borderRadius: 'var(--radius-md)',
                marginBottom: '16px',
              }}>
                {Object.entries(documentInfo).filter(([k]) => k !== 'line_items').map(([key, val]) => (
                  <div key={key}>
                    <label style={{ fontSize: '0.7rem', fontWeight: 500, color: 'var(--text-muted)', marginBottom: '2px', textTransform: 'capitalize', display: 'block' }}>
                      {key.replace(/_/g, ' ')}
                    </label>
                    <input
                      type="text"
                      value={String(val ?? '')}
                      onChange={(e) => {
                        const newVal = e.target.value
                        setDocumentInfo(prev => prev ? { ...prev, [key]: newVal } : prev)
                      }}
                      style={{
                        width: '100%',
                        padding: '6px 8px',
                        backgroundColor: 'var(--surface)',
                        border: '1px solid var(--border)',
                        borderRadius: 'var(--radius-sm)',
                        color: 'var(--text)',
                        fontSize: '0.85rem',
                        fontWeight: 600,
                        outline: 'none',
                        boxSizing: 'border-box',
                      }}
                      onFocus={(e) => { e.currentTarget.style.borderColor = 'var(--accent)' }}
                      onBlur={(e) => { e.currentTarget.style.borderColor = 'var(--border)' }}
                    />
                  </div>
                ))}
              </div>
            )}

            {/* Editable table */}
            {editableData.length > 0 && (
              <div style={{ overflowX: 'auto' }}>
                <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                  <thead>
                    <tr style={{ borderBottom: '1px solid var(--border)' }}>
                      {Object.keys(editableData[0]).map((key) => (
                        <th key={key} style={{
                          padding: '8px 12px',
                          textAlign: 'left',
                          fontSize: '0.75rem',
                          fontWeight: 600,
                          color: 'var(--text-muted)',
                          textTransform: 'uppercase',
                        }}>
                          {key}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {editableData.map((row, rowIdx) => (
                      <tr key={rowIdx} style={{ borderBottom: '1px solid var(--border)' }}>
                        {Object.keys(row).map((key) => (
                          <td key={key} style={{ padding: '6px 12px' }}>
                            <input
                              type="text"
                              value={String(row[key] ?? '')}
                              onChange={(e) => handleCellEdit(rowIdx, key, e.target.value)}
                              style={{
                                width: '100%',
                                padding: '4px 8px',
                                backgroundColor: 'var(--surface-2)',
                                border: '1px solid var(--border)',
                                borderRadius: 'var(--radius-sm)',
                                color: 'var(--text)',
                                fontSize: '0.8rem',
                                outline: 'none',
                                boxSizing: 'border-box',
                              }}
                              onFocus={(e) => { e.currentTarget.style.borderColor = 'var(--accent)' }}
                              onBlur={(e) => { e.currentTarget.style.borderColor = 'var(--border)' }}
                            />
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}

            <div style={{ display: 'flex', gap: '10px', marginTop: '16px', justifyContent: 'flex-end' }}>
              <button onClick={reset} style={{
                padding: '8px 16px',
                backgroundColor: 'transparent',
                color: 'var(--text-muted)',
                border: '1px solid var(--border)',
                borderRadius: 'var(--radius-md)',
                fontSize: '0.85rem',
                cursor: 'pointer',
              }}>
                Discard
              </button>
              <button
                onClick={handleCommit}
                disabled={committing}
                style={{
                  padding: '8px 20px',
                  backgroundColor: 'var(--accent)',
                  color: '#fff',
                  border: 'none',
                  borderRadius: 'var(--radius-md)',
                  fontSize: '0.85rem',
                  fontWeight: 600,
                  cursor: committing ? 'wait' : 'pointer',
                  opacity: committing ? 0.7 : 1,
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: '6px',
                }}
              >
                <Check size={16} />
                {committing ? 'Committing...' : 'Commit'}
              </button>
            </div>
          </Card>
        )}
      </div>
    </ErrorBoundary>
  )
}
