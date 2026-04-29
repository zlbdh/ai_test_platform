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
        { key: 'consumer', title: '消费者', sortable: true },
        { key: 'provider', title: '提供者', sortable: true },
        { key: 'version', title: '版本' },
        {
            key: 'actions', title: '操作', align: 'center' as const, render: (_v, record) => (
                <button
                    onClick={() => handleVerify(record.contract_id)}
                    disabled={!providerUrl}
                    className="text-xs text-indigo-500 hover:text-indigo-700 font-medium disabled:opacity-40"
                >
                    验证
                </button>
            )
        },
    ];

    return (
        <div className="space-y-6 max-w-7xl mx-auto">
            <PageHeader
                icon={<FileCode2 className="w-5 h-5" />}
                title="契约测试"
                description="管理 API 消费者-提供者契约（Pact），验证契约兼容性"
                accent="orange"
            />

            <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
                <StatCard icon={<FileCode2 className="w-5 h-5" />} label="总契约数" value={stats.total_contracts} gradient="bg-gradient-to-br from-orange-500 to-orange-700" />
                <StatCard icon={<CheckCircle2 className="w-5 h-5" />} label="已验证" value={stats.verified} gradient="bg-gradient-to-br from-emerald-500 to-emerald-700" />
                <StatCard icon={<XCircle className="w-5 h-5" />} label="验证失败" value={stats.failed} gradient="bg-gradient-to-br from-red-500 to-red-700" />
                <StatCard icon={<Clock className="w-5 h-5" />} label="待验证" value={stats.pending} gradient="bg-gradient-to-br from-amber-500 to-amber-700" />
            </div>

            <div className="grid lg:grid-cols-3 gap-6">
                <div className="lg:col-span-1 space-y-4">
                    {/* Create Contract */}
                    <div className="rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 p-4 space-y-3">
                        <h3 className="text-sm font-semibold text-slate-700 dark:text-slate-200 flex items-center gap-2">
                            <Plus className="w-4 h-4 text-orange-500" />
                            创建契约
                        </h3>
                        <input type="text" value={consumer} onChange={e => setConsumer(e.target.value)} placeholder="消费者名称" className="w-full text-xs rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 px-3 py-2 outline-none focus:ring-2 focus:ring-orange-500/30" />
                        <input type="text" value={provider} onChange={e => setProvider(e.target.value)} placeholder="提供者名称" className="w-full text-xs rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 px-3 py-2 outline-none focus:ring-2 focus:ring-orange-500/30" />
                        <input type="text" value={version} onChange={e => setVersion(e.target.value)} placeholder="版本号" className="w-full text-xs rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 px-3 py-2 outline-none focus:ring-2 focus:ring-orange-500/30" />
                        <button onClick={handleCreate} disabled={creating || !consumer || !provider} className="w-full flex items-center justify-center gap-2 rounded-lg bg-orange-500 hover:bg-orange-600 text-white text-xs font-medium py-2 transition-colors disabled:opacity-50">
                            {creating ? <RefreshCw className="w-3.5 h-3.5 animate-spin" /> : <Plus className="w-3.5 h-3.5" />}
                            {creating ? '创建中...' : '创建契约'}
                        </button>
                    </div>

                    {/* Verify Panel */}
                    <div className="rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 p-4 space-y-3">
                        <h3 className="text-sm font-semibold text-slate-700 dark:text-slate-200 flex items-center gap-2">
                            <Shield className="w-4 h-4 text-emerald-500" />
                            验证配置
                        </h3>
                        <input type="url" value={providerUrl} onChange={e => setProviderUrl(e.target.value)} placeholder="提供者 URL (例: http://api.example.com)" className="w-full text-xs rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 px-3 py-2 outline-none focus:ring-2 focus:ring-emerald-500/30" />
                        <p className="text-[10px] text-slate-400">设置后可在表格中点击"验证"按钮检查契约兼容性</p>
                    </div>

                    {/* OpenAPI Import Panel */}
                    <div className="rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 overflow-hidden">
                        <button onClick={() => setImportPanelOpen(!importPanelOpen)}
                            className="w-full p-4 flex items-center justify-between hover:bg-slate-50 dark:hover:bg-slate-800/50 transition">
                            <h3 className="text-sm font-semibold text-slate-700 dark:text-slate-200 flex items-center gap-2">
                                <Upload className="w-4 h-4 text-indigo-500" />
                                OpenAPI/Swagger 导入
                            </h3>
                            <ChevronDown className={`w-3.5 h-3.5 text-slate-400 transition-transform ${importPanelOpen ? 'rotate-180' : ''}`} />
                        </button>
                        {importPanelOpen && (
                            <div className="border-t border-slate-200 dark:border-slate-800 p-4 space-y-3">
                                {/* URL fetch */}
                                <div>
                                    <label className="text-[10px] text-slate-500 uppercase font-semibold tracking-wider mb-1 flex items-center gap-1">
                                        <Link2 className="w-3 h-3" /> 从 URL 获取
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
                                                setImportStatus('✅ 已获取 OpenAPI 规范');
                                            } catch {
                                                setImportStatus('❌ 获取失败，请检查 URL');
                                            }
                                            setImporting(false);
                                        }} disabled={importing || !openApiUrl}
                                            className="px-3 py-2 text-xs font-medium text-indigo-600 bg-indigo-50 dark:bg-indigo-900/20 border border-indigo-200 dark:border-indigo-800 rounded-lg hover:bg-indigo-100 transition disabled:opacity-50">
                                            {importing ? <RefreshCw className="w-3 h-3 animate-spin" /> : '获取'}
                                        </button>
                                    </div>
                                </div>

                                {/* JSON paste */}
                                <div>
                                    <label className="text-[10px] text-slate-500 uppercase font-semibold tracking-wider mb-1 flex items-center gap-1">
                                        <FileJson className="w-3 h-3" /> 或粘贴 OpenAPI JSON
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
                                            setImportStatus('❌ 未找到有效的 API 路径');
                                            setImporting(false);
                                            return;
                                        }
                                        const c = await createContract('Auto-Consumer', title, interactions, ver);
                                        setContracts(prev => [...prev, c]);
                                        await load();
                                        setImportStatus(`✅ 已导入 ${interactions.length} 个 API 路径为契约`);
                                        setOpenApiJson('');
                                        setOpenApiUrl('');
                                    } catch {
                                        setImportStatus('❌ 解析失败，请检查 JSON 格式');
                                    }
                                    setImporting(false);
                                }} disabled={importing || !openApiJson.trim()}
                                    className="w-full flex items-center justify-center gap-2 rounded-lg bg-indigo-500 hover:bg-indigo-600 text-white text-xs font-medium py-2 transition-colors disabled:opacity-50">
                                    {importing ? <RefreshCw className="w-3.5 h-3.5 animate-spin" /> : <Upload className="w-3.5 h-3.5" />}
                                    解析并导入契约
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
                        emptyText="暂无契约，请创建一个新的消费者-提供者契约"
                    />
                </div>
            </div>
        </div>
    );
};

export default ContractPage;
