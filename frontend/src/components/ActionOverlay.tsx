import React, { useState, useCallback } from 'react';

// ── 操作类型识别 ──
interface ParsedAction {
    type: string;
    icon: string;
    label: string;
    detail: string;
    color: string;
    timestamp: string;
}

const ACTION_PATTERNS: { pattern: RegExp; type: string; icon: string; color: string }[] = [
    { pattern: /goto|navigate|打开|访问|跳转/i, type: 'goto', icon: '', color: '#3b82f6' },
    { pattern: /click|点击|按钮/i, type: 'click', icon: '', color: '#10b981' },
    { pattern: /fill|input|输入|填写|type/i, type: 'fill', icon: '', color: '#8b5cf6' },
    { pattern: /assert|验证|检查|断言|expect/i, type: 'assert', icon: '', color: '#f59e0b' },
    { pattern: /wait|等待|sleep/i, type: 'wait', icon: '', color: '#6b7280' },
    { pattern: /screenshot|截图|截屏/i, type: 'screenshot', icon: '', color: '#6366f1' },
    { pattern: /scroll|滚动/i, type: 'scroll', icon: '', color: '#14b8a6' },
    { pattern: /hover|悬停/i, type: 'hover', icon: '', color: '#ec4899' },
    { pattern: /select|选择/i, type: 'select', icon: '', color: '#06b6d4' },
    { pattern: /key|按键|键盘|enter/i, type: 'key', icon: '', color: '#f97316' },
    { pattern: /success|成功|通过|passed/i, type: 'success', icon: '', color: '#22c55e' },
    { pattern: /error|失败|fail|错误/i, type: 'error', icon: '', color: '#ef4444' },
    { pattern: /heal|自愈|修复/i, type: 'heal', icon: '', color: '#a855f7' },
];

function parseAction(text: string): ParsedAction {
    const now = new Date().toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit', second: '2-digit' });
    const trimmed = text.slice(0, 120);

    for (const { pattern, type, icon, color } of ACTION_PATTERNS) {
        if (pattern.test(trimmed)) {
            return { type, icon, label: type.toUpperCase(), detail: trimmed, color, timestamp: now };
        }
    }
    return { type: 'action', icon: '▶', label: 'ACTION', detail: trimmed, color: '#94a3b8', timestamp: now };
}

// ── ActionOverlay 主组件 ──
interface ActionOverlayProps {
    currentAction: string;
    isActive: boolean;
}

const MAX_HISTORY = 5;

const ActionOverlay: React.FC<ActionOverlayProps> = ({ currentAction, isActive }) => {
    const [lastAction, setLastAction] = useState('');
    const [activeAction, setActiveAction] = useState<ParsedAction | null>(null);
    const [history, setHistory] = useState<ParsedAction[]>([]);
    const [isNew, setIsNew] = useState(false);

    // 操作变化处理 — 通过回调触发而非 effect
    const processAction = useCallback((action: string) => {
        const parsed = parseAction(action);
        setActiveAction(parsed);
        setIsNew(true);
        setHistory(prev => [parsed, ...prev].slice(0, MAX_HISTORY));
        // 动画重置
        setTimeout(() => setIsNew(false), 600);
    }, []);

    // 检测 currentAction 变化 — 用条件渲染触发
    if (isActive && currentAction && currentAction !== lastAction) {
        setLastAction(currentAction);
        processAction(currentAction);
    }

    if (!isActive) return null;

    return (
        <>
            {/* ── 当前操作标签 — 顶部居中弹入 ── */}
            {activeAction && (
                <div className={`absolute top-3 left-1/2 -translate-x-1/2 z-20 transition-all duration-300 ${isNew ? 'animate-bounce-in' : ''}`}>
                    <div
                        className="flex items-center gap-2 px-3 py-1.5 rounded-full shadow-lg backdrop-blur-md border"
                        style={{
                            backgroundColor: `${activeAction.color}20`,
                            borderColor: `${activeAction.color}40`,
                        }}
                    >
                        <span className="text-base">{activeAction.icon}</span>
                        <span
                            className="text-[11px] font-bold uppercase tracking-wider"
                            style={{ color: activeAction.color }}
                        >
                            {activeAction.label}
                        </span>
                        <span className="text-[10px] text-white/70 max-w-[200px] truncate">
                            {activeAction.detail.slice(0, 40)}
                        </span>
                    </div>
                </div>
            )}

            {/* ── 操作历史轨迹 — 右侧迷你时间线 ── */}
            {history.length > 0 && (
                <div className="absolute top-12 right-2 z-20 flex flex-col gap-1 pointer-events-none">
                    {history.map((h, i) => (
                        <div
                            key={`${h.timestamp}-${i}`}
                            className="flex items-center gap-1.5 px-2 py-1 rounded-md backdrop-blur-sm transition-opacity duration-500"
                            style={{
                                backgroundColor: 'rgba(0,0,0,0.5)',
                                opacity: 1 - i * 0.18,
                            }}
                        >
                            <span className="text-xs">{h.icon}</span>
                            <span
                                className="text-[9px] font-bold uppercase"
                                style={{ color: h.color }}
                            >
                                {h.label}
                            </span>
                            <span className="text-[9px] text-white/40">{h.timestamp}</span>
                        </div>
                    ))}
                </div>
            )}
        </>
    );
};

export default ActionOverlay;
