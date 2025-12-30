"""
Draw Simplifier Web Application.

A FastAPI web server that allows uploading DXF or SVG files,
simplifies them, converts to both formats, and provides a ZIP download.
"""

import io
import zipfile
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, File, UploadFile, HTTPException, Request
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from .simplify_dxf import simplify_dxf_bytes
from .simplify_svg import simplify_svg_bytes
from .converter import dxf_to_svg, svg_to_dxf

app = FastAPI(
    title="Draw Simplifier",
    description="Simplify DXF and SVG files by converting line segments to continuous polylines",
    version="0.1.0"
)


# HTML template for the upload page
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Draw Simplifier</title>
    <style>
        * {
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }
        
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            display: flex;
            justify-content: center;
            align-items: center;
            padding: 20px;
        }
        
        .container {
            background: white;
            border-radius: 20px;
            box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
            padding: 40px;
            max-width: 500px;
            width: 100%;
        }
        
        h1 {
            color: #333;
            text-align: center;
            margin-bottom: 10px;
            font-size: 2em;
        }
        
        .subtitle {
            color: #666;
            text-align: center;
            margin-bottom: 30px;
            font-size: 0.95em;
        }
        
        .upload-area {
            border: 3px dashed #ddd;
            border-radius: 15px;
            padding: 40px 20px;
            text-align: center;
            transition: all 0.3s ease;
            cursor: pointer;
            margin-bottom: 20px;
        }
        
        .upload-area:hover, .upload-area.dragover {
            border-color: #667eea;
            background: #f8f9ff;
        }
        
        .upload-area svg {
            width: 60px;
            height: 60px;
            margin-bottom: 15px;
            color: #667eea;
        }
        
        .upload-area p {
            color: #666;
            margin-bottom: 10px;
        }
        
        .upload-area .formats {
            font-size: 0.85em;
            color: #999;
        }
        
        #file-input {
            display: none;
        }
        
        .file-name {
            background: #f0f0f0;
            padding: 10px 15px;
            border-radius: 8px;
            margin-bottom: 20px;
            display: none;
            align-items: center;
            justify-content: space-between;
        }
        
        .file-name.visible {
            display: flex;
        }
        
        .file-name span {
            color: #333;
            font-weight: 500;
        }
        
        .file-name button {
            background: none;
            border: none;
            color: #999;
            cursor: pointer;
            font-size: 1.2em;
        }
        
        .submit-btn {
            width: 100%;
            padding: 15px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border: none;
            border-radius: 10px;
            font-size: 1.1em;
            font-weight: 600;
            cursor: pointer;
            transition: transform 0.2s, box-shadow 0.2s;
        }
        
        .submit-btn:hover {
            transform: translateY(-2px);
            box-shadow: 0 5px 20px rgba(102, 126, 234, 0.4);
        }
        
        .submit-btn:disabled {
            background: #ccc;
            cursor: not-allowed;
            transform: none;
            box-shadow: none;
        }
        
        .loading {
            display: none;
            text-align: center;
            padding: 20px;
        }
        
        .loading.visible {
            display: block;
        }
        
        .spinner {
            width: 40px;
            height: 40px;
            border: 4px solid #f3f3f3;
            border-top: 4px solid #667eea;
            border-radius: 50%;
            animation: spin 1s linear infinite;
            margin: 0 auto 15px;
        }
        
        @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }
        
        .error {
            background: #ffe6e6;
            color: #cc0000;
            padding: 15px;
            border-radius: 10px;
            margin-bottom: 20px;
            display: none;
        }
        
        .error.visible {
            display: block;
        }
        
        .success {
            background: #e6ffe6;
            color: #006600;
            padding: 15px;
            border-radius: 10px;
            margin-bottom: 20px;
            display: none;
            text-align: center;
        }
        
        .success.visible {
            display: block;
        }
        
        .stats {
            background: #f8f9ff;
            padding: 15px;
            border-radius: 10px;
            margin-top: 20px;
            display: none;
        }
        
        .stats.visible {
            display: block;
        }
        
        .stats h3 {
            color: #333;
            margin-bottom: 10px;
            font-size: 1em;
        }
        
        .stats-grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 10px;
        }
        
        .stat-item {
            background: white;
            padding: 10px;
            border-radius: 8px;
            text-align: center;
        }
        
        .stat-value {
            font-size: 1.5em;
            font-weight: bold;
            color: #667eea;
        }
        
        .stat-label {
            font-size: 0.8em;
            color: #666;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>🎨 Draw Simplifier</h1>
        <p class="subtitle">Simplify DXF and SVG files by merging line segments into continuous polylines</p>
        
        <form id="upload-form" enctype="multipart/form-data">
            <div class="upload-area" id="upload-area">
                <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
                </svg>
                <p>Drag & drop your file here</p>
                <p>or click to browse</p>
                <p class="formats">Supported formats: .dxf, .svg</p>
            </div>
            
            <input type="file" id="file-input" name="file" accept=".dxf,.svg">
            
            <div class="file-name" id="file-name">
                <span id="file-name-text"></span>
                <button type="button" id="clear-file">&times;</button>
            </div>
            
            <div class="error" id="error"></div>
            <div class="success" id="success"></div>
            
            <div class="loading" id="loading">
                <div class="spinner"></div>
                <p>Processing your file...</p>
            </div>
            
            <button type="submit" class="submit-btn" id="submit-btn" disabled>
                Simplify & Download
            </button>
            
            <div class="stats" id="stats">
                <h3>📊 Simplification Statistics</h3>
                <div class="stats-grid">
                    <div class="stat-item">
                        <div class="stat-value" id="stat-original">-</div>
                        <div class="stat-label">Original Elements</div>
                    </div>
                    <div class="stat-item">
                        <div class="stat-value" id="stat-simplified">-</div>
                        <div class="stat-label">Simplified Paths</div>
                    </div>
                    <div class="stat-item">
                        <div class="stat-value" id="stat-ratio">-</div>
                        <div class="stat-label">Reduction Ratio</div>
                    </div>
                    <div class="stat-item">
                        <div class="stat-value" id="stat-points">-</div>
                        <div class="stat-label">Unique Points</div>
                    </div>
                </div>
            </div>
        </form>
    </div>
    
    <script>
        const uploadArea = document.getElementById('upload-area');
        const fileInput = document.getElementById('file-input');
        const fileName = document.getElementById('file-name');
        const fileNameText = document.getElementById('file-name-text');
        const clearFile = document.getElementById('clear-file');
        const submitBtn = document.getElementById('submit-btn');
        const form = document.getElementById('upload-form');
        const loading = document.getElementById('loading');
        const error = document.getElementById('error');
        const success = document.getElementById('success');
        const stats = document.getElementById('stats');
        
        // Drag and drop
        uploadArea.addEventListener('dragover', (e) => {
            e.preventDefault();
            uploadArea.classList.add('dragover');
        });
        
        uploadArea.addEventListener('dragleave', () => {
            uploadArea.classList.remove('dragover');
        });
        
        uploadArea.addEventListener('drop', (e) => {
            e.preventDefault();
            uploadArea.classList.remove('dragover');
            const files = e.dataTransfer.files;
            if (files.length > 0) {
                handleFile(files[0]);
            }
        });
        
        uploadArea.addEventListener('click', () => {
            fileInput.click();
        });
        
        fileInput.addEventListener('change', () => {
            if (fileInput.files.length > 0) {
                handleFile(fileInput.files[0]);
            }
        });
        
        clearFile.addEventListener('click', () => {
            fileInput.value = '';
            fileName.classList.remove('visible');
            submitBtn.disabled = true;
            error.classList.remove('visible');
            success.classList.remove('visible');
            stats.classList.remove('visible');
        });
        
        function handleFile(file) {
            const ext = file.name.split('.').pop().toLowerCase();
            if (ext !== 'dxf' && ext !== 'svg') {
                showError('Please upload a .dxf or .svg file');
                return;
            }
            
            fileNameText.textContent = file.name;
            fileName.classList.add('visible');
            submitBtn.disabled = false;
            error.classList.remove('visible');
            success.classList.remove('visible');
            stats.classList.remove('visible');
            
            // Create a new FileList-like object
            const dataTransfer = new DataTransfer();
            dataTransfer.items.add(file);
            fileInput.files = dataTransfer.files;
        }
        
        function showError(message) {
            error.textContent = message;
            error.classList.add('visible');
            success.classList.remove('visible');
        }
        
        function showSuccess(message) {
            success.textContent = message;
            success.classList.add('visible');
            error.classList.remove('visible');
        }
        
        form.addEventListener('submit', async (e) => {
            e.preventDefault();
            
            if (!fileInput.files.length) {
                showError('Please select a file');
                return;
            }
            
            const formData = new FormData();
            formData.append('file', fileInput.files[0]);
            
            loading.classList.add('visible');
            submitBtn.disabled = true;
            error.classList.remove('visible');
            success.classList.remove('visible');
            stats.classList.remove('visible');
            
            try {
                const response = await fetch('/simplify', {
                    method: 'POST',
                    body: formData
                });
                
                if (!response.ok) {
                    const data = await response.json();
                    throw new Error(data.detail || 'Failed to process file');
                }
                
                // Get stats from header
                const statsHeader = response.headers.get('X-Stats');
                if (statsHeader) {
                    const statsData = JSON.parse(statsHeader);
                    document.getElementById('stat-original').textContent = 
                        statsData.original_line_count || statsData.original_segment_count || '-';
                    document.getElementById('stat-simplified').textContent = 
                        statsData.polyline_count || '-';
                    document.getElementById('stat-ratio').textContent = 
                        statsData.reduction_ratio ? statsData.reduction_ratio.toFixed(2) + 'x' : '-';
                    document.getElementById('stat-points').textContent = 
                        statsData.unique_points || '-';
                    stats.classList.add('visible');
                }
                
                // Download the file
                const blob = await response.blob();
                const url = window.URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = response.headers.get('Content-Disposition')?.split('filename=')[1]?.replace(/"/g, '') || 'simplified.zip';
                document.body.appendChild(a);
                a.click();
                window.URL.revokeObjectURL(url);
                a.remove();
                
                showSuccess('File simplified successfully! Download started.');
                
            } catch (err) {
                showError(err.message);
            } finally {
                loading.classList.remove('visible');
                submitBtn.disabled = false;
            }
        });
    </script>
</body>
</html>
"""


@app.get("/", response_class=HTMLResponse)
@app.head("/")
async def index():
    """Serve the main upload page."""
    return HTML_TEMPLATE


@app.post("/simplify")
async def simplify_file(file: UploadFile = File(...)):
    """
    Simplify an uploaded DXF or SVG file.
    
    Returns a ZIP file containing both simplified DXF and SVG versions.
    """
    # Validate file extension
    filename = file.filename or "unknown"
    ext = Path(filename).suffix.lower()
    
    if ext not in ('.dxf', '.svg'):
        raise HTTPException(
            status_code=400,
            detail="Unsupported file format. Please upload a .dxf or .svg file."
        )
    
    # Read file content
    content = await file.read()
    
    if not content:
        raise HTTPException(status_code=400, detail="Empty file uploaded.")
    
    try:
        # Process based on file type
        if ext == '.dxf':
            # Simplify DXF
            simplified_dxf, stats = simplify_dxf_bytes(content)
            # Convert to SVG
            simplified_svg = dxf_to_svg(simplified_dxf)
        else:  # .svg
            # Simplify SVG
            simplified_svg, stats = simplify_svg_bytes(content)
            # Convert to DXF
            simplified_dxf = svg_to_dxf(simplified_svg)
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error processing file: {str(e)}"
        )
    
    # Create ZIP file
    zip_buffer = io.BytesIO()
    base_name = Path(filename).stem
    
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(f"{base_name}_simplified.dxf", simplified_dxf)
        zf.writestr(f"{base_name}_simplified.svg", simplified_svg)
    
    zip_buffer.seek(0)
    
    # Return ZIP file with stats in header
    import json
    headers = {
        "Content-Disposition": f'attachment; filename="{base_name}_simplified.zip"',
        "X-Stats": json.dumps(stats)
    }
    
    return StreamingResponse(
        zip_buffer,
        media_type="application/zip",
        headers=headers
    )


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "draw-simplifier"}


def main():
    """Run the application with uvicorn."""
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)


if __name__ == "__main__":
    main()
