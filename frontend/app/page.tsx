'use client';

import { useState, useEffect } from 'react';

type UserRole = 'PHYSICIAN' | 'CMO_GOVERNANCE';

interface Scan {
  file_name: string;
  modality: string;
  body_part: string;
  date: string;
  file_path: string;
  sop_instance_uid: string;
}

interface PatientData {
  patient_info: {
    patient_id: string;
    age: string | number;
    gender: string;
  };
  imaging_studies: Array<Scan>;
  clinical_timeline: Array<{
    file_name: string;
    category: string;
    title: string;
    content: string;
    timestamp: string;
  }>;
}

interface Recommendation {
  score: number;
  title: string;
  source: string;
  content: string;
  category: string;
}

interface ChatMessage {
  sender: 'doctor' | 'assistant';
  text: string;
  reasoning_type?: string;
  citations?: Recommendation[];
}

interface VLMAnnotation {
  id: number;
  label: string;
  confidence: number;
  x_pct: number;
  y_pct: number;
  width_pct: number;
  height_pct: number;
}

interface VLMAnalysis {
  status: string;
  modality: string;
  body_part: string;
  ai_confidence: number;
  impression: string;
  findings: string[];
  annotations: VLMAnnotation[];
}

interface AttestationLog {
  id: number;
  physician_name: string;
  decision: string;
  target_type: string;
  findings_summary: string;
  physician_notes: string;
  timestamp: string;
}

interface AuditLogEntry {
  id: number;
  timestamp: string;
  user_name: string;
  user_role: string;
  patient_uid: string;
  action: string;
  details: string;
  ip_address: string;
  compliance_flag: string;
}

interface GovernanceMetrics {
  total_attestations: number;
  accepted: number;
  modified: number;
  rejected: number;
  acceptance_rate_pct: number;
  liability_risk_status: string;
  total_hipaa_logs: number;
  citation_compliance_pct: number;
}

const getAuthHeaders = () => {
  const token = typeof window !== 'undefined' ? localStorage.getItem('drpilot_token') : '';
  return {
    'Content-Type': 'application/json',
    ...(token ? { 'Authorization': `Bearer ${token}` } : {})
  };
};

function FormattedMarkdown({ content }: { content: string }) {
  const lines = content.split('\n');
  return (
    <div className="space-y-1.5 text-xs text-slate-200">
      {lines.map((line, idx) => {
        let trimmed = line.trim();
        if (!trimmed) return <div key={idx} className="h-1" />;

        if (trimmed.startsWith('### ')) {
          return <h3 key={idx} className="text-sm font-bold text-blue-300 mt-2 mb-1">{trimmed.replace('### ', '')}</h3>;
        }
        if (trimmed.startsWith('#### ')) {
          return <h4 key={idx} className="text-xs font-semibold text-slate-300 mt-2 mb-1 uppercase tracking-wider">{trimmed.replace('#### ', '')}</h4>;
        }

        const isBullet = trimmed.startsWith('* ') || trimmed.startsWith('- ');
        const isNumbered = /^\d+\.\s/.test(trimmed);

        if (isBullet || isNumbered) {
          const listText = trimmed.replace(/^(\*|-|\d+\.)\s*/, '');
          return (
            <div key={idx} className="flex gap-2 pl-2 my-0.5">
              <span className="text-blue-400 font-bold">{isNumbered ? trimmed.match(/^\d+\./)?.[0] : '•'}</span>
              <div>{renderInlineFormatting(listText)}</div>
            </div>
          );
        }

        return <p key={idx} className="leading-relaxed">{renderInlineFormatting(trimmed)}</p>;
      })}
    </div>
  );
}

function renderInlineFormatting(text: string) {
  const parts = text.split(/(\*\*.*?\*\*|`.*?`|\*.*?\*)/g);
  return parts.map((part, i) => {
    if (part.startsWith('**') && part.endsWith('**')) {
      return <strong key={i} className="font-semibold text-white">{part.slice(2, -2)}</strong>;
    }
    if (part.startsWith('`') && part.endsWith('`')) {
      return <code key={i} className="bg-slate-900 text-blue-300 px-1 py-0.5 rounded text-[11px] font-mono border border-slate-800">{part.slice(1, -1)}</code>;
    }
    if (part.startsWith('*') && part.endsWith('*')) {
      return <em key={i} className="text-slate-300 italic">{part.slice(1, -1)}</em>;
    }
    return part;
  });
}

