import { useEffect, useState } from "react";
import {
  Activity,
  BarChart3,
  BookMarked,
  BookOpenCheck,
  ChevronRight,
  Database,
  FlaskConical,
  KeyRound,
  Menu,
  Network,
  PlayCircle,
  Search,
  Settings2,
  ShieldCheck,
  X,
} from "lucide-react";
import { NavLink, Outlet, useLocation, useNavigate } from "react-router-dom";
import { endpoints, useApi } from "../api/client";
import type { HealthResponse, SymbolsResponse } from "../types";
import { humanize, toneForStatus } from "../utils/format";
import { resolveSnapshotPresentation, snapshotRunState } from "../utils/snapshot";
import { StatusPill } from "./Ui";

export function AppShell() {
  const [menuOpen, setMenuOpen] = useState(false);
  const location = useLocation();
  const navigate = useNavigate();
  const symbolsState = useApi<SymbolsResponse>(endpoints.symbols);
  const healthState = useApi<HealthResponse>(endpoints.health);
  const symbols = symbolsState.data?.symbols ?? [];
  const shellSnapshot = healthState.data?.snapshot ?? symbolsState.data?.snapshot;
  const shellPresentation = shellSnapshot ? resolveSnapshotPresentation(shellSnapshot) : null;
  const runMode = shellPresentation?.displayMode || "no_run";
  const runState = shellPresentation
    ? snapshotRunState(shellPresentation)
    : "No persisted snapshot";

  useEffect(() => setMenuOpen(false), [location.pathname]);

  // React Router does not replicate the browser's native behavior of
  // scrolling to an #id on navigation -- that only happens on a real page
  // load, not client-side routing. Without this, a link like
  // "/operations/research#cross-sectional-momentum" changes the URL but
  // leaves the viewport wherever it already was, which reads as "the link
  // took me to the wrong section" even though the content is correct.
  useEffect(() => {
    if (!location.hash) return;
    const id = decodeURIComponent(location.hash.slice(1));
    const element = document.getElementById(id);
    element?.scrollIntoView({ behavior: "smooth", block: "start" });
  }, [location.pathname, location.hash]);

  const serviceStatus = healthState.error
    ? "unavailable"
    : healthState.loading
      ? "checking"
      : healthState.data?.data_status || healthState.data?.status || "unknown";

  return (
    <div className="app-shell">
      <a className="skip-link" href="#main-content">
        Skip to content
      </a>
      <header className="mobile-header">
        <Brand compact />
        <button
          className="icon-button"
          type="button"
          aria-expanded={menuOpen}
          aria-controls="primary-sidebar"
          aria-label={menuOpen ? "Close navigation" : "Open navigation"}
          onClick={() => setMenuOpen((value) => !value)}
        >
          {menuOpen ? <X aria-hidden="true" /> : <Menu aria-hidden="true" />}
        </button>
      </header>

      {menuOpen ? <button className="sidebar-scrim" aria-label="Close navigation" onClick={() => setMenuOpen(false)} /> : null}

      <aside id="primary-sidebar" className={`sidebar ${menuOpen ? "sidebar--open" : ""}`}>
        <Brand />

        <div className="mode-card">
          <span className="mode-card__pulse" aria-hidden="true" />
          <div>
            <strong>{humanize(runMode)}</strong>
            <span>{runState}</span>
          </div>
          <ShieldCheck aria-hidden="true" size={17} />
        </div>

        <nav className="primary-nav" aria-label="Primary navigation">
          <p className="nav-label">Workspace</p>
          <NavLink to="/" end>
            <Activity aria-hidden="true" />
            <span>Today</span>
            <ChevronRight className="nav-chevron" aria-hidden="true" />
          </NavLink>
          <NavLink to="/symbols">
            <BarChart3 aria-hidden="true" />
            <span>Symbol research</span>
            <ChevronRight className="nav-chevron" aria-hidden="true" />
          </NavLink>
          <a href="/#hierarchy">
            <Network aria-hidden="true" />
            <span>Decision hierarchy</span>
            <ChevronRight className="nav-chevron" aria-hidden="true" />
          </a>
          <a href="/#data-health">
            <Database aria-hidden="true" />
            <span>Data health</span>
            <ChevronRight className="nav-chevron" aria-hidden="true" />
          </a>

          <p className="nav-label nav-label--secondary">Operations</p>
          <NavLink to="/operations" end>
            <PlayCircle aria-hidden="true" />
            <span>Run pipeline</span>
            <ChevronRight className="nav-chevron" aria-hidden="true" />
          </NavLink>
          <NavLink to="/operations/data">
            <Database aria-hidden="true" />
            <span>Data management</span>
            <ChevronRight className="nav-chevron" aria-hidden="true" />
          </NavLink>
          <NavLink to="/operations/credentials">
            <KeyRound aria-hidden="true" />
            <span>Credentials</span>
            <ChevronRight className="nav-chevron" aria-hidden="true" />
          </NavLink>
          <NavLink to="/operations/strategies">
            <BookOpenCheck aria-hidden="true" />
            <span>Strategy registry</span>
            <ChevronRight className="nav-chevron" aria-hidden="true" />
          </NavLink>
          <NavLink to="/operations/research">
            <FlaskConical aria-hidden="true" />
            <span>Research</span>
            <ChevronRight className="nav-chevron" aria-hidden="true" />
          </NavLink>
          <NavLink to="/operations/methodology">
            <BookMarked aria-hidden="true" />
            <span>Methodology</span>
            <ChevronRight className="nav-chevron" aria-hidden="true" />
          </NavLink>
        </nav>

        <div className="symbol-jump">
          <label htmlFor="symbol-jump-select">
            <Search aria-hidden="true" size={14} /> Symbol jump
          </label>
          <select
            id="symbol-jump-select"
            value=""
            disabled={!symbols.length}
            onChange={(event) => {
              if (event.target.value) navigate(`/symbols/${encodeURIComponent(event.target.value)}`);
            }}
          >
            <option value="">{symbols.length ? "Select a symbol" : "No symbols available"}</option>
            {symbols.map((symbol) => (
              <option key={symbol.symbol} value={symbol.symbol}>
                {symbol.symbol}{symbol.name ? ` · ${symbol.name}` : ""}
              </option>
            ))}
          </select>
        </div>

        <div className="sidebar-footer">
          <div className="sidebar-footer__row">
            <span>Data service</span>
            <StatusPill value={humanize(serviceStatus)} tone={toneForStatus(serviceStatus)} />
          </div>
          <p><Settings2 aria-hidden="true" size={11} /> Operator tools are local-only</p>
        </div>
      </aside>

      <main id="main-content" className="main-content" tabIndex={-1}>
        <Outlet />
      </main>
    </div>
  );
}

function Brand({ compact = false }: { compact?: boolean }) {
  return (
    <div className={`brand ${compact ? "brand--compact" : ""}`} aria-label="HEAE trade desk">
      <span className="brand__mark" aria-hidden="true">
        <i />
        <i />
        <i />
      </span>
      <span className="brand__copy">
        <strong>HEAE</strong>
        <small>Trade desk</small>
      </span>
    </div>
  );
}
