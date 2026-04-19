import { useState, useEffect, useMemo, useRef } from 'react'
import './App.css'
import SearchIcon from './assets/mag.png'
import { Place } from './types'
import Chat from './Chat'
import MapView from './MapView'

function App(): JSX.Element {
  const [useLlm, setUseLlm] = useState<boolean | null>(null)
  const [searchTerm, setSearchTerm] = useState<string>('')
  const [places, setPlaces] = useState<Place[]>([])
  const [selectedPlace, setSelectedPlace] = useState<Place | null>(null)
  const [loading, setLoading] = useState<boolean>(false)
  const [hasSearched, setHasSearched] = useState<boolean>(false)

  const requestIdRef = useRef(0)
  const abortControllerRef = useRef<AbortController | null>(null)
  const debounceTimeoutRef = useRef<number | null>(null)

  useEffect(() => {
    fetch('/api/config')
      .then((r) => r.json())
      .then((data) => setUseLlm(data.use_llm))
  }, [])

  const runSearch = async (value: string): Promise<void> => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort()
    }

    const trimmedValue = value.trim()

    if (trimmedValue === '') {
      requestIdRef.current += 1
      setLoading(false)
      setHasSearched(false)
      setPlaces([])
      setSelectedPlace(null)
      return
    }

    const currentRequestId = ++requestIdRef.current
    const controller = new AbortController()
    abortControllerRef.current = controller

    setLoading(true)
    setHasSearched(true)

    try {
      const response = await fetch(
        `/api/places?name=${encodeURIComponent(trimmedValue)}`,
        { signal: controller.signal }
      )

      if (!response.ok) {
        throw new Error(`Request failed with status ${response.status}`)
      }

      const data: Place[] = await response.json()

      if (currentRequestId !== requestIdRef.current) {
        return
      }

      if (trimmedValue === '') {
        return
      }

      const limited = data.slice(0, 10)
      setPlaces(limited)
      setSelectedPlace(limited.length > 0 ? limited[0] : null)
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
    } finally {
      if (currentRequestId === requestIdRef.current) {
        setLoading(false)
      }
    }
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
    }, 300)
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
    if (loading) return 'Searching...'
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

          <p className="results-summary">{resultCountText}</p>
        </div>

        <div className="results-panel">
          {searchTerm.trim() === '' && !loading && (
            <div className="empty-state">
              Start typing to see matching places appear on the map.
            </div>
          )}

          {loading && (
            <div className="loading-state">
              <div className="loading-spinner" />
              <p>Searching places...</p>
            </div>
          )}

          {!loading && hasSearched && places.length === 0 && (
            <div className="empty-state">
              No places matched your search. Try something broader like
              &nbsp;<strong>pizza</strong>, <strong>museum</strong>, or
              &nbsp;<strong>date night</strong>.
            </div>
          )}

          {places.map((place) => {
            const isActive = selectedPlace?.id === place.id

            return (
              <button
                key={place.id}
                type="button"
                className={`place-item ${isActive ? 'active' : ''}`}
                onClick={() => setSelectedPlace(place)}
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
                    <p className="place-rating place-box">
                    ⭐ {place.rating ?? 'N/A'}
                    </p>
                  <p className="place-score place-box">
                    {place.similarity_score !== null
                      ? `${(place.similarity_score*100).toFixed(1)}% match`
                      : 'N/A'}
                  </p>
                  </div>
                  {isActive && (

                    <div className='place-expanded'>
                      <div className='place-divide'>
                      <div>
                        {place.formatted_address && (
                        <p className='place-address'>Address: {place.formatted_address}</p>
                        )}
                      </div>
                      {place.tags?.length > 0 && (
                        <div className="place-tags">
                          {(place.tags ?? []).map((tag) => (
                            <span key={tag} className="place-tag">{tag}</span>
                          ))}
                        </div>
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
                    </div>
                    </div>
                  )}
                </div>
              </button>
            )
          })}
        </div>

        {useLlm && (
          <div className="chat-shell">
            <Chat onSearchTerm={runSearch} />
          </div>
        )}
      </aside>

      <main className="map-panel">
        <MapView
          places={places}
          selectedPlace={selectedPlace}
          onMarkerClick={setSelectedPlace}
        />
      </main>
    </div>
  )
}

export default App