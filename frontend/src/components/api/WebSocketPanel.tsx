import React, { useState, useEffect, useRef } from 'react';
import { AlertCircle, Clock, Radio, RefreshCw, Send, Trash2 } from '../icons';
import { API_ENDPOINTS } from '../../config';
import type { WSMessage } from './types';
import { ensureExecutionContextPayload } from '../../utils/executionContext';

// ============================================================
// WebSocket Panel Component
// ============================================================
const WebSocketPanel: React.FC = () => {
    const [url, setUrl] = useState('');
    const [message, setMessage] = useState('');
    const [messages, setMessages] = useState<WSMessage[]>([]);
    const [loading, setLoading] = useState(false);
    const [totalTime, setTotalTime] = useState(0);
    const [error, setError] = useState<string | null>(null);
    const messagesEndRef = useRef<HTMLDivElement>(null);

    useEffect(() => {
        messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }, [messages]);

    const quickTest = async () => {
        if (!url || !message) return;
        setLoading(true);
        setError(null);
        try {
            let msgData: any = message;
            try { msgData = JSON.parse(message); } catch { }
            const res = await fetch(API_ENDPOINTS.wsTest.quickTest, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ url, message: msgData, is_json: typeof msgData === 'object', ...ensureExecutionContextPayload("WebSocket test suite", { targetUrl: url }) })
            });
            const data = await res.json();
            if (data.error) setError(data.error);
            setMessages(prev => [...prev, ...(data.messages || [])]);
            setTotalTime(data.total_time_ms || 0);
        } catch (e: any) {
            setError(e.message);
        } finally {
            setLoading(false);
        }
    };

    const runScenario = async () => {
        if (!url) return;
        setLoading(true);
        setError(null);
        try {
            let msgData: any = message;
            try { msgData = JSON.parse(message); } catch { }
            const scenario = [
                { action: 'send', data: msgData },
                { action: 'receive', timeout: 5.0 }
            ];
            const res = await fetch(API_ENDPOINTS.wsTest.scenario, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ url, scenario, ...ensureExecutionContextPayload("WebSocket test suite", { targetUrl: url }) })
            });
            const data = await res.json();
            if (data.error) setError(data.error);
            setMessages(prev => [...prev, ...(data.messages || [])]);
            setTotalTime(data.total_time_ms || 0);
        } catch (e: any) {
            setError(e.message);
        } finally {
            setLoading(false);
        }
    };
    void runScenario; // Reserved for future "Scenario Test" button

    return (
        <div className="flex flex-col gap-4 h-full">
            {/* URL Bar */}
            <div className="flex items-center gap-3 p-4 rounded-xl border border-slate-200 dark:border-slate-800 bg-white/50 dark:bg-slate-900/50 backdrop-blur-md">
                <span className="px-3 py-2 text-sm font-bold text-emerald-500 bg-emerald-500/10 rounded-lg">WS</span>
                <input type="text" value={url} onChange={(e) => setUrl(e.target.value)}
                    placeholder="ws://localhost:8080/ws"
                    className="flex-1 px-4 py-2 bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg text-sm outline-none focus:ring-2 focus:ring-emerald-500/20 focus:border-emerald-500" />
                <button onClick={() => { setMessages([]); setError(null); }}
                    className="p-2 text-slate-400 hover:text-slate-600 dark:hover:text-slate-300 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-800 transition" title={"Clear"}>
                    <Trash2 className="w-4 h-4" />
                </button>
            </div>

            {/* Messages Timeline */}
            <div className="flex-1 rounded-xl border border-slate-200 dark:border-slate-800 bg-white/50 dark:bg-slate-900/50 backdrop-blur-md overflow-hidden flex flex-col min-h-0">
                <div className="p-3 border-b border-slate-200 dark:border-slate-800 flex items-center justify-between">
                    <span className="text-sm font-bold text-slate-700 dark:text-white">Message timeline</span>
                    <div className="flex items-center gap-3 text-xs text-slate-500">
                        {totalTime > 0 && <span className="flex items-center gap-1"><Clock className="w-3 h-3" /> {totalTime}ms</span>}
                        <span>{messages.length} entries</span>
                    </div>
                </div>
                <div className="flex-1 overflow-y-auto p-4 space-y-3">
                    {error && (
                        <div className="p-3 bg-red-50 dark:bg-red-900/10 border border-red-200 dark:border-red-800 rounded-lg text-red-600 dark:text-red-400 text-sm flex items-center gap-2">
                            <AlertCircle className="w-4 h-4" /> {error}
                        </div>
                    )}
                    {messages.map((msg, i) => (
                        <div key={i} className={`flex ${msg.direction === 'sent' ? 'justify-end' : 'justify-start'}`}>
                            <div className={`max-w-[80%] px-4 py-2.5 rounded-2xl text-sm ${msg.direction === 'sent'
                                ? 'bg-emerald-500 text-white rounded-br-md'
                                : 'bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 rounded-bl-md'
                                }`}>
                                <pre className="font-mono text-xs whitespace-pre-wrap break-all">
                                    {typeof msg.content === 'object' ? JSON.stringify(msg.content, null, 2) : String(msg.content)}
                                </pre>
                            </div>
                        </div>
                    ))}
                    {messages.length === 0 && !error && (
                        <div className="flex flex-col items-center justify-center h-full text-slate-400">
                            <Radio className="w-10 h-10 mb-3 opacity-30" />
                            <p className="text-sm">Send a message to start testing</p>
                        </div>
                    )}
                    <div ref={messagesEndRef} />
                </div>

                {/* Send Bar */}
                <div className="p-3 border-t border-slate-200 dark:border-slate-800 flex items-center gap-2">
                    <input type="text" value={message} onChange={(e) => setMessage(e.target.value)}
                        onKeyDown={(e) => e.key === 'Enter' && quickTest()}
                        placeholder={"Enter a message (text or JSON)..."}
                        className="flex-1 px-4 py-2 bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg text-sm outline-none" />
                    <button onClick={quickTest} disabled={loading}
                        className="flex items-center gap-1.5 px-4 py-2 bg-gradient-to-r from-emerald-600 to-teal-600 hover:from-emerald-500 hover:to-teal-500 text-white rounded-lg text-sm font-medium shadow-lg shadow-emerald-500/20 active:scale-95 transition-all disabled:opacity-50">
                        {loading ? <RefreshCw className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
                        Send
                    </button>
                </div>
            </div>
        </div>
    );
};

export default WebSocketPanel;
