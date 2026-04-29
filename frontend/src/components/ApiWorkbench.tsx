import React, { useState, useEffect } from 'react';
import {
    Send, Plus, Trash2, Save, ChevronRight, ChevronDown, Folder, FileJson, Check, X, Clock, AlertCircle, RefreshCw, History, Database, Settings
} from './icons';
import { API_ENDPOINTS } from '../config';
import type {
    ProtocolType, RequestItem, Collection, Environment, RequestResult,
} from './api/types';
import { METHOD_COLORS, PROTOCOL_CONFIG } from './api/types';
import GraphQLPanel from './api/GraphQLPanel';
import WebSocketPanel from './api/WebSocketPanel';
import GrpcPanel from './api/GrpcPanel';
import ExecutionBatchBanner from './ExecutionBatchBanner';
import { ensureExecutionContextPayload } from '../utils/executionContext';

// ============================================================
// HTTP Panel Component (original ApiWorkbench logic)
// ============================================================
const HttpPanel: React.FC = () => {
    const [collections, setCollections] = useState<Collection[]>([]);
    const [environments, setEnvironments] = useState<Environment[]>([]);
    const [activeEnvId, setActiveEnvId] = useState<string | null>(null);
    const [envPanelOpen, setEnvPanelOpen] = useState(false);
    const [requestHistory, setRequestHistory] = useState<Array<{ method: string; url: string; status: number; time: number; ts: number }>>([]);
    const [showHistory, setShowHistory] = useState(false);
    const [activeCollectionId, setActiveCollectionId] = useState<string | null>(null);
    const [activeRequestId, setActiveRequestId] = useState<string | null>(null);
    const [expandedCollections, setExpandedCollections] = useState<Set<string>>(new Set());
    const [currentRequest, setCurrentRequest] = useState<RequestItem | null>(null);
    const [result, setResult] = useState<RequestResult | null>(null);
    const [isLoading, setIsLoading] = useState(false);
    const [activeTab, setActiveTab] = useState<'params' | 'headers' | 'body' | 'assertions'>('params');
    const [responseTab, setResponseTab] = useState<'body' | 'headers' | 'assertions'>('body');

    useEffect(() => {
        fetchCollections();
        fetchEnvironments();
    }, []);

    const fetchCollections = async () => {
        try { const res = await fetch(API_ENDPOINTS.workbench.collections); const data = await res.json(); setCollections(data.collections || []); } catch (e) { console.error('Failed:', e); }
    };
    const fetchEnvironments = async () => {
        try { const res = await fetch(API_ENDPOINTS.workbench.environments); const data = await res.json(); setEnvironments(data.environments || []); } catch (e) { console.error('Failed:', e); }
    };
    const fetchCollectionDetails = async (collectionId: string) => {
        try { const res = await fetch(API_ENDPOINTS.workbench.collection(collectionId)); const data = await res.json(); setCollections(prev => prev.map(c => c.id === collectionId ? { ...c, ...data.collection } : c)); } catch (e) { console.error('Failed:', e); }
    };
    const createCollection = async () => {
        const name = prompt('输入集合名称:'); if (!name) return;
        try { const res = await fetch(API_ENDPOINTS.workbench.collections, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ name, description: '' }) }); if (res.ok) fetchCollections(); } catch (e) { console.error('Failed:', e); }
    };
    const deleteCollection = async (collectionId: string) => {
        if (!confirm('确定删除这个集合?')) return;
        try { await fetch(API_ENDPOINTS.workbench.collection(collectionId), { method: 'DELETE' }); fetchCollections(); if (activeCollectionId === collectionId) { setActiveCollectionId(null); setActiveRequestId(null); setCurrentRequest(null); } } catch (e) { console.error('Failed:', e); }
    };
    const addRequest = async (collectionId: string) => {
        try { const res = await fetch(API_ENDPOINTS.workbench.collectionRequests(collectionId), { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ name: 'New Request', method: 'GET', url: '' }) }); if (res.ok) fetchCollectionDetails(collectionId); } catch (e) { console.error('Failed:', e); }
    };
    const saveRequest = async () => {
        if (!activeCollectionId || !activeRequestId || !currentRequest) return;
        try { await fetch(API_ENDPOINTS.workbench.request(activeCollectionId, activeRequestId), { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(currentRequest) }); fetchCollectionDetails(activeCollectionId); } catch (e) { console.error('Failed:', e); }
    };
    const deleteRequest = async (collectionId: string, requestId: string) => {
        if (!confirm('确定删除这个请求?')) return;
        try { await fetch(API_ENDPOINTS.workbench.request(collectionId, requestId), { method: 'DELETE' }); fetchCollectionDetails(collectionId); if (activeRequestId === requestId) { setActiveRequestId(null); setCurrentRequest(null); } } catch (e) { console.error('Failed:', e); }
    };
    const executeRequest = async () => {
        if (!currentRequest) return;
        setIsLoading(true); setResult(null);
        try {
            // Resolve environment variables in URL
            const activeEnv = environments.find(e => e.id === activeEnvId);
            let resolvedRequest = { ...currentRequest };
            if (activeEnv) {
                let url = resolvedRequest.url;
                Object.entries(activeEnv.variables).forEach(([k, v]) => {
                    // eslint-disable-next-line no-useless-escape
                    url = url.replace(new RegExp(`\{\{${k}\}\}`, 'g'), v);
                });
                resolvedRequest = { ...resolvedRequest, url };
            }
            const res = await fetch(API_ENDPOINTS.workbench.execute, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    request: resolvedRequest,
                    extra_vars: activeEnv?.variables || {},
                    ...ensureExecutionContextPayload('API 专项测试', { targetUrl: resolvedRequest.url }),
                }),
            });
            const data = await res.json();
            setResult(data.result);
            setResponseTab('body');
            // Track history
            setRequestHistory(prev => [{ method: currentRequest.method, url: currentRequest.url, status: data.result?.status_code || 0, time: data.result?.response_time_ms || 0, ts: Date.now() }, ...prev].slice(0, 20));
        } catch (e) { console.error('Failed:', e); } finally { setIsLoading(false); }
    };
    const selectRequest = (collection: Collection, request: RequestItem) => {
        setActiveCollectionId(collection.id); setActiveRequestId(request.id); setCurrentRequest({ ...request }); setResult(null);
    };
    const toggleCollection = (collectionId: string) => {
        const n = new Set(expandedCollections); if (n.has(collectionId)) n.delete(collectionId); else { n.add(collectionId); fetchCollectionDetails(collectionId); } setExpandedCollections(n);
    };
    const updateKeyValue = (type: 'headers' | 'params', index: number, field: 'key' | 'value', value: string) => {
        if (!currentRequest) return; const entries = Object.entries(currentRequest[type]); if (index < entries.length) { const [oldKey, oldValue] = entries[index]; const newEntries = [...entries]; if (field === 'key') newEntries[index] = [value, oldValue]; else newEntries[index] = [oldKey, value]; setCurrentRequest({ ...currentRequest, [type]: Object.fromEntries(newEntries) }); }
    };
    const addKeyValue = (type: 'headers' | 'params') => {
        if (!currentRequest) return; setCurrentRequest({ ...currentRequest, [type]: { ...currentRequest[type], '': '' } });
    };
    const removeKeyValue = (type: 'headers' | 'params', key: string) => {
        if (!currentRequest) return; const newObj = { ...currentRequest[type] }; delete newObj[key]; setCurrentRequest({ ...currentRequest, [type]: newObj });
    };
    const formatJson = (str: string): string => { try { return JSON.stringify(JSON.parse(str), null, 2); } catch { return str; } };

    return (
        <div className="flex h-full gap-4">
            {/* Left Sidebar - Collections */}
            <div className="w-72 flex-shrink-0 flex flex-col rounded-xl border border-slate-200 dark:border-slate-800 bg-white/50 dark:bg-slate-900/50 backdrop-blur-md overflow-hidden">
                <div className="p-4 border-b border-slate-200 dark:border-slate-800 flex items-center justify-between">
                    <h3 className="font-bold text-slate-900 dark:text-white flex items-center gap-2">
                        <Folder className="w-4 h-4 text-indigo-500" /> 集合
                    </h3>
                    <button onClick={createCollection} className="p-1.5 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-800 text-slate-500 hover:text-indigo-500 transition">
                        <Plus className="w-4 h-4" />
                    </button>
                </div>
                <div className="flex-1 overflow-y-auto p-2 space-y-1">
                    {collections.map(coll => (
                        <div key={coll.id}>
                            <div className={`flex items-center gap-2 px-3 py-2 rounded-lg cursor-pointer transition group ${activeCollectionId === coll.id ? 'bg-indigo-50 dark:bg-indigo-500/10 text-indigo-600 dark:text-indigo-400' : 'hover:bg-slate-100 dark:hover:bg-slate-800 text-slate-700 dark:text-slate-300'}`}
                                onClick={() => toggleCollection(coll.id)}>
                                {expandedCollections.has(coll.id) ? <ChevronDown className="w-4 h-4 flex-shrink-0" /> : <ChevronRight className="w-4 h-4 flex-shrink-0" />}
                                <span className="flex-1 truncate text-sm font-medium">{coll.name}</span>
                                <span className="text-xs text-slate-400">{coll.request_count || 0}</span>
                                <button onClick={(e) => { e.stopPropagation(); addRequest(coll.id); }} className="opacity-0 group-hover:opacity-100 p-1 hover:bg-slate-200 dark:hover:bg-slate-700 rounded transition"><Plus className="w-3 h-3" /></button>
                                <button onClick={(e) => { e.stopPropagation(); deleteCollection(coll.id); }} className="opacity-0 group-hover:opacity-100 p-1 hover:bg-red-100 dark:hover:bg-red-900/30 text-red-500 rounded transition"><Trash2 className="w-3 h-3" /></button>
                            </div>
                            {expandedCollections.has(coll.id) && coll.requests && (
                                <div className="ml-4 mt-1 space-y-1">
                                    {coll.requests.map(req => (
                                        <div key={req.id} onClick={() => selectRequest(coll, req)}
                                            className={`flex items-center gap-2 px-3 py-2 rounded-lg cursor-pointer transition group ${activeRequestId === req.id ? 'bg-slate-100 dark:bg-slate-800' : 'hover:bg-slate-50 dark:hover:bg-slate-800/50'}`}>
                                            <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded ${METHOD_COLORS[req.method] || 'text-slate-500 bg-slate-500/10'}`}>{req.method}</span>
                                            <span className="flex-1 truncate text-sm text-slate-600 dark:text-slate-400">{req.name}</span>
                                            <button onClick={(e) => { e.stopPropagation(); deleteRequest(coll.id, req.id); }} className="opacity-0 group-hover:opacity-100 p-1 hover:bg-red-100 dark:hover:bg-red-900/30 text-red-500 rounded transition"><Trash2 className="w-3 h-3" /></button>
                                        </div>
                                    ))}
                                </div>
                            )}
                        </div>
                    ))}
                    {collections.length === 0 && (
                        <div className="text-center py-8 text-slate-400">
                            <FileJson className="w-8 h-8 mx-auto mb-2 opacity-50" />
                            <p className="text-sm">暂无集合</p>
                            <button onClick={createCollection} className="mt-2 text-xs text-indigo-500 hover:underline">创建第一个集合</button>
                        </div>
                    )}
                </div>

                {/* Environment Manager */}
                <div className="rounded-xl border border-slate-200 dark:border-slate-800 bg-white/50 dark:bg-slate-900/50 backdrop-blur-md overflow-hidden">
                    <button onClick={() => setEnvPanelOpen(!envPanelOpen)}
                        className="w-full p-3 flex items-center justify-between hover:bg-slate-50 dark:hover:bg-slate-800 transition">
                        <span className="flex items-center gap-2 text-sm font-bold text-slate-700 dark:text-white">
                            <Database className="w-4 h-4 text-emerald-500" /> 环境变量
                        </span>
                        <Settings className={`w-3.5 h-3.5 text-slate-400 transition-transform ${envPanelOpen ? 'rotate-90' : ''}`} />
                    </button>
                    {envPanelOpen && (
                        <div className="border-t border-slate-200 dark:border-slate-800 p-3 space-y-2">
                            {/* Env Selector */}
                            <div className="flex gap-1 flex-wrap">
                                {environments.map(env => (
                                    <button key={env.id} onClick={() => setActiveEnvId(activeEnvId === env.id ? null : env.id)}
                                        className={`text-[11px] px-2 py-1 rounded-lg border transition-all ${activeEnvId === env.id
                                            ? 'bg-emerald-50 dark:bg-emerald-500/10 border-emerald-300 dark:border-emerald-500/30 text-emerald-600 dark:text-emerald-400'
                                            : 'border-slate-200 dark:border-slate-700 text-slate-500 hover:border-emerald-300'}`}>
                                        {env.name}
                                    </button>
                                ))}
                                {environments.length === 0 && <span className="text-[11px] text-slate-400">暂无环境</span>}
                            </div>
                            {/* Active Env Variables */}
                            {activeEnvId && (() => {
                                const env = environments.find(e => e.id === activeEnvId);
                                if (!env) return null;
                                return (
                                    <div className="space-y-1">
                                        {Object.entries(env.variables).map(([k, v]) => (
                                            <div key={k} className="flex items-center gap-1 text-[11px]">
                                                <span className="font-mono text-emerald-600 dark:text-emerald-400 bg-emerald-50 dark:bg-emerald-900/20 px-1.5 py-0.5 rounded">{`{{${k}}}`}</span>
                                                <span className="text-slate-400">=</span>
                                                <span className="font-mono text-slate-600 dark:text-slate-400 truncate">{v}</span>
                                            </div>
                                        ))}
                                        {Object.keys(env.variables).length === 0 && <span className="text-[10px] text-slate-400">无变量</span>}
                                    </div>
                                );
                            })()}
                        </div>
                    )}
                </div>

                {/* Request History */}
                <div className="rounded-xl border border-slate-200 dark:border-slate-800 bg-white/50 dark:bg-slate-900/50 backdrop-blur-md overflow-hidden">
                    <button onClick={() => setShowHistory(!showHistory)}
                        className="w-full p-3 flex items-center justify-between hover:bg-slate-50 dark:hover:bg-slate-800 transition">
                        <span className="flex items-center gap-2 text-sm font-bold text-slate-700 dark:text-white">
                            <History className="w-4 h-4 text-amber-500" /> 请求历史
                            {requestHistory.length > 0 && <span className="text-[10px] bg-amber-100 dark:bg-amber-900/30 text-amber-600 px-1.5 rounded-full">{requestHistory.length}</span>}
                        </span>
                        <ChevronDown className={`w-3.5 h-3.5 text-slate-400 transition-transform ${showHistory ? 'rotate-180' : ''}`} />
                    </button>
                    {showHistory && requestHistory.length > 0 && (
                        <div className="border-t border-slate-200 dark:border-slate-800 max-h-48 overflow-y-auto">
                            {requestHistory.map((h, i) => (
                                <div key={i} className="px-3 py-2 border-b border-slate-100 dark:border-slate-800/50 hover:bg-slate-50 dark:hover:bg-slate-800/50 transition text-[11px]">
                                    <div className="flex items-center gap-2">
                                        <span className={`font-bold ${METHOD_COLORS[h.method]?.split(' ')[0] || 'text-slate-500'}`}>{h.method}</span>
                                        <span className="text-slate-500 truncate flex-1 font-mono">{h.url}</span>
                                        <span className={`font-mono ${h.status >= 200 && h.status < 300 ? 'text-green-500' : 'text-red-500'}`}>{h.status}</span>
                                    </div>
                                    <div className="flex items-center gap-2 text-[10px] text-slate-400 mt-0.5">
                                        <span>{h.time.toFixed(0)}ms</span>
                                        <span>{new Date(h.ts).toLocaleTimeString('zh-CN')}</span>
                                    </div>
                                </div>
                            ))}
                        </div>
                    )}
                </div>
            </div>

            {/* Main Content */}
            <div className="flex-1 flex flex-col gap-4 min-w-0">
                {currentRequest ? (
                    <>
                        {/* Request Editor */}
                        <div className="rounded-xl border border-slate-200 dark:border-slate-800 bg-white/50 dark:bg-slate-900/50 backdrop-blur-md overflow-hidden">
                            <div className="p-4 border-b border-slate-200 dark:border-slate-800 flex items-center gap-3">
                                <select value={currentRequest.method} onChange={(e) => setCurrentRequest({ ...currentRequest, method: e.target.value })}
                                    className={`px-3 py-2 rounded-lg font-bold text-sm border-0 outline-none cursor-pointer ${METHOD_COLORS[currentRequest.method] || 'bg-slate-100'}`}>
                                    {['GET', 'POST', 'PUT', 'PATCH', 'DELETE'].map(m => <option key={m} value={m}>{m}</option>)}
                                </select>
                                <input type="text" value={currentRequest.url} onChange={(e) => setCurrentRequest({ ...currentRequest, url: e.target.value })}
                                    placeholder="输入请求 URL..." className="flex-1 px-4 py-2 bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg text-sm outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500" />
                                <button onClick={saveRequest} className="p-2 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-800 text-slate-500 transition" title="保存"><Save className="w-5 h-5" /></button>
                                <button onClick={executeRequest} disabled={isLoading}
                                    className="flex items-center gap-2 px-4 py-2 bg-gradient-to-r from-indigo-600 to-violet-600 hover:from-indigo-500 hover:to-violet-500 text-white rounded-lg font-medium shadow-lg shadow-indigo-500/20 active:scale-95 transition-all disabled:opacity-50">
                                    {isLoading ? <RefreshCw className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />} 发送
                                </button>
                            </div>
                            <div className="px-4 py-2 border-b border-slate-200 dark:border-slate-800">
                                <input type="text" value={currentRequest.name} onChange={(e) => setCurrentRequest({ ...currentRequest, name: e.target.value })}
                                    className="text-lg font-semibold bg-transparent border-0 outline-none w-full text-slate-900 dark:text-white" placeholder="请求名称" />
                            </div>
                            <div className="flex border-b border-slate-200 dark:border-slate-800">
                                {(['params', 'headers', 'body', 'assertions'] as const).map(tab => (
                                    <button key={tab} onClick={() => setActiveTab(tab)}
                                        className={`px-4 py-3 text-sm font-medium transition border-b-2 ${activeTab === tab ? 'border-indigo-500 text-indigo-600 dark:text-indigo-400' : 'border-transparent text-slate-500 hover:text-slate-700 dark:hover:text-slate-300'}`}>
                                        {tab === 'params' && 'Params'}{tab === 'headers' && 'Headers'}{tab === 'body' && 'Body'}{tab === 'assertions' && 'Assertions'}
                                        {tab === 'params' && Object.keys(currentRequest.params).length > 0 && <span className="ml-1 text-xs bg-slate-200 dark:bg-slate-700 px-1.5 rounded">{Object.keys(currentRequest.params).length}</span>}
                                        {tab === 'headers' && Object.keys(currentRequest.headers).length > 0 && <span className="ml-1 text-xs bg-slate-200 dark:bg-slate-700 px-1.5 rounded">{Object.keys(currentRequest.headers).length}</span>}
                                    </button>
                                ))}
                            </div>
                            <div className="p-4 max-h-64 overflow-y-auto">
                                {activeTab === 'params' && (
                                    <div className="space-y-2">
                                        {Object.entries(currentRequest.params).map(([key, value], idx) => (
                                            <div key={idx} className="flex items-center gap-2">
                                                <input type="text" value={key} onChange={(e) => updateKeyValue('params', idx, 'key', e.target.value)} placeholder="Key" className="flex-1 px-3 py-2 bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg text-sm outline-none" />
                                                <input type="text" value={value} onChange={(e) => updateKeyValue('params', idx, 'value', e.target.value)} placeholder="Value" className="flex-1 px-3 py-2 bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg text-sm outline-none" />
                                                <button onClick={() => removeKeyValue('params', key)} className="p-2 text-red-500 hover:bg-red-50 dark:hover:bg-red-900/20 rounded-lg transition"><Trash2 className="w-4 h-4" /></button>
                                            </div>
                                        ))}
                                        <button onClick={() => addKeyValue('params')} className="flex items-center gap-1 text-sm text-indigo-500 hover:underline"><Plus className="w-4 h-4" /> 添加参数</button>
                                    </div>
                                )}
                                {activeTab === 'headers' && (
                                    <div className="space-y-2">
                                        {Object.entries(currentRequest.headers).map(([key, value], idx) => (
                                            <div key={idx} className="flex items-center gap-2">
                                                <input type="text" value={key} onChange={(e) => updateKeyValue('headers', idx, 'key', e.target.value)} placeholder="Header Name" className="flex-1 px-3 py-2 bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg text-sm outline-none" />
                                                <input type="text" value={value} onChange={(e) => updateKeyValue('headers', idx, 'value', e.target.value)} placeholder="Value" className="flex-1 px-3 py-2 bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg text-sm outline-none" />
                                                <button onClick={() => removeKeyValue('headers', key)} className="p-2 text-red-500 hover:bg-red-50 dark:hover:bg-red-900/20 rounded-lg transition"><Trash2 className="w-4 h-4" /></button>
                                            </div>
                                        ))}
                                        <button onClick={() => addKeyValue('headers')} className="flex items-center gap-1 text-sm text-indigo-500 hover:underline"><Plus className="w-4 h-4" /> 添加 Header</button>
                                    </div>
                                )}
                                {activeTab === 'body' && (
                                    <div className="space-y-2">
                                        <div className="flex items-center gap-2 mb-2">
                                            <select value={currentRequest.body_type} onChange={(e) => setCurrentRequest({ ...currentRequest, body_type: e.target.value })}
                                                className="px-3 py-1.5 bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg text-sm outline-none">
                                                <option value="json">JSON</option><option value="form">Form Data</option><option value="raw">Raw</option>
                                            </select>
                                        </div>
                                        <textarea value={currentRequest.body} onChange={(e) => setCurrentRequest({ ...currentRequest, body: e.target.value })}
                                            placeholder={currentRequest.body_type === 'json' ? '{\n  "key": "value"\n}' : 'Request body...'}
                                            className="w-full h-40 px-4 py-3 bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg text-sm font-mono outline-none resize-none" />
                                    </div>
                                )}
                                {activeTab === 'assertions' && (
                                    <div className="text-sm text-slate-500">
                                        <p>断言配置功能开发中...</p>
                                        <p className="mt-2 text-xs">支持的断言类型: status, json_path, header, response_time</p>
                                    </div>
                                )}
                            </div>
                        </div>

                        {/* Response Panel */}
                        <div className="flex-1 rounded-xl border border-slate-200 dark:border-slate-800 bg-white/50 dark:bg-slate-900/50 backdrop-blur-md overflow-hidden flex flex-col min-h-0">
                            <div className="p-4 border-b border-slate-200 dark:border-slate-800 flex items-center justify-between">
                                <h3 className="font-bold text-slate-900 dark:text-white">响应</h3>
                                {result && (
                                    <div className="flex items-center gap-4 text-sm">
                                        <span className={`font-mono font-bold ${result.status_code >= 200 && result.status_code < 300 ? 'text-green-500' : result.status_code >= 400 ? 'text-red-500' : 'text-yellow-500'}`}>{result.status_code}</span>
                                        <span className="text-slate-500 flex items-center gap-1"><Clock className="w-3 h-3" />{result.response_time_ms.toFixed(0)}ms</span>
                                        {result.assertions_passed + result.assertions_failed > 0 && (
                                            <span className={`flex items-center gap-1 ${result.assertions_failed > 0 ? 'text-red-500' : 'text-green-500'}`}>
                                                {result.assertions_failed > 0 ? <X className="w-3 h-3" /> : <Check className="w-3 h-3" />} {result.assertions_passed}/{result.assertions_passed + result.assertions_failed}
                                            </span>
                                        )}
                                    </div>
                                )}
                            </div>
                            {result && (
                                <div className="flex border-b border-slate-200 dark:border-slate-800">
                                    {(['body', 'headers', 'assertions'] as const).map(tab => (
                                        <button key={tab} onClick={() => setResponseTab(tab)}
                                            className={`px-4 py-2 text-sm font-medium transition border-b-2 ${responseTab === tab ? 'border-indigo-500 text-indigo-600 dark:text-indigo-400' : 'border-transparent text-slate-500 hover:text-slate-700 dark:hover:text-slate-300'}`}>
                                            {tab === 'body' && 'Body'}{tab === 'headers' && 'Headers'}{tab === 'assertions' && 'Assertions'}
                                        </button>
                                    ))}
                                </div>
                            )}
                            <div className="flex-1 overflow-auto p-4">
                                {isLoading ? (
                                    <div className="flex items-center justify-center h-full text-slate-400"><RefreshCw className="w-6 h-6 animate-spin mr-2" />发送请求中...</div>
                                ) : result ? (
                                    <>
                                        {result.error ? (
                                            <div className="p-4 bg-red-50 dark:bg-red-900/10 border border-red-200 dark:border-red-900/50 rounded-lg text-red-600 dark:text-red-400"><AlertCircle className="w-5 h-5 inline mr-2" />{result.error}</div>
                                        ) : (
                                            <>
                                                {responseTab === 'body' && <pre className="text-sm font-mono text-slate-700 dark:text-slate-300 whitespace-pre-wrap break-all">{formatJson(result.response_body)}</pre>}
                                                {responseTab === 'headers' && (
                                                    <div className="space-y-1">
                                                        {Object.entries(result.response_headers).map(([k, v]) => (
                                                            <div key={k} className="flex text-sm"><span className="font-medium text-slate-600 dark:text-slate-400 w-48 flex-shrink-0">{k}:</span><span className="text-slate-800 dark:text-slate-200 break-all">{v}</span></div>
                                                        ))}
                                                    </div>
                                                )}
                                                {responseTab === 'assertions' && (
                                                    <div className="space-y-2">
                                                        {result.assertion_details.length === 0 ? <p className="text-slate-400 text-sm">无断言配置</p> : (
                                                            result.assertion_details.map((a, i) => (
                                                                <div key={i} className={`p-3 rounded-lg border ${a.passed ? 'bg-green-50 dark:bg-green-900/10 border-green-200 dark:border-green-900/50' : 'bg-red-50 dark:bg-red-900/10 border-red-200 dark:border-red-900/50'}`}>
                                                                    <div className="flex items-center gap-2">{a.passed ? <Check className="w-4 h-4 text-green-500" /> : <X className="w-4 h-4 text-red-500" />}<span className="font-medium text-sm">{a.type}</span>{a.path && <span className="text-xs text-slate-500">({a.path})</span>}</div>
                                                                    <p className="text-xs text-slate-500 mt-1">{a.message}</p>
                                                                </div>
                                                            ))
                                                        )}
                                                    </div>
                                                )}
                                            </>
                                        )}
                                    </>
                                ) : (
                                    <div className="flex flex-col items-center justify-center h-full text-slate-400"><Send className="w-12 h-12 mb-4 opacity-30" /><p>点击发送按钮执行请求</p></div>
                                )}
                            </div>
                        </div>
                    </>
                ) : (
                    <div className="flex-1 flex items-center justify-center rounded-xl border border-slate-200 dark:border-slate-800 bg-white/50 dark:bg-slate-900/50 backdrop-blur-md">
                        <div className="text-center text-slate-400">
                            <FileJson className="w-16 h-16 mx-auto mb-4 opacity-30" />
                            <p className="text-lg font-medium">选择或创建一个请求</p>
                            <p className="text-sm mt-2">从左侧面板选择一个现有请求，或创建新的 API 集合</p>
                        </div>
                    </div>
                )}
            </div>
        </div>
    );
};

// ============================================================
// Main ApiWorkbench Component with Protocol Switching
// ============================================================
const ApiWorkbench: React.FC = () => {
    const [activeProtocol, setActiveProtocol] = useState<ProtocolType>('http');

    return (
        <div className="flex flex-col h-full gap-4 animate-in fade-in duration-500">
            <ExecutionBatchBanner standaloneHint="在这里执行的 HTTP / GraphQL / WebSocket / gRPC 测试会作为独立记录保存。" />

            {/* Protocol Tabs */}
            <div className="flex items-center gap-1 p-1 rounded-xl bg-slate-100 dark:bg-slate-800/50 w-fit">
                {(Object.entries(PROTOCOL_CONFIG) as [ProtocolType, typeof PROTOCOL_CONFIG[ProtocolType]][]).map(([key, config]) => (
                    <button
                        key={key}
                        onClick={() => setActiveProtocol(key)}
                        className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-all duration-200 ${activeProtocol === key
                            ? `${config.color} border shadow-sm`
                            : 'text-slate-500 hover:text-slate-700 dark:hover:text-slate-300 hover:bg-white/50 dark:hover:bg-slate-700/50 border border-transparent'
                            }`}
                    >
                        {config.icon}
                        {config.label}
                    </button>
                ))}
            </div>

            {/* Protocol Panel */}
            <div className="flex-1 min-h-0">
                {activeProtocol === 'http' && <HttpPanel />}
                {activeProtocol === 'graphql' && <GraphQLPanel />}
                {activeProtocol === 'websocket' && <WebSocketPanel />}
                {activeProtocol === 'grpc' && <GrpcPanel />}
            </div>
        </div>
    );
};

export default ApiWorkbench;
