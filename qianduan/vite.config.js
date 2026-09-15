import { defineConfig, loadEnv } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd())
  const apiPrefix = env.VITE_APP_BASE_API || '/api'
  const apiTarget = env.VITE_HOST_URL || 'http://127.0.0.1:8000'
  return {
    plugins: [vue()],
    base: './',
    resolve: { alias: { '@': '/src' } },
    css: {
      preprocessorOptions: {
        scss: {
          additionalData: `@import './src/assets/style/base.scss';`,
          silenceDeprecations: ['legacy-js-api', 'import']
        }
      }
    },
    optimizeDeps: {
      include: [
        'three',
        'three/addons/controls/OrbitControls.js',
        'three/addons/loaders/GLTFLoader.js',
        'axios',
        'pinia',
        'vue-router',
        'echarts',
        'countup.js'
      ]
    },
    build: {
      outDir: 'dist',
      minify: 'terser',
      terserOptions: {
        compress: { keep_infinity: true, drop_console: true, drop_debugger: true }
      },
      chunkSizeWarningLimit: 1500
    },
    server: {
      host: '127.0.0.1',
      port: 5173,
      strictPort: true,
      open: false,
      hmr: true,
      proxy: {
        [apiPrefix]: {
          target: apiTarget,
          changeOrigin: true,
          rewrite: path => path.startsWith(apiPrefix) ? path.slice(apiPrefix.length) : path
        }
      }
    }
  }
})
