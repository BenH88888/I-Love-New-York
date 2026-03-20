import { useState, useEffect } from 'react'
import './App.css'
import SearchIcon from './assets/mag.png'
import { Place } from './types'
import Chat from './Chat'

function App(): JSX.Element {
  const [useLlm, setUseLlm] = useState<boolean | null>(null)
  const [searchTerm, setSearchTerm] = useState<string>('')
  const [places, setPlaces] = useState<Place[]>([])

  useEffect(() => {
    fetch('/api/config').then(r => r.json()).then(data => setUseLlm(data.use_llm))
  }, [])

  const handleSearch = async (value: string): Promise<void> => {
    setSearchTerm(value)
    if (value.trim() === '') { setPlaces([]); return }
    const response = await fetch(`/api/places?name=${encodeURIComponent(value)}`)
    const data: Place[] = await response.json()
    setPlaces(data)
  }

  if (useLlm === null) return <></>

  return (
    <div className={`full-body-container ${useLlm ? 'llm-mode' : ''}`}>
      {/* Search bar (always shown) */}
      <div className="top-text">
        <div className="text-7xl font-['gothic_script'] text-stone-100">
          <h1> Discover New York </h1>
        </div>
        <div className="input-box" onClick={() => document.getElementById('search-input')?.focus()}>
          <img src={SearchIcon} alt="search" />
          <input
            id="search-input"
            placeholder="Search for places in New York..."
            value={searchTerm}
            onChange={(e) => handleSearch(e.target.value)}
          />
        </div>
      </div>

      {/* Search results (shown only when we have places) */}
      {places.length > 0 && (
        <div id="answer-box">
          {places.map((place, index) => (
            <div key={index} className="place-item">
              <h3 className="place-name">{place.name}</h3>
              <p className="place-description">{place.description}</p>
              <p className="place-address">Address: {place.formatted_address}</p>
              <p className="place-rating">Rating: {place.rating}</p>
              <a className="place-website" href={place.website_url} target="_blank" rel="noopener noreferrer">View Website</a>
            </div>
          ))}
        </div>
      )}

      {/* Chat (only when USE_LLM = True in routes.py) */}
      {useLlm && <Chat onSearchTerm={handleSearch} />}
    </div>
  )
}

export default App
