import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],

  server: {
    port: 5173,
    // ─── Proxy vers le backend FastAPI (développement uniquement) ──────────
    // Toutes les requêtes commençant par /api sont redirigées vers le backend.
    // Cela élimine TOUS les problèmes CORS en développement local.
    // Le frontend appelle /api/players → Vite redirige vers http://localhost:8000/players
    proxy: {
      "/api": {
        target: "http://localhost:8000",
        changeOrigin: true,
        secure: false,
        // Supprime le préfixe /api avant de transmettre au backend
        rewrite: (path) => path.replace(/^\/api/, ""),
        // Log les requêtes proxifiées pour debug
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

  // ─── Preview (npm run preview) ──────────────────────────────────────────
  preview: {
    port: 4173,
  },

  // ─── Build ──────────────────────────────────────────────────────────────
  build: {
    outDir: "dist",
    sourcemap: false,
    rollupOptions: {
      output: {
        // Sépare les vendors pour un meilleur caching
        manualChunks: {
          vendor: ["react", "react-dom"],
          supabase: ["@supabase/supabase-js"],
        },
      },
    },
  },
});