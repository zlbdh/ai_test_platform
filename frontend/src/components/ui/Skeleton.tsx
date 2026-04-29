import React from 'react';

interface SkeletonProps {
    className?: string;
    variant?: 'text' | 'circular' | 'rectangular';
    width?: string | number;
    height?: string | number;
    lines?: number;
}

const Skeleton: React.FC<SkeletonProps> = ({
    className = '', variant = 'text', width, height, lines = 1,
}) => {
    const baseClass = 'animate-pulse bg-slate-200 dark:bg-slate-700';

    const style: React.CSSProperties = {
        width: width ?? (variant === 'circular' ? height : '100%'),
        height: height ?? (variant === 'text' ? '1rem' : undefined),
    };

    const radiusClass = variant === 'circular'
        ? 'rounded-full'
        : variant === 'text'
            ? 'rounded-md'
            : 'rounded-lg';

    if (lines > 1) {
        return (
            <div className={`space-y-2 ${className}`}>
                {Array.from({ length: lines }, (_, i) => (
                    <div
                        key={i}
                        className={`${baseClass} ${radiusClass}`}
                        style={{ ...style, width: i === lines - 1 ? '75%' : style.width }}
                    />
                ))}
            </div>
        );
    }

    return <div className={`${baseClass} ${radiusClass} ${className}`} style={style} />;
};

/** Pre-built skeleton for card layouts */
export const CardSkeleton: React.FC<{ className?: string }> = ({ className }) => (
    <div className={`rounded-xl border border-slate-200 dark:border-slate-800 p-4 space-y-3 ${className || ''}`}>
        <div className="flex items-center gap-3">
            <Skeleton variant="circular" width={40} height={40} />
            <div className="flex-1 space-y-1.5">
                <Skeleton width="60%" height={14} />
                <Skeleton width="40%" height={10} />
            </div>
        </div>
        <Skeleton lines={3} />
    </div>
);

/** Pre-built skeleton for table rows */
export const TableRowSkeleton: React.FC<{ cols?: number }> = ({ cols = 5 }) => (
    <div className="flex items-center gap-4 py-3 px-4">
        {Array.from({ length: cols }, (_, i) => (
            <Skeleton key={i} width={i === 0 ? '30%' : `${60 / (cols - 1)}%`} height={12} />
        ))}
    </div>
);

export default Skeleton;
