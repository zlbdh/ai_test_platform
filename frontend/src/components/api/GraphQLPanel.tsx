import React, { useState } from 'react';
import { RefreshCw, Clock, Play, ArrowDownUp } from '../icons';
import { API_ENDPOINTS } from '../../config';
import { ensureExecutionContextPayload } from '../../utils/executionContext';

// ============================================================
// GraphQL Panel Component
// ============================================================
const GraphQLPanel: React.FC = () => {
    const [endpoint, setEndpoint] = useState('');
    const [query, setQuery] = useState('{\n  \n}');
    const [variables, setVariables] = useState('{}');
    const [response, setResponse] = useState<any>(null);
    const [schema, setSchema] = useState<any>(null);
    const [loading, setLoading] = useState(false);
    const [activeTab, setActiveTab] = useState<'query' | 'variables' | 'schema'>('query');
    const [responseTime, setResponseTime] = useState(0);

    const executeQuery = async () => {
        if (!endpoint || !query) return;
        setLoading(true);
        try {
            let vars = {};
            try { vars = JSON.parse(variables); } catch { }
            const res = await fetch(API_ENDPOINTS.graphql.execute, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ endpoint, query, variables: vars, ...ensureExecutionContextPayload("GraphQL test suite", { targetUrl: endpoint }) })
            });
            const data = await res.json();
            setResponse(data);
            setResponseTime(data.response_time_ms || 0);
        } catch (e: any) {
            setResponse({ error: e.message });
        } finally {
            setLoading(false);
        }
    };

    const introspect = async () => {
        if (!endpoint) return;
        setLoading(true);
        try {
            const res = await fetch(API_ENDPOINTS.graphql.introspect, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ endpoint, ...ensureExecutionContextPayload("GraphQL test suite", { targetUrl: endpoint }) })
            });
            const data = await res.json();
            setSchema(data.schema);
            setActiveTab('schema');
        } catch (e: any) {
            setResponse({ error: e.message });
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="flex flex-col gap-4 h-full">
            {/* Endpoint Bar */}
            <div className="flex items-center gap-3 p-4 rounded-xl border border-slate-200 dark:border-slate-800 bg-white/50 dark:bg-slate-900/50 backdrop-blur-md">
                <span className="px-3 py-2 text-sm font-bold text-pink-500 bg-pink-500/10 rounded-lg">GQL</span>
                <input
                    type="text"
                    value={endpoint}
                    onChange={(e) => setEndpoint(e.target.value)}
                    placeholder="https://api.example.com/graphql"
                    className="flex-1 px-4 py-2 bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg text-sm outline-none focus:ring-2 focus:ring-pink-500/20 focus:border-pink-500"
                />
                <button onClick={introspect} disabled={loading}
                    className="px-3 py-2 text-sm font-medium text-slate-600 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800 rounded-lg transition flex items-center gap-1.5">
                    <ArrowDownUp className="w-4 h-4" /> Schema
                </button>
                <button onClick={executeQuery} disabled={loading}
                    className="flex items-center gap-2 px-4 py-2 bg-gradient-to-r from-pink-600 to-rose-600 hover:from-pink-500 hover:to-rose-500 text-white rounded-lg font-medium shadow-lg shadow-pink-500/20 active:scale-95 transition-all disabled:opacity-50">
                    {loading ? <RefreshCw className="w-4 h-4 animate-spin" /> : <Play className="w-4 h-4" />}
                    Run
                </button>
            </div>

            <div className="flex-1 grid grid-cols-2 gap-4 min-h-0">
                {/* Query Editor */}
                <div className="flex flex-col rounded-xl border border-slate-200 dark:border-slate-800 bg-white/50 dark:bg-slate-900/50 backdrop-blur-md overflow-hidden">
                    <div className="flex border-b border-slate-200 dark:border-slate-800">
                        {(['query', 'variables', 'schema'] as const).map(tab => (
                            <button key={tab} onClick={() => setActiveTab(tab)}
                                className={`px-4 py-2.5 text-sm font-medium transition border-b-2 ${activeTab === tab
                                    ? 'border-pink-500 text-pink-600 dark:text-pink-400'
                                    : 'border-transparent text-slate-500 hover:text-slate-700'}`}>
                                {tab === 'query' && 'Query'}
                                {tab === 'variables' && 'Variables'}
                                {tab === 'schema' && 'Schema'}
                            </button>
                        ))}
                    </div>
                    <div className="flex-1 overflow-auto p-1">
                        {activeTab === 'query' && (
                            <textarea value={query} onChange={(e) => setQuery(e.target.value)}
                                className="w-full h-full px-4 py-3 bg-transparent text-sm font-mono outline-none resize-none text-slate-700 dark:text-slate-300"
                                spellCheck={false} placeholder="{ users { id name } }" />
                        )}
                        {activeTab === 'variables' && (
                            <textarea value={variables} onChange={(e) => setVariables(e.target.value)}
                                className="w-full h-full px-4 py-3 bg-transparent text-sm font-mono outline-none resize-none text-slate-700 dark:text-slate-300"
                                spellCheck={false} placeholder='{ "userId": 1 }' />
                        )}
                        {activeTab === 'schema' && (
                            <pre className="px-4 py-3 text-xs font-mono text-slate-600 dark:text-slate-400 whitespace-pre-wrap">
                                {schema ? JSON.stringify(schema, null, 2) : "Click Schema to retrieve introspection results"}
                            </pre>
                        )}
                    </div>
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
                        {response ? JSON.stringify(response, null, 2) : "Run a query to view its response..."}
                    </pre>
                </div>
            </div>
        </div>
    );
};

export default GraphQLPanel;
