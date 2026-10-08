import React, { useEffect, useState, useRef } from 'react';
import { API_ENDPOINTS } from '../config';
import ActionOverlay from './ActionOverlay';
import { Monitor, RefreshCw, Pause, AlertTriangle, Wrench, XCircle } from './icons';

interface RemoteBrowserViewProps {
    url: string;
    isActive: boolean;
    currentAction: string;
    sessionId: string;
}

const RemoteBrowserView: React.FC<RemoteBrowserViewProps> = ({ url, isActive, currentAction, sessionId }) => {
    const [isConnected, setIsConnected] = useState(false);
    const [frameSrc, setFrameSrc] = useState<string | null>(null);
    const [viewport, setViewport] = useState<{ width: number; height: number } | null>(null);
    const [alertState, setAlertState] = useState<{ reason: string, screenshot?: string } | null>(null);
    const [statusMessage, setStatusMessage] = useState<string | null>(null);
    const [hasEverConnected, setHasEverConnected] = useState(false);

    const wsRef = useRef<WebSocket | null>(null);
    const retryTimeoutRef = useRef<NodeJS.Timeout | null>(null);

    const handleIntervention = async (action: 'resume' | 'stop' | 'suspend') => {
        try {
            const endpoint = API_ENDPOINTS.control[action as keyof typeof API_ENDPOINTS.control];
            const url = typeof endpoint === 'function' ? endpoint(sessionId) : (endpoint as string);

            await fetch(url, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                // Suspend requires a request body.
                body: action === 'suspend' ? JSON.stringify({ session_id: sessionId, reason: 'User Intervention' }) : undefined
            });
            setAlertState(null); // Clear alert locally immediately
        } catch (e) {
            console.error("Intervention failed:", e);
        }
    };

    // WebSocket connection logic
    useEffect(() => {
        const connect = () => {
            if (!isActive) {
                return;
            }

            // Clear any existing retry timeout
            if (retryTimeoutRef.current) {
                clearTimeout(retryTimeoutRef.current);
                retryTimeoutRef.current = null;
            }

            // Connect to backend WebSocket Sandbox (via Vite Proxy)
            const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
            const host = window.location.host;
            const ws = new WebSocket(`${protocol}//${host}/ws/sandbox?session_id=${sessionId}`);
            wsRef.current = ws;

            ws.onopen = () => {
                setIsConnected(true);
                setHasEverConnected(true);
                setStatusMessage(null);
            };

            ws.onmessage = (event) => {
                try {
                    const data = JSON.parse(event.data);
                    if (data.type === 'frame') {
                        setFrameSrc(`data:image/jpeg;base64,${data.data}`);
                        setStatusMessage(null);
                    } else if (data.type === 'viewport') {
                        setViewport(data.data);
                    } else if (data.type === 'status') {
                        setStatusMessage(data.message || "Waiting...");
                    }
                } catch (e) {
                    console.warn("Failed to parse WebSocket message:", e);
                }
            };

            ws.onclose = () => {
                setIsConnected(false);
                // Keep frameSrc to preserve the last frame.
                if (isActive) {
                    retryTimeoutRef.current = setTimeout(connect, 3000);
                }
            };

            ws.onerror = (error) => {
                console.error('WebSocket error:', error);
                ws.close();
            };
        };

        if (isActive) {
            connect();
        }

        return () => {
            if (wsRef.current) {
                wsRef.current.close();
                wsRef.current = null;
            }
            if (retryTimeoutRef.current) {
                clearTimeout(retryTimeoutRef.current);
                retryTimeoutRef.current = null;
            }
        };
    }, [isActive, sessionId]);

    // Poll for Intervention Status (Logic Updated for INTERVENTION signal)
    useEffect(() => {
        const interval = setInterval(async () => {
            try {
                const res = await fetch(API_ENDPOINTS.status(sessionId));
                const data = await res.json();

                // Show Alert ONLY if signal is INTERVENTION
                if (data.signal === 'INTERVENTION') {
                    if (!alertState) {
                        setAlertState({
                            reason: data.pause_reason,
                            screenshot: data.intervention_screenshot || null
                        });
                    }
                }
                // If Signal changed to RUNNING or PAUSED (Suspend), auto-hide alert
                else if (data.signal !== 'INTERVENTION' && alertState) {
                    setAlertState(null);
                }
            } catch { /* silent — polling */ }
        }, 1000);
        return () => clearInterval(interval);
    }, [alertState, sessionId]);

    return (
        <div className="flex flex-col h-full bg-white dark:bg-slate-800 rounded-xl overflow-hidden border border-slate-200 dark:border-slate-700 shadow-sm relative group">
            {/* Header */}
            <div className="bg-white dark:bg-slate-800 p-2 border-b border-slate-200 dark:border-slate-700 flex items-center justify-between z-10">
                <div className="flex items-center gap-2">
                    <div className="bg-slate-100 dark:bg-slate-900 rounded px-3 py-1 text-xs text-slate-500 dark:text-slate-400 border border-slate-200 dark:border-slate-700 truncate max-w-[200px]" title={url}>
                        {url || 'No URL'}
                    </div>
                    {viewport && (
                        <span className="text-[10px] text-slate-400 font-mono">
                            {viewport.width}x{viewport.height}
                        </span>
                    )}
                </div>
                <div className="flex items-center gap-2">
                    <div className={`w-2 h-2 rounded-full ${isConnected ? 'bg-green-500 animate-pulse' : frameSrc ? 'bg-amber-500' : 'bg-red-500'}`} />
                    <div className="text-[10px] text-slate-400 font-bold uppercase">
                        {isConnected ? 'LIVE VIEW (WS)' : frameSrc ? "Session ended (last frame)" : isActive ? <><RefreshCw className="w-3 h-3 inline animate-spin" /> Reconnecting...</> : <><Pause className="w-3 h-3 inline" /> Standby</>}
                    </div>
                </div>
            </div>

            {/* Content */}
            <div className="flex-1 relative bg-slate-50 dark:bg-slate-900 flex items-center justify-center overflow-hidden">
                {frameSrc ? (
                    <img
                        src={frameSrc}
                        className={`w-full h-full object-contain ${!isConnected && hasEverConnected ? 'opacity-60' : ''}`}
                        alt="Live Stream"
                    />
                ) : (
                    <div className="flex flex-col items-center gap-2 text-slate-400">
                        {isActive ? (
                            <>
                                <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-indigo-500"></div>
                                <span className="text-xs">{statusMessage || "Connecting..."}</span>
                            </>
                        ) : (
                            <>
                                <div className="flex flex-col items-center gap-3">
                                    <div className="w-12 h-12 rounded-full bg-slate-200 dark:bg-slate-800 flex items-center justify-center">
                                        <Monitor className="w-6 h-6 text-slate-400" />
                                    </div>
                                    <span className="text-xs text-slate-500">Waiting for a test task to start...</span>
                                    <span className="text-[10px] text-slate-600 dark:text-slate-600">The live browser view connects automatically when the task starts</span>
                                </div>
                            </>
                        )}
                    </div>
                )}

                {/* Action annotation overlay*/}
                <ActionOverlay currentAction={currentAction} isActive={isActive} />

                {/* Footer Log (Overlay) */}
                {isActive && currentAction && (
                    <div className="absolute bottom-2 left-2 right-2 z-10 flex flex-col items-end pointer-events-none">
                        {/* Content Container - Pointer events auto to allow interaction */}
                        <div className="bg-black/80 backdrop-blur-md p-3 rounded-lg border border-white/10 text-[11px] text-green-400 font-mono shadow-xl max-w-full pointer-events-auto transition-all duration-300">
                            <div className="flex items-start justify-between gap-4">
                                <div className="flex items-center gap-2 text-white/50 mb-1">
                                    <span className="w-1.5 h-1.5 rounded-full bg-green-500 animate-pulse"></span>
                                    <span>{new Date().toLocaleTimeString()}</span>
                                </div>
                            </div>
                            <div className="max-h-[60px] overflow-y-auto custom-scrollbar break-all whitespace-pre-wrap leading-relaxed">
                                {currentAction}
                            </div>
                        </div>
                    </div>
                )}

                {/* Intervention Modal (Alert) */}
                {alertState && (
                    <div className="absolute inset-0 bg-black/80 backdrop-blur-xl z-50 flex flex-col items-center justify-center text-white px-8 text-center animate-in zoom-in-95 fade-in duration-300">
                        <div className="bg-amber-500/20 p-4 rounded-full mb-4 animate-bounce">
                            <AlertTriangle className="w-10 h-10 text-amber-400" />
                        </div>
                        <h3 className="text-xl font-bold mb-2 text-amber-400">Human assistance required</h3>
                        <p className="text-sm text-slate-300 mb-6 max-w-sm bg-black/50 p-4 rounded border border-white/10">
                            AI needs help: {alertState.reason}
                        </p>

                        {alertState.screenshot && (
                            <img src={`data:image/jpeg;base64,${alertState.screenshot}`} className="w-full max-w-lg h-auto rounded border border-slate-600 mb-6 shadow-2xl" alt="Evidence" />
                        )}

                        <div className="flex flex-col gap-3 w-full max-w-xs">
                            <button
                                onClick={() => handleIntervention('resume')}
                                className="w-full px-6 py-3 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white font-medium transition-all shadow-lg shadow-emerald-600/20 border border-emerald-500 flex items-center justify-center gap-2 focus:outline-none focus:ring-2 focus:ring-emerald-400/50"
                            >
                                <span><Wrench className="w-3.5 h-3.5 inline" /> Resolved (resume)</span>
                            </button>

                            <button
                                onClick={() => handleIntervention('suspend')}
                                className="w-full px-6 py-3 rounded-xl bg-amber-600 hover:bg-amber-500 text-white font-medium transition-all border border-amber-500 flex items-center justify-center gap-2 focus:outline-none focus:ring-2 focus:ring-amber-400/50"
                            >
                                <span><Pause className="w-3.5 h-3.5 inline" /> Suspend (handle later)</span>
                            </button>

                            <button
                                onClick={() => handleIntervention('stop')}
                                className="w-full px-6 py-3 rounded-xl bg-slate-700 hover:bg-slate-600 text-white font-medium transition-all border border-slate-600 flex items-center justify-center gap-2 focus:outline-none focus:ring-2 focus:ring-slate-400/50"
                            >
                                <span><XCircle className="w-3.5 h-3.5 inline" /> Cancel task</span>
                            </button>
                        </div>

                        <div className="mt-4 text-xs text-slate-500">
                            Suspend keeps the AI paused and closes this window so you can work freely. Click Resume in the control bar when you are ready.
                        </div>
                    </div>
                )}
            </div>
        </div>
    );
};

export default RemoteBrowserView;
