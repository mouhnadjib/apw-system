import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// البناء يُخرَج إلى app/static/panel ويُخدَّم من FastAPI على /panel/
export default defineConfig({
  plugins: [react()],
  base: "/panel/",
  build: { outDir: "../app/static/panel", emptyOutDir: true },
  server: {
    proxy: Object.fromEntries(
      ["/auth", "/admin", "/staff"].map((p) => [p, "http://127.0.0.1:8000"])
    ),
  },
});
