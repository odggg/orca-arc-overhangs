# /// script
# requires-python = ">=3.12"
# dependencies = ["numpy>=1.26,<3", "shapely>=2.0,<3"]
#
# [tool.orcaslicer.plugin]
# name = "Arc Overhang"
# description = "Concentric arc overhangs for OrcaSlicer 2.5. GPL-3.0; based on Kelsch, Nicolai Wachenschwan and Steven McCulloch."
# author = "Kelsch / Nicolai Wachenschwan / Steven McCulloch; Orca 2.5 adaptation"
# version = "0.2.3"
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

class Arc:

    def __init__(self, center: Point, r: float, kwargs: dict={}) -> None:
        self.center = center
        self.r = r
        self.pointsPerCircle = kwargs.get('PointsPerCircle', 80)
        self.parameters = kwargs

    def setPoly(self, poly: Polygon) -> None:
        self.poly = poly

    def extractArcBoundary(self) -> LineString | list:
        circ = create_circle(self.center, self.r, self.pointsPerCircle)
        trueArc = self.poly.boundary.intersection(circ.boundary.buffer(0.01))
        if trueArc.geom_type == 'MultiLineString':
            merged = linemerge(trueArc)
        elif trueArc.geom_type == 'LineString':
            self.arcline = trueArc
            return trueArc
        else:
            merged = linemerge(MultiLineString([l for l in trueArc.geoms if l.geom_type == 'LineString']))
        if merged.geom_type == 'LineString':
            self.arcline = merged
            return merged
        elif merged.geom_type == 'MultiLineString':
            arcList = []
            for ls in merged.geoms:
                arc = Arc(self.center, self.r, self.parameters)
                arc.arcline = ls
                arcList.append(arc)
            return arcList
        else:
            pass
            raise ValueError('ArcBoundary merging Error')

    def generateConcentricArc(self, startpt: Point, remainingSpace: Polygon | MultiPolygon) -> Polygon:
        circ = create_circle(startpt, self.r, self.pointsPerCircle)
        arc = circ.intersection(remainingSpace)
        self.poly = arc
        return arc

def midpoint(p1: Point, p2: Point):
    return Point((p1.x + p2.x) / 2, (p1.y + p2.y) / 2)

def getStartPtOnLS(ls: LineString, kwargs: dict={}, choseRandom: bool=False) -> Point:
    if ls.geom_type == 'MultiLineString' or ls.geom_type == 'GeometryCollection':
        lengths = []
        for lss in ls.geoms:
            if lss.geom_type == 'LineString':
                lengths.append(lss.length)
            else:
                pass
                lengths.append(0)
        lsidx = np.argmax(lengths)
        if not isinstance(lsidx, (int, np.integer)):
            try:
                lsidx = lsidx[0]
            except:
                pass
                lsidx = 0
        ls = ls.geoms[lsidx]
    if len(ls.coords) < 2:
        warnings.warn('Start LineString with <2 Points invalid')
        pass
        raise ValueError('Start LineString with <2 Points invalid')
    if len(ls.coords) == 2:
        return midpoint(Point(ls.coords[0]), Point(ls.coords[1]))
    scores = []
    curLength = 0
    pts = [Point(p) for p in ls.coords]
    if choseRandom:
        return kwargs['_rng'].choice(pts)
    coords = [np.array(p) for p in ls.coords]
    for idp, p in enumerate(pts):
        if idp == 0 or idp == len(pts) - 1:
            scores.append(0)
            continue
        curLength += p.distance(pts[idp - 1])
        relLength = curLength / ls.length
        lengthscore = 1 - np.abs(relLength - 0.5)
        v1 = coords[idp] - coords[idp - 1]
        v2 = coords[idp + 1] - coords[idp]
        if np.linalg.norm(v1) > 0 and np.linalg.norm(v2) > 0:
            v1 = v1 / np.linalg.norm(v1)
            v2 = v2 / np.linalg.norm(v2)
            anglescore = np.abs(np.sin(np.arccos(np.clip(np.dot(v1, v2), -1.0, 1.0))))
            anglescore *= kwargs.get('CornerImportanceMultiplier', 1)
            scores.append(lengthscore + anglescore)
        else:
            scores.append(lengthscore)
    maxIndex = scores.index(max(scores))
    return pts[maxIndex]

def create_circle(p: Point, radius: float, n: int) -> Polygon:
    x = p.x
    y = p.y
    return Polygon([[radius * np.sin(theta) + x, radius * np.cos(theta) + y] for theta in np.linspace(0, 2 * np.pi - 2 * np.pi / n, int(n))])

def get_farthest_point(arc: Polygon, base_poly: Polygon, remaining_empty_space: Polygon):
    """
    Find the point on a given arc that is farthest away from the base polygon.
    In other words, the point on which the largest circle can be drawn without going outside the base polygon.
    Parameters
    ----------
    arc: Polygon
        The arc in question
    base_poly: Polygon
        The base polygon
    remaining_empty_space: Polygon
        The polygon representing the space left to be filled in the base polygon        
    Returns
    -------
    farthest_point: Point
        The point on the arc that is farthest away from the base polygon
    longest_distance: float
        How far away the polygon is from the farthest point
    point_on_poly: Point
        The point on the base polygon that is closest to the arc
    """
    longest_distance = -1
    farthest_point = Point([0, 0])
    pointFound = False
    if arc.geom_type == 'Polygon':
        arc_coords = arc.exterior.coords
    elif arc.geom_type == 'LineString':
        arc_coords = np.linspace(list(arc.coords)[0], list(arc.coords)[1])
    else:
        pass
        pass
        pass
        pass
        pass
        pass
    for p in list(arc_coords):
        distance = Point(p).distance(base_poly.boundary)
        if distance > longest_distance and remaining_empty_space.buffer(0.01).contains(Point(p)):
            longest_distance = distance
            farthest_point = Point(p)
            pointFound = True
    point_on_poly = nearest_points(base_poly, farthest_point)[0]
    if pointFound:
        return (farthest_point, longest_distance, point_on_poly)
    else:
        return (None, None, None)

