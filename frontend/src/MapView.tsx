import { useEffect, useRef } from 'react'
import { Place } from './types'

declare global {
  interface Window {
    google: any
    __googleMapsInitPromise?: Promise<void>
  }
}

type MapViewProps = {
  places: Place[]
  selectedPlace: Place | null
  onMarkerClick: (place: Place) => void
}

const NYC_CENTER = { lat: 40.7128, lng: -74.0060 }
const DEFAULT_ZOOM = 11

function buildInfoWindowContent(place: Place): string {
  // const websiteHtml = place.website_url
  //   ? `<a href="${place.website_url}" target="_blank" rel="noopener noreferrer">View Website</a>`
  //   : ''

  return `
    <div style="max-width: 240px; font-family: Arial, sans-serif;">
      <h3 style="margin: 0 0 8px; font-size: 16px; font-weight: bold;">${place.name}</h3>
      <p style="margin: 0 0 6px; font-size: 13px; color: #444;">Address: ${place.formatted_address}</p>
    </div>
  `
}

function loadGoogleMapsApi(): Promise<void> {
  if (window.google?.maps) {
    return Promise.resolve()
  }

  if (window.__googleMapsInitPromise) {
    return window.__googleMapsInitPromise
  }

  const apiKey = import.meta.env.VITE_GOOGLE_MAPS_API_KEY

  if (!apiKey) {
    return Promise.reject(
      new Error('Missing VITE_GOOGLE_MAPS_API_KEY at build time')
    )
  }

  window.__googleMapsInitPromise = new Promise((resolve, reject) => {
    const existingScript = document.querySelector(
      'script[data-google-maps="true"]'
    ) as HTMLScriptElement | null

    if (existingScript) {
      existingScript.addEventListener('load', () => resolve())
      existingScript.addEventListener('error', () =>
        reject(new Error('Failed to load Google Maps script'))
      )
      return
    }

    const script = document.createElement('script')
    script.src = `https://maps.googleapis.com/maps/api/js?key=${apiKey}&v=weekly&libraries=marker`
    script.async = true
    script.defer = true
    script.dataset.googleMaps = 'true'

    script.onload = () => resolve()
    script.onerror = () => reject(new Error('Failed to load Google Maps script'))

    document.head.appendChild(script)
  })

  return window.__googleMapsInitPromise
}

function MapView({ places, selectedPlace, onMarkerClick }: MapViewProps): JSX.Element {
  const mapContainerRef = useRef<HTMLDivElement | null>(null)
  const mapRef = useRef<any>(null)
  const markersRef = useRef<any[]>([])
  const markerByPlaceIdRef = useRef<Map<number, any>>(new Map())
  const infoWindowRef = useRef<any>(null)
  const hasFitBoundsRef = useRef<boolean>(false)

  useEffect(() => {
    let isMounted = true

    const initializeMap = async (): Promise<void> => {
      await loadGoogleMapsApi()

      if (!isMounted || !mapContainerRef.current || mapRef.current) return

      const google = window.google
      const mapId = import.meta.env.VITE_GOOGLE_MAP_ID || 'DEMO_MAP_ID'

      mapRef.current = new google.maps.Map(mapContainerRef.current, {
        center: NYC_CENTER,
        zoom: DEFAULT_ZOOM,
        mapId
      })

      infoWindowRef.current = new google.maps.InfoWindow({
        disableAutoPan: true
      })
    }

    initializeMap().catch((error) => {
      console.error('Error initializing Google Maps:', error)
    })

    return () => {
      isMounted = false
    }
  }, [])

  useEffect(() => {
    const google = window.google
    const map = mapRef.current

    if (!google || !map) return

    markersRef.current.forEach((marker) => {
      marker.map = null
    })
    markersRef.current = []
    markerByPlaceIdRef.current.clear()

    if (places.length === 0) {
      hasFitBoundsRef.current = false
      if (infoWindowRef.current) {
        infoWindowRef.current.close()
      }
      map.setCenter(NYC_CENTER)
      map.setZoom(DEFAULT_ZOOM)
      return
    }

    const bounds = new google.maps.LatLngBounds()

    places.forEach((place) => {
      if (
        typeof place.latitude !== 'number' ||
        typeof place.longitude !== 'number'
      ) {
        return
      }

      const marker = new google.maps.marker.AdvancedMarkerElement({
        map,
        position: {
          lat: place.latitude,
          lng: place.longitude
        },
        title: place.name,
        gmpClickable: true
      })

      marker.addListener('click', () => {
        onMarkerClick(place)

        if (infoWindowRef.current) {
          infoWindowRef.current.setContent(buildInfoWindowContent(place))
          infoWindowRef.current.open({
            map,
            anchor: marker,
            shouldFocus: false
          })
        }
      })

      markersRef.current.push(marker)
      markerByPlaceIdRef.current.set(place.id, marker)
      bounds.extend({ lat: place.latitude, lng: place.longitude })
    })

    if (places.length === 1) {
      map.panTo({
        lat: places[0].latitude,
        lng: places[0].longitude
      })
      map.setZoom(15)
    } else if (!hasFitBoundsRef.current) {
      map.fitBounds(bounds, 80)
    } else {
      map.fitBounds(bounds, 80)
    }

    hasFitBoundsRef.current = true
  }, [places, onMarkerClick])

  useEffect(() => {
    const map = mapRef.current
    const marker = selectedPlace
      ? markerByPlaceIdRef.current.get(selectedPlace.id)
      : null

    if (!map || !selectedPlace) return

    map.panTo({
      lat: selectedPlace.latitude,
      lng: selectedPlace.longitude
    })
    map.setZoom(15)

    if (marker && infoWindowRef.current) {
      infoWindowRef.current.setContent(buildInfoWindowContent(selectedPlace))
      infoWindowRef.current.open({
        map,
        anchor: marker,
        shouldFocus: false
      })
    }
  }, [selectedPlace])

  return <div ref={mapContainerRef} className="map-view" />
}

export default MapView