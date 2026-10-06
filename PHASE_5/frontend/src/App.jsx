import { useEffect, useMemo, useState } from "react";
import { GeoJSON, MapContainer, TileLayer, useMap } from "react-leaflet";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000";
const GRID_API_BASE_URL = import.meta.env.VITE_GRID_API_BASE_URL || API_BASE_URL;
const SIGNAL_API_BASE_URL = import.meta.env.VITE_SIGNAL_API_BASE_URL || API_BASE_URL;
const RISK_API_BASE_URL = import.meta.env.VITE_RISK_API_BASE_URL || API_BASE_URL;
const pages = ["Overview", "Grid Activity", "Alerts", "Risk"];

// Exact extent of data/reference/milano-grid.geojson (100 x 100 Telecom Italia cells).
const MILAN_BOUNDS = [[45.356262, 9.011491], [45.568214, 9.312688]];
const MILAN_CENTER = [45.462238, 9.162089];
const GRID_GEOJSON_URL = `${import.meta.env.BASE_URL}reference/milano-grid-web.geojson`;
const SEVERITY_RANK = { low: 1, medium: 2, high: 3 };
const SEVERITY_FILL = { low: "#75ae88", medium: "#d6a544", high: "#c95d4c" };

function App() {
  const [page, setPage] = useState("Overview");
  const [state, setState] = useState({ status: "loading", data: null, error: "" });
  const [gridId, setGridId] = useState("5161");
  const [gridState, setGridState] = useState({ status: "idle", data: null, error: "" });
  const [signalState, setSignalState] = useState({ status: "loading", hotspots: [], alerts: [], error: "" });
  const [riskState, setRiskState] = useState({ status: "idle", data: null, error: "" });

  useEffect(() => {
    const controller = new AbortController();

    fetch(`${API_BASE_URL}/network/summary`, { signal: controller.signal })
      .then((response) => {
        if (!response.ok) throw new Error(`API request failed (${response.status})`);
        return response.json();
      })
      .then((data) => setState({ status: "success", data, error: "" }))
      .catch((error) => {
        if (error.name !== "AbortError") {
          setState({ status: "error", data: null, error: error.message });
        }
      });

    return () => controller.abort();
  }, []);

  useEffect(() => {
    if (page !== "Alerts" || signalState.status !== "loading") return undefined;
    Promise.all([
      fetch(`${SIGNAL_API_BASE_URL}/network/hotspots?limit=100`).then((response) => response.json().then((data) => ({ response, data }))),
      fetch(`${SIGNAL_API_BASE_URL}/network/alerts?limit=100`).then((response) => response.json().then((data) => ({ response, data }))),
    ])
      .then(([hotspots, alerts]) => {
        const failed = [hotspots, alerts].find(({ response }) => !response.ok);
        if (failed) throw new Error(`Signal request failed (${failed.response.status})`);
        setSignalState({ status: "success", hotspots: hotspots.data.items, alerts: alerts.data.items, error: "" });
      })
      .catch((error) => setSignalState((current) => ({ ...current, status: "error", error: error.message })));
  }, [page, signalState.status]);

  function searchGrid(event) {
    event.preventDefault();
    const parsedGridId = Number(gridId);
    if (!Number.isInteger(parsedGridId) || parsedGridId < 1 || parsedGridId > 10000) {
      setGridState({ status: "error", data: null, error: "Enter a grid ID between 1 and 10000." });
      return;
    }
    setGridState({ status: "loading", data: null, error: "" });
    fetch(`${GRID_API_BASE_URL}/network/grid/${parsedGridId}`)
      .then((response) => response.json().then((data) => ({ response, data })))
      .then(({ response, data }) => {
        if (!response.ok) throw new Error(data.detail || `Grid request failed (${response.status})`);
        setGridState({ status: "success", data, error: "" });
      })
      .catch((error) => setGridState({ status: "error", data: null, error: error.message }));
  }

  return (
    <main className="app-shell">
      <header className="topbar">
        <div>
          <p className="eyebrow">MILANO / NETWORK OPERATIONS</p>
          <h1>Signal board</h1>
        </div>
        <nav aria-label="Dashboard pages">
          {pages.map((item) => (
            <button className={page === item ? "nav-item active" : "nav-item"} key={item} onClick={() => setPage(item)}>
              {item}
            </button>
          ))}
        </nav>
      </header>

      <section className="page-heading">
        <div>
          <p className="eyebrow">LIVE VIEW / {page.toUpperCase()}</p>
          <h2>{page === "Overview" ? "Network pulse" : page}</h2>
        </div>
        <span className={`status-dot ${state.status}`}>{state.status}</span>
      </section>

      {state.status === "loading" && <section className="message-panel">Loading network summary...</section>}
      {state.status === "error" && <section className="status-banner error-panel">Unable to load network summary: {state.error}</section>}
      {state.status === "success" && <DashboardSummary data={state.data} page={page} gridId={gridId} setGridId={setGridId} searchGrid={searchGrid} gridState={gridState} signalState={signalState} setPage={setPage} riskState={riskState} setRiskState={setRiskState} />}
    </main>
  );
}

