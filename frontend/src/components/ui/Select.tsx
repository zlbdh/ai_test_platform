import React from 'react';
import { ChevronDown } from '../icons';

interface SelectOption {
    value: string;
    label: string;
    disabled?: boolean;
}

interface SelectProps {
    value: string;
    onChange: (value: string) => void;
    options: SelectOption[];
    placeholder?: string;
    label?: string;
    disabled?: boolean;
    className?: string;
    size?: 'sm' | 'md' | 'lg';
}

const sizeClasses = {
    sm: 'text-xs py-1.5 pl-3 pr-8',
    md: 'text-sm py-2 pl-3 pr-8',
    lg: 'text-base py-2.5 pl-4 pr-10',
};

const Select: React.FC<SelectProps> = ({
    value, onChange, options, placeholder = '请选择...', label, disabled = false, className = '', size = 'md',
}) => (
    <div className={className}>
        {label && (
            <label className="block text-xs font-medium text-slate-500 dark:text-slate-400 mb-1.5 uppercase tracking-wider">
                {label}
            </label>
        )}
        <div className="relative">
            <select
                value={value}
                onChange={(e) => onChange(e.target.value)}
                disabled={disabled}
                className={`w-full rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-900 dark:text-white appearance-none cursor-pointer transition-all duration-200 focus:ring-2 focus:ring-indigo-500/30 focus:border-indigo-500 hover:border-indigo-300 dark:hover:border-indigo-500/40 outline-none disabled:opacity-50 disabled:cursor-not-allowed ${sizeClasses[size]}`}
            >
                {placeholder && <option value="" disabled>{placeholder}</option>}
                {options.map((opt) => (
                    <option key={opt.value} value={opt.value} disabled={opt.disabled}>
                        {opt.label}
                    </option>
                ))}
            </select>
            <div className="pointer-events-none absolute inset-y-0 right-0 flex items-center pr-2.5">
                <ChevronDown className="w-4 h-4 text-slate-400 transition-transform" />
            </div>
        </div>
    </div>
);

export default Select;
