import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],

  server: {
    port: 5173,
    proxy: {
      "/api": {
        target: "http://localhost:8000",
        changeOrigin: true,
        secure: false,
        rewrite: (path) => path.replace(/^\/api/, ""),
        configure: (proxy) => {
          proxy.on("error", (err) => {
            console.error("\n❌ [PROXY] Backend inaccessible sur :8000 →", err.message);
            console.error("   Démarre le backend : uvicorn app.main:app --reload\n");
          });
          proxy.on("proxyReq", (_, req) => {
            if (process.env.NODE_ENV !== "production") {
              console.log(`[PROXY] ${req.method} ${req.url}`);
            }
          });
        },
      },
    },
  },

  preview: { port: 4173 },

  build: {
    outDir: "dist",
    sourcemap: false,
    rollupOptions: {
      output: {
        manualChunks: {
          vendor:   ["react", "react-dom"],
          supabase: ["@supabase/supabase-js"],
        },
      },
    },
  },
});