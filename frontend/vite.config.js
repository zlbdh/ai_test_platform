
import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'
import { fileURLToPath } from 'url'

const __filename = fileURLToPath(import.meta.url)
const __dirname = path.dirname(__filename)

// https://vitejs.dev/config/
export default defineConfig(({ mode }) => {
    const env = loadEnv(mode, __dirname, '')
    const proxyTarget = env.VITE_PROXY_TARGET || env.VITE_API_URL || 'http://localhost:8020'
    const wsProxyTarget = env.VITE_PROXY_WS_TARGET || env.VITE_WS_URL || 'ws://localhost:8020'

    return {
        plugins: [react()],
        resolve: {
            alias: {
                '@': path.resolve(__dirname, './src'),
            },
        },
        build: {
            rollupOptions: {
                output: {
                    manualChunks: {
                        'vendor-react': ['react', 'react-dom', 'react-router-dom'],
                        'vendor-ui': ['lucide-react', 'recharts', '@radix-ui/react-slot', 'class-variance-authority', 'tailwind-merge'],
                        'vendor-utils': ['axios', 'date-fns', 'clsx', 'zustand'],
                    },
                },
            },
            chunkSizeWarningLimit: 600,
        },
        server: {
            port: 8010,
            host: true,
            proxy: {
                '/planner': { target: proxyTarget, changeOrigin: true },
                '/agentic': { target: proxyTarget, changeOrigin: true },
                '/system': { target: proxyTarget, changeOrigin: true },
                '/control': { target: proxyTarget, changeOrigin: true },
                '^/api(?:/|$)': { target: proxyTarget, changeOrigin: true },
                '/ws': {
                    target: wsProxyTarget,
                    ws: true,
                }
            }
        }
    }
})
