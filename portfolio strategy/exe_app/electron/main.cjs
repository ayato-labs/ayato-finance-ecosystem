const { app, BrowserWindow } = require('electron');
const path = require('path');
const fs = require('fs');
const pino = require('pino');

// --- Logging Configuration ---
const logDir = path.join(app.getPath('userData'), 'logs');
if (!fs.existsSync(logDir)) {
  fs.mkdirSync(logDir, { recursive: true });
}

// Manage rotation: keep last 2 executions
const logFiles = fs.readdirSync(logDir)
  .filter(f => f.startsWith('main.') && f.endsWith('.log'))
  .sort((a, b) => fs.statSync(path.join(logDir, b)).mtime.getTime() - fs.statSync(path.join(logDir, a)).mtime.getTime());

// Delete old logs if more than 1 (so the new one will be the 2nd)
if (logFiles.length >= 2) {
  logFiles.slice(1).forEach(f => fs.unlinkSync(path.join(logDir, f)));
}

const currentLogPath = path.join(logDir, `main.${Date.now()}.log`);
const errorLogPath = path.join(logDir, 'error.log');

const transport = pino.transport({
  targets: [
    {
      target: 'pino/file',
      options: { destination: currentLogPath },
      level: 'debug'
    },
    {
      target: 'pino/file',
      options: { destination: errorLogPath },
      level: 'error'
    },
    {
      target: 'pino-pretty',
      options: { colorize: true },
      level: 'info'
    }
  ]
});

const logger = pino(transport);

logger.info('Application starting...');

const { ipcMain } = require('electron');
ipcMain.on('log', (event, { level, msg, context }) => {
  if (logger[level]) {
    logger[level]({ ...context, from: 'renderer' }, msg);
  } else {
    logger.info({ ...context, level, from: 'renderer' }, msg);
  }
});
// --- End Logging Configuration ---

function createWindow() {
  logger.debug('Creating browser window...');
  const win = new BrowserWindow({
    width: 1200,
    height: 800,
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
      preload: path.join(__dirname, 'preload.cjs') // We might need this for logging from renderer
    },
    title: "Alloc - Portfolio Rebalancer",
  });

  const isDev = !app.isPackaged;
  if (isDev) {
    win.loadURL('http://localhost:5173');
  } else {
    win.loadFile(path.join(__dirname, '../dist/index.html'));
  }
}

app.whenReady().then(() => {
  try {
    createWindow();
    logger.info('Window created successfully');
  } catch (err) {
    logger.error({ err }, 'Failed to create window');
  }

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      createWindow();
    }
  });
});

app.on('window-all-closed', () => {
  logger.info('All windows closed. Quitting app.');
  if (process.platform !== 'darwin') {
    app.quit();
  }
});

process.on('uncaughtException', (err) => {
  logger.error({ err }, 'Uncaught Exception in Main Process');
});
