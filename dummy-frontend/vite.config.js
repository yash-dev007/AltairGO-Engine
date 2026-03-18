import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    proxy: {
      '/api': 'http://127.0.0.1:5000',
      '/auth': 'http://127.0.0.1:5000',
      '/health': 'http://127.0.0.1:5000',
      '/generate-itinerary': 'http://127.0.0.1:5000',
      '/get-itinerary-status': 'http://127.0.0.1:5000',
      '/get-trip': 'http://127.0.0.1:5000',
      '/countries': 'http://127.0.0.1:5000',
      '/destinations': 'http://127.0.0.1:5000',
    }
  },
  build: {
    rollupOptions: {
      output: {
        manualChunks: {
          'vendor-react': ['react', 'react-dom', 'react-router-dom'],
          'vendor-charts': ['recharts'],
          'vendor-motion': ['framer-motion'],
          'vendor-icons': ['lucide-react'],
          'vendor-toast': ['react-hot-toast'],
        }
      }
    },
    chunkSizeWarningLimit: 600,
  }
})
