
export function checkElectronAPI(): boolean {
  if (typeof window === 'undefined') {
    console.error('[ElectronCheck] Window is undefined');
    return false;
  }

  const hasElectronAPI = typeof window.electronAPI !== 'undefined' && window.electronAPI !== null;
  
  if (hasElectronAPI) {
    console.log('[ElectronCheck] ✅ window.electronAPI is available: true');
    console.log('[ElectronCheck] Available methods:', Object.keys(window.electronAPI));
    return true;
  } else {
    console.warn('[ElectronCheck] ⚠️ window.electronAPI is NOT available');
    console.warn('[ElectronCheck] Running in browser mode - Electron features disabled');
    return false;
  }
}


export async function testPing(): Promise<string | null> {
  if (!window.electronAPI) {
    return null;
  }
  
  try {
    const result = await window.electronAPI.ping();
    console.log('[ElectronCheck] ping() test result:', result);
    return result;
  } catch (error) {
    console.error('[ElectronCheck] ping() test failed:', error);
    return null;
  }
}

