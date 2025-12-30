"""
Draw Simplifier - Simplify DXF and SVG files.

This package provides tools to simplify DXF and SVG files by converting
individual line segments into continuous polylines/paths.
"""

from .simplify_dxf import simplify_dxf, simplify_dxf_bytes
from .simplify_svg import simplify_svg, simplify_svg_bytes
from .converter import dxf_to_svg, svg_to_dxf

__version__ = "0.1.0"
__all__ = [
    "simplify_dxf",
    "simplify_dxf_bytes",
    "simplify_svg",
    "simplify_svg_bytes",
    "dxf_to_svg",
    "svg_to_dxf",
]
