import React, { useMemo } from 'react';
import {
  ResponsiveContainer,
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ReferenceLine,
} from 'recharts';
import { TelemetryPoint } from '../api/stations';

export type WeatherVariable =
  | 'temperature'
  | 'humidity'
  | 'pressure'
  | 'wind_speed'
  | 'rainfall'
  | 'solar_radiation';

export const VARIABLE_CONFIG: Record<
  WeatherVariable,
  { label: string; unit: string; color: string; defaultMin: number; defaultMax: number }
> = {
  temperature: { label: 'Temperature', unit: '°C', color: '#4FA8BD', defaultMin: -10, defaultMax: 55 },
  humidity: { label: 'Relative Humidity', unit: '%', color: '#3FB876', defaultMin: 0, defaultMax: 100 },
  pressure: { label: 'Atmospheric Pressure', unit: 'hPa', color: '#A371F7', defaultMin: 850, defaultMax: 1080 },
  wind_speed: { label: 'Wind Speed', unit: 'm/s', color: '#E8B84D', defaultMin: 0, defaultMax: 65 },
  rainfall: { label: 'Rainfall', unit: 'mm', color: '#58A6FF', defaultMin: 0, defaultMax: 300 },
  solar_radiation: { label: 'Solar Radiation', unit: 'W/m²', color: '#F0883E', defaultMin: 0, defaultMax: 1500 },
};

interface StationTimeSeriesChartProps {
  telemetry: TelemetryPoint[];
  selectedVariable: WeatherVariable;
  sensorSpecs?: Record<string, any>;
  onPointClick?: (point: TelemetryPoint) => void;
}

// Custom Tooltip component explaining QC verdict & reason code
const CustomQCChartTooltip = ({ active, payload }: any) => {
  if (!active || !payload || !payload.length) return null;

  const dataPoint = payload[0].payload;
  const val = payload[0].value;
  const qc = dataPoint.qc;
  const unit = dataPoint.unit;

  const isAnom = qc?.verdict === 'anomalous';
  const isSusp = qc?.verdict === 'suspect';

  return (
    <div className="bg-panel border border-line rounded shadow-xl p-3 text-[0.75rem] font-sans max-w-[260px] z-[50]">
      <div className="font-mono text-muted text-[0.6875rem] mb-1">
        {dataPoint.fullTimestamp}
      </div>

      <div className="flex items-baseline space-x-2 my-1">
        <span className="text-[1.125rem] font-mono font-bold text-ink font-mono-tabular">
          {val != null ? `${Number(val).toFixed(1)} ${unit}` : 'Missing'}
        </span>
      </div>

      {qc ? (
        <div className="mt-2 pt-2 border-t border-line space-y-1">
          <div className="flex items-center space-x-1.5">
            <span
              className={`w-2 h-2 rounded-full ${
                isAnom ? 'bg-[#E0655C]' : isSusp ? 'bg-[#E8B84D]' : 'bg-[#3FB876]'
              }`}
            />
            <span
              className={`font-mono font-semibold uppercase text-[0.6875rem] ${
                isAnom ? 'text-[#E0655C]' : isSusp ? 'text-[#E8B84D]' : 'text-[#3FB876]'
              }`}
            >
              {qc.verdict}
            </span>
          </div>

          <div className="font-mono text-[0.6875rem] text-muted">
            Reason: <span className="text-ink">{qc.reason_code}</span>
          </div>

          {qc.fault_type && (
            <div className="font-mono text-[0.6875rem] text-muted">
              Fault Type: <span className="text-[#E0655C] font-semibold">{qc.fault_type}</span>
            </div>
          )}

          <div className="font-mono text-[0.6875rem] text-muted">
            Confidence: <span className="text-ink">{(qc.confidence * 100).toFixed(0)}%</span>
          </div>
        </div>
      ) : (
        <div className="text-[0.6875rem] text-muted italic">QC verdict pending</div>
      )}
    </div>
  );
};

// Custom SVG Dot renderer to highlight anomalous and suspect points
const RenderCustomDot = (props: any) => {
  const { cx, cy, payload } = props;
  if (!cx || !cy) return null;

  const qc = payload.qc;
  if (!qc) return null;

  if (qc.verdict === 'anomalous') {
    return (
      <g>
        {/* Pulsing beacon glow */}
        <circle cx={cx} cy={cy} r={9} fill="#E0655C" opacity={0.25} />
        <circle cx={cx} cy={cy} r={5} fill="#E0655C" stroke="#ffffff" strokeWidth={1.5} />
      </g>
    );
  }

  if (qc.verdict === 'suspect') {
    return (
      <polygon
        points={`${cx},${cy - 5} ${cx + 5},${cy + 4} ${cx - 5},${cy + 4}`}
        fill="#E8B84D"
        stroke="#ffffff"
        strokeWidth={1}
      />
    );
  }

  return null;
};

