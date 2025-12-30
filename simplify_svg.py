#!/usr/bin/env python3
"""
SVG Line Simplifier - Converts line segments to continuous polylines/paths.

This script reads an SVG file containing many line segments (either as <line> elements
or as individual L commands in paths), builds a graph representation, and outputs
a simplified SVG with continuous path elements.
"""

import re
import xml.etree.ElementTree as ET
from collections import defaultdict
from typing import Dict, List, Set, Tuple, Optional
from pathlib import Path

# Type aliases
Point = Tuple[float, float]
Edge = Tuple[Point, Point]

# SVG namespace
SVG_NS = "http://www.w3.org/2000/svg"
NAMESPACES = {"svg": SVG_NS}


def round_point(x: float, y: float, decimals: int = 6) -> Point:
    """Round point coordinates to handle floating-point precision issues."""
    return (round(x, decimals), round(y, decimals))


def parse_path_d(d: str) -> List[Tuple[Point, Point]]:
    """
    Parse SVG path 'd' attribute and extract line segments.
    
    Handles M (moveto), L (lineto), H (horizontal), V (vertical), and Z (closepath).
    Returns list of (start, end) tuples for each line segment.
    """
    segments = []
    
    # Tokenize the path data - match commands and numbers separately
    # Commands: M, m, L, l, H, h, V, v, Z, z
    # Numbers: integers, decimals, scientific notation, with optional sign
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
            
            # Handle Z/z immediately (no parameters)
            if command in ('Z', 'z'):
                # Close path - draw line back to start
                start = round_point(current_pos[0], current_pos[1])
                end = round_point(path_start[0], path_start[1])
                if start != end:
                    segments.append((start, end))
                current_pos = path_start
            continue
        
        # It's a number - process based on current command
        if command in ('M', 'm'):
            x = float(token[1])
            i += 1
            if i < len(tokens) and tokens[i][1]:
                y = float(tokens[i][1])
                i += 1
            else:
                continue
            
            if command == 'm':  # relative
                current_pos = (current_pos[0] + x, current_pos[1] + y)
            else:  # absolute
                current_pos = (x, y)
            
            path_start = current_pos
            # After M, subsequent coordinates are treated as L
            command = 'L' if command == 'M' else 'l'
            
        elif command in ('L', 'l'):
            x = float(token[1])
            i += 1
            if i < len(tokens) and tokens[i][1]:
                y = float(tokens[i][1])
                i += 1
            else:
                continue
            
            if command == 'l':  # relative
                new_pos = (current_pos[0] + x, current_pos[1] + y)
            else:  # absolute
                new_pos = (x, y)
            
            start = round_point(current_pos[0], current_pos[1])
            end = round_point(new_pos[0], new_pos[1])
            if start != end:
                segments.append((start, end))
            current_pos = new_pos
            
        elif command in ('H', 'h'):
            x = float(token[1])
            i += 1
            
            if command == 'h':  # relative
                new_pos = (current_pos[0] + x, current_pos[1])
            else:  # absolute
                new_pos = (x, current_pos[1])
            
            start = round_point(current_pos[0], current_pos[1])
            end = round_point(new_pos[0], new_pos[1])
            if start != end:
                segments.append((start, end))
            current_pos = new_pos
            
        elif command in ('V', 'v'):
            y = float(token[1])
            i += 1
            
            if command == 'v':  # relative
                new_pos = (current_pos[0], current_pos[1] + y)
            else:  # absolute
                new_pos = (current_pos[0], y)
            
            start = round_point(current_pos[0], current_pos[1])
            end = round_point(new_pos[0], new_pos[1])
            if start != end:
                segments.append((start, end))
            current_pos = new_pos
            
        else:
            # Skip unknown commands/tokens
            i += 1
    
    return segments


def parse_line_element(elem: ET.Element) -> Optional[Tuple[Point, Point]]:
    """Parse an SVG <line> element and return the segment."""
    try:
        x1 = float(elem.get('x1', 0))
        y1 = float(elem.get('y1', 0))
        x2 = float(elem.get('x2', 0))
        y2 = float(elem.get('y2', 0))
        
        start = round_point(x1, y1)
        end = round_point(x2, y2)
        
        if start != end:
            return (start, end)
    except (ValueError, TypeError):
        pass
    return None


