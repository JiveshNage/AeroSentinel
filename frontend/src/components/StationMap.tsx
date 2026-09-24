import React, { useEffect, useRef } from 'react';
import L from 'leaflet';
import { StationSummary, StationHealthStatus } from '../api/stations';

interface StationMapProps {
  stations: StationSummary[];
  selectedStationId?: string | null;
  onSelectStation?: (station: StationSummary) => void;
  onInspectStation?: (stationId: string) => void;
}

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

    // Basemap tile layer from CARTO Voyager (with API key)
    const cartoTileUrl =
      import.meta.env.VITE_CARTO_TILE_URL ||
      'https://basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}.png?key=cb1_3wto_1_98681061742df32c284b0e0b';

    L.tileLayer(cartoTileUrl, {
      maxZoom: 19,
      attribution:
        '&copy; <a href="https://carto.com/">CARTO</a> &copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
    }).addTo(map);

    const markersLayer = L.layerGroup().addTo(map);
    markersLayerRef.current = markersLayer;
    mapInstanceRef.current = map;

    return () => {
      map.remove();
      mapInstanceRef.current = null;
    };
  }, []);

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
