// Web_app/src/utils/logger.ts
import pino from 'pino';

/**
 * Structured logger for the Web/PWA application.
 * Focuses on JSON output to console for observability.
 */

const baseLogger = pino({
  level: 'debug',
  browser: {
    asObject: true
  },
  base: {
    env: import.meta.env.MODE,
    platform: 'web-pwa'
  }
});

export const logger = {
  debug: (msg: string, context?: Record<string, unknown>) => {
    baseLogger.debug({ ...context }, msg);
  },
  info: (msg: string, context?: Record<string, unknown>) => {
    baseLogger.info({ ...context }, msg);
  },
  warn: (msg: string, context?: Record<string, unknown>) => {
    baseLogger.warn({ ...context }, msg);
  },
  error: (msg: string, context?: Record<string, unknown>) => {
    baseLogger.error({ ...context }, msg);
  }
};
