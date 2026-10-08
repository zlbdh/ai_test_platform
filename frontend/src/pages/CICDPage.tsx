import React, { useState, useCallback, useEffect } from 'react';
import {
    Webhook, RefreshCw, Play, Copy, CheckCircle2, XCircle,
    Clock, Download, Eye, EyeOff, Terminal, GitBranch,
    Settings2, Activity, FileText, Shield, Github, ChevronRight,
} from '../components/icons';
import Badge from '../components/ui/Badge';
import PageHeader from '../components/ui/PageHeader';
import DataTable, { type DataTableColumn } from '../components/ui/DataTable';
import {
    getCICDConfig, updateCICDConfig, getCICDSecret, getCICDHistory,
    triggerWebhook, getJunitReportUrl, getHtmlReportUrl,
    type CICDConfig, type TriggerRecord,
} from '../services/cicdService';
import StatCard from '../components/ui/StatCard';
import { statusBadge } from '../components/deploy/deployMeta';
import { useAsync } from '../hooks';



// ============================================================================
// CI/CD Page
// ============================================================================
const CICDPage: React.FC = () => {
    const [config, setConfig] = useState<CICDConfig | null>(null);
    const [history, setHistory] = useState<TriggerRecord[]>([]);
    const { loading, run } = useAsync({ initialLoading: true });
    const { loading: triggering, run: runTrigger } = useAsync();
    const [showSecret, setShowSecret] = useState(false);
    const [secret, setSecret] = useState<string>('');
    const [triggerSource, setTriggerSource] = useState<string>('manual');
    const [triggerRef, setTriggerRef] = useState<string>('main');
    const [copied, setCopied] = useState(false);
    // Wizard state
    const [wizardOpen, setWizardOpen] = useState(false);
    const [wizardStep, setWizardStep] = useState(0);
    const [wizardPlatform, setWizardPlatform] = useState<'github' | 'gitlab'>('github');
    const [wizardToken, setWizardToken] = useState('');
    const [wizardRepo, setWizardRepo] = useState('');
    const [wizardBranch, setWizardBranch] = useState('main');
    const [wizardGenerated, setWizardGenerated] = useState('');

    const load = useCallback(() => run(async () => {
        const [cfg, hist] = await Promise.all([getCICDConfig(), getCICDHistory()]);
        setConfig(cfg);
        setHistory(hist);
    }), [run]);

    useEffect(() => { load(); }, [load]);

    const handleToggle = async () => {
        if (!config) return;
        const updated = await updateCICDConfig({ enabled: !config.enabled });
        setConfig(updated);
    };

    const handleRevealSecret = async () => {
        if (showSecret) { setShowSecret(false); return; }
        const s = await getCICDSecret();
        setSecret(s);
        setShowSecret(true);
    };

    const handleCopySecret = () => {
        navigator.clipboard.writeText(secret);
        setCopied(true);
        setTimeout(() => setCopied(false), 2000);
    };

    const handleTrigger = () => runTrigger(async () => {
        await triggerWebhook(triggerSource, triggerRef);
        await load();
    });

    // ── Table Columns ──
    const columns: DataTableColumn<TriggerRecord>[] = [
        { key: 'id', title: 'ID', width: '80px', render: (v) => <code className="text-xs font-mono">{String(v)}</code> },
        {
            key: 'source', title: "Source", sortable: true, render: (v) => (
                <span className="inline-flex items-center gap-1.5 text-sm">
                    <GitBranch className="w-3.5 h-3.5 text-slate-400" />{String(v)}
                </span>
            )
        },
        { key: 'ref', title: "Branch/tag", sortable: true },
        { key: 'commit', title: 'Commit', width: '90px', render: (v) => <code className="text-xs font-mono">{String(v).slice(0, 8)}</code> },
        { key: 'status', title: "Status", sortable: true, render: (v) => statusBadge(String(v)) },
        { key: 'test_count', title: "Test cases", align: 'center' as const, sortable: true },
        { key: 'passed_count', title: "Passed", align: 'center' as const, render: (v) => <span className="text-emerald-500 font-medium">{String(v)}</span> },
        { key: 'failed_count', title: "Failed", align: 'center' as const, render: (v) => <span className={`font-medium ${Number(v) > 0 ? 'text-red-500' : 'text-slate-400'}`}>{String(v)}</span> },
        { key: 'duration_ms', title: "Duration", sortable: true, align: 'right' as const, render: (v) => `${(Number(v) / 1000).toFixed(1)}s` },
        { key: 'triggered_at', title: "Time", sortable: true, render: (v) => new Date(String(v)).toLocaleString('en-US', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' }) },
        {
            key: 'report_actions', title: "Report", align: 'center' as const, render: (_v, record) => (
                <div className="flex items-center gap-1">
                    <a href={getJunitReportUrl(record.id)} className="p-1 rounded hover:bg-slate-100 dark:hover:bg-slate-800 text-slate-400 hover:text-slate-600" title="JUnit XML" target="_blank" rel="noreferrer">
                        <FileText className="w-3.5 h-3.5" />
                    </a>
                    <a href={getHtmlReportUrl(record.id)} className="p-1 rounded hover:bg-slate-100 dark:hover:bg-slate-800 text-slate-400 hover:text-slate-600" title={"HTML report"} target="_blank" rel="noreferrer">
                        <Download className="w-3.5 h-3.5" />
                    </a>
                </div>
            )
        },
    ];

    // ── Stats ──
    const totalTriggers = history.length;
    const passedTotal = history.filter(t => t.status === 'completed' || t.status === 'passed').length;
    const failedTotal = history.filter(t => t.status === 'failed').length;
    const avgDuration = totalTriggers > 0 ? (history.reduce((s, t) => s + t.duration_ms, 0) / totalTriggers / 1000).toFixed(1) : '0';

    if (loading) {
        return (
            <div className="flex items-center justify-center h-64 text-slate-400">
                <RefreshCw className="w-6 h-6 animate-spin mr-2" /> Loading...
            </div>
        );
    }

    return (
        <div className="space-y-6 max-w-7xl mx-auto">
            <PageHeader
                icon={<Webhook className="w-5 h-5" />}
                title={"CI/CD integration management"}
                description={"Configure webhooks, view trigger history, and download test reports"}
                accent="indigo"
                actions={
                    <button onClick={load} className="p-2 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-800 text-slate-400 transition-colors" title={"Refresh"}>
                        <RefreshCw className="w-4 h-4" />
                    </button>
                }
            />

            {/* Stats */}
            <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
                <StatCard icon={<Activity className="w-5 h-5" />} label={"Total triggers"} value={totalTriggers} gradient="bg-gradient-to-br from-indigo-500 to-indigo-700" />
                <StatCard icon={<CheckCircle2 className="w-5 h-5" />} label={"Success"} value={passedTotal} gradient="bg-gradient-to-br from-emerald-500 to-emerald-700" />
                <StatCard icon={<XCircle className="w-5 h-5" />} label={"Failed"} value={failedTotal} gradient="bg-gradient-to-br from-red-500 to-red-700" />
                <StatCard icon={<Clock className="w-5 h-5" />} label={"Average duration"} value={`${avgDuration}s`} gradient="bg-gradient-to-br from-amber-500 to-amber-700" />
            </div>

            <div className="grid lg:grid-cols-3 gap-6">
                {/* ── Config Panel ── */}
                <div className="lg:col-span-1 space-y-4">
                    {/* Enable/Disable */}
                    <div className="rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 p-4 space-y-4">
                        <div className="flex items-center justify-between">
                            <h3 className="text-sm font-semibold flex items-center gap-2 text-slate-700 dark:text-slate-200">
                                <Settings2 className="w-4 h-4 text-indigo-500" />
                                Integration configuration
                            </h3>
                            <button
                                onClick={handleToggle}
                                className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${config?.enabled ? 'bg-indigo-500' : 'bg-slate-300 dark:bg-slate-600'}`}
                            >
                                <span className={`inline-block h-4 w-4 transform rounded-full bg-white transition ${config?.enabled ? 'translate-x-6' : 'translate-x-1'}`} />
                            </button>
                        </div>

                        <div className="text-xs text-slate-500 dark:text-slate-400 space-y-2">
                            <div className="flex justify-between"><span>Status</span>{config?.enabled ? <Badge variant="success" size="sm">Enabled</Badge> : <Badge variant="neutral" size="sm">Disabled</Badge>}</div>
                            <div className="flex justify-between"><span>Created at</span><span>{config?.created_at ? new Date(config.created_at).toLocaleDateString('en-US') : '-'}</span></div>
                        </div>
                    </div>

                    {/* Webhook URL & Secret */}
                    <div className="rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 p-4 space-y-3">
                        <h3 className="text-sm font-semibold flex items-center gap-2 text-slate-700 dark:text-slate-200">
                            <Shield className="w-4 h-4 text-amber-500" />
                            Webhook
                        </h3>
                        <div className="space-y-2">
                            <label className="block text-[10px] font-medium uppercase tracking-wider text-slate-400">URL</label>
                            <code className="block w-full text-xs bg-slate-50 dark:bg-slate-800 rounded-lg px-3 py-2 text-slate-600 dark:text-slate-300 break-all">
                                {config?.webhook_url || 'POST /api/ci/webhook'}
                            </code>
                        </div>
                        <div className="space-y-2">
                            <label className="block text-[10px] font-medium uppercase tracking-wider text-slate-400">Secret</label>
                            <div className="flex items-center gap-1.5">
                                <code className="flex-1 text-xs bg-slate-50 dark:bg-slate-800 rounded-lg px-3 py-2 text-slate-600 dark:text-slate-300 truncate">
                                    {showSecret ? secret : config?.webhook_secret_masked || '****'}
                                </code>
                                <button onClick={handleRevealSecret} className="p-1.5 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-800 text-slate-400" title={showSecret ? "Hide" : "Show"}>
                                    {showSecret ? <EyeOff className="w-3.5 h-3.5" /> : <Eye className="w-3.5 h-3.5" />}
                                </button>
                                {showSecret && (
                                    <button onClick={handleCopySecret} className="p-1.5 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-800 text-slate-400" title={"Copy"}>
                                        {copied ? <CheckCircle2 className="w-3.5 h-3.5 text-emerald-500" /> : <Copy className="w-3.5 h-3.5" />}
                                    </button>
                                )}
                            </div>
                        </div>
                    </div>

                    {/* Manual Trigger */}
                    <div className="rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 p-4 space-y-3">
                        <h3 className="text-sm font-semibold flex items-center gap-2 text-slate-700 dark:text-slate-200">
                            <Terminal className="w-4 h-4 text-emerald-500" />
                            Trigger manually
                        </h3>
                        <div className="space-y-2">
                            <select
                                value={triggerSource}
                                onChange={e => setTriggerSource(e.target.value)}
                                className="w-full text-xs rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 px-3 py-2 outline-none focus:ring-2 focus:ring-indigo-500/30"
                            >
                                <option value="manual">Trigger manually</option>
                                <option value="jenkins">Jenkins</option>
                                <option value="gitlab">GitLab CI</option>
                                <option value="github">GitHub Actions</option>
                            </select>
                            <input
                                type="text"
                                value={triggerRef}
                                onChange={e => setTriggerRef(e.target.value)}
                                placeholder={"Branch name (for example, main)"}
                                className="w-full text-xs rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 px-3 py-2 outline-none focus:ring-2 focus:ring-indigo-500/30"
                            />
                            <button
                                onClick={handleTrigger}
                                disabled={triggering || !config?.enabled}
                                className="w-full flex items-center justify-center gap-2 rounded-lg bg-indigo-500 hover:bg-indigo-600 text-white text-xs font-medium py-2 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                            >
                                {triggering ? <RefreshCw className="w-3.5 h-3.5 animate-spin" /> : <Play className="w-3.5 h-3.5" />}
                                {triggering ? "Triggering..." : "Trigger test"}
                            </button>
                        </div>
                    </div>

                    {/* GitHub/GitLab Connect Wizard */}
                    <div className="rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 overflow-hidden">
                        <button onClick={() => { setWizardOpen(!wizardOpen); setWizardStep(0); }}
                            className="w-full p-4 flex items-center justify-between hover:bg-slate-50 dark:hover:bg-slate-800/50 transition">
                            <h3 className="text-sm font-semibold flex items-center gap-2 text-slate-700 dark:text-slate-200">
                                <Github className="w-4 h-4 text-slate-700 dark:text-white" />
                                Direct connection guide
                            </h3>
                            <ChevronRight className={`w-3.5 h-3.5 text-slate-400 transition-transform ${wizardOpen ? 'rotate-90' : ''}`} />
                        </button>
                        {wizardOpen && (
                            <div className="border-t border-slate-200 dark:border-slate-800 p-4 space-y-4">
                                {/* Step indicator */}
                                <div className="flex items-center gap-2">
                                    {["Select platform", "Enter credentials", "Configure workflow"].map((label, i) => (
                                        <React.Fragment key={i}>
                                            <div className={`flex items-center gap-1 text-[10px] font-medium px-2 py-1 rounded-full transition ${wizardStep >= i
                                                ? 'bg-indigo-100 dark:bg-indigo-500/20 text-indigo-600 dark:text-indigo-400'
                                                : 'bg-slate-100 dark:bg-slate-800 text-slate-400'}`}>
                                                <span className="w-4 h-4 rounded-full flex items-center justify-center text-[9px] bg-current/10">{i + 1}</span>
                                                {label}
                                            </div>
                                            {i < 2 && <ChevronRight className="w-3 h-3 text-slate-300" />}
                                        </React.Fragment>
                                    ))}
                                </div>

                                {/* Step 0: Platform Select */}
                                {wizardStep === 0 && (
                                    <div className="grid grid-cols-2 gap-2">
                                        {(['github', 'gitlab'] as const).map(p => (
                                            <button key={p} onClick={() => { setWizardPlatform(p); setWizardStep(1); }}
                                                className={`flex flex-col items-center gap-2 p-4 rounded-lg border-2 transition-all ${wizardPlatform === p
                                                    ? 'border-indigo-400 bg-indigo-50 dark:bg-indigo-900/20'
                                                    : 'border-slate-200 dark:border-slate-700 hover:border-indigo-300'}`}>
                                                {p === 'github' ? <Github className="w-6 h-6" /> : <GitBranch className="w-6 h-6 text-orange-500" />}
                                                <span className="text-xs font-medium">{p === 'github' ? 'GitHub' : 'GitLab'}</span>
                                            </button>
                                        ))}
                                    </div>
                                )}

                                {/* Step 1: Credentials */}
                                {wizardStep === 1 && (
                                    <div className="space-y-2">
                                        <div>
                                            <label className="text-[10px] text-slate-500 uppercase font-semibold tracking-wider">
                                                {wizardPlatform === 'github' ? 'Personal Access Token' : 'Private Token'}
                                            </label>
                                            <input type="password" value={wizardToken} onChange={e => setWizardToken(e.target.value)}
                                                placeholder={wizardPlatform === 'github' ? 'ghp_xxxxxxxxxxxx' : 'glpat-xxxxxxxxxxxx'}
                                                className="w-full text-xs rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 px-3 py-2 outline-none focus:ring-2 focus:ring-indigo-500/30 font-mono" />
                                        </div>
                                        <div>
                                            <label className="text-[10px] text-slate-500 uppercase font-semibold tracking-wider">Repository</label>
                                            <input type="text" value={wizardRepo} onChange={e => setWizardRepo(e.target.value)}
                                                placeholder={wizardPlatform === 'github' ? 'owner/repo' : 'group/project'}
                                                className="w-full text-xs rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 px-3 py-2 outline-none focus:ring-2 focus:ring-indigo-500/30 font-mono" />
                                        </div>
                                        <div>
                                            <label className="text-[10px] text-slate-500 uppercase font-semibold tracking-wider">Branch</label>
                                            <input type="text" value={wizardBranch} onChange={e => setWizardBranch(e.target.value)}
                                                placeholder="main"
                                                className="w-full text-xs rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 px-3 py-2 outline-none focus:ring-2 focus:ring-indigo-500/30 font-mono" />
                                        </div>
                                        <div className="flex gap-2 pt-1">
                                            <button onClick={() => setWizardStep(0)} className="flex-1 text-xs py-2 rounded-lg border border-slate-200 dark:border-slate-700 text-slate-500 hover:bg-slate-50 dark:hover:bg-slate-800 transition">Back</button>
                                            <button onClick={() => {
                                                // Generate workflow config
                                                const webhookUrl = config?.webhook_url || 'https://your-server/api/ci/webhook';
                                                if (wizardPlatform === 'github') {
                                                    setWizardGenerated(`# .github/workflows/ai-test.yml
name: AI Test Platform
on:
  push:
    branches: [${wizardBranch}]
  pull_request:
    branches: [${wizardBranch}]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Trigger AI Tests
        run: |
          curl -X POST ${webhookUrl} \\
            -H "Content-Type: application/json" \\
            -H "X-Hub-Signature: \${{ secrets.WEBHOOK_SECRET }}" \\
            -d '{"source":"github","ref":"\${{ github.ref }}","commit":"\${{ github.sha }}"}'`);
                                                } else {
                                                    /* eslint-disable no-useless-escape */
                                                    setWizardGenerated(`# .gitlab-ci.yml
stages:
  - test

ai_test:
  stage: test
  only:
    - ${wizardBranch}
  script:
    - |
      curl -X POST ${webhookUrl} \\
        -H "Content-Type: application/json" \\
        -H "X-Gitlab-Token: \$WEBHOOK_SECRET" \\
        -d '{"source":"gitlab","ref":"'\$CI_COMMIT_REF_NAME'","commit":"'\$CI_COMMIT_SHA'"}'`);
                                                }
                                                /* eslint-enable no-useless-escape */
                                                setWizardStep(2);
                                            }} disabled={!wizardToken || !wizardRepo}
                                                className="flex-1 text-xs py-2 rounded-lg bg-indigo-500 hover:bg-indigo-600 text-white font-medium transition disabled:opacity-50">Next</button>
                                        </div>
                                    </div>
                                )}

                                {/* Step 2: Generated Config */}
                                {wizardStep === 2 && (
                                    <div className="space-y-2">
                                        <p className="text-[11px] text-slate-500">Add the following configuration to your repository <code className="text-indigo-500">{wizardRepo}</code>:</p>
                                        <pre className="text-[11px] font-mono bg-slate-50 dark:bg-slate-800 rounded-lg p-3 overflow-auto max-h-40 text-slate-600 dark:text-slate-400 whitespace-pre-wrap">{wizardGenerated}</pre>
                                        <div className="flex gap-2">
                                            <button onClick={() => setWizardStep(1)} className="flex-1 text-xs py-2 rounded-lg border border-slate-200 dark:border-slate-700 text-slate-500 hover:bg-slate-50 dark:hover:bg-slate-800 transition">Back</button>
                                            <button onClick={() => { navigator.clipboard.writeText(wizardGenerated); }}
                                                className="flex-1 flex items-center justify-center gap-1 text-xs py-2 rounded-lg bg-emerald-500 hover:bg-emerald-600 text-white font-medium transition">
                                                <Copy className="w-3 h-3" /> Copy configuration
                                            </button>
                                        </div>
                                        <p className="text-[10px] text-slate-400">✅ Paste the copied configuration into your repository to complete integration</p>
                                    </div>
                                )}
                            </div>
                        )}
                    </div>
                </div>

                {/* ── History Table ── */}
                <div className="lg:col-span-2">
                    <DataTable<TriggerRecord>
                        columns={columns}
                        data={history}
                        rowKey="id"
                        pageSize={8}
                        emptyText={"No trigger records yet. Start a test through a webhook or manual trigger."}
                    />
                </div>
            </div>
        </div>
    );
};

export default CICDPage;