def parse_polyline_element(elem: ET.Element) -> List[Tuple[Point, Point]]:
    """Parse an SVG <polyline> or <polygon> element and return segments."""
    segments = []
    points_str = elem.get('points', '')
    
    # Parse points (format: "x1,y1 x2,y2 ..." or "x1 y1 x2 y2 ...")
    numbers = re.findall(r'-?\d+\.?\d*(?:[eE][+-]?\d+)?', points_str)
    
    points = []
    for i in range(0, len(numbers) - 1, 2):
        x = float(numbers[i])
        y = float(numbers[i + 1])
        points.append(round_point(x, y))
    
    # Create segments from consecutive points
    for i in range(len(points) - 1):
        if points[i] != points[i + 1]:
            segments.append((points[i], points[i + 1]))
    
    # For polygon, close the path
    if elem.tag.endswith('polygon') and len(points) >= 2:
        if points[-1] != points[0]:
            segments.append((points[-1], points[0]))
    
    return segments


def extract_segments_from_svg(root: ET.Element) -> List[Tuple[Point, Point]]:
    """Extract all line segments from SVG elements."""
    segments = []
    
    # Process all elements recursively
    for elem in root.iter():
        tag = elem.tag.split('}')[-1] if '}' in elem.tag else elem.tag  # Remove namespace
        
        if tag == 'line':
            seg = parse_line_element(elem)
            if seg:
                segments.append(seg)
                
        elif tag == 'path':
            d = elem.get('d', '')
            if d:
                segments.extend(parse_path_d(d))
                
        elif tag in ('polyline', 'polygon'):
            segments.extend(parse_polyline_element(elem))
    
    return segments


def build_graph(segments: List[Tuple[Point, Point]]) -> Dict[Point, List[Point]]:
    """
    Build an adjacency graph from line segments.
    
    Each point is a node, and each line segment creates bidirectional edges.
    """
    graph: Dict[Point, List[Point]] = defaultdict(list)
    
    for start, end in segments:
        # Skip zero-length segments
        if start == end:
            continue
        
        # Add bidirectional edges
        graph[start].append(end)
        graph[end].append(start)
    
    return graph


def get_edge_key(p1: Point, p2: Point) -> Edge:
    """Create a canonical edge key (smaller point first) for tracking visited edges."""
    return (min(p1, p2), max(p1, p2))


def find_endpoints_and_junctions(graph: Dict[Point, List[Point]]) -> Tuple[Set[Point], Set[Point]]:
    """
    Identify endpoints (degree 1) and junctions (degree 3+) in the graph.
    
    Returns:
        Tuple of (endpoints, junctions)
    """
    endpoints: Set[Point] = set()
    junctions: Set[Point] = set()
    
    for point, neighbors in graph.items():
        degree = len(neighbors)
        if degree == 1:
            endpoints.add(point)
        elif degree >= 3:
            junctions.add(point)
    
    return endpoints, junctions


def trace_path(
    start: Point,
    graph: Dict[Point, List[Point]],
    visited_edges: Set[Edge],
    endpoints: Set[Point],
    junctions: Set[Point]
) -> List[Point]:
    """
    Trace a continuous path from a starting point.
    
    Follows connections until reaching an endpoint, junction, or dead end.
    Marks edges as visited to avoid duplicates.
    
    Returns:
        List of points forming the path
    """
    path = [start]
    current = start
    
    while True:
        neighbors = graph[current]
        next_point = None
        
        for neighbor in neighbors:
            edge_key = get_edge_key(current, neighbor)
            if edge_key not in visited_edges:
                next_point = neighbor
                visited_edges.add(edge_key)
                break
        
        if next_point is None:
            # No unvisited edges from current point
            break
        
        path.append(next_point)
        
        # Stop if we've reached an endpoint or junction (but include it in path)
        if next_point in endpoints or next_point in junctions:
            break
        
        current = next_point
    
    return path


def extract_polylines(graph: Dict[Point, List[Point]]) -> List[List[Point]]:
    """
    Extract all continuous polylines from the graph.
    
    Strategy:
    1. Start from endpoints (degree 1 nodes) first
    2. Then handle remaining edges from junctions
    3. Finally handle any isolated loops
    
    Returns:
        List of polylines, where each polyline is a list of points
    """
    visited_edges: Set[Edge] = set()
    polylines: List[List[Point]] = []
    
    endpoints, junctions = find_endpoints_and_junctions(graph)
    
    # First, trace paths starting from endpoints
    for endpoint in endpoints:
        for neighbor in graph[endpoint]:
            edge_key = get_edge_key(endpoint, neighbor)
            if edge_key not in visited_edges:
                path = trace_path(endpoint, graph, visited_edges, endpoints, junctions)
                if len(path) >= 2:
                    polylines.append(path)
    
    # Then, trace paths starting from junctions (for branches between junctions)
    for junction in junctions:
        for neighbor in graph[junction]:
            edge_key = get_edge_key(junction, neighbor)
            if edge_key not in visited_edges:
                path = trace_path(junction, graph, visited_edges, endpoints, junctions)
                if len(path) >= 2:
                    polylines.append(path)
    
    # Finally, handle any remaining edges (isolated loops)
    for point in graph:
        for neighbor in graph[point]:
            edge_key = get_edge_key(point, neighbor)
            if edge_key not in visited_edges:
                # Start tracing from this point
                path = trace_path(point, graph, visited_edges, endpoints, junctions)
                if len(path) >= 2:
                    polylines.append(path)
    
    return polylines


