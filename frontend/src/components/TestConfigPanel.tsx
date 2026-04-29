import React, { useState } from 'react';
import { BrainCircuit, Link, Loader2, Eye, Bookmark, ChevronDown, Settings2 } from './icons';
import type { AISettings } from '../types';
import { RESOURCE_PACK_MODEL } from '../config/aiModelConfig';

interface TestConfigPanelProps {
    requirement: string;
    setRequirement: (val: string) => void;
    targetUrl: string;
    setTargetUrl: (val: string) => void;
    probeMode: boolean;
    setProbeMode: (val: boolean) => void;
    useMultiAgent: boolean;
    setUseMultiAgent: (val: boolean) => void;
    aiSettings: AISettings;
    isPlanning: boolean;
    isExecuting: boolean;
    onGeneratePlan: () => void;
    onQuickDiagnose?: () => void;
    onOpenSettings?: () => void;
}

const TestConfigPanel: React.FC<TestConfigPanelProps> = ({
    requirement, setRequirement, targetUrl, setTargetUrl,
    probeMode, setProbeMode, useMultiAgent, setUseMultiAgent, aiSettings,
    isPlanning, isExecuting, onGeneratePlan, onQuickDiagnose, onOpenSettings
}) => {
    const extractUrl = () => {
        const urlMatch = requirement.match(/(https?:\/\/[a-zA-Z0-9\-._~:/?#[\]@!$&'*+,;=%]+)/);
        if (urlMatch) {
            const cleaned = urlMatch[0].replace(/[)}\]，。、；]+$/, '');
            setTargetUrl(cleaned);
        } else {
            alert("未在需求描述中找到有效的 URL 链接。");
        }
    };

    const [showTemplates, setShowTemplates] = useState(false);

    const TEMPLATES = [
        { name: '登录流程', prompt: '测试登录功能：输入正确用户名和密码登录，验证登录成功后跳转；测试错误密码提示；测试空输入校验；检查密码显示/隐藏切换' },
        { name: '表单验证', prompt: '测试表单验证：必填字段空提交提示；邮箱格式验证；电话号格式验证；密码强度提示；提交成功后的反馈信息' },
        { name: '购物流程', prompt: '测试电商购物流程：浏览商品列表；搜索商品；添加到购物车；修改数量；填写收货地址；选择支付方式；提交订单' },
        { name: '搜索功能', prompt: '测试搜索功能：输入关键词搜索；验证搜索结果相关性；测试空搜索提示；测试特殊字符搜索；检查结果分页和排序' },
        { name: '用户注册', prompt: '测试用户注册流程：填写注册表单；邮箱重复检查；密码确认一致性；服务条款勾选；注册成功蛤验证邮件提示' },
        { name: '页面导航', prompt: '测试页面导航：检查所有导航链接可点击；验证页面跳转正确；检查面包屑导航；测试浏览器后退/前进按钮；检查 404 页面处理' },
    ];

    return (
        <div className="rounded-xl border border-slate-200 dark:border-slate-800 bg-white/50 dark:bg-slate-900/50 p-6 backdrop-blur-md">
            {/* Header: Title + Controls */}
            <div className="mb-4 space-y-3">
                <div className="flex items-center justify-between">
                    <h2 className="text-lg font-bold text-slate-900 dark:text-white flex items-center gap-2">
                        <BrainCircuit className="w-5 h-5 text-indigo-400" />
                        测试配置
                    </h2>
                    <div className="flex items-center gap-2">
                        <button
                            onClick={onQuickDiagnose}
                            disabled={isPlanning || isExecuting || !targetUrl}
                            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-blue-50 dark:bg-blue-900/20 text-blue-600 dark:text-blue-400 text-xs font-medium hover:bg-blue-100 dark:hover:bg-blue-900/30 transition-colors whitespace-nowrap disabled:opacity-50"
                        >
                            <Eye className="w-3 h-3" />
                            快速诊断
                        </button>
                        <button
                            onClick={extractUrl}
                            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-indigo-50 dark:bg-indigo-900/20 text-indigo-600 dark:text-indigo-400 text-xs font-medium hover:bg-indigo-100 dark:hover:bg-indigo-900/30 transition-colors whitespace-nowrap"
                        >
                            <Link className="w-3 h-3" />
                            提取链接
                        </button>
                    </div>
                </div>

                <div className="flex items-center gap-2">
                    {/* Model Configuration Button */}
                    <button
                        type="button"
                        onClick={onOpenSettings}
                        disabled={isPlanning || isExecuting}
                            className={`flex-1 flex items-center justify-between gap-2 px-3 py-1.5 rounded-lg text-xs border shadow-sm transition-all focus-within:ring-1 focus-within:ring-indigo-500
                            ${isPlanning || isExecuting ? 'opacity-50 cursor-not-allowed bg-slate-100/50 dark:bg-slate-800/50 border-slate-200 dark:border-slate-700' : 'cursor-pointer bg-slate-100 dark:bg-slate-700/50 border-slate-200 dark:border-slate-600 hover:border-indigo-300 dark:hover:border-indigo-500 hover:bg-white dark:hover:bg-slate-800'}
                        `}
                        title="点击配置系统核心模型"
                    >
                        <div className="flex items-center gap-2 overflow-hidden">
                            <span className="font-bold text-slate-500 text-[10px] uppercase shrink-0">当前模型</span>
                            <span className="font-mono text-indigo-600 dark:text-indigo-400 font-semibold truncate" title={aiSettings.modelName || RESOURCE_PACK_MODEL}>
                                {aiSettings.modelName || RESOURCE_PACK_MODEL}
                            </span>
                        </div>
                        <Settings2 className="w-3.5 h-3.5 text-slate-400 shrink-0" />
                    </button>

                    {/* Multi-Agent Toggle */}
                    <label className="flex items-center gap-2 cursor-pointer bg-slate-100 dark:bg-slate-700/50 px-3 py-1.5 rounded-lg border border-slate-200 dark:border-slate-600 transition-all hover:bg-slate-200 dark:hover:bg-slate-600 shrink-0 shadow-sm">
                        <span className="text-xs font-medium text-slate-600 dark:text-slate-300 select-none">多智能体协同</span>
                        <div className="relative">
                            <input
                                type="checkbox"
                                className="peer sr-only"
                                checked={useMultiAgent}
                                onChange={(e) => setUseMultiAgent(e.target.checked)}
                            />
                            <div className="w-8 h-4 bg-slate-300 dark:bg-slate-600 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:start-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-3 after:w-3 after:transition-all dark:border-gray-600 peer-checked:bg-indigo-600"></div>
                        </div>
                    </label>

                    <label className="flex items-center gap-2 cursor-pointer bg-emerald-50 dark:bg-emerald-900/20 px-3 py-1.5 rounded-lg border border-emerald-200 dark:border-emerald-700 transition-all hover:bg-emerald-100 dark:hover:bg-emerald-900/30 shrink-0 shadow-sm">
                        <span className="text-xs font-medium text-emerald-700 dark:text-emerald-300 select-none">只读探针</span>
                        <div className="relative">
                            <input
                                type="checkbox"
                                className="peer sr-only"
                                checked={probeMode}
                                onChange={(e) => setProbeMode(e.target.checked)}
                            />
                            <div className="w-8 h-4 bg-emerald-200 dark:bg-emerald-800 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:start-[2px] after:bg-white after:border-emerald-300 after:border after:rounded-full after:h-3 after:w-3 after:transition-all dark:border-emerald-700 peer-checked:bg-emerald-600"></div>
                        </div>
                    </label>
                </div>
            </div>

            <div className="space-y-4">
                {/* Test Templates */}
                <div>
                    <button
                        onClick={() => setShowTemplates(!showTemplates)}
                        className="flex items-center gap-1.5 text-xs text-slate-500 hover:text-indigo-500 font-medium mb-2 transition-colors"
                    >
                        <Bookmark className="w-3 h-3" />
                        测试模板
                        <ChevronDown className={`w-3 h-3 transition-transform ${showTemplates ? 'rotate-180' : ''}`} />
                    </button>
                    {showTemplates && (
                        <div className="grid grid-cols-2 gap-1.5 mb-3 animate-in slide-in-from-top-2 duration-200">
                            {TEMPLATES.map(t => (
                                <button
                                    key={t.name}
                                    onClick={() => { setRequirement(t.prompt); setShowTemplates(false); }}
                                    disabled={isPlanning || isExecuting}
                                    className="text-left px-2.5 py-2 rounded-lg bg-slate-50 dark:bg-slate-800/50 border border-slate-200 dark:border-slate-700 text-xs text-slate-600 dark:text-slate-300 hover:border-indigo-400 hover:bg-indigo-50 dark:hover:bg-indigo-900/20 transition-all disabled:opacity-50 truncate"
                                    title={t.prompt}
                                >
                                    {t.name}
                                </button>
                            ))}
                        </div>
                    )}
                </div>

                {/* Prompt Input */}
                <div>
                    <label className="text-xs text-slate-600 dark:text-slate-400 font-medium mb-1.5 block ml-1">测试需求 (Prompt)</label>
                    <textarea
                        className="w-full h-24 bg-slate-50 dark:bg-slate-900 border border-slate-300 dark:border-slate-700 rounded-lg p-3 text-sm text-slate-900 dark:text-slate-200 focus:ring-2 focus:ring-indigo-500 focus:outline-none resize-none placeholder-slate-400 dark:placeholder-slate-500 custom-scrollbar"
                        placeholder="例如: 登录系统并检查个人中心..."
                        value={requirement}
                        onChange={(e) => setRequirement(e.target.value)}
                        disabled={isPlanning || isExecuting}
                    />
                </div>

                {/* Target URL Input */}
                <div>
                    <label className="text-xs text-slate-600 dark:text-slate-400 font-medium mb-1.5 block ml-1">目标网站 URL (可选)</label>
                    <input
                        type="text"
                        className="w-full bg-slate-50 dark:bg-slate-900 border border-slate-300 dark:border-slate-700 rounded-lg px-3 py-2 text-sm text-slate-900 dark:text-slate-200 focus:ring-2 focus:ring-indigo-500 focus:outline-none placeholder-slate-400 dark:placeholder-slate-500"
                        placeholder="https://example.com"
                        value={targetUrl}
                        onChange={(e) => setTargetUrl(e.target.value)}
                    />
                </div>

                {probeMode && (
                    <div className="rounded-lg border border-emerald-200 dark:border-emerald-800 bg-emerald-50/80 dark:bg-emerald-950/30 px-3 py-2 text-xs text-emerald-700 dark:text-emerald-300">
                        只读探针已开启：平台只会做页面可访问性与首屏可见性检查，不会尝试登录、输入、提交或写入数据。
                    </div>
                )}

                <div className="pt-4">
                    <button
                        onClick={onGeneratePlan}
                        disabled={isPlanning || isExecuting || !requirement}
                        className="w-full flex items-center justify-center gap-2 bg-indigo-600 hover:bg-indigo-500 text-white py-2.5 px-6 rounded-lg font-medium transition-all shadow-lg shadow-indigo-500/20 hover:shadow-indigo-500/30 disabled:opacity-50 disabled:cursor-not-allowed active:scale-[0.98]"
                    >
                        {isPlanning ? <Loader2 className="animate-spin w-4 h-4" /> : <BrainCircuit className="w-4 h-4" />}
                        自动化生成测试计划
                    </button>
                </div>
            </div>
        </div>
    );
};

export default TestConfigPanel;