function DashboardSummary({ data, page, gridId, setGridId, searchGrid, gridState, signalState, setPage, riskState, setRiskState }) {
  if (page !== "Overview") {
    if (page === "Grid Activity") {
      return <GridActivity gridId={gridId} setGridId={setGridId} searchGrid={searchGrid} gridState={gridState} />;
    }
    if (page === "Alerts") return <SignalsView signalState={signalState} />;
    if (page === "Risk") return <RiskView riskState={riskState} setRiskState={setRiskState} />;
    return <section className="message-panel">{page} data is ready for the next API integration.</section>;
  }

  const metrics = [
    ["Total activity", data.total_activity.toLocaleString(undefined, { maximumFractionDigits: 0 }), "units"],
    ["Active grids", data.active_grids.toLocaleString(), "cells"],
    ["Peak hour", `${String(data.peak_hour).padStart(2, "0")}:00`, "local time"],
    ["Top grid", data.top_grid.toLocaleString(), "grid ID"],
  ];

  return (
    <>
      <section className="metric-grid">
        {metrics.map(([label, value, unit]) => (
          <article className="metric" key={label}>
            <p>{label}</p>
            <strong>{value}</strong>
            <span>{unit}</span>
          </article>
        ))}
      </section>
      <section className="as-of-panel">
        <span>Reporting timestamp</span>
        <strong>{new Date(data.as_of).toLocaleString()}</strong>
        <span className="live-mark">CURATED DATA</span>
      </section>
    </>
  );
}

// RE5: submit feature values, keep model output separate, and reserve an AI explanation action.
function RiskView({ riskState, setRiskState }) {
  const [form, setForm] = useState({ grid_id: "5161", avg_activity: "1000", activity_growth: "0", active_hours: "24", peak_ratio: "1", variability: "0", internet_share: "0.5", feature_timestamp: "2013-11-07T23:00" });
  function updateField(event) {
    setForm((current) => ({ ...current, [event.target.name]: event.target.value }));
  }
  function submitRisk(event) {
    event.preventDefault();
    setRiskState({ status: "loading", data: null, error: "" });
    const payload = { ...form, grid_id: Number(form.grid_id), avg_activity: Number(form.avg_activity), activity_growth: Number(form.activity_growth), active_hours: Number(form.active_hours), peak_ratio: Number(form.peak_ratio), variability: Number(form.variability), internet_share: Number(form.internet_share), feature_timestamp: new Date(form.feature_timestamp).toISOString() };
    fetch(`${RISK_API_BASE_URL}/network/predict-risk`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) })
      .then((response) => response.json().then((data) => ({ response, data })))
      .then(({ response, data }) => { if (!response.ok) throw new Error(data.detail?.map?.((item) => item.msg).join(", ") || data.detail || `Risk request failed (${response.status})`); setRiskState({ status: "success", data, error: "" }); })
      .catch((error) => setRiskState({ status: "error", data: null, error: error.message }));
  }
  return <section className="risk-view"><form className="risk-form" onSubmit={submitRisk}><div className="risk-form-heading"><p className="eyebrow">MODEL INPUTS</p><h3>Score a grid</h3></div><div className="risk-fields">{[["grid_id", "Grid ID"], ["avg_activity", "Average activity"], ["activity_growth", "Activity growth"], ["active_hours", "Active hours"], ["peak_ratio", "Peak ratio"], ["variability", "Variability"], ["internet_share", "Internet share"], ["feature_timestamp", "Feature timestamp"]].map(([name, label]) => <label key={name}>{label}<input name={name} type={name === "feature_timestamp" ? "datetime-local" : "number"} step="any" value={form[name]} onChange={updateField} required /></label>)}</div><button className="risk-submit" type="submit">Predict risk</button></form>{riskState.status === "loading" && <section className="status-banner">Submitting prediction...</section>}{riskState.status === "error" && <section className="status-banner error-panel">Risk unavailable: {riskState.error}</section>}{riskState.status === "success" && <RiskResult data={riskState.data} />}</section>;
}

