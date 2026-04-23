import { useState, useEffect, useMemo, useRef } from 'react'
import './App.css'
import SearchIcon from './assets/mag.png'
import { Place, QueryDimension, BaseModel, PlaceDim } from './types'
import Chat from './Chat'
import MapView from './MapView'

function App(): JSX.Element {
  const [useLlm, setUseLlm] = useState<boolean | null>(null)
  const [searchTerm, setSearchTerm] = useState<string>('')
  const [places, setPlaces] = useState<Place[]>([])
  const [selectedPlace, setSelectedPlace] = useState<Place | null>(null)
  const [loading, setLoading] = useState<boolean>(false)
  const [hasSearched, setHasSearched] = useState<boolean>(false)
  const [queryDimensions, setDimensions] = useState<QueryDimension[]>([])
  const [chatOpen, setChatOpen] = useState<boolean>(true)
  const [baseModel, setBaseModel] = useState<BaseModel>('tfidf')
  const [useSvd, setUseSvd] = useState<boolean>(true)
  const [summaries, setSummaries] = useState<Record<number, string>>({})
  const [summaryLoading, setSummaryLoading] = useState<Record<number, boolean>>({})
  const [dimLabels, setDimLabels] = useState<Record<number, string>>({})
  const [openChips, setOpenChips] = useState<Record<number, Record<string, boolean>>>({})


  const requestIdRef = useRef(0)
  const abortControllerRef = useRef<AbortController | null>(null)
  const debounceTimeoutRef = useRef<number | null>(null)

  useEffect(() => {
    fetch('/api/config')
      .then((r) => r.json())
      .then((data) => setUseLlm(data.use_llm))
  }, [])

  const runSearch = async (
    value: string,
    modelOverride?: BaseModel,
    svdOverride?: boolean
  ): Promise<void> => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort()
    }

    const trimmedValue = value.trim()
    if (trimmedValue!== searchTerm) setSearchTerm(trimmedValue)

    if (trimmedValue === '') {
      requestIdRef.current += 1
      setLoading(false)
      setHasSearched(false)
      setPlaces([])
      setOpenChips({})
      setSelectedPlace(null)
      setDimensions([])
      return
    }

    const currentRequestId = ++requestIdRef.current
    const controller = new AbortController()
    abortControllerRef.current = controller

    const resolvedBaseModel = modelOverride ?? baseModel
    const resolvedUseSvd = svdOverride ?? useSvd

    setLoading(true)
    setHasSearched(true)

    try {
      const response = await fetch(
        `/api/places?name=${encodeURIComponent(trimmedValue)}&base_model=${resolvedBaseModel}&use_svd=${resolvedUseSvd}&top=10`,
        { signal: controller.signal }
      )

      if (!response.ok) {
        throw new Error(`Request failed with status ${response.status}`)
      }

      const data = await response.json()

      if (currentRequestId !== requestIdRef.current) {
        return
      }

      const limited = (data.results ?? []).slice(0, 10)
      const qDims: QueryDimension[] = data.dimensions ?? []
      setPlaces(limited)
      setDimensions(qDims)
      setSelectedPlace(limited.length > 0 ? limited[0] : null)
      const placeDimsList = limited.map((p: any) => p.dims ?? [])
      fetchDimLabels(qDims, placeDimsList)
      if (useLlm && limited.length > 0) fetchSummary(limited[0])

    } catch (error) {
      if ((error as Error).name === 'AbortError') {
        return
      }

      if (currentRequestId !== requestIdRef.current) {
        return
      }

      console.error('Search failed:', error)
      setPlaces([])
      setSelectedPlace(null)
      setDimensions([])
    } finally {
      if (currentRequestId === requestIdRef.current) {
        setLoading(false)
      }
    }
  }

  useEffect(() => {
    if (searchTerm.trim() !== '') {
      runSearch(searchTerm)
    }
  }, [baseModel, useSvd])

  const fetchSummary = async (place: Place) => {
  if (summaries[place.id] || summaryLoading[place.id]) return // don't re-fetch
  setSummaryLoading(prev => ({ ...prev, [place.id]: true }))
  try {
    const res = await fetch('/api/summary', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ place, query: searchTerm })
    })
    const data = await res.json()
    setSummaries(prev => ({ ...prev, [place.id]: data.summary }))
  } catch {
    setSummaries(prev => ({ ...prev, [place.id]: 'Could not generate summary.' }))
  } finally {
    setSummaryLoading(prev => ({ ...prev, [place.id]: false }))
  }
  }

  const fetchDimLabels = async (queryDims: QueryDimension[], placeDimsList: PlaceDim[][]) => {
    if (!useLlm) return
    const seen = new Set<number>()
    const toLabel: { dimension: number; top_terms: string[] }[] = []
    const consider = (dim: number, terms: string[]) => {
      if (seen.has(dim) || dimLabels[dim]) return
      seen.add(dim)
      if (terms.length > 0) toLabel.push({ dimension: dim, top_terms: terms })
    }
    for (const d of queryDims) consider(d.dimension, d.terms ?? [])
    for (const dims of placeDimsList) for (const d of dims) consider(d.dimension, d.terms ?? [])
    if (toLabel.length === 0) return
    const res = await fetch('/api/label-dims', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({ dims: toLabel }) })
    const data = await res.json()
    if (data.labels) setDimLabels(prev => ({ ...prev, ...data.labels }))
  }

  const PlaceDimBars = ({ dims }: { dims: PlaceDim[] }) => {
    if (!dims || dims.length === 0) return null
    const maxAbs = Math.max(...dims.map(d => Math.abs(d.activation)), 0.0001)
    return (
      <div className="query-dims place-dims">
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '10px' }}>
        <div className="query-dims-title" style={{ margin: 0 }}>Place SVD dimensions</div>
        <div className="dims-info">
          <div className="dims-info-icon">i</div>
          <div className="dims-info-tooltip">
            Each bar shows a latent topic this place strongly associates with.
            Blue bars are themes the place leans toward; red means it leans away.
            Labels are AI-generated from the top terms shown below them.
          </div>
        </div>
      </div>
        {dims.map(dim => {
          const pct = (Math.abs(dim.activation) / maxAbs) * 45
          const isPos = dim.activation >= 0
          const label = dimLabels[dim.dimension]
          return (
            <div key={dim.dimension} className="dim-row">
              <div className="dim-header">
                <span className="dim-terms">
                  {label && <span className="dim-label">{label}</span>}
                  <span className="dim-top-terms">{dim.terms.join(' · ')}</span>
                </span>
                <span className="dim-num">{isPos ? '+' : ''}{dim.activation.toFixed(2)}</span>
            </div>
              <div className="bar-track">
                <div className="bar-center" />
                <div className={`bar-fill ${isPos ? 'bar-pos' : 'bar-neg'}`} style={{ width: `${pct}%` }} />
              </div>
            </div>
          )
        })}
      </div>
    )
  }

  const toggleChip = (placeId: number, chip: string) => {
  setOpenChips(prev => ({
    ...prev,
    [placeId]: {
      ...prev[placeId],
      [chip]: !(prev[placeId]?.[chip] ?? false) 
    }
  }))
  }

  const isChipOpen = (placeId: number, chip: string) => {
  return openChips[placeId]?.[chip] ?? true
  }

  const handleSearch = (value: string): void => {
    setSearchTerm(value)

    if (debounceTimeoutRef.current !== null) {
      window.clearTimeout(debounceTimeoutRef.current)
      debounceTimeoutRef.current = null
    }

    if (value.trim() === '') {
      if (abortControllerRef.current) {
        abortControllerRef.current.abort()
        abortControllerRef.current = null
      }

      requestIdRef.current += 1

      setLoading(false)
      setHasSearched(false)
      setPlaces([])
      setSelectedPlace(null)
      return
    }

    debounceTimeoutRef.current = window.setTimeout(() => {
      runSearch(value)
    }, 600)
  }

  useEffect(() => {
    return () => {
      if (abortControllerRef.current) {
        abortControllerRef.current.abort()
      }
      if (debounceTimeoutRef.current !== null) {
        window.clearTimeout(debounceTimeoutRef.current)
      }
    }
  }, [])

  useEffect(() => {
    if (!selectedPlace || places.length === 0) return

    const stillExists = places.some((place) => place.id === selectedPlace.id)
    if (!stillExists) {
      setSelectedPlace(places[0] ?? null)
    }
  }, [places, selectedPlace])

  const resultCountText = useMemo(() => {
    if (searchTerm.trim() === '') return 'Search for places in New York'
    if (loading) return (
      <div className="loading-container">
        <p>Loading...</p>
        <div className="loading-spinner"/> 
      </div>
      )
    if (places.length === 0 && hasSearched) return 'No matches found'
    if (places.length === 1) return '1 result'
    return `${places.length} results`
  }, [places, searchTerm, loading, hasSearched])

  if (useLlm === null) return <></>

  return (
    <div className={`app-shell ${useLlm ? 'llm-mode' : ''}`}>
      <aside className="sidebar">
        <div className="sidebar-header">
          <h1 className="app-title">I Love New York</h1>
          <div className="search-controls">
            <div className="control-group">
              <span className="control-label">Base model</span>
              <button
                type="button"
                className={baseModel === 'tfidf' ? 'control-btn active' : 'control-btn'}
                onClick={() => setBaseModel('tfidf')}
              >
                TF-IDF
              </button>
              <button
                type="button"
                className={baseModel === 'sbert' ? 'control-btn active' : 'control-btn'}
                onClick={() => setBaseModel('sbert')}
              >
                SBERT
              </button>
            </div>

            <div className="control-group">
              <span className="control-label">SVD</span>
              <button
                type="button"
                className={!useSvd ? 'control-btn active' : 'control-btn'}
                onClick={() => setUseSvd(false)}
              >
                Off
              </button>
              <button
                type="button"
                className={useSvd ? 'control-btn active' : 'control-btn'}
                onClick={() => setUseSvd(true)}
              >
                On
              </button>
            </div>
          </div>
          <div
            className="input-box"
            onClick={() => document.getElementById('search-input')?.focus()}
          >
            <img src={SearchIcon} alt="search" />
            <input
              id="search-input"
              placeholder="Search for places in New York..."
              value={searchTerm}
              onChange={(e) => handleSearch(e.target.value)}
            />
          </div>

          <div className="results-summary">{resultCountText}</div>

        </div>

        <div className="results-panel">
          {searchTerm.trim() === '' && !loading && (
            <div className="empty-state">
              Start typing to see matching places appear on the map.
            </div>
          )}

          {!loading && hasSearched && places.length === 0 && (
            <div className="empty-state">
              No places matched your search. Try something broader like
              &nbsp;<strong>pizza</strong>, <strong>museum</strong>, or
              &nbsp;<strong>date night</strong>.
            </div>
          )}

          {queryDimensions.length > 0 && searchTerm.trim() !== '' && !loading  && baseModel !== 'sbert' && useSvd &&(
            <div className="query-dims">
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '10px' }}>
              <span className="query-dims-title">Query SVD fingerprint</span>
              <div className="dims-info">
                <div className="dims-info-icon">i</div>
                <div className="dims-info-tooltip">
                  Each bar is a latent topic found by SVD. The label is AI-generated from the top terms below it.
                  Blue bars mean your query activates that theme; red means it pulls away from it.
                  The number shows activation strength.
                </div>
              </div>
            </div>
              {queryDimensions.map((dim) => {
                const pct = Math.abs(dim.activation) * 50
                const isPos = dim.activation >= 0
                const label = dimLabels[dim.dimension]
                return (
                  <div key={dim.dimension} className="dim-row">
                    <div className="dim-header">
                      <span className="dim-terms">
                        {label && <span className="dim-label">{label}</span>}
                        <span className="dim-top-terms">{dim.terms?.join(' · ')}</span>
                      </span>
                      <span className="dim-num">{isPos ? '+' : ''}{dim.activation.toFixed(2)}</span>
                    </div>
                    <div className="bar-track">
                      <div className="bar-center" />
                      <div
                        className={`bar-fill ${isPos ? 'bar-pos' : 'bar-neg'}`}
                        style={{ width: `${pct}%` }}
                      />
                    </div>
                  </div>
                )
              })}
            </div>
          )}

          {places.map((place) => {
            const isActive = selectedPlace?.id === place.id
            const placeDims: PlaceDim[] = (place as any).dims ?? []

            return (
              <button
                key={place.id}
                type="button"
                className={`place-item ${isActive ? 'active' : ''}`}
                onClick={() => {setSelectedPlace(place) 
                  if (useLlm) fetchSummary(place)}}
              >
                <div className="place-item-content">
                  <h3 className="place-name">{place.name}</h3>
                  <p className="place-description">{place.description}</p>
                    <div className='place-info'>
                      {place.price_level && (
                        <p className='place-price place-box'>
                          {(['cheap', 'moderate', 'expensive', 'very expensive'].includes(place.price_level)
                            ? '$'.repeat(['cheap', 'moderate', 'expensive', 'very expensive'].indexOf(place.price_level) + 1)
                            : place.price_level)}
                        </p>
                      )}
                    {place.rating>0 && (
                    <p className="place-rating place-box">
                    ⭐ {place.rating  ?? 'N/A'}
                    </p>
                    )}
                  <p className="place-score place-box">
                    {place.similarity_score !== null
                      ? `${(place.similarity_score*100).toFixed(1)}% match`
                      : 'N/A'}
                  </p>
                  </div>
                  {isActive && (

                    <div className='place-expanded'>
                      <div className='place-divide'>
                    {place.formatted_address && (
                      <p className='place-address'>Address: {place.formatted_address}</p>
                    )}
                    {place.website_url && (
                      <a
                        className="place-website"
                        href={place.website_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        onClick={(e) => e.stopPropagation()}
                      >
                        View Website
                      </a>
                    )}

                    <div className="chip-row">
                      {baseModel === 'tfidf' && useSvd && placeDims.length > 0 && (
                        <button
                          className={`chip ${isChipOpen(place.id, 'dims') ? 'active' : ''}`}
                          onClick={e => { e.stopPropagation(); toggleChip(place.id, 'dims') }}
                        >
                          SVD fingerprint
                        </button>
                      )}
                      {useLlm && (
                        <button
                          className={`chip ${isChipOpen(place.id, 'summary') ? 'active' : ''}`}
                          onClick={e => { e.stopPropagation(); toggleChip(place.id, 'summary') }}
                        >
                          AI summary
                        </button>
                      )}
                    </div>

                    <div className={`chip-section-body ${isChipOpen(place.id, 'dims') ? 'open' : ''}`}>
                      <PlaceDimBars dims={placeDims} />
                    </div>

                    <div className={`chip-section-body ${isChipOpen(place.id, 'summary') ? 'open' : ''}`}>
                      {summaryLoading[place.id] ? (
                        <div className="ai-summary-loading">
                          <div className="loading-spinner" />
                          <span>Generating AI summary...</span>
                        </div>
                      ) : summaries[place.id] ? (
                        <div className="ai-summary">
                          <span className="ai-summary-label">Why this matches your search</span>
                          <p>{summaries[place.id]}</p>
                        </div>
                      ) : null}
                    </div> 
                  </div>   
                </div>     
                )}
              </div>       
            </button>
          )
        })}
      </div>   

      </aside>

    <div className="right-col">
    <main className="map-panel">
        <MapView
          places={places}
          selectedPlace={selectedPlace}
          onMarkerClick={setSelectedPlace}
        />
    </main>
    {useLlm && (
      <div className="chat-section">
        <button className="section-toggle chat-toggle" onClick={() => setChatOpen(o => !o)}>
          <span className="section-toggle-left">
            <span>✨</span>
            <span className="section-title">AI Assistant</span>
            <span className="section-count">RAG-powered</span>
          </span>
          <span className={`chevron ${chatOpen ? 'open' : ''}`}>›</span>
        </button>
        {chatOpen && <div className="chat-shell"><Chat onSearchTerm={runSearch} /></div>}
      </div>
    )}
    </div>
    </div>
  )
}

export default App