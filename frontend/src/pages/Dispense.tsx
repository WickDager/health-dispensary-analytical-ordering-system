import { useState, useEffect, useCallback, useRef } from 'react'
import { Search, Check, AlertTriangle, Package } from 'lucide-react'
import api, { extractResults } from '../api/client'
import { formatDate, formatCurrency, cn } from '../lib/utils'
import Card from '../components/ui/Card'
import Badge from '../components/ui/Badge'
import Stepper from '../components/ui/Stepper'
import LoadingSpinner from '../components/ui/LoadingSpinner'
import ErrorBoundary from '../components/ui/ErrorBoundary'

interface ProductOption {
  id: string
  name: string
  api: string
  strength: string
  soh: number
}

interface FefoLot {
  lot_id: string
  batch_number: string
  expiry_date: string
  available: number
  allocated_quantity: number
}

interface DispenseResult {
  total_dispensed: number
  allocations: { lot_id: string; batch_number: string; qty: number; expiry_date: string }[]
}

const STEPS = [
  { label: 'Search Drug', description: 'Find the product' },
  { label: 'Enter Details', description: 'Quantity & MRN' },
  { label: 'Review FEFO', description: 'Verify allocation' },
  { label: 'Confirm', description: 'Complete dispense' },
]

export default function Dispense() {
  const [activeStep, setActiveStep] = useState(0)
  const [search, setSearch] = useState('')
  const [searchResults, setSearchResults] = useState<ProductOption[]>([])
  const [searching, setSearching] = useState(false)
  const [selectedProduct, setSelectedProduct] = useState<ProductOption | null>(null)
  const [quantity, setQuantity] = useState('')
  const [mrn, setMrn] = useState('')
  const [fefoLots, setFefoLots] = useState<FefoLot[]>([])
  const [suggestedAllocation, setSuggestedAllocation] = useState<FefoLot[]>([])
  const [loadingAllocation, setLoadingAllocation] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [result, setResult] = useState<DispenseResult | null>(null)
  const [error, setError] = useState('')
  const searchTimeout = useRef<ReturnType<typeof setTimeout> | null>(null)

  // Debounced product search
  useEffect(() => {
    if (!search.trim() || search.trim().length < 2) {
      setSearchResults([])
      return
    }
    if (searchTimeout.current) clearTimeout(searchTimeout.current)
    searchTimeout.current = setTimeout(async () => {
      setSearching(true)
      try {
        const data = await api.get<ProductOption[]>(`/products/?search=${encodeURIComponent(search.trim())}&limit=10`)
        setSearchResults(extractResults(data))
      } catch {
        setSearchResults([])
      } finally {
        setSearching(false)
      }
    }, 300)
    return () => {
      if (searchTimeout.current) clearTimeout(searchTimeout.current)
    }
  }, [search])

  const selectProduct = (p: ProductOption) => {
    setSelectedProduct(p)
    setSearch(p.name)
    setSearchResults([])
    setError('')
  }

  // Suggest FEFO allocation (client-side allocation over the server's
  // FEFO-ordered lot list, earliest expiry first)
  const suggestFefo = useCallback(async () => {
    if (!selectedProduct || !quantity || isNaN(Number(quantity)) || Number(quantity) <= 0) return
    setLoadingAllocation(true)
    setError('')
    try {
      const data = await api.get<{ lots: FefoLot[] }>(
        `/lots/fefo_suggestion/?product_id=${selectedProduct.id}`
      )
      let remaining = Number(quantity)
      const allocated: FefoLot[] = (data.lots || [])
        .map((l) => {
          const take = Math.min(l.available, remaining)
          remaining -= take
          return { ...l, allocated_quantity: take }
        })
        .filter((l) => l.allocated_quantity > 0)
      setFefoLots(data.lots || [])
      setSuggestedAllocation(allocated)
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to get FEFO suggestion.'
      setError(msg)
    } finally {
      setLoadingAllocation(false)
    }
  }, [selectedProduct, quantity])

  const goNext = () => {
    if (activeStep === 1) {
      if (!selectedProduct) { setError('Please select a product.'); return }
      if (!quantity || isNaN(Number(quantity)) || Number(quantity) <= 0) { setError('Enter a valid quantity.'); return }
      if (!mrn.trim()) { setError('Please enter an MRN.'); return }
      setError('')
      suggestFefo()
    }
    setActiveStep((s) => Math.min(STEPS.length - 1, s + 1))
  }

  const goBack = () => setActiveStep((s) => Math.max(0, s - 1))

  const handleConfirm = async () => {
    setSubmitting(true)
    setError('')
    try {
      const data = await api.post<DispenseResult>('/lots/dispense/', {
        product_id: selectedProduct!.id,
        quantity: Number(quantity),
        mrn: mrn.trim(),
      })
      setResult(data)
      setActiveStep(3)
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Dispense failed.'
      setError(msg)
    } finally {
      setSubmitting(false)
    }
  }

  const reset = () => {
    setActiveStep(0)
    setSearch('')
    setSearchResults([])
    setSelectedProduct(null)
    setQuantity('')
    setMrn('')
    setFefoLots([])
    setSuggestedAllocation([])
    setResult(null)
    setError('')
  }

  return (
    <ErrorBoundary>
      <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
        <div>
          <h1 style={{ fontSize: '1.5rem', fontWeight: 700, color: 'var(--text)' }}>Dispense</h1>
          <p style={{ fontSize: '0.85rem', color: 'var(--text-muted)', marginTop: '2px' }}>
            FEFO-based medication dispensing workflow
          </p>
        </div>

        <Card>
          <Stepper steps={STEPS} activeStep={activeStep} />
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

        {/* Step 0: Search Drug */}
        {activeStep === 0 && (
          <Card title="Select Product">
            <div style={{ position: 'relative' }}>
              <Search
                size={16}
                style={{
                  position: 'absolute',
                  left: '12px',
                  top: '50%',
                  transform: 'translateY(-50%)',
                  color: 'var(--text-muted)',
                }}
              />
              <input
                type="text"
                placeholder="Search by product name, API, or strength..."
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                autoFocus
                style={{
                  width: '100%',
                  padding: '10px 14px 10px 38px',
                  backgroundColor: 'var(--surface-2)',
                  border: '1px solid var(--border)',
                  borderRadius: 'var(--radius-md)',
                  color: 'var(--text)',
                  fontSize: '0.9rem',
                  outline: 'none',
                  boxSizing: 'border-box',
                }}
                onFocus={(e) => { e.currentTarget.style.borderColor = 'var(--accent)' }}
                onBlur={(e) => { e.currentTarget.style.borderColor = 'var(--border)' }}
              />
              {searching && (
                <div style={{ position: 'absolute', right: '12px', top: '50%', transform: 'translateY(-50%)' }}>
                  <LoadingSpinner size={16} />
                </div>
              )}
            </div>

            {/* Results dropdown */}
            {searchResults.length > 0 && (
              <div
                style={{
                  marginTop: '8px',
                  backgroundColor: 'var(--surface)',
                  border: '1px solid var(--border)',
                  borderRadius: 'var(--radius-md)',
                  overflow: 'hidden',
                }}
              >
                {searchResults.map((p) => (
                  <button
                    key={p.id}
                    onClick={() => selectProduct(p)}
                    style={{
                      width: '100%',
                      textAlign: 'left',
                      padding: '12px 14px',
                      background: 'none',
                      border: 'none',
                      borderBottom: '1px solid var(--border)',
                      cursor: 'pointer',
                      display: 'flex',
                      justifyContent: 'space-between',
                      alignItems: 'center',
                      color: 'var(--text)',
                    }}
                    onMouseEnter={(e) => { (e.currentTarget as HTMLElement).style.backgroundColor = 'var(--surface-2)' }}
                    onMouseLeave={(e) => { (e.currentTarget as HTMLElement).style.backgroundColor = 'transparent' }}
                  >
                    <div>
                      <div style={{ fontWeight: 500 }}>{p.name}</div>
                      <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
                        {p.api} {p.strength}
                      </div>
                    </div>
                    <Badge variant={p.soh > 0 ? 'ok' : 'danger'}>
                      SOH: {p.soh}
                    </Badge>
                  </button>
                ))}
              </div>
            )}

            {selectedProduct && (
              <div
                style={{
                  marginTop: '12px',
                  padding: '12px',
                  backgroundColor: 'color-mix(in srgb, var(--accent) 8%, transparent)',
                  borderRadius: 'var(--radius-md)',
                  border: '1px solid color-mix(in srgb, var(--accent) 20%, transparent)',
                }}
              >
                <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>Selected Product</div>
                <div style={{ fontWeight: 600, color: 'var(--text)' }}>
                  {selectedProduct.name} ({selectedProduct.api} {selectedProduct.strength})
                </div>
                <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
                  Stock On Hand: {selectedProduct.soh}
                </div>
              </div>
            )}

            <div style={{ marginTop: '20px', display: 'flex', justifyContent: 'flex-end' }}>
              <button
                onClick={goNext}
                disabled={!selectedProduct}
                style={{
                  padding: '8px 20px',
                  backgroundColor: selectedProduct ? 'var(--accent)' : 'var(--border)',
                  color: selectedProduct ? '#fff' : 'var(--text-muted)',
                  border: 'none',
                  borderRadius: 'var(--radius-md)',
                  fontSize: '0.85rem',
                  fontWeight: 600,
                  cursor: selectedProduct ? 'pointer' : 'default',
                }}
              >
                Next
              </button>
            </div>
          </Card>
        )}

        {/* Step 1: Enter quantity + MRN */}
        {activeStep === 1 && (
          <Card title="Dispense Details">
            <div style={{ display: 'flex', flexDirection: 'column', gap: '16px', maxWidth: '400px' }}>
              <div>
                <label style={{ display: 'block', fontSize: '0.85rem', fontWeight: 500, color: 'var(--text)', marginBottom: '6px' }}>
                  Quantity to Dispense
                </label>
                <input
                  type="number"
                  min={1}
                  max={selectedProduct?.soh || 9999}
                  value={quantity}
                  onChange={(e) => setQuantity(e.target.value)}
                  style={{
                    width: '100%',
                    padding: '10px 12px',
                    backgroundColor: 'var(--surface-2)',
                    border: '1px solid var(--border)',
                    borderRadius: 'var(--radius-md)',
                    color: 'var(--text)',
                    fontSize: '0.9rem',
                    outline: 'none',
                    boxSizing: 'border-box',
                  }}
                  onFocus={(e) => { e.currentTarget.style.borderColor = 'var(--accent)' }}
                  onBlur={(e) => { e.currentTarget.style.borderColor = 'var(--border)' }}
                />
              </div>
              <div>
                <label style={{ display: 'block', fontSize: '0.85rem', fontWeight: 500, color: 'var(--text)', marginBottom: '6px' }}>
                  MRN (Medical Record Number)
                </label>
                <input
                  type="text"
                  value={mrn}
                  onChange={(e) => setMrn(e.target.value)}
                  placeholder="e.g. MRN-12345"
                  style={{
                    width: '100%',
                    padding: '10px 12px',
                    backgroundColor: 'var(--surface-2)',
                    border: '1px solid var(--border)',
                    borderRadius: 'var(--radius-md)',
                    color: 'var(--text)',
                    fontSize: '0.9rem',
                    outline: 'none',
                    boxSizing: 'border-box',
                  }}
                  onFocus={(e) => { e.currentTarget.style.borderColor = 'var(--accent)' }}
                  onBlur={(e) => { e.currentTarget.style.borderColor = 'var(--border)' }}
                />
              </div>
            </div>
            <div style={{ marginTop: '20px', display: 'flex', justifyContent: 'space-between' }}>
              <button
                onClick={goBack}
                style={{
                  padding: '8px 20px',
                  backgroundColor: 'transparent',
                  color: 'var(--text-muted)',
                  border: '1px solid var(--border)',
                  borderRadius: 'var(--radius-md)',
                  fontSize: '0.85rem',
                  cursor: 'pointer',
                }}
              >
                Back
              </button>
              <button
                onClick={goNext}
                disabled={loadingAllocation}
                style={{
                  padding: '8px 20px',
                  backgroundColor: 'var(--accent)',
                  color: '#fff',
                  border: 'none',
                  borderRadius: 'var(--radius-md)',
                  fontSize: '0.85rem',
                  fontWeight: 600,
                  cursor: loadingAllocation ? 'wait' : 'pointer',
                  opacity: loadingAllocation ? 0.7 : 1,
                }}
              >
                {loadingAllocation ? 'Loading FEFO...' : 'Next'}
              </button>
            </div>
          </Card>
        )}

        {/* Step 2: Review FEFO */}
        {activeStep === 2 && (
          <Card title="FEFO Allocation Review">
            {loadingAllocation ? (
              <LoadingSpinner message="Calculating FEFO allocation..." />
            ) : suggestedAllocation.length === 0 ? (
              <div style={{ textAlign: 'center', padding: '20px', color: 'var(--text-muted)' }}>
                <AlertTriangle size={32} style={{ marginBottom: '8px' }} />
                <p>No lots available for allocation.</p>
              </div>
            ) : (
              <div style={{ overflowX: 'auto' }}>
                <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                  <thead>
                    <tr style={{ borderBottom: '1px solid var(--border)' }}>
                      <th style={thStyle}>Batch #</th>
                      <th style={thStyle}>Expiry Date</th>
                      <th style={thStyle}>Available</th>
                      <th style={thStyle}>Allocated</th>
                    </tr>
                  </thead>
                  <tbody>
                    {suggestedAllocation.map((lot) => {
                      const now = new Date()
                      const exp = new Date(lot.expiry_date)
                      const diffDays = Math.ceil((exp.getTime() - now.getTime()) / (1000 * 60 * 60 * 24))
                      return (
                        <tr key={lot.lot_id} style={{ borderBottom: '1px solid var(--border)' }}>
                          <td style={tdStyle}>
                            <span style={{ fontWeight: 500 }}>{lot.batch_number}</span>
                          </td>
                          <td style={tdStyle}>
                            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                              <span>{formatDate(lot.expiry_date)}</span>
                              <Badge variant={diffDays < 0 ? 'danger' : diffDays <= 60 ? 'warn' : 'ok'}>
                                {diffDays < 0 ? 'Expired' : `${diffDays}d`}
                              </Badge>
                            </div>
                          </td>
                          <td style={tdStyle}>{lot.available}</td>
                          <td style={tdStyle}>
                            <span style={{ fontWeight: 700, color: 'var(--accent)' }}>
                              {lot.allocated_quantity}
                            </span>
                          </td>
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
                <div style={{
                  marginTop: '12px',
                  padding: '12px',
                  backgroundColor: 'color-mix(in srgb, var(--accent) 8%, transparent)',
                  borderRadius: 'var(--radius-md)',
                  fontSize: '0.85rem',
                }}>
                  <strong style={{ color: 'var(--text)' }}>Total to dispense:</strong>{' '}
                  <span style={{ color: 'var(--accent)', fontWeight: 700 }}>
                    {suggestedAllocation.reduce((s, l) => s + l.allocated_quantity, 0)} units
                  </span>{' '}
                  across {suggestedAllocation.length} lot{suggestedAllocation.length !== 1 ? 's' : ''}
                </div>
              </div>
            )}
            <div style={{ marginTop: '20px', display: 'flex', justifyContent: 'space-between' }}>
              <button onClick={goBack} style={secBtnStyle}>Back</button>
              <button onClick={() => setActiveStep(3)} style={priBtnStyle}>
                Next
              </button>
            </div>
          </Card>
        )}

        {/* Step 3: Confirm */}
        {activeStep === 3 && !result && (
          <Card title="Confirm Dispense">
            <div style={{
              padding: '16px',
              backgroundColor: 'color-mix(in srgb, var(--warn) 10%, transparent)',
              borderRadius: 'var(--radius-md)',
              border: '1px solid color-mix(in srgb, var(--warn) 20%, transparent)',
              marginBottom: '16px',
            }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <AlertTriangle size={18} style={{ color: 'var(--warn)' }} />
                <span style={{ fontSize: '0.85rem', color: 'var(--warn)', fontWeight: 500 }}>
                  Please review all details before confirming
                </span>
              </div>
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
              <DetailRow label="Product" value={`${selectedProduct!.name} (${selectedProduct!.api} ${selectedProduct!.strength})`} />
              <DetailRow label="Quantity" value={String(quantity)} />
              <DetailRow label="MRN" value={mrn} />
              <DetailRow label="Lots Used" value={`${suggestedAllocation.length} lot(s)`} />
              <DetailRow label="Lot Numbers" value={suggestedAllocation.map((l) => l.batch_number).join(', ')} />
            </div>
            <div style={{ marginTop: '20px', display: 'flex', justifyContent: 'space-between' }}>
              <button onClick={goBack} style={secBtnStyle}>Back</button>
              <button
                onClick={handleConfirm}
                disabled={submitting}
                style={{
                  padding: '8px 20px',
                  backgroundColor: 'var(--accent)',
                  color: '#fff',
                  border: 'none',
                  borderRadius: 'var(--radius-md)',
                  fontSize: '0.85rem',
                  fontWeight: 600,
                  cursor: submitting ? 'wait' : 'pointer',
                  opacity: submitting ? 0.7 : 1,
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: '6px',
                }}
              >
                <Check size={16} />
                {submitting ? 'Dispensing...' : 'Confirm Dispense'}
              </button>
            </div>
          </Card>
        )}

        {/* Step 3 alt: Success */}
        {activeStep === 3 && result && (
          <Card title="Dispense Complete">
            <div style={{
              textAlign: 'center',
              padding: '32px 20px',
            }}>
              {/* A failed dispense arrives as an HTTP error and is shown in
                  the error banner, so reaching this card means success. */}
              <div style={{
                width: '56px',
                height: '56px',
                borderRadius: '50%',
                backgroundColor: 'color-mix(in srgb, var(--ok) 15%, transparent)',
                color: 'var(--ok)',
                display: 'inline-flex',
                alignItems: 'center',
                justifyContent: 'center',
                marginBottom: '16px',
              }}>
                <Check size={28} />
              </div>
              <h2 style={{ color: 'var(--text)', fontSize: '1.2rem', fontWeight: 600, marginBottom: '8px' }}>
                Dispense Successful
              </h2>
              <p style={{ color: 'var(--text-muted)', fontSize: '0.9rem', marginBottom: '20px' }}>
                {result.total_dispensed} units dispensed across {result.allocations.length} lot(s).
              </p>
              <button onClick={reset} style={priBtnStyle}>
                New Dispense
              </button>
            </div>
          </Card>
        )}
      </div>
    </ErrorBoundary>
  )
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

const priBtnStyle: React.CSSProperties = {
  padding: '8px 20px',
  backgroundColor: 'var(--accent)',
  color: '#fff',
  border: 'none',
  borderRadius: 'var(--radius-md)',
  fontSize: '0.85rem',
  fontWeight: 600,
  cursor: 'pointer',
}

const secBtnStyle: React.CSSProperties = {
  padding: '8px 20px',
  backgroundColor: 'transparent',
  color: 'var(--text-muted)',
  border: '1px solid var(--border)',
  borderRadius: 'var(--radius-md)',
  fontSize: '0.85rem',
  cursor: 'pointer',
}

function DetailRow({ label, value }: { label: string; value: string }) {
  return (
    <div style={{ display: 'flex', gap: '12px', padding: '6px 0' }}>
      <span style={{ fontSize: '0.85rem', color: 'var(--text-muted)', minWidth: '100px' }}>{label}</span>
      <span style={{ fontSize: '0.85rem', color: 'var(--text)', fontWeight: 500 }}>{value}</span>
    </div>
  )
}
