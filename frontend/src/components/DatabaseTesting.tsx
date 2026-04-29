import React, { useState, useEffect, useMemo } from 'react';
import {
    Database, Play, Table, Download, Camera, GitCompare,
    RefreshCw, AlertCircle, Check, Copy, Trash2, Settings, X, Loader2,
} from './icons';
import { API_ENDPOINTS } from '../config';
import { API_BASE_URL } from '../config';
import ExecutionBatchBanner from './ExecutionBatchBanner';
import { ensureExecutionContextPayload } from '../utils/executionContext';

// ── Lightweight SQL Syntax Highlighter ──
const SQL_KEYWORDS = new Set([
    'SELECT', 'FROM', 'WHERE', 'AND', 'OR', 'NOT', 'IN', 'EXISTS',
    'INSERT', 'INTO', 'VALUES', 'UPDATE', 'SET', 'DELETE', 'DROP',
    'CREATE', 'ALTER', 'TABLE', 'INDEX', 'VIEW', 'DATABASE',
    'JOIN', 'LEFT', 'RIGHT', 'INNER', 'OUTER', 'CROSS', 'ON',
    'GROUP', 'BY', 'ORDER', 'ASC', 'DESC', 'HAVING', 'LIMIT',
    'OFFSET', 'UNION', 'ALL', 'DISTINCT', 'AS', 'CASE', 'WHEN',
    'THEN', 'ELSE', 'END', 'IS', 'NULL', 'LIKE', 'BETWEEN',
    'PRIMARY', 'KEY', 'FOREIGN', 'REFERENCES', 'CONSTRAINT',
    'DEFAULT', 'CHECK', 'UNIQUE', 'IF', 'BEGIN', 'COMMIT',
    'ROLLBACK', 'TRANSACTION', 'PRAGMA', 'EXPLAIN', 'ANALYZE',
    'WITH', 'RECURSIVE', 'REPLACE', 'TRIGGER', 'CASCADE',
    'INTEGER', 'TEXT', 'REAL', 'BLOB', 'VARCHAR', 'BOOLEAN',
    'TRUE', 'FALSE', 'COUNT', 'SUM', 'AVG', 'MIN', 'MAX',
]);

const SQL_FUNCTIONS = new Set([
    'COUNT', 'SUM', 'AVG', 'MIN', 'MAX', 'COALESCE', 'IFNULL',
    'NULLIF', 'CAST', 'TYPEOF', 'LENGTH', 'SUBSTR', 'REPLACE',
    'TRIM', 'UPPER', 'LOWER', 'ROUND', 'ABS', 'RANDOM',
    'DATE', 'TIME', 'DATETIME', 'STRFTIME', 'GROUP_CONCAT',
]);

const highlightSQL = (sql: string): string => {
    // Escape HTML
    const esc = (s: string) => s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
    // Tokenize and highlight
    return sql.replace(
        /(--[^\n]*|'[^']*'|"[^"]*"|\b\d+\.?\d*\b|\b[A-Za-z_]\w*\b|[^\s])/g,
        (token) => {
            // Comments
            if (token.startsWith('--')) return `<span class="sql-comment">${esc(token)}</span>`;
            // Strings
            if (token.startsWith("'") || token.startsWith('"')) return `<span class="sql-string">${esc(token)}</span>`;
            // Numbers
            if (/^\d+\.?\d*$/.test(token)) return `<span class="sql-number">${esc(token)}</span>`;
            // Functions (keywords followed by parens)
            if (SQL_FUNCTIONS.has(token.toUpperCase())) return `<span class="sql-function">${esc(token)}</span>`;
            // Keywords
            if (SQL_KEYWORDS.has(token.toUpperCase())) return `<span class="sql-keyword">${esc(token)}</span>`;
            return esc(token);
        }
    );
};

interface QueryResult {
    status: string;
    data?: Record<string, unknown>[];
    count?: number;
    affected_rows?: number;
    elapsed_ms?: number;
    error?: string;
    message?: string;
}

interface QueryRunSummary {
    status: 'running' | 'success' | 'error';
    message: string;
    connectionLabel: string;
    executedAt: string;
    elapsedMs?: number;
    rowCount?: number;
}

interface SnapshotData {
    table: string;
    condition: string;
    data: Record<string, unknown>[];
    timestamp: string;
}

interface SavedConnection {
    id: string;
    name: string;
    connection_string: string;
    db_type: string;
    database?: string;
    read_only: boolean;
}

