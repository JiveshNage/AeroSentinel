# design.md — AeroSentinel — Intelligent AWS Anomaly Detection & Quality Control

**Purpose:** Visual/UX spec for the operator dashboard (`features.md` F11–F13). Read alongside `architecture.md` (component responsibilities) and `techstack.md` (React + TS + Tailwind + Leaflet + Recharts). This is a mission-critical monitoring tool for government meteorological operators, not a consumer product — every design choice below is grounded in that.

## 1. Who this is for, and what that means for the design
Primary user: an **IMD Data Quality Officer** watching a live map of ~1,000 stations for hours at a stretch, triaging alerts under time pressure, sometimes during an actual unfolding weather event. Secondary users: forecasters glancing at confidence flags, field technicians checking a prioritized repair queue.

What that implies:
- **Legibility and speed of comprehension beat visual flourish.** A judge or operator should understand a station's health state in under one second of looking at it.
- **Calm by default, loud only when it matters.** Most of the screen, most of the time, should look quiet — so that when something goes red, it's unmistakable. If everything is colorful all the time, nothing stands out.
- **Trust and precision over "friendly" software feel.** This is closer to air-traffic-control or a hospital monitoring station in spirit than a SaaS product — the visual language should read as instrumented and precise, not playful.
- **This is not a generic admin-panel template.** Avoid defaulting to a generic SaaS dashboard look (rounded cards everywhere, soft grey shadows, gradient washes, ALL-CAPS eyebrow labels) — those read as templated rather than built for meteorological operations. Ground every choice in "this is a data-instrument for weather-station health," not "this is a dashboard."

## 2. Design tokens

### Color — dual theme, one token system
Same structural rules apply in both themes: status color is reserved *only* for station/alert health and never used decoratively elsewhere; the working surface stays low-saturation so status is the one thing that pops. Dark mode is a legitimate, deliberate choice here — this is a 24/7 monitoring tool and operators run long low-light shifts — not a stylistic default, so it earns the same discipline as light mode: no near-black-with-one-neon-accent as decoration, no ALL-CAPS eyebrow labels, no arrow-suffixed buttons, no marketing-hero headline sitting above live data, in either theme.

Implement as CSS custom properties on a `[data-theme="light"|"dark"]` root attribute so every component references the token, never a hardcoded hex — this is what makes the toggle a true theme swap rather than two separate UIs to maintain.

| Token | Light | Dark | Role |
|---|---|---|---|
| `--ink` | `#10161C` | `#E8ECEF` | Primary text |
| `--surface` | `#F6F7F8` | `#12171C` | App background |
| `--panel` | `#FFFFFF` | `#1B2228` | Cards/panels on `--surface` |
| `--panel-raised` | — | `#212A31` | Dark-mode only: a second, slightly lighter panel step for the one or two elements that should read as "in front" (e.g. the primary CTA card) — this replaces uniform drop-shadows, which read worse in dark UI, with actual elevation via tone |
| `--line` | `#D8DCE0` | `#2C363D` | Borders, dividers, map graticule |
| `--accent` | `#1D4E5F` (deep teal) | `#4FA8BD` (lighter teal, same hue family — not a hue swap to cyan/neon) | Primary interactive accent |
| `--muted` | `#5B6670` | `#8A97A0` | Secondary text, metadata |

Status colors — identical hue family across themes (only lightness/saturation adjusted for dark-background contrast), so an operator switching themes mid-shift never has to relearn what a color means:

| Status | Light | Dark | Meaning |
|---|---|---|---|
| `--status-valid` | `#2E8B57` | `#3FB876` | Reading passed QC |
| `--status-suspect` | `#D9A02B` | `#E8B84D` | Borderline, under review |
| `--status-anomalous` | `#C1443C` | `#E0655C` | Flagged fault |
| `--status-offline` | `#8A8F98` | `#6B747C` | No data / dropout |

**Default theme:** light, for daytime control-room use and for the SIH demo itself (judges reviewing in a lit room, screen-shared/projected — light mode reads better projected and photographs better for a pitch deck). Dark mode is opt-in via a persistent toggle in the header (state stored per-user, not per-session) — see §3.1.

**What does *not* change between themes:** typography (same two families/roles), spacing scale, border-radius rules, layout structure, screen wireframes in §3, voice/copy in §5, and the "what to avoid" list in §7. Theme is a token swap, not a redesign.

### Typography
Two families, clearly distinct roles, no third:
- **Interface/body: `IBM Plex Sans`** — chosen because it's a typeface designed for instrumentation and technical interfaces (IBM's own systems), reads as precise without being cold. Weights 400/500/600 only.
- **Data/numeric: `IBM Plex Mono`** — used specifically for sensor readings, timestamps, station codes, coordinates. Tabular figures so numbers align in columns. This is a functional choice (numeric alignment matters when scanning a table of readings), not decoration.