export const StationTimeSeriesChart: React.FC<StationTimeSeriesChartProps> = ({
  telemetry,
  selectedVariable,
  sensorSpecs,
}) => {
  const conf = VARIABLE_CONFIG[selectedVariable] || VARIABLE_CONFIG.temperature;

  // Retrieve sensor specs limits for threshold reference lines
  const varSpecs = sensorSpecs?.[selectedVariable];
  const specMin = varSpecs?.min != null ? varSpecs.min : conf.defaultMin;
  const specMax = varSpecs?.max != null ? varSpecs.max : conf.defaultMax;

  // Transform data for Recharts
  const chartData = useMemo(() => {
    return telemetry.map((pt) => {
      const dt = new Date(pt.timestamp);
      const formattedTime = dt.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
      const fullTimestamp = dt.toISOString().replace('.000Z', ' UTC');
      const val = pt[selectedVariable] ?? null;
      const qc = pt.qc_verdicts?.[selectedVariable];

      return {
        formattedTime,
        fullTimestamp,
        value: val,
        unit: conf.unit,
        qc,
        rawPoint: pt,
      };
    });
  }, [telemetry, selectedVariable, conf.unit]);

  const hasData = chartData.some((d) => d.value !== null);

  return (
    <div className="w-full bg-panel border border-line rounded p-4 shadow-sm">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between pb-3 mb-2 border-b border-line gap-2">
        <div>
          <div className="flex items-center space-x-2">
            <span
              className="w-2.5 h-2.5 rounded-full inline-block"
              style={{ backgroundColor: conf.color }}
            />
            <h3 className="text-[0.9375rem] font-semibold text-ink font-sans">
              {conf.label} Telemetry & QC Stream
            </h3>
          </div>
          <p className="text-[0.75rem] text-muted mt-0.5">
            Range bounds [{specMin} to {specMax} {conf.unit}] · Anomalies highlighted in red
          </p>
        </div>

        <div className="flex items-center space-x-3 text-[0.6875rem] font-mono">
          <div className="flex items-center space-x-1.5">
            <span className="w-2 h-2 rounded-full bg-[#E0655C]" />
            <span className="text-[#E0655C] font-semibold">Anomalous (Flagged)</span>
          </div>
          <div className="flex items-center space-x-1.5">
            <span className="w-2 h-2 rounded-full bg-[#E8B84D]" />
            <span className="text-[#E8B84D] font-semibold">Suspect</span>
          </div>
          <div className="flex items-center space-x-1.5">
            <span className="w-2 h-2 rounded-full" style={{ backgroundColor: conf.color }} />
            <span className="text-muted">Observation</span>
          </div>
        </div>
      </div>

      {!hasData ? (
        <div className="h-[340px] flex items-center justify-center text-muted font-mono text-[0.8125rem]">
          No recorded observations for {conf.label} in selected window.
        </div>
      ) : (
        <div className="h-[360px] w-full">
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={chartData} margin={{ top: 15, right: 25, left: 0, bottom: 5 }}>
              <defs>
                <linearGradient id={`gradient-${selectedVariable}`} x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor={conf.color} stopOpacity={0.4} />
                  <stop offset="95%" stopColor={conf.color} stopOpacity={0.0} />
                </linearGradient>
              </defs>

              <CartesianGrid strokeDasharray="3 3" stroke="#2C363D" opacity={0.6} />

              <XAxis
                dataKey="formattedTime"
                stroke="#8A97A0"
                fontSize={11}
                tickLine={false}
                dy={5}
              />

              <YAxis
                stroke="#8A97A0"
                fontSize={11}
                tickLine={false}
                domain={['auto', 'auto']}
                unit={` ${conf.unit}`}
                dx={-5}
              />

              {/* Spec Limit Reference Lines */}
              {specMax != null && (
                <ReferenceLine
                  y={specMax}
                  stroke="#E0655C"
                  strokeDasharray="4 4"
                  strokeWidth={1}
                  label={{
                    value: `Max: ${specMax}${conf.unit}`,
                    fill: '#E0655C',
                    fontSize: 10,
                    position: 'insideTopRight',
                  }}
                />
              )}

              {specMin != null && (
                <ReferenceLine
                  y={specMin}
                  stroke="#58A6FF"
                  strokeDasharray="4 4"
                  strokeWidth={1}
                  label={{
                    value: `Min: ${specMin}${conf.unit}`,
                    fill: '#58A6FF',
                    fontSize: 10,
                    position: 'insideBottomRight',
                  }}
                />
              )}

              <Tooltip content={<CustomQCChartTooltip />} />

              <Area
                type="monotone"
                dataKey="value"
                stroke={conf.color}
                strokeWidth={2}
                fillOpacity={1}
                fill={`url(#gradient-${selectedVariable})`}
                dot={<RenderCustomDot />}
                activeDot={{ r: 6, stroke: '#ffffff', strokeWidth: 2 }}
              />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      )}
    </div>
  );
};