def move_toward_point(start_point: Point, target_point: Point, distance: float) -> Point:
    """Moves a point a set distance toward another point"""
    dx = target_point.x - start_point.x
    dy = target_point.y - start_point.y
    magnitude = (dx ** 2 + dy ** 2) ** 0.5
    if magnitude == 0:
        return start_point
    dx /= magnitude
    dy /= magnitude
    return Point(start_point.x + dx * distance, start_point.y + dy * distance)

def redistribute_vertices(geom: LineString | MultiLineString, distance: float) -> LineString | MultiLineString:
    if geom.geom_type == 'LineString':
        num_vert = int(round(geom.length / distance))
        if num_vert == 0:
            num_vert = 1
        return LineString([geom.interpolate(float(n) / num_vert, normalized=True) for n in range(num_vert + 1)])
    elif geom.geom_type == 'MultiLineString':
        parts = [redistribute_vertices(part, distance) for part in geom.geoms]
        return type(geom)([p for p in parts if not p.is_empty])
    else:
        warnings.warn('unhandled geometry %s', (geom.geom_type,))
        return geom

def generateMultipleConcentricArcs(startpt: Point, rMin: float, rMax: float, boundaryLineString: LineString, remainingSpace: Polygon | MultiPolygon, kwargs={}) -> list:
    arcs = []
    r = rMin
    while r <= rMax:
        if kwargs.get('_cancelled', lambda: False)():
            raise Cancelled('Cancelled.')
        arcObj = Arc(startpt, r, kwargs=kwargs)
        arc = arcObj.generateConcentricArc(startpt, remainingSpace)
        if arc.intersects(boundaryLineString) and (not kwargs.get('UseLeastAmountOfCenterPoints', False)):
            break
        if arc.is_empty or arc.area < 1e-10:
            break
        arcs.append(arcObj)
        r += kwargs.get('ArcWidth')
    return arcs

def getArcBoundarys(concentricArcs: list) -> list:
    """Handle arcs composited from multiple parts"""
    boundarys = []
    for arc in concentricArcs:
        arcLine = arc.extractArcBoundary()
        if type(arcLine) == type([]):
            for arc in arcLine:
                boundarys.append(arc.arcline)
        else:
            boundarys.append(arcLine)
    return boundarys

VERSION = "0.2.3"
MARKER = "; ARC_OVERHANG_PLUGIN:"
DEFAULTS = {
    "enabled": True,
    "arc_speed_mm_s": 1.5,
    "minimum_arc_speed_mm_s": 0.5,
    "travel_speed_mm_s": 30.0,
    "arc_spacing_nozzle_ratio": 0.95,
    "wall_overlap_mm": 0.8,
    "arc_center_offset_mm": 2.0,
    "max_radius_mm": 100.0,
    "minimum_area_mm2": 50.0,
    "minimum_overhang_length_mm": 5.0,
    "minimum_coverage_percent": 90.0,
    "flow_multiplier": 1.35,
    "minimum_arc_time_s": 3.0,
    "max_edge_gap_mm": 0.8,
    "points_per_circle": 80,
    "max_centers": 2000,
    "retract_length_mm": 0.8,
    "retract_speed_mm_s": 35.0,
    "z_min_mm": 0.0,
    "z_max_mm": 10000.0,
}
CONFIG_KEYS = ("nozzle_diameter", "filament_diameter", "outer_wall_line_width",
               "line_width", "layer_height", "filament_flow_ratio", "use_volumetric_e")
NUMBER = r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?"
WORD = re.compile(r"([A-Z])\s*(" + NUMBER + r")", re.I)

class UnsupportedGCode(ValueError):
    pass

class Cancelled(RuntimeError):
    pass

def configuration(overrides=None):
    result = dict(DEFAULTS)
    if overrides:
        if not isinstance(overrides, dict):
            raise ValueError("Plugin configuration must be a JSON object.")
        unknown = set(overrides) - set(DEFAULTS)
        if unknown:
            raise ValueError("Unknown settings: " + ", ".join(sorted(unknown)))
        result.update(overrides)
    for key, value in result.items():
        if isinstance(DEFAULTS[key], bool):
            if type(value) is not bool:
                raise ValueError(key + " must be true or false.")
        elif isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
            raise ValueError(key + " must be a finite number.")
        elif value < 0:
            raise ValueError(key + " must not be negative.")
    for key in ("arc_speed_mm_s", "minimum_arc_speed_mm_s", "travel_speed_mm_s",
                "arc_spacing_nozzle_ratio", "max_radius_mm", "flow_multiplier",
                "minimum_arc_time_s", "max_edge_gap_mm", "retract_speed_mm_s"):
        if result[key] <= 0:
            raise ValueError(key + " must be greater than 0.")
    if result["minimum_arc_speed_mm_s"] > result["arc_speed_mm_s"]:
        raise ValueError("Minimum arc speed exceeds maximum arc speed.")
    if not 0.1 <= result["arc_spacing_nozzle_ratio"] <= 1.5:
        raise ValueError("arc_spacing_nozzle_ratio must be between 0.1 and 1.5.")
    if not 50 <= result["minimum_coverage_percent"] <= 100:
        raise ValueError("minimum_coverage_percent must be between 50 and 100.")
    if not 16 <= result["points_per_circle"] <= 80 or int(result["points_per_circle"]) != result["points_per_circle"]:
        raise ValueError("points_per_circle must be an integer from 16 to 80.")
    if not 1 <= result["max_centers"] <= 10000 or int(result["max_centers"]) != result["max_centers"]:
        raise ValueError("max_centers must be an integer from 1 to 10000.")
    if result["z_min_mm"] > result["z_max_mm"]:
        raise ValueError("z_min_mm exceeds z_max_mm.")
    return result

