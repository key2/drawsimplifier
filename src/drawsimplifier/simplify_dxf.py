"""
DXF Line Simplifier - Converts LINE entities to continuous LWPOLYLINE entities.

This module reads a DXF file containing many LINE entities that form continuous paths,
builds a graph representation, and outputs a simplified DXF with LWPOLYLINE entities.
"""

import ezdxf
from collections import defaultdict
from typing import Dict, List, Set, Tuple, BinaryIO
from io import BytesIO, StringIO

# Type aliases
Point = Tuple[float, float]
Edge = Tuple[Point, Point]


def round_point(x: float, y: float, decimals: int = 6) -> Point:
    """Round point coordinates to handle floating-point precision issues."""
    return (round(x, decimals), round(y, decimals))


def build_graph(lines: List) -> Dict[Point, List[Point]]:
    """
    Build an adjacency graph from LINE entities.
    
    Each point is a node, and each line segment creates bidirectional edges.
    """
    graph: Dict[Point, List[Point]] = defaultdict(list)
    
    for line in lines:
        start = round_point(line.dxf.start.x, line.dxf.start.y)
        end = round_point(line.dxf.end.x, line.dxf.end.y)
        
        # Skip zero-length lines
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


def simplify_dxf_bytes(input_bytes: bytes) -> Tuple[bytes, dict]:
    """
    Simplify a DXF file from bytes and return simplified DXF bytes.
    
    Args:
        input_bytes: Input DXF file content as bytes
        
    Returns:
        Tuple of (simplified DXF bytes, statistics dict)
    """
    # Read from bytes (ezdxf expects text stream, so decode bytes first)
    input_stream = StringIO(input_bytes.decode('utf-8', errors='ignore'))
    doc = ezdxf.read(input_stream)
    
    msp = doc.modelspace()
    
    # Collect all LINE entities
    lines = list(msp.query("LINE"))
    original_line_count = len(lines)
    
    if original_line_count == 0:
        raise ValueError("No LINE entities found. Nothing to simplify.")
    
    # Build graph from lines
    graph = build_graph(lines)
    
    # Find endpoints and junctions for statistics
    endpoints, junctions = find_endpoints_and_junctions(graph)
    
    # Extract polylines
    polylines = extract_polylines(graph)
    
    # Create new DXF document (use R2000 or later for LWPOLYLINE support)
    dxf_version = doc.dxfversion
    if dxf_version < "AC1015":  # AC1015 = R2000
        dxf_version = "R2000"
    new_doc = ezdxf.new(dxfversion=dxf_version)
    new_msp = new_doc.modelspace()
    
    # Add polylines to new document
    for polyline_points in polylines:
        new_msp.add_lwpolyline(polyline_points)
    
    # Copy any non-LINE entities from original (optional - preserves other geometry)
    other_entities = 0
    for entity in msp:
        if entity.dxftype() != "LINE":
            try:
                new_msp.add_entity(entity.copy())
                other_entities += 1
            except Exception:
                # Some entities may not be copyable
                pass
    
    # Save to bytes (ezdxf writes strings, so we use StringIO and encode)
    output_stream = StringIO()
    new_doc.write(output_stream)
    output_bytes = output_stream.getvalue().encode('utf-8')
    
    # Statistics
    stats = {
        "original_line_count": original_line_count,
        "unique_points": len(graph),
        "endpoints": len(endpoints),
        "junctions": len(junctions),
        "polyline_count": len(polylines),
        "other_entities": other_entities,
        "reduction_ratio": original_line_count / len(polylines) if polylines else 0
    }
    
    return output_bytes, stats


def simplify_dxf(input_file: str, output_file: str) -> dict:
    """
    Main function to simplify a DXF file by converting LINE entities to LWPOLYLINE.
    
    Args:
        input_file: Path to input DXF file
        output_file: Path to output DXF file
        
    Returns:
        Statistics dictionary
    """
    with open(input_file, 'rb') as f:
        input_bytes = f.read()
    
    output_bytes, stats = simplify_dxf_bytes(input_bytes)
    
    with open(output_file, 'wb') as f:
        f.write(output_bytes)
    
    return stats
