
import React, { useState, useEffect } from 'react';
import { Search, FileText, Database, Trash2, UploadCloud, RefreshCw, AlertCircle, Eye, Tag, X } from './icons';
import { API_ENDPOINTS } from '../config';

interface KnowledgeDoc {
    id: string; // usually filename or hash
    title: string;
    type: 'markdown' | 'pdf' | 'text' | 'unknown';
    size: string;
    updatedAt: string;
    status: 'indexed' | 'indexing' | 'error';
    path?: string;
    content?: string;
}

interface KnowledgeListItem {
    id?: string;
    content?: string;
    metadata?: Record<string, unknown>;
}

const inferDocType = (filename: string): KnowledgeDoc['type'] => {
    const lower = filename.toLowerCase();
    if (lower.endsWith('.md')) return 'markdown';
    if (lower.endsWith('.pdf')) return 'pdf';
    if (lower.endsWith('.txt') || lower.endsWith('.json') || lower.endsWith('.sql')) return 'text';
    return 'unknown';
};

const mapKnowledgeItem = (item: KnowledgeListItem): KnowledgeDoc => {
    const metadata = item.metadata || {};
    const filename = String(
        metadata.filename ||
        metadata.original_filename ||
        metadata.source ||
        item.id ||
        'Untitled'
    );
    const updatedAtRaw = metadata.updated_at || metadata.updatedAt;
    return {
        id: String(item.id || ''),
        title: filename,
        type: inferDocType(filename),
        size: metadata.size ? String(metadata.size) : 'Unknown',
        updatedAt: updatedAtRaw ? String(updatedAtRaw) : new Date().toLocaleDateString(),
        status: 'indexed',
        path: metadata.source_path ? String(metadata.source_path) : undefined,
        content: item.content || '',
    };
};