def scalar(value, key):
    if isinstance(value, (list, tuple)):
        if len(value) != 1:
            raise UnsupportedGCode("Multiple values for " + key + ": only single-extruder configurations are supported.")
        value = value[0]
    if isinstance(value, str):
        value = value.strip().strip('[]"')
        if ";" in value or "," in value:
            parts = re.split(r"[;,]", value)
            if len(parts) != 1:
                raise UnsupportedGCode("Multiple values for " + key + ": only single-extruder configurations are supported.")
        if value.endswith("%"):
            return ("percent", float(value[:-1]))
    try:
        value = float(value)
    except (ValueError, TypeError):
        raise UnsupportedGCode("Missing or invalid print setting: " + key)
    if not math.isfinite(value):
        raise UnsupportedGCode("Invalid print setting: " + key)
    return value

def printer_settings(lines, resolved=None):
    raw = {}
    for line in lines:
        match = re.match(r"^;\s*(\w+)\s*=\s*(.*?)\s*$", line)
        if match and match[1] in CONFIG_KEYS:
            raw[match[1]] = match[2]
    raw.update({k: v for k, v in (resolved or {}).items() if v is not None})
    result = {}
    for key in ("nozzle_diameter", "filament_diameter", "layer_height"):
        result[key] = scalar(raw.get(key), key)
        if not isinstance(result[key], float) or result[key] <= 0:
            raise UnsupportedGCode(key + " must be positive.")
    width = scalar(raw.get("outer_wall_line_width", raw.get("line_width", result["nozzle_diameter"])), "outer_wall_line_width")
    if isinstance(width, tuple):
        width = result["layer_height"] * width[1] / 100
    if width == 0:
        width = result["nozzle_diameter"] * 1.125
    result["outer_wall_line_width"] = width
    flow = scalar(raw.get("filament_flow_ratio", 1), "filament_flow_ratio")
    if not isinstance(flow, float) or flow <= 0:
        raise UnsupportedGCode("Invalid filament_flow_ratio.")
    result["filament_flow_ratio"] = flow
    volumetric = raw.get("use_volumetric_e", False)
    if str(volumetric).strip().lower() not in ("0", "false", "none", ""):
        raise UnsupportedGCode("Volumetric extrusion is not supported.")
    return result

@dataclass
class State:
    x: float | None = None
    y: float | None = None
    z: float | None = None
    e: float = 0.0
    feed: float = 1800.0
    relative_e: bool = False
    absolute_xyz: bool = True
    retracted: float = 0.0

@dataclass
class Move:
    index: int
    before: State
    after: State
    delta_e: float
    command: str
    words: dict = field(default_factory=dict)

@dataclass
class Feature:
    layer: int
    role: str
    start: int
    end: int = 0
    moves: list = field(default_factory=list)

def command(line):
    body = line.split(";", 1)[0].strip().upper()
    if not body:
        return "", {}
    match = re.match(r"^([GMT]\d+(?:\.\d+)?|T\d+)\b", body)
    if not match:
        return body.split()[0], {}
    return {"G00":"G0","G01":"G1","G02":"G2","G03":"G3"}.get(match[1], match[1]), {k: float(v) for k, v in WORD.findall(body[match.end():])}

def parse(lines, cancelled=lambda: False):
    state = State()
    features = []
    feature = None
    layer = -1
    physical_tools = set()
    for i, line in enumerate(lines):
        if i % 2048 == 0 and cancelled():
            raise Cancelled("Cancelled.")
        if re.match(r"^;\s*(?:LAYER_CHANGE|CHANGE_LAYER)\s*$", line):
            if feature:
                feature.end = i
                features.append(feature)
                feature = None
            layer += 1
        role = re.match(r"^;\s*(?:TYPE|FEATURE)\s*:\s*(.*?)\s*$", line)
        if role:
            if feature:
                feature.end = i
                features.append(feature)
            feature = Feature(layer, role[1].lower(), i)
        cmd, words = command(line)
        if cmd == "G20":
            raise UnsupportedGCode("G20/inch units are not supported.")
        if cmd in ("G90", "G91"):
            state.absolute_xyz = cmd == "G90"
        elif cmd in ("M82", "M83"):
            state.relative_e = cmd == "M83"
        elif cmd == "G92":
            for key in ("X", "Y", "Z", "E"):
                if key in words:
                    setattr(state, key.lower(), words[key])
        elif cmd in ("G0", "G00", "G1", "G01", "G2", "G3"):
            before = replace(state)
            if feature and layer >= 0 and "E" in words and not state.relative_e:
                raise UnsupportedGCode("Enable relative extrusion (M83).")
            for key in ("X", "Y", "Z"):
                if key in words:
                    previous = getattr(state, key.lower())
                    setattr(state, key.lower(), words[key] if state.absolute_xyz else (previous or 0) + words[key])
            if "F" in words:
                state.feed = words["F"]
            delta = 0.0
            if "E" in words:
                delta = words["E"] if state.relative_e else words["E"] - state.e
                state.e = state.e + words["E"] if state.relative_e else words["E"]
                if delta < 0:
                    state.retracted -= delta
                elif delta > 0:
                    # Positive E repays a previous retraction even during XY motion.
                    # Rounded wipe segments can differ from their matching prime by
                    # fractions of a micron of filament; do not accumulate that noise.
                    state.retracted = max(0, state.retracted - delta)
                    if state.retracted < 0.0005:
                        state.retracted = 0.0
            if feature:
                feature.moves.append(Move(i, before, replace(state), delta, cmd, words))
        elif cmd in ("G10", "G11", "G60", "G61", "G90.1", "G18", "G19", "G68", "G69"):
            raise UnsupportedGCode("Unsupported state command: " + cmd)
        elif cmd.startswith("T") and cmd[1:].isdigit():
            tool = int(cmd[1:])
            # Orca can number the sole active extruder with a non-zero index.
            # Bambu's T0/T255/T1000 are virtual markers, not physical tools.
            if tool not in (0, 255, 1000):
                physical_tools.add(tool)
                if len(physical_tools) > 1:
                    raise UnsupportedGCode("Tool changes and multiple materials are not supported.")
        elif cmd == "M200" and words.get("D", 0) > 0:
            raise UnsupportedGCode("M200/volumetric extrusion is not supported.")
    if feature:
        feature.end = len(lines)
        features.append(feature)
    return features

