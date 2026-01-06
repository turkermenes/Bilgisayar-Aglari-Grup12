import { app, BrowserWindow, ipcMain, dialog } from 'electron';
import { spawn } from 'child_process';
import * as path from 'path';
import * as fs from 'fs';

let mainWindow: BrowserWindow | null = null;

function createWindow() {
  const isDev = process.env.NODE_ENV === 'development' || !app.isPackaged;
  
 
  const possiblePaths = [
    path.join(__dirname, 'preload.cjs'), 
    path.join(process.cwd(), 'electron', 'preload.cjs'),
    path.join(__dirname, '..', 'electron', 'preload.cjs'),
    path.resolve(__dirname, 'preload.cjs'),
    path.resolve(process.cwd(), 'electron', 'preload.cjs'),
  ];
  
  let preloadPath: string | null = null;
  
  for (const testPath of possiblePaths) {
    const absolutePath = path.resolve(testPath);
    if (fs.existsSync(absolutePath)) {
      preloadPath = absolutePath;
      console.log(`[Main] ✓ Preload script found at: ${preloadPath}`);
      break;
    } else {
      console.log(`[Main] ✗ Preload not found at: ${absolutePath}`);
    }
  }
  
  if (!preloadPath) {
    console.error(`[Main] ❌ Preload script not found in any location!`);
    console.error(`[Main] __dirname: ${__dirname}`);
    console.error(`[Main] process.cwd(): ${process.cwd()}`);
    console.error(`[Main] Tried paths:`, possiblePaths.map(p => path.resolve(p)));
    
    return;
  }

  console.log(`[Main] preload path: ${preloadPath}`);
  console.log(`[Main] Preload file exists: ${fs.existsSync(preloadPath)}`);

  mainWindow = new BrowserWindow({
    width: 1600,
    height: 1000,
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
      preload: preloadPath,
      webSecurity: true,
    },
  });

 
  mainWindow.webContents.on('preload-error', (event, preloadPath, error) => {
    console.error('[Main] ❌ PRELOAD SCRIPT ERROR!');
    console.error('[Main] Path:', preloadPath);
    console.error('[Main] Error:', error);
  });

  
  mainWindow.webContents.on('did-finish-load', () => {
    console.log('[Main] Page finished loading');
    
  
    setTimeout(() => {
      mainWindow?.webContents.executeJavaScript(`
        console.log('[Renderer] window.electronAPI available:', typeof window.electronAPI !== 'undefined');
        if (window.electronAPI) {
          console.log('[Renderer] ✅ electronAPI methods:', Object.keys(window.electronAPI));
        }
      `).catch(err => console.error('[Main] Error executing script:', err));
    }, 500);
  });
  
  if (isDev) {
    console.log('[Main] loading URL: http://localhost:5173');
    mainWindow.loadURL('http://localhost:5173');
    mainWindow.webContents.openDevTools();
  } else {
    mainWindow.loadFile(path.join(__dirname, '../dist/renderer/index.html'));
  }
}


ipcMain.handle('ping', async () => {
  console.log('[Main] ping() called');
  return 'pong';
});

