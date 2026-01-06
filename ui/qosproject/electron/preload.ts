import { contextBridge, ipcRenderer } from 'electron';


console.log('[Preload] ========================================');
console.log('[Preload] Preload script STARTING');
console.log('[Preload] ========================================');


if (!contextBridge) {
  console.error('[Preload] ❌ contextBridge is not available!');
}

if (!ipcRenderer) {
  console.error('[Preload] ❌ ipcRenderer is not available!');
}

try {
  const electronAPI = {
    runSolver: (payload: any) => {
      console.log('[Preload] runSolver called with payload:', payload);
      return ipcRenderer.invoke('run-solver', payload);
    },
    readCSV: (filePath: string) => {
      console.log('[Preload] readCSV called with path:', filePath);
      return ipcRenderer.invoke('read-csv', filePath);
    },
    selectFile: (options: { title: string; filters?: any[] }) => {
      console.log('[Preload] selectFile called with options:', options);
      return ipcRenderer.invoke('select-file', options);
    },
  };

  console.log('[Preload] Attempting to expose electronAPI...');
  console.log('[Preload] electronAPI object:', Object.keys(electronAPI));
  
  contextBridge.exposeInMainWorld('electronAPI', electronAPI);
  
  console.log('[Preload] ✅ electronAPI exposed successfully!');
  console.log('[Preload] window.electronAPI should now be available in renderer');
  
  
  if ((globalThis as any).electronAPI) {
    console.log('[Preload] ✅ Verified: electronAPI is in globalThis');
  }
} catch (error: any) {
  console.error('[Preload] ❌ Error exposing electronAPI:', error);
  console.error('[Preload] Error details:', {
    message: error?.message,
    stack: error?.stack,
    name: error?.name
  });
}

console.log('[Preload] ========================================');
console.log('[Preload] Preload script FINISHED');
console.log('[Preload] ========================================');

