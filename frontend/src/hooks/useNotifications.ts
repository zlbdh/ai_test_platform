/**
 * useNotifications — 通知状态管理 Hook (P2-1)
 * 
 * 管理通知列表、已读状态、桌面通知推送
 * 支持与 SSE/WebSocket 事件集成
 */
import { useState, useCallback } from 'react';
import type { AppNotification } from '../components/NotificationCenter';

let nextId = 1;

export function useNotifications() {
    const [notifications, setNotifications] = useState<AppNotification[]>([]);

    const addNotification = useCallback((
        type: AppNotification['type'],
        title: string,
        message: string,
        url?: string
    ) => {
        const id = `notif-${nextId++}-${Date.now()}`;
        const notif: AppNotification = {
            id,
            type,
            title,
            message,
            timestamp: Date.now(),
            read: false,
            url,
        };

        setNotifications(prev => [notif, ...prev].slice(0, 50)); // 最多保留 50 条

        // 桌面通知
        if ('Notification' in window && Notification.permission === 'granted') {
            try {
                new Notification(title, {
                    body: message,
                    icon: '/favicon.ico',
                    tag: id,
                });
            } catch {
                // 静默失败
            }
        }

        return id;
    }, []);

    const markRead = useCallback((id: string) => {
        setNotifications(prev =>
            prev.map(n => n.id === id ? { ...n, read: true } : n)
        );
    }, []);

    const markAllRead = useCallback(() => {
        setNotifications(prev => prev.map(n => ({ ...n, read: true })));
    }, []);

    const clearAll = useCallback(() => {
        setNotifications([]);
    }, []);

    const removeOne = useCallback((id: string) => {
        setNotifications(prev => prev.filter(n => n.id !== id));
    }, []);

    return {
        notifications,
        addNotification,
        markRead,
        markAllRead,
        clearAll,
        removeOne,
    };
}

export default useNotifications;
