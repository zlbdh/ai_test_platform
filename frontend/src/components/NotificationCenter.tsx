/** NotificationCenter (P2-1): collect test completion, failure, and self-healing notifications.
 * Supports desktop notifications, read/unread state, and clearing notifications.
 */
import React, { useState, useEffect, useRef } from 'react';
import { Bell, CheckCheck, Trash2, X, Zap, AlertTriangle, CheckCircle, Info } from './icons';
import { useT } from '../hooks/useT';

export interface AppNotification {
    id: string;
    type: 'success' | 'error' | 'warning' | 'info' | 'healing';
    title: string;
    message: string;
    timestamp: number;
    read: boolean;
    url?: string; // Navigate on click.
}

interface NotificationCenterProps {
    notifications: AppNotification[];
    onMarkRead: (id: string) => void;
    onMarkAllRead: () => void;
    onClear: () => void;
    onRemove: (id: string) => void;
}

const ICON_MAP = {
    success: <CheckCircle size={16} className="text-emerald-500" />,
    error: <AlertTriangle size={16} className="text-red-500" />,
    warning: <AlertTriangle size={16} className="text-amber-500" />,
    info: <Info size={16} className="text-blue-500" />,
    healing: <Zap size={16} className="text-purple-500" />,
};

function timeAgo(ts: number, tt: (key: string) => string): string {
    const diff = Date.now() - ts;
    if (diff < 60000) return tt('notifications.justNow');
    if (diff < 3600000) return `${Math.floor(diff / 60000)} ${tt('notifications.minutesAgo')}`;
    if (diff < 86400000) return `${Math.floor(diff / 3600000)} ${tt('notifications.hoursAgo')}`;
    return `${Math.floor(diff / 86400000)} ${tt('notifications.daysAgo')}`;
}

const NotificationCenter: React.FC<NotificationCenterProps> = ({
    notifications,
    onMarkRead,
    onMarkAllRead,
    onClear,
    onRemove,
}) => {
    const [isOpen, setIsOpen] = useState(false);
    const panelRef = useRef<HTMLDivElement>(null);
    const tt = useT();

    const unreadCount = notifications.filter(n => !n.read).length;

    // Close when clicking outside.
    useEffect(() => {
        const handleClick = (e: MouseEvent) => {
            if (panelRef.current && !panelRef.current.contains(e.target as Node)) {
                setIsOpen(false);
            }
        };
        if (isOpen) document.addEventListener('mousedown', handleClick);
        return () => document.removeEventListener('mousedown', handleClick);
    }, [isOpen]);

    // Desktop notification permission
    useEffect(() => {
        if ('Notification' in window && Notification.permission === 'default') {
            Notification.requestPermission();
        }
    }, []);

    return (
        <div className="relative z-[100]" ref={panelRef}>
            {/* Bell Button */}
            <button
                onClick={() => setIsOpen(!isOpen)}
                className="relative p-2 rounded-lg text-slate-500 hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors"
                title={tt('notifications.title')}
            >
                <Bell className="w-4 h-4" />
                {unreadCount > 0 && (
                    <span className="absolute -top-0.5 -right-0.5 w-4 h-4 rounded-full bg-red-500 text-white text-[10px] flex items-center justify-center font-bold">
                        {unreadCount > 9 ? '9+' : unreadCount}
                    </span>
                )}
            </button>

            {/* Dropdown Panel */}
            {isOpen && (
                <div
                    className="absolute right-0 top-full mt-2 w-80 rounded-xl border border-slate-200/80 dark:border-slate-700/80 shadow-2xl shadow-black/20 dark:shadow-black/50 overflow-hidden z-[9999] bg-white/95 dark:bg-slate-900/95 backdrop-blur-xl animate-in fade-in slide-in-from-top-2 duration-200"
                >
                    {/* Header */}
                    <div className="flex items-center justify-between px-4 py-3 border-b border-slate-200/80 dark:border-slate-700/80 bg-gradient-to-r from-slate-50/80 to-transparent dark:from-slate-800/50">
                        <span className="text-sm font-semibold text-slate-800 dark:text-white">
                            {tt('notifications.title')} {unreadCount > 0 && `(${unreadCount})`}
                        </span>
                        <div className="flex items-center gap-1">
                            {unreadCount > 0 && (
                                <button
                                    onClick={onMarkAllRead}
                                    className="p-1.5 rounded-lg text-slate-400 hover:text-blue-500 hover:bg-blue-50 dark:hover:bg-blue-500/10 transition-all focus:outline-none focus:ring-2 focus:ring-blue-500/40"
                                    title={tt('notifications.markAllRead')}
                                >
                                    <CheckCheck size={14} />
                                </button>
                            )}
                            <button
                                onClick={onClear}
                                className="p-1.5 rounded-lg text-slate-400 hover:text-red-500 hover:bg-red-50 dark:hover:bg-red-500/10 transition-all focus:outline-none focus:ring-2 focus:ring-red-500/40"
                                title={tt('notifications.clearAll')}
                            >
                                <Trash2 size={14} />
                            </button>
                        </div>
                    </div>

                    {/* List */}
                    <div className="max-h-[40vh] overflow-y-auto">
                        {notifications.length === 0 ? (
                            <div className="py-10 text-center text-sm text-slate-400 dark:text-slate-500">
                                {tt('notifications.noNotifications')}
                            </div>
                        ) : (
                            notifications.map(n => (
                                <div
                                    key={n.id}
                                    className={`flex gap-3 px-4 py-3 border-b border-slate-100 dark:border-slate-800/50 cursor-pointer transition-all ${n.read ? 'opacity-60' : 'hover:bg-slate-50/80 dark:hover:bg-slate-800/50'
                                        }`}
                                    onClick={() => { onMarkRead(n.id); }}
                                >
                                    <div className="shrink-0 pt-0.5">{ICON_MAP[n.type]}</div>
                                    <div className="flex-1 min-w-0">
                                        <div className="flex items-center justify-between gap-2">
                                            <span className="text-xs font-medium truncate text-slate-800 dark:text-slate-200">
                                                {n.title}
                                            </span>
                                            <button
                                                onClick={(e) => { e.stopPropagation(); onRemove(n.id); }}
                                                className="shrink-0 p-1 rounded-lg text-slate-400 hover:text-red-400 hover:bg-red-50 dark:hover:bg-red-500/10 transition-all"
                                            >
                                                <X size={12} />
                                            </button>
                                        </div>
                                        <p className="text-[11px] mt-0.5 line-clamp-2 text-slate-500 dark:text-slate-400">
                                            {n.message}
                                        </p>
                                        <span className="text-[10px] mt-1 block text-slate-400 dark:text-slate-500">
                                            {timeAgo(n.timestamp, tt)}
                                        </span>
                                    </div>
                                    {!n.read && (
                                        <div className="shrink-0 w-2 h-2 rounded-full bg-blue-500 mt-1.5" />
                                    )}
                                </div>
                            ))
                        )}
                    </div>
                </div>
            )}
        </div>
    );
};

export default NotificationCenter;
