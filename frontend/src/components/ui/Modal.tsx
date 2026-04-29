import React, { useEffect, type ReactNode } from 'react';
import { X } from '../icons';

interface ModalProps {
    isOpen: boolean;
    onClose: () => void;
    title?: string;
    children: ReactNode;
    footer?: ReactNode;
    size?: 'sm' | 'md' | 'lg' | 'xl';
    className?: string;
}

const sizeClasses = {
    sm: 'max-w-sm',
    md: 'max-w-md',
    lg: 'max-w-lg',
    xl: 'max-w-xl',
    '2xl': 'max-w-2xl',
};

const Modal: React.FC<ModalProps> = ({
    isOpen, onClose, title, children, footer, size = 'md', className = '',
}: ModalProps & { size?: 'sm' | 'md' | 'lg' | 'xl' | '2xl' }) => {
    // ESC to close
    useEffect(() => {
        if (!isOpen) return;
        const handler = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose(); };
        document.addEventListener('keydown', handler);
        return () => document.removeEventListener('keydown', handler);
    }, [isOpen, onClose]);

    // Prevent body scroll
    useEffect(() => {
        if (isOpen) document.body.style.overflow = 'hidden';
        return () => { document.body.style.overflow = ''; };
    }, [isOpen]);

    if (!isOpen) return null;

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
            {/* Backdrop */}
            <div
                className="absolute inset-0 bg-black/60 backdrop-blur-md animate-in fade-in duration-300"
                onClick={onClose}
            />
            {/* Dialog */}
            <div className={`relative w-full ${sizeClasses[size]} bg-white/95 dark:bg-slate-900/95 backdrop-blur-xl rounded-2xl shadow-2xl shadow-black/20 dark:shadow-black/50 border border-slate-200/80 dark:border-slate-700/80 animate-in zoom-in-95 fade-in duration-300 ${className}`}>
                {/* Header */}
                {title && (
                    <div className="relative">
                        <div className="absolute top-0 left-6 right-6 h-0.5 bg-gradient-to-r from-indigo-500 via-purple-500 to-cyan-500 rounded-full" />
                        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-200/80 dark:border-slate-700/60 bg-slate-50/80 dark:bg-slate-800/40 rounded-t-2xl">
                            <h3 className="text-base font-semibold text-slate-900 dark:text-white">{title}</h3>
                            <button
                                onClick={onClose}
                                className="p-1.5 rounded-lg text-slate-400 hover:bg-slate-200/80 dark:hover:bg-slate-700/80 hover:text-slate-600 dark:hover:text-slate-300 transition-all duration-200 hover:rotate-90 focus:outline-none focus:ring-2 focus:ring-indigo-500/40"
                            >
                                <X className="w-4 h-4" />
                            </button>
                        </div>
                    </div>
                )}
                {/* Body */}
                <div className="px-6 py-4 max-h-[70vh] overflow-y-auto custom-scrollbar">
                    {children}
                </div>
                {/* Footer */}
                {footer && (
                    <div className="flex items-center justify-end gap-2 px-6 py-4 border-t border-slate-200/80 dark:border-slate-700/60 bg-slate-50/50 dark:bg-slate-800/30 rounded-b-2xl">
                        {footer}
                    </div>
                )}
            </div>
        </div>
    );
};

export default Modal;
