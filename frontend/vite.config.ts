import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/analyze": {
        target: "http://127.0.0.1:8000",
        changeOrigin: true,
      },
      "/intent": {
        target: "http://127.0.0.1:8000",
        changeOrigin: true,
      },
      "/divergence": {
        target: "http://127.0.0.1:8000",
        changeOrigin: true,
      },
      "/simulate": {
        target: "http://127.0.0.1:8000",
        changeOrigin: true,
      },
    },
  },
});
