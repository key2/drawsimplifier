# Draw Simplifier

A web application that simplifies DXF and SVG files by converting individual line segments into continuous polylines/paths.

## Features

- **Upload DXF or SVG files** via a modern drag-and-drop web interface
- **Automatic simplification** - converts LINE entities (DXF) or line segments (SVG) into continuous polylines
- **Format conversion** - outputs both DXF and SVG versions of the simplified drawing
- **ZIP download** - get both formats in a single ZIP file
- **Statistics** - view reduction ratio and other metrics after processing

## Installation

This project uses [PDM](https://pdm-project.org/) for dependency management.

```bash
# Install PDM if you haven't already
pip install pdm

# Install dependencies
pdm install
```

## Usage

### Start the Web Server

```bash
# Using PDM scripts
pdm run serve

# Or with development mode (auto-reload)
pdm run dev

# Or directly with uvicorn
pdm run uvicorn drawsimplifier.app:app --reload --host 0.0.0.0 --port 8000
```

Then open your browser to http://localhost:8000

### Command Line Usage

You can also use the simplification functions directly in Python:

```python
from drawsimplifier import simplify_dxf, simplify_svg, dxf_to_svg, svg_to_dxf

# Simplify a DXF file
stats = simplify_dxf("input.dxf", "output.dxf")
print(f"Reduced {stats['original_line_count']} lines to {stats['polyline_count']} polylines")

# Simplify an SVG file
stats = simplify_svg("input.svg", "output.svg")
print(f"Reduced {stats['original_segment_count']} segments to {stats['polyline_count']} paths")

# Convert between formats
with open("input.dxf", "rb") as f:
    dxf_bytes = f.read()
svg_bytes = dxf_to_svg(dxf_bytes)

with open("input.svg", "rb") as f:
    svg_bytes = f.read()
dxf_bytes = svg_to_dxf(svg_bytes)
```

## How It Works

1. **Parse Input**: The application reads the input file and extracts all line segments
2. **Build Graph**: Line segments are converted into a graph where points are nodes and segments are edges
3. **Find Paths**: The algorithm identifies endpoints (degree 1) and junctions (degree 3+), then traces continuous paths
4. **Output**: Continuous polylines are written to the output file, significantly reducing the number of entities

## API Endpoints

- `GET /` - Web interface for file upload
- `POST /simplify` - Upload a file and receive a ZIP with simplified versions
- `GET /health` - Health check endpoint

## Development

```bash
# Install development dependencies
pdm install -d

# Run tests
pdm run pytest

# Run with auto-reload
pdm run dev
```

## Deployment on Render.com

This project is configured for easy deployment on [Render.com](https://render.com).

### Option 1: Deploy with Blueprint (Recommended)

1. Push this repository to GitHub/GitLab
2. Go to [Render Dashboard](https://dashboard.render.com)
3. Click "New" → "Blueprint"
4. Connect your repository
5. Render will automatically detect the `render.yaml` and configure the service

### Option 2: Manual Deployment

1. Push this repository to GitHub/GitLab
2. Go to [Render Dashboard](https://dashboard.render.com)
3. Click "New" → "Web Service"
4. Connect your repository
5. Configure the service:
   - **Runtime**: Python
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `uvicorn drawsimplifier.app:app --host 0.0.0.0 --port $PORT`
   - **Environment Variables**:
     - `PYTHON_VERSION`: `3.13.0`
     - `PYTHONPATH`: `src`

### Environment Variables

| Variable | Value | Description |
|----------|-------|-------------|
| `PYTHON_VERSION` | `3.13.0` | Python version to use |
| `PYTHONPATH` | `src` | Path to source code |

## License

MIT License