def arc_polyline(move, tolerance=0.01):
    a, b, words = move.before, move.after, move.words
    clockwise = move.command == "G2"
    if "I" in words or "J" in words:
        cx, cy = a.x + words.get("I", 0), a.y + words.get("J", 0)
    elif "R" in words:
        radius = abs(words["R"])
        dx, dy = b.x - a.x, b.y - a.y
        chord = math.hypot(dx, dy)
        if chord < 1e-9 or chord > 2 * radius + 0.02:
            raise UnsupportedGCode("Invalid R arc.")
        height = math.sqrt(max(0, radius * radius - (chord / 2) ** 2))
        centers = [((a.x+b.x)/2 - sign*dy/chord*height,
                    (a.y+b.y)/2 + sign*dx/chord*height) for sign in (1,-1)]
        def size(center):
            x,y=center
            start=math.atan2(a.y-y,a.x-x)
            end=math.atan2(b.y-y,b.x-x)
            return ((start-end) if clockwise else (end-start)) % (2*math.pi)
        cx,cy = min(centers,key=size) if words["R"] >= 0 else max(centers,key=size)
    else:
        raise UnsupportedGCode("G2/G3 requires I/J or R.")
    radius = math.hypot(a.x-cx,a.y-cy)
    if radius < 1e-9 or abs(math.hypot(b.x-cx,b.y-cy)-radius) > max(0.03,radius*0.005):
        raise UnsupportedGCode("Inconsistent G2/G3 radius.")
    start=math.atan2(a.y-cy,a.x-cx)
    end=math.atan2(b.y-cy,b.x-cx)
    sweep = ((start-end) if clockwise else (end-start)) % (2*math.pi)
    if math.hypot(b.x-a.x,b.y-a.y) < 1e-6:
        sweep = 2*math.pi
    max_angle = 2*math.acos(max(-1,min(1,1-tolerance/radius)))
    count = max(2,math.ceil(sweep/max(max_angle,1e-8)))
    if count > 16384:
        raise UnsupportedGCode("G2/G3 arc is too large for geometry analysis.")
    direction = -1 if clockwise else 1
    points=[(a.x,a.y)]
    points.extend((cx+radius*math.cos(start+direction*sweep*i/count),
                   cy+radius*math.sin(start+direction*sweep*i/count)) for i in range(1,count))
    points.append((b.x,b.y))
    return LineString(points)

def segment(move):
    a, b = move.before, move.after
    if move.delta_e <= 1e-9 or None in (a.x, a.y, b.x, b.y):
        return None
    if not a.absolute_xyz or not a.relative_e:
        raise UnsupportedGCode("Requires G90 and relative extrusion (M83).")
    if move.command in ("G2", "G3"):
        return arc_polyline(move)
    if math.hypot(b.x - a.x, b.y - a.y) < 1e-8:
        return None
    return LineString([(a.x, a.y), (b.x, b.y)])

def layer_shape(features, width):
    # Merge walls across feature boundaries: Orca splits overhang wall from outer wall.
    segments = []
    for feature in features:
        if feature.role not in ("outer wall", "external perimeter", "overhang wall", "overhang perimeter"):
            continue
        for move in feature.moves:
            ls = segment(move)
            if ls is not None:
                segments.append(ls)
    if not segments:
        return GeometryCollection()
    network = unary_union(segments)
    merged = network if network.geom_type == "LineString" else linemerge(network)
    parts = [merged] if merged.geom_type == "LineString" else list(merged.geoms)
    shape = GeometryCollection()
    ring_count = 0
    for line in parts:
        coords = list(line.coords)
        if len(coords) > 3 and math.dist(coords[0], coords[-1]) <= width:
            ring = Polygon(coords).buffer(0)
            shape = shape.symmetric_difference(ring)
            ring_count += 1
    # Scarf seams retrace a contour with overlapping tails. Exact line merging
    # then sees open/branched paths. A thin stroke closes only sub-nozzle gaps;
    # its holes identify complete contours without inventing long closing chords.
    radius = min(width * 0.1, 0.03)
    stroke = network.buffer(radius)
    loops = [part for part in polygons(stroke) if any(Polygon(r).area > width*width for r in part.interiors)]
    if loops and len(loops) != ring_count:
        shape = GeometryCollection()
        for part in loops:
            footprint = Polygon(part.exterior).buffer(-radius)
            shape = shape.symmetric_difference(footprint)
    return shape

