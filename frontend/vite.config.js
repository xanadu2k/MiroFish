import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import path from 'path'

// https://vite.dev/config/
export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, 'src'),
      '@locales': path.resolve(__dirname, '../locales')
    }
  },
  server: {
    host: '0.0.0.0',
    port: 5555,
    open: true,
    proxy: {
      '/api': {
        target: 'http://localhost:5556',
        changeOrigin: true,
        secure: false
      }
    }
  }
})
