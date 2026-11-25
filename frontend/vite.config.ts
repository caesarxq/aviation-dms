import path from "path";
import { fileURLToPath } from "url";
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

const __dirname = path.dirname(fileURLToPath(import.meta.url));

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  server: {
    port: 5173,
    proxy: {
      "/api": "http://localhost:8000",
    },
  },
  build: {
    rollupOptions: {
      output: {
        manualChunks: {
          // ProseMirror / TipTap editor (largest vendor)
          prosemirror: [
            "@tiptap/core",
            "@tiptap/react",
            "@tiptap/starter-kit",
            "@tiptap/extension-text-align",
            "@tiptap/extension-link",
            "@tiptap/extension-image",
          ],
          // UI component libraries
          ui: [
            "@radix-ui/react-dialog",
            "@radix-ui/react-select",
            "@radix-ui/react-popover",
            "@radix-ui/react-checkbox",
            "@radix-ui/react-radio-group",
            "@radix-ui/react-switch",
            "@radix-ui/react-tooltip",
            "@radix-ui/react-slot",
            "@radix-ui/react-label",
            "lucide-react",
            "clsx",
            "tailwind-merge",
          ],
          // React ecosystem
          react: ["react", "react-dom", "react-router-dom"],
          // Data fetching & state
          query: ["@tanstack/react-query"],
          // Utilities
          utils: ["dompurify", "axios", "zod"],
        },
      },
    },
    chunkSizeWarningLimit: 800,
  },
});