Type scale (rem, 16px base):
| Role | Size | Weight | Family |
|---|---|---|---|
| Page title | 1.5 | 600 | Plex Sans |
| Section header | 1.125 | 600 | Plex Sans |
| Body | 0.9375 | 400 | Plex Sans |
| Metadata/caption | 0.8125 | 400 | Plex Sans, `--muted` |
| Sensor reading value | 1.125 | 500 | Plex Mono, tabular-nums |
| Station code | 0.8125 | 500 | Plex Mono |

Line length: keep body/explanatory text under 75 characters per line (alert descriptions, tooltips).

### Theme implementation notes (for the frontend build, F11)
- `Tailwind` config maps each utility to the CSS custom properties above (e.g. `bg-surface`, `text-ink`, `border-line`) rather than hardcoded Tailwind palette classes — this is what lets the same component tree render correctly in both themes with zero per-component theme logic.
- Toggle persists via `localStorage` (client-side UI preference only — not written to the `users` table in `database.md`, no backend round-trip needed for this).
- Map tiles: use a light and a dark Leaflet basemap pair (e.g. a light CARTO/OSM tile set and its dark counterpart) so the map itself switches too — a light-mode UI with a default OSM map sitting in a dark shell (or vice versa) is a common half-finished-dark-mode mistake, avoid it.
- Charts (Recharts): grid lines, axis text, and the "reference line" for a flagged point must all read `--line`/`--ink`/`--status-anomalous` from the active theme, not a hardcoded chart-library default gray — check this specifically, chart libraries are the most common place a theme switch gets forgotten.

### Layout
- Left-aligned throughout. No centered marketing-style layout — this is a working tool, not a landing page.
- 8px base spacing unit; panel padding 16–24px; dense but not cramped (operators scan this for hours — cramming causes fatigue, but marketing-scale whitespace wastes screen real estate they need for the map/data).
- Border radius: **4px, applied consistently and only to interactive containers** (buttons, panels, badges) — not the "every card gets the same soft-rounded-corner" SaaS default. Map markers and status dots are circular (functional, not decorative).

## 3. Screen specs