export default function Home() {
  // Authentication State
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [usernameInput, setUsernameInput] = useState('');
  const [passwordInput, setPasswordInput] = useState('');
  const [loginError, setLoginError] = useState('');
  
  const [currentUser, setCurrentUser] = useState('');
  const [currentRole, setCurrentRole] = useState<UserRole>('PHYSICIAN');

  // Search & Patient State
  const [patientIdInput, setPatientIdInput] = useState('');
  const [patientData, setPatientData] = useState<PatientData | null>(null);
  const [guidelines, setGuidelines] = useState<Recommendation[]>([]);
  const [selectedScan, setSelectedScan] = useState<Scan | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  // Chat State
  const [chatMessages, setChatMessages] = useState<ChatMessage[]>([]);
  const [chatInput, setChatInput] = useState('');
  const [chatLoading, setChatLoading] = useState(false);

  // VLM State
  const [vlmAnalysis, setVlmAnalysis] = useState<VLMAnalysis | null>(null);
  const [vlmLoading, setVlmLoading] = useState(false);
  const [showOverlays, setShowOverlays] = useState(true);

  // Attestation State
  const [attestations, setAttestations] = useState<AttestationLog[]>([]);
  const [attestationNotes, setAttestationNotes] = useState('');
  const [attestationSubmitting, setAttestationSubmitting] = useState(false);

  // CMO & Governance State
  const [governanceMetrics, setGovernanceMetrics] = useState<GovernanceMetrics | null>(null);
  const [auditTrail, setAuditTrail] = useState<AuditLogEntry[]>([]);
  const [selectedFiles, setSelectedFiles] = useState<FileList | null>(null);
  const [uploadCategory, setUploadCategory] = useState('Cardiology Protocol');
  const [uploading, setUploading] = useState(false);
  const [ingestLogs, setIngestLogs] = useState<any[]>([]);
  const [ingestedDocsList, setIngestedDocsList] = useState<any[]>([]);
  const [docRepoStats, setDocRepoStats] = useState({ total_documents: 0, completed_documents: 0, total_chunks_indexed: 0 });
  const [docSearchQuery, setDocSearchQuery] = useState('');
  const [selectedCategoryFilter, setSelectedCategoryFilter] = useState('ALL');

  const fetchDocumentRepository = async () => {
    try {
      const res = await fetch(`http://localhost:8000/api/v1/governance/documents?t=${Date.now()}`, {
        headers: getAuthHeaders(),
        cache: 'no-store'
      });
      if (res.ok) {
        const data = await res.json();
        setIngestedDocsList(data.documents || []);
        setDocRepoStats(data.stats || { total_documents: 0, completed_documents: 0, total_chunks_indexed: 0 });
      }
    } catch (e) {
      console.error('Failed to fetch document repository', e);
    }
  };

  const handleDeleteDocument = async (docId: number, filename: string) => {
    if (!confirm(`Are you sure you want to delete "${filename}"? This will remove its vectors from Qdrant.`)) {
      return;
    }

    try {
      const res = await fetch(`http://localhost:8000/api/v1/governance/documents/${docId}`, {
        method: 'DELETE',
        headers: getAuthHeaders()
      });

      if (res.ok) {
        alert(`Document "${filename}" deleted.`);
        fetchDocumentRepository();
      } else {
        alert('Failed to delete document');
      }
    } catch (e) {
      console.error('Delete document error', e);
    }
  };

  const fetchIngestLogs = async () => {
    try {
      const res = await fetch('http://localhost:8000/api/v1/governance/ingest/status', {
        headers: getAuthHeaders()
      });
      if (res.ok) {
        const data = await res.json();
        setIngestLogs(data);
      }
    } catch (e) {
      console.error('Failed to fetch ingest status', e);
    }
  };

  const handleBulkUploadSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedFiles || selectedFiles.length === 0) return;

    setUploading(true);
    const formData = new FormData();
    formData.append('category', uploadCategory);

    Array.from(selectedFiles).forEach((file) => {
      formData.append('files', file);
    });

    try {
      const res = await fetch('http://localhost:8000/api/v1/governance/ingest/mass-upload', {
        method: 'POST',
        headers: {
          'Authorization': getAuthHeaders().Authorization || ''
        },
        body: formData
      });

      if (res.ok) {
        alert('Batch successfully queued for processing!');
        setSelectedFiles(null);
        fetchIngestLogs();
      }
    } catch (err) {
      alert('Failed to upload batch');
    } finally {
      setUploading(false);
    }
  };
  // NON-BLOCKING SIGN OUT
  const handleLogout = () => {
    if (typeof window !== 'undefined') {
      localStorage.removeItem('drpilot_token');
    }
    setIsAuthenticated(false);
    setCurrentUser('');
    setCurrentRole('PHYSICIAN');
    setUsernameInput('');
    setPasswordInput('');
    setLoginError('');
    setPatientData(null);
    setChatMessages([]);
    setSelectedScan(null);
    setGovernanceMetrics(null);
    setAuditTrail([]);

    // Background log notification to backend
    fetch('http://localhost:8000/api/v1/auth/logout', {
      method: 'POST',
      headers: getAuthHeaders()
    }).catch((e) => console.log('Logout notification sent to backend:', e));
  };

  const fetchGovernanceData = async () => {
    console.log('[Governance] Fetching latest metrics...');
    try {
      const resM = await fetch(`http://localhost:8000/api/v1/governance/metrics?t=${Date.now()}`, {
        headers: getAuthHeaders(),
        cache: 'no-store'
      });

      if (resM.ok) {
        const dataM = await resM.json();
        console.log('[Governance] Metrics Received:', dataM);
        setGovernanceMetrics(dataM.summary || dataM);
      } else {
        console.error('[Governance] Metrics endpoint returned:', resM.status);
      }

      const resA = await fetch(`http://localhost:8000/api/v1/governance/audit-logs?t=${Date.now()}`, {
        headers: getAuthHeaders(),
        cache: 'no-store'
      });

      if (resA.ok) {
        const dataA = await resA.json();
        setAuditTrail(dataA);
      }

      // Automatically sync mass ingestion queue & guideline repository
      await fetchIngestLogs();
      await fetchDocumentRepository();

    } catch (e) {
      console.error('[Governance] Network error:', e);
    }
  };

  useEffect(() => {
    if (isAuthenticated) {
      fetchGovernanceData();
    }
  }, [isAuthenticated, currentRole]);

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoginError('');

    try {
      const res = await fetch('http://localhost:8000/api/v1/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          username: usernameInput,
          password: passwordInput
        })
      });

      if (!res.ok) {
        const errData = await res.json();
        throw new Error(errData.detail || 'Invalid username or password');
      }

      const data = await res.json();

      setIsAuthenticated(true);
      setCurrentUser(data.full_name);
      setCurrentRole(data.role as UserRole);

      if (typeof window !== 'undefined') {
        localStorage.setItem('drpilot_token', data.access_token);
      }

      fetchGovernanceData();
    } catch (err: any) {
      setLoginError(err.message || 'Invalid username or password');
    }
  };

  const fetchAttestations = async (uid: string) => {
    try {
      const res = await fetch(`http://localhost:8000/api/v1/patients/${uid}/attestations`, {
        headers: getAuthHeaders()
      });
      if (res.ok) {
        const data = await res.json();
        setAttestations(data);
      }
    } catch (e) {
      console.error('Failed to fetch attestations', e);
    }
  };

  const handleSearch = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!patientIdInput.trim()) return;

    setLoading(true);
    setError('');
    setSelectedScan(null);
    setGuidelines([]);
    setChatMessages([]);
    setAttestations([]);

    try {
      const res = await fetch(`http://localhost:8000/api/v1/patients/${patientIdInput.trim()}/dashboard`, {
        headers: getAuthHeaders()
      });

      if (!res.ok) {
        const errorData = await res.json();
        throw new Error(errorData.detail || 'Patient record not found');
      }
      const data = await res.json();
      setPatientData(data);

      const ragRes = await fetch(`http://localhost:8000/api/v1/patients/${patientIdInput.trim()}/guideline-recommendations`, {
        headers: getAuthHeaders()
      });
      if (ragRes.ok) {
        const ragData = await ragRes.json();
        setGuidelines(ragData.recommendations || []);
      }

      await fetchAttestations(patientIdInput.trim());

      setChatMessages([
        {
          sender: 'assistant',
          text: `Chart loaded for **Patient ${patientIdInput.trim()}**.\n\nAsk me a clinical question, query treatment options, or run a **"What-If" simulation**.`
        }
      ]);
    } catch (err: any) {
      setError(err.message || 'Failed to retrieve patient chart');
      setPatientData(null);
    } finally {
      setLoading(false);
    }
  };

  const handleSendMessage = async (messageText: string) => {
    if (!messageText.trim() || !patientData) return;

    const userMsg: ChatMessage = { sender: 'doctor', text: messageText };
    setChatMessages((prev) => [...prev, userMsg]);
    setChatInput('');
    setChatLoading(true);

    try {
      const res = await fetch(`http://localhost:8000/api/v1/patients/${patientData.patient_info.patient_id}/chat`, {
        method: 'POST',
        headers: getAuthHeaders(),
        body: JSON.stringify({ message: messageText, history: [] })
      });

      if (!res.ok) throw new Error('Assistant failed to respond');

      const data = await res.json();
      const botMsg: ChatMessage = {
        sender: 'assistant',
        text: data.response,
        reasoning_type: data.reasoning_type,
        citations: data.cited_guidelines
      };

      setChatMessages((prev) => [...prev, botMsg]);
    } catch (err: any) {
      setChatMessages((prev) => [
        ...prev,
        { sender: 'assistant', text: 'Error processing query. Please ensure backend services are active.' }
      ]);
    } finally {
      setChatLoading(false);
    }
  };

  const handleRunVLMAnalysis = async () => {
    if (!selectedScan || !patientData) return;
    setVlmLoading(true);
    setVlmAnalysis(null);

    try {
      const res = await fetch(
        `http://localhost:8000/api/v1/patients/${patientData.patient_info.patient_id}/scans/${encodeURIComponent(selectedScan.sop_instance_uid)}/analyze`,
        { headers: getAuthHeaders() }
      );
      if (!res.ok) throw new Error('Vision analysis failed');
      const data = await res.json();
      setVlmAnalysis(data);
    } catch (err) {
      console.error(err);
    } finally {
      setVlmLoading(false);
    }
  };

  const handleSignOff = async (decision: 'ACCEPTED' | 'MODIFIED' | 'REJECTED') => {
    if (!patientData || !vlmAnalysis) return;
    setAttestationSubmitting(true);

    try {
      const res = await fetch(`http://localhost:8000/api/v1/patients/${patientData.patient_info.patient_id}/attest`, {
        method: 'POST',
        headers: getAuthHeaders(),
        body: JSON.stringify({
          decision,
          target_type: 'VLM_SCAN_FINDING',
          findings_summary: vlmAnalysis.impression,
          physician_notes: attestationNotes
        })
      });

      if (res.ok) {
        setAttestationNotes('');
        await fetchAttestations(patientData.patient_info.patient_id);
        await fetchGovernanceData();
        alert(`Attestation recorded: ${decision}`);
      }
    } catch (e) {
      console.error(e);
    } finally {
      setAttestationSubmitting(false);
    }
  };

  /* STANDARD LOGIN VIEW (UNAUTHENTICATED) */
  if (!isAuthenticated) {
    return (
      <div className="min-h-screen bg-slate-950 flex items-center justify-center p-6 font-sans">
        <div className="w-full max-w-md bg-slate-900 border border-slate-800 rounded-2xl p-8 shadow-2xl space-y-6">
          <div className="text-center">
            <h1 className="text-2xl font-bold text-blue-400 tracking-tight">DrPilot Medical Portal</h1>
            <p className="text-xs text-slate-400 mt-1">Enterprise Authentication & Access Control</p>
          </div>

          {loginError && (
            <div className="p-3 bg-red-950/70 border border-red-500/50 rounded-lg text-red-200 text-xs text-center font-medium">
              {loginError}
            </div>
          )}

          <form onSubmit={handleLogin} className="space-y-4">
            <div>
              <label className="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-1.5">
                Username
              </label>
              <input
                type="text"
                placeholder="Enter username..."
                value={usernameInput}
                onChange={(e) => setUsernameInput(e.target.value)}
                className="w-full px-4 py-2.5 bg-slate-950 border border-slate-700 rounded-xl text-sm text-white focus:outline-none focus:ring-2 focus:ring-blue-500 placeholder-slate-600"
                required
              />
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-1.5">
                Password
              </label>
              <input
                type="password"
                placeholder="••••••••"
                value={passwordInput}
                onChange={(e) => setPasswordInput(e.target.value)}
                className="w-full px-4 py-2.5 bg-slate-950 border border-slate-700 rounded-lg text-sm text-white focus:outline-none focus:ring-2 focus:ring-blue-500 placeholder-slate-600"
                required
              />
            </div>

            <button
              type="submit"
              className="w-full py-2.5 bg-blue-600 hover:bg-blue-500 font-semibold text-white rounded-xl text-sm transition shadow-md mt-2"
            >
              Sign In to Workspace
            </button>
          </form>

          <div className="pt-4 border-t border-slate-800 text-[11px] text-slate-500 text-center space-y-1">
            <p>Authorized personnel only. All access events are logged under HIPAA standard protocols.</p>
            <p className="text-slate-600">Test Physician: <code className="text-slate-400">dr.vance / doctor123</code></p>
            <p className="text-slate-600">Test CMO: <code className="text-slate-400">cmo.jenkins / cmo123</code></p>
          </div>
        </div>
      </div>
    );
  }

  const isCMO = currentRole?.toUpperCase().includes('CMO');

  /* AUTHENTICATED WORKSPACE */
  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 p-6 font-sans">
      {/* Navigation Header */}
      <header className="max-w-7xl mx-auto flex flex-col md:flex-row items-center justify-between gap-4 pb-6 border-b border-slate-800">
        <div>
          <h1 className="text-2xl font-bold text-blue-400 tracking-tight">DrPilot Enterprise Workspace</h1>
          <p className="text-xs text-slate-400 mt-0.5">Real-Time Multimodal Decision Support & Clinical Governance</p>
        </div>

        {/* User Profile Info & Instant Logout */}
        <div className="flex items-center gap-4 bg-slate-900 border border-slate-800 px-4 py-2 rounded-xl shadow-inner">
          <div className="text-right">
            <p className="text-xs font-bold text-slate-200">{currentUser}</p>
            <p className="text-[10px] text-slate-500 uppercase tracking-wider font-semibold">Role: {currentRole}</p>
          </div>
          <button
            type="button"
            onClick={handleLogout}
            className="px-3 py-1.5 bg-slate-800 hover:bg-red-900/60 hover:text-red-200 text-slate-400 rounded-lg text-xs font-medium border border-slate-700 transition"
          >
            Sign Out 🚪
          </button>
        </div>
      </header>

      {/* VIEW 1: CMO & GOVERNANCE COMPLIANCE COMMAND CENTER */}
      {isCMO && (
        <main className="max-w-7xl mx-auto mt-6 space-y-6">
          <div className="p-5 bg-slate-900 border border-slate-800 rounded-xl flex justify-between items-center shadow-lg">
            <div>
              <h2 className="text-lg font-bold text-emerald-400 flex items-center gap-2">
                <span>🛡️</span> Chief Medical Officer & Safety Command Center
              </h2>
              <p className="text-xs text-slate-400 mt-0.5">
                Monitoring clinical liability, diagnostic AI acceptance ratios, transparent citation integrity, and HIPAA/GDPR compliance.
              </p>
            </div>
            <button
              type="button"
              onClick={fetchGovernanceData}
              className="px-3 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-semibold rounded-lg border border-slate-700 transition"
            >
              🔄 Refresh Logs
            </button>
          </div>

          {/* Metrics Cards Grid */}
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            <div className="p-4 bg-slate-900 border border-slate-800 rounded-xl">
              <span className="text-[10px] text-slate-500 font-semibold uppercase tracking-wider">Liability Status</span>
              <p className="text-xl font-bold text-emerald-400 mt-1">{governanceMetrics?.liability_risk_status || 'LOW RISK'}</p>
              <p className="text-[10px] text-slate-400 mt-1">{governanceMetrics?.rejected ?? 0} unreviewed AI overrides</p>
            </div>

            <div className="p-4 bg-slate-900 border border-slate-800 rounded-xl">
              <span className="text-[10px] text-slate-500 font-semibold uppercase tracking-wider">AI Acceptance Rate</span>
              <p className="text-xl font-bold text-blue-400 mt-1">
                {governanceMetrics?.acceptance_rate_pct !== undefined ? `${governanceMetrics.acceptance_rate_pct}%` : '--'}
              </p>
              <p className="text-[10px] text-slate-400 mt-1">
                {governanceMetrics?.accepted ?? 0} accepted / {governanceMetrics?.total_attestations ?? 0} total
              </p>
            </div>

            <div className="p-4 bg-slate-900 border border-slate-800 rounded-xl">
              <span className="text-[10px] text-slate-500 font-semibold uppercase tracking-wider">Citation Integrity</span>
              <p className="text-xl font-bold text-purple-400 mt-1">
                {governanceMetrics?.citation_compliance_pct !== undefined ? `${governanceMetrics.citation_compliance_pct}%` : '100%'}
              </p>
              <p className="text-[10px] text-slate-400 mt-1">Verified against Qdrant RAG</p>
            </div>

            <div className="p-4 bg-slate-900 border border-slate-800 rounded-xl">
              <span className="text-[10px] text-slate-500 font-semibold uppercase tracking-wider">HIPAA Audit Volume</span>
              <p className="text-xl font-bold text-white mt-1">{governanceMetrics?.total_hipaa_logs ?? 0} Events</p>
              <p className="text-[10px] text-slate-400 mt-1">Full audit trail active</p>
            </div>
          </div>

          {/* Automated Bulk RAG Guideline Ingestion Card */}
          <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 shadow-lg space-y-4">
            <h3 className="text-xs uppercase font-bold text-blue-400 tracking-wider flex items-center justify-between">
              <span className="flex items-center gap-2">
                <span>📚</span> Automated Mass Guideline Ingestion (RAG)
              </span>
              <button
                type="button"
                onClick={fetchIngestLogs}
                className="text-[10px] text-slate-400 hover:text-white underline font-normal transition"
              >
                Refresh Queue Status
              </button>
            </h3>

            <form onSubmit={handleBulkUploadSubmit} className="grid grid-cols-1 md:grid-cols-12 gap-3 items-end">
              <div className="md:col-span-4">
                <label className="block text-[11px] text-slate-400 mb-1">Guideline Specialty Category</label>
                <input
                  type="text"
                  value={uploadCategory}
                  onChange={(e) => setUploadCategory(e.target.value)}
                  placeholder="e.g. Cardiology Protocol"
                  className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-lg text-xs text-white focus:outline-none focus:ring-1 focus:ring-blue-500 transition"
                  required
                />
              </div>

              <div className="md:col-span-5">
                <label className="block text-[11px] text-slate-400 mb-1">Select Multiple PDF Documents</label>
                <input
                  type="file"
                  multiple
                  accept=".pdf"
                  onChange={(e) => setSelectedFiles(e.target.files)}
                  className="w-full text-xs text-slate-400 file:mr-3 file:py-1.5 file:px-3 file:rounded-lg file:border-0 file:text-xs file:font-semibold file:bg-blue-600 file:text-white hover:file:bg-blue-500 cursor-pointer transition"
                  required
                />
              </div>

              <div className="md:col-span-3">
                <button
                  type="submit"
                  disabled={uploading}
                  className="w-full py-2 bg-emerald-600 hover:bg-emerald-500 disabled:bg-slate-800 text-white font-bold text-xs rounded-lg transition shadow-md flex items-center justify-center gap-1.5"
                >
                  {uploading ? 'Queueing Batch...' : 'Start Mass Ingestion 🚀'}
                </button>
              </div>
            </form>

            {/* Ingestion Queue Status Logs */}
            {ingestLogs && ingestLogs.length > 0 && (
              <div className="mt-3 border-t border-slate-800/80 pt-3">
                <span className="text-[10px] uppercase text-slate-500 font-semibold block mb-2">
                  Async Ingestion Queue Status ({ingestLogs.length})
                </span>
                <div className="max-h-44 overflow-y-auto space-y-1.5 font-mono text-[11px] pr-1">
                  {ingestLogs.map((log: any) => (
                    <div
                      key={log.id}
                      className="p-2.5 bg-slate-950 rounded-lg border border-slate-800/60 flex items-center justify-between gap-3"
                    >
                      <div className="flex items-center gap-2 truncate">
                        <span className="text-slate-200 font-sans font-medium truncate max-w-[220px]">
                          {log.filename}
                        </span>
                        <span className="text-[10px] text-slate-500 font-sans px-2 py-0.5 bg-slate-900 border border-slate-800 rounded">
                          {log.category}
                        </span>
                      </div>

                      <div className="flex items-center gap-4">
                        <span className="text-slate-400 text-[10px]">{log.chunks_count ?? 0} chunks</span>
                        <span
                          className={`px-2 py-0.5 rounded font-bold text-[9px] ${
                            log.status === 'COMPLETED'
                              ? 'bg-emerald-950 text-emerald-400 border border-emerald-800'
                              : log.status === 'PROCESSING'
                              ? 'bg-blue-950 text-blue-400 border border-blue-800 animate-pulse'
                              : log.status === 'PENDING'
                              ? 'bg-amber-950 text-amber-400 border border-amber-800'
                              : 'bg-red-950 text-red-400 border border-red-800'
                          }`}
                        >
                          {log.status}
                        </span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>

          {/* Clinical Guideline Library & RAG Vector Repository */}
          <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 shadow-lg space-y-4">
            
            {/* Header & Stats Banner */}
            <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-3 border-b border-slate-800">
              <div>
                <h3 className="text-sm font-bold text-slate-100 flex items-center gap-2">
                  <span>📂</span> Clinical Guideline Repository & Qdrant Index
                </h3>
                <p className="text-xs text-slate-400 mt-0.5">
                  Manage active medical protocols feeding into RAG vector search.
                </p>
              </div>

              {/* Quick Summary Badges */}
              <div className="flex items-center gap-2 font-mono text-[11px]">
                <span className="px-2.5 py-1 bg-slate-950 border border-slate-800 rounded-lg text-slate-300">
                  📄 Total Docs: <strong className="text-blue-400">{docRepoStats.total_documents}</strong>
                </span>
                <span className="px-2.5 py-1 bg-slate-950 border border-slate-800 rounded-lg text-slate-300">
                  🧩 Chunks Indexed: <strong className="text-emerald-400">{docRepoStats.total_chunks_indexed}</strong>
                </span>
                <button
                  type="button"
                  onClick={fetchDocumentRepository}
                  className="px-2.5 py-1 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-lg transition"
                  title="Refresh Repository"
                >
                  🔄
                </button>
              </div>
            </div>

            {/* Filter & Search Bar */}
            <div className="flex flex-col sm:flex-row gap-3 items-center justify-between">
              <input
                type="text"
                placeholder="Search documents by title or category..."
                value={docSearchQuery}
                onChange={(e) => setDocSearchQuery(e.target.value)}
                className="w-full sm:w-80 px-3 py-1.5 bg-slate-950 border border-slate-800 rounded-lg text-xs text-white focus:outline-none focus:ring-1 focus:ring-blue-500 placeholder-slate-500"
              />

              <div className="flex items-center gap-2 w-full sm:w-auto">
                <span className="text-xs text-slate-400 whitespace-nowrap">Filter Specialty:</span>
                <select
                  value={selectedCategoryFilter}
                  onChange={(e) => setSelectedCategoryFilter(e.target.value)}
                  className="px-3 py-1.5 bg-slate-950 border border-slate-800 rounded-lg text-xs text-slate-200 focus:outline-none"
                >
                  <option value="ALL">All Categories</option>
                  {Array.from(new Set(ingestedDocsList.map((d) => d.category))).map((cat) => (
                    <option key={cat} value={cat}>
                      {cat}
                    </option>
                  ))}
                </select>
              </div>
            </div>

            {/* Document Repository Table */}
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs text-slate-300">
                <thead className="bg-slate-950 text-slate-400 uppercase text-[10px] border-b border-slate-800">
                  <tr>
                    <th className="p-3">Document Title</th>
                    <th className="p-3">Category</th>
                    <th className="p-3">Size</th>
                    <th className="p-3">RAG Chunks</th>
                    <th className="p-3">Status</th>
                    <th className="p-3">Uploaded</th>
                    <th className="p-3 text-right">Action</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/60 bg-slate-950/40 font-mono text-[11px]">
                  {ingestedDocsList
                    .filter((doc) => {
                      const matchesSearch =
                        doc.filename.toLowerCase().includes(docSearchQuery.toLowerCase()) ||
                        doc.category.toLowerCase().includes(docSearchQuery.toLowerCase());
                      const matchesCategory =
                        selectedCategoryFilter === 'ALL' || doc.category === selectedCategoryFilter;
                      return matchesSearch && matchesCategory;
                    })
                    .length === 0 ? (
                    <tr>
                      <td colSpan={7} className="p-6 text-center text-slate-500 italic font-sans">
                        No guideline documents match your query or none have been ingested yet.
                      </td>
                    </tr>
                  ) : (
                    ingestedDocsList
                      .filter((doc) => {
                        const matchesSearch =
                          doc.filename.toLowerCase().includes(docSearchQuery.toLowerCase()) ||
                          doc.category.toLowerCase().includes(docSearchQuery.toLowerCase());
                        const matchesCategory =
                          selectedCategoryFilter === 'ALL' || doc.category === selectedCategoryFilter;
                        return matchesSearch && matchesCategory;
                      })
                      .map((doc) => (
                        <tr key={doc.id} className="hover:bg-slate-900/50">
                          <td className="p-3 font-sans font-semibold text-slate-100 flex items-center gap-2">
                            <span>📄</span>
                            <span className="truncate max-w-[220px]" title={doc.filename}>
                              {doc.filename}
                            </span>
                          </td>
                          <td className="p-3">
                            <span className="px-2 py-0.5 rounded bg-slate-900 text-blue-300 text-[10px] border border-slate-800 font-sans">
                              {doc.category}
                            </span>
                          </td>
                          <td className="p-3 text-slate-400">
                            {(doc.file_size_bytes / 1024).toFixed(1)} KB
                          </td>
                          <td className="p-3 text-emerald-400 font-bold">
                            {doc.chunks_count} chunks
                          </td>
                          <td className="p-3">
                            <span
                              className={`px-2 py-0.5 rounded font-bold text-[9px] ${
                                doc.status === 'COMPLETED'
                                  ? 'bg-emerald-950 text-emerald-400 border border-emerald-800'
                                  : doc.status === 'PROCESSING'
                                  ? 'bg-blue-950 text-blue-400 border border-blue-800 animate-pulse'
                                  : doc.status === 'PENDING'
                                  ? 'bg-amber-950 text-amber-400 border border-amber-800'
                                  : 'bg-red-950 text-red-400 border border-red-800'
                              }`}
                            >
                              {doc.status}
                            </span>
                          </td>
                          <td className="p-3 text-slate-400 text-[10px]">{doc.created_at}</td>
                          <td className="p-3 text-right">
                            <button
                              type="button"
                              onClick={() => handleDeleteDocument(doc.id, doc.filename)}
                              className="px-2 py-1 bg-slate-900 hover:bg-red-950 text-slate-400 hover:text-red-300 border border-slate-800 hover:border-red-800 rounded transition font-sans text-[10px]"
                              title="Delete document and purge vectors"
                            >
                              🗑️ Delete
                            </button>
                          </td>
                        </tr>
                      ))
                  )}
                </tbody>
              </table>
            </div>
          </div>

          {/* Audit Trail Table */}
          <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 shadow-lg">
            <h3 className="text-xs uppercase font-bold text-slate-300 tracking-wider mb-4 flex items-center justify-between">
              <span>📋 Institutional HIPAA & GDPR Access Audit Trail</span>
              <span className="text-[10px] font-normal text-emerald-400 bg-emerald-950/60 px-2.5 py-0.5 rounded border border-emerald-800">
                Encrypted & Non-Repudiable
              </span>
            </h3>

            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs text-slate-300">
                <thead className="bg-slate-950 text-slate-400 uppercase text-[10px] border-b border-slate-800">
                  <tr>
                    <th className="p-3">Timestamp</th>
                    <th className="p-3">User / Identity</th>
                    <th className="p-3">Role</th>
                    <th className="p-3">Patient UID</th>
                    <th className="p-3">Action Recorded</th>
                    <th className="p-3">Compliance Standard</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/60 bg-slate-950/40 font-mono text-[11px]">
                  {auditTrail.length === 0 ? (
                    <tr>
                      <td colSpan={6} className="p-4 text-center text-slate-500 italic">No audit trail records indexed yet.</td>
                    </tr>
                  ) : (
                    auditTrail.map((log) => (
                      <tr key={log.id} className="hover:bg-slate-900/50">
                        <td className="p-3 text-slate-400">{log.timestamp}</td>
                        <td className="p-3 font-semibold text-slate-200">{log.user_name}</td>
                        <td className="p-3">
                          <span className="px-2 py-0.5 rounded bg-slate-800 text-blue-300 text-[10px]">
                            {log.user_role}
                          </span>
                        </td>
                        <td className="p-3 text-blue-400 font-bold">{log.patient_uid}</td>
                        <td className="p-3 text-slate-300">{log.action}</td>
                        <td className="p-3">
                          <span className="px-2 py-0.5 bg-emerald-950 text-emerald-400 border border-emerald-800 rounded text-[10px]">
                            {log.compliance_flag}
                          </span>
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </main>
      )}

      {/* VIEW 2: PHYSICIAN & SURGEON CLINICAL WORKSPACE */}
      {!isCMO && (
        <main className="max-w-7xl mx-auto mt-6">
          <div className="flex justify-between items-center mb-6 bg-slate-900 border border-slate-800 p-4 rounded-xl">
            <div>
              <h2 className="text-base font-bold text-white">Attending Physician Chart Lookup</h2>
              <p className="text-xs text-slate-400">Search patient records from VNA storage to run multimodal AI queries.</p>
            </div>
            <form onSubmit={handleSearch} className="flex w-full md:w-96 gap-2">
              <input
                type="text"
                placeholder="Enter Patient ID (e.g. PAT-1001)..."
                value={patientIdInput}
                onChange={(e) => setPatientIdInput(e.target.value)}
                className="flex-1 px-4 py-2 bg-slate-950 border border-slate-700 rounded-lg text-white text-xs focus:outline-none focus:ring-2 focus:ring-blue-500 placeholder-slate-500"
              />
              <button
                type="submit"
                disabled={loading}
                className="px-5 py-2 bg-blue-600 hover:bg-blue-500 disabled:bg-blue-800 rounded-lg text-xs font-semibold transition text-white"
              >
                {loading ? 'Searching...' : 'Search'}
              </button>
            </form>
          </div>

          {error && (
            <div className="p-4 mb-6 bg-red-950/60 border border-red-500/50 rounded-lg text-red-200 text-xs">
              {error}
            </div>
          )}

          {!patientData && !loading && (
            <div className="text-center py-24 text-slate-500 border-2 border-dashed border-slate-800 rounded-xl">
              <svg className="w-16 h-16 mx-auto mb-4 opacity-40" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.5" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
              </svg>
              <p className="text-lg font-medium text-slate-400">Search for a Patient ID to pull up VNA scans, clinical notes, and interactive AI assistant.</p>
              <p className="text-sm text-slate-600 mt-1">Try typing <code className="bg-slate-900 px-2 py-0.5 rounded text-blue-400">PAT-1001</code></p>
            </div>
          )}

          {patientData && (
            <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
              {/* Left Column: Chart & Timeline (7 cols) */}
              <div className="lg:col-span-7 space-y-6">
                <div className="bg-slate-900 border border-slate-800 rounded-xl p-5">
                  <h2 className="text-xs uppercase tracking-wider text-slate-400 mb-3 font-semibold">Patient Demographics</h2>
                  <div className="flex justify-between items-center">
                    <div>
                      <h3 className="text-xl font-bold text-white">{patientData.patient_info.patient_id}</h3>
                      <p className="text-sm text-slate-400 mt-1">
                        Age: <span className="text-slate-200 font-medium">{patientData.patient_info.age}</span> • Gender: <span className="text-slate-200 font-medium">{patientData.patient_info.gender}</span>
                      </p>
                    </div>
                    <span className="px-3 py-1 bg-emerald-500/10 text-emerald-400 text-xs font-semibold rounded-full border border-emerald-500/20">
                      VNA Synced
                    </span>
                  </div>
                </div>

                {/* PACS Scans */}
                <div className="bg-slate-900 border border-slate-800 rounded-xl p-5">
                  <h2 className="text-xs uppercase tracking-wider text-slate-400 mb-3 font-semibold">
                    PACS DICOM Scans ({patientData.imaging_studies.length})
                  </h2>
                  {patientData.imaging_studies.length === 0 ? (
                    <p className="text-sm text-slate-500 italic">No DICOM files found in /dicom subfolder.</p>
                  ) : (
                    <div className="space-y-3">
                      {patientData.imaging_studies.map((scan, idx) => (
                        <div key={idx} className="p-3 bg-slate-950 border border-slate-800 rounded-lg flex items-center justify-between">
                          <div>
                            <p className="font-semibold text-blue-300 text-sm">{scan.modality} - {scan.body_part}</p>
                            <p className="text-xs text-slate-500 mt-0.5">{scan.date}</p>
                          </div>
                          <button
                            onClick={() => {
                              setSelectedScan(scan);
                              setVlmAnalysis(null);
                            }}
                            className="px-3 py-1 text-xs font-medium bg-blue-600 hover:bg-blue-500 text-white rounded transition shadow-sm"
                          >
                            Launch Scan
                          </button>
                        </div>
                      ))}
                    </div>
                  )}
                </div>

                {/* Attestation History */}
                <div className="bg-slate-900 border border-emerald-900/50 rounded-xl p-5 shadow-lg">
                  <div className="flex justify-between items-center mb-3">
                    <h2 className="text-xs uppercase tracking-wider text-emerald-400 font-semibold flex items-center gap-1.5">
                      <span>🛡️</span> Physician Sign-Off & Audit Log ({attestations.length})
                    </h2>
                    <span className="text-[10px] text-slate-500">PostgreSQL Verified</span>
                  </div>

                  {attestations.length === 0 ? (
                    <p className="text-xs text-slate-500 italic">No attestations recorded for this patient yet.</p>
                  ) : (
                    <div className="space-y-2.5 max-h-56 overflow-y-auto pr-1">
                      {attestations.map((a) => (
                        <div key={a.id} className="p-3 bg-slate-950 border border-slate-800 rounded-lg text-xs">
                          <div className="flex justify-between items-center mb-1">
                            <span className={`px-2 py-0.5 rounded font-bold text-[10px] ${
                              a.decision === 'ACCEPTED' ? 'bg-emerald-900/60 text-emerald-300 border border-emerald-700/50' :
                              a.decision === 'MODIFIED' ? 'bg-amber-900/60 text-amber-300 border border-amber-700/50' :
                              'bg-red-900/60 text-red-300 border border-red-700/50'
                            }`}>
                              {a.decision}
                            </span>
                            <span className="text-[10px] text-slate-500">{a.timestamp}</span>
                          </div>
                          <p className="font-semibold text-slate-200 mt-1">{a.physician_name}</p>
                          <p className="text-slate-400 text-[11px] mt-0.5">{a.findings_summary}</p>
                          {a.physician_notes && (
                            <p className="text-slate-300 text-[11px] mt-1 bg-slate-900 p-1.5 rounded italic">
                              Notes: "{a.physician_notes}"
                            </p>
                          )}
                        </div>
                      ))}
                    </div>
                  )}
                </div>

                {/* RAG Guidelines */}
                <div className="bg-slate-900 border border-blue-900/50 rounded-xl p-5 shadow-lg">
                  <h2 className="text-xs uppercase tracking-wider text-blue-400 font-semibold mb-3">
                    Clinical Evidence & RAG Guideline Match
                  </h2>
                  {guidelines.length === 0 ? (
                    <p className="text-sm text-slate-500 italic">No guideline matches retrieved.</p>
                  ) : (
                    <div className="space-y-3">
                      {guidelines.map((rec, idx) => (
                        <div key={idx} className="p-3 bg-slate-950 border border-slate-800 rounded-lg">
                          <div className="flex justify-between items-start gap-2 mb-1">
                            <h4 className="font-semibold text-blue-200 text-sm">{rec.title}</h4>
                            <span className="px-2 py-0.5 text-[10px] font-bold bg-blue-900/60 text-blue-300 rounded border border-blue-700/50">
                              {rec.score}% Match
                            </span>
                          </div>
                          <p className="text-xs text-slate-400 mb-1">Source: {rec.source}</p>
                          <p className="text-xs text-slate-300 bg-slate-900/70 p-2 rounded border border-slate-800">{rec.content}</p>
                        </div>
                      ))}
                    </div>
                  )}
                </div>

                {/* Timeline */}
                <div className="bg-slate-900 border border-slate-800 rounded-xl p-5">
                  <h2 className="text-xs uppercase tracking-wider text-slate-400 mb-4 font-semibold">
                    Aggregated Clinical Timeline ({patientData.clinical_timeline.length})
                  </h2>
                  <div className="space-y-4">
                    {patientData.clinical_timeline.map((note, idx) => (
                      <div key={idx} className="p-4 bg-slate-950 border border-slate-800 rounded-lg">
                        <div className="flex justify-between items-center mb-2">
                          <span className="px-2.5 py-0.5 text-xs font-semibold bg-blue-900/40 text-blue-300 border border-blue-800/60 rounded">
                            {note.category}
                          </span>
                          <span className="text-xs text-slate-500">{note.timestamp}</span>
                        </div>
                        <h4 className="font-medium text-slate-200 text-base">{note.title}</h4>
                        <p className="text-sm text-slate-300 mt-2 leading-relaxed whitespace-pre-line">{note.content}</p>
                      </div>
                    ))}
                  </div>
                </div>
              </div>

              {/* Right Column: AI Chat Assistant (5 cols) */}
              <div className="lg:col-span-5 bg-slate-900 border border-slate-800 rounded-xl flex flex-col h-[820px] overflow-hidden sticky top-6 shadow-xl">
                <div className="p-4 border-b border-slate-800 bg-slate-950 flex justify-between items-center">
                  <div>
                    <h2 className="font-bold text-slate-100 flex items-center gap-2 text-sm">
                      <span className="w-2.5 h-2.5 rounded-full bg-emerald-500 animate-pulse"></span>
                      Interactive AI Assistant
                    </h2>
                    <p className="text-xs text-slate-400 mt-0.5">Clinical reasoning & "What-If" scenario engine</p>
                  </div>
                </div>

                <div className="flex-1 p-4 overflow-y-auto space-y-4 bg-slate-950/50">
                  {chatMessages.map((msg, idx) => (
                    <div key={idx} className={`flex flex-col ${msg.sender === 'doctor' ? 'items-end' : 'items-start'}`}>
                      <div
                        className={`max-w-[92%] p-4 rounded-xl text-xs ${
                          msg.sender === 'doctor'
                            ? 'bg-blue-600 text-white rounded-br-none'
                            : 'bg-slate-900 border border-slate-800 text-slate-200 rounded-bl-none shadow-md'
                        }`}
                      >
                        {msg.reasoning_type && (
                          <div className="text-[10px] uppercase font-bold text-blue-400 mb-2 pb-1 border-b border-slate-800 flex items-center justify-between">
                            <span>{msg.reasoning_type}</span>
                            <span className="text-[9px] text-slate-500 font-normal">DrPilot Engine</span>
                          </div>
                        )}
                        
                        <FormattedMarkdown content={msg.text} />

                        {msg.citations && msg.citations.length > 0 && (
                          <div className="mt-3 pt-2.5 border-t border-slate-800/80 bg-slate-950/60 p-2.5 rounded-lg border border-slate-800/50">
                            <p className="text-[10px] font-bold uppercase tracking-wider text-blue-400 mb-1.5 flex items-center gap-1">
                              <span>📚</span> Attached Evidence Sources ({msg.citations.length})
                            </p>
                            <div className="space-y-1.5">
                              {msg.citations.map((c, cIdx) => (
                                <div key={cIdx} className="text-[11px] bg-slate-900/80 p-2 rounded border border-slate-800">
                                  <div className="flex justify-between font-semibold text-slate-200">
                                    <span>{c.title}</span>
                                    <span className="text-blue-400 text-[10px]">{c.score}%</span>
                                  </div>
                                  <p className="text-[10px] text-slate-400 mt-0.5">{c.source} • {c.category}</p>
                                </div>
                              ))}
                            </div>
                          </div>
                        )}
                      </div>
                    </div>
                  ))}

                  {chatLoading && (
                    <div className="text-xs text-slate-500 italic flex items-center gap-2 p-2">
                      <span className="w-2 h-2 rounded-full bg-blue-400 animate-ping"></span>
                      Evaluating clinical parameters...
                    </div>
                  )}
                </div>

                <div className="p-2.5 bg-slate-900 border-t border-slate-800 flex gap-2 overflow-x-auto text-xs">
                  <button
                    onClick={() => handleSendMessage('Summarize this case for consult')}
                    className="px-2.5 py-1 bg-slate-800 hover:bg-slate-700 text-blue-300 border border-slate-700 rounded-full whitespace-nowrap transition"
                  >
                    📋 Summarize Case
                  </button>
                  <button
                    onClick={() => handleSendMessage('What if D-Dimer test was normal?')}
                    className="px-2.5 py-1 bg-slate-800 hover:bg-slate-700 text-blue-300 border border-slate-700 rounded-full whitespace-nowrap transition"
                  >
                    🧪 What if D-Dimer was normal?
                  </button>
                </div>

                <form
                  onSubmit={(e) => {
                    e.preventDefault();
                    handleSendMessage(chatInput);
                  }}
                  className="p-3 bg-slate-950 border-t border-slate-800 flex gap-2"
                >
                  <input
                    type="text"
                    placeholder="Ask a question or type a scenario..."
                    value={chatInput}
                    onChange={(e) => setChatInput(e.target.value)}
                    className="flex-1 px-3 py-2 bg-slate-900 border border-slate-800 rounded-lg text-xs text-white focus:outline-none focus:ring-1 focus:ring-blue-500 placeholder-slate-500"
                  />
                  <button
                    type="submit"
                    disabled={chatLoading}
                    className="px-4 py-2 bg-blue-600 hover:bg-blue-500 text-xs font-semibold rounded-lg text-white transition disabled:bg-slate-800"
                  >
                    Send
                  </button>
                </form>
              </div>
            </div>
          )}
        </main>
      )}

      {/* DICOM Modal */}
      {selectedScan && patientData && (
        <div className="fixed inset-0 z-50 bg-black/85 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-slate-900 border border-slate-700 rounded-xl max-w-5xl w-full max-h-[92vh] flex flex-col overflow-hidden shadow-2xl">
            <div className="p-4 border-b border-slate-800 flex justify-between items-center bg-slate-950">
              <div>
                <h3 className="text-lg font-bold text-white flex items-center gap-2">
                  <span className="px-2 py-0.5 bg-blue-600 text-xs rounded text-white">{selectedScan.modality}</span>
                  {selectedScan.body_part} Examination
                </h3>
                <p className="text-xs text-slate-400 mt-0.5">
                  File: {selectedScan.file_name} • Date: {selectedScan.date}
                </p>
              </div>
              <div className="flex items-center gap-3">
                <button
                  onClick={handleRunVLMAnalysis}
                  disabled={vlmLoading}
                  className="px-3.5 py-1.5 bg-emerald-600 hover:bg-emerald-500 disabled:bg-emerald-800 text-white font-semibold rounded-lg text-xs transition flex items-center gap-1.5"
                >
                  {vlmLoading ? 'Analyzing Pixels...' : '✨ Run AI Vision Analysis'}
                </button>
                <button
                  onClick={() => setSelectedScan(null)}
                  className="px-3 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-lg text-xs font-semibold transition"
                >
                  Close Viewer ✕
                </button>
              </div>
            </div>

            <div className="flex-1 bg-black flex flex-col md:flex-row overflow-hidden min-h-[450px]">
              <div className="flex-1 relative flex items-center justify-center p-4 bg-black overflow-hidden">
                <div className="relative inline-block max-h-[65vh]">
                  <img
                    src={`http://localhost:8000/api/v1/patients/${patientData.patient_info.patient_id}/scans/${encodeURIComponent(selectedScan.sop_instance_uid)}/render`}
                    alt="DICOM Scan Preview"
                    className="max-h-[65vh] object-contain rounded border border-slate-800 shadow-lg"
                  />

                  {vlmAnalysis && showOverlays && vlmAnalysis.annotations.map((ann) => (
                    <div
                      key={ann.id}
                      style={{
                        left: `${ann.x_pct}%`,
                        top: `${ann.y_pct}%`,
                        width: `${ann.width_pct}%`,
                        height: `${ann.height_pct}%`
                      }}
                      className="absolute border-2 border-amber-400 bg-amber-400/10 rounded pointer-events-none transition-all duration-300 flex flex-col justify-between p-1"
                    >
                      <span className="bg-amber-500 text-slate-950 font-bold text-[9px] px-1 py-0.5 rounded self-start shadow">
                        {ann.label} ({ann.confidence}%)
                      </span>
                    </div>
                  ))}
                </div>
              </div>

              {vlmAnalysis && (
                <div className="w-full md:w-80 bg-slate-900 border-t md:border-t-0 md:border-l border-slate-800 p-4 overflow-y-auto space-y-4">
                  <div className="flex justify-between items-center pb-2 border-b border-slate-800">
                    <span className="text-xs font-bold text-amber-400 uppercase tracking-wider flex items-center gap-1.5">
                      <span className="w-2 h-2 rounded-full bg-amber-400 animate-ping"></span>
                      AI Vision Findings
                    </span>
                    <button
                      onClick={() => setShowOverlays(!showOverlays)}
                      className="text-[10px] text-slate-400 hover:text-white underline"
                    >
                      {showOverlays ? 'Hide Box' : 'Show Box'}
                    </button>
                  </div>

                  <div>
                    <span className="text-[10px] text-slate-500 uppercase font-semibold">Impression</span>
                    <p className="text-xs text-slate-200 mt-1 leading-relaxed bg-slate-950 p-2.5 rounded border border-slate-800">
                      {vlmAnalysis.impression}
                    </p>
                  </div>

                  <div>
                    <span className="text-[10px] text-slate-500 uppercase font-semibold">Key Radiologic Findings</span>
                    <ul className="mt-1 space-y-1.5 text-xs text-slate-300">
                      {vlmAnalysis.findings.map((f, i) => (
                        <li key={i} className="flex gap-1.5 text-[11px] leading-snug">
                          <span className="text-amber-400 font-bold">•</span>
                          <span>{f}</span>
                        </li>
                      ))}
                    </ul>
                  </div>

                  <div className="pt-3 border-t border-slate-800 space-y-2 bg-slate-950/80 p-3 rounded-lg border border-slate-800">
                    <span className="text-[11px] font-bold text-emerald-400 uppercase tracking-wider block">
                      Physician Attestation Sign-Off
                    </span>
                    <input
                      type="text"
                      placeholder="Optional notes or modification remarks..."
                      value={attestationNotes}
                      onChange={(e) => setAttestationNotes(e.target.value)}
                      className="w-full px-2.5 py-1.5 bg-slate-900 border border-slate-800 rounded text-xs text-white focus:outline-none focus:ring-1 focus:ring-emerald-500 placeholder-slate-500"
                    />
                    <div className="grid grid-cols-3 gap-1.5 pt-1">
                      <button
                        onClick={() => handleSignOff('ACCEPTED')}
                        disabled={attestationSubmitting}
                        className="px-2 py-1.5 bg-emerald-700 hover:bg-emerald-600 text-white font-bold text-[10px] rounded transition shadow-sm"
                      >
                        Accept
                      </button>
                      <button
                        onClick={() => handleSignOff('MODIFIED')}
                        disabled={attestationSubmitting}
                        className="px-2 py-1.5 bg-amber-700 hover:bg-amber-600 text-white font-bold text-[10px] rounded transition shadow-sm"
                      >
                        Modify
                      </button>
                      <button
                        onClick={() => handleSignOff('REJECTED')}
                        disabled={attestationSubmitting}
                        className="px-2 py-1.5 bg-red-700 hover:bg-red-600 text-white font-bold text-[10px] rounded transition shadow-sm"
                      >
                        Reject
                      </button>
                    </div>
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}