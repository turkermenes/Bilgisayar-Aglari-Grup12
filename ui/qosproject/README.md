# QoS Multi-Objective Routing Application

A desktop application for finding optimal paths in network topologies using Ant Colony Optimization (ACO) and Genetic Algorithms (GA). Built with React, Electron, and Python.

## Features

- **Graph Visualization**: Interactive network graph visualization using Cytoscape.js
- **Multiple Algorithms**: Support for ACO and GA pathfinding algorithms
- **Multi-Objective Optimization**: Optimize for delay, reliability, and resource usage
- **CSV Data Loading**: Load network topology and demand data from CSV files
- **Path Highlighting**: Visual highlighting of found paths on the graph
- **Real-time Metrics**: Display total cost, delay, reliability cost, and resource cost

## Project Structure

```
qosproject/
├── electron/           # Electron main process
│   ├── main.ts        # Main process entry point
│   └── preload.ts     # Preload script for IPC
├── python/            # Python backend
│   ├── solver.py      # Main solver entry point
│   ├── aco_algorithm.py
│   ├── ga_algorithm.py
│   └── requirements.txt
├── src/               # React frontend
│   ├── components/    # React components
│   ├── App.tsx
│   └── main.tsx
└── package.json
```

## Prerequisites

- **Node.js** (v18 or higher)
- **Python** (v3.8 or higher)
- **npm** or **yarn**

## Installation

1. **Clone or navigate to the project directory:**
   ```bash
   cd qosproject
   ```

2. **Install Node.js dependencies:**
   ```bash
   npm install
   ```

3. **Install Python dependencies:**
   ```bash
   cd python
   pip install -r requirements.txt
   cd ..
   ```

## Running the Application

### Development Mode

1. **Start the development server:**
   ```bash
   npm run dev
   ```

   This will:
   - Start the Vite dev server for React (port 5173)
   - Launch Electron when the server is ready

2. **Or run separately:**
   ```bash
   # Terminal 1: Start React dev server
   npm run dev:react

   # Terminal 2: Start Electron
   npm run dev:electron
   ```

### Building for Production

1. **Build the application:**
   ```bash
   npm run build
   ```

2. **The built files will be in:**
   - `dist/renderer/` - React build output
   - `dist/` - Electron main process build

## Usage

1. **Load CSV Files:**
   - Click "Select File" button for each CSV file:
     - **Node Data CSV**: columns `node_id`, `s_ms`, `r_node`
     - **Edge Data CSV**: columns `src`, `dst`, `capacity_mbps`, `delay_ms`, `r_link`
     - **Demand Data CSV**: columns `src`, `dst`, `demand_mbps`
   - In Electron, this will open a file dialog
   - In web mode, use the file input
   - Click "Load Graph" to visualize the network

2. **Configure Algorithm:**
   - Select algorithm: ACO or GA
   - Choose source and target nodes
   - Select or enter demand bandwidth (Mbps)
   - Adjust weights for delay, reliability, and resource (must sum to 1.0)

3. **Run Algorithm:**
   - Click "Run Algorithm"
   - Wait for the algorithm to complete
   - View results in the right panel
   - See the highlighted path on the graph

## CSV File Format

### Node Data CSV
```csv
node_id;s_ms;r_node
0;0,85;0,962
1;0,88;0,977
...
```

**Note:** Decimal values can use comma (`,`) - the application will automatically convert them.

### Edge Data CSV
```csv
src;dst;capacity_mbps;delay_ms;r_link
0;2;502;13;0,968
0;3;855;10;0,967
...
```

### Demand Data CSV
```csv
src;dst;demand_mbps
8;44;200
24;221;172
...
```

## Algorithm Parameters

### ACO Parameters
- `ants`: Number of ants (default: 30)
- `iters`: Number of iterations (default: 200)
- `alpha`: Pheromone influence (default: 1.0)
- `beta`: Heuristic influence (default: 2.0)
- `rho`: Evaporation rate (default: 0.1)

### GA Parameters
- `population`: Population size (default: 100)
- `generations`: Number of generations (default: 25)
- `mutation_rate`: Mutation probability (default: 0.2)
- `elitism`: Elite percentage (default: 0.1)
- `tournament_size`: Tournament selection size (default: 25)

## Troubleshooting

### Python Not Found
- Ensure Python is installed and in your PATH
- On Windows, you may need to use `python` instead of `python3`
- Check by running: `python --version`

### CSV Loading Issues
- Ensure CSV files use semicolon (`;`) as separator
- Check that column names match expected format
- Decimal values can use comma (`,`) - will be auto-converted

### Graph Not Displaying
- Check browser console for errors
- Ensure Cytoscape.js is properly loaded
- Try reloading the graph data

### Algorithm Not Running
- Check that Python dependencies are installed
- Verify CSV file paths are correct
- Check Electron console for error messages

## Development Notes

- The application uses IPC (Inter-Process Communication) between Electron and Python
- Python solver accepts JSON via stdin and outputs JSON via stdout
- Graph is treated as undirected (both directions added automatically)
- Weights are automatically normalized to sum to 1.0

## License

MIT

## Author

QoS Routing Project - BSM307

