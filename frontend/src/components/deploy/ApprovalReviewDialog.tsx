import React from 'react';
import { CheckCircle2, Loader2, X, XCircle } from '../icons';

interface ApprovalReviewDialogProps {
    open: boolean;
    action: 'approve' | 'reject';
    targetLabel: string;
    comment: string;
    submitting?: boolean;
    onCommentChange: (value: string) => void;
    onCancel: () => void;
    onSubmit: () => void;
}

const ApprovalReviewDialog: React.FC<ApprovalReviewDialogProps> = ({
    open,
    action,
    targetLabel,
    comment,
    submitting = false,
    onCommentChange,
    onCancel,
    onSubmit,
}) => {
    if (!open) return null;

    const isApprove = action === 'approve';
    const title = isApprove ? "Approve deployment" : "Reject deployment";
    const desc = isApprove
        ? "After you enter an approval note, the system immediately creates a deployment task and starts tracking its execution."
        : "After you enter a rejection reason, the approval request closes and deployment does not continue.";

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-md animate-in fade-in duration-300" onClick={submitting ? undefined : onCancel}>
            <div
                className="w-full max-w-lg rounded-2xl bg-white/95 dark:bg-slate-900/95 backdrop-blur-xl shadow-2xl border border-slate-200/80 dark:border-slate-700/80 overflow-hidden animate-in zoom-in-95 duration-300"
                onClick={e => e.stopPropagation()}
            >
                <div className={`px-6 py-4 flex items-center justify-between ${isApprove
                    ? 'bg-gradient-to-r from-emerald-500 to-teal-500'
                    : 'bg-gradient-to-r from-red-500 to-rose-500'
                    }`}>
                    <h3 className="text-sm font-bold text-white flex items-center gap-2">
                        {isApprove ? <CheckCircle2 className="w-4 h-4" /> : <XCircle className="w-4 h-4" />}
                        {title}
                    </h3>
                    <button
                        onClick={onCancel}
                        disabled={submitting}
                        className="text-white/70 hover:text-white transition disabled:opacity-40"
                        title={"Close"}
                    >
                        <X className="w-4 h-4" />
                    </button>
                </div>

                <div className="p-6 space-y-4">
                    <div className="rounded-xl border border-slate-200 dark:border-slate-700 bg-slate-50/80 dark:bg-slate-800/60 px-4 py-3">
                        <div className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider mb-1">Target</div>
                        <div className="text-sm font-semibold text-slate-800 dark:text-slate-100">{targetLabel || "Unnamed target"}</div>
                        <p className="text-xs text-slate-500 dark:text-slate-400 mt-1 leading-relaxed">{desc}</p>
                    </div>

                    <div>
                        <label className="block text-[11px] font-semibold text-slate-500 mb-2">
                            {isApprove ? "Approval note" : "Rejection reason"}
                        </label>
                        <textarea
                            value={comment}
                            onChange={e => onCommentChange(e.target.value)}
                            rows={4}
                            placeholder={isApprove ? "Example: The deployment window is confirmed. Proceed." : "Example: The change window has not started. Submit again later."}
                            className="w-full px-3 py-2.5 text-sm rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800/70 text-slate-700 dark:text-slate-200 outline-none focus:ring-2 focus:ring-cyan-500/30 focus:border-cyan-400 transition resize-none"
                        />
                    </div>
                </div>

                <div className="px-6 py-4 border-t border-slate-100 dark:border-slate-800 bg-slate-50/60 dark:bg-slate-800/30 flex justify-end gap-2">
                    <button
                        type="button"
                        onClick={onCancel}
                        disabled={submitting}
                        className="px-4 py-2 rounded-xl text-xs font-medium border border-slate-200 dark:border-slate-700 text-slate-500 hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors disabled:opacity-50"
                    >
                        Cancel
                    </button>
                    <button
                        type="button"
                        onClick={onSubmit}
                        disabled={submitting}
                        className={`px-4 py-2 rounded-xl text-xs font-semibold text-white transition-all disabled:opacity-60 flex items-center gap-1.5 ${isApprove
                            ? 'bg-gradient-to-r from-emerald-500 to-teal-500 hover:from-emerald-600 hover:to-teal-600'
                            : 'bg-gradient-to-r from-red-500 to-rose-500 hover:from-red-600 hover:to-rose-600'
                            }`}
                    >
                        {submitting ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : (isApprove ? <CheckCircle2 className="w-3.5 h-3.5" /> : <XCircle className="w-3.5 h-3.5" />)}
                        {isApprove ? "Confirm approval" : "Confirm rejection"}
                    </button>
                </div>
            </div>
        </div>
    );
};

export default ApprovalReviewDialog;
