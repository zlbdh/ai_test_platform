import { describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import ApprovalReviewDialog from '../components/deploy/ApprovalReviewDialog';

describe('ApprovalReviewDialog', () => {
    it('关闭时不渲染内容', () => {
        render(
            <ApprovalReviewDialog
                open={false}
                action="approve"
                targetLabel="后端服务"
                comment=""
                onCommentChange={vi.fn()}
                onCancel={vi.fn()}
                onSubmit={vi.fn()}
            />,
        );

        expect(screen.queryByText("Approve deployment")).not.toBeInTheDocument();
    });

    it('批准模式下支持输入备注并提交', () => {
        const onCommentChange = vi.fn();
        const onSubmit = vi.fn();

        render(
            <ApprovalReviewDialog
                open
                action="approve"
                targetLabel="支付后端"
                comment="允许发布"
                onCommentChange={onCommentChange}
                onCancel={vi.fn()}
                onSubmit={onSubmit}
            />,
        );

        expect(screen.getByText("Approve deployment")).toBeInTheDocument();
        expect(screen.getByText('支付后端')).toBeInTheDocument();

        fireEvent.change(screen.getByPlaceholderText("Example: The deployment window is confirmed. Proceed."), {
            target: { value: '今天可以发版' },
        });
        fireEvent.click(screen.getByText("Confirm approval"));

        expect(onCommentChange).toHaveBeenCalledWith('今天可以发版');
        expect(onSubmit).toHaveBeenCalledTimes(1);
    });

    it('驳回模式下展示对应文案并支持取消', () => {
        const onCancel = vi.fn();

        render(
            <ApprovalReviewDialog
                open
                action="reject"
                targetLabel="前端门户"
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

    it('提交中状态会禁用按钮并显示加载文案', () => {
        render(
            <ApprovalReviewDialog
                open
                action="approve"
                targetLabel="结算服务"
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
