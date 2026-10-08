/** usePolling: shared polling hook for deployment progress, task status, and other periodic updates.
 * @example
 *   const { start, stop, active } = usePolling(async () => {
 *       const status = await fetchDeployStatus(repoId);
 *       setProgress(status);
 *       if (status.done) return false; // Return false to stop polling.
 *   }, { interval: 2000 });
 *   start(); // Start polling.
 *   stop(); // Stop manually.
 */
import { useState, useCallback, useRef, useEffect } from 'react';

interface UsePollingOptions {
    /** Polling interval in milliseconds; defaults to 3000. */
    interval?: number;
    /** Execute the first poll immediately; defaults to true. */
    immediate?: boolean;
    /** Maximum number of polls; 0 means unlimited. */
    maxRetries?: number;
}

interface UsePollingReturn {
    /** Start polling. */
    start: () => void;
    /** Stop polling. */
    stop: () => void;
    /** Whether polling is active. */
    active: boolean;
}

/** @param fn Polling function; returning false stops polling automatically.
 */
export function usePolling(
    fn: () => Promise<boolean | void>,
    options: UsePollingOptions = {},
): UsePollingReturn {
    const { interval = 3000, immediate = true, maxRetries = 0 } = options;
    const [active, setActive] = useState(false);
    const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
    const countRef = useRef(0);
    const fnRef = useRef(fn);

    useEffect(() => {
        fnRef.current = fn;
    }, [fn]);

    const stop = useCallback(() => {
        if (timerRef.current) {
            clearTimeout(timerRef.current);
            timerRef.current = null;
        }
        setActive(false);
        countRef.current = 0;
    }, []);

    const tick = useCallback(async function runPollingTick() {
        try {
            const shouldContinue = await fnRef.current();
            countRef.current++;

            if (shouldContinue === false) {
                stop();
                return;
            }
            if (maxRetries > 0 && countRef.current >= maxRetries) {
                stop();
                return;
            }
            timerRef.current = setTimeout(() => {
                void runPollingTick();
            }, interval);
        } catch {
            stop();
        }
    }, [interval, maxRetries, stop]);

    const start = useCallback(() => {
        stop();
        setActive(true);
        countRef.current = 0;
        if (immediate) {
            void tick();
        } else {
            timerRef.current = setTimeout(() => {
                void tick();
            }, interval);
        }
    }, [stop, tick, immediate, interval]);

    // Stop automatically when the component unmounts.
    useEffect(() => {
        return () => {
            if (timerRef.current) clearTimeout(timerRef.current);
        };
    }, []);

    return { start, stop, active };
}

export default usePolling;