const DatabaseTesting: React.FC = () => {
    const [sql, setSql] = useState('SELECT 1 AS value');
    const highlightedSQL = useMemo(() => highlightSQL(sql), [sql]);
    const [result, setResult] = useState<QueryResult | null>(null);
    const [schema, setSchema] = useState<string>('');
    const [tables, setTables] = useState<string[]>([]);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [querySummary, setQuerySummary] = useState<QueryRunSummary | null>(null);
    const [activeTab, setActiveTab] = useState<'query' | 'schema' | 'snapshot'>('query');
    const [snapshots, setSnapshots] = useState<SnapshotData[]>([]);
    const [snapshotTable, setSnapshotTable] = useState('');
    const [snapshotCondition, setSnapshotCondition] = useState('1=1');
    const [diffResult, setDiffResult] = useState<Record<string, unknown> | null>(null);

    // 连接配置弹窗
    const [showConfig, setShowConfig] = useState(false);
    const [dbConnStr, setDbConnStr] = useState('');
    const [dbConnName, setDbConnName] = useState('');
    const [testingConn, setTestingConn] = useState(false);
    const [connTestResult, setConnTestResult] = useState<{ ok: boolean; msg: string } | null>(null);
    const [connections, setConnections] = useState<SavedConnection[]>([]);
    const [selectedConnectionId, setSelectedConnectionId] = useState<string>('builtin');

    const activeConnection = useMemo(
        () => connections.find((item) => item.id === selectedConnectionId) || null,
        [connections, selectedConnectionId]
    );
    const usingBuiltinConnection = !activeConnection;

    const loadConnections = async () => {
        try {
            const res = await fetch(`${API_BASE_URL}/api/db/connections`);
            const data = await res.json();
            const nextConnections = data.connections || [];
            setConnections(nextConnections);
            setSelectedConnectionId((prev) => {
                if (prev === 'builtin') return prev;
                return nextConnections.some((item: SavedConnection) => item.id === prev) ? prev : 'builtin';
            });
        } catch { /* ignore */ }
    };

    useEffect(() => {
        loadConnections();
    }, []);

    useEffect(() => {
        fetchTables();
        fetchSchema();
    }, [selectedConnectionId]);

    const resolveExecutionPayload = (seedTitle: string) => ensureExecutionContextPayload(seedTitle, {
        targetUrl: activeConnection?.database || 'platform',
    });

    const withExecutionContext = (body: Record<string, unknown>, seedTitle: string) => ({
        ...body,
        ...resolveExecutionPayload(seedTitle),
    });

    const buildContextQueryUrl = (baseUrl: string, seedTitle: string) => {
        const context = resolveExecutionPayload(seedTitle);
        const params = new URLSearchParams();
        params.set('session_id', context.session_id);
        if (context.execution_group_id) params.set('execution_group_id', context.execution_group_id);
        if (context.group_title) params.set('group_title', context.group_title);
        return `${baseUrl}?${params.toString()}`;
    };

    const runManagedQuery = async (connId: string, sqlText: string, limit: number = 100) => {
        const controller = new AbortController();
        const timer = window.setTimeout(() => controller.abort(), 60_000);
        const context = resolveExecutionPayload('数据库专项测试');
        try {
            const res = await fetch(API_ENDPOINTS.db.query(connId), {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    sql: sqlText,
                    limit,
                    session_id: context.session_id,
                    execution_group_id: context.execution_group_id,
                    group_title: context.group_title,
                }),
                signal: controller.signal,
            });
            const data = await res.json();
            if (!res.ok) {
                return {
                    success: false,
                    error: data.error || data.detail || data.message || `请求失败 (${res.status})`,
                    rows: [],
                };
            }
            return data;
        } catch (error) {
            if (error instanceof DOMException && error.name === 'AbortError') {
                return {
                    success: false,
                    error: '查询超时（60 秒）。请缩小查询范围或稍后重试。',
                    rows: [],
                };
            }
            return {
                success: false,
                error: error instanceof Error ? error.message : '查询失败',
                rows: [],
            };
        } finally {
            window.clearTimeout(timer);
        }
    };

    const fetchTables = async () => {
        try {
            const endpoint = activeConnection
                ? API_ENDPOINTS.db.tablesForConn(activeConnection.id)
                : API_ENDPOINTS.db.tables;
            const res = await fetch(endpoint);
            const data = await res.json();
            setTables(data.tables || []);
        } catch (e) { console.error('Failed to fetch tables:', e); }
    };

    const fetchSchema = async () => {
        try {
            const endpoint = activeConnection
                ? API_ENDPOINTS.db.schemaForConn(activeConnection.id)
                : API_ENDPOINTS.db.schema;
            const res = await fetch(endpoint);
            const data = await res.json();
            setSchema(data.schema || '');
        } catch (e) { console.error('Failed to fetch schema:', e); }
    };

    const executeSQL = async () => {
        if (!sql.trim()) return;
        setLoading(true);
        setError(null);
        setResult(null);
        const connectionLabel = activeConnection ? activeConnection.name || activeConnection.id : '内置 SQLite';
        const executedAt = new Date().toLocaleTimeString();
        setQuerySummary({
            status: 'running',
            message: `正在查询 ${connectionLabel}...`,
            connectionLabel,
            executedAt,
        });
        try {
            if (activeConnection) {
                const data = await runManagedQuery(activeConnection.id, sql);
                if (!data.success) {
                    const message = data.error || '执行失败';
                    setError(message);
                    setQuerySummary({
                        status: 'error',
                        message,
                        connectionLabel,
                        executedAt,
                    });
                } else {
                    setResult({
                        status: 'success',
                        data: data.rows || [],
                        count: data.count,
                        elapsed_ms: data.elapsed_ms,
                        error: data.error,
                        message: data.message,
                    });
                    setQuerySummary({
                        status: 'success',
                        message: data.message || '查询成功',
                        connectionLabel,
                        executedAt,
                        elapsedMs: data.elapsed_ms,
                        rowCount: data.count,
                    });
                }
            } else {
                const res = await fetch(API_ENDPOINTS.db.execute, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(withExecutionContext({ sql, allow_unsafe: false }, '数据库专项测试'))
                });
                const data = await res.json();
                if (data.status === 'error') {
                    const message = data.error || data.message || '执行失败';
                    setError(message);
                    setQuerySummary({
                        status: 'error',
                        message,
                        connectionLabel,
                        executedAt,
                    });
                } else {
                    setResult(data);
                    setQuerySummary({
                        status: 'success',
                        message: data.message || '查询成功',
                        connectionLabel,
                        executedAt,
                        elapsedMs: data.elapsed_ms,
                        rowCount: data.count,
                    });
                }
            }
        } catch (e: unknown) {
            const message = (e as Error).message;
            setError(message);
            setQuerySummary({
                status: 'error',
                message,
                connectionLabel,
                executedAt,
            });
        } finally {
            setLoading(false);
        }
    };

    const takeSnapshot = async () => {
        if (activeConnection) {
            setError('远端只读连接暂不支持快照与 Diff，请切回内置数据库。');
            return;
        }
        if (!snapshotTable) return;
        setLoading(true);
        try {
            const res = await fetch(API_ENDPOINTS.db.snapshot, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(withExecutionContext({ table: snapshotTable, condition: snapshotCondition || '1=1' }, '数据库专项测试'))
            });
            const data = await res.json();
            if (data.status === 'success') {
                setSnapshots(prev => [...prev, {
                    table: snapshotTable,
                    condition: snapshotCondition,
                    data: data.data || [],
                    timestamp: new Date().toLocaleTimeString()
                }]);
            }
        } catch (e: unknown) {
            setError((e as Error).message);
        } finally {
            setLoading(false);
        }
    };

    const compareSnapshot = async (snapshot: SnapshotData) => {
        if (activeConnection) {
            setError('远端只读连接暂不支持快照与 Diff，请切回内置数据库。');
            return;
        }
        setLoading(true);
        try {
            const res = await fetch(API_ENDPOINTS.db.diff, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    table: snapshot.table,
                    condition: snapshot.condition,
                    snapshot_data: snapshot.data,
                    ...resolveExecutionPayload('数据库专项测试'),
                })
            });
            const data = await res.json();
            setDiffResult(data);
        } catch (e: unknown) {
            setError((e as Error).message);
        } finally {
            setLoading(false);
        }
    };

    const backupDB = async () => {
        if (activeConnection) {
            setError('远端连接不支持平台内置备份；当前仅允许只读元数据和 SELECT 查询。');
            return;
        }
        setLoading(true);
        try {
            const res = await fetch(API_ENDPOINTS.db.backup, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(withExecutionContext({}, '数据库专项测试'))
            });
            const data = await res.json();
            if (data.status === 'success') {
                setError(null);
                alert(data.message || '备份成功');
            } else {
                setError(data.message || '备份失败');
            }
        } catch (e: unknown) {
            setError((e as Error).message);
        } finally {
            setLoading(false);
        }
    };

    const copyToClipboard = (text: string) => {
        navigator.clipboard.writeText(text).catch(() => { });
    };

    return (
        <div className="flex flex-col h-full gap-4 animate-in fade-in duration-500">
            <ExecutionBatchBanner standaloneHint="数据库测试结果现在也会统一进入执行中心；如果当前没有测试批次，首次执行连接测试、查询、快照、Diff 或备份时会自动创建专项测试批次。" />

            {/* Header */}
            <div className="flex items-center justify-between">
                <div className="flex items-center gap-1 p-1 rounded-xl bg-slate-100 dark:bg-slate-800/50 w-fit">
                    {(['query', 'schema', 'snapshot'] as const).map(tab => (
                        <button key={tab} onClick={() => setActiveTab(tab)}
                            className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-all duration-200 ${activeTab === tab
                                ? 'text-violet-500 bg-violet-500/10 border border-violet-500/30 shadow-sm'
                                : 'text-slate-500 hover:text-slate-700 dark:hover:text-slate-300 border border-transparent'
                                }`}>
                            {tab === 'query' && <><Play className="w-4 h-4" /> SQL 查询</>}
                            {tab === 'schema' && <><Table className="w-4 h-4" /> Schema</>}
                            {tab === 'snapshot' && <><Camera className="w-4 h-4" /> 快照 & Diff</>}
                        </button>
                    ))}
                </div>
                    <div className="flex items-center gap-2">
                        {/* 当前连接指示器 */}
                        <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-emerald-50 dark:bg-emerald-500/10 border border-emerald-200 dark:border-emerald-500/30 mr-1">
                        <span className="relative flex h-2 w-2">
                            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
                            <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500"></span>
                        </span>
                        <span className="text-xs font-medium text-emerald-700 dark:text-emerald-400">
                            {activeConnection ? activeConnection.name || activeConnection.id : '内置 SQLite'}
                        </span>
                        <span className="text-[10px] px-1.5 py-0.5 rounded bg-emerald-100 dark:bg-emerald-500/20 text-emerald-600 dark:text-emerald-300 font-mono">
                            {activeConnection ? activeConnection.db_type.toUpperCase() : 'SQLite'}
                        </span>
                        {activeConnection?.read_only && (
                            <span className="text-[10px] px-1.5 py-0.5 rounded bg-amber-100 dark:bg-amber-500/20 text-amber-700 dark:text-amber-300">
                                只读
                            </span>
                        )}
                    </div>
                    <select
                        value={selectedConnectionId}
                        onChange={(e) => setSelectedConnectionId(e.target.value)}
                        className="px-3 py-2 text-sm bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700 rounded-lg outline-none"
                    >
                        <option value="builtin">内置 SQLite</option>
                        {connections.map((conn) => (
                            <option key={conn.id} value={conn.id}>
                                {conn.name} {conn.read_only ? '· 只读' : ''}
                            </option>
                        ))}
                    </select>
                    <button onClick={() => { setShowConfig(true); loadConnections(); }}
                        className="flex items-center gap-2 px-3 py-2 text-sm font-medium text-indigo-600 dark:text-indigo-400 hover:bg-indigo-50 dark:hover:bg-indigo-500/10 rounded-lg transition border border-indigo-200 dark:border-indigo-500/30">
                        <Settings className="w-4 h-4" /> 连接配置
                    </button>
                    <button onClick={backupDB} disabled={loading || !usingBuiltinConnection}
                        className="flex items-center gap-2 px-4 py-2 text-sm font-medium text-slate-600 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800 rounded-lg transition border border-slate-200 dark:border-slate-700">
                        <Download className="w-4 h-4" /> 备份
                    </button>
                </div>
            </div>

            {/* 连接配置弹窗 */}
            {showConfig && (
                <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-md animate-in fade-in duration-300">
                    <div className="bg-white/95 dark:bg-slate-800/95 backdrop-blur-xl rounded-2xl shadow-2xl shadow-black/20 dark:shadow-black/50 border border-slate-200/80 dark:border-slate-700/80 w-full max-w-lg p-6 relative animate-in zoom-in-95 duration-300">
                        <button onClick={() => setShowConfig(false)} className="absolute top-4 right-4 text-slate-400 hover:text-slate-600 dark:hover:text-slate-300 p-1 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-700/50 transition-all focus:outline-none focus:ring-2 focus:ring-indigo-500/40">
                            <X className="w-5 h-5" />
                        </button>
                        <h3 className="text-lg font-bold text-slate-800 dark:text-white mb-4 flex items-center gap-2">
                            <Database className="w-5 h-5 text-violet-500" /> 数据库连接配置
                        </h3>

                        {/* 已有连接 */}
                        {connections.length > 0 && (
                            <div className="mb-4">
                                <div className="text-xs font-medium text-slate-500 mb-2">已保存的连接</div>
                                <div className="space-y-1.5">
                                    {connections.map(c => (
                                        <button
                                            key={c.id}
                                            onClick={() => setSelectedConnectionId(c.id)}
                                            className={`w-full flex items-center justify-between px-3 py-2 rounded-lg text-sm text-left transition ${
                                                selectedConnectionId === c.id
                                                    ? 'bg-indigo-50 dark:bg-indigo-500/10 border border-indigo-200 dark:border-indigo-500/30'
                                                    : 'bg-slate-50 dark:bg-slate-700/50 border border-transparent'
                                            }`}
                                        >
                                            <div className="min-w-0">
                                                <div className="font-medium text-slate-700 dark:text-slate-300 flex items-center gap-2">
                                                    <span>{c.name || c.id}</span>
                                                    {c.read_only && <span className="text-[10px] px-1.5 py-0.5 rounded bg-amber-100 dark:bg-amber-500/20 text-amber-700 dark:text-amber-300">只读</span>}
                                                </div>
                                                <div className="text-xs text-slate-400 font-mono truncate max-w-[320px]">{c.connection_string}</div>
                                            </div>
                                            {selectedConnectionId === c.id && <Check className="w-4 h-4 text-indigo-500 flex-shrink-0" />}
                                        </button>
                                    ))}
                                </div>
                            </div>
                        )}

                        <div className="rounded-lg border border-amber-200 bg-amber-50/80 dark:border-amber-500/30 dark:bg-amber-500/10 px-3 py-2 text-xs text-amber-700 dark:text-amber-300">
                            外部数据库连接默认按只读保存。平台只允许连接测试、元数据读取和 SELECT 查询，不会通过这个入口执行写操作。
                        </div>

                        <div className="space-y-3">
                            <div>
                                <label className="text-xs font-medium text-slate-500 dark:text-slate-400">连接名称</label>
                                <input type="text" value={dbConnName} onChange={e => setDbConnName(e.target.value)}
                                    placeholder="例如：生产环境 MySQL" className="w-full mt-1 px-3 py-2 rounded-lg bg-slate-50 dark:bg-slate-700/50 border border-slate-200 dark:border-slate-600 text-sm outline-none" />
                            </div>
                            <div>
                                <label className="text-xs font-medium text-slate-500 dark:text-slate-400">连接字符串 (SQLAlchemy 格式)</label>
                                <input type="text" value={dbConnStr} onChange={e => { setDbConnStr(e.target.value); setConnTestResult(null); }}
                                    placeholder="mysql+pymysql://user:pass@host:3306/db" className="w-full mt-1 px-3 py-2 rounded-lg bg-slate-50 dark:bg-slate-700/50 border border-slate-200 dark:border-slate-600 text-sm font-mono outline-none" />
                                <p className="text-xs text-slate-400 mt-1">支持 MySQL / PostgreSQL / SQLite 等</p>
                            </div>

                            {connTestResult && (
                                <div className={`px-3 py-2 rounded-lg text-sm ${connTestResult.ok
                                    ? 'bg-emerald-50 text-emerald-600 dark:bg-emerald-500/10 dark:text-emerald-400'
                                    : 'bg-red-50 text-red-600 dark:bg-red-500/10 dark:text-red-400'}`}>
                                    {connTestResult.ok ? '✅ ' : '❌ '}{connTestResult.msg}
                                </div>
                            )}

                            <div className="flex items-center gap-2 pt-2">
                                <button
                                    onClick={async () => {
                                        if (!dbConnStr.trim()) return;
                                        setTestingConn(true); setConnTestResult(null);
                                        try {
                                            const createRes = await fetch(`${API_BASE_URL}/api/db/connections`, {
                                                method: 'POST', headers: { 'Content-Type': 'application/json' },
                                                body: JSON.stringify({ name: dbConnName || 'test', connection_string: dbConnStr, read_only: true }),
                                            });
                                            const createData = await createRes.json();
                                            const testId = createData.connection?.id;
                                            if (testId) {
                                                const testRes = await fetch(buildContextQueryUrl(`${API_BASE_URL}/api/db/connections/${testId}/test`, '数据库连接测试'), { method: 'POST' });
                                                const testData = await testRes.json();
                                                setConnTestResult({ ok: !!testData.success, msg: testData.message || (testData.success ? '连接成功' : testData.error || '连接失败') });
                                                setSelectedConnectionId(testId);
                                            } else {
                                                setConnTestResult({ ok: false, msg: '连接保存失败' });
                                            }
                                            loadConnections();
                                        } catch (e) {
                                            setConnTestResult({ ok: false, msg: `测试失败: ${e instanceof Error ? e.message : '网络错误'}` });
                                        } finally { setTestingConn(false); }
                                    }}
                                    disabled={testingConn || !dbConnStr.trim()}
                                    className="flex-1 flex items-center justify-center gap-2 px-4 py-2.5 bg-gradient-to-r from-violet-500 to-purple-500 text-white rounded-lg text-sm font-medium disabled:opacity-50 transition-all"
                                >
                                    {testingConn ? <Loader2 className="w-4 h-4 animate-spin" /> : <Database className="w-4 h-4" />}
                                    {testingConn ? '测试中...' : '测试并保存'}
                                </button>
                                <button onClick={() => setShowConfig(false)}
                                    className="px-4 py-2.5 text-sm text-slate-500 hover:bg-slate-100 dark:hover:bg-slate-700 rounded-lg transition">
                                    关闭
                                </button>
                            </div>
                        </div>
                    </div>
                </div>
            )}

            {/* Query Tab */}
            {activeTab === 'query' && (
                <div className="flex-1 flex flex-col gap-4 min-h-0">
                    {/* SQL Editor */}
                    <div className="rounded-xl border border-slate-200 dark:border-slate-800 bg-white/50 dark:bg-slate-900/50 backdrop-blur-md overflow-hidden">
                        <div className="p-3 border-b border-slate-200 dark:border-slate-800 flex items-center justify-between">
                            <div className="flex items-center gap-2">
                                <Database className="w-4 h-4 text-violet-500" />
                                <span className="text-sm font-bold text-slate-700 dark:text-white">SQL 编辑器</span>
                                {activeConnection && (
                                    <span className="text-xs px-2 py-0.5 rounded-full bg-amber-100 dark:bg-amber-500/20 text-amber-700 dark:text-amber-300">
                                        远端只读连接
                                    </span>
                                )}
                            </div>
                            <div className="flex items-center gap-2">
                                {tables.length > 0 && (
                                    <select onChange={(e) => { if (e.target.value) setSql(`SELECT * FROM ${e.target.value} LIMIT 50`); }}
                                        className="px-2 py-1 text-xs bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg outline-none">
                                        <option value="">快速查询表...</option>
                                        {tables.map(t => <option key={t} value={t}>{t}</option>)}
                                    </select>
                                )}
                                <button onClick={executeSQL} disabled={loading}
                                    className="flex items-center gap-1.5 px-4 py-1.5 bg-gradient-to-r from-violet-600 to-purple-600 hover:from-violet-500 hover:to-purple-500 text-white rounded-lg text-sm font-medium shadow-lg shadow-violet-500/20 active:scale-95 transition-all disabled:opacity-50">
                                    {loading ? <RefreshCw className="w-3.5 h-3.5 animate-spin" /> : <Play className="w-3.5 h-3.5" />}
                                    执行
                                </button>
                            </div>
                        </div>
                        <div className="relative">
                            {/* Highlighted overlay */}
                            <pre
                                className="absolute inset-0 px-4 py-3 text-sm font-mono whitespace-pre-wrap break-words pointer-events-none overflow-hidden leading-[1.625]"
                                aria-hidden="true"
                                dangerouslySetInnerHTML={{ __html: highlightedSQL + '\n' }}
                            />
                            {/* Transparent textarea */}
                            <textarea value={sql} onChange={(e) => setSql(e.target.value)}
                                onKeyDown={(e) => { if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) executeSQL(); }}
                                className="relative w-full h-32 px-4 py-3 bg-transparent text-sm font-mono outline-none resize-none text-transparent caret-slate-700 dark:caret-slate-300 leading-[1.625]"
                                spellCheck={false} placeholder="输入 SQL 查询... (Ctrl+Enter 执行)" />
                            {/* Inline CSS for syntax colors */}
                            <style>{`
                                .sql-keyword { color: #8b5cf6; font-weight: 600; }
                                .sql-function { color: #0ea5e9; }
                                .sql-string { color: #22c55e; }
                                .sql-number { color: #f59e0b; }
                                .sql-comment { color: #94a3b8; font-style: italic; }
                                .dark .sql-keyword { color: #a78bfa; }
                                .dark .sql-function { color: #38bdf8; }
                                .dark .sql-string { color: #4ade80; }
                                .dark .sql-number { color: #fbbf24; }
                                .dark .sql-comment { color: #64748b; }
                            `}</style>
                        </div>
                    </div>

                    {activeConnection && (
                        <div className="p-3 rounded-xl border border-amber-200 bg-amber-50/80 text-amber-700 dark:border-amber-500/30 dark:bg-amber-500/10 dark:text-amber-300 text-sm">
                            当前正在查询外部连接 `{activeConnection.name}`。平台已强制限制为只读模式，只允许元数据读取和 `SELECT` 查询。
                        </div>
                    )}

                    {querySummary && (
                        <div className={`p-3 rounded-xl border text-sm ${querySummary.status === 'success'
                            ? 'border-emerald-200 bg-emerald-50/80 text-emerald-700 dark:border-emerald-500/30 dark:bg-emerald-500/10 dark:text-emerald-300'
                            : querySummary.status === 'error'
                                ? 'border-red-200 bg-red-50/80 text-red-700 dark:border-red-500/30 dark:bg-red-500/10 dark:text-red-300'
                                : 'border-sky-200 bg-sky-50/80 text-sky-700 dark:border-sky-500/30 dark:bg-sky-500/10 dark:text-sky-300'
                            }`}>
                            <div className="flex flex-wrap items-center gap-2">
                                <span className="font-semibold">
                                    {querySummary.status === 'success' ? '最近查询成功' : querySummary.status === 'error' ? '最近查询失败' : '查询进行中'}
                                </span>
                                <span className="text-xs opacity-80">{querySummary.connectionLabel}</span>
                                <span className="text-xs opacity-70">{querySummary.executedAt}</span>
                                {querySummary.rowCount !== undefined && (
                                    <span className="text-xs px-2 py-0.5 rounded-full bg-white/60 dark:bg-slate-900/30">
                                        {querySummary.rowCount} 行
                                    </span>
                                )}
                                {querySummary.elapsedMs !== undefined && (
                                    <span className="text-xs px-2 py-0.5 rounded-full bg-white/60 dark:bg-slate-900/30">
                                        {querySummary.elapsedMs} ms
                                    </span>
                                )}
                            </div>
                            <p className="mt-1 text-xs opacity-90">{querySummary.message}</p>
                        </div>
                    )}

                    {/* Error */}
                    {error && (
                        <div className="p-3 bg-red-50 dark:bg-red-900/10 border border-red-200 dark:border-red-800 rounded-xl text-red-600 dark:text-red-400 text-sm flex items-center gap-2">
                            <AlertCircle className="w-4 h-4 flex-shrink-0" /> {error}
                        </div>
                    )}

                    {/* Results Table */}
                    {result && (
                        <div className="flex-1 rounded-xl border border-slate-200 dark:border-slate-800 bg-white/50 dark:bg-slate-900/50 backdrop-blur-md overflow-hidden flex flex-col min-h-0">
                            <div className="p-3 border-b border-slate-200 dark:border-slate-800 flex items-center justify-between">
                                <div>
                                    <span className="text-sm font-bold text-slate-700 dark:text-white flex items-center gap-2">
                                        <Check className="w-4 h-4 text-green-500" />
                                        结果 {result.count !== undefined && `(${result.count} 行)`}
                                        {result.affected_rows !== undefined && `(${result.affected_rows} 行受影响)`}
                                    </span>
                                    {(result.message || result.elapsed_ms !== undefined) && (
                                        <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">
                                            {result.message || `查询完成，用时 ${result.elapsed_ms} ms`}
                                        </p>
                                    )}
                                </div>
                                <button onClick={() => copyToClipboard(JSON.stringify(result.data, null, 2))}
                                    className="p-1.5 text-slate-400 hover:text-slate-600 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-800 transition" title="复制 JSON">
                                    <Copy className="w-4 h-4" />
                                </button>
                            </div>
                            <div className="flex-1 overflow-auto">
                                {result.data && result.data.length > 0 ? (
                                    <table className="w-full text-sm">
                                        <thead className="sticky top-0 bg-slate-50 dark:bg-slate-800">
                                            <tr>
                                                {Object.keys(result.data[0]).map(col => (
                                                    <th key={col} className="px-4 py-2 text-left font-medium text-slate-600 dark:text-slate-400 border-b border-slate-200 dark:border-slate-700 whitespace-nowrap">{col}</th>
                                                ))}
                                            </tr>
                                        </thead>
                                        <tbody>
                                            {result.data.map((row, i) => (
                                                <tr key={i} className="hover:bg-slate-50 dark:hover:bg-slate-800/50 transition">
                                                    {Object.values(row).map((val, j) => (
                                                        <td key={j} className="px-4 py-2 border-b border-slate-100 dark:border-slate-800 text-slate-700 dark:text-slate-300 font-mono text-xs max-w-xs truncate">
                                                            {val === null ? <span className="text-slate-400 italic">NULL</span> : String(val)}
                                                        </td>
                                                    ))}
                                                </tr>
                                            ))}
                                        </tbody>
                                    </table>
                                ) : (
                                    <div className="p-4 text-center text-slate-400 text-sm">无数据</div>
                                )}
                            </div>
                        </div>
                    )}
                </div>
            )}

            {/* Schema Tab */}
            {activeTab === 'schema' && (
                <div className="flex-1 rounded-xl border border-slate-200 dark:border-slate-800 bg-white/50 dark:bg-slate-900/50 backdrop-blur-md overflow-hidden flex flex-col min-h-0">
                    <div className="p-3 border-b border-slate-200 dark:border-slate-800 flex items-center justify-between">
                        <span className="text-sm font-bold text-slate-700 dark:text-white flex items-center gap-2">
                            <Table className="w-4 h-4 text-violet-500" /> 数据库 Schema
                        </span>
                        <button onClick={fetchSchema} className="p-1.5 text-slate-400 hover:text-slate-600 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-800 transition">
                            <RefreshCw className="w-4 h-4" />
                        </button>
                    </div>
                    <div className="flex-1 overflow-auto p-4">
                        <pre className="text-sm font-mono text-slate-700 dark:text-slate-300 whitespace-pre-wrap">
                                    {schema || '加载中...'}
                        </pre>
                    </div>
                    {tables.length > 0 && (
                        <div className="p-3 border-t border-slate-200 dark:border-slate-800">
                            <div className="flex flex-wrap gap-2">
                                {tables.map(t => (
                                    <button key={t} onClick={() => { setActiveTab('query'); setSql(`SELECT * FROM ${t} LIMIT 50`); }}
                                        className="px-3 py-1 text-xs font-medium bg-violet-50 dark:bg-violet-500/10 text-violet-600 dark:text-violet-400 rounded-full hover:bg-violet-100 dark:hover:bg-violet-500/20 transition">
                                        {t}
                                    </button>
                                ))}
                            </div>
                        </div>
                    )}
                </div>
            )}

            {/* Snapshot & Diff Tab */}
            {activeTab === 'snapshot' && (
                <div className="flex-1 flex flex-col gap-4 min-h-0">
                    {/* Create Snapshot */}
                    <div className="rounded-xl border border-slate-200 dark:border-slate-800 bg-white/50 dark:bg-slate-900/50 backdrop-blur-md p-4">
                        <h3 className="text-sm font-bold text-slate-700 dark:text-white mb-3 flex items-center gap-2">
                            <Camera className="w-4 h-4 text-violet-500" /> 创建数据快照
                        </h3>
                        <div className="flex items-center gap-3">
                            <select value={snapshotTable} onChange={(e) => setSnapshotTable(e.target.value)}
                                className="px-3 py-2 bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg text-sm outline-none">
                                <option value="">选择表...</option>
                                {tables.map(t => <option key={t} value={t}>{t}</option>)}
                            </select>
                            <input type="text" value={snapshotCondition} onChange={(e) => setSnapshotCondition(e.target.value)}
                                placeholder="WHERE 条件 (默认 1=1)" className="flex-1 px-3 py-2 bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg text-sm outline-none font-mono" />
                            <button onClick={takeSnapshot} disabled={loading || !snapshotTable}
                                className="flex items-center gap-1.5 px-4 py-2 bg-gradient-to-r from-violet-600 to-purple-600 text-white rounded-lg text-sm font-medium shadow-lg shadow-violet-500/20 active:scale-95 transition-all disabled:opacity-50">
                                <Camera className="w-4 h-4" /> 快照
                            </button>
                        </div>
                    </div>

                    {/* Snapshots List */}
                    <div className="flex-1 rounded-xl border border-slate-200 dark:border-slate-800 bg-white/50 dark:bg-slate-900/50 backdrop-blur-md overflow-hidden flex flex-col min-h-0">
                        <div className="p-3 border-b border-slate-200 dark:border-slate-800">
                            <span className="text-sm font-bold text-slate-700 dark:text-white">已保存快照 ({snapshots.length})</span>
                        </div>
                        <div className="flex-1 overflow-auto">
                            {snapshots.length === 0 ? (
                                <div className="p-8 text-center text-slate-400">
                                    <Camera className="w-10 h-10 mx-auto mb-3 opacity-30" />
                                    <p className="text-sm">暂无快照，先创建一个吧</p>
                                </div>
                            ) : (
                                <div className="p-3 space-y-2">
                                    {snapshots.map((snap, i) => (
                                        <div key={i} className="flex items-center justify-between p-3 rounded-lg border border-slate-200 dark:border-slate-700 hover:bg-slate-50 dark:hover:bg-slate-800/50 transition">
                                            <div>
                                                <div className="text-sm font-medium text-slate-700 dark:text-slate-300">
                                                    <span className="font-mono text-violet-500">{snap.table}</span>
                                                    <span className="text-slate-400 text-xs ml-2">WHERE {snap.condition}</span>
                                                </div>
                                                <div className="text-xs text-slate-400 mt-0.5">{snap.timestamp} · {snap.data.length} 行</div>
                                            </div>
                                            <div className="flex items-center gap-2">
                                                <button onClick={() => compareSnapshot(snap)}
                                                    className="flex items-center gap-1 px-3 py-1.5 text-xs font-medium text-emerald-600 bg-emerald-50 dark:bg-emerald-500/10 rounded-lg hover:bg-emerald-100 dark:hover:bg-emerald-500/20 transition">
                                                    <GitCompare className="w-3.5 h-3.5" /> Diff
                                                </button>
                                                <button onClick={() => setSnapshots(prev => prev.filter((_, idx) => idx !== i))}
                                                    className="p-1.5 text-red-400 hover:text-red-500 hover:bg-red-50 dark:hover:bg-red-900/20 rounded-lg transition">
                                                    <Trash2 className="w-3.5 h-3.5" />
                                                </button>
                                            </div>
                                        </div>
                                    ))}
                                </div>
                            )}
                        </div>

                        {/* Diff Result */}
                        {diffResult && (
                            <div className="border-t border-slate-200 dark:border-slate-800 p-4">
                                <h4 className="text-sm font-bold text-slate-700 dark:text-white mb-2 flex items-center gap-2">
                                    <GitCompare className="w-4 h-4" /> Diff 结果
                                </h4>
                                <div className={`p-3 rounded-lg text-sm ${diffResult && typeof diffResult === 'object' && 'status' in diffResult && (diffResult as any).status === 'same'
                                    ? 'bg-green-50 dark:bg-green-900/10 text-green-600 dark:text-green-400 border border-green-200 dark:border-green-800'
                                    : 'bg-yellow-50 dark:bg-yellow-900/10 text-yellow-700 dark:text-yellow-400 border border-yellow-200 dark:border-yellow-800'
                                    }`}>
                                    <p className="font-medium">{diffResult && typeof diffResult === 'object' && 'message' in diffResult ? (diffResult as any).message : ''}</p>
                                    {diffResult && typeof diffResult === 'object' && 'details' in diffResult && Array.isArray((diffResult as any).details) && (
                                        <ul className="mt-2 text-xs space-y-1">
                                            {(diffResult as any).details.map((d: string, i: number) => (
                                                <li key={i} className="font-mono">• {d}</li>
                                            ))}
                                        </ul>
                                    )}
                                </div>
                            </div>
                        )}
                    </div>
                </div>
            )}
        </div>
    );
};

export default DatabaseTesting;
