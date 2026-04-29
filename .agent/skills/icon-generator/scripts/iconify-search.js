#!/usr/bin/env node

/**
 * Iconify API 图标搜索辅助脚本
 *
 * 用法:
 *   node iconify-search.js search <query> [--prefix <prefix>] [--limit <n>]
 *   node iconify-search.js get <icon_id> [--color <color>] [--size <px>]
 *   node iconify-search.js collections [--search <keyword>]
 *
 * 示例:
 *   node iconify-search.js search arrow
 *   node iconify-search.js search home --prefix lucide --limit 5
 *   node iconify-search.js get lucide:home
 *   node iconify-search.js get mdi:settings --color "#333" --size 24
 *   node iconify-search.js collections --search material
 */

import https from 'https';

const API_BASE = 'https://api.iconify.design';

// ============================================================
// HTTP 请求工具
// ============================================================

function fetchJSON(url) {
    return new Promise((resolve, reject) => {
        https.get(url, (res) => {
            let data = '';
            res.on('data', chunk => data += chunk);
            res.on('end', () => {
                try {
                    resolve(JSON.parse(data));
                } catch (e) {
                    reject(new Error(`JSON 解析失败: ${data.substring(0, 200)}`));
                }
            });
        }).on('error', reject);
    });
}

function fetchText(url) {
    return new Promise((resolve, reject) => {
        https.get(url, (res) => {
            let data = '';
            res.on('data', chunk => data += chunk);
            res.on('end', () => resolve(data));
        }).on('error', reject);
    });
}

// ============================================================
// 命令实现
// ============================================================

async function searchIcons(query, options = {}) {
    const { prefix, limit = 20 } = options;
    let url = `${API_BASE}/search?query=${encodeURIComponent(query)}&limit=${limit}`;
    if (prefix) url += `&prefix=${prefix}`;

    console.log(`🔍 搜索: "${query}"${prefix ? ` (在 ${prefix} 中)` : ''}\n`);

    const data = await fetchJSON(url);

    if (!data.icons || data.icons.length === 0) {
        console.log('❌ 未找到匹配的图标');
        return;
    }

    console.log(`✅ 找到 ${data.total || data.icons.length} 个结果:\n`);

    data.icons.forEach((icon, i) => {
        console.log(`  ${String(i + 1).padStart(3)}. ${icon}`);
    });

    console.log(`\n💡 获取图标: node iconify-search.js get ${data.icons[0]}`);
    console.log(`💡 预览: ${API_BASE}/${data.icons[0].replace(':', '/')}.svg`);
}

async function getIcon(iconId, options = {}) {
    const { color, size } = options;
    const [prefix, name] = iconId.split(':');

    if (!prefix || !name) {
        console.error('❌ 图标 ID 格式错误，应为 "prefix:name"，例如 "lucide:home"');
        process.exit(1);
    }

    let url = `${API_BASE}/${prefix}/${name}.svg`;
    const params = [];
    if (color) params.push(`color=${encodeURIComponent(color)}`);
    if (size) params.push(`height=${size}`);
    if (params.length) url += `?${params.join('&')}`;

    console.log(`📦 获取图标: ${iconId}\n`);

    const svg = await fetchText(url);

    if (svg.includes('404') || svg.includes('not found')) {
        console.error('❌ 图标不存在');
        process.exit(1);
    }

    console.log('SVG 代码:');
    console.log('─'.repeat(50));
    console.log(svg);
    console.log('─'.repeat(50));

    // React 组件代码
    const componentName = name.split('-').map(w => w[0].toUpperCase() + w.slice(1)).join('');
    console.log(`\nReact 用法:  import { ${componentName} } from 'lucide-react'`);
    console.log(`HTML 用法:   <img src="${url}" alt="${name}" />`);
    console.log(`Iconify:     <span class="iconify" data-icon="${iconId}"></span>`);
    console.log(`预览 URL:    ${url}`);
}

async function listCollections(options = {}) {
    const { search } = options;
    console.log('📚 图标集合列表\n');

    const data = await fetchJSON(`${API_BASE}/collections`);

    let entries = Object.entries(data);
    if (search) {
        const keyword = search.toLowerCase();
        entries = entries.filter(([key, info]) =>
            key.includes(keyword) || (info.name && info.name.toLowerCase().includes(keyword))
        );
    }

    entries.sort((a, b) => (b[1].total || 0) - (a[1].total || 0));
    const top = entries.slice(0, 30);

    console.log(`${'前缀'.padEnd(20)} ${'名称'.padEnd(30)} ${'图标数'}`);
    console.log('─'.repeat(65));

    top.forEach(([prefix, info]) => {
        const name = (info.name || '').substring(0, 28);
        console.log(`${prefix.padEnd(20)} ${name.padEnd(30)} ${info.total || '?'}`);
    });

    console.log(`\n共 ${entries.length} 个集合`);
}

// ============================================================
// CLI 参数解析
// ============================================================

function parseArgs(args) {
    const result = { _: [] };
    for (let i = 0; i < args.length; i++) {
        if (args[i].startsWith('--')) {
            const key = args[i].slice(2);
            result[key] = args[i + 1] || true;
            i++;
        } else {
            result._.push(args[i]);
        }
    }
    return result;
}

async function main() {
    const args = parseArgs(process.argv.slice(2));
    const command = args._[0];

    if (!command) {
        console.log(`
Iconify 图标搜索工具

用法:
  node iconify-search.js search <query> [--prefix <prefix>] [--limit <n>]
  node iconify-search.js get <icon_id> [--color <color>] [--size <px>]
  node iconify-search.js collections [--search <keyword>]

示例:
  node iconify-search.js search arrow
  node iconify-search.js search home --prefix lucide --limit 5
  node iconify-search.js get lucide:home
  node iconify-search.js get mdi:settings --color "#333" --size 24
  node iconify-search.js collections --search material
`);
        return;
    }

    try {
        switch (command) {
            case 'search':
                await searchIcons(args._[1], { prefix: args.prefix, limit: parseInt(args.limit) || 20 });
                break;
            case 'get':
                await getIcon(args._[1], { color: args.color, size: args.size });
                break;
            case 'collections':
                await listCollections({ search: args.search });
                break;
            default:
                console.error(`❌ 未知命令: ${command}`);
                process.exit(1);
        }
    } catch (err) {
        console.error(`❌ 错误: ${err.message}`);
        process.exit(1);
    }
}

main();
