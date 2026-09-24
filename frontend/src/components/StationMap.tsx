import React, { useEffect, useRef, useState } from 'react';
import L from 'leaflet';
import { Layers, Globe } from 'lucide-react';
import { StationSummary, StationHealthStatus } from '../api/stations';

interface StationMapProps {
  stations: StationSummary[];
  selectedStationId?: string | null;
  onSelectStation?: (station: StationSummary) => void;
  onInspectStation?: (stationId: string) => void;
}

type BasemapKey = 'carto_voyager' | 'carto_dark' | 'osm' | 'offline';

const BASEMAP_CONFIGS: Record<BasemapKey, { name: string; url: string; subdomains?: string; attribution: string; maxZoom: number }> = {
  carto_voyager: {
    name: 'CARTO Voyager',
    url:
      import.meta.env.VITE_CARTO_TILE_URL ||
      'https://basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}.png?key=cb1_3wto_1_98681061742df32c284b0e0b',
    attribution: '&copy; <a href="https://carto.com/">CARTO</a> &copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
    maxZoom: 19,
  },
  carto_dark: {
    name: 'CARTO Dark',
    url: 'https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png',
    subdomains: 'abcd',
    attribution: '&copy; <a href="https://carto.com/">CARTO</a> &copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
    maxZoom: 19,
  },
  osm: {
    name: 'OpenStreetMap',
    url: 'https://tile.openstreetmap.org/{z}/{x}/{y}.png',
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
    maxZoom: 19,
  },
  offline: {
    name: 'Offline Tiles (Local)',
    url: '/tiles/{z}/{x}/{y}.png',
    attribution: 'Local Offline Tile Cache (asset/map)',
    maxZoom: 8,
  },
};

// Bounding box defined in asset/map (minlat=43.04, minlon=-18.76, maxlat=58.63, maxlon=18.59)
const OSM_BOUNDS: [L.LatLngTuple, L.LatLngTuple] = [
  [43.04, -18.76],
  [58.63, 18.59],
];

const HEALTH_COLORS: Record<StationHealthStatus, { bg: string; border: string; label: string }> = {
  healthy: { bg: '#3FB876', border: '#238636', label: 'HEALTHY' },
  suspect: { bg: '#E8B84D', border: '#D9A02B', label: 'SUSPECT' },
  anomalous: { bg: '#E0655C', border: '#C1443C', label: 'CRITICAL ANOMALY' },
  offline: { bg: '#6B747C', border: '#4E565E', label: 'OFFLINE' },
};

