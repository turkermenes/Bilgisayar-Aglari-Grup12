const { contextBridge, ipcRenderer } = require('electron');

console.log('[Preload] loaded');

try {
  const electronAPI = {
    ping: () => {
      console.log('[Preload] ping() called');
      return ipcRenderer.invoke('ping');
    },
    runSolver: (payload) => {
      console.log('[Preload] runSolver called with payload:', payload);
      return ipcRenderer.invoke('run-solver', payload);
    },
    readCSV: (filePath) => {
      console.log('[Preload] readCSV called with path:', filePath);
      return ipcRenderer.invoke('read-csv', filePath);
    },
    selectFile: (options) => {
      console.log('[Preload] selectFile called with options:', options);
      return ipcRenderer.invoke('select-file', options);
    },
  };

  contextBridge.exposeInMainWorld('electronAPI', electronAPI);
  console.log('[Preload] electronAPI exposed');
} catch (error) {
  console.error('[Preload] ❌ Error exposing electronAPI:', error);
  console.error('[Preload] Error details:', {
    message: error?.message,
    stack: error?.stack,
    name: error?.name
  });
}


