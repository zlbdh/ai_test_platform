import React, { useState, useRef, useCallback } from 'react';
import { Play, FileJson, Layers, CheckCircle, XCircle, AlertTriangle, Upload, FileSpreadsheet, X } from './icons';
import { API_ENDPOINTS } from '../config';

interface BatchResult {
    task_id: string;
    task: string;
    status: 'success' | 'error';
    logs: unknown[];
}

const BatchTesting: React.FC = () => {
    const [batchName, setBatchName] = useState('New Batch');
    const [taskTemplate, setTaskTemplate] = useState('Search for {keyword} on Baidu');
    const [datasetStr, setDatasetStr] = useState('[{"keyword": "AI"}, {"keyword": "Playwright"}]');
    const [results, setResults] = useState<BatchResult[]>([]);
    const [isRunning, setIsRunning] = useState(false);
    const [summary, setSummary] = useState('');
    const [csvFile, setCsvFile] = useState<File | null>(null);
    const [csvPreview, setCsvPreview] = useState<Record<string, string>[]>([]);
    const [isDragOver, setIsDragOver] = useState(false);
    const fileInputRef = useRef<HTMLInputElement>(null);

    // CSV parser
    const parseCSV = useCallback((text: string) => {
        const lines = text.trim().split(/\r?\n/);
        if (lines.length < 2) return [];
        const sep = lines[0].includes('\t') ? '\t' : ',';
        const headers = lines[0].split(sep).map(h => h.trim().replace(/^"|"$/g, ''));
        const rows: Record<string, string>[] = [];
        for (let i = 1; i < lines.length; i++) {
            const vals = lines[i].split(sep).map(v => v.trim().replace(/^"|"$/g, ''));
            if (vals.length !== headers.length) continue;
            const row: Record<string, string> = {};
            headers.forEach((h, j) => { row[h] = vals[j]; });
            rows.push(row);
        }
        return rows;
    }, []);

    const handleFileSelect = useCallback((file: File) => {
        if (!file.name.match(/\.(csv|tsv|txt)$/i)) {
            alert('请选择 .csv / .tsv / .txt 文件');
            return;
        }
        setCsvFile(file);
        const reader = new FileReader();
        reader.onload = (e) => {
            const text = e.target?.result as string;
            const data = parseCSV(text);
            setCsvPreview(data);
            setDatasetStr(JSON.stringify(data, null, 2));
        };
        reader.readAsText(file);
    }, [parseCSV]);

    const handleDrop = useCallback((e: React.DragEvent) => {
        e.preventDefault();
        setIsDragOver(false);
        const file = e.dataTransfer.files?.[0];
        if (file) handleFileSelect(file);
    }, [handleFileSelect]);

    const clearCsv = () => {
        setCsvFile(null);
        setCsvPreview([]);
        if (fileInputRef.current) fileInputRef.current.value = '';
    };

    const handleRunBatch = async () => {
        try {
            const dataset = JSON.parse(datasetStr);
            if (!Array.isArray(dataset)) {
                alert("Dataset must be a JSON array.");
                return;
            }

            setIsRunning(true);
            setResults([]);
            setSummary('Running batch...');

            const payload = {
                batch_name: batchName,
                task_template: taskTemplate,
                dataset: dataset
            };

            const response = await fetch(API_ENDPOINTS.batch.run, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });

            const data = await response.json();

            if (data.details) {
                setResults(data.details);
            }
            if (data.summary) {
                setSummary(data.summary);
            }

        } catch (e: unknown) {
            setSummary(`Error: ${(e as Error).message}`);
        } finally {
            setIsRunning(false);
        }
    };

    return (
        <div className="flex h-full gap-6 animate-in fade-in duration-500">
            {/* Left: Config */}
            <div className="w-1/3 flex flex-col gap-4 overflow-y-auto pr-2">
                <div className="relative overflow-hidden rounded-xl border border-slate-200 dark:border-slate-800 bg-white/50 dark:bg-slate-900/50 backdrop-blur-md p-6 shadow-sm transition-all hover:border-slate-300 dark:hover:border-slate-700">
                    <h3 className="text-lg font-bold text-slate-900 dark:text-white mb-6 flex items-center gap-3">
                        <div className="p-2 rounded-lg bg-indigo-500/10">
                            <Layers className="w-5 h-5 text-indigo-500" />
                        </div>
                        批量测试配置
                    </h3>

                    <div className="space-y-5">
                        <div>
                            <label className="text-xs font-semibold text-slate-500 uppercase mb-2 block tracking-wider">批次名称</label>
                            <input
                                type="text"
                                className="w-full bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg p-3 text-sm text-slate-900 dark:text-white focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500 transition-all outline-none"
                                value={batchName}
                                onChange={e => setBatchName(e.target.value)}
                            />
                        </div>

                        <div>
                            <label className="text-xs font-semibold text-slate-500 uppercase mb-2 block tracking-wider">任务模板 (Task Template)</label>
                            <textarea
                                className="w-full h-24 bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg p-3 text-sm text-slate-900 dark:text-white focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500 transition-all outline-none"
                                value={taskTemplate}
                                onChange={e => setTaskTemplate(e.target.value)}
                                placeholder="Use {variable} for interpolation"
                            />
                            <p className="text-xs text-slate-400 mt-2 flex items-center gap-1">
                                <span className="bg-slate-200 dark:bg-slate-700 px-1 rounded text-[10px] font-mono">VAR</span>
                                支持变量替换，例如: <code>Login as {"{user}"}</code>
                            </p>
                        </div>

                        <div>
                            <label className="text-xs font-semibold text-slate-500 uppercase mb-2 flex items-center gap-2 tracking-wider">
                                <FileJson className="w-3 h-3" /> 数据集 (JSON Array)
                            </label>
                            <textarea
                                className="w-full h-32 bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg p-3 text-sm font-mono text-slate-900 dark:text-slate-300 focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500 transition-all outline-none"
                                value={datasetStr}
                                onChange={e => setDatasetStr(e.target.value)}
                                placeholder='[{"user": "admin"}, {"user": "guest"}]'
                            />
                        </div>

                        {/* CSV Upload */}
                        <div>
                            <label className="text-xs font-semibold text-slate-500 uppercase mb-2 flex items-center gap-2 tracking-wider">
                                <FileSpreadsheet className="w-3 h-3" /> 或从 CSV 文件导入
                            </label>
                            <div
                                onDragOver={e => { e.preventDefault(); setIsDragOver(true); }}
                                onDragLeave={() => setIsDragOver(false)}
                                onDrop={handleDrop}
                                onClick={() => fileInputRef.current?.click()}
                                className={`border-2 border-dashed rounded-lg p-4 text-center cursor-pointer transition-all ${isDragOver
                                    ? 'border-indigo-400 bg-indigo-50 dark:bg-indigo-900/20'
                                    : csvFile
                                        ? 'border-emerald-300 bg-emerald-50 dark:bg-emerald-900/10'
                                        : 'border-slate-300 dark:border-slate-600 hover:border-indigo-300 bg-slate-50/50 dark:bg-slate-800/50'
                                    }`}
                            >
                                <input
                                    ref={fileInputRef}
                                    type="file"
                                    accept=".csv,.tsv,.txt"
                                    className="hidden"
                                    onChange={e => { const f = e.target.files?.[0]; if (f) handleFileSelect(f); }}
                                />
                                {csvFile ? (
                                    <div className="flex items-center justify-center gap-2">
                                        <FileSpreadsheet className="w-4 h-4 text-emerald-500" />
                                        <span className="text-sm text-emerald-600 dark:text-emerald-400 font-medium">{csvFile.name}</span>
                                        <span className="text-[10px] text-slate-400">({csvPreview.length} 行)</span>
                                        <button onClick={e => { e.stopPropagation(); clearCsv(); }}
                                            className="p-1 hover:bg-red-100 dark:hover:bg-red-900/20 rounded transition-colors">
                                            <X className="w-3 h-3 text-red-500" />
                                        </button>
                                    </div>
                                ) : (
                                    <div>
                                        <Upload className="w-6 h-6 text-slate-400 mx-auto mb-1" />
                                        <p className="text-xs text-slate-400">拖拽 CSV 文件到此处，或点击选择</p>
                                        <p className="text-[10px] text-slate-300 dark:text-slate-500 mt-0.5">支持 .csv .tsv .txt</p>
                                    </div>
                                )}
                            </div>

                            {/* CSV Preview Table */}
                            {csvPreview.length > 0 && (
                                <div className="mt-2 max-h-32 overflow-auto rounded-lg border border-slate-200 dark:border-slate-700">
                                    <table className="w-full text-[11px]">
                                        <thead>
                                            <tr className="bg-slate-100 dark:bg-slate-800">
                                                {Object.keys(csvPreview[0]).map(k => (
                                                    <th key={k} className="px-2 py-1 text-left font-medium text-slate-500">{k}</th>
                                                ))}
                                            </tr>
                                        </thead>
                                        <tbody>
                                            {csvPreview.slice(0, 5).map((row, i) => (
                                                <tr key={i} className="border-t border-slate-100 dark:border-slate-800">
                                                    {Object.values(row).map((v, j) => (
                                                        <td key={j} className="px-2 py-1 text-slate-600 dark:text-slate-400 truncate max-w-[120px]">{v}</td>
                                                    ))}
                                                </tr>
                                            ))}
                                            {csvPreview.length > 5 && (
                                                <tr><td colSpan={Object.keys(csvPreview[0]).length} className="px-2 py-1 text-center text-slate-400">... 还有 {csvPreview.length - 5} 行</td></tr>
                                            )}
                                        </tbody>
                                    </table>
                                </div>
                            )}
                        </div>

                        <button
                            onClick={handleRunBatch}
                            disabled={isRunning}
                            className="w-full py-3 bg-gradient-to-r from-indigo-600 to-violet-600 hover:from-indigo-500 hover:to-violet-500 text-white rounded-lg font-medium shadow-lg shadow-indigo-500/20 hover:shadow-indigo-500/40 transition-all flex items-center justify-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed active:scale-95"
                        >
                            {isRunning ? (
                                <div className="flex items-center gap-2">
                                    <div className="w-4 h-4 rounded-full border-2 border-white/30 border-t-white animate-spin" />
                                    Running...
                                </div>
                            ) : (
                                <><Play className="w-4 h-4 fill-current" /> 开始批量执行</>
                            )}
                        </button>
                    </div>
                </div>
            </div>

            {/* Right: Results */}
            <div className="flex-1 flex flex-col relative overflow-hidden rounded-xl border border-slate-200 dark:border-slate-800 bg-white/50 dark:bg-slate-900/50 backdrop-blur-md shadow-sm transition-all">
                <div className="p-4 border-b border-slate-200 dark:border-slate-700 bg-slate-50/50 dark:bg-slate-900/50 flex justify-between items-center backdrop-blur-sm">
                    <h3 className="font-bold text-slate-900 dark:text-white flex items-center gap-2">
                        <CheckCircle className="w-5 h-5 text-emerald-500" />
                        执行结果
                    </h3>
                    <span className="text-xs font-mono px-2 py-1 rounded bg-slate-200 dark:bg-slate-800 text-slate-600 dark:text-slate-400">{summary}</span>
                </div>

                <div className="flex-1 overflow-y-auto p-4 space-y-3">
                    {results.length === 0 && !isRunning && (
                        <div className="text-center text-slate-400 mt-10">
                            等待执行...
                            <div className="mt-4 flex justify-center text-slate-300">
                                <AlertTriangle className="w-12 h-12" />
                            </div>
                        </div>
                    )}

                    {results.map((res: BatchResult, idx: number) => (
                        <div key={idx} className={`p-4 rounded-lg border ${res.status === 'success' ? 'border-emerald-200 bg-emerald-50 dark:bg-emerald-900/10' : 'border-red-200 bg-red-50 dark:bg-red-900/10'}`}>
                            <div className="flex justify-between items-start mb-2">
                                <div className="font-medium text-slate-900 dark:text-white">{res.task}</div>
                                {res.status === 'success' ? <CheckCircle className="w-5 h-5 text-emerald-500" /> : <XCircle className="w-5 h-5 text-red-500" />}
                            </div>
                            <div className="text-xs text-slate-500 font-mono">ID: {res.task_id}</div>

                            {res.logs && res.logs.length > 0 && (
                                <div className="mt-2 text-xs text-slate-600 bg-white/50 dark:bg-black/20 rounded p-2 max-h-20 overflow-y-auto">
                                    {res.logs.slice(-3).map((l: unknown, i: number) => (
                                        <div key={i}>{typeof l === 'string' ? l : (l as Record<string, unknown>).message as string}</div>
                                    ))}
                                </div>
                            )}
                        </div>
                    ))}
                </div>
            </div>
        </div>
    );
};

export default BatchTesting;