def polyline_to_path_d(points: List[Point]) -> str:
    """Convert a list of points to an SVG path 'd' attribute."""
    if not points:
        return ""
    
    parts = [f"M {points[0][0]},{points[0][1]}"]
    for point in points[1:]:
        parts.append(f"L {point[0]},{point[1]}")
    
    # Check if it's a closed path
    if len(points) >= 3 and points[0] == points[-1]:
        parts[-1] = "Z"
    
    return " ".join(parts)


def simplify_svg(input_file: str, output_file: str) -> None:
    """
    Main function to simplify an SVG file by converting line segments to continuous paths.
    
    Args:
        input_file: Path to input SVG file
        output_file: Path to output SVG file
    """
    print(f"Reading input file: {input_file}")
    
    try:
        # Register SVG namespace to preserve it in output
        ET.register_namespace('', SVG_NS)
        ET.register_namespace('xlink', 'http://www.w3.org/1999/xlink')
        
        tree = ET.parse(input_file)
        root = tree.getroot()
    except FileNotFoundError:
        print(f"Error: Cannot find file '{input_file}'")
        return
    except ET.ParseError as e:
        print(f"Error: Invalid SVG/XML structure: {e}")
        return
    
    # Extract all line segments
    print("Extracting line segments from SVG...")
    segments = extract_segments_from_svg(root)
    original_segment_count = len(segments)
    print(f"Found {original_segment_count} line segments")
    
    if original_segment_count == 0:
        print("No line segments found. Nothing to simplify.")
        return
    
    # Build graph from segments
    print("Building graph from line segments...")
    graph = build_graph(segments)
    print(f"Graph has {len(graph)} unique points")
    
    # Find endpoints and junctions for statistics
    endpoints, junctions = find_endpoints_and_junctions(graph)
    print(f"Found {len(endpoints)} endpoints (degree 1)")
    print(f"Found {len(junctions)} junctions (degree 3+)")
    
    # Extract polylines
    print("Extracting continuous polylines...")
    polylines = extract_polylines(graph)
    print(f"Extracted {len(polylines)} continuous polylines")
    
    # Get SVG attributes from original
    svg_attribs = dict(root.attrib)
    
    # Create new SVG document
    print("Creating output SVG file...")
    new_root = ET.Element('svg', svg_attribs)
    new_root.set('xmlns', SVG_NS)
    
    # Add title if present in original
    for title in root.iter():
        tag = title.tag.split('}')[-1] if '}' in title.tag else title.tag
        if tag == 'title':
            new_title = ET.SubElement(new_root, 'title')
            new_title.text = title.text
            break
    
    # Add polylines as path elements
    for polyline_points in polylines:
        path_d = polyline_to_path_d(polyline_points)
        path_elem = ET.SubElement(new_root, 'path')
        path_elem.set('d', path_d)
        path_elem.set('stroke', 'black')
        path_elem.set('fill', 'none')
        path_elem.set('stroke-width', '0.5')
    
    # Write output file
    try:
        new_tree = ET.ElementTree(new_root)
        
        # Write with XML declaration
        with open(output_file, 'w', encoding='UTF-8') as f:
            f.write('<?xml version="1.0" encoding="UTF-8"?>\n')
            new_tree.write(f, encoding='unicode')
        
        print(f"Saved output file: {output_file}")
    except IOError as e:
        print(f"Error: Cannot write file '{output_file}': {e}")
        return
    
    # Print statistics
    print("\n" + "=" * 50)
    print("STATISTICS")
    print("=" * 50)
    print(f"Original line segments:    {original_segment_count}")
    print(f"Resulting paths:           {len(polylines)}")
    if polylines:
        print(f"Reduction ratio:           {original_segment_count / len(polylines):.2f}x")
    print("=" * 50)


if __name__ == "__main__":
    input_file = "layout_2d.svg"
    output_file = "simplified.svg"
    
    simplify_svg(input_file, output_file)
