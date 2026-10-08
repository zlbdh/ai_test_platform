#!/usr/bin/env node

/**
 * Iconify API icon search helper
 *
 * Usage:
 *   node iconify-search.js search <query> [--prefix <prefix>] [--limit <n>]
 *   node iconify-search.js get <icon_id> [--color <color>] [--size <px>]
 *   node iconify-search.js collections [--search <keyword>]
 *
 * Examples:
 *   node iconify-search.js search arrow
 *   node iconify-search.js search home --prefix lucide --limit 5
 *   node iconify-search.js get lucide:home
 *   node iconify-search.js get mdi:settings --color "#333" --size 24
 *   node iconify-search.js collections --search material
 */

import https from 'https';

const API_BASE = 'https://api.iconify.design';

// ============================================================
// HTTP request helper
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
                    reject(new Error(`Failed to parse JSON: ${data.substring(0, 200)}`));
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
// Command implementations
// ============================================================

async function searchIcons(query, options = {}) {
    const { prefix, limit = 20 } = options;
    let url = `${API_BASE}/search?query=${encodeURIComponent(query)}&limit=${limit}`;
    if (prefix) url += `&prefix=${prefix}`;

    console.log(`🔍 Search: "${query}"${prefix ? ` (in ${prefix})` : ''}\n`);

    const data = await fetchJSON(url);

    if (!data.icons || data.icons.length === 0) {
        console.log('❌ No matching icons found');
        return;
    }

    console.log(`✅ Found ${data.total || data.icons.length} results:\n`);

    data.icons.forEach((icon, i) => {
        console.log(`  ${String(i + 1).padStart(3)}. ${icon}`);
    });

    console.log(`\n💡 Get an icon: node iconify-search.js get ${data.icons[0]}`);
    console.log(`💡 Preview: ${API_BASE}/${data.icons[0].replace(':', '/')}.svg`);
}

async function getIcon(iconId, options = {}) {
    const { color, size } = options;
    const [prefix, name] = iconId.split(':');

    if (!prefix || !name) {
        console.error('❌ Invalid icon ID; use "prefix:name", such as "lucide:home"');
        process.exit(1);
    }

    let url = `${API_BASE}/${prefix}/${name}.svg`;
    const params = [];
    if (color) params.push(`color=${encodeURIComponent(color)}`);
    if (size) params.push(`height=${size}`);
    if (params.length) url += `?${params.join('&')}`;

    console.log(`📦 Get icon: ${iconId}\n`);

    const svg = await fetchText(url);

    if (svg.includes('404') || svg.includes('not found')) {
        console.error('❌ Icon not found');
        process.exit(1);
    }

    console.log('SVG code:');
    console.log('─'.repeat(50));
    console.log(svg);
    console.log('─'.repeat(50));

    // React component code
    const componentName = name.split('-').map(w => w[0].toUpperCase() + w.slice(1)).join('');
    console.log(`\nReact usage: import { ${componentName} } from 'lucide-react'`);
    console.log(`HTML usage:  <img src="${url}" alt="${name}" />`);
    console.log(`Iconify:     <span class="iconify" data-icon="${iconId}"></span>`);
    console.log(`Preview URL: ${url}`);
}

async function listCollections(options = {}) {
    const { search } = options;
    console.log('📚 Icon collections\n');

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

    console.log(`${'Prefix'.padEnd(20)} ${'Name'.padEnd(30)} ${'Icons'}`);
    console.log('─'.repeat(65));

    top.forEach(([prefix, info]) => {
        const name = (info.name || '').substring(0, 28);
        console.log(`${prefix.padEnd(20)} ${name.padEnd(30)} ${info.total || '?'}`);
    });

    console.log(`\n${entries.length} collections total`);
}

// ============================================================
// Parse CLI arguments
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
Iconify Icon Search Tool

Usage:
  node iconify-search.js search <query> [--prefix <prefix>] [--limit <n>]
  node iconify-search.js get <icon_id> [--color <color>] [--size <px>]
  node iconify-search.js collections [--search <keyword>]

Examples:
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
                console.error(`❌ Unknown command: ${command}`);
                process.exit(1);
        }
    } catch (err) {
        console.error(`❌ Error: ${err.message}`);
        process.exit(1);
    }
}

main();
