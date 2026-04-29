/**
 * usePolling — 通用轮询 Hook
 *
 * 适用于部署进度、任务状态等需要定时刷新的场景。
 *
 * @example
 *   const { start, stop, active } = usePolling(async () => {
 *       const status = await fetchDeployStatus(repoId);
 *       setProgress(status);
 *       if (status.done) return false; // 返回 false 停止轮询
 *   }, { interval: 2000 });
 *
 *   // 启动
 *   start();
 *   // 手动停止
 *   stop();
 */
import { useState, useCallback, useRef, useEffect } from 'react';

interface UsePollingOptions {
    /** 轮询间隔(ms)，默认 3000 */
    interval?: number;
    /** 是否立即执行第一次，默认 true */
    immediate?: boolean;
    /** 最大轮询次数，0=无限 */
    maxRetries?: number;
}

interface UsePollingReturn {
    /** 启动轮询 */
    start: () => void;
    /** 停止轮询 */
    stop: () => void;
    /** 是否正在轮询 */
    active: boolean;
}

/**
 * @param fn 轮询函数，返回 false 时自动停止
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

    // 组件卸载时自动停止
    useEffect(() => {
        return () => {
            if (timerRef.current) clearTimeout(timerRef.current);
        };
    }, []);

    return { start, stop, active };
}

export default usePolling;
