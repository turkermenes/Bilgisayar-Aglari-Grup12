# Setup Instructions

## Quick Start

1. **Install dependencies:**
   ```bash
   npm install
   cd python
   pip install -r requirements.txt
   cd ..
   ```

2. **Build preload script (first time only):**
   ```bash
   npm run build:preload
   ```

3. **Run in development:**
   ```bash
   npm run dev
   ```

## File Path Handling

The application handles CSV files in two ways:

### Electron Mode (Desktop App)
- Uses Electron's file dialog to select files
- Stores absolute file paths
- Passes absolute paths to Python solver

### Web Mode (Development)
- Uses HTML file input
- Reads file contents directly
- Stores file names (Python solver will need files in a known location)

**Note:** For production Electron builds, ensure CSV files are accessible or copy them to a temp directory.

## Python Solver

The Python solver (`python/solver.py`) expects:
- Absolute file paths to CSV files
- JSON input via stdin
- Outputs JSON via stdout

Example input:
```json
{
  "algorithm": "ACO",
  "nodes_csv": "/path/to/NodeData.csv",
  "edges_csv": "/path/to/EdgeData.csv",
  "source": 1,
  "target": 44,
  "demand_mbps": 200,
  "weights": {
    "delay": 0.5,
    "reliability": 0.25,
    "resource": 0.25
  },
  "params": {
    "aco": { "ants": 30, "iters": 200 },
    "ga": { "population": 100, "generations": 25 }
  }
}
```

## Troubleshooting

### "solver.py not found"
- Ensure you're running from the project root
- Check that `python/solver.py` exists
- Verify Python path in `electron/main.ts`

### "Python process failed"
- Check Python is installed: `python --version`
- Verify dependencies: `pip install -r python/requirements.txt`
- Check Python path (Windows: `python`, Linux/Mac: `python3`)

### CSV files not loading
- Check file paths are correct
- Verify CSV format (semicolon separator, correct columns)
- Check browser/Electron console for errors

### Graph not displaying
- Ensure Cytoscape.js is loaded
- Check browser console for errors
- Verify graph data is valid (nodes and edges)

