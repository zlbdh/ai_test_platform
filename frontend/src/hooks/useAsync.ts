/** useAsync: shared asynchronous operation state management.
 * Replaces repeated loading state and try/catch/finally patterns in more than ten pages.
 * @example
 *   const { loading, error, run } = useAsync();
 *   const load = useCallback(() => run(async () => {
 *       const data = await fetchProjects();
 *       setProjects(data);
 *   }), [run]);
 *   useEffect(() => { load(); }, [load]);
 */
import { useState, useCallback, useRef } from 'react';

interface UseAsyncOptions {
    /** Initial loading state; defaults to false. */
    initialLoading?: boolean;
    /** Error callback. */
    onError?: (error: Error) => void;
}

interface UseAsyncReturn {
    /** Whether an operation is loading. */
    loading: boolean;
    /** Most recent error. */
    error: Error | null;
    /** Wrap an asynchronous function to manage loading and error state. */
    run: <T>(fn: () => Promise<T>) => Promise<T | undefined>;
    /** Set loading manually. */
    setLoading: (v: boolean) => void;
    /** Clear the error. */
    clearError: () => void;
}

export function useAsync(options: UseAsyncOptions = {}): UseAsyncReturn {
    const { initialLoading = false, onError } = options;
    const [loading, setLoading] = useState(initialLoading);
    const [error, setError] = useState<Error | null>(null);
    const mountedRef = useRef(true);

    // Do not update state after unmounting.
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
