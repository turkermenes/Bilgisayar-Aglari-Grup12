export interface ElectronAPI {
  runSolver: (payload: any) => Promise<any>;
  readCSV: (filePath: string) => Promise<{ success: boolean; content?: string; error?: string }>;
  selectFile: (options: { title: string; filters?: any[] }) => Promise<{ success: boolean; filePath?: string | null }>;
}

declare global {
  interface Window {
    electronAPI?: ElectronAPI;
  }
}