const KnowledgeBase: React.FC = () => {
    const [docs, setDocs] = useState<KnowledgeDoc[]>([]);
    const [isLoading, setIsLoading] = useState(false);
    const [searchQuery, setSearchQuery] = useState('');
    const [isUploading, setIsUploading] = useState(false);
    const fileInputRef = React.useRef<HTMLInputElement>(null);
    const [previewDoc, setPreviewDoc] = useState<KnowledgeDoc | null>(null);
    const [previewContent, setPreviewContent] = useState<string>('');
    const [previewLoading, setPreviewLoading] = useState(false);
    const [activeTag, setActiveTag] = useState<string>('all');

    const handlePreview = async (doc: KnowledgeDoc) => {
        setPreviewDoc(doc);
        setPreviewLoading(true);
        if (doc.content) {
            setPreviewContent(doc.content);
            setPreviewLoading(false);
            return;
        }
        try {
            const res = await fetch(API_ENDPOINTS.knowledge.content(doc.id));
            if (res.ok) {
                const data = await res.json();
                setPreviewContent(data.content || '无法加载内容');
            } else {
                setPreviewContent(`文档: ${doc.title}\n类型: ${doc.type}\n状态: ${doc.status}\n\n(预览接口暂未对接，请通过后端 API 实现)`);
            }
        } catch {
            setPreviewContent('加载失败');
        }
        setPreviewLoading(false);
    };

    const fetchDocs = async (signal?: AbortSignal) => {
        setIsLoading(true);
        try {
            const res = await fetch(API_ENDPOINTS.knowledge.list, { signal });
            const data = await res.json();
            if (data.status === 'success' && Array.isArray(data.items)) {
                const mappedDocs: KnowledgeDoc[] = data.items.map((item: KnowledgeListItem) => mapKnowledgeItem(item));
                setDocs(mappedDocs);
            }
        } catch (e) {
            if (!(e instanceof DOMException && e.name === 'AbortError')) {
                console.error("Failed to fetch knowledge:", e);
            }
        } finally {
            setIsLoading(false);
        }
    };

    useEffect(() => {
        const controller = new AbortController();
        fetchDocs(controller.signal);
        return () => controller.abort();
    }, []);

    const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
        if (!e.target.files?.length) return;
        const file = e.target.files[0];
        setIsUploading(true);

        const formData = new FormData();
        formData.append('file', file);
        formData.append('description', 'Uploaded via Web UI');

        try {
            const res = await fetch(API_ENDPOINTS.knowledge.upload, {
                method: 'POST',
                body: formData
            });
            if (res.ok) {
                await fetchDocs();
            } else {
                alert('Upload failed: ' + await res.text());
            }
        } catch (error) {
            console.error('Upload Error', error);
            alert('Upload Error');
        } finally {
            setIsUploading(false);
            if (fileInputRef.current) fileInputRef.current.value = '';
        }
    };

    const handleDelete = async (id: string, e: React.MouseEvent) => {
        e.stopPropagation();
        if (!confirm('Are you sure you want to delete this document?')) return;
        try {
            await fetch(API_ENDPOINTS.knowledge.delete(id), { method: 'DELETE' });
            await fetchDocs();
        } catch (error) {
            console.error('Delete Error', error);
        }
    };

    const filteredDocs = docs.filter(doc => {
        const matchSearch = doc.title.toLowerCase().includes(searchQuery.toLowerCase());
        const matchTag = activeTag === 'all' || doc.type === activeTag;
        return matchSearch && matchTag;
    });

    const docTypes = ['all', ...Array.from(new Set(docs.map(d => d.type)))];
    const tagLabels: Record<string, string> = { all: '全部', markdown: 'Markdown', pdf: 'PDF', text: '文本', unknown: '其他' };

    return (
        <div className="flex flex-col h-full gap-6 animate-in fade-in duration-500">
            {/* Header / Toolbar */}
            <div className="relative overflow-hidden rounded-xl border border-slate-200 dark:border-slate-800 bg-white/50 dark:bg-slate-900/50 backdrop-blur-md p-6 transition-all hover:border-slate-300 dark:hover:border-slate-700">
                <div className="flex items-center justify-between mb-4">
                    <div className="flex items-center gap-3">
                        <div className="p-2 rounded-lg bg-indigo-500/10">
                            <Database className="w-5 h-5 text-indigo-500" />
                        </div>
                        <div>
                            <h2 className="text-xl font-bold text-slate-900 dark:text-white">
                                知识库管理
                            </h2>
                            <p className="text-sm text-slate-500 mt-0.5">
                                管理用于 RAG 增强生成的文档上下文
                            </p>
                        </div>
                    </div>
                    <div className="flex gap-3">
                        <button
                            onClick={() => { void fetchDocs(); }}
                            className="p-2 text-slate-500 hover:text-indigo-600 transition-colors rounded-lg hover:bg-slate-100 dark:hover:bg-slate-800"
                            title="刷新列表"
                        >
                            <RefreshCw className={`w-5 h-5 ${isLoading ? 'animate-spin' : ''}`} />
                        </button>

                        <input
                            type="file"
                            ref={fileInputRef}
                            className="hidden"
                            onChange={handleFileUpload}
                            accept=".md,.txt,.json,.sql"
                        />

                        <button
                            onClick={() => fileInputRef.current?.click()}
                            disabled={isUploading}
                            className="flex items-center gap-2 px-4 py-2 bg-gradient-to-r from-indigo-600 to-violet-600 hover:from-indigo-500 hover:to-violet-500 text-white rounded-lg text-sm font-medium transition-all shadow-lg shadow-indigo-500/20 active:scale-95 disabled:opacity-50"
                        >
                            {isUploading ? <RefreshCw className="w-4 h-4 animate-spin" /> : <UploadCloud className="w-4 h-4" />}
                            {isUploading ? '上传中...' : '上传文件'}
                        </button>
                    </div>
                </div>

                {/* Search Bar */}
                <div className="relative">
                    <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-slate-400" />
                    <input
                        type="text"
                        placeholder="搜索文档..."
                        value={searchQuery}
                        onChange={(e) => setSearchQuery(e.target.value)}
                        className="w-full pl-10 pr-4 py-2.5 bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500 focus:outline-none transition-all text-sm"
                    />
                </div>

                {/* Tag Filters */}
                <div className="flex items-center gap-2 flex-wrap">
                    <Tag className="w-3.5 h-3.5 text-slate-400" />
                    {docTypes.map(tag => (
                        <button key={tag} onClick={() => setActiveTag(tag)}
                            className={`text-xs px-2.5 py-1 rounded-lg border transition-all ${activeTag === tag
                                ? 'bg-indigo-50 dark:bg-indigo-500/10 border-indigo-300 dark:border-indigo-500/30 text-indigo-600 dark:text-indigo-400'
                                : 'border-slate-200 dark:border-slate-700 text-slate-500 hover:border-indigo-300'}`}>
                            {tagLabels[tag] || tag}
                        </button>
                    ))}
                </div>
            </div>

            {/* Document List */}
            <div className="flex-1 rounded-xl border border-slate-200 dark:border-slate-800 bg-white/50 dark:bg-slate-900/50 backdrop-blur-md overflow-hidden flex flex-col shadow-sm transition-all hover:border-slate-300 dark:hover:border-slate-700">
                <div className="grid grid-cols-12 gap-4 p-4 border-b border-slate-200 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-800/50 text-xs font-semibold text-slate-500 uppercase tracking-wider backdrop-blur-sm">
                    <div className="col-span-6">文件名称</div>
                    <div className="col-span-2">类型</div>
                    <div className="col-span-2">状态</div>
                    <div className="col-span-2 text-right">操作</div>
                </div>

                <div className="flex-1 overflow-y-auto">
                    {filteredDocs.map(doc => (
                        <div key={doc.id} onClick={() => handlePreview(doc)} className="grid grid-cols-12 gap-4 p-4 items-center border-b border-slate-100 dark:border-slate-700/50 hover:bg-slate-50 dark:hover:bg-slate-700/30 transition-colors group cursor-pointer">
                            <div className="col-span-6 flex items-center gap-3">
                                <div className={`p-2 rounded-lg ${doc.type === 'pdf' ? 'bg-red-50 text-red-500' :
                                    doc.type === 'markdown' ? 'bg-blue-50 text-blue-500' : 'bg-slate-100 text-slate-500'
                                    }`}>
                                    <FileText className="w-5 h-5" />
                                </div>
                                <div>
                                    <div className="font-medium text-slate-900 dark:text-slate-200 truncate pr-4" title={doc.path}>{doc.title}</div>
                                    <div className="text-xs text-slate-400">{doc.updatedAt}</div>
                                </div>
                            </div>
                            <div className="col-span-2">
                                <span className="px-2 py-1 rounded-md bg-slate-100 dark:bg-slate-800 text-xs font-medium text-slate-600 dark:text-slate-400 border border-slate-200 dark:border-slate-700">
                                    {doc.type.toUpperCase()}
                                </span>
                            </div>
                            <div className="col-span-2">
                                <div className="flex items-center gap-2">
                                    <div className={`w-2 h-2 rounded-full ${doc.status === 'indexed' ? 'bg-emerald-500' :
                                        doc.status === 'indexing' ? 'bg-amber-500 animate-pulse' : 'bg-red-500'
                                        }`}></div>
                                    <span className={`text-sm ${doc.status === 'indexed' ? 'text-emerald-600' :
                                        doc.status === 'indexing' ? 'text-amber-600' : 'text-red-600'
                                        }`}>
                                        {doc.status === 'indexed' ? '已索引' : doc.status === 'indexing' ? '索引中...' : '失败'}
                                    </span>
                                </div>
                            </div>
                            <div className="col-span-2 text-right opacity-0 group-hover:opacity-100 transition-opacity">
                                <button
                                    onClick={(e) => handleDelete(doc.id, e)}
                                    className="p-2 hover:bg-red-50 text-slate-400 hover:text-red-500 rounded-lg transition-colors"
                                    title="删除文档"
                                >
                                    <Trash2 className="w-4 h-4" />
                                </button>
                            </div>
                        </div>
                    ))}

                    {filteredDocs.length === 0 && !isLoading && (
                        <div className="flex flex-col items-center justify-center h-64 text-slate-400">
                            <AlertCircle className="w-12 h-12 mb-4 opacity-20" />
                            <p>暂无文档，请上传.</p>
                        </div>
                    )}
                </div>
            </div>

            {/* Document Preview Panel */}
            {previewDoc && (
                <div className="fixed inset-y-0 right-0 w-full md:w-[420px] bg-white dark:bg-slate-900 border-l border-slate-200 dark:border-slate-800 shadow-2xl z-40 flex flex-col animate-in slide-in-from-right duration-300">
                    <div className="flex items-center justify-between px-5 py-4 border-b border-slate-200 dark:border-slate-800">
                        <div className="flex items-center gap-2">
                            <Eye className="w-4 h-4 text-indigo-500" />
                            <h3 className="text-sm font-bold text-slate-900 dark:text-white truncate">文档预览</h3>
                        </div>
                        <button onClick={() => setPreviewDoc(null)}
                            className="p-1.5 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-800 text-slate-400 transition">
                            <X className="w-4 h-4" />
                        </button>
                    </div>
                    <div className="px-5 py-3 border-b border-slate-100 dark:border-slate-800/50 space-y-1">
                        <h4 className="font-medium text-slate-800 dark:text-white text-sm">{previewDoc.title}</h4>
                        <div className="flex items-center gap-3 text-[11px] text-slate-400">
                            <span className={`px-2 py-0.5 rounded ${previewDoc.type === 'markdown' ? 'bg-blue-50 text-blue-500' :
                                previewDoc.type === 'pdf' ? 'bg-red-50 text-red-500' : 'bg-slate-100 text-slate-500'
                                }`}>{previewDoc.type.toUpperCase()}</span>
                            <span>{previewDoc.updatedAt}</span>
                            <span className={`${previewDoc.status === 'indexed' ? 'text-emerald-500' : 'text-amber-500'}`}>
                                {previewDoc.status === 'indexed' ? '✅ 已索引' : '⏳ 索引中'}
                            </span>
                        </div>
                    </div>
                    <div className="flex-1 overflow-y-auto px-5 py-4">
                        {previewLoading ? (
                            <div className="flex items-center gap-2 text-slate-400">
                                <RefreshCw className="w-4 h-4 animate-spin" /> 加载中...
                            </div>
                        ) : (
                            <pre className="text-xs font-mono text-slate-600 dark:text-slate-400 whitespace-pre-wrap break-words leading-relaxed">
                                {previewContent}
                            </pre>
                        )}
                    </div>
                </div>
            )}
        </div>
    );
};

export default KnowledgeBase;
