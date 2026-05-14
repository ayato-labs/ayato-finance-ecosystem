// exe_app/src/utils/logger.ts
/**
 * Structured logger for the Desktop application.
 * Connects to Electron's main process logger via IPC.
 */

declare global {
  interface Window {
    electronAPI?: {
      log: (level: string, msg: string, context?: any) => void;
    };
  }
}

const isElectron = typeof window !== 'undefined' && window.electronAPI;

export const logger = {
  debug: (msg: string, context?: any) => {
    if (isElectron) {
      window.electronAPI?.log('debug', msg, context);
    } else {
      console.debug(`[DEBUG] ${msg}`, context || '');
    }
  },
  info: (msg: string, context?: any) => {
    if (isElectron) {
      window.electronAPI?.log('info', msg, context);
    } else {
      console.info(`[INFO] ${msg}`, context || '');
    }
  },
  warn: (msg: string, context?: any) => {
    if (isElectron) {
      window.electronAPI?.log('warn', msg, context);
    } else {
      console.warn(`[WARN] ${msg}`, context || '');
    }
  },
  error: (msg: string, context?: any) => {
    if (isElectron) {
      window.electronAPI?.log('error', msg, context);
    } else {
      console.error(`[ERROR] ${msg}`, context || '');
    }
  }
};
