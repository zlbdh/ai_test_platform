import React, { useState, useCallback } from 'react';
import { AlertTriangle } from '../icons';

interface ConfirmDialogProps {
    open: boolean;
    title: string;
    message: string;
    onConfirm: () => void;
    onCancel: () => void;
}

export const ConfirmDialog: React.FC<ConfirmDialogProps> = ({ open, title, message, onConfirm, onCancel }) => {
    if (!open) return null;

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center">
            {/* 背景遮罩 */}
            <div className="absolute inset-0 bg-black/60 backdrop-blur-md animate-in fade-in duration-300" onClick={onCancel} />
            {/* 对话框 */}
            <div className="relative bg-white/95 dark:bg-slate-800/95 backdrop-blur-xl rounded-2xl shadow-2xl shadow-black/20 dark:shadow-black/50 border border-slate-200/80 dark:border-slate-700/80 p-6 max-w-sm w-full mx-4 animate-in zoom-in-95 duration-300">
                <div className="flex items-start gap-3 mb-4">
                    <div className="p-2.5 rounded-xl bg-gradient-to-br from-red-50 to-rose-100 dark:from-red-900/30 dark:to-rose-900/20 text-red-500 dark:text-red-400">
                        <AlertTriangle className="w-5 h-5" />
                    </div>
                    <div>
                        <h3 className="font-semibold text-slate-900 dark:text-white">{title}</h3>
                        <p className="text-sm text-slate-500 dark:text-slate-400 mt-1">{message}</p>
                    </div>
                </div>
                <div className="flex justify-end gap-2 mt-6">
                    <button
                        onClick={onCancel}
                        className="px-4 py-2 text-sm font-medium text-slate-700 dark:text-slate-300 bg-slate-100/80 dark:bg-slate-700/80 rounded-xl hover:bg-slate-200/80 dark:hover:bg-slate-600/80 transition-all duration-200 focus:outline-none focus:ring-2 focus:ring-slate-400/40"
                    >
                        取消
                    </button>
                    <button
                        onClick={onConfirm}
                        className="px-4 py-2 text-sm font-medium text-white bg-gradient-to-r from-red-500 to-rose-500 rounded-xl hover:from-red-600 hover:to-rose-600 transition-all duration-200 shadow-lg shadow-red-500/25 focus:outline-none focus:ring-2 focus:ring-red-500/40"
                    >
                        确认删除
                    </button>
                </div>
            </div>
        </div>
    );
};

// Hook: 简化使用
// eslint-disable-next-line react-refresh/only-export-components
export function useConfirmDialog() {
    const [state, setState] = useState<{
        open: boolean;
        title: string;
        message: string;
        resolve: ((v: boolean) => void) | null;
    }>({ open: false, title: '', message: '', resolve: null });

    const confirm = useCallback((title: string, message: string): Promise<boolean> => {
        return new Promise(resolve => {
            setState({ open: true, title, message, resolve });
        });
    }, []);

    const handleConfirm = useCallback(() => {
        state.resolve?.(true);
        setState(prev => ({ ...prev, open: false }));
    }, [state]);

    const handleCancel = useCallback(() => {
        state.resolve?.(false);
        setState(prev => ({ ...prev, open: false }));
    }, [state]);

    const dialogProps = {
        open: state.open,
        title: state.title,
        message: state.message,
        onConfirm: handleConfirm,
        onCancel: handleCancel,
    };

    return { confirm, dialogProps, ConfirmDialog };
}
