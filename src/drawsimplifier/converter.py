"""
File format converter between DXF and SVG.

This module provides conversion utilities between DXF and SVG formats,
using the polyline data extracted from either format.
"""

import ezdxf
import xml.etree.ElementTree as ET
from io import BytesIO, StringIO
from typing import List, Tuple

# Type aliases
Point = Tuple[float, float]

# SVG namespace
SVG_NS = "http://www.w3.org/2000/svg"


def extract_polylines_from_dxf(dxf_bytes: bytes) -> List[List[Point]]:
    """
    Extract polylines from a DXF file.
    
    Args:
        dxf_bytes: DXF file content as bytes
        
    Returns:
        List of polylines, where each polyline is a list of (x, y) points
    """
    # ezdxf expects text stream, so decode bytes first
    input_stream = StringIO(dxf_bytes.decode('utf-8', errors='ignore'))
    doc = ezdxf.read(input_stream)
    msp = doc.modelspace()
    
    polylines = []
    
    # Extract LWPOLYLINE entities
    for entity in msp.query("LWPOLYLINE"):
        points = [(p[0], p[1]) for p in entity.get_points()]
        if len(points) >= 2:
            polylines.append(points)
    
    # Extract POLYLINE entities (2D)
    for entity in msp.query("POLYLINE"):
        points = [(v.dxf.location.x, v.dxf.location.y) for v in entity.vertices]
        if len(points) >= 2:
            polylines.append(points)
    
    # Extract LINE entities
    for entity in msp.query("LINE"):
        start = (entity.dxf.start.x, entity.dxf.start.y)
        end = (entity.dxf.end.x, entity.dxf.end.y)
        polylines.append([start, end])
    
    return polylines


def extract_polylines_from_svg(svg_bytes: bytes) -> List[List[Point]]:
    """
    Extract polylines from an SVG file.
    
    Args:
        svg_bytes: SVG file content as bytes
        
    Returns:
        List of polylines, where each polyline is a list of (x, y) points
    """
    import re
    
    root = ET.fromstring(svg_bytes)
    polylines = []
    
    for elem in root.iter():
        tag = elem.tag.split('}')[-1] if '}' in elem.tag else elem.tag
        
        if tag == 'path':
            d = elem.get('d', '')
            if d:
                points = parse_svg_path_to_points(d)
                if len(points) >= 2:
                    polylines.append(points)
        
        elif tag == 'line':
            try:
                x1 = float(elem.get('x1', 0))
                y1 = float(elem.get('y1', 0))
                x2 = float(elem.get('x2', 0))
                y2 = float(elem.get('y2', 0))
                polylines.append([(x1, y1), (x2, y2)])
            except (ValueError, TypeError):
                pass
        
        elif tag in ('polyline', 'polygon'):
            points_str = elem.get('points', '')
            numbers = re.findall(r'-?\d+\.?\d*(?:[eE][+-]?\d+)?', points_str)
            points = []
            for i in range(0, len(numbers) - 1, 2):
                x = float(numbers[i])
                y = float(numbers[i + 1])
                points.append((x, y))
            if len(points) >= 2:
                polylines.append(points)
    
    return polylines


def parse_svg_path_to_points(d: str) -> List[Point]:
    """
    Parse SVG path 'd' attribute and extract points.
    
    Args:
        d: SVG path data string
        
    Returns:
        List of (x, y) points
    """
    import re
    
    points = []
    token_pattern = r'([MLHVZmlhvz])|(-?(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?)'
    tokens = re.findall(token_pattern, d)
    
    current_pos = (0.0, 0.0)
    path_start = (0.0, 0.0)
    command = 'M'
    i = 0
    
    while i < len(tokens):
        token = tokens[i]
        
        if token[0]:  # It's a command
            command = token[0]
            i += 1
            
            if command in ('Z', 'z'):
                if path_start != current_pos:
                    points.append(path_start)
                current_pos = path_start
            continue
        
        if command in ('M', 'm'):
            x = float(token[1])
            i += 1
            if i < len(tokens) and tokens[i][1]:
                y = float(tokens[i][1])
                i += 1
            else:
                continue
            
            if command == 'm':
                current_pos = (current_pos[0] + x, current_pos[1] + y)
            else:
                current_pos = (x, y)
            
            path_start = current_pos
            points.append(current_pos)
            command = 'L' if command == 'M' else 'l'
            
        elif command in ('L', 'l'):
            x = float(token[1])
            i += 1
            if i < len(tokens) and tokens[i][1]:
                y = float(tokens[i][1])
                i += 1
            else:
                continue
            
            if command == 'l':
                current_pos = (current_pos[0] + x, current_pos[1] + y)
            else:
                current_pos = (x, y)
            
            points.append(current_pos)
            
        elif command in ('H', 'h'):
            x = float(token[1])
            i += 1
            
            if command == 'h':
                current_pos = (current_pos[0] + x, current_pos[1])
            else:
                current_pos = (x, current_pos[1])
            
            points.append(current_pos)
            
        elif command in ('V', 'v'):
            y = float(token[1])
            i += 1
            
            if command == 'v':
                current_pos = (current_pos[0], current_pos[1] + y)
            else:
                current_pos = (current_pos[0], y)
            
            points.append(current_pos)
            
        else:
            i += 1
    
    return points


