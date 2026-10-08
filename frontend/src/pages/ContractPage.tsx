import React, { useState, useCallback, useEffect } from 'react';
import {
    FileCode2, Plus, RefreshCw, CheckCircle2,
    XCircle, Clock, Shield, Upload, FileJson, Link2, ChevronDown
} from '../components/icons';
// Badge used in main component
import DataTable, { type DataTableColumn } from '../components/ui/DataTable';
import PageHeader from '../components/ui/PageHeader';
import { API_BASE_URL } from '../config';
import StatCard from '../components/ui/StatCard';

// ── Types ──
interface Contract {
    contract_id: string;
    consumer: string;
    provider: string;
    created_at?: string;
    version?: string;
}

interface ContractStats {
    total_contracts: number;
    verified: number;
    failed: number;
    pending: number;
}

// ── API ──
const createContract = async (consumer: string, provider: string, interactions: object[], version: string): Promise<Contract> => {
    const res = await fetch(`${API_BASE_URL}/api/contract/create`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ consumer, provider, interactions, version }),
    });
    return res.json();
};

const verifyContract = async (contractId: string, providerUrl: string) => {
    const res = await fetch(`${API_BASE_URL}/api/contract/${contractId}/verify`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ provider_url: providerUrl }),
    });
    return res.json();
};

const getContractStats = async (): Promise<ContractStats> => {
    const res = await fetch(`${API_BASE_URL}/api/contract/stats`);
    return res.json();
};


