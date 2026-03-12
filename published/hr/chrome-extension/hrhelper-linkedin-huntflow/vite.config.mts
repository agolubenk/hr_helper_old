import { defineConfig } from "vite";
import { resolve } from "path";

// Билдим Chrome Extension (MV3) без изменения структуры: html остаются как есть,
// js/css бандлятся и минифицируются Vite/Rollup.

export default defineConfig({
  root: ".",
  build: {
    outDir: "dist",
    emptyOutDir: true,
    rollupOptions: {
      input: {
        popup: resolve(__dirname, "popup.html"),
        options: resolve(__dirname, "options.html"),
        background: resolve(__dirname, "background.js"),
        contentLinkedIn: resolve(__dirname, "content.js"),
        contentResume: resolve(__dirname, "content-resume.js"),
        contentMeet: resolve(__dirname, "content-meet.js"),
        contentCalendar: resolve(__dirname, "content-calendar.js"),
        contentHuntflow: resolve(__dirname, "content-huntflow.js"),
      },
      output: {
        // Сохраняем читаемые имена файлов по entry-поинтам
        entryFileNames: (chunk) => {
          const name = chunk.name || "entry";
          return `[name].js`;
        },
        chunkFileNames: "chunks/[name]-[hash].js",
        assetFileNames: (asset) => {
          if (asset.name && asset.name.endsWith(".css")) return "[name].css";
          return "assets/[name]-[hash][extname]";
        },
      },
    },
    minify: "esbuild",
  },
});
