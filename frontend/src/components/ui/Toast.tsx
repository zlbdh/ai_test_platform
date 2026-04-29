import React, { useState, useEffect, useCallback, createContext, useContext } from 'react';

// === Toast Types ===
type ToastType = 'success' | 'error' | 'warning' | 'info';

interface ToastItem {
    id: number;
    type: ToastType;
    message: string;
    duration: number;
}

interface ToastContextType {
    showToast: (type: ToastType, message: string, duration?: number) => void;
}

const ToastContext = createContext<ToastContextType | null>(null);

// === Hook ===
// eslint-disable-next-line react-refresh/only-export-components
export function useToast() {
    const ctx = useContext(ToastContext);
    if (!ctx) throw new Error('useToast must be used within ToastProvider');
    return ctx;
}

// === Provider ===
let _nextId = 0;

export function ToastProvider({ children }: { children: React.ReactNode }) {
    const [toasts, setToasts] = useState<ToastItem[]>([]);

    const showToast = useCallback((type: ToastType, message: string, duration = 4000) => {
        const id = ++_nextId;
        setToasts(prev => [...prev, { id, type, message, duration }]);
    }, []);

    const removeToast = useCallback((id: number) => {
        setToasts(prev => prev.filter(t => t.id !== id));
    }, []);

    return (
        <ToastContext.Provider value={{ showToast }}>
            {children}
            <div style={{
                position: 'fixed',
                top: 16,
                right: 16,
                zIndex: 99999,
                display: 'flex',
                flexDirection: 'column',
                gap: 8,
                pointerEvents: 'none',
            }}>
                {toasts.map(toast => (
                    <ToastItem key={toast.id} toast={toast} onClose={() => removeToast(toast.id)} />
                ))}
            </div>
        </ToastContext.Provider>
    );
}

// === Single Toast ===
const ICONS: Record<ToastType, string> = {
    success: '',
    error: '',
    warning: '',
    info: 'ℹ',
};

const COLORS: Record<ToastType, { bg: string; border: string; text: string }> = {
    success: { bg: 'rgba(16, 185, 129, 0.15)', border: '#10b981', text: '#a7f3d0' },
    error: { bg: 'rgba(239, 68, 68, 0.15)', border: '#ef4444', text: '#fca5a5' },
    warning: { bg: 'rgba(245, 158, 11, 0.15)', border: '#f59e0b', text: '#fde68a' },
    info: { bg: 'rgba(59, 130, 246, 0.15)', border: '#3b82f6', text: '#93c5fd' },
};

function ToastItem({ toast, onClose }: { toast: ToastItem; onClose: () => void }) {
    const [visible, setVisible] = useState(false);

    useEffect(() => {
        requestAnimationFrame(() => setVisible(true));
        const timer = setTimeout(() => {
            setVisible(false);
            setTimeout(onClose, 300);
        }, toast.duration);
        return () => clearTimeout(timer);
    }, [toast.duration, onClose]);

    const colors = COLORS[toast.type];

    return (
        <div
            style={{
                pointerEvents: 'auto',
                display: 'flex',
                alignItems: 'center',
                gap: 10,
                padding: '12px 18px',
                borderRadius: 10,
                background: colors.bg,
                backdropFilter: 'blur(12px)',
                border: `1px solid ${colors.border}40`,
                color: colors.text,
                fontSize: 14,
                fontWeight: 500,
                boxShadow: '0 8px 32px rgba(0,0,0,0.3)',
                transform: visible ? 'translateX(0)' : 'translateX(120%)',
                opacity: visible ? 1 : 0,
                transition: 'all 0.3s cubic-bezier(0.4, 0, 0.2, 1)',
                maxWidth: 400,
                cursor: 'pointer',
            }}
            onClick={onClose}
        >
            <span style={{ fontSize: 18 }}>{ICONS[toast.type]}</span>
            <span style={{ flex: 1, lineHeight: 1.4 }}>{toast.message}</span>
            <span style={{ opacity: 0.5, fontSize: 16, marginLeft: 8 }}>×</span>
        </div>
    );
}
