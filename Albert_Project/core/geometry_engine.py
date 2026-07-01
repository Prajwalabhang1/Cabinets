"""
===========================================================================
  core/geometry_engine.py — High-Fidelity 2D CAD Layouts Engine
===========================================================================
  Translates sequenced cabinets, appliances, and openings into detailed
  architectural 2D lines, dimensions, texts, and swing annotations.
===========================================================================
"""
from __future__ import annotations

from typing import List, Dict, Any
from core.engines.floor_plan_generator import FloorPlanGenerator
from core.engines.elevation_generator import ElevationGenerator

class GeometryEngine:
    """
    Builds plan views and detailed elevation views coordinates.
    All dimensions inside this engine use inches.
    """

    def __init__(self):
        pass

    def generate_layout_geometry(
        self,
        walls: list[dict],
        appliances: list[dict],
        ceiling_height: float = 108.0,
        soffit_height: float = 96.0
    ) -> dict:
        """
        Processes wall runs to generate plan and elevation geometries.
        Returns:
        {
          "plan": { "lines": [], "dimensions": [], "blocks": [], "texts": [] },
          "elevation": { "lines": [], "dimensions": [], "blocks": [], "texts": [] },
          "side": { "lines": [], "dimensions": [], "blocks": [], "texts": [] }
        }
        """
        # Call the new modular engines
        plan_geom = FloorPlanGenerator.generate(
            walls=walls,
            start_ox=0.0,
            start_oy=0.0,
            scale_factor=1.0
        )
        
        elev_geom = ElevationGenerator.generate(
            walls=walls,
            start_ox=0.0,
            start_oy=0.0,
            ceiling_height=ceiling_height,
            scale_x=1.0,
            scale_y=1.0
        )
        
        # Phase 2 will implement the SectionGenerator
        side_geom = {"lines": [], "dimensions": [], "blocks": [], "texts": []}

        return {
            "plan": plan_geom,
            "elevation": elev_geom,
            "side": side_geom
        }
