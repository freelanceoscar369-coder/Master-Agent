/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** 'mock' (default) | 'http' */
  readonly VITE_KERNEL_ADAPTER?: string;
  /** Base URL for the HTTP kernel, e.g. https://kernel.kalpavriksha.internal */
  readonly VITE_KERNEL_BASE_URL?: string;
  /** Stream transport for the HTTP kernel: 'sse' | 'websocket' | 'poll' */
  readonly VITE_KERNEL_STREAM?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
