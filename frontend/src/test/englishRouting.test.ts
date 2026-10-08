import { describe, expect, it } from 'vitest';
import { detectSemanticTestType } from '../utils/semanticIntent';
import { failureReasonLabel } from '../utils/failureReasonLabel';

describe('English semantic instruction routing', () => {
    it.each(['Verify the title', 'CHECK the page', 'Confirm results', 'The button should be visible', 'Determine whether login succeeded', 'assert the result'])('routes %s as an assertion', text => {
        expect(detectSemanticTestType(text)).toBe('assert');
    });
    it.each(['Fetch the title', 'GET the first row', 'Extract the data', 'Read the message', 'List all rows', 'query the table'])('routes %s as a query', text => {
        expect(detectSemanticTestType(text)).toBe('query');
    });
    it.each(['Click checkout', 'Click listItem', 'Click the thread', 'Enter a value'])('keeps %s as an action', text => {
        expect(detectSemanticTestType(text)).toBe('action');
    });
    it('preserves legacy routing and assertion precedence', () => {
        expect(detectSemanticTestType('验证页面')).toBe('assert');
        expect(detectSemanticTestType('获取标题')).toBe('query');
        expect(detectSemanticTestType('Verify and fetch the title')).toBe('assert');
    });
});

describe('failure reason display compatibility', () => {
    it.each([
        ['超时', 'Timeout'], ['元素定位', 'Element location'],
        ['断言失败', 'Assertion failure'], ['网络错误', 'Network error'],
        ['权限/认证', 'Permissions/authentication'], ['其他', 'Other'],
        ['Assertion failed', 'Assertion failure'],
    ])('displays %s as %s', (input, output) => expect(failureReasonLabel(input)).toBe(output));
    it('preserves canonical labels, custom values, and inherited property names', () => {
        for (const input of ['Assertion failure', 'Custom reason', '自定义原因', 'constructor', '__proto__']) {
            expect(failureReasonLabel(input)).toBe(input);
        }
    });
});
