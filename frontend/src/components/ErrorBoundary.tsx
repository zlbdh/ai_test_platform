import React from 'react';

interface Props {
    children: React.ReactNode;
    fallback?: React.ReactNode;
}

interface State {
    hasError: boolean;
    error: Error | null;
}

/**
 * 全局 Error Boundary — 防止子组件 JS 崩溃导致白屏
 */
class ErrorBoundary extends React.Component<Props, State> {
    constructor(props: Props) {
        super(props);
        this.state = { hasError: false, error: null };
    }

    static getDerivedStateFromError(error: Error): State {
        return { hasError: true, error };
    }

    componentDidCatch(error: Error, errorInfo: React.ErrorInfo) {
        console.error('[ErrorBoundary]', error, errorInfo);
    }

    handleRetry = () => {
        this.setState({ hasError: false, error: null });
    };

    render() {
        if (this.state.hasError) {
            if (this.props.fallback) return this.props.fallback;

            return (
                <div className="flex flex-col items-center justify-center min-h-[40vh] text-center px-6">
                    <div className="w-16 h-16 mb-4 rounded-2xl bg-red-50 dark:bg-red-500/10 flex items-center justify-center">
                        <svg className="w-8 h-8 text-red-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                                d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4.5c-.77-.833-2.694-.833-3.464 0L3.34 16.5c-.77.833.192 2.5 1.732 2.5z" />
                        </svg>
                    </div>
                    <h2 className="text-lg font-semibold text-slate-800 dark:text-slate-200 mb-2">
                        页面加载出错
                    </h2>
                    <p className="text-sm text-slate-500 dark:text-slate-400 mb-4 max-w-md">
                        {this.state.error?.message || '发生了一个未预期的错误'}
                    </p>
                    <button
                        onClick={this.handleRetry}
                        className="px-4 py-2 rounded-lg bg-indigo-500 text-white text-sm font-medium
                                   hover:bg-indigo-600 transition-colors"
                    >
                        重试
                    </button>
                </div>
            );
        }

        return this.props.children;
    }
}

export default ErrorBoundary;
