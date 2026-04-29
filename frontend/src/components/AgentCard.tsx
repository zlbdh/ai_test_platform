
import React from 'react';
import { AgentStat, AgentType } from '../types';
import { Bot, Database, Globe, Server, Activity, AlertCircle, Sparkles } from './icons';

interface AgentCardProps {
    stat: AgentStat;
}

const AgentCard: React.FC<AgentCardProps> = ({ stat }) => {
    const getIcon = () => {
        switch (stat.id) {
            case AgentType.UI: return <Globe className="w-6 h-6" />;
            case AgentType.API: return <Server className="w-6 h-6" />;
            case AgentType.DATA: return <Database className="w-6 h-6" />;
            case AgentType.RCA: return <AlertCircle className="w-6 h-6" />;
            default: return <Bot className="w-6 h-6" />;
        }
    };

    const getStatusColor = () => {
        switch (stat.status) {
            case 'BUSY': return 'text-amber-400 border-amber-400/30 bg-amber-400/10';
            case 'ERROR': return 'text-red-400 border-red-400/30 bg-red-400/10';
            case 'HEALING': return 'text-purple-400 border-purple-400/30 bg-purple-400/10';
            default: return 'text-emerald-400 border-emerald-400/30 bg-emerald-400/10';
        }
    };

    const getStatusLabel = (status: string) => {
        switch (status) {
            case 'IDLE': return '空闲';
            case 'BUSY': return '忙碌';
            case 'ERROR': return '异常';
            case 'HEALING': return '自愈中';
            default: return status;
        }
    };



    return (
        <div className={`relative overflow-hidden rounded-xl border p-6 backdrop-blur-sm transition-all ${stat.status === 'HEALING'
            ? 'border-purple-500/50 bg-purple-500/5 shadow-[0_0_15px_rgba(168,85,247,0.15)]'
            : 'border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800/50 hover:border-slate-300 dark:hover:border-slate-600'
            }`}>
            <div className="flex items-start justify-between">
                <div className="flex items-center gap-3">
                    <div className={`rounded-lg p-2 ${getStatusColor()}`}>
                        {getIcon()}
                    </div>
                    <div>
                        <h3 className="text-lg font-semibold text-slate-900 dark:text-white">{stat.name}</h3>
                        <p className="text-xs text-slate-500 dark:text-slate-400">{stat.role}</p>
                    </div>
                </div>
                <div className="flex flex-col items-end gap-2">
                    <div className={`flex items-center gap-2 rounded-full px-3 py-1 text-xs font-medium border ${getStatusColor()}`}>
                        {stat.status === 'HEALING' ? <Sparkles className="w-3 h-3 animate-pulse" /> : <Activity className="w-3 h-3" />}
                        {getStatusLabel(stat.status)}
                    </div>
                </div>
            </div>

            <div className="mt-6 grid grid-cols-2 gap-4">
                <div>
                    <p className="text-xs text-slate-500 dark:text-slate-400">已完成任务</p>
                    <p className="text-xl font-mono text-slate-900 dark:text-slate-200">{stat.tasksCompleted}</p>
                </div>
                <div>
                    <p className="text-xs text-slate-500 dark:text-slate-400">成功率</p>
                    <p className="text-xl font-mono text-slate-900 dark:text-slate-200">{stat.successRate}%</p>
                </div>
            </div>

            {/* Animated background pulse for busy/healing state */}
            {stat.status === 'BUSY' && (
                <div className="absolute inset-0 -z-10 animate-pulse bg-amber-500/5" />
            )}
            {stat.status === 'HEALING' && (
                <div className="absolute inset-0 -z-10 animate-pulse bg-purple-500/10" />
            )}
        </div>
    );
};

export default AgentCard;