def polygons(geom):
    if geom.geom_type == "Polygon":
        return [geom]
    if hasattr(geom, "geoms"):
        return [p for g in geom.geoms for p in polygons(g)]
    return []

def parameters(config, printer, cancelled):
    return {
        "ArcWidth": printer["nozzle_diameter"] * config["arc_spacing_nozzle_ratio"],
        "ArcCenterOffset": config["arc_center_offset_mm"],
        "PointsPerCircle": int(config["points_per_circle"]),
        "CornerImportanceMultiplier": 0.2,
        "UseLeastAmountOfCenterPoints": False,
        "_rng": random.Random(0),
        "_cancelled": cancelled,
    }

def fill_polygon(poly, support, cfg, printer, cancelled):
    params = parameters(cfg, printer, cancelled)
    overlap = support.intersection(poly)
    if overlap.is_empty or overlap.area < 1e-5:
        return None
    startline = overlap.boundary.intersection(poly.boundary.buffer(0.01))
    if startline.is_empty:
        startline = overlap.boundary
    boundary = poly.boundary.difference(overlap.boundary.buffer(0.01))
    candidates = [getStartPtOnLS(startline, params)]
    ls_parts = [startline] if startline.geom_type == "LineString" else [g for g in startline.geoms if g.geom_type == "LineString"]
    candidates.extend(ls.interpolate(f, normalized=True) for ls in ls_parts for f in (0.25, 0.5, 0.75))
    remaining = poly
    initial = []
    for pt in candidates:
        if cancelled():
            raise Cancelled("Cancelled.")
        initial = generateMultipleConcentricArcs(pt, printer["nozzle_diameter"], cfg["max_radius_mm"], boundary, remaining, params)
        if len(initial) >= 2:
            break
    if len(initial) < 2:
        return None
    lines = getArcBoundarys(initial)
    frontier = [initial[-1]]
    for arc in initial:
        remaining = remaining.difference(arc.poly.buffer(0.01))
    index = 0
    iterations = 0
    while index < len(frontier):
        if cancelled():
            raise Cancelled("Cancelled.")
        if iterations >= cfg["max_centers"]:
            break
        cur = frontier[index]
        choices = []
        for piece in polygons(cur.poly):
            pt, dist, _ = get_farthest_point(piece, poly, remaining)
            if pt is not None:
                choices.append((dist, pt))
        if not choices:
            index += 1
            continue
        dist, pt = max(choices, key=lambda v: v[0])
        if dist < cfg["max_edge_gap_mm"]:
            index += 1
            continue
        start = move_toward_point(pt, cur.center, cfg["arc_center_offset_mm"])
        arcs = generateMultipleConcentricArcs(start, cfg["arc_center_offset_mm"] + params["ArcWidth"] / 1.5,
                                              cfg["max_radius_mm"], poly.boundary, remaining, params)
        iterations += 1
        if not arcs:
            index += 1
            continue
        lines.extend(getArcBoundarys(arcs))
        before = remaining.area
        for arc in arcs:
            remaining = remaining.difference(arc.poly.buffer(0.01))
        if before - remaining.area <= 1e-7:
            index += 1
        else:
            frontier.append(arcs[-1])
    coverage = 100 * (1 - remaining.area / poly.area)
    if coverage + 1e-6 < cfg["minimum_coverage_percent"]:
        return None
    return [ls for ls in lines if not ls.is_empty and ls.length > 1e-5], coverage

def emit_arcs(arcs, before, after, cfg, printer):
    if before.retracted > 1e-5 or after.retracted > 1e-5:
        raise UnsupportedGCode(
            f"Bridge region starts or ends with unrecovered retraction "
            f"(start {before.retracted:.5f} mm, end {after.retracted:.5f} mm). "
            "The region will not be modified.")
    e_per_mm = (printer["nozzle_diameter"] / printer["filament_diameter"]) ** 2 * cfg["flow_multiplier"] * printer["filament_flow_ratio"]
    travel = cfg["travel_speed_mm_s"] * 60
    retract = cfg["retract_length_mm"]
    retract_feed = cfg["retract_speed_mm_s"] * 60
    out = [MARKER + "BEGIN\n", ";TYPE:Bridge\n"]
    for i, arc in enumerate(arcs):
        coords = list(arc.coords)
        if len(coords) < 2:
            continue
        speed = max(cfg["minimum_arc_speed_mm_s"], min(cfg["arc_speed_mm_s"], arc.length / cfg["minimum_arc_time_s"])) * 60
        if retract:
            out.append(f"G1 E{-retract:.5f} F{retract_feed:.1f}\n")
        x, y = coords[0]
        out.append(f"G1 X{x:.5f} Y{y:.5f} F{travel:.1f}\n")
        if retract:
            out.append(f"G1 E{retract:.5f} F{retract_feed:.1f}\n")
        out.append(f"; Arc {i + 1}\nG1 F{speed:.2f}\n")
        last = coords[0]
        for pt in coords[1:]:
            distance = math.dist(last, pt)
            if distance > 1e-8:
                out.append(f"G1 X{pt[0]:.5f} Y{pt[1]:.5f} E{distance * e_per_mm:.7f}\n")
            last = pt
    if retract:
        out.append(f"G1 E{-retract:.5f} F{retract_feed:.1f}\n")
    out.append(f"G1 X{after.x:.5f} Y{after.y:.5f} F{travel:.1f}\n")
    if retract:
        out.append(f"G1 E{retract:.5f} F{retract_feed:.1f}\n")
    out.append(f"G92 E{after.e:.7f}\nG1 F{after.feed:.2f}\n")
    out.append(MARKER + "END\n")
    return out

