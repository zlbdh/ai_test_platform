export type SemanticTestType = 'action' | 'assert' | 'query';

// Retain legacy instructions while recognizing English words without matching
// substrings such as "checkout" or "listItem".
export function detectSemanticTestType(text: string): SemanticTestType {
    const lower = text.toLowerCase();
    if (['验证', '检查', 'assert', '确认', '应该', '是否'].some(word => lower.includes(word))
        || /\b(?:verify|check|confirm|should|whether)\b/i.test(text)) return 'assert';
    if (['获取', '查询', 'query', '提取', '读取', '列出'].some(word => lower.includes(word))
        || /\b(?:get|fetch|extract|read|list)\b/i.test(text)) return 'query';
    return 'action';
}
