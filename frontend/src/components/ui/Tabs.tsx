import React, { useState, type ReactNode } from 'react';

interface TabItem {
    key: string;
    label: string | ReactNode;
    content: ReactNode;
    disabled?: boolean;
}

interface TabsProps {
    items: TabItem[];
    defaultActiveKey?: string;
    activeKey?: string;
    onChange?: (key: string) => void;
    className?: string;
    variant?: 'pills' | 'underline';
}

const Tabs: React.FC<TabsProps> = ({
    items, defaultActiveKey, activeKey: controlledKey, onChange, className = '', variant = 'pills',
}) => {
    const [internalKey, setInternalKey] = useState(defaultActiveKey || items[0]?.key || '');
    const currentKey = controlledKey ?? internalKey;

    const handleClick = (key: string) => {
        if (!controlledKey) setInternalKey(key);
        onChange?.(key);
    };

    const activeItem = items.find(i => i.key === currentKey);

    const pillStyle = (active: boolean) =>
        active
            ? 'bg-white dark:bg-slate-700 text-indigo-600 dark:text-indigo-400 shadow-sm font-semibold'
            : 'text-slate-500 dark:text-slate-400 hover:text-slate-700 dark:hover:text-slate-300 hover:bg-white/50 dark:hover:bg-slate-700/50';

    const underlineStyle = (active: boolean) =>
        active
            ? 'border-b-2 border-indigo-500 text-indigo-600 dark:text-indigo-400 font-semibold'
            : 'border-b-2 border-transparent text-slate-500 dark:text-slate-400 hover:text-slate-700 dark:hover:text-slate-300 hover:border-slate-300 dark:hover:border-slate-600';

    return (
        <div className={className}>
            <div className={variant === 'pills'
                ? 'flex gap-1 bg-slate-100/80 dark:bg-slate-800/80 rounded-lg p-1 backdrop-blur-sm'
                : 'flex gap-4 border-b border-slate-200 dark:border-slate-700'
            }>
                {items.map(item => (
                    <button
                        key={item.key}
                        onClick={() => !item.disabled && handleClick(item.key)}
                        disabled={item.disabled}
                        className={`px-3 py-1.5 text-xs font-medium transition-all duration-200 cursor-pointer disabled:opacity-40 disabled:cursor-not-allowed ${variant === 'pills'
                            ? `rounded-md ${pillStyle(currentKey === item.key)}`
                            : `pb-2 ${underlineStyle(currentKey === item.key)}`
                            }`}
                    >
                        {item.label}
                    </button>
                ))}
            </div>
            {activeItem && (
                <div className="mt-3 animate-in fade-in duration-200">
                    {activeItem.content}
                </div>
            )}
        </div>
    );
};

export default Tabs;