function RiskResult({ data }) {
  return <section className="risk-result"><div className="risk-output"><p className="eyebrow">MODEL OUTPUT</p><div className="risk-output-grid"><div><span>Risk score</span><strong>{data.risk_score.toFixed(2)}</strong></div><div><span>Risk level</span><strong>{data.risk_level}</strong></div><div><span>Model version</span><strong>{data.model_version}</strong></div></div></div><div className="risk-explanation"><p className="eyebrow">NARRATIVE EXPLANATION</p><p>{data.explanation_note}</p><button type="button" disabled title="Available after Claude integration">Explain with AI</button></div></section>;
}

function SignalsView({ signalState }) {
  const [limit, setLimit] = useState(10);
  const [severity, setSeverity] = useState("all");
  if (signalState.status === "loading") return <section className="message-panel">Loading hotspots, alerts, and Milan grid...</section>;
  if (signalState.status === "error") return <section className="status-banner error-panel">Unable to load signals: {signalState.error}</section>;

  const combined = [...signalState.hotspots.map((item) => ({ ...item, source: "HOTSPOT", status: "ATTENTION" })), ...signalState.alerts.map((item) => ({ ...item, source: "ALERT", status: item.severity === "high" ? "HIGH" : "ATTENTION" }))]
    .filter((item) => severity === "all" || item.severity === severity)
    .sort((left, right) => right.total_activity - left.total_activity)
    .slice(0, limit);
  return (
    <section className="signals-view">
      <div className="signal-toolbar">
        <label>Show <select value={limit} onChange={(event) => setLimit(Number(event.target.value))}><option value="10">10 rows</option><option value="25">25 rows</option><option value="50">50 rows</option></select></label>
        <label>Severity <select value={severity} onChange={(event) => setSeverity(event.target.value)}><option value="all">All</option><option value="high">High</option><option value="medium">Medium</option><option value="low">Low</option></select></label>
      </div>
      <div className="signals-layout">
        <SignalMap hotspots={signalState.hotspots} alerts={signalState.alerts} />
        <section className="alert-panel">
          <div className="table-heading"><span>Ranked alerts and hotspots</span><span>{combined.length} shown</span></div>
          <div className="alert-summary"><strong>{signalState.alerts.length}</strong><span>alerts</span><strong>{signalState.hotspots.length}</strong><span>hotspots</span></div>
          <div className="ranked-table table-wrap"><table><thead><tr><th>Grid</th><th>Activity</th><th>Status</th><th>Timestamp</th></tr></thead><tbody>{combined.map((item) => <tr key={`${item.source}-${item.grid_id}-${item.timestamp}`}><td>{item.grid_id}</td><td>{item.total_activity.toLocaleString(undefined, { maximumFractionDigits: 0 })}</td><td><span className={`signal-status ${item.status.toLowerCase()}`}>{item.status}</span></td><td>{new Date(item.timestamp).toLocaleString()}</td></tr>)}</tbody></table></div>
        </section>
      </div>
    </section>
  );
}

// Leaflet measures its container on creation. React-leaflet mounts the map before the
// panel has been laid out, so without this the fit falls back to zoom 0 and the whole
// world tile is stretched across the panel as giant blue/yellow blocks.
function FitMilanBounds() {
  const map = useMap();
  useEffect(() => {
    const refit = () => {
      map.invalidateSize();
      map.fitBounds(MILAN_BOUNDS);
    };
    const frame = requestAnimationFrame(refit);
    window.addEventListener("resize", refit);
    return () => {
      cancelAnimationFrame(frame);
      window.removeEventListener("resize", refit);
    };
  }, [map]);
  return null;
}

// Only the flagged cells are drawn: the reference layer holds all 10000 grid polygons and
// painting every one of them buries the basemap.
function toFlaggedCells(hotspots, alerts) {
  const flagged = new Map();
  const candidates = [
    ...hotspots.map((item) => ({ ...item, source: "HOTSPOT", severity: item.severity || "medium" })),
    ...alerts.map((item) => ({ ...item, source: "ALERT", severity: item.severity || "medium" })),
  ];
  for (const item of candidates) {
    const current = flagged.get(item.grid_id);
    const outranks = !current
      || (SEVERITY_RANK[item.severity] || 0) > (SEVERITY_RANK[current.severity] || 0)
      || ((SEVERITY_RANK[item.severity] || 0) === (SEVERITY_RANK[current.severity] || 0) && item.total_activity > current.total_activity);
    if (outranks) flagged.set(item.grid_id, item);
  }
  return flagged;
}

