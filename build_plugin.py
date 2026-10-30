from pathlib import Path
import ast
ROOT = Path(__file__).parent
src = (ROOT / 'upstream/softfever_slicer_post_processing_script.py').read_text(encoding='utf-8')
names = {'Arc', 'midpoint', 'getStartPtOnLS', 'create_circle', 'get_farthest_point', 'move_toward_point', 'redistribute_vertices', 'generateMultipleConcentricArcs', 'getArcBoundarys'}
class Clean(ast.NodeTransformer):
    def visit_Expr(self, node):
        call = node.value
        if isinstance(call, ast.Call):
            f = call.func
            if isinstance(f, ast.Name) and f.id in {'input', 'print', 'plot_geometry'}:
                return ast.Pass()
            if isinstance(f, ast.Attribute) and isinstance(f.value, ast.Name) and f.value.id == 'plt':
                return ast.Pass()
        return self.generic_visit(node)
nodes = [Clean().visit(n) for n in ast.parse(src).body if isinstance(n, (ast.ClassDef, ast.FunctionDef)) and n.name in names]
geometry = '\n\n'.join(ast.unparse(n) for n in nodes)
geometry = geometry.replace('if not lsidx.is_integer():', 'if not isinstance(lsidx, (int, np.integer)):')
geometry = geometry.replace('random.choice(pts)', "kwargs['_rng'].choice(pts)")
geometry = geometry.replace('dx /= magnitude', 'if magnitude == 0:\n        return start_point\n    dx /= magnitude')
geometry = geometry.replace('while r <= rMax:', "while r <= rMax:\n        if kwargs.get('_cancelled', lambda: False)():\n            raise Cancelled('Cancelled.')")
geometry = geometry.replace('arcs.append(arcObj)', 'if arc.is_empty or arc.area < 1e-10:\n            break\n        arcs.append(arcObj)')
header = '''# /// script
# requires-python = ">=3.12"
# dependencies = ["numpy>=1.26,<3", "shapely>=2.0,<3"]
#
# [tool.orcaslicer.plugin]
# name = "Arc Overhang"
# description = "Concentric arc overhangs for OrcaSlicer 2.5. GPL-3.0; based on Kelsch, Nicolai Wachenschwan and Steven McCulloch."
# author = "Kelsch / Nicolai Wachenschwan / Steven McCulloch; Orca 2.5 adaptation"
# version = "0.2.4"
# ///
"""Arc Overhang for OrcaSlicer 2.5. Modified 2026-10-24.
GPL-3.0, no warranty. See LICENSE in the source distribution.
Geometry derived from Kelsch/arc-overhang-orcaslicer-integration,
commit 0693ef29a0eb3e96fdc336841cd714e071f3ed9a.
Original idea: Steven McCulloch; slicer integration: Nicolai Wachenschwan;
Orca integration: Kelsch. New parser, configuration and plugin adapter.
"""
from __future__ import annotations
import json
import math
import os
import random
import re
import tempfile
import warnings
from dataclasses import dataclass, field, replace
from pathlib import Path
import numpy as np
from shapely import Point, Polygon, LineString, MultiLineString, MultiPolygon, GeometryCollection
from shapely.ops import nearest_points, linemerge, unary_union, polygonize

'''
out = ROOT / 'dist'
out.mkdir(exist_ok=True)
(out / 'arc_overhang.py').write_text(header + geometry + '\n\n' + (ROOT / 'adapter.py.in').read_text(encoding='utf-8'), encoding='utf-8')
print(out / 'arc_overhang.py')
