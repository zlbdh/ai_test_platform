import { detectSemanticTestType } from '../utils/semanticIntent';
import { useState, useRef, useEffect, useCallback, type ReactNode } from 'react';
import { Send, Sparkles, Globe, CheckCircle, Search, Loader2, MousePointer, X } from '../components/icons';
import { API_BASE_URL } from '../config';

interface ChatMessage {
    id: string;
    role: 'user' | 'assistant' | 'system';
    content: string;
    type?: 'action' | 'assert' | 'query' | 'info';
    result?: any;
    timestamp: number;
}

const MESSAGE_TYPE_META = {
    action: { icon: <MousePointer className="w-3 h-3" />, label: "Actions" },
    assert: { icon: <CheckCircle className="w-3 h-3" />, label: "Assertion" },
    query: { icon: <Search className="w-3 h-3" />, label: "Query" },
    info: { icon: <Sparkles className="w-3 h-3" />, label: "Informational" },
} satisfies Record<NonNullable<ChatMessage['type']>, { icon: ReactNode; label: string }>;

export default function SemanticTestPage() {
    const [messages, setMessages] = useState<ChatMessage[]>([
        { id: '0', role: 'system', content: "👋 Welcome to the semantic testing engine!\n\nDescribe test actions in natural language:\n• \"Click the login button\"\n• \"Enter AI testing in the search box\"\n• \"Verify that the page displays a welcome message\"\n• \"Fetch the first row of the table\"\n\n⚠️ Enter a target URL below and click \"Start browser\" first.", timestamp: Date.now() },
    ]);
    const [input, setInput] = useState('');
    const [loading, setLoading] = useState(false);
    const [sessionId, setSessionId] = useState('');
    const [activeSessions, setActiveSessions] = useState<{ session_id: string; url: string; title: string }[]>([]);
    const [browserUrl, setBrowserUrl] = useState('');
    const [startingBrowser, setStartingBrowser] = useState(false);
    const messagesEndRef = useRef<HTMLDivElement>(null);
    const inputRef = useRef<HTMLInputElement>(null);
    // Track session polling with ref to avoid dependency cycle
    const sessionIdRef = useRef(sessionId);
    sessionIdRef.current = sessionId;

    // Start an independent browser
    const handleStartBrowser = async () => {
        if (!browserUrl.trim()) {
            addSystemMessage("⚠️ Enter a target URL first");
            return;
        }
        setStartingBrowser(true);
        try {
            const res = await fetch(`${API_BASE_URL}/api/semantic/start-browser`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ url: browserUrl, session_id: 'semantic_session' }),
            });
            const data = await res.json();
            if (res.ok) {
                setSessionId(data.session_id);
                addSystemMessage(`🚀 Browser started! ${browserUrl ? `Navigated to ${browserUrl}` : "A blank page is ready"}

You can now send test instructions in natural language.`);
            } else {
                addSystemMessage(`❌ Failed to start: ${data.detail || "Unknown error"}`);
            }
        } catch (e) {
            addSystemMessage(`❌ Failed to start: ${e instanceof Error ? e.message : "Network error"}

Tip: Make sure the backend service (${API_BASE_URL}) is running`);
        } finally {
            setStartingBrowser(false);
        }
    };

    // Stop the browser
    const handleStopBrowser = async () => {
        try {
            await fetch(`${API_BASE_URL}/api/semantic/stop-browser?session_id=${sessionId}`, { method: 'POST' });
            setSessionId('');
            addSystemMessage("🛑 Browser stopped");
        } catch { /* ignore */ }
    };

    const addSystemMessage = useCallback((content: string) => {
        setMessages(prev => [...prev, {
            id: String(Date.now()),
            role: 'system',
            content,
            timestamp: Date.now(),
        }]);
    }, []);

    // Poll active sessions; use a ref to avoid a sessionId dependency cycle
    useEffect(() => {
        const fetchSessions = async () => {
            try {
                const res = await fetch(`${API_BASE_URL}/api/semantic/sessions`);
                if (!res.ok) return;
                const data = await res.json();
                setActiveSessions(data.sessions || []);
                // Select the first active session only when no session is selected
                if (data.sessions?.length > 0 && !sessionIdRef.current) {
                    setSessionId(data.sessions[0].session_id);
                }
            } catch { /* The backend may not be running; ignore silently*/ }
        };
        fetchSessions();
        const timer = setInterval(fetchSessions, 5000);
        return () => clearInterval(timer);
    }, []); // No dependencies; start only once

    useEffect(() => { messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' }); }, [messages]);

    const detectType = detectSemanticTestType;

    const sendMessage = async () => {
        if (!input.trim() || loading || !sessionId) return;
        const text = input.trim();
        setInput('');

        const userMsg: ChatMessage = { id: Date.now().toString(), role: 'user', content: text, timestamp: Date.now() };
        setMessages(prev => [...prev, userMsg]);
        setLoading(true);

        try {
            const type = detectType(text);
            const endpoint = `/api/semantic/${type}`;
            const body = type === 'action' ? { instruction: text, session_id: sessionId }
                : type === 'assert' ? { assertion: text, session_id: sessionId }
                    : { query: text, session_id: sessionId };

            const res = await fetch(`${API_BASE_URL}${endpoint}`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(body),
            });
            const data = await res.json();

            if (!res.ok) {
                setMessages(prev => [...prev, {
                    id: (Date.now() + 1).toString(),
                    role: 'assistant',
                    content: `❌ ${data.detail || `Request failed (${res.status})`}`,
                    timestamp: Date.now(),
                }]);
            } else {
                const assistantMsg: ChatMessage = {
                    id: (Date.now() + 1).toString(),
                    role: 'assistant',
                    content: formatResult(type, data),
                    type,
                    result: data,
                    timestamp: Date.now(),
                };
                setMessages(prev => [...prev, assistantMsg]);
            }
        } catch (e: any) {
            setMessages(prev => [...prev, {
                id: (Date.now() + 1).toString(),
                role: 'assistant',
                content: `❌ Execution failed: ${e.message}

Tip: Make sure the backend is running and an active browser session exists`,
                timestamp: Date.now(),
            }]);
        }
        setLoading(false);
        inputRef.current?.focus();
    };

    const hasSession = !!sessionId;

    return (
        <div className="flex flex-col h-[calc(100vh-80px)]">
            <div className="flex items-center gap-3 mb-4">
                <div className="p-2 rounded-xl bg-gradient-to-br from-cyan-500 to-blue-600 text-white">
                    <Sparkles className="w-5 h-5" />
                </div>
                <div>
                    <h2 className="text-2xl font-bold text-slate-900 dark:text-white">Semantic testing engine</h2>
                    <p className="text-sm text-slate-500 dark:text-slate-400">Describe an action in natural language; AI interprets and executes it</p>
                </div>
            </div>

            {/* Quick actions*/}
            <div className="flex gap-2 mb-3 flex-wrap">
                {[
                    { icon: MousePointer, label: "Click the login button", color: 'text-blue-500 dark:text-blue-400' },
                    { icon: Search, label: "Enter AI testing in the search box", color: 'text-emerald-500 dark:text-emerald-400' },
                    { icon: CheckCircle, label: "Verify that the page displays search results", color: 'text-amber-500 dark:text-amber-400' },
                    { icon: Globe, label: "Fetch the current page title", color: 'text-violet-500 dark:text-violet-400' },
                ].map(q => (
                    <button key={q.label} onClick={() => { setInput(q.label); inputRef.current?.focus(); }}
                        disabled={!hasSession}
                        className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-white hover:bg-slate-50 border border-slate-200 text-xs text-slate-600 hover:text-slate-900 dark:bg-slate-800/60 dark:hover:bg-slate-700/60 dark:border-slate-700 dark:text-slate-300 dark:hover:text-white transition-colors shadow-sm disabled:opacity-40 disabled:cursor-not-allowed">
                        <q.icon className={`w-3.5 h-3.5 ${q.color}`} /> {q.label}
                    </button>
                ))}
            </div>

            {/* Session status indicator*/}
            <div className={`flex items-center gap-3 px-4 py-2.5 rounded-xl border text-sm mb-3 ${hasSession
                ? 'bg-emerald-50 border-emerald-200 text-emerald-700 dark:bg-emerald-500/10 dark:border-emerald-500/30 dark:text-emerald-400'
                : 'bg-amber-50 border-amber-200 text-amber-700 dark:bg-amber-500/10 dark:border-amber-500/30 dark:text-amber-400'
                }`}>
                <span className={`w-2 h-2 rounded-full shrink-0 ${hasSession ? 'bg-emerald-500 animate-pulse' : 'bg-amber-500'}`} />
                {hasSession ? (
                    <>
                        <span>Browser session connected</span>
                        {activeSessions.length > 1 ? (
                            <select value={sessionId} onChange={e => setSessionId(e.target.value)}
                                className="ml-auto px-2 py-1 rounded-lg bg-white border border-emerald-200 text-xs font-mono dark:bg-slate-800 dark:border-emerald-500/30">
                                {activeSessions.map(s => (
                                    <option key={s.session_id} value={s.session_id}>
                                        {s.session_id} — {s.title || s.url}
                                    </option>
                                ))}
                            </select>
                        ) : (
                            <span className="ml-1 text-xs font-mono opacity-60">({sessionId})</span>
                        )}
                        <button onClick={handleStopBrowser}
                            className="ml-auto shrink-0 flex items-center gap-1 px-2 py-1 rounded-lg bg-red-50 hover:bg-red-100 border border-red-200 text-red-600 text-xs font-medium dark:bg-red-500/10 dark:hover:bg-red-500/20 dark:border-red-500/30 dark:text-red-400 transition-colors">
                            <X className="w-3 h-3" /> Stop
                        </button>
                    </>
                ) : (
                    <>
                        <span className="shrink-0">No browser session</span>
                        <input
                            type="text"
                            placeholder={"Enter a target URL (required), such as https://example.com"}
                            value={browserUrl}
                            onChange={e => setBrowserUrl(e.target.value)}
                            onKeyDown={e => e.key === 'Enter' && handleStartBrowser()}
                            className="flex-1 px-3 py-1 rounded-lg bg-white border border-amber-200 text-xs text-slate-700 placeholder:text-slate-400 dark:bg-slate-800 dark:border-amber-500/30 dark:text-slate-300 min-w-0"
                        />
                        <button
                            onClick={handleStartBrowser}
                            disabled={startingBrowser || !browserUrl.trim()}
                            className="shrink-0 px-3 py-1 rounded-lg bg-indigo-500 hover:bg-indigo-600 text-white text-xs font-medium disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                        >
                            {startingBrowser ? "Starting..." : "🚀 Start browser"}
                        </button>
                    </>
                )}
            </div>

            {/* Chat area*/}
            <div className="flex-1 overflow-y-auto rounded-2xl card-hover-lift border border-slate-200/60 bg-white/80 backdrop-blur-sm p-4 space-y-4 dark:border-slate-700/60 dark:bg-slate-800/60">
                {messages.map(msg => {
                    const meta = msg.type ? MESSAGE_TYPE_META[msg.type] : null;
                    return (
                        <div key={msg.id} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                            <div className={`max-w-[80%] rounded-2xl px-4 py-3 ${msg.role === 'user'
                                ? 'bg-gradient-to-r from-indigo-500 to-indigo-600 text-white'
                                : msg.role === 'system'
                                    ? 'bg-indigo-50 text-slate-700 border border-indigo-100 dark:bg-indigo-500/10 dark:text-slate-300 dark:border-indigo-500/20'
                                    : 'bg-slate-50 text-slate-800 border border-slate-200 dark:bg-slate-700/60 dark:text-slate-200 dark:border-slate-600'
                                }`}>
                                <pre className="whitespace-pre-wrap text-sm font-sans">{msg.content}</pre>
                                {meta && (
                                    <div className="mt-2 flex items-center gap-1.5 text-xs opacity-60">
                                        {meta.icon}
                                        <span>{meta.label}</span>
                                        {msg.result?.duration_ms && <span>· {(msg.result.duration_ms / 1000).toFixed(1)}s</span>}
                                    </div>
                                )}
                            </div>
                        </div>
                    );
                })}
                {loading && (
                    <div className="flex justify-start">
                        <div className="bg-slate-50 dark:bg-slate-700/60 rounded-2xl px-4 py-3 border border-slate-200 dark:border-slate-600">
                            <div className="flex items-center gap-2 text-sm text-slate-500 dark:text-slate-400">
                                <Loader2 className="w-4 h-4 animate-spin" /> Running...
                            </div>
                        </div>
                    </div>
                )}
                <div ref={messagesEndRef} />
            </div>

            {/* Input field*/}
            <div className="mt-3 flex gap-2">
                <input ref={inputRef} value={input} onChange={e => setInput(e.target.value)}
                    onKeyDown={e => e.key === 'Enter' && sendMessage()}
                    placeholder={hasSession ? "Describe a test action in natural language..." : "⚠️ Start a browser session first"}
                    disabled={!hasSession}
                    className="flex-1 px-4 py-3 rounded-xl bg-white border border-slate-200 text-slate-900 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-indigo-500/50 focus:border-indigo-400 transition-all shadow-sm dark:bg-slate-800/60 dark:border-slate-700 dark:text-white dark:placeholder:text-slate-500 dark:focus:ring-indigo-500/30 dark:focus:border-indigo-500/50 disabled:opacity-50 disabled:cursor-not-allowed"
                />
                <button onClick={sendMessage} disabled={loading || !input.trim() || !sessionId}
                    className="px-5 py-3 rounded-xl bg-gradient-to-r from-indigo-500 to-indigo-600 hover:from-indigo-600 hover:to-indigo-700 text-white transition-all disabled:opacity-50 disabled:cursor-not-allowed shadow-sm">
                    <Send className="w-5 h-5" />
                </button>
            </div>
        </div>
    );
}

function formatResult(type: string, data: any): string {
    if (data.detail) return `❌ ${data.detail}`;
    if (type === 'action') {
        const success = data.success;
        const method = data.method || '';
        const el = data.element;
        let text = success ? "✅ Action succeeded" : "❌ Action failed";
        if (method) text += ` (${method})`;
        if (data.error) text += `
Error: ${data.error}`;
        if (el) text += `
Element: <${el.role}> "${el.text}"`;
        if (data.duration_ms) text += `
Duration: ${(data.duration_ms / 1000).toFixed(1)}s`;
        return text;
    } else if (type === 'assert') {
        const passed = data.passed;
        let text = passed ? "✅ Assertion passed" : "❌ Assertion failed";
        if (data.reasoning) text += `
Reason: ${data.reasoning}`;
        if (data.evidence) text += `
Evidence: ${data.evidence}`;
        return text;
    } else {
        let text = "📊 Query results:";
        if (data.data !== undefined) text += `\n${JSON.stringify(data.data, null, 2)}`;
        if (data.confidence) text += `
Confidence: ${(data.confidence * 100).toFixed(0)}%`;
        return text;
    }
}