function SignalMap({ hotspots, alerts }) {
  const [grid, setGrid] = useState({ status: "loading", cells: null, error: "" });

  useEffect(() => {
    const controller = new AbortController();
    fetch(GRID_GEOJSON_URL, { signal: controller.signal })
      .then((response) => {
        if (!response.ok) throw new Error(`Grid layer failed (${response.status})`);
        return response.json();
      })
      .then((data) => {
        const cells = new Map();
        for (const feature of data.features) cells.set(Number(feature.properties.grid_id), feature);
        setGrid({ status: "success", cells, error: "" });
      })
      .catch((error) => {
        if (error.name !== "AbortError") setGrid({ status: "error", cells: null, error: error.message });
      });
    return () => controller.abort();
  }, []);

  const layer = useMemo(() => {
    if (grid.status !== "success") return null;
    const flagged = toFlaggedCells(hotspots, alerts);
    const features = [];
    for (const [gridId, signal] of flagged) {
      const cell = grid.cells.get(gridId);
      if (!cell) continue;
      features.push({ ...cell, properties: { ...cell.properties, ...signal } });
    }
    return { type: "FeatureCollection", features };
  }, [grid, hotspots, alerts]);

  const cellCount = layer ? layer.features.length : 0;
  return (
    <section className="map-panel">
      <div className="map-header">
        <span>Milan / OpenStreetMap</span>
        <span>{grid.status === "success" ? `${cellCount} FLAGGED CELLS` : "LOADING GRID"}</span>
      </div>
      <MapContainer
        className="leaflet-map"
        center={MILAN_CENTER}
        zoom={11}
        minZoom={10}
        maxZoom={16}
        maxBounds={MILAN_BOUNDS}
        maxBoundsViscosity={0.7}
        scrollWheelZoom
      >
        <FitMilanBounds />
        <TileLayer noWrap attribution="&copy; OpenStreetMap contributors" url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" />
        {layer && layer.features.length > 0 && (
          <GeoJSON
            key={layer.features.map((feature) => feature.properties.grid_id).join("-")}
            data={layer}
            style={(feature) => ({
              className: "map-cell",
              color: SEVERITY_FILL[feature.properties.severity] || SEVERITY_FILL.medium,
              weight: 1,
              fillColor: SEVERITY_FILL[feature.properties.severity] || SEVERITY_FILL.medium,
              fillOpacity: 0.45,
            })}
            onEachFeature={(feature, cellLayer) => {
              const { grid_id: cellId, source, severity, total_activity: activity, timestamp } = feature.properties;
              cellLayer.bindPopup(`<strong>Grid ${cellId}</strong><br/>${source} / ${String(severity).toUpperCase()}<br/>${Math.round(activity).toLocaleString()} units<br/>${new Date(timestamp).toLocaleString()}`);
            }}
          />
        )}
      </MapContainer>
      {grid.status === "error" && <p className="map-note">Grid layer unavailable: {grid.error}</p>}
      <div className="legend">
        <span className="normal">Low</span>
        <span className="attention">Medium</span>
        <span className="high">High</span>
      </div>
    </section>
  );
}

function GridActivity({ gridId, setGridId, searchGrid, gridState }) {
  return (
    <section className="grid-view">
      <form className="grid-search" onSubmit={searchGrid}>
        <label htmlFor="grid-id">Grid ID</label>
        <input id="grid-id" type="number" min="1" max="10000" value={gridId} onChange={(event) => setGridId(event.target.value)} />
        <button type="submit">Search</button>
      </form>
      {gridState.status === "idle" && <p className="grid-note">Search for a grid to inspect its hourly activity.</p>}
      {gridState.status === "loading" && <section className="message-panel">Loading grid activity...</section>}
      {gridState.status === "error" && <section className="status-banner error-panel">Grid unavailable: {gridState.error}</section>}
      {gridState.status === "success" && <ActivityTable data={gridState.data} />}
    </section>
  );
}

function ActivityTable({ data }) {
  return (
    <div className="table-wrap">
      <div className="table-heading"><span>Grid {data.grid_id}</span><span>{data.activity.length} hourly records</span></div>
      <table>
        <thead><tr><th>Timestamp</th><th>Call</th><th>SMS</th><th>Internet</th><th>Total</th></tr></thead>
        <tbody>{data.activity.map((point) => <tr key={point.timestamp}><td>{new Date(point.timestamp).toLocaleString()}</td><td>{point.call_activity.toLocaleString()}</td><td>{point.sms_activity.toLocaleString()}</td><td>{point.internet_activity.toLocaleString()}</td><td className="total-cell">{point.total_activity.toLocaleString()}</td></tr>)}</tbody>
      </table>
    </div>
  );
}

export default App;