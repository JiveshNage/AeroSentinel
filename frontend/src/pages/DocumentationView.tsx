import React, { useState } from 'react';
import {
  BookOpen,
  FileText,
  Download,
  ExternalLink,
  Shield,
  Layers,
  CheckCircle2,
  Zap,
  Code2,
  Eye,
} from 'lucide-react';
import { AuthUser } from '../api/auth';
import { AppNavTab } from '../components/Sidebar';

interface DocumentationViewProps {
  currentUser: AuthUser | null;
  onNavigateTab?: (tab: AppNavTab) => void;
}

export const DocumentationView: React.FC<DocumentationViewProps> = ({
  currentUser,
  onNavigateTab,
}) => {
  const [activeTab, setActiveTab] = useState<'manual' | 'spec' | 'api' | 'viewer'>('manual');
  const [selectedPdfToView, setSelectedPdfToView] = useState<'manual' | 'spec'>('manual');

  const pdfFiles = {
    manual: {
      title: 'AeroSentinel Operational User Manual',
      filename: 'AeroSentinel_User_Manual.pdf',
      path: '/AeroSentinel_User_Manual.pdf',
      version: 'v2.4-PROD',
      size: '1.8 MB',
      description:
        'Standard Operating Procedures (SOP) & step-by-step user guide for meteorological quality control, anomaly triage, role-based workflows, and predictive maintenance dispatch.',
      target: 'Forecasters, QC Analysts, Field Technicians, Station Operators',
    },
    spec: {
      title: 'AeroSentinel Technical Product Specification & Architecture',
      filename: 'AeroSentinel_Technical_Product_Spec.pdf',
      path: '/AeroSentinel_Technical_Product_Spec.pdf',
      version: 'v2.4-PROD',
      size: '1.8 MB',
      description:
        'Complete system architecture dossier: SIH 26073 problem definition, 4-tier QC engine mathematics, 3D KDTree spatial cross-validation, Explainable AI (SHAP), self-healing network, and zero-false-alarm benchmark proof.',
      target: 'System Architects, Data Scientists, IMD Technical Officers, Evaluators',
    },
  };

  return (
    <div className="space-y-8 pb-12 font-sans select-none">
      {/* Hero Banner */}
      <div className="bg-panel border border-line rounded-2xl p-6 sm:p-8 relative overflow-hidden shadow-lg backdrop-blur-md">
        <div className="relative z-10 max-w-3xl space-y-3">
          <div className="flex flex-wrap items-center gap-2.5">
            <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-accent/15 border border-accent/30 text-accent font-mono text-xs font-semibold">
              <BookOpen className="w-3.5 h-3.5" />
              Official Documentation & Publication Library
            </div>
            {currentUser && (
              <div className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-surface border border-line text-muted font-mono text-[11px]">
                <Shield className="w-3 h-3 text-accent" />
                <span>Active Clearance: <strong className="text-ink uppercase">{currentUser.role}</strong></span>
              </div>
            )}
          </div>
          <h1 className="text-2xl sm:text-3xl font-bold text-ink tracking-tight">
            AeroSentinel Knowledge Base & Product Manuals
          </h1>
          <p className="text-sm text-muted leading-relaxed">
            Access verified operational manuals, mathematical specifications, Explainable AI architectures,
            and interactive guides for the AeroSentinel Automatic Weather Station (AWS) Quality Control System (SIH 26073).
          </p>
        </div>

        {/* Decorative corner glow */}
        <div className="absolute right-0 top-0 w-80 h-80 bg-accent/5 rounded-full blur-3xl -z-0 pointer-events-none" />
      </div>

      {/* Primary Download Cards Section */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* PDF Card 1: User Manual */}
        <div className="bg-panel border border-line hover:border-accent/50 rounded-xl p-6 flex flex-col justify-between transition-all duration-200 shadow-sm hover:shadow-md group">
          <div className="space-y-4">
            <div className="flex items-start justify-between">
              <div className="p-3 rounded-lg bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 group-hover:scale-105 transition-transform">
                <BookOpen className="w-6 h-6" />
              </div>
              <div className="flex items-center gap-2">
                <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-surface border border-line text-muted">
                  {pdfFiles.manual.size}
                </span>
                <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-emerald-500/15 text-emerald-400 border border-emerald-500/30 font-semibold">
                  {pdfFiles.manual.version}
                </span>
              </div>
            </div>

            <div>
              <h2 className="text-base sm:text-lg font-bold text-ink group-hover:text-accent transition-colors">
                {pdfFiles.manual.title}
              </h2>
              <p className="text-xs text-muted mt-2 leading-relaxed">
                {pdfFiles.manual.description}
              </p>
            </div>

            <div className="space-y-1.5 pt-2 border-t border-line text-xs">
              <div className="flex items-center text-muted text-[11px]">
                <strong className="text-ink mr-1.5 font-medium">Target Personas:</strong>
                <span>{pdfFiles.manual.target}</span>
              </div>
              <div className="flex items-center text-muted text-[11px]">
                <strong className="text-ink mr-1.5 font-medium">Standards:</strong>
                <span>IMD AWS SOP, WMO No. 8 Instrument Protocols</span>
              </div>
            </div>
          </div>

          <div className="pt-6 mt-6 border-t border-line flex flex-col sm:flex-row items-stretch sm:items-center gap-3">
            <a
              href={pdfFiles.manual.path}
              download={pdfFiles.manual.filename}
              className="flex-1 inline-flex items-center justify-center gap-2 px-4 py-2.5 rounded-lg bg-accent text-white hover:bg-accent/90 text-xs font-semibold shadow-xs transition-all"
            >
              <Download className="w-4 h-4" />
              Download User Manual PDF
            </a>
            <a
              href={pdfFiles.manual.path}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center justify-center gap-1.5 px-3 py-2.5 rounded-lg bg-surface hover:bg-hover border border-line text-ink text-xs font-medium transition-colors"
              title="Open PDF directly in a new browser tab"
            >
              <ExternalLink className="w-3.5 h-3.5" />
              View in Tab
            </a>
          </div>
        </div>

        {/* PDF Card 2: Technical Product Spec */}
        <div className="bg-panel border border-line hover:border-accent/50 rounded-xl p-6 flex flex-col justify-between transition-all duration-200 shadow-sm hover:shadow-md group">
          <div className="space-y-4">
            <div className="flex items-start justify-between">
              <div className="p-3 rounded-lg bg-sky-500/10 text-sky-400 border border-sky-500/20 group-hover:scale-105 transition-transform">
                <FileText className="w-6 h-6" />
              </div>
              <div className="flex items-center gap-2">
                <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-surface border border-line text-muted">
                  {pdfFiles.spec.size}
                </span>
                <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-sky-500/15 text-sky-400 border border-sky-500/30 font-semibold">
                  {pdfFiles.spec.version}
                </span>
              </div>
            </div>

            <div>
              <h2 className="text-base sm:text-lg font-bold text-ink group-hover:text-accent transition-colors">
                {pdfFiles.spec.title}
              </h2>
              <p className="text-xs text-muted mt-2 leading-relaxed">
                {pdfFiles.spec.description}
              </p>
            </div>

            <div className="space-y-1.5 pt-2 border-t border-line text-xs">
              <div className="flex items-center text-muted text-[11px]">
                <strong className="text-ink mr-1.5 font-medium">Target Personas:</strong>
                <span>{pdfFiles.spec.target}</span>
              </div>
              <div className="flex items-center text-muted text-[11px]">
                <strong className="text-ink mr-1.5 font-medium">Algorithms:</strong>
                <span>SHAP TreeExplainer, 3D KDTree, IDW, LSTM-AE</span>
              </div>
            </div>
          </div>

          <div className="pt-6 mt-6 border-t border-line flex flex-col sm:flex-row items-stretch sm:items-center gap-3">
            <a
              href={pdfFiles.spec.path}
              download={pdfFiles.spec.filename}
              className="flex-1 inline-flex items-center justify-center gap-2 px-4 py-2.5 rounded-lg bg-[#2563EB] text-white hover:bg-[#1D4ED8] text-xs font-semibold shadow-xs transition-all"
            >
              <Download className="w-4 h-4" />
              Download Technical Spec PDF
            </a>
            <a
              href={pdfFiles.spec.path}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center justify-center gap-1.5 px-3 py-2.5 rounded-lg bg-surface hover:bg-hover border border-line text-ink text-xs font-medium transition-colors"
              title="Open PDF directly in a new browser tab"
            >
              <ExternalLink className="w-3.5 h-3.5" />
              View in Tab
            </a>
          </div>
        </div>
      </div>

      {/* Interactive Tabs Header */}
      <div className="border-b border-line flex items-center space-x-1 sm:space-x-2 text-xs font-medium">
        <button
          onClick={() => setActiveTab('manual')}
          className={`px-4 py-2.5 border-b-2 transition-all flex items-center gap-2 ${
            activeTab === 'manual'
              ? 'border-accent text-accent font-semibold'
              : 'border-transparent text-muted hover:text-ink'
          }`}
        >
          <BookOpen className="w-4 h-4" />
          <span>How to Use (User Guide)</span>
        </button>

        <button
          onClick={() => setActiveTab('spec')}
          className={`px-4 py-2.5 border-b-2 transition-all flex items-center gap-2 ${
            activeTab === 'spec'
              ? 'border-accent text-accent font-semibold'
              : 'border-transparent text-muted hover:text-ink'
          }`}
        >
          <Layers className="w-4 h-4" />
          <span>Product Architecture & QC Tiers</span>
        </button>

        <button
          onClick={() => setActiveTab('api')}
          className={`px-4 py-2.5 border-b-2 transition-all flex items-center gap-2 ${
            activeTab === 'api'
              ? 'border-accent text-accent font-semibold'
              : 'border-transparent text-muted hover:text-ink'
          }`}
        >
          <Code2 className="w-4 h-4" />
          <span>API Reference</span>
        </button>

        <button
          onClick={() => setActiveTab('viewer')}
          className={`px-4 py-2.5 border-b-2 transition-all flex items-center gap-2 ${
            activeTab === 'viewer'
              ? 'border-accent text-accent font-semibold'
              : 'border-transparent text-muted hover:text-ink'
          }`}
        >
          <Eye className="w-4 h-4" />
          <span>Embedded PDF Viewer</span>
        </button>
      </div>

      {/* TAB 1: HOW TO USE (USER GUIDE) */}
      {activeTab === 'manual' && (
        <div className="space-y-6">
          {/* Quick Start 4-Step Flow */}
          <div className="bg-panel border border-line rounded-xl p-6 space-y-4">
            <h3 className="text-base font-bold text-ink flex items-center gap-2">
              <Zap className="w-4 h-4 text-amber-400" />
              Quick Start: Operator 4-Step Onboarding
            </h3>

            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 pt-2">
              <div className="p-4 rounded-lg bg-surface border border-line space-y-2">
                <div className="w-6 h-6 rounded-full bg-accent/20 text-accent font-mono text-xs font-bold flex items-center justify-center">
                  1
                </div>
                <h4 className="text-xs font-bold text-ink">Select Your Persona</h4>
                <p className="text-[11px] text-muted">
                  Use the top right profile pill to switch between <b>Duty Forecaster</b>, <b>QC Analyst</b>,{' '}
                  <b>Field Technician</b>, or <b>Administrator</b>.
                </p>
              </div>

              <div
                onClick={() => onNavigateTab?.('map')}
                className="p-4 rounded-lg bg-surface border border-line space-y-2 cursor-pointer hover:border-accent/40 transition-colors"
                title="Click to navigate to Fleet Map"
              >
                <div className="w-6 h-6 rounded-full bg-accent/20 text-accent font-mono text-xs font-bold flex items-center justify-center">
                  2
                </div>
                <h4 className="text-xs font-bold text-ink">Monitor Real-Time Fleet →</h4>
                <p className="text-[11px] text-muted">
                  Open the <b>Fleet Map</b> or <b>Live Stream</b> to observe active AWS telemetry across the NCR
                  grid and verify operational health.
                </p>
              </div>

              <div
                onClick={() => onNavigateTab?.('alerts')}
                className="p-4 rounded-lg bg-surface border border-line space-y-2 cursor-pointer hover:border-accent/40 transition-colors"
                title="Click to navigate to Alerts Feed"
              >
                <div className="w-6 h-6 rounded-full bg-accent/20 text-accent font-mono text-xs font-bold flex items-center justify-center">
                  3
                </div>
                <h4 className="text-xs font-bold text-ink">Triage Anomaly Alerts →</h4>
                <p className="text-[11px] text-muted">
                  Under <b>Monitoring → Alerts</b>, review flagged readings, inspect SHAP feature attributions, and
                  submit binding QC feedback.
                </p>
              </div>

              <div
                onClick={() => onNavigateTab?.('maintenance')}
                className="p-4 rounded-lg bg-surface border border-line space-y-2 cursor-pointer hover:border-accent/40 transition-colors"
                title="Click to navigate to Predictive Maintenance"
              >
                <div className="w-6 h-6 rounded-full bg-accent/20 text-accent font-mono text-xs font-bold flex items-center justify-center">
                  4
                </div>
                <h4 className="text-xs font-bold text-ink">Dispatch Maintenance →</h4>
                <p className="text-[11px] text-muted">
                  Under <b>Operations → Maintenance</b>, inspect stations ranked by 30-day failure risk and issue
                  proactive field repair work orders.
                </p>
              </div>
            </div>
          </div>

          {/* Role-Specific Workflows */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {/* Duty Forecaster Guide */}
            <div className="bg-panel border border-line rounded-xl p-5 space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-xs font-mono font-bold uppercase tracking-wider text-sky-400">
                  Duty Forecaster Workflow
                </span>
                <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-sky-500/10 text-sky-400 border border-sky-500/30">
                  Synoptic Oversight
                </span>
              </div>
              <ul className="text-xs text-muted space-y-2">
                <li className="flex items-start gap-2">
                  <CheckCircle2 className="w-3.5 h-3.5 text-sky-400 shrink-0 mt-0.5" />
                  <span>
                    <b>Fleet Geospatial Status:</b> Use the Fleet Map to track weather stations color-coded by real-time status (Normal, Suspect, Anomalous, Stale).
                  </span>
                </li>
                <li className="flex items-start gap-2">
                  <CheckCircle2 className="w-3.5 h-3.5 text-sky-400 shrink-0 mt-0.5" />
                  <span>
                    <b>Live Telemetry Streams:</b> Watch incoming high-frequency packets. Click <i>Pause</i> when a sudden severe squall or microburst is observed.
                  </span>
                </li>
                <li className="flex items-start gap-2">
                  <CheckCircle2 className="w-3.5 h-3.5 text-sky-400 shrink-0 mt-0.5" />
                  <span>
                    <b>Self-Healing Imputation:</b> Downstream numerical forecast feeds receive continuous, spatial IDW-corrected values even during sensor failure.
                  </span>
                </li>
              </ul>
            </div>

            {/* QC Analyst Guide */}
            <div className="bg-panel border border-line rounded-xl p-5 space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-xs font-mono font-bold uppercase tracking-wider text-emerald-400">
                  QC Analyst Workflow
                </span>
                <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-emerald-500/10 text-emerald-400 border border-emerald-500/30">
                  Adjudication & Feedback
                </span>
              </div>
              <ul className="text-xs text-muted space-y-2">
                <li className="flex items-start gap-2">
                  <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400 shrink-0 mt-0.5" />
                  <span>
                    <b>Alert Triage:</b> Filter open alerts by Critical, High, or Medium severity. Click <i>Acknowledge</i> to claim the ticket.
                  </span>
                </li>
                <li className="flex items-start gap-2">
                  <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400 shrink-0 mt-0.5" />
                  <span>
                    <b>Human Feedback Labeling:</b> Click <b>Confirm Fault</b> if physical damage or drift is verified, or <b>Mark Genuine / False Alarm</b> if peer stations confirm extreme weather.
                  </span>
                </li>
                <li className="flex items-start gap-2">
                  <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400 shrink-0 mt-0.5" />
                  <span>
                    <b>Active Learning Retrain:</b> In the Model Audit tab, trigger active learning retraining once ≥10 feedback samples are pooled.
                  </span>
                </li>
              </ul>
            </div>

            {/* Field Technician Guide */}
            <div className="bg-panel border border-line rounded-xl p-5 space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-xs font-mono font-bold uppercase tracking-wider text-amber-400">
                  Field Technician Workflow
                </span>
                <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-amber-500/10 text-amber-400 border border-amber-500/30">
                  Proactive Dispatch
                </span>
              </div>
              <ul className="text-xs text-muted space-y-2">
                <li className="flex items-start gap-2">
                  <CheckCircle2 className="w-3.5 h-3.5 text-amber-400 shrink-0 mt-0.5" />
                  <span>
                    <b>Failure Probability Ranking:</b> Stations are ordered by 30-day failure probability derived from drift, flatlines, and age.
                  </span>
                </li>
                <li className="flex items-start gap-2">
                  <CheckCircle2 className="w-3.5 h-3.5 text-amber-400 shrink-0 mt-0.5" />
                  <span>
                    <b>Primary Driver Attribution:</b> Inspect the failure driver (e.g. <i>Sensor Drift Accumulation</i> vs <i>Telemetry Dropouts</i>) to know what spares to bring.
                  </span>
                </li>
                <li className="flex items-start gap-2">
                  <CheckCircle2 className="w-3.5 h-3.5 text-amber-400 shrink-0 mt-0.5" />
                  <span>
                    <b>Work Order Dispatch:</b> Click <b>Dispatch Ticket</b> to log the official field service order with automated calibration checklists.
                  </span>
                </li>
              </ul>
            </div>

            {/* System Administrator Guide */}
            <div className="bg-panel border border-line rounded-xl p-5 space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-xs font-mono font-bold uppercase tracking-wider text-purple-400">
                  Administrator & Governance
                </span>
                <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-purple-500/10 text-purple-400 border border-purple-500/30">
                  Security & Audit
                </span>
              </div>
              <ul className="text-xs text-muted space-y-2">
                <li className="flex items-start gap-2">
                  <CheckCircle2 className="w-3.5 h-3.5 text-purple-400 shrink-0 mt-0.5" />
                  <span>
                    <b>Role & Permissions Matrix:</b> View and enforce granular access control across 15 system permission nodes.
                  </span>
                </li>
                <li className="flex items-start gap-2">
                  <CheckCircle2 className="w-3.5 h-3.5 text-purple-400 shrink-0 mt-0.5" />
                  <span>
                    <b>Tamper-Evident Audit Trail:</b> Track every administrative change, alert resolution, model retraining run, and login event.
                  </span>
                </li>
                <li className="flex items-start gap-2">
                  <CheckCircle2 className="w-3.5 h-3.5 text-purple-400 shrink-0 mt-0.5" />
                  <span>
                    <b>System Settings:</b> Fine-tune WMO physical thresholds, spatial neighbor count (k=5), and Isolation Forest contamination ratios.
                  </span>
                </li>
              </ul>
            </div>
          </div>
        </div>
      )}

      {/* TAB 2: PRODUCT ARCHITECTURE & QC TIERS */}
      {activeTab === 'spec' && (
        <div className="space-y-6">
          {/* Architecture Summary Card */}
          <div className="bg-panel border border-line rounded-xl p-6 space-y-4">
            <h3 className="text-base font-bold text-ink flex items-center gap-2">
              <Layers className="w-4 h-4 text-accent" />
              Multi-Tier Quality Control Pipeline (Feature F1 - F16)
            </h3>
            <p className="text-xs text-muted leading-relaxed">
              AeroSentinel fuses three distinct diagnostic layers into a deterministic merge classifier,
              achieving <b>100.0% precision</b> and <b>zero false alarms</b> on real meteorological benchmarks.
            </p>

            <div className="space-y-3 pt-2">
              {/* Tier 1 */}
              <div className="p-4 rounded-lg bg-surface border border-line space-y-1.5">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-bold text-ink">Tier 1: Deterministic Physical Rules Engine</span>
                  <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-emerald-500/15 text-emerald-400 border border-emerald-500/30">
                    WMO No. 8 Standard
                  </span>
                </div>
                <p className="text-[11px] text-muted">
                  Sub-millisecond verification of physical bounds (e.g. Temperature [-50°C, +60°C]), circular directional rates-of-change, and zero-variance persistence flatlines (N ≥ 6 consecutive identical readings).
                </p>
              </div>

              {/* Tier 2 */}
              <div className="p-4 rounded-lg bg-surface border border-line space-y-1.5">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-bold text-ink">Tier 2: Deep Sequence & Statistical ML Scorer</span>
                  <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-sky-500/15 text-sky-400 border border-sky-500/30">
                    IsolationForest + PyTorch LSTM
                  </span>
                </div>
                <p className="text-[11px] text-muted">
                  Models multi-variate correlations and sequence reconstruction error to detect subtle calibration drift before gross failure. Includes SHAP TreeExplainer feature attribution for complete interpretability.
                </p>
              </div>

              {/* Tier 3 */}
              <div className="p-4 rounded-lg bg-surface border border-line space-y-1.5">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-bold text-ink">Tier 3: 3D KDTree Geospatial Neighbor Cross-Validation</span>
                  <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-indigo-500/15 text-indigo-400 border border-indigo-500/30">
                    Inverse Distance Weighting (IDW)
                  </span>
                </div>
                <p className="text-[11px] text-muted">
                  Queries the <i>k=5</i> nearest peer stations in Earth-centered Cartesian space. Explains whether an extreme reading is an isolated sensor defect (<code>SPATIAL_MISMATCH</code>) or a regional storm (<code>SPATIAL_VALIDATED_EXTREME</code>), eliminating false alarms.
                </p>
              </div>

              {/* Tier 4 */}
              <div className="p-4 rounded-lg bg-surface border border-line space-y-1.5">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-bold text-ink">Tier 4: Merge Classifier & Self-Healing Imputation</span>
                  <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-amber-500/15 text-amber-400 border border-amber-500/30">
                    Automated Imputation
                  </span>
                </div>
                <p className="text-[11px] text-muted">
                  Outputs unified verdicts with calibrated confidence scores and automatically generates spatial IDW or temporal rolling imputed values so downstream NWP forecast pipelines never experience data gaps.
                </p>
              </div>
            </div>
          </div>

          {/* Benchmark Table Card */}
          <div className="bg-panel border border-line rounded-xl p-6 space-y-4">
            <h3 className="text-sm font-bold text-ink">Empirical Benchmark Verification (National Capital Region Fleet)</h3>
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs font-mono">
                <thead>
                  <tr className="border-b border-line text-muted">
                    <th className="py-2 px-3">Model / Strategy</th>
                    <th className="py-2 px-3">Precision</th>
                    <th className="py-2 px-3">Recall</th>
                    <th className="py-2 px-3">F1-Score</th>
                    <th className="py-2 px-3">False Alarms</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-line/60">
                  <tr>
                    <td className="py-2.5 px-3 text-ink">Tier 1: Rules Alone</td>
                    <td className="py-2.5 px-3">95.2%</td>
                    <td className="py-2.5 px-3">52.4%</td>
                    <td className="py-2.5 px-3">67.7%</td>
                    <td className="py-2.5 px-3 text-amber-400">4 (Extreme Weather)</td>
                  </tr>
                  <tr>
                    <td className="py-2.5 px-3 text-ink">Tier 2: Raw ML (IsoForest)</td>
                    <td className="py-2.5 px-3">29.6%</td>
                    <td className="py-2.5 px-3">85.7%</td>
                    <td className="py-2.5 px-3">43.9%</td>
                    <td className="py-2.5 px-3 text-rose-400">68 (Severe Fatigue)</td>
                  </tr>
                  <tr className="bg-accent/5 font-bold">
                    <td className="py-2.5 px-3 text-accent">AeroSentinel Merged (Tiers 1-4)</td>
                    <td className="py-2.5 px-3 text-emerald-400">100.0%</td>
                    <td className="py-2.5 px-3">66.7%</td>
                    <td className="py-2.5 px-3 text-accent">80.0%</td>
                    <td className="py-2.5 px-3 text-emerald-400">ZERO (0 False Alarms)</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {/* TAB 3: API REFERENCE */}
      {activeTab === 'api' && (
        <div className="space-y-6">
          <div className="bg-panel border border-line rounded-xl p-6 space-y-4">
            <div className="flex items-center justify-between">
              <h3 className="text-base font-bold text-ink flex items-center gap-2">
                <Code2 className="w-4 h-4 text-accent" />
                REST & WebSocket API Endpoints
              </h3>
              <a
                href="http://127.0.0.1:8000/docs"
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-1.5 px-3 py-1 rounded bg-surface hover:bg-hover border border-line text-accent text-xs font-mono transition-colors"
              >
                <span>Interactive Swagger UI</span>
                <ExternalLink className="w-3 h-3" />
              </a>
            </div>

            <p className="text-xs text-muted">
              AeroSentinel exposes production OpenAPI 3.0 endpoints and bidirectional WebSocket streams for seamless
              integration with SCADA, IMD telecommunication hubs, and numerical forecast ingestors:
            </p>

            <div className="space-y-2 pt-2 text-xs font-mono">
              <div className="p-3 rounded bg-surface border border-line flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                <div className="flex items-center gap-2">
                  <span className="px-2 py-0.5 rounded bg-emerald-500/15 text-emerald-400 border border-emerald-500/30 text-[10px] font-bold">
                    POST
                  </span>
                  <span className="text-ink font-semibold">/ingest</span>
                </div>
                <span className="text-muted text-[11px]">High-speed AWS telemetry ingestion</span>
              </div>

              <div className="p-3 rounded bg-surface border border-line flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                <div className="flex items-center gap-2">
                  <span className="px-2 py-0.5 rounded bg-sky-500/15 text-sky-400 border border-sky-500/30 text-[10px] font-bold">
                    GET
                  </span>
                  <span className="text-ink font-semibold">/api/stations</span>
                </div>
                <span className="text-muted text-[11px]">Retrieve registered weather stations & latest readings</span>
              </div>

              <div className="p-3 rounded bg-surface border border-line flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                <div className="flex items-center gap-2">
                  <span className="px-2 py-0.5 rounded bg-sky-500/15 text-sky-400 border border-sky-500/30 text-[10px] font-bold">
                    GET
                  </span>
                  <span className="text-ink font-semibold">/api/alerts</span>
                </div>
                <span className="text-muted text-[11px]">Query operational alerts with severity and status filters</span>
              </div>

              <div className="p-3 rounded bg-surface border border-line flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                <div className="flex items-center gap-2">
                  <span className="px-2 py-0.5 rounded bg-purple-500/15 text-purple-400 border border-purple-500/30 text-[10px] font-bold">
                    WS
                  </span>
                  <span className="text-ink font-semibold">/api/alerts/ws</span>
                </div>
                <span className="text-muted text-[11px]">Live WebSocket broadcast of newly generated alerts</span>
              </div>

              <div className="p-3 rounded bg-surface border border-line flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                <div className="flex items-center gap-2">
                  <span className="px-2 py-0.5 rounded bg-purple-500/15 text-purple-400 border border-purple-500/30 text-[10px] font-bold">
                    WS
                  </span>
                  <span className="text-ink font-semibold">/api/telemetry/ws</span>
                </div>
                <span className="text-muted text-[11px]">Real-time stream of parsed telemetry observations</span>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* TAB 4: EMBEDDED PDF VIEWER */}
      {activeTab === 'viewer' && (
        <div className="space-y-4">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 p-4 rounded-xl bg-panel border border-line">
            <div className="flex items-center gap-2">
              <span className="text-xs font-semibold text-ink">Selected Document:</span>
              <div className="inline-flex rounded-lg bg-surface border border-line p-0.5">
                <button
                  onClick={() => setSelectedPdfToView('manual')}
                  className={`px-3 py-1 rounded-md text-xs font-medium transition-colors ${
                    selectedPdfToView === 'manual'
                      ? 'bg-accent text-white shadow-xs'
                      : 'text-muted hover:text-ink'
                  }`}
                >
                  Operational User Manual
                </button>
                <button
                  onClick={() => setSelectedPdfToView('spec')}
                  className={`px-3 py-1 rounded-md text-xs font-medium transition-colors ${
                    selectedPdfToView === 'spec'
                      ? 'bg-accent text-white shadow-xs'
                      : 'text-muted hover:text-ink'
                  }`}
                >
                  Technical Product Spec
                </button>
              </div>
            </div>

            <div className="flex items-center gap-2">
              <a
                href={pdfFiles[selectedPdfToView].path}
                download={pdfFiles[selectedPdfToView].filename}
                className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-accent text-white text-xs font-medium hover:bg-accent/90 transition-colors shadow-xs"
              >
                <Download className="w-3.5 h-3.5" />
                Download PDF
              </a>
              <a
                href={pdfFiles[selectedPdfToView].path}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-surface hover:bg-hover border border-line text-ink text-xs font-medium transition-colors"
              >
                <ExternalLink className="w-3.5 h-3.5" />
                Open Fullscreen
              </a>
            </div>
          </div>

          {/* Embedded PDF iframe */}
          <div className="w-full h-[750px] bg-slate-900 rounded-xl border border-line overflow-hidden shadow-xl">
            <iframe
              src={pdfFiles[selectedPdfToView].path}
              title={pdfFiles[selectedPdfToView].title}
              className="w-full h-full border-0"
            />
          </div>
        </div>
      )}
    </div>
  );
};