def process_text(text, overrides=None, resolved=None, cancelled=lambda: False):
    cfg = configuration(overrides)
    report = {"replaced_features": 0, "generated_arcs": 0, "skipped_features": 0, "minimum_coverage_percent": None, "bridge_features": 0, "skip_reasons": {}}
    if not cfg["enabled"] or MARKER in text:
        return text, report
    lines = text.splitlines(keepends=True)
    features = parse(lines, cancelled)
    bridges = [f for f in features if f.role in ("bridge", "bridge infill", "internal bridge")]
    report["bridge_features"] = len(bridges)
    def skipped(reason):
        report["skipped_features"] += 1
        report["skip_reasons"][reason] = report["skip_reasons"].get(reason, 0) + 1
    if not bridges:
        return text, report
    printer = printer_settings(lines, resolved)
    width = printer["outer_wall_line_width"]
    by_layer = {}
    for feature in features:
        by_layer.setdefault(feature.layer, []).append(feature)
    shapes = {}
    replacements = []
    for feature in bridges:
        if cancelled():
            raise Cancelled("Cancelled.")
        moves = [m for m in feature.moves if segment(m) is not None]
        if not moves:
            continue
        first, last = moves[0], moves[-1]
        z = first.after.z
        if feature.layer < 1 or z is None or not cfg["z_min_mm"] <= z <= cfg["z_max_mm"]:
            continue
        if any(m.before.z != z or m.after.z != z for m in moves):
            raise UnsupportedGCode("Non-planar bridges are not supported.")
        if any(command(lines[i])[0] not in ("", "G0", "G1", "G2", "G3", "M73") for i in range(first.index, last.index + 1)):
            skipped("State command inside bridge region")
            continue
        for layer in (feature.layer - 1, feature.layer):
            if layer not in shapes:
                shapes[layer] = layer_shape(by_layer.get(layer, []), width)
        support, current = shapes[feature.layer - 1], shapes[feature.layer]
        if support.is_empty or current.is_empty:
            skipped("No closed contour")
            continue
        # Only real extrusion segments form the region; travel moves cannot join islands.
        region = unary_union([segment(m).buffer(width * 0.6) for m in moves]).buffer(cfg["wall_overlap_mm"]).intersection(current)
        pieces = polygons(region)
        arcs = []
        coverages = []
        valid = bool(pieces)
        for poly in pieces:
            unsupported = poly.difference(support.buffer(width * 0.05))
            geometric_overhang = unsupported.area >= cfg["minimum_area_mm2"] and unsupported.length >= cfg["minimum_overhang_length_mm"]
            # A nearby Orca overhang label is not proof of a real overhang.
            # In particular, keep Bridge paths that are supported by the
            # previous layer's footprint unchanged.
            if poly.area < cfg["minimum_area_mm2"] or not geometric_overhang:
                valid = False
                break
            generated = fill_polygon(poly, support, cfg, printer, cancelled)
            if generated is None:
                valid = False
                break
            part, coverage = generated
            arcs.extend(part)
            coverages.append(coverage)
        if not valid or not arcs:
            skipped("Insufficient area, anchoring or coverage")
            continue
        # Replacement is all-or-nothing for this feature, never all bridges in a layer.
        replacement = emit_arcs(arcs, first.before, last.after, cfg, printer)
        # Progress messages do not change tool state and must not disable a bridge.
        replacement.extend(lines[i] for i in range(first.index,last.index+1) if command(lines[i])[0] == "M73")
        replacements.append((first.index, last.index + 1, replacement))
        report["replaced_features"] += 1
        report["generated_arcs"] += len(arcs)
        previous = report["minimum_coverage_percent"]
        report["minimum_coverage_percent"] = min(coverages + ([previous] if previous is not None else []))
    if not replacements:
        return text, report
    for start, end, replacement in reversed(replacements):
        lines[start:end] = replacement
    return MARKER + VERSION + "\n" + "".join(lines), report

def process_file(path, overrides=None, resolved=None, cancelled=lambda: False):
    target = Path(path)
    original = target.read_bytes()
    if original[:2] == b"PK" or b"\0" in original[:1024]:
        raise UnsupportedGCode("Expected uncompressed text G-code, not a 3MF/BGCode file.")
    # utf-8-sig lazily imports a codec under Program Files and triggers repeated
    # audited pycache writes in Orca's embedded Python. UTF-8 itself is built in.
    text = (original[3:] if original.startswith(b"\xef\xbb\xbf") else original).decode("utf-8")
    output, report = process_text(text, overrides, resolved, cancelled)
    if output == text:
        return report
    if cancelled():
        raise Cancelled("Cancelled.")
    data = output.encode("utf-8")
    temp_path = None
    try:
        with tempfile.NamedTemporaryFile(mode="wb", prefix=".arc-overhang-", suffix=".tmp", dir=target.parent, delete=False) as stream:
            temp_path = Path(stream.name)
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        if target.read_bytes() != original:
            raise RuntimeError("G-code was changed during processing.")
        if cancelled():
            raise Cancelled("Cancelled.")
        os.replace(temp_path, target)
    finally:
        if temp_path is not None and temp_path.exists():
            temp_path.unlink()
    return report

