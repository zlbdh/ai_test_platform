/** useNotifications: notification state management (P2-1).
 * Manage notifications, read state, and desktop delivery, with SSE/WebSocket integration.
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

        setNotifications(prev => [notif, ...prev].slice(0, 50)); // Keep at most 50 notifications.

        // Desktop notification
        if ('Notification' in window && Notification.permission === 'granted') {
            try {
                new Notification(title, {
                    body: message,
                    icon: '/favicon.ico',
                    tag: id,
                });
            } catch {
                // Fail silently.
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
