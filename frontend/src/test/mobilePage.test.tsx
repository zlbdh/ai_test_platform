import { describe, expect, it } from 'vitest';

import { normalizeMobileIssue, normalizeMobileTestResult } from '../pages/MobilePage';

describe('MobilePage normalization', () => {
    it('should normalize object issues for rendering', () => {
        const issue = normalizeMobileIssue({
            rule_id: 'viewport-meta',
            description: '缺少 viewport meta 标签',
            severity: 'critical',
            suggestion: '补充 viewport',
        }, 'iPhone 14');

        expect(issue).toEqual({
            ruleId: 'viewport-meta',
            description: '缺少 viewport meta 标签',
            severity: 'critical',
            device: 'iPhone 14',
            suggestion: '补充 viewport',
        });
    });

    it('should parse string viewport and derive score when backend omits it', () => {
        const result = normalizeMobileTestResult({
            device: 'Pixel 7',
            viewport: '412x915',
            issues: [
                {
                    rule_id: 'touch-target',
                    description: '触控目标过小',
                    severity: 'major',
                },
                '存在额外兼容性提示',
            ],
        });

        expect(result.viewport).toEqual({ width: 412, height: 915 });
        expect(result.viewportText).toBe('412×915');
        expect(result.score).toBe(89);
        expect(result.issues[0].ruleId).toBe('touch-target');
        expect(result.issues[1].description).toBe('存在额外兼容性提示');
    });

    it('should keep explicit score when backend provides it', () => {
        const result = normalizeMobileTestResult({
            device: 'iPad Air',
            viewport: { width: 820, height: 1180 },
            issues: [],
            score: 96,
        });

        expect(result.viewportText).toBe('820×1180');
        expect(result.score).toBe(96);
    });
});
