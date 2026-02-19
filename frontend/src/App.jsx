import React, { useState, useEffect } from 'react';
import { Upload, ShieldAlert, Download, Activity, Search, X, Crosshair, BarChart3, Database, Cpu, Zap, Play, Pause } from 'lucide-react';
import GraphView from './components/GraphView';
import StatsDashboard from './components/StatsDashboard';
import TrendChart from './components/TrendChart';

// Simplified Error Boundary
const ErrorBoundary = ({ children }) => {
    const [hasError, setHasError] = useState(false);
    useEffect(() => {
        const handleError = (error) => {
            console.error("React Captured Error:", error);
            setHasError(true);
        };
        window.addEventListener('error', handleError);
        return () => window.removeEventListener('error', handleError);
    }, []);

    if (hasError) {
        return (
            <div className="min-h-screen bg-black text-red-500 flex flex-col items-center justify-center p-10 font-mono">
                <ShieldAlert size={48} className="mb-4" />
                <h1 className="text-2xl font-bold mb-2">CRITICAL UI FAILURE</h1>
                <p className="text-slate-400 text-center">The behavioral engine encountered a runtime exception. Check the browser console for details.</p>
                <button onClick={() => window.location.reload()} className="mt-8 px-6 py-2 bg-red-500 text-white rounded-lg">RELOAD SYSTEM</button>
            </div>
        );
    }
    return children;
};

const App = () => {
    const [file, setFile] = useState(null);
    const [data, setData] = useState(null);
    const [loading, setLoading] = useState(false);
    const [progress, setProgress] = useState({ status: '', percent: 0 });
    const [selectedAcc, setSelectedAcc] = useState(null);
    const [error, setError] = useState(null);
    const [filterSuspicious, setFilterSuspicious] = useState(false);
    const [searchQuery, setSearchQuery] = useState('');
    const [riskFilter, setRiskFilter] = useState(0);
    const [aiAnalysis, setAiAnalysis] = useState(null);
    const [aiLoading, setAiLoading] = useState(false);

    const API_BASE_URL = import.meta.env.VITE_API_URL || '/api';

    // Simulation States
    const [isSimulating, setIsSimulating] = useState(false);
    const [simulationIndex, setSimulationIndex] = useState(0);
    const [simulationSpeed, setSimulationSpeed] = useState(1);
    const [simulationData, setSimulationData] = useState(null);

    // Simulation Loop
    useEffect(() => {
        let interval;
        if (isSimulating && data) {
            interval = setInterval(() => {
                setSimulationIndex(prev => {
                    const next = prev + 1;
                    if (next >= 100) {
                        setIsSimulating(false);
                        return 100;
                    }
                    return next;
                });
            }, 100 / simulationSpeed);
        }
        return () => clearInterval(interval);
    }, [isSimulating, data, simulationSpeed]);

    // Compute simulation data
    useEffect(() => {
        if (!data || !isSimulating) {
            setSimulationData(data);
            return;
        }

        // Slice the graph based on the simulation percentage
        // For a true forensic replay, we'd slice by actual timestamps
        // but for a demo, we'll reveal nodes based on risk order
        const totalNodes = data.graph_data.nodes.length;
        const visibleNodeCount = Math.floor((simulationIndex / 100) * totalNodes);

        const visibleNodes = data.graph_data.nodes.slice(0, Math.max(1, visibleNodeCount));
        const visibleNodeIds = new Set(visibleNodes.map(n => n.id));

        const visibleEdges = data.graph_data.edges.filter(e =>
            visibleNodeIds.has(e.from_node) && visibleNodeIds.has(e.to_node)
        );

        setSimulationData({
            ...data,
            graph_data: {
                nodes: visibleNodes,
                edges: visibleEdges
            }
        });
    }, [data, simulationIndex, isSimulating]);

    const handleAIAnalyze = async (accountId) => {
        setAiLoading(true);
        setAiAnalysis(null);
        try {
            const response = await fetch(`${API_BASE_URL}/ai-analyze/${accountId}`, { method: 'POST' });
            if (!response.ok) throw new Error('AI analysis failed');
            const result = await response.json();
            setAiAnalysis(result);
        } catch (err) {
            console.error(err);
        } finally {
            setAiLoading(false);
        }
    };

    const processAnalysisStream = async (response) => {
        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';

        while (true) {
            const { value, done } = await reader.read();
            if (done) break;

            buffer += decoder.decode(value, { stream: true });
            const parts = buffer.split('\n\n');
            buffer = parts.pop();

            for (const part of parts) {
                const line = part.trim();
                if (line.startsWith('data: ')) {
                    const jsonStr = line.replace('data: ', '');
                    try {
                        const parsed = JSON.parse(jsonStr);
                        if (parsed.error) {
                            setError(parsed.error);
                            setLoading(false);
                            return;
                        }
                        if (parsed.complete) {
                            setData(parsed);
                            setProgress({ status: 'Analysis Complete', percent: 100 });
                        } else {
                            setProgress({ status: parsed.status, percent: (parsed.progress || 0) * 100 });
                        }
                    } catch (e) {
                        console.error("JSON parse error:", e);
                        console.log("Raw received:", jsonStr);
                        // If it's not JSON, it might be an HTML error page from Vercel
                        if (jsonStr.includes('<!DOCTYPE html>') || jsonStr.includes('<html')) {
                            setError("Server Error: The backend returned an HTML error page. This often happens on Vercel if the function crashes or times out.");
                        } else {
                            setError("Analysis Error: Failed to parse server response.");
                        }
                        setLoading(false);
                        return;
                    }
                }
            }
        }
    };

    const handleGenerateDemo = async () => {
        setLoading(true);
        setError(null);
        setProgress({ status: 'Synthesizing Demo Dataset...', percent: 5 });
        const response = await fetch(`${API_BASE_URL}/generate-demo`, { method: 'POST' });
        if (!response.ok) {
            const errText = await response.text();
            throw new Error(`Server Error (${response.status}): ${errText.substring(0, 100)}...`);
        }
        await processAnalysisStream(response);
    } catch (err) {
        setError(err.message);
    } finally {
        setLoading(false);
    }
};

