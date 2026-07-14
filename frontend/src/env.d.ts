/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_API_BASE_URL: string
  readonly VITE_USE_MOCK: string
}

declare module 'node:url' {
  export function fileURLToPath(url: URL | string): string
}