// ============================================================================
const ContractPage: React.FC = () => {
    const [stats, setStats] = useState<ContractStats>({ total_contracts: 0, verified: 0, failed: 0, pending: 0 });
    const [contracts, setContracts] = useState<Contract[]>([]);
    const [loading, setLoading] = useState(true);
    const [consumer, setConsumer] = useState('');
    const [provider, setProvider] = useState('');
    const [version, setVersion] = useState('1.0.0');
    const [providerUrl, setProviderUrl] = useState('');
    const [creating, setCreating] = useState(false);
    const [openApiJson, setOpenApiJson] = useState('');
    const [openApiUrl, setOpenApiUrl] = useState('');
    const [importPanelOpen, setImportPanelOpen] = useState(false);
    const [importStatus, setImportStatus] = useState<string | null>(null);
    const [importing, setImporting] = useState(false);

    const load = useCallback(async () => {
        try {
            const s = await getContractStats();
            setStats(s);
        } catch { /* */ }
        setLoading(false);
    }, []);

    useEffect(() => {
        // eslint-disable-next-line react-hooks/set-state-in-effect -- async load
        load();
    }, [load]);

    const handleCreate = async () => {
        if (!consumer || !provider) return;
        setCreating(true);
        try {
            const c = await createContract(consumer, provider, [{ description: 'Default interaction', request: {}, response: {} }], version);
            setContracts(prev => [...prev, c]);
            setConsumer('');
            setProvider('');
            await load();
        } catch { /* */ }
        setCreating(false);
    };

    const handleVerify = async (contractId: string) => {
        if (!providerUrl) return;
        try {
            const result = await verifyContract(contractId, providerUrl);
            // Update UI with result
            setContracts(prev => prev.map(c =>
                c.contract_id === contractId ? { ...c, status: result.passed ? 'passed' : 'failed' } : c
            ));
            await load();
        } catch { /* */ }
    };

    const columns: DataTableColumn<Contract>[] = [
        { key: 'contract_id', title: 'ID', width: '90px', render: (v) => <code className="text-xs font-mono">{String(v).slice(0, 8)}</code> },
        { key: 'consumer', title: "Consumer", sortable: true },
        { key: 'provider', title: "Provider", sortable: true },
        { key: 'version', title: "Version" },
        {
            key: 'actions', title: "Actions", align: 'center' as const, render: (_v, record) => (
                <button
                    onClick={() => handleVerify(record.contract_id)}
                    disabled={!providerUrl}
                    className="text-xs text-indigo-500 hover:text-indigo-700 font-medium disabled:opacity-40"
                >
                    Verify
                </button>
            )
        },
    ];

    return (
        <div className="space-y-6 max-w-7xl mx-auto">
            <PageHeader
                icon={<FileCode2 className="w-5 h-5" />}
                title={"Contract testing"}
                description={"Manage API consumer-provider contracts (Pact) and verify compatibility"}
                accent="orange"
            />

            <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
                <StatCard icon={<FileCode2 className="w-5 h-5" />} label={"Total contracts"} value={stats.total_contracts} gradient="bg-gradient-to-br from-orange-500 to-orange-700" />
                <StatCard icon={<CheckCircle2 className="w-5 h-5" />} label={"Verified"} value={stats.verified} gradient="bg-gradient-to-br from-emerald-500 to-emerald-700" />
                <StatCard icon={<XCircle className="w-5 h-5" />} label={"Verification failed"} value={stats.failed} gradient="bg-gradient-to-br from-red-500 to-red-700" />
                <StatCard icon={<Clock className="w-5 h-5" />} label={"Pending verification"} value={stats.pending} gradient="bg-gradient-to-br from-amber-500 to-amber-700" />
            </div>

            <div className="grid lg:grid-cols-3 gap-6">
                <div className="lg:col-span-1 space-y-4">
                    {/* Create Contract */}
                    <div className="rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 p-4 space-y-3">
                        <h3 className="text-sm font-semibold text-slate-700 dark:text-slate-200 flex items-center gap-2">
                            <Plus className="w-4 h-4 text-orange-500" />
                            Create contract
                        </h3>
                        <input type="text" value={consumer} onChange={e => setConsumer(e.target.value)} placeholder={"Consumer name"} className="w-full text-xs rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 px-3 py-2 outline-none focus:ring-2 focus:ring-orange-500/30" />
                        <input type="text" value={provider} onChange={e => setProvider(e.target.value)} placeholder={"Provider name"} className="w-full text-xs rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 px-3 py-2 outline-none focus:ring-2 focus:ring-orange-500/30" />
                        <input type="text" value={version} onChange={e => setVersion(e.target.value)} placeholder={"Version number"} className="w-full text-xs rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 px-3 py-2 outline-none focus:ring-2 focus:ring-orange-500/30" />
                        <button onClick={handleCreate} disabled={creating || !consumer || !provider} className="w-full flex items-center justify-center gap-2 rounded-lg bg-orange-500 hover:bg-orange-600 text-white text-xs font-medium py-2 transition-colors disabled:opacity-50">
                            {creating ? <RefreshCw className="w-3.5 h-3.5 animate-spin" /> : <Plus className="w-3.5 h-3.5" />}
                            {creating ? "Creating..." : "Create contract"}
                        </button>
                    </div>

                    {/* Verify Panel */}
                    <div className="rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 p-4 space-y-3">
                        <h3 className="text-sm font-semibold text-slate-700 dark:text-slate-200 flex items-center gap-2">
                            <Shield className="w-4 h-4 text-emerald-500" />
                            Verification settings
                        </h3>
                        <input type="url" value={providerUrl} onChange={e => setProviderUrl(e.target.value)} placeholder={"Provider URL (for example, http://api.example.com)"} className="w-full text-xs rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 px-3 py-2 outline-none focus:ring-2 focus:ring-emerald-500/30" />
                        <p className="text-[10px] text-slate-400">After configuration, click Verify in the table to check contract compatibility</p>
                    </div>

                    {/* OpenAPI Import Panel */}
                    <div className="rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 overflow-hidden">
                        <button onClick={() => setImportPanelOpen(!importPanelOpen)}
                            className="w-full p-4 flex items-center justify-between hover:bg-slate-50 dark:hover:bg-slate-800/50 transition">
                            <h3 className="text-sm font-semibold text-slate-700 dark:text-slate-200 flex items-center gap-2">
                                <Upload className="w-4 h-4 text-indigo-500" />
                                OpenAPI/Swagger import
                            </h3>
                            <ChevronDown className={`w-3.5 h-3.5 text-slate-400 transition-transform ${importPanelOpen ? 'rotate-180' : ''}`} />
                        </button>
                        {importPanelOpen && (
                            <div className="border-t border-slate-200 dark:border-slate-800 p-4 space-y-3">
                                {/* URL fetch */}
                                <div>
                                    <label className="text-[10px] text-slate-500 uppercase font-semibold tracking-wider mb-1 flex items-center gap-1">
                                        <Link2 className="w-3 h-3" /> Fetch from URL
                                    </label>
                                    <div className="flex gap-1.5">
                                        <input type="url" value={openApiUrl} onChange={e => setOpenApiUrl(e.target.value)}
                                            placeholder="https://petstore.swagger.io/v2/swagger.json"
                                            className="flex-1 text-xs rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 px-3 py-2 outline-none focus:ring-2 focus:ring-indigo-500/30" />
                                        <button onClick={async () => {
                                            if (!openApiUrl) return;
                                            setImporting(true); setImportStatus(null);
                                            try {
                                                const res = await fetch(openApiUrl);
                                                const text = await res.text();
                                                setOpenApiJson(text);
                                                setImportStatus("✅ OpenAPI specification fetched");
                                            } catch {
                                                setImportStatus("❌ Failed to fetch. Check the URL.");
                                            }
                                            setImporting(false);
                                        }} disabled={importing || !openApiUrl}
                                            className="px-3 py-2 text-xs font-medium text-indigo-600 bg-indigo-50 dark:bg-indigo-900/20 border border-indigo-200 dark:border-indigo-800 rounded-lg hover:bg-indigo-100 transition disabled:opacity-50">
                                            {importing ? <RefreshCw className="w-3 h-3 animate-spin" /> : "Fetch"}
                                        </button>
                                    </div>
                                </div>

                                {/* JSON paste */}
                                <div>
                                    <label className="text-[10px] text-slate-500 uppercase font-semibold tracking-wider mb-1 flex items-center gap-1">
                                        <FileJson className="w-3 h-3" /> Or paste OpenAPI JSON
                                    </label>
                                    <textarea value={openApiJson} onChange={e => setOpenApiJson(e.target.value)}
                                        rows={5} placeholder='{"openapi": "3.0.0", "info": {...}, "paths": {...}}'
                                        className="w-full text-xs font-mono rounded-lg border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800 px-3 py-2 outline-none focus:ring-2 focus:ring-indigo-500/30 resize-none" />
                                </div>

                                {importStatus && <p className="text-[11px] text-slate-500">{importStatus}</p>}

                                <button onClick={async () => {
                                    if (!openApiJson.trim()) return;
                                    setImporting(true); setImportStatus(null);
                                    try {
                                        const spec = JSON.parse(openApiJson);
                                        const title = spec.info?.title || 'OpenAPI Service';
                                        const ver = spec.info?.version || '1.0.0';
                                        const paths = spec.paths || {};
                                        const interactions: { description: string; request: { method: string; path: string }; response: { status: number } }[] = [];
                                        for (const [path, methods] of Object.entries(paths)) {
                                            for (const [method, detail] of Object.entries(methods as Record<string, { summary?: string }>)) {
                                                if (['get', 'post', 'put', 'delete', 'patch'].includes(method)) {
                                                    interactions.push({
                                                        description: detail?.summary || `${method.toUpperCase()} ${path}`,
                                                        request: { method: method.toUpperCase(), path },
                                                        response: { status: 200 },
                                                    });
                                                }
                                            }
                                        }
                                        if (interactions.length === 0) {
                                            setImportStatus("❌ No valid API paths found");
                                            setImporting(false);
                                            return;
                                        }
                                        const c = await createContract('Auto-Consumer', title, interactions, ver);
                                        setContracts(prev => [...prev, c]);
                                        await load();
                                        setImportStatus(`✅ Imported ${interactions.length} API paths as contracts`);
                                        setOpenApiJson('');
                                        setOpenApiUrl('');
                                    } catch {
                                        setImportStatus("❌ Failed to parse. Check the JSON format.");
                                    }
                                    setImporting(false);
                                }} disabled={importing || !openApiJson.trim()}
                                    className="w-full flex items-center justify-center gap-2 rounded-lg bg-indigo-500 hover:bg-indigo-600 text-white text-xs font-medium py-2 transition-colors disabled:opacity-50">
                                    {importing ? <RefreshCw className="w-3.5 h-3.5 animate-spin" /> : <Upload className="w-3.5 h-3.5" />}
                                    Parse and import contracts
                                </button>
                            </div>
                        )}
                    </div>
                </div>

                <div className="lg:col-span-2">
                    <DataTable<Contract>
                        columns={columns}
                        data={contracts}
                        rowKey="contract_id"
                        pageSize={8}
                        loading={loading}
                        emptyText={"No contracts yet. Create a consumer-provider contract to begin."}
                    />
                </div>
            </div>
        </div>
    );
};

export default ContractPage;
