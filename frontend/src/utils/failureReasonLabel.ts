const FAILURE_REASON_LABELS: Record<string, string> = {
    '超时': 'Timeout',
    '元素定位': 'Element location',
    '断言失败': 'Assertion failure',
    '网络错误': 'Network error',
    '权限/认证': 'Permissions/authentication',
    '其他': 'Other',
    'Assertion failed': 'Assertion failure',
};

// Change only known display labels. Preserve custom reasons and the raw record.
export function failureReasonLabel(reason: string): string {
    return Object.prototype.hasOwnProperty.call(FAILURE_REASON_LABELS, reason)
        ? FAILURE_REASON_LABELS[reason] : reason;
}