def config_page(as_tab=False):
    fields = [
        ("arc_speed_mm_s", "Arc speed", "mm/s"),
        ("minimum_arc_speed_mm_s", "Minimum arc speed", "mm/s"),
        ("arc_spacing_nozzle_ratio", "Arc spacing / nozzle diameter", "Factor"),
        ("wall_overlap_mm", "Wall anchoring", "mm"),
        ("arc_center_offset_mm", "Arc center offset", "mm"),
        ("max_radius_mm", "Maximum radius", "mm"),
        ("minimum_area_mm2", "Minimum area", "mm2"),
        ("minimum_overhang_length_mm", "Minimum overhang length", "mm"),
        ("flow_multiplier", "Arc flow", "Factor"),
        ("minimum_arc_time_s", "Minimum time per arc", "s"),
        ("max_edge_gap_mm", "Maximum edge gap", "mm"),
        ("minimum_coverage_percent", "Required area coverage", "%"),
        ("travel_speed_mm_s", "Travel speed", "mm/s"),
        ("retract_length_mm", "Retraction", "mm"),
        ("retract_speed_mm_s", "Retraction speed", "mm/s"),
        ("points_per_circle", "Points per circle", "16-80"),
        ("max_centers", "Maximum number of centers", "Count"),
        ("z_min_mm", "Minimum Z", "mm"),
        ("z_max_mm", "Maximum Z", "mm"),
    ]
    rows = "".join(f'<label>{label}<span><input id="{key}" name="{key}" type="number" step="any" min="0" required> {unit}</span></label>' for key, label, unit in fields)
    page = r"""<!doctype html><html lang="en"><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Arc Overhang</title>
<style>
:root{color-scheme:light dark;font:14px system-ui,sans-serif}body{max-width:780px;margin:24px auto;padding:0 20px}
h1{font-size:26px;margin-bottom:8px}p{line-height:1.5;color:light-dark(#555,#aaa)}
label{display:flex;justify-content:space-between;align-items:center;gap:12px;padding:10px 0;border-bottom:1px solid #8884}
input[type=number]{width:100px;padding:7px;border:1px solid #8886;border-radius:5px;font:inherit}
button{padding:10px 17px;border:0;border-radius:5px;background:#147c60;color:white;cursor:pointer;font:inherit;margin-top:18px}
#status{margin-left:12px}summary{cursor:pointer;margin-top:20px;font-weight:600}.notice{padding:12px;background:#8881;border-radius:6px}
small{display:block;margin:20px 0;color:light-dark(#555,#aaa)}
</style><h1>Arc Overhang</h1>
<p>Concentric arc toolpaths for flat overhangs. Applied during G-code export.</p>
<p id="last-report" role="status"></p><p class="notice">Arc spacing and wall anchoring are independent. Spacing is a factor of nozzle diameter: 0.5 with a 0.4 mm nozzle gives 0.2 mm spacing.</p>
<div id="settings"><label>Enable Arc Overhang<input id="enabled" type="checkbox"></label>
__ROWS__
<button id="save" type="button">Save settings</button><button id="refresh" type="button">Refresh</button><span id="status" role="status"></span>
</div><small>Version 0.2.3  -  GPL-3.0  -  No warranty. Algorithm: Steven McCulloch, Nicolai Wachenschwan and Kelsch. Orca 2.5 adaptation dated 2026-10-24.</small>
<script>
const defaults = __DEFAULTS__;
const fields = Object.keys(defaults);
const status = document.getElementById('status');
async function initialize(){
  try {
    let saved = await settingsBridge.getConfig();
    if(typeof saved === 'string') saved = JSON.parse(saved);
    const values = {...defaults,...(saved||{})};
    for(const key of fields){
      const el=document.getElementById(key);
      if(typeof defaults[key]==='boolean') el.checked=values[key]; else el.value=values[key];
    }
  }catch(error){status.textContent='Could not load settings: '+error.message;}
}
document.getElementById('save').onclick=async()=>{
  const values={};
  for(const key of fields){
    const el=document.getElementById(key);
    values[key]=typeof defaults[key]==='boolean'?el.checked:Number(el.value);
    if(typeof values[key]==='number'&&!Number.isFinite(values[key])){status.textContent='Please enter valid numbers.';return;}
  }
  if(values.minimum_arc_speed_mm_s>values.arc_speed_mm_s){status.textContent='Minimum speed must not exceed maximum arc speed.';return;}
  if(values.z_min_mm>values.z_max_mm){status.textContent='Invalid Z range.';return;}
  try{
    const ok=await settingsBridge.saveConfig(values);
    status.textContent=ok===false?'Save failed.':
      (ok && ok.preset_override_active ? 'Global defaults saved. The active preset overrides some values; edit them in Plugin Configuration.' : 'Saved.');
  }catch(error){status.textContent='Save failed: '+error.message;}
};
document.getElementById('refresh').onclick=initialize;
document.addEventListener('visibilitychange',()=>{if(!document.hidden) initialize();});
initialize();
</script></html>"""
    bridge = r"""
let saving = null;
const settingsBridge = {
  getConfig:()=>window.orca.getConfig(),
  saveConfig:values=>{
    const context=window.orca.getContext ? window.orca.getContext() : {};
    if(context.readOnly) return Promise.reject(new Error('This preset is read-only.'));
    if(saving) return Promise.reject(new Error('A save is already in progress.'));
    return new Promise((resolve,reject)=>{
      if(typeof window.orca.onConfig!=='function'){
        reject(new Error('Orca save acknowledgement is unavailable. Please update Orca 2.5.'));
        return;
      }
      const timer=setTimeout(()=>{saving=null;reject(new Error('No save acknowledgement from Orca. The preset may be unchanged or the host encountered an error.'));},8000);
      saving={values,resolve,reject,timer};
      window.orca.saveConfig(values);
    });
  }
};
if(typeof window.orca.onConfig==='function') window.orca.onConfig(config=>{
  if(!saving) return;
  const actual=typeof config==='string'?JSON.parse(config):config;
  if(Object.keys(saving.values).every(key=>actual[key]===saving.values[key])){
    const pending=saving;saving=null;clearTimeout(pending.timer);pending.resolve(true);
  }
});
"""

    if as_tab:
        bridge = r"""
const pending = new Map();
let requestNumber = 0;
window.orca.onMessage(message=>{
  const request=pending.get(message.request_id);
  if(!request) return;
  clearTimeout(request.timer);
  pending.delete(message.request_id);
  if(message.ok) request.resolve(message); else request.reject(new Error(message.error||'Plugin request failed.'));
});
function requestSettings(action,config){
  return new Promise((resolve,reject)=>{
    const request_id=++requestNumber;
    const timer=setTimeout(()=>{pending.delete(request_id);reject(new Error('No response. Enable the plugin and reload it.'));},15000);
    pending.set(request_id,{resolve,reject,timer});
    try{window.orca.postMessage({action,request_id,config});}
    catch(error){clearTimeout(timer);pending.delete(request_id);reject(error);}
  });
}
const settingsBridge = {
  getConfig:async()=>{
    const response=await requestSettings('read');
    const report=response.last_report;
    document.getElementById('last-report').textContent=report ?
      (report.error ? 'Last export: '+report.error :
       'Last export: '+report.replaced_features+' bridges replaced, '+report.generated_arcs+' arc toolpaths, '+report.skipped_features+' skipped. '+JSON.stringify(report.skip_reasons||{})) :
      'No export with this plugin version yet.';
    return response.config;
  },
  saveConfig:config=>requestSettings('save',config)
};
"""
        page = page.replace('<div id="settings">', '<p>This page shows settings for the active preset. Saving updates global defaults; existing preset overrides still take precedence.</p><div id="settings">')
    return page.replace("__ROWS__", rows).replace("__DEFAULTS__", json.dumps(DEFAULTS)).replace("<script>", "<script>" + bridge, 1)


