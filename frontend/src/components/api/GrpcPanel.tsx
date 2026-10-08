import React, { useState } from 'react';
import { RefreshCw, Play, Clock, ArrowDownUp } from '../icons';
import { API_ENDPOINTS } from '../../config';
import { ensureExecutionContextPayload } from '../../utils/executionContext';

// ============================================================
// gRPC Panel Component
// ============================================================
const GrpcPanel: React.FC = () => {
    const [host, setHost] = useState('');
    const [port, setPort] = useState('50051');
    const [service, setService] = useState('');
    const [method, setMethod] = useState('');
    const [payload, setPayload] = useState('{}');
    const [response, setResponse] = useState<any>(null);
    const [services, setServices] = useState<string[]>([]);
    const [loading, setLoading] = useState(false);
    const [responseTime, setResponseTime] = useState(0);

    const listServices = async () => {
        if (!host) return;
        setLoading(true);
        try {
            const res = await fetch(API_ENDPOINTS.grpc.services, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ host, port: parseInt(port), ...ensureExecutionContextPayload("gRPC test suite", { targetUrl: `${host}:${port}` }) })
            });
            const data = await res.json();
            setServices(data.services || []);
        } catch (e: any) {
            setResponse({ error: e.message });
        } finally {
            setLoading(false);
        }
    };

    const callMethod = async () => {
        if (!host || !service || !method) return;
        setLoading(true);
        try {
            let data = {};
            try { data = JSON.parse(payload); } catch { }
            const res = await fetch(API_ENDPOINTS.grpc.call, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ host, port: parseInt(port), service, method, data, ...ensureExecutionContextPayload("gRPC test suite", { targetUrl: `${host}:${port}` }) })
            });
            const result = await res.json();
            setResponse(result);
            setResponseTime(result.response_time_ms || 0);
        } catch (e: any) {
            setResponse({ error: e.message });
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="flex flex-col gap-4 h-full">
            {/* Address Bar */}
            <div className="flex items-center gap-3 p-4 rounded-xl border border-slate-200 dark:border-slate-800 bg-white/50 dark:bg-slate-900/50 backdrop-blur-md">
                <span className="px-3 py-2 text-sm font-bold text-orange-500 bg-orange-500/10 rounded-lg">gRPC</span>
                <input type="text" value={host} onChange={(e) => setHost(e.target.value)}
                    placeholder="localhost" className="w-48 px-4 py-2 bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg text-sm outline-none focus:ring-2 focus:ring-orange-500/20" />
                <span className="text-slate-400">:</span>
                <input type="text" value={port} onChange={(e) => setPort(e.target.value)}
                    className="w-20 px-3 py-2 bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg text-sm outline-none text-center" />
                <button onClick={listServices} disabled={loading}
                    className="px-3 py-2 text-sm text-slate-600 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800 rounded-lg transition flex items-center gap-1.5">
                    <ArrowDownUp className="w-4 h-4" /> Reflection
                </button>
                <button onClick={callMethod} disabled={loading}
                    className="flex items-center gap-2 px-4 py-2 bg-gradient-to-r from-orange-600 to-amber-600 hover:from-orange-500 hover:to-amber-500 text-white rounded-lg font-medium shadow-lg shadow-orange-500/20 active:scale-95 transition-all disabled:opacity-50">
                    {loading ? <RefreshCw className="w-4 h-4 animate-spin" /> : <Play className="w-4 h-4" />}
                    Invoke
                </button>
            </div>

            {/* Service / Method Selector */}
            <div className="flex items-center gap-3 px-4">
                <div className="flex-1">
                    <label className="text-xs text-slate-500 mb-1 block">Service</label>
                    {services.length > 0 ? (
                        <select value={service} onChange={(e) => setService(e.target.value)}
                            className="w-full px-3 py-2 bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg text-sm outline-none">
                            <option value="">Select a service...</option>
                            {services.map(s => <option key={s} value={s}>{s}</option>)}
                        </select>
                    ) : (
                        <input type="text" value={service} onChange={(e) => setService(e.target.value)}
                            placeholder="com.example.UserService"
                            className="w-full px-3 py-2 bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg text-sm outline-none" />
                    )}
                </div>
                <div className="flex-1">
                    <label className="text-xs text-slate-500 mb-1 block">Method</label>
                    <input type="text" value={method} onChange={(e) => setMethod(e.target.value)}
                        placeholder="GetUser"
                        className="w-full px-3 py-2 bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg text-sm outline-none" />
                </div>
            </div>

            <div className="flex-1 grid grid-cols-2 gap-4 min-h-0">
                {/* Request Payload */}
                <div className="flex flex-col rounded-xl border border-slate-200 dark:border-slate-800 bg-white/50 dark:bg-slate-900/50 backdrop-blur-md overflow-hidden">
                    <div className="p-3 border-b border-slate-200 dark:border-slate-800">
                        <span className="text-sm font-bold text-slate-700 dark:text-white">Request Payload</span>
                    </div>
                    <textarea value={payload} onChange={(e) => setPayload(e.target.value)}
                        className="flex-1 px-4 py-3 bg-transparent text-sm font-mono outline-none resize-none text-slate-700 dark:text-slate-300"
                        spellCheck={false} placeholder='{ "user_id": 1 }' />
                </div>

                {/* Response */}
                <div className="flex flex-col rounded-xl border border-slate-200 dark:border-slate-800 bg-white/50 dark:bg-slate-900/50 backdrop-blur-md overflow-hidden">
                    <div className="p-3 border-b border-slate-200 dark:border-slate-800 flex items-center justify-between">
                        <span className="text-sm font-bold text-slate-700 dark:text-white">Response</span>
                        {responseTime > 0 && (
                            <span className="text-xs text-slate-500 flex items-center gap-1">
                                <Clock className="w-3 h-3" /> {responseTime}ms
                            </span>
                        )}
                    </div>
                    <pre className="flex-1 overflow-auto px-4 py-3 text-sm font-mono text-slate-700 dark:text-slate-300 whitespace-pre-wrap">
                        {response ? JSON.stringify(response, null, 2) : "Invoke a method to view its response..."}
                    </pre>
                </div>
            </div>
        </div>
    );
};

export default GrpcPanel;
