import { defineConfig } from "vite";
import solid from "vite-plugin-solid";
const host = process.env.TAURI_DEV_HOST;
export default defineConfig({
    plugins: [solid()],
    clearScreen: false,
    server: {
        port: 1420,
        strictPort: true,
        host: host || false,
        ...(host
            ? {
                hmr: {
                    protocol: "ws",
                    host,
                    port: 1421
                }
            }
            : {}),
        watch: {
            ignored: ["**/src-tauri/**"]
        }
    },
    envPrefix: ["VITE_", "TAURI_ENV_*"],
    build: {
        target: "es2022",
        minify: process.env.TAURI_ENV_DEBUG ? false : "esbuild",
        sourcemap: Boolean(process.env.TAURI_ENV_DEBUG)
    }
});
//# sourceMappingURL=vite.config.js.map