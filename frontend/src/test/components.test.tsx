/**
 * 核心组件单元测试 (P2-2)
 *
 * 覆盖：LogTerminal / AgentCard
 * - 渲染正确性
 * - 日志过滤
 * - 折叠/展开
 * - AgentCard 状态展示
 * - AgentCard 操作按钮
 */
import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import LogTerminal from '../components/LogTerminal';
import AgentCard from '../components/AgentCard';
import { AgentType } from '../types';
import type { LogEntry, AgentStat } from '../types';

// ============================================================
// LogTerminal
// ============================================================
describe('LogTerminal', () => {
    const makeLogs = (count: number, level: LogEntry['level'] = 'INFO'): LogEntry[] =>
        Array.from({ length: count }, (_, i) => ({
            timestamp: `12:00:0${i}`,
            agent: AgentType.PLANNER,
            level,
            message: `Log message ${i}`,
        }));

    it('should render empty state when no logs', () => {
        render(<LogTerminal logs={[]} />);
        expect(screen.getByText("No activity yet...")).toBeInTheDocument();
    });

    it('should render log messages', () => {
        const logs = makeLogs(3);
        render(<LogTerminal logs={logs} />);
        expect(screen.getByText('Log message 0')).toBeInTheDocument();
        expect(screen.getByText('Log message 2')).toBeInTheDocument();
    });

    it('should show log count badge', () => {
        const logs = makeLogs(5);
        render(<LogTerminal logs={logs} />);
        expect(screen.getByText('5')).toBeInTheDocument();
    });

    it('should show error count badge when errors exist', () => {
        const logs: LogEntry[] = [
            { timestamp: '12:00', agent: AgentType.PLANNER, level: 'ERROR', message: 'err1' },
            { timestamp: '12:01', agent: AgentType.PLANNER, level: 'INFO', message: 'ok' },
            { timestamp: '12:02', agent: AgentType.PLANNER, level: 'ERROR', message: 'err2' },
        ];
        render(<LogTerminal logs={logs} />);
        expect(screen.getByText('2 Errors')).toBeInTheDocument();
    });

    it('should filter logs by level when filter button is clicked', () => {
        const logs: LogEntry[] = [
            { timestamp: '12:00', agent: AgentType.PLANNER, level: 'ERROR', message: 'error msg' },
            { timestamp: '12:01', agent: AgentType.PLANNER, level: 'INFO', message: 'info msg' },
            { timestamp: '12:02', agent: AgentType.PLANNER, level: 'SUCCESS', message: 'success msg' },
        ];
        render(<LogTerminal logs={logs} />);

        // All visible initially
        expect(screen.getByText('error msg')).toBeInTheDocument();
        expect(screen.getByText('info msg')).toBeInTheDocument();

        // Click ERROR filter
        fireEvent.click(screen.getByText("Error"));
        expect(screen.getByText('error msg')).toBeInTheDocument();
        expect(screen.queryByText('info msg')).not.toBeInTheDocument();
        expect(screen.queryByText('success msg')).not.toBeInTheDocument();
    });

    it('should collapse/expand log body', () => {
        const logs = makeLogs(2);
        render(<LogTerminal logs={logs} />);

        // Initially visible
        expect(screen.getByText('Log message 0')).toBeInTheDocument();

        // Find collapse button (ChevronDown) and click
        const collapseBtn = screen.getByTitle("Collapse logs");
        fireEvent.click(collapseBtn);

        // Logs should be hidden
        expect(screen.queryByText('Log message 0')).not.toBeInTheDocument();

        // Expand again
        const expandBtn = screen.getByTitle("Expand logs");
        fireEvent.click(expandBtn);

        expect(screen.getByText('Log message 0')).toBeInTheDocument();
    });

    it('should call onClear when clear button is clicked', () => {
        const onClear = vi.fn();
        const logs = makeLogs(1);
        render(<LogTerminal logs={logs} onClear={onClear} />);

        fireEvent.click(screen.getByTitle("Clear logs"));
        expect(onClear).toHaveBeenCalledTimes(1);
    });

    it('should display correct agent labels', () => {
        const logs: LogEntry[] = [
            { timestamp: '12:00', agent: AgentType.UI, level: 'INFO', message: 'ui test' },
            { timestamp: '12:01', agent: AgentType.API, level: 'INFO', message: 'api test' },
            { timestamp: '12:02', agent: AgentType.DATA, level: 'INFO', message: 'data test' },
        ];
        render(<LogTerminal logs={logs} />);
        expect(screen.getByText('UI-BOT')).toBeInTheDocument();
        expect(screen.getByText('API-BOT')).toBeInTheDocument();
        expect(screen.getByText('DB-BOT')).toBeInTheDocument();
    });
});

// ============================================================
// AgentCard
// ============================================================
describe('AgentCard', () => {
    const baseStat: AgentStat = {
        id: AgentType.UI,
        name: 'UI Agent',
        role: 'UI 测试',
        status: 'IDLE',
        tasksCompleted: 42,
        successRate: 95,
    };

    it('should render agent name and role', () => {
        render(<AgentCard stat={baseStat} />);
        expect(screen.getByText('UI Agent')).toBeInTheDocument();
        expect(screen.getByText('UI 测试')).toBeInTheDocument();
    });

    it('should show tasks completed and success rate', () => {
        render(<AgentCard stat={baseStat} />);
        expect(screen.getByText('42')).toBeInTheDocument();
        expect(screen.getByText('95%')).toBeInTheDocument();
    });

    it('should display IDLE status label', () => {
        render(<AgentCard stat={baseStat} />);
        expect(screen.getByText("Idle")).toBeInTheDocument();
    });

    it('should display BUSY status label', () => {
        render(<AgentCard stat={{ ...baseStat, status: 'BUSY' }} />);
        expect(screen.getByText("Busy")).toBeInTheDocument();
    });

    it('should display ERROR status label', () => {
        render(<AgentCard stat={{ ...baseStat, status: 'ERROR' }} />);
        expect(screen.getByText("Error")).toBeInTheDocument();
    });

    it('should display HEALING status label', () => {
        render(<AgentCard stat={{ ...baseStat, status: 'HEALING' }} />);
        expect(screen.getByText("Self-healing")).toBeInTheDocument();
    });

});
