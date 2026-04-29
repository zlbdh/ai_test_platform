import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import KnowledgeBase from '../components/KnowledgeBase';

const mockFetch = vi.fn();
global.fetch = mockFetch;

function mockJsonResponse(body: unknown): Response {
    return {
        ok: true,
        status: 200,
        statusText: 'OK',
        json: vi.fn().mockResolvedValue(body),
        text: vi.fn().mockResolvedValue(JSON.stringify(body)),
        headers: new Headers(),
        redirected: false,
        type: 'basic',
        url: '',
        clone: vi.fn(),
        body: null,
        bodyUsed: false,
        arrayBuffer: vi.fn(),
        blob: vi.fn(),
        formData: vi.fn(),
        bytes: vi.fn(),
    } as unknown as Response;
}

describe('KnowledgeBase', () => {
    beforeEach(() => {
        mockFetch.mockReset();
    });

    it('能将后端 knowledge list 的 metadata 映射成文件名和类型', async () => {
        mockFetch.mockResolvedValue(mockJsonResponse({
            status: 'success',
            items: [
                {
                    id: 'doc-1',
                    content: '# hello',
                    metadata: {
                        filename: 'guide.md',
                        source_path: 'D:/docs/guide.md',
                    },
                },
            ],
        }));

        render(<KnowledgeBase />);

        await waitFor(() => {
            expect(screen.getByText('guide.md')).toBeInTheDocument();
        });
        expect(screen.getByText('MARKDOWN')).toBeInTheDocument();
    });
});
