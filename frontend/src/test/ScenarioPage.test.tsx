import { describe, expect, it, beforeEach, vi } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';

const mockFetch = vi.fn();
global.fetch = mockFetch;

import ScenarioPage from '../pages/ScenarioPage';

describe('ScenarioPage', () => {
    beforeEach(() => {
        mockFetch.mockReset();
    });

    it('should import sample_platform playbook scenarios', async () => {
        mockFetch.mockImplementation(async (input: RequestInfo | URL, init?: RequestInit) => {
            const url = String(input);
            if (url.endsWith('/api/scenarios') && (!init || !init.method || init.method === 'GET')) {
                return {
                    ok: true,
                    json: vi.fn().mockResolvedValue({
                        scenarios: [
                            {
                                id: 'scn-1',
                                name: "[Business operations role]-Login authentication-Wave0 baseline-Test environment",
                                description: 'desc',
                                stepCount: 3,
                                status: 'draft',
                                tags: ["Sample project", 'wave0'],
                                updated_at: '2026-03-24T12:00:00',
                            },
                        ],
                    }),
                } as unknown as Response;
            }

            if (url.endsWith('/api/scenarios/import-playbook/sample-first-regression')) {
                return {
                    ok: true,
                    json: vi.fn().mockResolvedValue({
                        status: 'success',
                        playbook_id: 'sample-first-regression',
                        playbook_name: "Sample enterprise platform initial live regression",
                        playbook_title: "Sample enterprise platform initial live regression",
                        project_name: "Sample business platform",
                        imported_count: 2,
                        scenarios: [
                            {
                                id: 'scn-1',
                                name: "[Business operations role]-Login authentication-Wave0 baseline-Test environment",
                                stepCount: 3,
                                tags: ["Sample project", 'wave0'],
                            },
                            {
                                id: 'scn-2',
                                name: "[Business operations role]-Work order dispatch-Wave1 main workflow-Test environment",
                                stepCount: 3,
                                tags: ["Sample project", 'wave1'],
                            },
                        ],
                    }),
                } as unknown as Response;
            }

            throw new Error(`Unhandled fetch: ${url}`);
        });

        render(<ScenarioPage />);

        await waitFor(() => expect(mockFetch).toHaveBeenCalled());
        fireEvent.click(screen.getByRole('button', { name: "Import sample project scenarios" }));

        await waitFor(() => expect(mockFetch).toHaveBeenCalledWith(
            expect.stringContaining('/api/scenarios/import-playbook/sample-first-regression'),
            expect.objectContaining({ method: 'POST' }),
        ));

        expect(await screen.findByText("Sample enterprise platform initial live regression")).toBeInTheDocument();
        expect(screen.getByText("Imported 2 scenarios covering Wave 0 through Wave 4. Run them individually or edit them first.")).toBeInTheDocument();
        expect(screen.getByText("[Business operations role]-Work order dispatch-Wave1 main workflow-Test environment")).toBeInTheDocument();
    });

    it('should import sample_platform platform prototype scenarios', async () => {
        mockFetch.mockImplementation(async (input: RequestInfo | URL, init?: RequestInit) => {
            const url = String(input);
            if (url.endsWith('/api/scenarios') && (!init || !init.method || init.method === 'GET')) {
                return {
                    ok: true,
                    json: vi.fn().mockResolvedValue({ scenarios: [] }),
                } as unknown as Response;
            }

            if (url.endsWith('/api/scenarios/import-playbook/sample-platform-prototype')) {
                return {
                    ok: true,
                    json: vi.fn().mockResolvedValue({
                        status: 'success',
                        playbook_id: 'sample-platform-prototype',
                        playbook_name: "Sample project platform prototype test package",
                        playbook_title: "Sample project platform prototype test package",
                        project_name: "Sample platform",
                        imported_count: 3,
                        scenarios: [
                            {
                                id: 'pt-1',
                                name: "[Platform administrator role]-Business management-Page structure check-Prototype stage",
                                stepCount: 1,
                                tags: ["Sample platform", "Prototype testing", "Business management", 'structure'],
                            },
                        ],
                    }),
                } as unknown as Response;
            }

            throw new Error(`Unhandled fetch: ${url}`);
        });

        render(<ScenarioPage />);

        await waitFor(() => expect(mockFetch).toHaveBeenCalled());
        fireEvent.click(screen.getByRole('button', { name: "Import platform prototype scenarios" }));

        await waitFor(() => expect(mockFetch).toHaveBeenCalledWith(
            expect.stringContaining('/api/scenarios/import-playbook/sample-platform-prototype'),
            expect.objectContaining({ method: 'POST' }),
        ));

        expect(await screen.findByText("Sample project platform prototype test package")).toBeInTheDocument();
        expect(screen.getByText("Imported 3 prototype scenarios covering login, 15 business modules, and cross-module workflows. Add the real environment details before running them.")).toBeInTheDocument();
        expect(screen.getByText("[Platform administrator role]-Business management-Page structure check-Prototype stage")).toBeInTheDocument();
    });
});
