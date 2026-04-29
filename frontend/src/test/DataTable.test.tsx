import { describe, it, expect, vi, afterEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import DataTable, { type DataTableColumn } from '../components/ui/DataTable';

interface RowData {
    id: string;
    name: string;
}

describe('DataTable', () => {
    const columns: DataTableColumn<RowData>[] = [
        { key: 'id', title: 'ID' },
        { key: 'id', title: '重复 ID 列', render: (_value, row) => row.id },
        { key: 'name', title: '名称' },
    ];

    const data: RowData[] = [
        { id: 'row-1', name: '第一行' },
    ];

    const consoleErrorSpy = vi.spyOn(console, 'error').mockImplementation(() => { });

    afterEach(() => {
        consoleErrorSpy.mockClear();
    });

    it('允许重复业务列 key，但不应产生 React duplicate key 警告', () => {
        render(
            <DataTable<RowData>
                columns={columns}
                data={data}
                rowKey="id"
            />
        );

        expect(screen.getByText('重复 ID 列')).toBeInTheDocument();
        const duplicateKeyWarnings = consoleErrorSpy.mock.calls.filter(([message]) =>
            String(message).includes('same key')
        );
        expect(duplicateKeyWarnings).toHaveLength(0);
    });

    it('支持根据 activeRowKey 自动翻页并高亮目标行', () => {
        render(
            <DataTable<RowData>
                columns={columns}
                data={[
                    { id: 'row-1', name: '第一行' },
                    { id: 'row-2', name: '第二行' },
                    { id: 'row-3', name: '第三行' },
                ]}
                rowKey="id"
                pageSize={1}
                activeRowKey="row-2"
            />
        );

        expect(screen.queryByText('第一行')).not.toBeInTheDocument();
        expect(screen.getByText('第二行')).toBeInTheDocument();
        expect(screen.getByText('第二行').closest('tr')).toHaveAttribute('data-active', 'true');
    });
});