ipcMain.handle('run-solver', async (_event, payload) => {
  console.log('[Main] run-solver called with payload:', payload);
  
 
  const possibleSolverPaths = [
    path.join(process.cwd(), 'python', 'solver.py'),
    path.join(__dirname, '..', 'python', 'solver.py'), 
    path.resolve(process.cwd(), 'python', 'solver.py'),
    path.resolve(__dirname, '..', 'python', 'solver.py'),
  ];
  
  let solverPath: string | null = null;
  for (const testPath of possibleSolverPaths) {
    const absolutePath = path.resolve(testPath);
    if (fs.existsSync(absolutePath)) {
      solverPath = absolutePath;
      console.log(`[Main] ✓ Solver found at: ${solverPath}`);
      break;
    }
  }
  
  if (!solverPath) {
    console.error('[Main] ❌ solver.py not found!');
    console.error('[Main] Tried paths:', possibleSolverPaths.map(p => path.resolve(p)));
    return {
      ok: false,
      best_path: null,
      best_path_str: null,
      metrics: null,
      time_sec: 0,
      error: 'solver.py not found. Please ensure python/solver.py exists.'
    };
  }
  
  
  const isWindows = process.platform === 'win32';
  const pythonCmd = isWindows ? 'py' : 'python3';
  const pythonArgs = isWindows ? ['-3', solverPath] : [solverPath];
  
  console.log(`[Main] Running Python: ${pythonCmd} ${pythonArgs.join(' ')}`);
  
  return new Promise((resolve) => {
    const proc = spawn(pythonCmd, pythonArgs, {
      stdio: ['pipe', 'pipe', 'pipe'],
      cwd: path.dirname(solverPath)
    });
    
    let stdout = '';
    let stderr = '';
    
    proc.stdout.on('data', (data) => {
      stdout += data.toString();
    });
    
    proc.stderr.on('data', (data) => {
      stderr += data.toString();
    });
    
    proc.on('close', (code) => {
      if (stderr) {
        console.error('[Python stderr]', stderr);
      }
      
      if (code !== 0) {
        console.error(`[Main] Python process exited with code ${code}`);
        resolve({
          ok: false,
          best_path: null,
          best_path_str: null,
          metrics: null,
          time_sec: 0,
          error: `Python process failed with code ${code}. ${stderr.slice(0, 500)}`
        });
        return;
      }
      
      try {
        
        const jsonResult = JSON.parse(stdout.trim());
        console.log('[Main] Python solver returned:', jsonResult.ok ? 'SUCCESS' : 'FAILED');
        resolve(jsonResult);
      } catch (e: any) {
        console.error('[Main] Failed to parse Python output:', e.message);
        console.error('[Main] stdout (first 2000 chars):', stdout.slice(0, 2000));
        resolve({
          ok: false,
          best_path: null,
          best_path_str: null,
          metrics: null,
          time_sec: 0,
          error: `Failed to parse solver output. code=${code}. stdout=${stdout.slice(0, 2000)}`
        });
      }
    });
    
    proc.on('error', (error) => {
      console.error('[Main] Failed to start Python process:', error);
      resolve({
        ok: false,
        best_path: null,
        best_path_str: null,
        metrics: null,
        time_sec: 0,
        error: `Failed to start Python: ${error.message}`
      });
    });
    
   
    try {
      const inputJson = JSON.stringify(payload);
      proc.stdin.write(inputJson);
      proc.stdin.end();
    } catch (e: any) {
      console.error('[Main] Failed to write to Python stdin:', e);
      resolve({
        ok: false,
        best_path: null,
        best_path_str: null,
        metrics: null,
        time_sec: 0,
        error: `Failed to send payload to Python: ${e.message}`
      });
    }
  });
});

app.whenReady().then(() => {
  console.log('[Main] App ready, creating window...');
  createWindow();

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      createWindow();
    }
  });
});

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    app.quit();
  }
});


ipcMain.handle('select-file', async (event, options: { title: string; filters?: any[] }) => {
  const result = await dialog.showOpenDialog(mainWindow!, {
    title: options.title,
    filters: options.filters || [{ name: 'CSV Files', extensions: ['csv'] }],
    properties: ['openFile'],
  });

  if (result.canceled) {
    return { success: false, filePath: null };
  }

  return { success: true, filePath: result.filePaths[0] };
});


ipcMain.handle('read-csv', async (event, filePath: string) => {
  try {
    if (!filePath) {
      throw new Error('No file path provided');
    }
    
  
    const absolutePath = path.isAbsolute(filePath) 
      ? filePath 
      : path.join(app.getAppPath(), filePath);
    
    if (!fs.existsSync(absolutePath)) {
      throw new Error(`File not found: ${absolutePath}`);
    }
    
    const content = fs.readFileSync(absolutePath, 'utf-8');
    return { success: true, content };
  } catch (error: any) {
    return { success: false, error: error.message };
  }
});


