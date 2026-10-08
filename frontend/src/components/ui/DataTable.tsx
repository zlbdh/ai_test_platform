import React, { useState, useMemo, useEffect, type ReactNode } from 'react';
import { ChevronUp, ChevronDown, ChevronLeft, ChevronRight as PageRight } from '../icons';

// ============================================================================
// Types
// ============================================================================
export interface DataTableColumn<T> {
    key: string;
    title: string;
    render?: (value: unknown, record: T, index: number) => ReactNode;
    sortable?: boolean;
    width?: string;
    align?: 'left' | 'center' | 'right';
}

interface DataTableProps<T> {
    columns: DataTableColumn<T>[];
    data: T[];
    rowKey: keyof T | ((record: T) => string);
    pageSize?: number;
    emptyText?: string;
    className?: string;
    onRowClick?: (record: T) => void;
    loading?: boolean;
    activeRowKey?: string | null;
}

// ============================================================================
// DataTable Component
// ============================================================================
function DataTable<T extends object>({
    columns, data, rowKey, pageSize = 10, emptyText = "No data yet",
    className = '', onRowClick, loading, activeRowKey = null,
}: DataTableProps<T>) {
    const [sortKey, setSortKey] = useState<string | null>(null);
    const [sortDir, setSortDir] = useState<'asc' | 'desc'>('asc');
    const [page, setPage] = useState(1);

    // Safe value accessor for generic T
    const getValue = (record: T, key: string): unknown => (record as Record<string, unknown>)[key];

    // Sort
    const sorted = useMemo(() => {
        const getVal = (record: T, key: string): unknown => (record as Record<string, unknown>)[key];
        if (!sortKey) return data;
        return [...data].sort((a, b) => {
            const va = getVal(a, sortKey);
            const vb = getVal(b, sortKey);
            if (va == null || vb == null) return 0;
            const cmp = va < vb ? -1 : va > vb ? 1 : 0;
            return sortDir === 'asc' ? cmp : -cmp;
        });
    }, [data, sortKey, sortDir]);

    // Paginate
    const totalPages = Math.max(1, Math.ceil(sorted.length / pageSize));
    const safePage = Math.min(page, totalPages);
    const paged = sorted.slice((safePage - 1) * pageSize, safePage * pageSize);

    const getRowKeyValue = (record: T): string =>
        typeof rowKey === 'function' ? rowKey(record) : String(record[rowKey]);

    useEffect(() => {
        if (!activeRowKey) return;
        const targetIndex = sorted.findIndex(record => getRowKeyValue(record) === activeRowKey);
        if (targetIndex < 0) return;
        const targetPage = Math.floor(targetIndex / pageSize) + 1;
        setPage(targetPage);
    }, [activeRowKey, sorted, pageSize]);

    const handleSort = (key: string) => {
        if (sortKey === key) {
            setSortDir(d => d === 'asc' ? 'desc' : 'asc');
        } else {
            setSortKey(key);
            setSortDir('asc');
        }
        setPage(1);
    };

    const alignClass = (align?: string) =>
        align === 'center' ? 'text-center' : align === 'right' ? 'text-right' : 'text-left';

    return (
        <div className={`rounded-xl border border-slate-200 dark:border-slate-800 overflow-hidden ${className}`}>
            <div className="overflow-x-auto">
                <table className="w-full">
                    <thead>
                        <tr className="bg-slate-50 dark:bg-slate-800/50 border-b border-slate-200 dark:border-slate-800">
                            {columns.map((col, colIndex) => (
                                <th
                                    key={`${col.key}-${colIndex}`}
                                    className={`px-4 py-3 text-[10px] font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400 ${alignClass(col.align)} ${col.sortable ? 'cursor-pointer select-none hover:text-slate-700 dark:hover:text-slate-300' : ''}`}
                                    style={{ width: col.width }}
                                    onClick={() => col.sortable && handleSort(col.key)}
                                >
                                    <span className="inline-flex items-center gap-1">
                                        {col.title}
                                        {col.sortable && sortKey === col.key && (
                                            sortDir === 'asc'
                                                ? <ChevronUp className="w-3 h-3" />
                                                : <ChevronDown className="w-3 h-3" />
                                        )}
                                    </span>
                                </th>
                            ))}
                        </tr>
                    </thead>
                    <tbody>
                        {loading ? (
                            Array.from({ length: 3 }, (_, i) => (
                                <tr key={i} className="border-b border-slate-100 dark:border-slate-800/50">
                                    {columns.map((col, colIndex) => (
                                        <td key={`${col.key}-${colIndex}`} className="px-4 py-3">
                                            <div className="h-3 rounded bg-slate-200 dark:bg-slate-700 animate-pulse" style={{ width: `${50 + Math.random() * 40}%` }} />
                                        </td>
                                    ))}
                                </tr>
                            ))
                        ) : paged.length === 0 ? (
                            <tr>
                                <td colSpan={columns.length} className="px-4 py-8 text-center text-sm text-slate-400 dark:text-slate-500">
                                    {emptyText}
                                </td>
                            </tr>
                        ) : (
                            paged.map((record, idx) => (
                                <tr
                                    key={getRowKeyValue(record)}
                                    onClick={() => onRowClick?.(record)}
                                    data-active={getRowKeyValue(record) === activeRowKey ? 'true' : 'false'}
                                    className={`border-b border-slate-100 dark:border-slate-800/50 transition-colors ${onRowClick ? 'cursor-pointer hover:bg-slate-50 dark:hover:bg-slate-800/30' : ''} ${getRowKeyValue(record) === activeRowKey ? 'bg-cyan-50/80 dark:bg-cyan-900/20' : ''}`}
                                >
                                    {columns.map((col, colIndex) => (
                                        <td key={`${col.key}-${colIndex}`} className={`px-4 py-3 text-sm text-slate-700 dark:text-slate-300 ${alignClass(col.align)}`}>
                                            {col.render
                                                ? col.render(getValue(record, col.key), record, (safePage - 1) * pageSize + idx)
                                                : String(getValue(record, col.key) ?? '-')}
                                        </td>
                                    ))}
                                </tr>
                            ))
                        )}
                    </tbody>
                </table>
            </div>

            {/* Pagination */}
            {totalPages > 1 && (
                <div className="flex items-center justify-between px-4 py-3 border-t border-slate-200 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-800/30">
                    <span className="text-[10px] text-slate-400">
                        Total: {sorted.length} entries · Page {safePage}/{totalPages} 
                    </span>
                    <div className="flex items-center gap-1">
                        <button
                            onClick={() => setPage(p => Math.max(1, p - 1))}
                            disabled={safePage <= 1}
                            className="p-1 rounded hover:bg-slate-200 dark:hover:bg-slate-700 text-slate-500 disabled:opacity-30 transition-colors"
                        >
                            <ChevronLeft className="w-4 h-4" />
                        </button>
                        {Array.from({ length: totalPages }, (_, i) => i + 1)
                            .filter(p => p === 1 || p === totalPages || Math.abs(p - safePage) <= 1)
                            .map((p, idx, arr) => (
                                <React.Fragment key={p}>
                                    {idx > 0 && arr[idx - 1] !== p - 1 && (
                                        <span className="text-[10px] text-slate-400 px-0.5">...</span>
                                    )}
                                    <button
                                        onClick={() => setPage(p)}
                                        className={`w-6 h-6 rounded text-xs font-medium transition-all ${p === safePage
                                            ? 'bg-indigo-500 text-white shadow shadow-indigo-500/20'
                                            : 'text-slate-500 hover:bg-slate-200 dark:hover:bg-slate-700'
                                            }`}
                                    >
                                        {p}
                                    </button>
                                </React.Fragment>
                            ))}
                        <button
                            onClick={() => setPage(p => Math.min(totalPages, p + 1))}
                            disabled={safePage >= totalPages}
                            className="p-1 rounded hover:bg-slate-200 dark:hover:bg-slate-700 text-slate-500 disabled:opacity-30 transition-colors"
                        >
                            <PageRight className="w-4 h-4" />
                        </button>
                    </div>
                </div>
            )}
        </div>
    );
}

export default DataTable;
