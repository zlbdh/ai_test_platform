/**
 * useAsync — 统一异步操作状态管理 Hook
 *
 * 消除 10+ 页面中重复的 [loading, setLoading] + try/catch/finally 模式。
 *
 * @example
 *   const { loading, error, run } = useAsync();
 *
 *   const load = useCallback(() => run(async () => {
 *       const data = await fetchProjects();
 *       setProjects(data);
 *   }), [run]);
 *
 *   useEffect(() => { load(); }, [load]);
 */
import { useState, useCallback, useRef } from 'react';

interface UseAsyncOptions {
    /** 初始 loading 状态，默认 false */
    initialLoading?: boolean;
    /** 错误回调 */
    onError?: (error: Error) => void;
}

interface UseAsyncReturn {
    /** 是否正在加载 */
    loading: boolean;
    /** 最近一次错误 */
    error: Error | null;
    /** 包裹异步函数，自动管理 loading/error */
    run: <T>(fn: () => Promise<T>) => Promise<T | undefined>;
    /** 手动设置 loading */
    setLoading: (v: boolean) => void;
    /** 清除错误 */
    clearError: () => void;
}

export function useAsync(options: UseAsyncOptions = {}): UseAsyncReturn {
    const { initialLoading = false, onError } = options;
    const [loading, setLoading] = useState(initialLoading);
    const [error, setError] = useState<Error | null>(null);
    const mountedRef = useRef(true);

    // 组件卸载后不更新状态
    const isMounted = useCallback(() => mountedRef.current, []);

    const run = useCallback(async <T>(fn: () => Promise<T>): Promise<T | undefined> => {
        setLoading(true);
        setError(null);
        try {
            const result = await fn();
            if (isMounted()) setLoading(false);
            return result;
        } catch (e) {
            const err = e instanceof Error ? e : new Error(String(e));
            if (isMounted()) {
                setError(err);
                setLoading(false);
            }
            onError?.(err);
            return undefined;
        }
    }, [isMounted, onError]);

    const clearError = useCallback(() => setError(null), []);

    return { loading, error, run, setLoading, clearError };
}

export default useAsync;
