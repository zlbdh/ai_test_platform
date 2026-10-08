import { describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import ApprovalReviewDialog from '../components/deploy/ApprovalReviewDialog';

describe('ApprovalReviewDialog', () => {
    it("renders no content while closed", () => {
        render(
            <ApprovalReviewDialog
                open={false}
                action="approve"
                targetLabel={"Backend service"}
                comment=""
                onCommentChange={vi.fn()}
                onCancel={vi.fn()}
                onSubmit={vi.fn()}
            />,
        );

        expect(screen.queryByText("Approve deployment")).not.toBeInTheDocument();
    });

    it("supports entering and submitting a note in approval mode", () => {
        const onCommentChange = vi.fn();
        const onSubmit = vi.fn();

        render(
            <ApprovalReviewDialog
                open
                action="approve"
                targetLabel={"Payments backend"}
                comment={"Allow release"}
                onCommentChange={onCommentChange}
                onCancel={vi.fn()}
                onSubmit={onSubmit}
            />,
        );

        expect(screen.getByText("Approve deployment")).toBeInTheDocument();
        expect(screen.getByText("Payments backend")).toBeInTheDocument();

        fireEvent.change(screen.getByPlaceholderText("Example: The deployment window is confirmed. Proceed."), {
            target: { value: "The release can proceed today" },
        });
        fireEvent.click(screen.getByText("Confirm approval"));

        expect(onCommentChange).toHaveBeenCalledWith("The release can proceed today");
        expect(onSubmit).toHaveBeenCalledTimes(1);
    });

    it("shows rejection copy and supports canceling", () => {
        const onCancel = vi.fn();

        render(
            <ApprovalReviewDialog
                open
                action="reject"
                targetLabel={"Frontend portal"}
                comment=""
                onCommentChange={vi.fn()}
                onCancel={onCancel}
                onSubmit={vi.fn()}
            />,
        );

        expect(screen.getByText("Reject deployment")).toBeInTheDocument();
        expect(screen.getByPlaceholderText("Example: The change window has not started. Submit again later.")).toBeInTheDocument();

        fireEvent.click(screen.getByText("Cancel"));
        expect(onCancel).toHaveBeenCalledTimes(1);
    });

    it("disables buttons and shows loading text while submitting", () => {
        render(
            <ApprovalReviewDialog
                open
                action="approve"
                targetLabel={"Settlement service"}
                comment=""
                submitting
                onCommentChange={vi.fn()}
                onCancel={vi.fn()}
                onSubmit={vi.fn()}
            />,
        );

        expect(screen.getByText("Confirm approval")).toBeDisabled();
        expect(screen.getByText("Cancel")).toBeDisabled();
    });
});