def polylines_to_dxf(polylines: List[List[Point]]) -> bytes:
    """
    Convert polylines to DXF format.
    
    Args:
        polylines: List of polylines, where each polyline is a list of (x, y) points
        
    Returns:
        DXF file content as bytes
    """
    doc = ezdxf.new(dxfversion='R2000')
    msp = doc.modelspace()
    
    for points in polylines:
        if len(points) >= 2:
            msp.add_lwpolyline(points)
    
    # ezdxf writes strings, so we use StringIO and encode
    output_stream = StringIO()
    doc.write(output_stream)
    return output_stream.getvalue().encode('utf-8')


def polylines_to_svg(polylines: List[List[Point]], width: float = None, height: float = None, units: str = "mm") -> bytes:
    """
    Convert polylines to SVG format.
    
    Args:
        polylines: List of polylines, where each polyline is a list of (x, y) points
        width: Optional SVG width
        height: Optional SVG height
        units: Units for width/height (default: "mm")
        
    Returns:
        SVG file content as bytes
    """
    # Calculate bounds
    if not polylines:
        min_x, min_y, max_x, max_y = 0, 0, 100, 100
    else:
        all_points = [p for polyline in polylines for p in polyline]
        min_x = min(p[0] for p in all_points)
        max_x = max(p[0] for p in all_points)
        min_y = min(p[1] for p in all_points)
        max_y = max(p[1] for p in all_points)
    
    # No margin - use exact bounds
    svg_width = width or (max_x - min_x)
    svg_height = height or (max_y - min_y)
    
    # Register namespace
    ET.register_namespace('', SVG_NS)
    
    # Create SVG root
    root = ET.Element('svg')
    root.set('xmlns', SVG_NS)
    root.set('width', f"{svg_width}{units}")
    root.set('height', f"{svg_height}{units}")
    # SVG Y-axis goes down, DXF Y-axis goes up, so we flip by using negative Y in viewBox
    # viewBox: min-x, min-y (which is -max_y to flip), width, height
    root.set('viewBox', f"{min_x} {-max_y} {max_x - min_x} {max_y - min_y}")
    
    # Add paths with Y-axis flipped
    for points in polylines:
        if len(points) < 2:
            continue
        
        # Flip Y coordinates for SVG (negate Y values)
        d_parts = [f"M {points[0][0]},{-points[0][1]}"]
        for point in points[1:]:
            d_parts.append(f"L {point[0]},{-point[1]}")
        
        path_elem = ET.SubElement(root, 'path')
        path_elem.set('d', ' '.join(d_parts))
        path_elem.set('stroke', 'black')
        path_elem.set('fill', 'none')
        path_elem.set('stroke-width', '0.5')
    
    # Generate output
    output = '<?xml version="1.0" encoding="UTF-8"?>\n'
    output += ET.tostring(root, encoding='unicode')
    return output.encode('utf-8')


def dxf_to_svg(dxf_bytes: bytes) -> bytes:
    """
    Convert DXF file to SVG format.
    
    Args:
        dxf_bytes: DXF file content as bytes
        
    Returns:
        SVG file content as bytes
    """
    polylines = extract_polylines_from_dxf(dxf_bytes)
    return polylines_to_svg(polylines)


def svg_to_dxf(svg_bytes: bytes) -> bytes:
    """
    Convert SVG file to DXF format.
    
    Args:
        svg_bytes: SVG file content as bytes
        
    Returns:
        DXF file content as bytes
    """
    polylines = extract_polylines_from_svg(svg_bytes)
    return polylines_to_dxf(polylines)
