import React, { useState } from 'react';
import { ChevronLeft, ChevronRight, SplitSquareHorizontal, Layers, Camera, X } from './icons';

interface ScreenshotDiffProps {
    beforeSrc: string;
    afterSrc: string;
    beforeLabel: string;
    afterLabel: string;
    onClose: () => void;
}

type ViewMode = 'side-by-side' | 'overlay';

const ScreenshotDiff: React.FC<ScreenshotDiffProps> = ({
    beforeSrc,
    afterSrc,
    beforeLabel,
    afterLabel,
    onClose,
}) => {
    const [viewMode, setViewMode] = useState<ViewMode>('side-by-side');
    const [overlayOpacity, setOverlayOpacity] = useState(50);

    return (
        <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur-xl flex flex-col animate-in fade-in duration-300">
            {/* Header */}
            <div className="flex items-center justify-between px-6 py-3 border-b border-white/10 bg-gradient-to-r from-white/5 to-transparent">
                <div className="flex items-center gap-4">
                    <h3 className="text-sm font-bold text-white flex items-center gap-2">
                        <Camera className="w-4 h-4 text-indigo-400" /> 截图对比
                    </h3>
                    {/* View mode toggle */}
                    <div className="flex bg-white/10 rounded-lg p-0.5">
                        <button
                            onClick={() => setViewMode('side-by-side')}
                            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium transition-all ${viewMode === 'side-by-side'
                                ? 'bg-indigo-500 text-white shadow-lg'
                                : 'text-white/60 hover:text-white'
                                }`}
                        >
                            <SplitSquareHorizontal className="w-3.5 h-3.5" />
                            并排对比
                        </button>
                        <button
                            onClick={() => setViewMode('overlay')}
                            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium transition-all ${viewMode === 'overlay'
                                ? 'bg-indigo-500 text-white shadow-lg'
                                : 'text-white/60 hover:text-white'
                                }`}
                        >
                            <Layers className="w-3.5 h-3.5" />
                            叠加对比
                        </button>
                    </div>
                </div>
                <button
                    onClick={onClose}
                    className="text-white/60 hover:text-white text-sm px-3 py-1.5 rounded-lg hover:bg-white/10 transition-all focus:outline-none focus:ring-2 focus:ring-indigo-500/40"
                >
                    <X className="w-4 h-4 inline" /> 关闭
                </button>
            </div>

            {/* Content */}
            <div className="flex-1 p-6 overflow-hidden">
                {viewMode === 'side-by-side' ? (
                    /* ── 并排对比模式 ── */
                    <div className="flex gap-4 h-full">
                        {/* Before */}
                        <div className="flex-1 flex flex-col min-w-0">
                            <div className="flex items-center gap-2 mb-2">
                                <ChevronLeft className="w-3.5 h-3.5 text-amber-400" />
                                <span className="text-xs font-bold text-amber-400 uppercase tracking-wider">之前</span>
                                <span className="text-[10px] text-white/40 truncate max-w-[200px]">{beforeLabel}</span>
                            </div>
                            <div className="flex-1 rounded-xl border border-amber-500/30 overflow-hidden bg-slate-950/80 backdrop-blur-sm flex items-center justify-center shadow-lg shadow-amber-500/5">
                                <img
                                    src={beforeSrc}
                                    className="max-w-full max-h-full object-contain"
                                    alt="before"
                                />
                            </div>
                        </div>

                        {/* Divider */}
                        <div className="flex flex-col items-center justify-center gap-2">
                            <div className="w-px flex-1 bg-white/10" />
                            <span className="text-white/30 text-lg">→</span>
                            <div className="w-px flex-1 bg-white/10" />
                        </div>

                        {/* After */}
                        <div className="flex-1 flex flex-col min-w-0">
                            <div className="flex items-center gap-2 mb-2">
                                <ChevronRight className="w-3.5 h-3.5 text-emerald-400" />
                                <span className="text-xs font-bold text-emerald-400 uppercase tracking-wider">之后</span>
                                <span className="text-[10px] text-white/40 truncate max-w-[200px]">{afterLabel}</span>
                            </div>
                            <div className="flex-1 rounded-xl border border-emerald-500/30 overflow-hidden bg-slate-950/80 backdrop-blur-sm flex items-center justify-center shadow-lg shadow-emerald-500/5">
                                <img
                                    src={afterSrc}
                                    className="max-w-full max-h-full object-contain"
                                    alt="after"
                                />
                            </div>
                        </div>
                    </div>
                ) : (
                    /* ── 叠加对比模式 ── */
                    <div className="flex flex-col h-full">
                        {/* Slider */}
                        <div className="flex items-center gap-3 mb-4">
                            <span className="text-[10px] text-amber-400 font-bold uppercase">之前</span>
                            <input
                                type="range"
                                min="0"
                                max="100"
                                value={overlayOpacity}
                                onChange={(e) => setOverlayOpacity(Number(e.target.value))}
                                className="flex-1 h-1.5 accent-indigo-500"
                            />
                            <span className="text-[10px] text-emerald-400 font-bold uppercase">之后</span>
                            <span className="text-[10px] text-white/40 font-mono w-10 text-right">{overlayOpacity}%</span>
                        </div>

                        {/* Overlay container */}
                        <div className="flex-1 rounded-xl border border-white/10 overflow-hidden bg-slate-950/80 backdrop-blur-sm relative flex items-center justify-center shadow-lg">
                            {/* Before (bottom layer) */}
                            <img
                                src={beforeSrc}
                                className="max-w-full max-h-full object-contain absolute"
                                alt="before"
                            />
                            {/* After (top layer with opacity) */}
                            <img
                                src={afterSrc}
                                className="max-w-full max-h-full object-contain absolute"
                                style={{ opacity: overlayOpacity / 100 }}
                                alt="after"
                            />
                        </div>

                        {/* Labels */}
                        <div className="flex items-center justify-between mt-2 text-[10px] text-white/30">
                            <span>{beforeLabel}</span>
                            <span>{afterLabel}</span>
                        </div>
                    </div>
                )}
            </div>
        </div>
    );
};

export default ScreenshotDiff;