const handleUpload = async (e) => {
    const selectedFile = e.target.files[0];
    if (!selectedFile) return;

    setFile(selectedFile);
    setLoading(true);
    setError(null);
    setProgress({ status: 'Initializing Engine...', percent: 5 });

    const formData = new FormData();
    formData.append('file', selectedFile);

    try {
        const response = await fetch(`${API_BASE_URL}/upload`, {
            method: 'POST',
            body: formData,
        });

        if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.detail || 'Upload failed');
        }

        await processAnalysisStream(response);
    } catch (err) {
        setError(err.message || 'Failed to analyze data');
    } finally {
        setLoading(false);
    }
};

const downloadReport = () => {
    if (!data) return;

    // Exact format matching for hackathon submission
    const exportData = {
        suspicious_accounts: data.suspicious_accounts.map(acc => ({
            account_id: acc.account_id,
            suspicion_score: acc.suspicion_score,
            detected_patterns: acc.detected_patterns,
            ring_id: acc.ring_id
        })),
        fraud_rings: data.fraud_rings.map(ring => ({
            ring_id: ring.ring_id,
            member_accounts: ring.member_accounts,
            pattern_type: ring.pattern_type,
            risk_score: ring.risk_score
        })),
        summary: {
            total_accounts_analyzed: data.summary.total_accounts_analyzed,
            suspicious_accounts_flagged: data.summary.suspicious_accounts_flagged,
            fraud_rings_detected: data.summary.fraud_rings_detected,
            processing_time_seconds: data.summary.processing_time_seconds
        }
    };

    const blob = new Blob([JSON.stringify(exportData, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `money_muling_analysis_${Date.now()}.json`;
    a.click();
};

return (
    <div className="min-h-screen bg-[#070708] text-slate-100 p-4 md:p-10 font-sans selection:bg-blue-500/30">
        {/* Nav / Hero Header */}
        <nav className="w-full max-w-[2400px] mx-auto mb-16 flex flex-col xl:flex-row xl:items-end justify-between gap-10 px-4 md:px-12">
            <div className="flex-1">
                <div className="flex items-center gap-2 text-blue-500 mb-4 font-mono text-sm tracking-widest font-bold uppercase overflow-hidden">
                    <Zap size={14} className="fill-current" />
                    <span className="animate-shimmer bg-gradient-to-r from-transparent via-white/20 to-transparent bg-[length:200%_100%]">Real-Time Forensic Engine Active</span>
                </div>
                <h1 className="text-5xl md:text-7xl font-extrabold tracking-tighter text-gradient pb-2 bg-clip-text">
                    FINANCIAL <br /><span className="text-blue-500">FORENSICS</span> ENGINE
                </h1>
                <p className="mt-4 text-slate-400 text-lg max-w-2xl font-light leading-relaxed">
                    Identify money muling networks and dispersal hierarchies using
                    <span className="text-slate-200"> behavioral graph analytics</span>.
                </p>
            </div>

            {/* Unified Command Center */}
            <div className="glass-shiny p-6 rounded-[2.5rem] flex flex-wrap items-center gap-6 shadow-2xl border-white/10">
                <div className="flex flex-col gap-2">
                    <div className="text-[10px] font-black text-slate-500 uppercase tracking-widest ml-1">Command Center</div>
                    <div className="flex items-center gap-3">
                        <label className="relative overflow-hidden flex items-center gap-3 px-8 py-4 bg-blue-600 hover:bg-blue-500 text-white rounded-2xl cursor-pointer transition-all active:scale-95 shadow-[0_0_20px_rgba(37,99,235,0.3)]">
                            <Upload size={18} className={loading ? 'animate-bounce' : ''} />
                            <span className="font-bold tracking-tight uppercase text-sm">{loading ? 'Processing...' : 'Ingest Data'}</span>
                            <input type="file" className="hidden" accept=".csv" onChange={handleUpload} disabled={loading} />
                        </label>

                        <button
                            onClick={handleGenerateDemo}
                            className="px-6 py-4 glass border-white/10 hover:bg-white/5 rounded-2xl text-xs font-bold uppercase tracking-widest text-blue-400 transition-all"
                        >
                            <Database size={16} className="inline mr-2" /> Load Demo Data
                        </button>
                    </div>
                </div>

                <div className="h-12 w-px bg-white/5 mx-2 hidden md:block" />

                {data && (
                    <>
                        <div className="flex flex-col gap-2">
                            <div className="text-[10px] font-black text-slate-500 uppercase tracking-widest ml-1">Risk Filter: {riskFilter}%</div>
                            <div className="px-6 py-4 glass border-white/5 rounded-2xl flex items-center group">
                                <input
                                    type="range"
                                    min="0"
                                    max="100"
                                    value={riskFilter}
                                    onChange={(e) => setRiskFilter(parseInt(e.target.value))}
                                    className="w-32 accent-blue-500"
                                />
                            </div>
                        </div>

                        <div className="flex flex-col gap-2 ml-auto">
                            <div className="text-[10px] font-black text-slate-500 uppercase tracking-widest ml-1 text-right">Reports</div>
                            <button
                                onClick={downloadReport}
                                className="flex items-center gap-3 px-8 py-4 bg-white/5 hover:bg-white/10 text-white rounded-2xl transition-all border border-white/10 text-sm font-bold uppercase"
                            >
                                <Download size={18} /> Download JSON
                            </button>
                        </div>
                    </>
                )}

                {!data && (
                    <div className="px-10 py-10 glass border-white/5 border-dashed rounded-[2rem] text-[10px] font-black text-slate-600 uppercase tracking-[0.2em] flex flex-col items-center gap-2">
                        <Cpu size={20} className="opacity-20" />
                        System Standby
                    </div>
                )}
            </div>
        </nav>

        {/* Error or Progress State */}
        {loading && (
            <div className="w-full max-w-[2400px] mx-auto mb-10 overflow-hidden glass p-10 flex flex-col items-center justify-center relative rounded-[3rem]">
                <div className="absolute inset-0 shimmer opacity-5" />
                <Cpu size={56} className="text-blue-500 mb-6 pulse-red" />
                <h3 className="text-xl font-bold font-mono tracking-widest text-blue-400">{progress.status}</h3>
                <div className="w-full max-w-md h-1.5 bg-white/5 rounded-full mt-6 overflow-hidden">
                    <div
                        className="h-full bg-blue-500 transition-all duration-500 ease-out shadow-[0_0_15px_rgba(59,130,246,0.6)]"
                        style={{ width: `${progress.percent}%` }}
                    />
                </div>
            </div>
        )}

        {error && (
            <div className="w-full max-w-[2400px] mx-auto mb-10 p-6 bg-red-500/10 border border-red-500/20 text-red-400 rounded-3xl flex items-center gap-4 animate-in slide-in-from-top duration-300">
                <ShieldAlert size={24} />
                <span className="font-medium">{error}</span>
            </div>
        )}

        {data && !loading && (
            <div className="w-full max-w-[2400px] mx-auto space-y-10 animate-in fade-in zoom-in-95 duration-700 px-4 md:px-12">
                {/* KPI Ribbon */}
                <div className="grid grid-cols-2 md:grid-cols-3 xl:grid-cols-6 gap-4">
                    {[
                        { label: 'Analytic Scope', value: data.summary.total_accounts_analyzed, sub: 'ACCOUNTS', icon: <Database size={16} /> },
                        { label: 'Ingested', value: data.summary.total_transactions, sub: 'TRANSACTIONS', icon: <Activity size={16} /> },
                        { label: 'Flagged Mules', value: data.summary.suspicious_accounts_flagged, color: 'text-red-500', sub: 'THREATS DETECTED', icon: <ShieldAlert size={16} />, pulse: true },
                        { label: 'Clusters', value: data.summary.fraud_rings_detected, sub: 'RINGS DETECTED', icon: <Crosshair size={16} /> },
                        { label: 'Avg Risk', value: `${data.summary.avg_risk_score}%`, color: 'text-orange-400', sub: 'NETWORK LOAD', icon: <BarChart3 size={16} /> },
                        { label: 'Execution', value: `${data.summary.processing_time_seconds.toFixed(3)}s`, sub: 'LATENCY', icon: <Cpu size={16} /> }
                    ].map((stat, idx) => (
                        <div key={idx} className={`glass p-6 group hover:translate-y-[-4px] transition-all duration-300 ${stat.pulse ? 'border-red-500/30' : ''}`}>
                            <div className="flex items-center gap-2 text-slate-500 text-[10px] font-black tracking-[0.2em] mb-3 uppercase">
                                {stat.icon} {stat.label}
                            </div>
                            <div className={`text-4xl font-extrabold tracking-tighter ${stat.color || ''}`}>{stat.value}</div>
                            <div className="text-[10px] text-slate-600 mt-2 font-bold tracking-widest">{stat.sub}</div>
                        </div>
                    ))}
                </div>

                {/* Main Workspace */}
                <div className="grid grid-cols-1 gap-10">
                    <section className="space-y-4">
                        <div className="flex items-center justify-between">
                            <h2 className="text-xl font-black uppercase tracking-widest text-slate-500 flex items-center gap-3">
                                <div className="w-2 h-2 rounded-full bg-blue-500 animate-pulse" />
                                Behavioral Topology
                            </h2>

                            {data && (
                                <div className="flex items-center gap-6 glass px-6 py-3 border-white/5 rounded-2xl">
                                    <div className="flex items-center gap-4">
                                        <button
                                            onClick={() => {
                                                if (simulationIndex >= 100) setSimulationIndex(0);
                                                setIsSimulating(!isSimulating);
                                            }}
                                            className={`p-2 rounded-lg transition-all ${isSimulating ? 'bg-red-500/10 text-red-500' : 'bg-blue-500/10 text-blue-500'}`}
                                        >
                                            {isSimulating ? <Pause size={18} fill="currentColor" /> : <Play size={18} fill="currentColor" />}
                                        </button>
                                        <div className="w-48 h-1 bg-white/5 rounded-full overflow-hidden relative">
                                            <div
                                                className="h-full bg-blue-500 transition-all duration-300"
                                                style={{ width: `${simulationIndex}%` }}
                                            />
                                        </div>
                                        <span className="text-[10px] font-black font-mono text-slate-500 w-12 text-right">
                                            {simulationIndex}%
                                        </span>
                                    </div>
                                    <div className="h-4 w-px bg-white/10" />
                                    <div className="flex border border-white/5 rounded-lg overflow-hidden">
                                        {[1, 2, 5].map(s => (
                                            <button
                                                key={s}
                                                onClick={() => setSimulationSpeed(s)}
                                                className={`px-3 py-1 text-[9px] font-black uppercase transition-all ${simulationSpeed === s ? 'bg-blue-600 text-white' : 'bg-white/5 text-slate-500 hover:bg-white/10'}`}
                                            >
                                                {s}x
                                            </button>
                                        ))}
                                    </div>
                                </div>
                            )}
                        </div>
                        <GraphView
                            data={simulationData || data}
                            onSelectNode={setSelectedAcc}
                            filterSuspiciousOnly={filterSuspicious}
                            highlightNode={searchQuery.length > 5 ? searchQuery : null}
                        />
                    </section>

                    <section className="space-y-4">
                        <h2 className="text-xl font-black uppercase tracking-widest text-slate-500 flex items-center gap-3">
                            <div className="w-2 h-2 rounded-full bg-red-500" />
                            Forensic Ledger & Network Clusters
                        </h2>
                        <StatsDashboard
                            accounts={data.suspicious_accounts.filter(a =>
                                a.suspicion_score >= riskFilter && (
                                    a.account_id.includes(searchQuery) ||
                                    a.detected_patterns.some(p => p.includes(searchQuery.toLowerCase()))
                                )
                            )}
                            rings={data.fraud_rings.filter(r =>
                                r.risk_score >= riskFilter && (
                                    r.ring_id.includes(searchQuery) ||
                                    r.member_accounts.some(m => m.includes(searchQuery))
                                )
                            )}
                            onSelect={(acc) => {
                                setSelectedAcc(acc);
                                window.scrollTo({ top: 0, behavior: 'smooth' });
                            }}
                        />
                    </section>
                </div>
            </div>
        )}

        {/* Premium Overlay */}
        {selectedAcc && (
            <div className="fixed inset-0 z-[100] flex items-center justify-center p-4 md:p-6 backdrop-blur-xl bg-black/80 animate-in fade-in duration-300">
                <div className="glass max-w-2xl w-full p-0 relative border-white/10 shadow-[0_32px_128px_rgba(0,0,0,1)] overflow-hidden flex flex-col max-h-[90vh]">
                    <div className="absolute top-0 right-0 p-20 bg-blue-500/5 blur-[100px] -z-1" />

                    <button
                        onClick={() => {
                            setSelectedAcc(null);
                            setAiAnalysis(null);
                        }}
                        className="absolute top-6 right-6 p-2 bg-white/10 hover:bg-white/20 rounded-xl transition-all border border-white/10 z-[110] backdrop-blur-md"
                    >
                        <X size={20} />
                    </button>

                    <div className="flex-1 overflow-y-auto p-10 custom-scrollbar mt-4">
                        <div className="flex flex-col md:flex-row items-start gap-8 mb-10">
                            <div className={`p-6 rounded-3xl shrink-0 ${selectedAcc.suspicion_score > 70 ? 'bg-red-500/10 border border-red-500/20' : 'bg-orange-500/10 border border-orange-500/20'}`}>
                                <ShieldAlert size={40} className={selectedAcc.suspicion_score > 70 ? 'text-red-500' : 'text-orange-500'} />
                                <div className="text-center mt-4 text-xs font-black opacity-40">FLAGGED</div>
                            </div>
                            <div className="flex-1">
                                <h2 className="text-4xl font-extrabold font-mono tracking-tighter break-all">{selectedAcc.account_id}</h2>
                                <div className="flex flex-wrap gap-2 mt-4">
                                    {selectedAcc.detected_patterns.map(tag => (
                                        <span key={tag} className="text-[10px] px-3 py-1 rounded-lg bg-white/5 border border-white/5 text-slate-400 font-bold uppercase tracking-widest">
                                            {tag.replace('_', ' ')}
                                        </span>
                                    ))}
                                </div>
                            </div>
                        </div>

                        <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-10">
                            <div className="p-6 bg-white/5 rounded-3xl border border-white/5">
                                <div className="text-[10px] font-black opacity-30 tracking-widest mb-1 uppercase">Risk Index</div>
                                <div className={`text-5xl font-extrabold tracking-tighter ${selectedAcc.suspicion_score > 70 ? 'text-red-500' : 'text-orange-400'}`}>
                                    {selectedAcc.suspicion_score}<span className="text-xl opacity-40 text-white">%</span>
                                </div>
                            </div>
                            <div className="p-6 bg-white/5 rounded-3xl border border-white/5">
                                <div className="text-[10px] font-black opacity-30 tracking-widest mb-1 uppercase">Entity Classification</div>
                                <div className="text-xl font-bold flex items-center gap-2 mt-2">
                                    {selectedAcc.is_legitimate_hub ? <Activity size={18} className="text-blue-500" /> : <Zap size={18} className="text-red-500" />}
                                    {selectedAcc.is_legitimate_hub ? 'Verified Hub' : 'Hostile Node'}
                                </div>
                            </div>
                        </div>

                        <div className="mb-10">
                            <div className="text-[10px] font-black opacity-30 tracking-widest mb-3 uppercase">Investigation Summary</div>
                            <p className="text-slate-400 leading-relaxed font-light italic border-l-2 border-slate-800 pl-6 text-lg">
                                "{selectedAcc.explanation}"
                            </p>
                        </div>

                        <div className="mb-10">
                            <div className="text-[10px] font-black opacity-30 tracking-widest mb-3 uppercase">Velocity Metrics</div>
                            <TrendChart transactions={selectedAcc.recent_transactions} />
                        </div>

                        {/* AI Forensic Report Section */}
                        <div className="mb-10 pt-10 border-t border-white/5">
                            <div className="flex items-center justify-between mb-6">
                                <div className="text-[10px] font-black text-blue-500 tracking-[0.2em] uppercase flex items-center gap-2">
                                    <Cpu size={14} className="animate-pulse" /> AI Laboratory
                                </div>
                                <button
                                    onClick={() => handleAIAnalyze(selectedAcc.account_id)}
                                    disabled={aiLoading}
                                    className={`px-6 py-2 rounded-xl text-[10px] font-black uppercase tracking-widest transition-all ${aiLoading ? 'bg-white/5 text-slate-500 cursor-not-allowed' : 'bg-blue-600 hover:bg-blue-500 text-white shadow-[0_0_20px_rgba(37,99,235,0.4)]'}`}
                                >
                                    {aiLoading ? 'Analyzing Patterns...' : 'Run AI Deep Dive'}
                                </button>
                            </div>

                            {aiAnalysis ? (
                                <div className="glass p-8 border-blue-500/20 bg-blue-500/[0.02] animate-in zoom-in-95 duration-500">
                                    <div className="flex items-center gap-2 text-blue-400 text-xs font-bold mb-4 uppercase">
                                        <ShieldAlert size={14} /> Intelligence Report
                                    </div>
                                    <p className="text-slate-200 text-lg font-bold leading-relaxed mb-6">
                                        {aiAnalysis.forensic_summary}
                                    </p>
                                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
                                        {aiAnalysis.behavioral_flags.map((flag, idx) => (
                                            <div key={idx} className="p-4 bg-white/5 rounded-2xl border border-white/5">
                                                <div className="text-[9px] font-black text-slate-500 uppercase mb-1">{flag.type} Anomaly</div>
                                                <div className="text-xs text-slate-300 font-medium">{flag.detail}</div>
                                            </div>
                                        ))}
                                    </div>
                                    <div className="p-6 bg-red-500/10 border border-red-500/20 rounded-2xl">
                                        <div className="text-[9px] font-black text-red-500 uppercase mb-2">System Recommendation</div>
                                        <div className="text-sm font-bold text-red-400">{aiAnalysis.recommendation}</div>
                                    </div>
                                    <div className="mt-4 text-right">
                                        <span className="text-[9px] font-black text-slate-600 uppercase">Confidence Level: {(aiAnalysis.prediction_confidence * 100).toFixed(1)}%</span>
                                    </div>
                                </div>
                            ) : (
                                !aiLoading && (
                                    <div className="p-12 border border-dashed border-white/5 rounded-[2rem] text-center">
                                        <Cpu size={32} className="mx-auto text-slate-800 mb-4" />
                                        <p className="text-xs text-slate-600 font-bold uppercase tracking-widest">Awaiting Forensic Scan</p>
                                    </div>
                                )
                            )}

                            {aiLoading && (
                                <div className="p-12 border border-blue-500/20 rounded-[2rem] text-center glass">
                                    <div className="w-10 h-10 border-4 border-blue-500/30 border-t-blue-500 rounded-full animate-spin mx-auto mb-4" />
                                    <p className="text-xs text-blue-500 font-black uppercase tracking-widest animate-pulse">Running Neural Investigation...</p>
                                </div>
                            )}
                        </div>

                        {selectedAcc.recent_transactions && selectedAcc.recent_transactions.length > 0 && (
                            <div>
                                <div className="text-[10px] font-black opacity-30 tracking-widest mb-6 uppercase flex items-center gap-2">
                                    <BarChart3 size={14} /> Transactional Evidence
                                </div>
                                <div className="space-y-3">
                                    {selectedAcc.recent_transactions.map((tx, idx) => (
                                        <div key={idx} className="p-5 bg-white/5 border border-white/5 rounded-2xl flex justify-between items-center group hover:bg-white/10 transition-colors">
                                            <div className="space-y-1">
                                                <div className="text-[9px] font-bold font-mono opacity-20 tracking-tighter uppercase">{tx.transaction_id}</div>
                                                <div className="text-sm font-bold font-mono">
                                                    <span className={tx.sender_id === selectedAcc.account_id ? 'text-red-500' : 'text-blue-400'}>
                                                        {tx.sender_id === selectedAcc.account_id ? 'DISBURSED TO' : 'RECEIVED FROM'}
                                                    </span>
                                                    {' '}
                                                    <span className="opacity-80 text-xs">
                                                        {tx.sender_id === selectedAcc.account_id ? tx.receiver_id : tx.sender_id}
                                                    </span>
                                                </div>
                                                <div className="text-[10px] opacity-20 font-medium">{tx.timestamp}</div>
                                            </div>
                                            <div className="text-xl font-black group-hover:scale-110 transition-transform duration-300">
                                                ${tx.amount.toLocaleString()}
                                            </div>
                                        </div>
                                    ))}
                                </div>
                            </div>
                        )}
                    </div>
                </div>
            </div>
        )}

        {!data && !loading && (
            <div className="w-full max-w-[2400px] mx-auto py-32 glass border-2 border-dashed border-white/5 flex flex-col items-center justify-center text-center px-10 relative overflow-hidden group rounded-[4rem]">
                <div className="absolute inset-0 bg-blue-500/5 opacity-0 group-hover:opacity-100 transition-opacity duration-700" />
                <Upload size={80} className="text-blue-500/20 mb-8 group-hover:scale-110 group-hover:text-blue-500 transition-all duration-700" />
                <h2 className="text-4xl font-extrabold tracking-tighter mb-4 opacity-50">SYSTEM AWAITING INGESTION</h2>
                <p className="text-slate-500 text-lg max-w-md font-light">
                    Upload a transaction dataset (CSV) to initialize the analysis.
                    Your submission-ready <span className="text-blue-500/60 font-bold">Forensic JSON Report</span> will be generated automatically.
                </p>
                <div className="mt-10 flex gap-4">
                    <div className="px-4 py-2 bg-white/5 rounded-full text-[10px] font-black tracking-widest opacity-30 uppercase border border-white/5">Auto-Mapping Enabled</div>
                    <div className="px-4 py-2 bg-white/5 rounded-full text-[10px] font-black tracking-widest opacity-30 uppercase border border-white/5">Graph-Ready</div>
                </div>
            </div>
        )}
    </div>
);
};

const AppSafe = () => (
    <ErrorBoundary>
        <App />
    </ErrorBoundary>
);

export default AppSafe;
