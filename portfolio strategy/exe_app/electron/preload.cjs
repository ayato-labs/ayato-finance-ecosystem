const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('electronAPI', {
  log: (level, msg, context) => ipcRenderer.send('log', { level, msg, context })
});