export const StationMap: React.FC<StationMapProps> = ({
  stations,
  selectedStationId,
  onSelectStation,
  onInspectStation,
}) => {
  const mapContainerRef = useRef<HTMLDivElement | null>(null);
  const mapInstanceRef = useRef<L.Map | null>(null);
  const markersLayerRef = useRef<L.LayerGroup | null>(null);
  const tileLayerRef = useRef<L.TileLayer | null>(null);
  const osmRegionLayerRef = useRef<L.LayerGroup | null>(null);

  const [activeBasemap, setActiveBasemap] = useState<BasemapKey>('carto_voyager');
  const [showOsmRegion, setShowOsmRegion] = useState<boolean>(false);

  // Initialize Leaflet map instance once
  useEffect(() => {
    if (!mapContainerRef.current || mapInstanceRef.current) return;

    // Center on Northern/Central India (Delhi/Rajasthan/Maharashtra regional clusters)
    const map = L.map(mapContainerRef.current, {
      center: [23.5, 77.5],
      zoom: 5.5,
      zoomControl: true,
      attributionControl: true,
    });

    const conf = BASEMAP_CONFIGS['carto_voyager'];
    const tileLayer = L.tileLayer(conf.url, {
      maxZoom: conf.maxZoom,
      subdomains: conf.subdomains || 'abc',
      attribution: conf.attribution,
    }).addTo(map);

    tileLayerRef.current = tileLayer;

    const markersLayer = L.layerGroup().addTo(map);
    markersLayerRef.current = markersLayer;

    const osmLayer = L.layerGroup().addTo(map);
    osmRegionLayerRef.current = osmLayer;

    mapInstanceRef.current = map;

    return () => {
      map.remove();
      mapInstanceRef.current = null;
    };
  }, []);

  // Update Tile Layer when user toggles basemap
  useEffect(() => {
    const map = mapInstanceRef.current;
    if (!map) return;

    if (tileLayerRef.current) {
      map.removeLayer(tileLayerRef.current);
    }

    const conf = BASEMAP_CONFIGS[activeBasemap];
    const newLayer = L.tileLayer(conf.url, {
      maxZoom: conf.maxZoom,
      subdomains: conf.subdomains || 'abc',
      attribution: conf.attribution,
    }).addTo(map);

    tileLayerRef.current = newLayer;
  }, [activeBasemap]);

  // Toggle OSM Region Bounding Box Overlay
  useEffect(() => {
    const map = mapInstanceRef.current;
    const layer = osmRegionLayerRef.current;
    if (!map || !layer) return;

    layer.clearLayers();

    if (showOsmRegion) {
      const rect = L.rectangle(OSM_BOUNDS, {
        color: '#6366f1',
        weight: 2,
        dashArray: '6, 6',
        fillColor: '#6366f1',
        fillOpacity: 0.12,
      });

      rect.bindPopup(`
        <div style="padding: 8px 10px; font-family: 'IBM Plex Sans', sans-serif; font-size: 12px; color: var(--ink); min-width: 220px;">
          <div style="font-weight: 600; font-size: 13px; margin-bottom: 4px; color: #4338ca;">
            📍 OSM Region Boundary (asset/map)
          </div>
          <div style="margin-bottom: 6px; color: var(--muted); font-size: 11px;">
            Western & Central Europe Coverage Zone
          </div>
          <div style="background: rgba(99, 102, 241, 0.08); border-radius: 4px; padding: 6px; font-family: 'IBM Plex Mono', monospace; font-size: 10px;">
            <div>Lat: 43.04°N → 58.63°N</div>
            <div>Lon: -18.76°W → 18.59°E</div>
          </div>
        </div>
      `);

      layer.addLayer(rect);
      map.fitBounds(OSM_BOUNDS, { padding: [40, 40], maxZoom: 6 });
    } else {
      // Re-fit to stations if available
      const bounds = L.latLngBounds([]);
      stations.forEach((st) => {
        if (typeof st.latitude === 'number' && typeof st.longitude === 'number') {
          bounds.extend([st.latitude, st.longitude]);
        }
      });
      if (bounds.isValid() && stations.length > 0) {
        map.fitBounds(bounds, { padding: [40, 40], maxZoom: 8 });
      }
    }
  }, [showOsmRegion, stations]);

  // Update station markers when station list changes
  useEffect(() => {
    const map = mapInstanceRef.current;
    const markersLayer = markersLayerRef.current;
    if (!map || !markersLayer) return;

    markersLayer.clearLayers();

    const bounds = L.latLngBounds([]);

    stations.forEach((st) => {
      if (typeof st.latitude !== 'number' || typeof st.longitude !== 'number') return;

      const pos: [number, number] = [st.latitude, st.longitude];
      bounds.extend(pos);

      const health = st.health_status || 'offline';
      const colorConf = HEALTH_COLORS[health];
      const isAnomalous = health === 'anomalous';
      const isSelected = selectedStationId === st.id || selectedStationId === st.station_code;

      // Custom HTML Marker using L.divIcon
      const markerHtml = `
        <div style="position: relative; width: 30px; height: 30px; display: flex; align-items: center; justify-content: center; cursor: pointer;">
          ${
            isAnomalous
              ? `<div class="pulse-anomalous" style="position: absolute; width: 30px; height: 30px; border-radius: 50%;"></div>`
              : ''
          }
          <div style="
            position: relative;
            width: ${isSelected ? '26px' : '22px'};
            height: ${isSelected ? '26px' : '22px'};
            border-radius: 50%;
            background-color: ${colorConf.bg};
            border: 2px solid ${isSelected ? '#ffffff' : colorConf.border};
            box-shadow: 0 2px 8px rgba(0,0,0,0.6);
            display: flex;
            align-items: center;
            justify-content: center;
            color: #ffffff;
            font-family: 'IBM Plex Mono', monospace;
            font-size: 9px;
            font-weight: 600;
            transition: transform 0.15s ease;
          ">
            ${st.station_code.slice(-2)}
          </div>
        </div>
      `;

      const customIcon = L.divIcon({
        html: markerHtml,
        className: 'custom-station-pin',
        iconSize: [30, 30],
        iconAnchor: [15, 15],
        popupAnchor: [0, -16],
      });

      const marker = L.marker(pos, { icon: customIcon }).addTo(markersLayer);

      // Popup Content template
      const r = st.latest_reading;
      const formattedTime = r?.timestamp
        ? new Date(r.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })
        : 'N/A';

      const popupHtml = `
        <div style="padding: 12px 14px; font-family: 'IBM Plex Sans', sans-serif; min-width: 250px; font-size: 12px; color: var(--ink);">
          <div style="display: flex; align-items: flex-start; justify-content: space-between; gap: 8px; margin-bottom: 6px;">
            <div>
              <span style="font-family: 'IBM Plex Mono', monospace; font-size: 11px; font-weight: 600; color: var(--accent); letter-spacing: 0.5px;">
                ${st.station_code}
              </span>
              <h4 style="margin: 2px 0 0 0; font-size: 14px; font-weight: 600; color: var(--ink);">
                ${st.name}
              </h4>
            </div>
            <span style="
              font-family: 'IBM Plex Mono', monospace;
              font-size: 10px;
              font-weight: 600;
              padding: 2px 6px;
              border-radius: 3px;
              background-color: ${colorConf.bg}22;
              color: ${colorConf.bg};
              border: 1px solid ${colorConf.border};
              white-space: nowrap;
            ">
              ${colorConf.label}
            </span>
          </div>

          <div style="font-size: 11px; color: var(--muted); margin-bottom: 10px;">
            ${st.district}, ${st.state} · Elev ${st.elevation_m ? `${st.elevation_m}m` : '—'}
          </div>

          ${
            st.active_alerts_count > 0
              ? `
              <div style="background-color: #E0655C18; border: 1px solid #E0655C55; border-radius: 4px; padding: 6px 8px; margin-bottom: 10px;">
                <span style="color: #E0655C; font-weight: 600; font-size: 11px;">
                  ⚠️ Active Alerts: ${st.active_alerts_count} ${st.latest_fault_type ? `(${st.latest_fault_type})` : ''}
                </span>
              </div>
            `
              : ''
          }

          <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 6px; background: var(--surface); padding: 8px; border-radius: 4px; border: 1px solid var(--line); margin-bottom: 10px;">
            <div>
              <span style="font-size: 10px; color: var(--muted); display: block;">Temp</span>
              <span style="font-family: 'IBM Plex Mono', monospace; font-size: 12px; font-weight: 600; color: var(--ink);">
                ${r?.temperature != null ? `${r.temperature.toFixed(1)} °C` : '—'}
              </span>
            </div>
            <div>
              <span style="font-size: 10px; color: var(--muted); display: block;">Humidity</span>
              <span style="font-family: 'IBM Plex Mono', monospace; font-size: 12px; font-weight: 600; color: var(--ink);">
                ${r?.humidity != null ? `${r.humidity.toFixed(1)} %` : '—'}
              </span>
            </div>
            <div>
              <span style="font-size: 10px; color: var(--muted); display: block;">Pressure</span>
              <span style="font-family: 'IBM Plex Mono', monospace; font-size: 12px; font-weight: 600; color: var(--ink);">
                ${r?.pressure != null ? `${r.pressure.toFixed(1)} hPa` : '—'}
              </span>
            </div>
            <div>
              <span style="font-size: 10px; color: var(--muted); display: block;">Wind</span>
              <span style="font-family: 'IBM Plex Mono', monospace; font-size: 12px; font-weight: 600; color: var(--ink);">
                ${r?.wind_speed != null ? `${r.wind_speed.toFixed(1)} m/s` : '—'}
              </span>
            </div>
          </div>

          <div style="display: flex; align-items: center; justify-content: space-between; font-size: 10px; color: var(--muted); margin-bottom: 10px;">
            <span>Last Telemetry: ${formattedTime}</span>
            <span>QC: ${st.latest_verdict ? st.latest_verdict.toUpperCase() : 'PENDING'}</span>
          </div>

          <button
            id="inspect-btn-${st.station_code}"
            style="
              width: 100%;
              padding: 6px 10px;
              background-color: var(--accent);
              color: #ffffff;
              border: none;
              border-radius: 4px;
              font-family: 'IBM Plex Sans', sans-serif;
              font-size: 11px;
              font-weight: 500;
              cursor: pointer;
              transition: opacity 0.15s ease;
            "
          >
            Inspect Station Telemetry →
          </button>
        </div>
      `;

      marker.bindPopup(popupHtml, { maxWidth: 300 });

      marker.on('click', () => {
        onSelectStation?.(st);
      });

      marker.on('popupopen', () => {
        const btn = document.getElementById(`inspect-btn-${st.station_code}`);
        if (btn) {
          btn.onclick = () => {
            onInspectStation?.(st.station_code);
          };
        }
      });
    });

    // Auto-fit bounds if we have stations loaded
    if (bounds.isValid() && stations.length > 0) {
      map.fitBounds(bounds, { padding: [40, 40], maxZoom: 8 });
    }
  }, [stations, selectedStationId, onSelectStation, onInspectStation]);

  return (
    <div className="relative w-full h-[520px] rounded border border-line overflow-hidden bg-panel shadow-sm">
      <div ref={mapContainerRef} className="w-full h-full z-0" />

      {/* Top Map Controls Overlay: Basemap Switcher & OSM Region Toggle */}
      <div className="absolute top-3 right-3 z-[500] flex flex-wrap items-center gap-2">
        {/* Basemap Switcher */}
        <div className="bg-panel/95 backdrop-blur-md border border-line rounded px-2 py-1.5 shadow-md flex items-center space-x-1.5 text-xs font-mono">
          <Layers className="w-3.5 h-3.5 text-accent" />
          <span className="text-[10px] text-muted uppercase tracking-wider mr-1">Basemap:</span>
          {(['carto_voyager', 'carto_dark', 'osm', 'offline'] as BasemapKey[]).map((key) => (
            <button
              key={key}
              onClick={() => setActiveBasemap(key)}
              className={`px-2 py-0.5 rounded text-[11px] font-sans font-medium transition-all ${
                activeBasemap === key
                  ? 'bg-accent text-white shadow-xs'
                  : 'text-muted hover:text-ink hover:bg-hover'
              }`}
              title={BASEMAP_CONFIGS[key].name}
            >
              {key === 'carto_voyager' ? 'Voyager' : key === 'carto_dark' ? 'Dark' : key === 'osm' ? 'OSM' : 'Offline'}
            </button>
          ))}
        </div>

        {/* OSM Region Toggle (asset/map) */}
        <button
          onClick={() => setShowOsmRegion(!showOsmRegion)}
          className={`flex items-center space-x-1 px-2.5 py-1.5 rounded text-xs font-mono border shadow-md backdrop-blur-md transition-all ${
            showOsmRegion
              ? 'bg-indigo-600/90 text-white border-indigo-400 font-semibold ring-1 ring-indigo-400'
              : 'bg-panel/95 text-ink border-line hover:bg-hover hover:border-muted'
          }`}
          title="Toggle OpenStreetMap Bounding Box defined in asset/map"
        >
          <Globe className="w-3.5 h-3.5" />
          <span>{showOsmRegion ? 'OSM Region Active' : 'OSM Region (asset/map)'}</span>
        </button>
      </div>
      
      {/* Map Legend Overlay */}
      <div className="absolute bottom-4 right-4 z-[500] bg-panel/90 backdrop-blur-sm border border-line px-3 py-2 rounded text-[0.6875rem] font-mono shadow-lg flex items-center space-x-3 pointer-events-none">
        <div className="flex items-center space-x-1.5">
          <span className="w-2.5 h-2.5 rounded-full bg-[#3FB876] inline-block" />
          <span className="text-ink">Healthy</span>
        </div>
        <div className="flex items-center space-x-1.5">
          <span className="w-2.5 h-2.5 rounded-full bg-[#E8B84D] inline-block" />
          <span className="text-ink">Suspect</span>
        </div>
        <div className="flex items-center space-x-1.5">
          <span className="w-2.5 h-2.5 rounded-full bg-[#E0655C] pulse-anomalous inline-block" />
          <span className="text-ink">Anomalous</span>
        </div>
        <div className="flex items-center space-x-1.5">
          <span className="w-2.5 h-2.5 rounded-full bg-[#6B747C] inline-block" />
          <span className="text-ink">Offline</span>
        </div>
      </div>
    </div>
  );
};