### 3.1 Map view (primary/landing screen — F11)
```
┌─────────────────────────────────────────────────────────────────┐
│ AeroSentinel        [Network health: 942 valid / 12 suspect /   │
│                       6 anomalous]     [🔔 6] [☀/☾] [admin ▾]   │
├───────────────┬─────────────────────────────────────────────────┤
│ Filter panel   │                                                  │
│  State: [ ▾]   │              [ India map, Leaflet ]               │
│  Status:       │        ● stations colored by status               │
│   ☑ valid      │        (green/amber/red/grey dots,                │
│   ☑ suspect    │         red pulses subtly on new anomaly)         │
│   ☑ anomalous  │                                                  │
│   ☑ offline    │                                                  │
│                │                                                  │
│ Recent alerts  │                                                  │
│  [station] ·   │                                                  │
│   flatline ·   │                                                  │
│   2 min ago     │                                                  │
│  [station] ·   │                                                  │
│   spike · ...  │                                                  │
└───────────────┴─────────────────────────────────────────────────┘
```
- Marker color = current status token above. Size constant (don't encode a second variable in marker size — keep it one signal, one meaning).
- A station transitioning to `anomalous` gets a brief (1–2 second, one-time) pulse/ring animation to draw the eye — this is the **one** orchestrated motion moment on this screen. No hover-animate-everything.
- Left rail: filters + a compact live alert list (newest first), clicking an alert jumps to 3.2.
- Header band shows network-wide counts in plain numerals, always visible — this is the "can I trust the network right now" glance-metric.

### 3.2 Station detail (F12)
```
┌─────────────────────────────────────────────────────────────────┐
│ ← Map      NCR004 · Faridabad                    [status: ⬤ anomalous] │
│  28.4089°N, 77.3178°E · 201m · last reading 3 min ago            │
├─────────────────────────────────────────────────────────────────┤
│  Temperature (°C)                                                 │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │      line chart, last 48h, flagged points marked ⚠          │
│  └───────────────────────────────────────────────────────────┘  │
│  [ similarly stacked: humidity / pressure / wind / rainfall ]    │
├─────────────────────────────────────────────────────────────────┤
│  Flagged: 14:32 IST — Flatline (confidence 0.91)                  │
│  Reason: 6 identical consecutive readings; spatial check:          │
│  4 neighboring stations show normal variation in this window.      │
│  [Confirm Fault]   [False Alarm]                                   │
└─────────────────────────────────────────────────────────────────┘
```
- Anomalous points on the chart use `--status-anomalous`, not a generic red highlight — consistent with the status token system.
- The reason text is written in plain operational language (per §5, Voice), not a raw JSON dump of `qc_results.details` — that raw data can be available behind a "details" disclosure for engineers, but the primary text must read like something a human meteorologist would say to a colleague.
- Confirm/False-Alarm buttons are the single clearest call-to-action on the page — high-contrast `--accent` for one, quiet outline for the other, not two equally-weighted buttons (they aren't equally likely/desirable outcomes to encourage carelessly).

### 3.3 Alerts feed (F13, can also be a full-width tab rather than just the rail)
- Table, not cards. This is scannable operational data (station, fault type, severity, time, status) — a dense `IBM Plex Mono`-numeric table with sortable columns fits the "instrument panel" register better than a SaaS card grid.
- Row left-border colored by severity (thin 3px bar), not full-row background tint — keeps the table calm and lets red genuinely stand out where it appears.

### 3.4 Admin / station management (F15/F1-adjacent)
- Standard form + table patterns, same type/color tokens. Not a design priority screen — keep it plain and functional, spend design effort on 3.1–3.3.

## 4. States (required for every data view)
- **Loading:** a thin indeterminate bar in `--accent` at the top of the panel — not a full-screen spinner that blanks the map/data the operator was just looking at.
- **Empty (e.g., new station, no history yet):** explicit text — "No readings yet for this station. Data will appear once it starts reporting." — not a blank chart with no explanation.
- **Error (e.g., ingestion/API failure):** state what happened and what to do — "Live updates paused — reconnecting…" with an auto-retry, not a silent stall or a raw stack trace.
- **Offline station:** distinct from `anomalous` — grey, not red — since "no data" and "bad data" are different operational problems (matches `fault_type = dropout` vs. others in `database.md`).

## 5. Voice & copy
- Plain, operational language. "Flatline detected — sensor may be stuck" not "Anomaly event triggered." Name the actual weather variable and fault type, always.
- Buttons say exactly what they do: **Confirm Fault**, **False Alarm**, **View station**, **Retrain model** — not "Submit" or "Go."
- No exclamation points, no alarmist copy — even `critical` severity is communicated through the color token and layout hierarchy, not through tone of voice. A disaster-management tool should never sound panicked; that erodes trust exactly when trust matters most.
- Empty/error states explain what happened and what to do next, in the system's own voice — see §4.

## 6. Accessibility & responsiveness
- All status information is encoded in **color + a text label + (for the map) marker distinctness** — never color alone, since red/green status is exactly the kind of signal that must survive color-vision deficiency in a safety-relevant tool.
- Visible keyboard focus states on every interactive element (buttons, map markers, table rows).
- Minimum contrast ratio 4.5:1 for body text against `--surface`/`--panel`.
- Dashboard is primarily a desktop/large-screen tool (operators at a workstation), but the station-detail and alerts views should degrade gracefully to tablet width for field technicians; the full map view is desktop-only in v1 (note this constraint rather than half-building a cramped mobile map).
- Respect `prefers-reduced-motion`: disable the map pulse animation and any chart entrance transitions for users who've set that preference.
- On first load (before any explicit toggle choice is stored), default to `prefers-color-scheme` if set, otherwise light (per §2's default-theme rationale) — don't force light on a user whose OS is set to dark and then require them to find the toggle.

## 7. What to explicitly avoid
Per the traits that read as generic/AI-templated rather than purpose-built — do not reach for these unless the content genuinely calls for it. Note: **dark mode itself is not on this list** — a deliberate, disciplined dark theme (§2) is legitimate for a 24/7 ops tool. What's avoided is the *generic execution* of it:
- Warm cream background with a terracotta accent, or a near-black background with a single bright neon/cyan accent used as decoration — our dark theme uses the same restrained teal family as light mode, not a hue swap to a "techy" neon.
- Identical rounded "SaaS cards" with soft grey drop-shadows and gradient washes as decoration — in dark mode this becomes "identical dark cards with a glow," same problem in a different palette; use the `--panel-raised` elevation step instead of shadows.
- ALL-CAPS tracked-out eyebrow labels above every section header, meta-strings joined with middle dots, em-dash "WORD — fragment" labels, or a monospace label slapped on things just for a "technical" look — `IBM Plex Mono` is used here for an actual functional reason (numeric alignment), not as a decorative signal.
- A marketing-style hero headline + subhead + two pill CTAs sitting on top of live operational data — this is a landing page pasted onto a dashboard, wrong register for a tool an operator lives in for hours. AeroSentinel opens straight into the map (§3.1), no hero section.
- Arrow-suffixed button/link text ("Explore detection →") — say what the action does in the label itself.
- Numbered-step markers (01/02/03) anywhere in this UI — nothing here is a linear onboarding sequence.
