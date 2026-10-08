import React from 'react';

/** StatCard: shared statistics card extracted from six pages, with basic and enhanced modes.
 * @example Basic mode
 *   <StatCard icon={<Activity />} label="Total" value={42}
 *            gradient="bg-gradient-to-br from-indigo-500 to-indigo-700" />
 * @example Enhanced mode with a unit and subtitle
 *   <StatCard icon={<Timer />} label="Average latency" value="120" unit="ms"
 *            gradient="bg-gradient-to-br from-cyan-500 to-cyan-700"
 *            subValue="Range: 10–500 ms" />
 */
export const StatCard: React.FC<{
    icon: React.ReactNode;
    label: string;
    value: string | number;
    gradient: string;
    /** Optional value unit, such as ms, req/s, or %. */
    unit?: string;
    /** Optional subtitle. */
    subValue?: string;
}> = ({ icon, label, value, gradient, unit, subValue }) => (
    <div className={`relative overflow-hidden rounded-2xl p-5 text-white shadow-lg ${gradient}`}>
        <div className="absolute -right-4 -top-4 h-24 w-24 rounded-full bg-white/10 blur-2xl" />
        <div className="relative z-10 flex items-start justify-between">
            <div>
                <p className="text-sm font-medium text-white/80">{label}</p>
                <div className="mt-1 flex items-baseline gap-1">
                    <span className="text-3xl font-extrabold tracking-tight">{value}</span>
                    {unit && <span className="text-sm text-white/60">{unit}</span>}
                </div>
                {subValue && <p className="text-[11px] text-white/50 mt-1">{subValue}</p>}
            </div>
            <div className="rounded-xl bg-white/20 p-2.5">{icon}</div>
        </div>
    </div>
);

export default StatCard;
