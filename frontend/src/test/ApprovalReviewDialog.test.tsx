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

        expect(screen.queryByText('批准部署审批')).not.toBeInTheDocument();
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

        expect(screen.getByText('批准部署审批')).toBeInTheDocument();
        expect(screen.getByText('支付后端')).toBeInTheDocument();

        fireEvent.change(screen.getByPlaceholderText('例如：已确认发布时间窗，可以执行。'), {
            target: { value: '今天可以发版' },
        });
        fireEvent.click(screen.getByText('确认批准'));

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

        expect(screen.getByText('驳回部署审批')).toBeInTheDocument();
        expect(screen.getByPlaceholderText('例如：变更窗口未到，请稍后重新申请。')).toBeInTheDocument();

        fireEvent.click(screen.getByText('取消'));
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

        expect(screen.getByText('确认批准')).toBeDisabled();
        expect(screen.getByText('取消')).toBeDisabled();
    });
});
