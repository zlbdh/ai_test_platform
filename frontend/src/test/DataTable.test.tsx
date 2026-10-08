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
        { key: 'id', title: "Duplicate ID column", render: (_value, row) => row.id },
        { key: 'name', title: "Name" },
    ];

    const data: RowData[] = [
        { id: 'row-1', name: "First row" },
    ];

    const consoleErrorSpy = vi.spyOn(console, 'error').mockImplementation(() => { });

    afterEach(() => {
        consoleErrorSpy.mockClear();
    });

    it("allows duplicate business column keys without React duplicate key warnings", () => {
        render(
            <DataTable<RowData>
                columns={columns}
                data={data}
                rowKey="id"
            />
        );

        expect(screen.getByText("Duplicate ID column")).toBeInTheDocument();
        const duplicateKeyWarnings = consoleErrorSpy.mock.calls.filter(([message]) =>
            String(message).includes('same key')
        );
        expect(duplicateKeyWarnings).toHaveLength(0);
    });

    it("paginates and highlights the target row using activeRowKey", () => {
        render(
            <DataTable<RowData>
                columns={columns}
                data={[
                    { id: 'row-1', name: "First row" },
                    { id: 'row-2', name: "Second row" },
                    { id: 'row-3', name: "Third row" },
                ]}
                rowKey="id"
                pageSize={1}
                activeRowKey="row-2"
            />
        );

        expect(screen.queryByText("First row")).not.toBeInTheDocument();
        expect(screen.getByText("Second row")).toBeInTheDocument();
        expect(screen.getByText("Second row").closest('tr')).toHaveAttribute('data-active', 'true');
    });
});