# The engine can be tested from a normal Python interpreter; Orca registers it here.
try:
    import orca
except ModuleNotFoundError as error:
    if error.name != "orca":
        raise
    orca = None

_pipeline_capability = None
_last_report = None

if orca is not None:
    class ArcOverhangCapability(orca.slicing.SlicingPipelineCapabilityBase):
        def get_name(self):
            return "Arc Overhang"
        def on_load(self):
            global _pipeline_capability
            _pipeline_capability = self
        def on_unload(self):
            global _pipeline_capability
            if _pipeline_capability is self:
                _pipeline_capability = None
        def get_default_config(self):
            return dict(DEFAULTS)
        def has_config_ui(self):
            return True
        def get_config_ui(self):
            return config_page()
        def execute(self, ctx):
            global _last_report
            if ctx.step != orca.slicing.Step.psGCodePostProcess:
                return orca.ExecutionResult.skipped("Arc Overhang runs at psGCodePostProcess.")
            try:
                cfg = json.loads(self.get_config() or "{}")
                resolved = {key: ctx.config_value(key) for key in CONFIG_KEYS}
                report = process_file(ctx.gcode_path, cfg, resolved, ctx.cancelled)
                _last_report = dict(report)
                message = f"Arc Overhang: {report['replaced_features']} features, {report['generated_arcs']} arcs, {report['skipped_features']} skipped."
                print(message)
                return orca.ExecutionResult.success(message, json.dumps(report))
            except Cancelled:
                return orca.ExecutionResult.skipped("Arc Overhang cancelled; G-code unchanged.")
            except Exception as error:
                _last_report = {"error":str(error)}
                return orca.ExecutionResult.failure(orca.PluginResult.FatalError, "Arc Overhang: " + str(error))


    class ArcOverhangPage(orca.pages.PagesPluginCapabilityBase):
        def get_name(self):
            return "Arc Overhang"
        def get_ui(self):
            return config_page(as_tab=True)
        def on_message(self, data):
            if not isinstance(data, dict):
                return
            request_id = data.get("request_id")
            if not isinstance(request_id, int) or isinstance(request_id, bool):
                return
            try:
                capability = _pipeline_capability
                if capability is None:
                    raise RuntimeError("Arc Overhang processing is not loaded. Enable both plugin capabilities.")
                action = data.get("action")
                if action not in ("read", "save"):
                    raise ValueError("Unknown request.")
                if action == "save":
                    requested = configuration(data.get("config"))
                    if not isinstance(data.get("config"), dict):
                        raise ValueError("Settings must be a JSON object.")
                    if not capability.save_config(json.dumps(requested)):
                        raise RuntimeError("Could not save settings.")
                effective = configuration(json.loads(capability.get_config() or "{}"))
                response = {"request_id":request_id, "ok":True, "config":effective, "last_report":_last_report}
                if action == "save":
                    response["preset_override_active"] = effective != requested
                self.post_message(response)
            except Exception as error:
                self.post_message({"request_id":request_id, "ok":False, "error":str(error)})

    @orca.plugin
    class ArcOverhangPlugin(orca.base):
        def register_capabilities(self):
            orca.register_capability(ArcOverhangCapability)
            orca.register_capability(ArcOverhangPage)

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Arc Overhang for OrcaSlicer 2.5")
    parser.add_argument("gcode")
    parser.add_argument("--config", help="JSON configuration file")
    args = parser.parse_args()
    settings = json.loads(Path(args.config).read_text(encoding="utf-8")) if args.config else None
    print(json.dumps(process_file(args.gcode, settings), indent=2))
