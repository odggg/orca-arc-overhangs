# /// script
# requires-python = ">=3.12"
# dependencies = ["numpy>=1.26,<3", "shapely>=2.0,<3"]
#
# [tool.orcaslicer.plugin]
# name = "Arc Overhang"
# description = "Concentric arc overhangs for OrcaSlicer 2.5. GPL-3.0; based on Kelsch, Nicolai Wachenschwan and Steven McCulloch."
# author = "Kelsch / Nicolai Wachenschwan / Steven McCulloch; Orca 2.5 adaptation"
# version = "0.3.1"
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
import shapely
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

UI_TEMPLATE = '<!doctype html>\n<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">\n<title>Arc Overhang</title><style>:root{color-scheme:light dark;font:14px/1.5 "Segoe UI",system-ui,sans-serif;--bg:light-dark(#f6f5f0,#161c1b);--panel:light-dark(#fffefa,#1f2725);--ink:light-dark(#1c3230,#e1e9e5);--muted:light-dark(#63726b,#a4b4aa);--line:light-dark(#dce2d9,#39443d);--soft:light-dark(#f0f3ec,#29332b);--accent:light-dark(#19645a,#8ed4bb);--accent-ink:light-dark(#fffefa,#14281e);--warm:light-dark(#9d5c2b,#e8b780);--shadow:0 3px 16px #102e2110}\nhtml[data-orca-theme=dark],html[data-theme=dark]{color-scheme:dark}html[data-orca-theme=light],html[data-theme=light]{color-scheme:light}\n*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink)}button,input,select,textarea{font:inherit;color:inherit}button{cursor:pointer}button:disabled{cursor:wait;opacity:.55}a{color:var(--accent)}:focus-visible{outline:3px solid var(--accent);outline-offset:3px}[hidden]{display:none!important}.sr-only{position:absolute;width:1px;height:1px;padding:0;overflow:hidden;clip:rect(0,0,0,0);white-space:nowrap;border:0}\n.app-shell{max-width:1320px;margin:auto;padding:28px 34px 0}.app-header{display:flex;align-items:center;justify-content:space-between;gap:18px;padding-bottom:24px}.identity{display:flex;align-items:center;gap:12px}.brand{width:42px;height:42px;color:var(--accent)}h1{font-size:23px;letter-spacing:-.7px;line-height:1.3;margin:0;font-weight:650}.version{font:11px/1.5 ui-monospace,monospace;letter-spacing:0;color:var(--muted);vertical-align:middle;margin-left:8px}.eyebrow{font-size:12px;margin:2px 0 0;color:var(--muted)}.local-badge{display:inline-flex;align-items:center;gap:7px;color:var(--muted);font-size:11px;white-space:nowrap}.local-badge>span{width:6px;height:6px;background:var(--accent);border-radius:50%}.view-nav{display:flex;gap:26px;border-bottom:1px solid var(--line)}.view-nav button{border:0;border-bottom:2px solid transparent;background:none;padding:12px 0;margin-bottom:-1px;color:var(--muted);font-weight:600}.view-nav button[aria-current=page]{color:var(--accent);border-color:var(--accent)}.context-note{font-size:11px;color:var(--muted);margin:10px 0 0}.section-heading{display:flex;justify-content:space-between;align-items:center;gap:16px;margin:30px 0 22px}.kicker{font-size:10px;letter-spacing:1.7px;font-weight:700;color:var(--muted);margin:0 0 6px}h2{font-size:30px;line-height:1.2;letter-spacing:-1px;font-weight:600;margin:0 0 8px}.section-heading p:not(.kicker){color:var(--muted);margin:0}h3{font-size:16px;letter-spacing:-.25px;margin:0;font-weight:650}h4{font-size:18px;letter-spacing:-.4px;margin:8px 0}p{margin:0 0 12px}.enable-switch{display:flex;gap:12px;align-items:center;font-size:12px;white-space:nowrap}input[type=checkbox]{accent-color:var(--accent);width:18px;height:18px;cursor:pointer}input[role=switch]{appearance:none;background:var(--line);border-radius:30px;width:40px;height:23px;position:relative;border:1px solid transparent}input[role=switch]::before{content:"";position:absolute;width:17px;height:17px;background:var(--panel);border-radius:50%;left:2px;top:2px;transition:transform .16s}input[role=switch]:checked{background:var(--accent)}input[role=switch]:checked::before{transform:translateX(17px)}\n.overview-grid{display:grid;grid-template-columns:minmax(0,1fr) 328px;gap:22px;align-items:start}.panel{background:var(--panel);border:1px solid var(--line);border-radius:15px;box-shadow:var(--shadow);overflow:hidden}.panel-heading{display:flex;justify-content:space-between;align-items:center;gap:15px;padding:20px 22px}.panel-heading .kicker{font-size:9px}.layer-picker{max-width:50%;font-size:11px}.layer-picker select{font-size:11px;padding:7px;max-width:100%}.plot{position:relative;min-height:360px;background:radial-gradient(ellipse at 50% 70%,var(--soft),transparent 68%)}#export-drawing{display:block;width:100%;height:360px}#export-paths polyline{fill:none;stroke:var(--accent);stroke-width:1.5;stroke-linecap:round;stroke-linejoin:round;vector-effect:non-scaling-stroke}#export-outlines polyline{fill:none;stroke:var(--muted);stroke-width:1;stroke-dasharray:4 4;opacity:.7;vector-effect:non-scaling-stroke}.empty-state{position:absolute;inset:0;display:flex;flex-direction:column;align-items:center;justify-content:center;text-align:center;padding:25px;max-width:450px;margin:auto}.empty-state svg{width:180px;height:110px;color:var(--accent);opacity:.6}.empty-state p{color:var(--muted);font-size:12px;max-width:300px}.text-button{background:none;border:0;padding:5px 0;color:var(--accent);font-size:12px;font-weight:650}.text-button span{padding-left:6px}.plot-caption{display:flex;gap:15px;align-items:center;flex-wrap:wrap;padding:10px 22px 18px;font-size:10px;color:var(--muted)}.plot-caption>span{display:inline-flex;gap:5px;align-items:center}.plot-caption>span:last-child{margin-left:auto}.legend-line{display:inline-block;width:14px;height:2px;background:var(--accent)}.legend-line.outline{height:0;background:none;border-top:1px dashed var(--muted)}.export-stats{display:grid;grid-template-columns:repeat(3,1fr);border-top:1px solid var(--line);padding:18px 0}.export-stats>div{text-align:center;border-right:1px solid var(--line)}.export-stats>div:last-child{border:0}.export-stats span{display:block;font-size:24px;line-height:1.1;letter-spacing:-.5px;font-weight:600}.export-stats small{display:block;font-size:10px;color:var(--muted);margin-top:5px}.report-summary{font-size:11px;color:var(--muted);padding:0 22px 14px;margin:0}.report-details{margin:0 22px 18px;font-size:12px}.report-details summary{cursor:pointer;color:var(--accent)}.report-details li{margin-top:7px}\n.setup-panel{padding:20px}.step-heading{display:flex;align-items:flex-start;gap:11px;margin-bottom:15px}.step-heading>span{display:inline-flex;align-items:center;justify-content:center;width:26px;height:26px;flex-shrink:0;font:11px ui-monospace,monospace;border:1px solid var(--line);border-radius:50%;color:var(--accent)}.step-heading p{font-size:11px;color:var(--muted);margin:3px 0 0}.mode-select{font-weight:600;width:100%}.mode-note{font-size:11px;color:var(--muted);margin:10px 0 16px}.quick-fields{border-top:1px solid var(--line)}.field{display:grid;grid-template-columns:minmax(0,1fr) auto;column-gap:12px;align-items:center;padding:15px 0;border-bottom:1px solid var(--line)}.field>label{font-weight:600;font-size:12px}.field-help{font-size:11px;color:var(--muted);margin:6px 0 0}.field .field-help{grid-column:1/-1}.number-control{display:flex;align-items:center;gap:7px;white-space:nowrap}.number-control>span{font-size:10px;color:var(--muted);min-width:25px}.number-control input{width:82px;padding:8px 8px;font-variant-numeric:tabular-nums}select,input[type=number],textarea{background:var(--panel);border:1px solid var(--line);border-radius:7px;padding:9px 10px}select{max-width:100%}input[aria-invalid=true]{border-color:var(--warm);outline-color:var(--warm)}.decision-grid{display:grid;grid-template-columns:1fr 1fr;gap:22px;margin-top:22px}.decision{padding:20px 22px}.decision>select{width:100%;font-size:12px}.sequence{display:flex;align-items:center;gap:6px;padding:0;list-style:none;margin:14px 0 0;font-size:10px;color:var(--muted)}.sequence li{display:flex;align-items:center;gap:6px}.sequence li:not(:last-child)::after{content:"→";color:var(--warm)}.inline-note{font-size:11px;color:var(--warm);background:var(--soft);padding:10px 14px;margin:0 20px;border-radius:6px}.decision .inline-note{margin:10px 0 0}\n.settings-group{background:var(--panel);border:1px solid var(--line);border-radius:12px;margin:14px 0;overflow:hidden}.settings-group>summary{cursor:pointer;padding:18px 22px;font-size:15px;font-weight:600;list-style-position:inside}.settings-group>summary small{display:block;padding-left:18px;font-size:11px;color:var(--muted);font-weight:400;margin-top:3px}.field-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));column-gap:32px;padding:0 22px 15px}.field-grid .field:nth-last-child(-n+2){border-bottom:0}.import-area,.guide-text{padding:0 22px 22px;font-size:12px;color:var(--muted)}textarea{width:100%;display:block;margin:8px 0 12px;font:12px/1.5 ui-monospace,monospace}.guide-panel #guide-drawing{width:100%;max-height:330px;display:block;color:var(--ink)}#guide-drawing text{fill:var(--muted);font:12px "Segoe UI",sans-serif}#guide-paths path{fill:none;stroke:var(--accent);stroke-width:2;stroke-linecap:round}.guide-copy{border-top:1px solid var(--line);padding:20px 24px;display:grid;grid-template-columns:1fr auto;column-gap:30px}.guide-copy h4,.guide-copy p{grid-column:1}.guide-copy p{font-size:12px;color:var(--muted);max-width:630px}.mini-measure{grid-column:2;grid-row:1/3;display:flex;flex-direction:column;justify-content:center;border-left:1px solid var(--line);padding-left:25px}.mini-measure span{font-size:11px;color:var(--muted)}.mini-measure strong{font-size:19px;font-weight:500}.guide-steps{display:grid;grid-template-columns:repeat(3,1fr);gap:22px;margin:28px 0}.guide-steps article>span{display:inline-block;font:14px ui-monospace,monospace;color:var(--warm);border-bottom:1px solid var(--warm);margin-bottom:12px;padding-right:16px}.guide-steps h3{font-size:15px;margin-bottom:8px}.guide-steps p{font-size:12px;color:var(--muted)}\n.save-bar{position:sticky;bottom:12px;z-index:2;display:flex;justify-content:space-between;align-items:center;gap:16px;margin:30px 0 0;padding:13px 16px;background:var(--panel);border:1px solid var(--line);border-radius:12px;box-shadow:0 4px 25px #102e2120}.save-state{display:flex;align-items:center;gap:9px;max-width:65%;font-size:12px;color:var(--muted)}.state-dot{display:inline-block;width:6px;height:6px;border-radius:50%;background:var(--accent);flex-shrink:0}.save-actions{display:flex;gap:9px;flex-shrink:0}.primary,.secondary{padding:10px 17px;border-radius:7px;font-size:12px;font-weight:600;border:1px solid var(--line);background:var(--panel)}.primary{background:var(--accent);border-color:var(--accent);color:var(--accent-ink)}.primary span{padding-left:13px}.secondary:hover{background:var(--soft)}.app-footer{display:flex;justify-content:space-between;gap:15px;padding:17px 2px 22px;font-size:10px;color:var(--muted)}\n@media(max-width:1000px){.app-shell{padding:20px 22px 0}.overview-grid{grid-template-columns:minmax(0,1fr) 295px;gap:16px}.decision-grid{gap:16px}.panel-heading{padding:17px}.setup-panel{padding:17px}h2{font-size:26px}.plot-caption>span:last-child{margin-left:0}}@media(max-width:760px){.app-shell{padding:18px 16px 0}.overview-grid,.decision-grid{grid-template-columns:1fr}.app-header{gap:10px}.app-header>.local-badge{display:none}.section-heading{align-items:flex-start;flex-direction:column;margin-top:24px}.enable-switch{align-self:flex-end}.field-grid{grid-template-columns:1fr}.field-grid .field{border-bottom:1px solid var(--line)}.field-grid .field:last-child{border:0}.quick-fields{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:15px}.quick-fields .field{display:flex;flex-direction:column;align-items:flex-start;gap:8px}.quick-fields .number-control input{width:74px}.quick-fields .field-help{margin:0}.guide-steps{grid-template-columns:1fr;gap:10px}.guide-copy{display:block}.mini-measure{border:0;border-top:1px solid var(--line);padding:14px 0 0}.save-bar{bottom:8px;flex-wrap:wrap}.save-state{max-width:100%;font-size:11px}.save-actions{margin-left:auto}.app-footer{flex-direction:column;gap:4px}.plot,#export-drawing{min-height:280px;height:280px}h2{font-size:25px}}@media(max-width:440px){.quick-fields{grid-template-columns:1fr}.quick-fields .field{display:grid;grid-template-columns:1fr auto}.quick-fields .field-help{grid-column:1/-1}.number-control input{width:84px}.view-nav{gap:23px}.view-nav button{font-size:12px}.layer-picker{max-width:55%}.panel-heading h3{font-size:14px}.guide-panel .panel-heading>.local-badge{font-size:9px}.guide-copy h4{font-size:17px}.sequence{flex-wrap:wrap}.app-shell{padding:14px 12px 0}}@media(prefers-reduced-motion:reduce){*{transition:none!important;animation:none!important;scroll-behavior:auto!important}}\n\n.plot-caption .text-button{font-size:10px;padding:0}.plot-caption .text-button:disabled{cursor:default}\n</style></head>\n<body><div class="app-shell">\n<header class="app-header"><div class="identity"><svg class="brand" viewBox="0 0 40 40" aria-hidden="true"><path d="M7 31V9h9v22M19 31a12 12 0 0 1 12-12M19 24a5 5 0 0 1 5-5" fill="none" stroke="currentColor" stroke-width="3.5" stroke-linejoin="round"/></svg><div><h1>Arc Overhang <span class="version">__VERSION__</span></h1><p class="eyebrow">Overhang support, made visible.</p></div></div><span class="local-badge"><span></span> Local · open source</span></header>\n<nav class="view-nav" aria-label="Plugin workspace"><button type="button" data-view="overview" aria-current="page">Overview</button><button type="button" data-view="tuning">Fine tuning</button><button type="button" data-view="guide">How it works</button></nav>\n<p class="context-note">__CONTEXT__</p>\n<main id="settings">\n<section id="view-overview" class="app-view" aria-label="Overview">\n<div class="section-heading"><div><p class="kicker">THE WORKBENCH</p><h2>Shape your overhang support.</h2><p>Choose how the overhang is filled. Export, then inspect the result.</p></div><label class="enable-switch"><span>Enable processing</span><input id="enabled" type="checkbox" role="switch"></label></div>\n<p id="processing-note" class="inline-note" hidden>Processing is disabled. You can adjust settings, then enable and save them before exporting.</p>\n<div class="overview-grid">\n<section class="panel export-panel" aria-labelledby="preview-heading"><div class="panel-heading"><div><p class="kicker">LAST EXPORT</p><h3 id="preview-heading">Your generated support</h3></div><label class="layer-picker"><span class="sr-only">Exported region</span><select id="preview-layer" disabled><option>No export yet</option></select></label></div>\n<div id="preview-warning" class="inline-note" hidden></div>\n<div class="plot"><svg id="export-drawing" viewBox="0 0 480 340" role="img" aria-label="Simplified support paths from the last export"><g id="export-outlines"></g><g id="export-paths"></g></svg><div id="preview-empty" class="empty-state"><svg viewBox="0 0 180 110" aria-hidden="true"><path d="M20 90V25H65V90M65 88a58 58 0 0 1 58-58M65 78a48 48 0 0 1 48-48M65 68a38 38 0 0 1 38-38M65 58a28 28 0 0 1 28-28" fill="none" stroke="currentColor" stroke-width="2.5"/><path d="M65 90H157V25H65" fill="none" stroke="currentColor" stroke-dasharray="4 5"/></svg><h4>A path, once you export.</h4><p>Select Arc Overhang in your process pipeline and export. Generated support will appear here; this view does not upload your model.</p><button type="button" class="text-button" id="open-guide">See how it works <span aria-hidden="true">↗</span></button></div></div>\n<div class="plot-caption"><span><i class="legend-line"></i> Generated support</span><span><i class="legend-line outline"></i> Layer outline</span><button id="preview-fit" class="text-button" type="button" aria-pressed="false" disabled>Show whole layer</button><span id="preview-caption">A simplified 2D snapshot of the last export.</span></div>\n<div class="export-stats" aria-label="Last export summary"><div><span id="stat-regions">—</span><small>regions replaced</small></div><div><span id="stat-paths">—</span><small>support paths</small></div><div><span id="stat-hilbert">—</span><small>Hilbert regions</small></div></div>\n<p id="last-report" class="report-summary" role="status">No export with this plugin version yet.</p><details id="report-details" class="report-details" hidden><summary>Why regions were kept</summary><ul id="skip-list"></ul></details></section>\n<aside class="setup-stack" aria-label="Essential settings"><section class="panel setup-panel"><div class="step-heading"><span>01</span><div><h3>Choose your path</h3><p>One overhang, two approaches.</p></div></div><label for="overhang_mode" class="sr-only">Overhang mode</label><select id="overhang_mode" class="mode-select"><option value="arc">Concentric Arcs</option><option value="wave">Wave fronts · experimental</option></select><p id="mode-note" class="mode-note"></p><div data-mode="arc" class="quick-fields">__ARC_QUICK__</div><div data-mode="wave" class="quick-fields" hidden>__WAVE_QUICK__</div><div class="quick-fields">__ANCHOR_QUICK__</div><button type="button" class="text-button" id="open-tuning">All settings <span aria-hidden="true">↗</span></button></section></aside>\n</div>\n<div class="decision-grid"><section class="panel decision"><div class="step-heading"><span>02</span><div><h3>Decide the sequence</h3><p>Where support sits in the layer.</p></div></div><label for="print_order" class="sr-only">Print order</label><select id="print_order"><option value="layer_tail">Our previous order · default</option><option value="slicer">Keep slicer order</option></select><ol id="sequence" class="sequence"><li>Walls + infill</li><li>Arcs / Waves</li><li>Overhang walls</li></ol><p id="sequence-note" class="field-help">Applied within each layer and tool section.</p></section>\n<section class="panel decision"><div class="step-heading"><span>03</span><div><h3>The layer above</h3><p>Choose its internal solid infill.</p></div></div><label for="next_layer_pattern" class="sr-only">Infill on next layer</label><select id="next_layer_pattern"><option value="slicer">Keep slicer pattern · default</option><option value="hilbert">Hilbert curve · slower, experimental</option></select><p class="field-help">Hilbert applies only to eligible internal solid infill directly above generated support. Top surfaces, bridges and sparse infill stay as sliced.</p><p id="floor-note" class="inline-note" hidden>Wave floor Hilbert is also enabled in Fine tuning. It can affect more than one layer.</p></section></div>\n</section>\n<section id="view-tuning" class="app-view" aria-label="Fine tuning" hidden><div class="section-heading"><div><p class="kicker">FINE TUNING</p><h2>A little more control.</h2><p>Your existing values are preserved, including settings for the other mode.</p></div></div>\n<details class="settings-group" data-mode="arc" open><summary><span>Arc behaviour</span><small>Shape, flow &amp; cooling time</small></summary><div class="field-grid">__ARC__</div></details>\n<details class="settings-group" data-mode="wave" open hidden><summary><span>Wave behaviour</span><small>Path shape, travel &amp; anchoring</small></summary><div class="field-grid">__WAVE__</div></details>\n<details class="settings-group" data-mode="wave" hidden><summary><span>Above the Waves</span><small>Floor layers, Hilbert &amp; cooling</small></summary><div class="field-grid">__FLOOR__</div></details>\n<details class="settings-group"><summary><span>Shared controls</span><small>Eligibility, travel, retraction &amp; limits</small></summary><div class="field-grid">__SHARED__</div></details>\n<details class="settings-group" data-mode="wave" hidden><summary><span>Import a Wave profile</span><small>Paste values; review before saving</small></summary><div class="import-area"><p>Paste WaveOverhangs <code>wave_overhang_*</code> settings, a profile JSON, or its <code>WAVE_OVERHANG_CONFIG</code> comment. Only recognised Wave options are imported. Printer and filament profiles stay in Orca.</p><label for="import_text">Profile values</label><textarea id="import_text" rows="5" placeholder="; wave_overhang_line_spacing = 0.35" spellcheck="false"></textarea><button id="import" class="secondary" type="button">Import pasted values</button></div></details>\n</section>\n<section id="view-guide" class="app-view" aria-label="How it works" hidden><div class="section-heading"><div><p class="kicker">UNDERSTAND THE PATH</p><h2>From supported edge to open space.</h2><p>A visual explanation of the selected method. This drawing is a concept, not your model.</p></div></div><section class="panel guide-panel"><div class="panel-heading"><h3 id="guide-heading">Concentric Arcs</h3><span class="local-badge">Concept illustration</span></div><svg id="guide-drawing" viewBox="0 0 640 270" role="img" aria-label="Concept drawing of generated support"><defs><pattern id="support-hatch" width="10" height="10" patternUnits="userSpaceOnUse"><path d="M0 10L10 0" stroke="currentColor" opacity=".15"/></pattern><clipPath id="guide-clip"><rect x="188" y="26" width="400" height="204" rx="8"/></clipPath></defs><rect x="42" y="26" width="146" height="204" rx="8" fill="url(#support-hatch)" stroke="currentColor" opacity=".6"/><rect x="188" y="26" width="400" height="204" rx="8" fill="none" stroke="currentColor" stroke-dasharray="5 7" opacity=".25"/><g id="guide-paths" clip-path="url(#guide-clip)"></g><text x="42" y="255">Supported area</text><text x="384" y="255">Overhang area</text></svg><div class="guide-copy"><h4 id="guide-title">Connected paths, built outwards.</h4><p id="guide-note"></p><div class="mini-measure"><span>Current spacing</span><strong id="spacing-readout">0.95 × nozzle</strong></div></div></section>\n<div class="guide-steps"><article><span>1</span><h3>Enable the pipeline</h3><p>Select Arc Overhang in Orca\'s process pipeline settings. Enabling this switch alone does not select the pipeline for your preset.</p></article><article><span>2</span><h3>Slice &amp; export</h3><p>Only suitable unsupported Bridge regions are replaced. If Orca uses extra overhang walls instead of bridges, that area stays unchanged.</p></article><article><span>3</span><h3>Reopen &amp; inspect</h3><p>Orca\'s normal preview precedes post-processing. Reopen the exported G-code to inspect the final print order and paths before printing.</p></article></div>\n<details class="settings-group"><summary><span>When no support appears</span><small>What to check</small></summary><div class="guide-text"><p>Check that the pipeline is selected and that the export includes unsupported Bridge or Internal Bridge paths. A supported bridge above infill is intentionally retained.</p><p>The default minimum area is 50 mm². Small, unanchored or insufficiently covered regions remain as sliced. Read the last export\'s skipped reasons on Overview.</p><p>For counterbore models, partially bridged strips may already be supported. Check Orca\'s counterbore setting if you expected a different result.</p></div></details>\n</section>\n</main>\n<div class="save-bar"><div class="save-state"><span class="state-dot" aria-hidden="true"></span><span id="status" role="status" aria-live="polite">Loading settings…</span></div><div class="save-actions"><button id="refresh" type="button" class="secondary">Reload saved</button><button id="save" type="button" class="primary">Save settings <span aria-hidden="true">↗</span></button></div></div>\n<footer class="app-footer"><span>GPL-3.0 · runs locally · __VERSION__</span><span>Arc concept: McCulloch · Wachenschwan · Kelsch. Contributions: persano.</span></footer>\n</div><script>__BRIDGE__\nconst defaults = __DEFAULTS__;\nconst IMPORT = __IMPORT__;\nconst ALIASES = __ALIASES__;\nconst fields = Object.keys(defaults);\nconst $ = id => document.getElementById(id);\nconst all = selector => Array.from(document.querySelectorAll?.(selector) || []);\nconst status = $(\'status\');\nlet draft = null, ready = false, savingUI = false, lastReport = null, showWholeLayer = false;\nfunction text(id, value) { const el=$(id); if(el) el.textContent=value; }\nfunction collect() {\n  const values={};\n  for(const key of fields) {\n    const el=$(key); if(!el) continue;\n    values[key]=typeof defaults[key]===\'boolean\'?el.checked:(typeof defaults[key]===\'string\'?el.value:Number(el.value));\n  }\n  return values;\n}\nfunction selectView(name) {\n  for(const view of all(\'.app-view\')) view.hidden=view.id!==\'view-\'+name;\n  for(const button of all(\'[data-view]\')) {\n    if(button.dataset.view===name) button.setAttribute(\'aria-current\',\'page\');\n    else button.removeAttribute(\'aria-current\');\n  }\n  if(name===\'guide\') renderGuide();\n}\nfunction renderState() {\n  const disabled=$(\'processing-note\'); if(disabled) disabled.hidden=!!$(\'enabled\')?.checked;\n  const wave=$(\'overhang_mode\')?.value===\'wave\';\n  for(const section of all(\'[data-mode]\')) section.hidden=section.dataset.mode!==(wave?\'wave\':\'arc\');\n  text(\'mode-note\',wave?\'Offset fronts grow from the supported edge. Wave mode is experimental.\':\'Concentric paths connect to the previous layer and extend into the overhang.\');\n  const slicer=$(\'print_order\')?.value===\'slicer\';\n  const labels=slicer?[\'Slicer sequence\',\'Bridge → support\',\'Early overhang walls follow\']:[\'Walls + infill\',wave?\'Waves\':\'Arcs\',\'Overhang walls\'];\n  all(\'#sequence li\').forEach((el,index)=>{el.textContent=labels[index];});\n  text(\'sequence-note\',slicer?\'Normal walls and infill stay in their sliced positions. Early Overhang walls follow the support.\':\'The previous order is kept within each layer and tool section.\');\n  const note=$(\'floor-note\'); if(note) note.hidden=!(wave && $(\'wave_floor_use_hilbert\')?.checked);\n  renderGuide(); renderPreviewWarning();\n}\nfunction renderGuide() {\n  const group=$(\'guide-paths\'); if(!group) return;\n  const wave=$(\'overhang_mode\')?.value===\'wave\';\n  const raw=Number($(wave?\'wave_line_spacing_mm\':\'arc_spacing_nozzle_ratio\')?.value);\n  const spacing=Number.isFinite(raw)?Math.max(.05,Math.min(1.5,raw)):0.4;\n  const count=Math.max(8,Math.min(30,Math.round(13/spacing)));\n  while(group.firstChild) group.removeChild(group.firstChild);\n  for(let i=0;i<count;i++) {\n    const path=document.createElementNS(\'http://www.w3.org/2000/svg\',\'path\');\n    const step=400/count, x=193+i*step;\n    path.setAttribute(\'d\',wave?`M${x} 32 C${x+25} 83 ${x+25} 173 ${x} 224`:`M190 ${224-i*2} Q${190+i*4} ${32-i*1.2} ${Math.min(588,205+i*step)} 32`);\n    group.appendChild(path);\n  }\n  text(\'guide-heading\',wave?\'Wave fronts\':\'Concentric Arcs\');\n  text(\'guide-title\',wave?\'A front that grows from support.\':\'Connected paths, built outwards.\');\n  text(\'guide-note\',wave?\'Each front grows from supported material. Flow, spacing and cooling affect adhesion; this drawing explains the pattern and does not predict print quality.\':\'The first path starts on existing support. Later paths connect to material already laid down. The actual geometry is calculated from your exported Bridge regions.\');\n  text(\'spacing-readout\',wave?`${raw===0?\'Nozzle ratio\':Number.isFinite(raw)?raw:\'—\'}${raw===0?\'\':\' mm\'}`:`${Number.isFinite(raw)?raw:\'—\'} × nozzle`);\n}\nfunction renderPreviewWarning() {\n  const el=$(\'preview-warning\'); if(!el) return;\n  const snapshot=lastReport?.preview, values=collect();\n  const different=snapshot?.settings && fields.some(key=>snapshot.settings[key]!==undefined && snapshot.settings[key]!==values[key]);\n  el.hidden=!different;\n  el.textContent=different?\'Settings differ from this export snapshot. Save and export again to update the paths.\':\'\';\n}\nfunction renderSnapshot(index=0) {\n  const layers=lastReport?.preview?.layers || [], layer=layers[index];\n  const empty=$(\'preview-empty\'), canvas=$(\'export-drawing\');\n  if(empty) empty.hidden=!!layer;\n  if(!canvas) return;\n  const paths=$(\'export-paths\'), outlines=$(\'export-outlines\');\n  if(!paths || !outlines) return;\n  paths.replaceChildren(); outlines.replaceChildren();\n  if(!layer) { canvas.setAttribute(\'viewBox\',\'0 0 480 340\'); return; }\n  const lines=showWholeLayer?[...(layer.outlines||[]),...(layer.paths||[])]:layer.paths||[];\n  const points=lines.flat().filter(p=>Array.isArray(p)&&p.length===2&&p.every(Number.isFinite));\n  if(!points.length) return;\n  const xs=points.map(p=>p[0]),ys=points.map(p=>p[1]);\n  const minX=Math.min(...xs),maxX=Math.max(...xs),minY=Math.min(...ys),maxY=Math.max(...ys);\n  const span=Math.max(maxX-minX,maxY-minY,1), pad=span*.12;\n  canvas.setAttribute(\'viewBox\',`${minX-pad} ${minY-pad} ${maxX-minX+pad*2} ${maxY-minY+pad*2}`);\n  for(const [key,group] of [[\'outlines\',outlines],[\'paths\',paths]]) {\n    group.setAttribute(\'transform\',`translate(0 ${minY+maxY}) scale(1 -1)`);\n    for(const line of layer[key]||[]) {\n      if(!line.every(p=>Array.isArray(p)&&p.length===2&&p.every(Number.isFinite))) continue;\n      const poly=document.createElementNS(\'http://www.w3.org/2000/svg\',\'polyline\');\n      poly.setAttribute(\'points\',line.map(p=>p.join(\',\')).join(\' \')); group.appendChild(poly);\n    }\n  }\n  text(\'preview-caption\',`Layer ${layer.layer} · Z ${layer.z} mm · T${layer.tool} · ${layer.mode===\'wave\'?\'Wave\':\'Arc\'}${lastReport.preview.limited?\' · limited snapshot\':\' · simplified 2D\'}`);\n}\nfunction renderReport(report) {\n  lastReport=report || null;\n  const valid=report && !report.error;\n  text(\'stat-regions\',valid?report.replaced_features:\'—\');\n  text(\'stat-paths\',valid?report.generated_arcs:\'—\');\n  text(\'stat-hilbert\',valid?(report.hilbert_features||0):\'—\');\n  text(\'last-report\',!report?\'No export with this plugin version yet.\':report.error?\'Last export: \'+report.error:`Last export: ${report.replaced_features} regions replaced, ${report.generated_arcs} support paths, ${report.skipped_features} skipped.${report.preview_error?\' \'+report.preview_error:\'\'}`);\n  const reasons=Object.entries(report?.skip_reasons||{}), details=$(\'report-details\'),list=$(\'skip-list\');\n  if(details) details.hidden=!reasons.length;\n  if(list) { list.replaceChildren(); for(const [reason,count] of reasons) { const item=document.createElement(\'li\'); item.textContent=`${count} × ${reason}`; list.appendChild(item); } }\n  const select=$(\'preview-layer\');\n  if(select) {\n    select.replaceChildren(); const layers=report?.preview?.layers||[];\n    for(const [index,layer] of layers.entries()) { const option=document.createElement(\'option\'); option.value=String(index); option.textContent=`Region ${index+1} · Layer ${layer.layer} · T${layer.tool}`; select.appendChild(option); }\n    if(!layers.length) { const option=document.createElement(\'option\'); option.textContent=\'No support snapshot\'; select.appendChild(option); }\n    select.disabled=!layers.length;\n  }\n  if($(\'preview-fit\')) $(\'preview-fit\').disabled=!(report?.preview?.layers||[]).length;\n  renderSnapshot(); renderPreviewWarning();\n}\nfunction remember() { draft=collect(); status.textContent=\'Unsaved changes.\'; renderState(); }\nfunction readonly() { return window.orca.getContext ? !!window.orca.getContext().readOnly : false; }\nasync function initialize(discard=false) {\n  try {\n    let saved=await settingsBridge.getConfig(); if(typeof saved===\'string\') saved=JSON.parse(saved);\n    if(discard===true) draft=null;\n    const values={...defaults,...(saved||{}),...(draft||{})};\n    for(const key of fields) {\n      const el=$(key); if(!el) continue;\n      if(typeof defaults[key]===\'boolean\') el.checked=values[key]; else el.value=values[key];\n      el.disabled=readonly(); el.removeAttribute?.(\'aria-invalid\');\n    }\n    ready=true; renderState();\n    status.textContent=readonly()?\'This preset is read-only.\':draft?\'Unsaved changes.\':\'Settings loaded.\';\n  } catch(error) { status.textContent=\'Could not load settings: \'+error.message; }\n}\nfunction invalid(key,message) {\n  const el=$(key); el?.setAttribute?.(\'aria-invalid\',\'true\');\n  if(el?.closest) {\n    selectView(\'tuning\');\n    const overview=el.closest(\'#view-overview\'); if(overview) selectView(\'overview\');\n    let parent=el.parentElement;\n    while(parent) { if(parent.tagName===\'DETAILS\') parent.open=true; if(parent.dataset?.mode) parent.hidden=false; parent=parent.parentElement; }\n    el.focus();\n  }\n  status.textContent=message;\n}\n$(\'save\').onclick=async()=>{\n  if(!ready) { status.textContent=\'Wait for settings to load.\'; return; }\n  if(readonly()) { status.textContent=\'This preset is read-only.\'; return; }\n  if(savingUI) return;\n  const values=collect();\n  for(const key of fields) {\n    $(key)?.removeAttribute?.(\'aria-invalid\');\n    if(typeof values[key]===\'number\' && (!Number.isFinite(values[key]) || $(key)?.value===\'\')) { invalid(key,\'Please enter a valid number for \'+key+\'.\'); return; }\n    if($(key)?.checkValidity && !$(key).checkValidity()) { invalid(key,$(key).validationMessage); return; }\n  }\n  if(values.minimum_arc_speed_mm_s>values.arc_speed_mm_s) { invalid(\'minimum_arc_speed_mm_s\',\'Minimum speed must not exceed maximum arc speed.\'); return; }\n  if(values.z_min_mm>values.z_max_mm) { invalid(\'z_min_mm\',\'Invalid Z range.\'); return; }\n  savingUI=true; $(\'save\').disabled=true; status.textContent=\'Saving…\';\n  try {\n    const result=await settingsBridge.saveConfig(values);\n    if(result===false) status.textContent=\'Save failed.\';\n    else { draft=null; status.textContent=result?.preset_override_active?\'Global defaults saved. The active preset overrides some values; edit them in Plugin Configuration.\':\'Saved.\'; }\n  } catch(error) {\n    const key=fields.find(key=>error.message.startsWith(key+\' \'));\n    if(key) invalid(key,\'Save failed: \'+error.message);\n    else status.textContent=\'Save failed: \'+error.message;\n  }\n  finally { savingUI=false; $(\'save\').disabled=false; renderPreviewWarning(); }\n};\nfunction importProfile(text) {\n  const marker={},explicit={},prefixed=new Set(),ignored=[];\n  for(const line of text.split(/\\r?\\n/)) {\n    if(line.includes(\'WAVE_OVERHANG_CONFIG\')) for(const m of line.matchAll(/(\\w+)=(\\S+)/g)) marker[ALIASES[m[1]]||m[1]]=m[2];\n    for(const m of line.matchAll(/wave_overhang_(\\w+?)["\']?\\s*[:=]\\s*["\']?([^\\s"\',;]+)/g)) { explicit[m[1]]=m[2]; prefixed.add(m[1]); }\n  }\n  const found={...marker,...explicit},values={overhang_mode:\'wave\'};\n  for(const [key,raw] of Object.entries(found)) {\n    const spec=IMPORT[key];\n    if(!spec) { if(prefixed.has(key)&&![\'min_angle\',\'spacing_mode\',\'seam_mode\',\'debug_gcode\',\'outer_perimeters\'].includes(key)) ignored.push(\'wave_overhang_\'+key); continue; }\n    const [target,kind]=spec,number=Number(raw);\n    if(kind===\'text\') { if([\'smart\',\'zigzag\',\'monotonic\'].includes(raw.toLowerCase())) values[target]=raw.toLowerCase(); else ignored.push(\'wave_overhang_\'+key); }\n    else if(kind===\'bool\') { if([\'0\',\'1\',\'true\',\'false\'].includes(raw.toLowerCase())) values[target]=[\'1\',\'true\'].includes(raw.toLowerCase()); else ignored.push(\'wave_overhang_\'+key); }\n    else if(!Number.isFinite(number)) ignored.push(\'wave_overhang_\'+key);\n    else if(kind===\'fan\') { values[target[0]]=number>=0; values[target[1]]=Math.max(0,number); }\n    else values[target]=number;\n  }\n  return {values,ignored};\n}\n$(\'import\').onclick=()=>{\n  if(readonly()) { status.textContent=\'This preset is read-only.\'; return; }\n  const {values,ignored}=importProfile($(\'import_text\').value||\'\');\n  const count=Object.keys(values).length-1;\n  if(!count) { status.textContent=\'No wave_overhang_ settings found in the pasted text.\'; return; }\n  for(const [key,value] of Object.entries(values)) { const el=$(key); if(!el) continue; if(typeof value===\'boolean\') el.checked=value; else el.value=value; }\n  remember(); $(\'import_text\').value=\'\';\n  status.textContent=`Imported ${count} settings; press Save to keep them.`+(ignored.length?\' No equivalent for: \'+ignored.join(\', \')+\'.\':\'\');\n};\n$(\'refresh\').onclick=()=>initialize(true);\n$(\'settings\').addEventListener(\'input\',event=>{if(fields.includes(event.target.id)) remember();});\n$(\'settings\').addEventListener(\'change\',event=>{if(fields.includes(event.target.id)) remember();});\nfor(const button of all(\'[data-view]\')) button.onclick=()=>selectView(button.dataset.view);\nif($(\'open-guide\')) $(\'open-guide\').onclick=()=>selectView(\'guide\');\nif($(\'open-tuning\')) $(\'open-tuning\').onclick=()=>selectView(\'tuning\');\nif($(\'preview-layer\')) $(\'preview-layer\').onchange=()=>renderSnapshot(Number($(\'preview-layer\').value));\nif($(\'preview-fit\')) $(\'preview-fit\').onclick=()=>{showWholeLayer=!showWholeLayer; $(\'preview-fit\').setAttribute(\'aria-pressed\',String(showWholeLayer)); $(\'preview-fit\').textContent=showWholeLayer?\'Fit support\':\'Show whole layer\'; renderSnapshot(Number($(\'preview-layer\')?.value||0));};\ndocument.addEventListener(\'visibilitychange\',()=>{if(!document.hidden) initialize();});\ninitialize();\n</script></body></html>\n'

VERSION = "0.3.1"
MARKER = "; ARC_OVERHANG_PLUGIN:"
DEFAULTS = {
    "enabled": True,
    "next_layer_pattern": "slicer",
    "print_order": "layer_tail",
    "overhang_mode": "arc",
    "wave_pattern": "smart",
    "wave_spacing_nozzle_ratio": 0.875,
    "wave_line_spacing_mm": 0.35,
    "wave_speed_mm_s": 2.0,
    "wave_travel_speed_mm_s": 40.0,
    "wave_flow_mm3_per_mm": 0.15,
    "wave_perimeter_overlap_mm": 0.1,
    "wave_min_width_mm": 0.7,
    "wave_min_new_area_mm2": 0.01,
    "wave_min_length_mm": 0.0,
    "wave_max_iterations": 0,
    "wave_corner_taper": False,
    "wave_corner_spacing_mm": 0.2,
    "wave_corner_distance_mm": 3.0,
    "wave_corner_angle_deg": 90.0,
    "wave_fan_override": False,
    "wave_fan_percent": 100.0,
    "wave_aux_fan_override": False,
    "wave_aux_fan_percent": 0.0,
    "wave_temperature_c": 0.0,
    "wave_min_time_s": 0.0,
    "wave_min_layer_time_s": 0.0,
    "wave_instead_of_bridges": True,
    "wave_end_retract_mm": 0.0,
    "wave_perimeter_speed_mm_s": 0.0,
    "wave_floor_layers": 2,
    "wave_floor_print_speed_mm_s": 0.0,
    "wave_floor_perimeter_speed_mm_s": 0.0,
    "wave_floor_speed_ramp": 0,
    "wave_floor_use_hilbert": False,
    "wave_floor_hilbert_layers": 0,
    "wave_floor_hilbert_density_percent": 100.0,
    "wave_floor_fan_override": False,
    "wave_floor_fan_percent": 0.0,
    "wave_floor_aux_fan_override": False,
    "wave_floor_aux_fan_percent": 0.0,
    "z_hop_mm": 0.0,
    "arc_speed_mm_s": 1.5,
    "minimum_arc_speed_mm_s": 0.5,
    "travel_speed_mm_s": 30.0,
    "arc_spacing_nozzle_ratio": 0.95,
    "wall_overlap_mm": 0.2,
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
CHOICES = {"print_order": ("layer_tail", "slicer"), "next_layer_pattern": ("slicer", "hilbert"), "overhang_mode": ("arc", "wave"),
           "wave_pattern": ("smart", "zigzag", "monotonic")}
CONFIG_KEYS = ("nozzle_diameter", "filament_diameter", "outer_wall_line_width",
               "line_width", "layer_height", "filament_flow_ratio", "use_volumetric_e",
               "filament_max_volumetric_speed")
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
        elif isinstance(DEFAULTS[key], str):
            if type(value) is not str or value not in CHOICES[key]:
                raise ValueError(key + " must be one of: " + ", ".join(CHOICES[key]) + ".")
        elif isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
            raise ValueError(key + " must be a finite number.")
        elif value < 0:
            raise ValueError(key + " must not be negative.")
    for key in ("arc_speed_mm_s", "minimum_arc_speed_mm_s", "travel_speed_mm_s",
                "arc_spacing_nozzle_ratio", "max_radius_mm", "flow_multiplier",
                "minimum_arc_time_s", "max_edge_gap_mm", "retract_speed_mm_s",
                "wave_speed_mm_s", "wave_flow_mm3_per_mm", "wave_travel_speed_mm_s"):
        if result[key] <= 0:
            raise ValueError(key + " must be greater than 0.")
    if result["minimum_arc_speed_mm_s"] > result["arc_speed_mm_s"]:
        raise ValueError("Minimum arc speed exceeds maximum arc speed.")
    for key in ("arc_spacing_nozzle_ratio", "wave_spacing_nozzle_ratio"):
        if not 0.1 <= result[key] <= 1.5:
            raise ValueError(key + " must be between 0.1 and 1.5.")
    if result["wave_line_spacing_mm"] and not 0.05 <= result["wave_line_spacing_mm"] <= 1.5:
        raise ValueError("wave_line_spacing_mm must be 0 (use the ratio) or between 0.05 and 1.5.")
    if not 0 <= result["wave_fan_percent"] <= 100:
        raise ValueError("wave_fan_percent must be between 0 and 100.")
    if result["wave_temperature_c"] and not 100 <= result["wave_temperature_c"] <= 400:
        raise ValueError("wave_temperature_c must be 0 (off) or between 100 and 400.")
    if not 10 <= result["wave_corner_angle_deg"] <= 179:
        raise ValueError("wave_corner_angle_deg must be between 10 and 179.")
    if int(result["wave_max_iterations"]) != result["wave_max_iterations"]:
        raise ValueError("wave_max_iterations must be a whole number.")
    if result["wave_corner_taper"] and not 0 < result["wave_corner_spacing_mm"]:
        raise ValueError("wave_corner_spacing_mm must be greater than 0 when the corner taper is on.")
    for key in ("wave_min_time_s", "wave_min_layer_time_s"):
        if result[key] > 600:
            raise ValueError(key + " must not exceed 600.")
    for key, top in (("wave_floor_layers", 20), ("wave_floor_hilbert_layers", 20), ("wave_floor_speed_ramp", 64)):
        if int(result[key]) != result[key] or result[key] > top:
            raise ValueError(f"{key} must be a whole number from 0 to {top}.")
    for key in ("wave_perimeter_speed_mm_s", "wave_floor_print_speed_mm_s", "wave_floor_perimeter_speed_mm_s"):
        if result[key] > 1000:
            raise ValueError(key + " must not exceed 1000.")
    for key in ("wave_floor_fan_percent", "wave_floor_aux_fan_percent", "wave_aux_fan_percent"):
        if result[key] > 100:
            raise ValueError(key + " must be between 0 and 100.")
    if not 1 <= result["wave_floor_hilbert_density_percent"] <= 100:
        raise ValueError("wave_floor_hilbert_density_percent must be between 1 and 100.")
    if result["wave_end_retract_mm"] > 10:
        raise ValueError("wave_end_retract_mm must not exceed 10.")
    if not 50 <= result["minimum_coverage_percent"] <= 100:
        raise ValueError("minimum_coverage_percent must be between 50 and 100.")
    if not 16 <= result["points_per_circle"] <= 80 or int(result["points_per_circle"]) != result["points_per_circle"]:
        raise ValueError("points_per_circle must be an integer from 16 to 80.")
    if not 1 <= result["max_centers"] <= 10000 or int(result["max_centers"]) != result["max_centers"]:
        raise ValueError("max_centers must be an integer from 1 to 10000.")
    if result["z_min_mm"] > result["z_max_mm"]:
        raise ValueError("z_min_mm exceeds z_max_mm.")
    return result

def scalar(value, key, tool_index=0):
    if isinstance(value, (list, tuple)):
        if len(value) == 1:
            value = value[0]
        elif 0 <= tool_index < len(value):
            value = value[tool_index]
        else:
            raise UnsupportedGCode(f"No {key} value for physical tool T{tool_index}.")
    if isinstance(value, str):
        value = value.strip()
        if value.startswith("[") and value.endswith("]"):
            value = value[1:-1].strip()
        parts = [part.strip().strip('[]"') for part in re.split(r"[;,]", value)]
        if len(parts) > 1:
            if not 0 <= tool_index < len(parts):
                raise UnsupportedGCode(f"No {key} value for physical tool T{tool_index}.")
            value = parts[tool_index]
        else:
            value = parts[0]
        if value.endswith("%"):
            return ("percent", float(value[:-1]))
    try:
        value = float(value)
    except (ValueError, TypeError):
        raise UnsupportedGCode("Missing or invalid print setting: " + key)
    if not math.isfinite(value):
        raise UnsupportedGCode("Invalid print setting: " + key)
    return value

def printer_settings(lines, resolved=None, tool_index=0):
    raw = {}
    for line in lines:
        match = re.match(r"^;\s*(\w+)\s*=\s*(.*?)\s*$", line)
        if match and match[1] in CONFIG_KEYS:
            raw[match[1]] = match[2]
    raw.update({k: v for k, v in (resolved or {}).items() if v is not None})
    result = {}
    for key in ("nozzle_diameter", "filament_diameter", "layer_height"):
        result[key] = scalar(raw.get(key), key, tool_index)
        if not isinstance(result[key], float) or result[key] <= 0:
            raise UnsupportedGCode(key + " must be positive.")
    width = scalar(raw.get("outer_wall_line_width", raw.get("line_width", result["nozzle_diameter"])), "outer_wall_line_width", tool_index)
    if isinstance(width, tuple):
        width = result["layer_height"] * width[1] / 100
    if width == 0:
        width = result["nozzle_diameter"] * 1.125
    result["outer_wall_line_width"] = width
    flow = scalar(raw.get("filament_flow_ratio", 1), "filament_flow_ratio", tool_index)
    if not isinstance(flow, float) or flow <= 0:
        raise UnsupportedGCode("Invalid filament_flow_ratio.")
    result["filament_flow_ratio"] = flow
    try:
        cap = scalar(raw.get("filament_max_volumetric_speed", 0), "filament_max_volumetric_speed", tool_index)
    except UnsupportedGCode:
        cap = 0.0
    result["max_volumetric_speed"] = cap if isinstance(cap, float) and cap > 0 else 0.0
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
    firmware_retracted: bool = False
    tool: int = 0
    modal: tuple = ()

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
    # Bambu inserts T1000/T255 as virtual markers; T0 in that stream is not
    # a physical multi-tool change. Ordinary Orca T0/T1 commands are physical.
    has_bambu_virtual_markers = any(command(line)[0] in ("T255", "T1000") for line in lines)
    has_nonzero_physical_tool = any(command(line)[0].startswith("T")
                                    and command(line)[0][1:].isdigit()
                                    and int(command(line)[0][1:]) not in (0, 255, 1000)
                                    for line in lines)
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
        elif cmd in ("G10", "G11"):
            if words:
                raise UnsupportedGCode(cmd + " with parameters is not supported; expected firmware retract/unretract.")
            # Orca emits parameterless G10/G11 for firmware retract. Track the
            # state independently from E-based retracts because only G11 clears it.
            state.firmware_retracted = cmd == "G10"
        elif cmd in ("G60", "G61", "G90.1", "G18", "G19", "G68", "G69"):
            raise UnsupportedGCode("Unsupported state command: " + cmd)
        elif cmd.startswith("T") and cmd[1:].isdigit():
            tool = int(cmd[1:])
            if tool in (255, 1000) or (has_bambu_virtual_markers and not has_nonzero_physical_tool and tool == 0):
                continue
            state.tool = tool
        elif cmd in ("M204", "M104", "M109", "M106", "M107"):
            # Immutable snapshots let relocated blocks restore the fan, active
            # tool's temperature and acceleration expected at each location.
            modal = dict(state.modal)
            if cmd == "M204" and words:
                modal["acceleration"] = "M204 " + " ".join(f"{k}{v:g}" for k, v in sorted(words.items())) + "\n"
            elif cmd in ("M104", "M109") and "S" in words:
                tool = int(words.get("T", state.tool))
                modal[f"temperature:{tool}"] = f"M104 T{tool} S{words['S']:g}\n"
            elif cmd in ("M106", "M107"):
                channel = int(words.get("P", 0))
                speed = words.get("S", 255) if cmd == "M106" else 0
                modal[f"fan:{channel}"] = f"M106 P{channel} S{speed:g}\n"
            state.modal = tuple(sorted(modal.items()))
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
        raise UnsupportedGCode(f"Requires G90 and relative extrusion (M83); at G-code line {move.index + 1} G90 is {'on' if a.absolute_xyz else 'off'} and M83 is {'on' if a.relative_e else 'off'}.")
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

def anchor_arc_paths(paths, support, arc_width, wall_width):
    """Order extrusion paths so every new arc starts on printed material."""
    pending = [path for path in paths if not path.is_empty and path.length > 1e-5]
    if not pending or support.is_empty:
        return None
    printed = support.buffer(wall_width * 0.5)
    ordered = []
    tolerance = max(0.01, arc_width * 0.05)
    while pending:
        best = None
        for index, path in enumerate(pending):
            coords = list(path.coords)
            start, end = Point(coords[0]), Point(coords[-1])
            start_gap, end_gap = start.distance(printed), end.distance(printed)
            if best is None or start_gap < best[0]:
                best = (start_gap, index, False)
            if end_gap < best[0]:
                best = (end_gap, index, True)
        gap, index, reverse = best
        if gap > arc_width * 0.5 + tolerance:
            return None
        path = pending.pop(index)
        if reverse:
            path = LineString(list(path.coords)[::-1])
        ordered.append(path)
        printed = unary_union((printed, path.buffer(arc_width * 0.5)))
    return ordered

def bridge_region(segments, current, wall_width, arc_width, wall_overlap):
    """Expand bridge material toward every current-layer wall for anchoring."""
    strokes = [line.buffer(wall_width * 0.6)
               for line in segments if line is not None and not line.is_empty]
    if not strokes:
        return GeometryCollection()
    region = unary_union(strokes).buffer(wall_overlap)
    clearance = max(0.0, (wall_width + arc_width) * 0.5 - wall_overlap)
    # At positive anchoring, the buffered bridge region may reach inner wall
    # rings as far as the configured distance. Keep the cap at the full wall
    # footprint so the arcs cannot wander outside the printed model outline.
    wall_limit = current.buffer(wall_width * 0.5) if wall_overlap >= (wall_width + arc_width) * 0.5 \
        else current.buffer(-clearance)
    return region.intersection(wall_limit)

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
    arc_width = params["ArcWidth"]
    anchored = anchor_arc_paths(lines, support, arc_width, printer["outer_wall_line_width"])
    if anchored is None:
        return None
    return anchored, coverage

def _parts(geom, kind):
    return [g for g in shapely.get_parts(geom) if g.geom_type == kind and not g.is_empty]

def _lines(geom):
    """Coordinate lists of every LineString in a geometry (clipper intersection_pl)."""
    return [list(g.coords) for g in _parts(geom, "LineString") if len(g.coords) >= 2]

def _simplify(line, tolerance):
    return list(LineString(line).simplify(tolerance, preserve_topology=False).coords)

def _path_length(line):
    return sum(math.dist(a, b) for a, b in zip(line, line[1:]))

def reconnect_polylines(polylines, limit):
    """Greedily chain polylines whose end points are closer than limit (WaveOverhangs detail::reconnect_polylines)."""
    chains = [list(p) for p in polylines]
    alive = [bool(p) for p in chains]
    close = lambda p, q: math.dist(p, q) ** 2 < limit * limit
    changed = True
    while changed:
        changed = False
        for i in range(len(chains)):
            if not alive[i]:
                continue
            for j in range(i + 1, len(chains)):
                if not alive[j]:
                    continue
                base, nxt = chains[i], chains[j]
                if close(base[-1], nxt[0]):
                    base.extend(nxt)
                elif close(base[-1], nxt[-1]):
                    base.extend(reversed(nxt))
                elif close(base[0], nxt[-1]):
                    chains[i] = nxt + base
                elif close(base[0], nxt[0]):
                    chains[i] = base[::-1] + nxt
                else:
                    continue
                alive[j] = False
                changed = True
    return [c for c, ok in zip(chains, alive) if ok]

def detect_overhang_corners(geom, angle_rad):
    """Convex vertices whose interior angle is below the threshold."""
    corners = []
    for poly in polygons(geom):
        poly = shapely.geometry.polygon.orient(poly, 1.0)
        rings = [(list(poly.exterior.coords)[:-1], True)] + [(list(r.coords)[:-1], False) for r in poly.interiors]
        for pts, ccw in rings:
            n = len(pts)
            if n < 3:
                continue
            for i in range(n):
                a, b, c = pts[i - 1], pts[i], pts[(i + 1) % n]
                v1, v2 = (b[0] - a[0], b[1] - a[1]), (c[0] - b[0], c[1] - b[1])
                if v1[0] ** 2 + v1[1] ** 2 < 1e-12 or v2[0] ** 2 + v2[1] ** 2 < 1e-12:
                    continue
                turn = math.atan2(v1[0] * v2[1] - v1[1] * v2[0], v1[0] * v2[0] + v1[1] * v2[1])
                if (turn > 0 if ccw else turn < 0) and math.pi - abs(turn) < angle_rad:
                    corners.append(b)
    return corners

def corner_influence(corners, radius):
    """Union of 16-sided disks around each corner: the reinforcement zone mask."""
    if not corners or radius <= 0:
        return GeometryCollection()
    disks = [Polygon([(x + math.cos(2 * math.pi * k / 16) * radius, y + math.sin(2 * math.pi * k / 16) * radius)
                      for k in range(16)]) for x, y in corners]
    return unary_union(disks)

def _boundary_points(poly):
    return list(poly.exterior.coords)[:-1] + [p for r in poly.interiors for p in list(r.coords)[:-1]]

def _closest_boundary_pair(a, b, container):
    best = None
    for src_poly, other, src_is_a in ((a, b, True), (b, a, False)):
        for src in _boundary_points(src_poly):
            projected = nearest_points(other.boundary, Point(src))[0]
            dist = math.dist(src, (projected.x, projected.y))
            if best is not None and dist >= best[0]:
                continue
            mid = Point((src[0] + projected.x) / 2, (src[1] + projected.y) / 2)
            if not container.covers(mid):
                continue
            pair = (src, (projected.x, projected.y)) if src_is_a else ((projected.x, projected.y), src)
            best = (dist, pair[0], pair[1])
    return best

def _slit(a, b, extension, half_width):
    length = math.dist(a, b)
    if length <= 0:
        return None
    dx, dy = (b[0] - a[0]) / length, (b[1] - a[1]) / length
    nx, ny = -dy * half_width, dx * half_width
    s = (a[0] - dx * extension, a[1] - dy * extension)
    e = (b[0] + dx * extension, b[1] + dy * extension)
    return Polygon([(s[0] + nx, s[1] + ny), (e[0] + nx, e[1] + ny), (e[0] - nx, e[1] - ny), (s[0] - nx, s[1] - ny)])

def _hole_count(geom):
    return sum(len(p.interiors) for p in polygons(geom))

def _effective_slit(cover, a, b, extension, spacing):
    """A slit about one line spacing wide that really splits the cover (or opens a hole)."""
    half = spacing / 2 + 1e-6
    for _ in range(6):
        slit = _slit(a, b, extension, half)
        if slit is not None and slit.is_valid:
            split = cover.difference(slit)
            if len(polygons(split)) != 1 or _hole_count(split) != len(cover.interiors):
                return slit
        half = max(half + 1e-6, half * 2)
    return None

def narrow_split_slits(cover, spacing, minimum_width):
    """Slits that cut the wave cover where a neck is narrower than minimum_width."""
    if minimum_width <= 0:
        return None
    max_gap = minimum_width
    thin = max(1e-6, spacing / 20)
    extension = max(thin, minimum_width)
    holes = len(cover.interiors)
    candidates = []
    def add(pair):
        if pair is None or pair[0] > max_gap:
            return
        slit = _effective_slit(cover, pair[1], pair[2], spacing + extension, spacing)
        if slit is not None:
            candidates.append((pair[0], ((pair[1][0] + pair[2][0]) / 2, (pair[1][1] + pair[2][1]) / 2), slit))
    for fraction in (0.25, 0.5, 0.75, 1.0):
        inset = cover.buffer(-max(1e-6, fraction * spacing), join_style="round")
        parts = polygons(inset)
        count_changed, hole_changed = len(parts) > 1, _hole_count(inset) != holes
        if not count_changed and not hole_changed:
            continue
        if count_changed:
            for i in range(len(parts)):
                for j in range(i + 1, len(parts)):
                    add(_closest_boundary_pair(parts[i], parts[j], cover))
        if hole_changed and cover.interiors:
            outer = Polygon(cover.exterior)
            for i, hole in enumerate(cover.interiors):
                hp = Polygon(hole)
                add(_closest_boundary_pair(outer, hp, cover))
                for other in list(cover.interiors)[i + 1:]:
                    add(_closest_boundary_pair(hp, Polygon(other), cover))
    kept, slits = [], []
    for dist, mid, slit in sorted(candidates, key=lambda c: c[0]):
        if any(math.dist(mid, m) <= spacing / 2 for m in kept):
            continue
        kept.append(mid)
        slits.append(slit)
    return unary_union(slits) if slits else None

def _point_at(line, distance):
    if distance <= 0 or len(line) == 1:
        return line[0]
    walked = 0.0
    for a, b in zip(line, line[1:]):
        seg = math.dist(a, b)
        if seg <= 0:
            continue
        if walked + seg >= distance:
            t = (distance - walked) / seg
            return (a[0] + t * (b[0] - a[0]), a[1] + t * (b[1] - a[1]))
        walked += seg
    return line[-1]

def _foot(line, pt):
    """Segment index and clamped foot point of pt on a polyline."""
    best = None
    for i, (a, b) in enumerate(zip(line, line[1:])):
        dx, dy = b[0] - a[0], b[1] - a[1]
        denom = dx * dx + dy * dy
        t = 0.0 if denom == 0 else max(0.0, min(1.0, ((pt[0] - a[0]) * dx + (pt[1] - a[1]) * dy) / denom))
        foot = (a[0] + t * dx, a[1] + t * dy)
        d = math.dist(pt, foot)
        if best is None or d < best[0]:
            best = (d, i, foot, 0.0 < t < 1.0)
    return best

def _support_score(candidate, supports, reach, prefix):
    if not supports or len(candidate) < 2:
        return -1.0
    length = _path_length(candidate)
    if length <= 0:
        return -1.0
    sample = min(length, max(1e-6, prefix))
    best = -1.0
    for support in reversed(supports):
        if len(support) < 2:
            continue
        score = 0.0
        for dist, weight in ((0.0, 3.0), (0.5 * sample, 2.0), (sample, 1.0)):
            found = _foot(support, _point_at(candidate, dist))
            if found is None:
                continue
            normalized = max(0.0, 1.0 - found[0] / max(1e-6, reach))
            score += weight * (3.0 * normalized + (1.5 if found[3] else 0.2))
        best = max(best, score)
    return best

def wave_smart_order(fronts, reach, prefix):
    """Smart pattern: flip each front to start nearest the paths already laid down."""
    laid = []
    for front in fronts:
        if len(front) < 2:
            continue
        if _support_score(front[::-1], laid, reach, prefix) > _support_score(front, laid, reach, prefix):
            front = front[::-1]
        laid.append(front)
    return laid

def wave_zigzag(levels, connector_limit):
    """ZigZag pattern: chain fronts of successive levels into continuous paths."""
    used = [[False] * len(level) for level in levels]
    limit_sq = connector_limit * connector_limit
    region = []
    def append_or_start(front):
        if not region:
            region.append(list(front))
            return
        cur = region[-1]
        d_keep, d_flip = math.dist(cur[-1], front[0]) ** 2, math.dist(cur[-1], front[-1]) ** 2
        if min(d_keep, d_flip) > limit_sq:
            region.append(list(front))
            return
        if d_flip < d_keep:
            front = front[::-1]
        cur.extend(front[1:] if cur[-1] == front[0] else front)
    def follow(level, idx, rev):
        while True:
            used[level][idx] = True
            cur = levels[level][idx]
            if len(cur) < 2:
                return
            append_or_start(cur[::-1] if rev else cur)
            anchor, found = region[-1][-1], None
            for nl in range(level + 1, len(levels)):
                best_idx, best_d, best_rev = None, limit_sq, False
                for ci, cand in enumerate(levels[nl]):
                    if used[nl][ci] or len(cand) < 2:
                        continue
                    d = math.dist(anchor, cand[0]) ** 2
                    if d <= best_d:
                        best_d, best_idx, best_rev = d, ci, False
                    d = math.dist(anchor, cand[-1]) ** 2
                    if d <= best_d:
                        best_d, best_idx, best_rev = d, ci, True
                if best_idx is not None:
                    found = (nl, best_idx, best_rev)
                break
            if found is None:
                return
            level, idx, rev = found
    for li, level in enumerate(levels):
        for fi in range(len(level)):
            if not used[li][fi]:
                follow(li, fi, False)
    return region

def _clean_fronts(next_region, trim, tolerance, reconnect, mask=None):
    fronts = next_region.boundary.intersection(trim)
    if mask is not None:
        fronts = fronts.intersection(mask)
    lines = [_simplify(l, tolerance) for l in _lines(fronts)]
    return reconnect_polylines([l for l in lines if len(l) >= 2], reconnect)

def bridging_unsupported_distance(real_overhang, anchors):
    """Port of detect_bridging_direction's cost: length of overhang edge left floating for the best bridge direction."""
    area = real_overhang.difference(anchors)
    if area.is_empty:
        return 0.0
    floating = area.boundary.difference(anchors.buffer(1e-3))
    edges = [(a, b) for line in _lines(floating) for a, b in zip(line, line[1:]) if math.dist(a, b) > 1e-9]
    if not edges:
        return 0.0
    normals = {}
    for (ax, ay), (bx, by) in edges:
        length = math.hypot(bx - ax, by - ay)
        nx, ny = -(by - ay) / length, (bx - ax) / length
        normals.setdefault(math.ceil(math.atan2(ny, nx) * 1000.0), (nx, ny))
    return min(sum(abs((bx - ax) * nx + (by - ay) * ny) for (ax, ay), (bx, by) in edges) for nx, ny in normals.values())

def should_generate_waves(region, real_overhang, anchors, inset_anchors, cover_area, spacing, instead_of_bridges):
    """Port of should_generate_waves_for_region: False means a plain bridge is good enough."""
    if real_overhang.is_empty:
        return False
    if instead_of_bridges or region.interiors:
        return True
    anchoring = cover_area.buffer(1.1 * spacing, join_style="round").intersection(inset_anchors)
    unbridgeable = real_overhang.difference(anchoring.convex_hull).area if not anchoring.is_empty else real_overhang.area
    return (unbridgeable >= 0.2 * real_overhang.area
            or bridging_unsupported_distance(real_overhang, anchors) >= real_overhang.length * 0.2)

def wave_generate(poly, support, cfg, printer, cancelled):
    """Port of WaveOverhangs::generate (Andersons / Klappe). Returns (paths as point lists, covered geometry) or None."""
    nozzle = printer["nozzle_diameter"]
    spacing = max(1e-6, cfg["wave_line_spacing_mm"] or nozzle * cfg["wave_spacing_nozzle_ratio"])
    width = nozzle
    base = spacing
    overlap = cfg["wave_perimeter_overlap_mm"]
    resolution = 0.0125
    anchors_size = min(3.0, base * 2)
    seed_expansion = max(1e-6, base / 10)
    connector = max(spacing, width) + overlap
    growth = cfg["wave_min_new_area_mm2"] if cfg["wave_min_new_area_mm2"] > 0 else 0.05 * spacing * spacing
    corner_spacing = cfg["wave_corner_spacing_mm"]
    taper = cfg["wave_corner_taper"] and 0 < corner_spacing < spacing and cfg["wave_corner_distance_mm"] > 0
    substeps = min(8, max(2, round(spacing / corner_spacing))) if taper else 1
    step = max(corner_spacing, spacing / substeps) if taper else spacing
    angle = math.radians(max(10.0, min(179.0, cfg["wave_corner_angle_deg"])))
    pattern = cfg["wave_pattern"]
    max_iter = int(cfg["wave_max_iterations"])

    lower = support
    overhangs = poly.difference(lower)
    if overhangs.is_empty:
        return None
    anchors = poly.intersection(lower)
    inset_anchors = anchors.difference(overhangs.buffer(anchors_size + 0.1 * width, join_style="bevel"))
    inset_area = poly.difference(inset_anchors)
    out_paths, filled = [], []
    for overhang in polygons(unary_union(polygons(inset_area))):
        if cancelled():
            raise Cancelled("Cancelled.")
        if cfg["wave_min_length_mm"] > 0 and overhang.exterior.length < cfg["wave_min_length_mm"]:
            continue
        cover_area = overhang.buffer(overlap, join_style="round")
        influence = GeometryCollection()
        if taper:
            influence = corner_influence(detect_overhang_corners(overhang, angle), cfg["wave_corner_distance_mm"])
        if cover_area.intersection(overhangs).is_empty:
            continue
        if not should_generate_waves(overhang, cover_area.intersection(overhangs), anchors, inset_anchors,
                                     cover_area, base, cfg["wave_instead_of_bridges"]):
            continue
        region_paths = []
        for cover in polygons(unary_union(polygons(cover_area))):
            slits = narrow_split_slits(cover, spacing, cfg["wave_min_width_mm"])
            splits = polygons(cover.difference(slits)) if slits is not None else [cover]
            splits = polygons(unary_union(splits))
            anchoring = cover.buffer(1.1 * base, join_style="round").intersection(inset_anchors)
            if anchoring.is_empty:
                anchoring = cover.buffer(1.1 * base, join_style="round").intersection(anchors)
            if anchoring.is_empty:
                anchoring = cover.buffer(1.1 * base, join_style="round").intersection(lower)
            if anchoring.is_empty:
                continue
            # wave_seeds: the anchoring outline (grown a little) clipped to the cover; fallback is the cover edge inside it.
            grown_anchor = anchoring.buffer(seed_expansion, join_style="round")
            base_seeds = grown_anchor.boundary.intersection(cover)
            if not _lines(base_seeds):
                base_seeds = cover.boundary.intersection(grown_anchor)
            if base_seeds.is_empty:
                continue
            for split in splits:
                seeds = base_seeds.intersection(split)
                if seeds.is_empty:
                    continue
                trim = split.buffer(-width / 2, join_style="round")
                if trim.is_empty:
                    trim = split.buffer(-0.1 * base, join_style="round")
                if trim.is_empty:
                    trim = split
                accumulated = seeds.buffer(seed_expansion, cap_style="round").intersection(split)
                if accumulated.is_empty:
                    continue
                levels, area, iteration = [], accumulated.area, 0
                taper_active = taper and not influence.is_empty and not influence.intersection(split).is_empty
                while True:
                    if cancelled():
                        raise Cancelled("Cancelled.")
                    if max_iter > 0 and iteration >= max_iter:
                        break
                    iteration += 1
                    if taper_active:
                        for sub in range(1, substeps):
                            grown = accumulated.buffer(sub * step, join_style="round").intersection(split)
                            if grown.is_empty:
                                continue
                            fronts = _clean_fronts(grown, trim, min(0.05 * step, resolution), step, influence)
                            if fronts:
                                levels.append(fronts)
                    next_region = accumulated.buffer(spacing, join_style="round").intersection(split)
                    if next_region.is_empty or next_region.area <= area + growth:
                        break
                    fronts = _clean_fronts(next_region, trim, min(0.05 * spacing, resolution), spacing)
                    if fronts:
                        levels.append(fronts)
                    accumulated, area = next_region, next_region.area
                if not levels:
                    continue
                if pattern == "zigzag":
                    paths = wave_zigzag(levels, connector)
                elif pattern == "smart":
                    paths = wave_smart_order([f for level in levels for f in level], max(width, connector), max(width, connector / 2))
                else:
                    paths = [f for level in levels for f in level]
                if paths:
                    region_paths.extend(paths)
                    filled.append(accumulated)
        out_paths.extend(region_paths)
    if not out_paths:
        return None
    return out_paths, unary_union(filled).buffer(base / 2).buffer(-base / 2)

def fill_polygon_wave(poly, support, cfg, printer, cancelled):
    """Wave overhang fill. Same return contract as fill_polygon: (ordered paths, coverage %) or None.

    Algorithm: Janis Andersons; Orca C++ port: Dennis Klappe's OrcaSlicer-WaveOverhangs (AGPL-3.0).
    Ported: narrow-neck slit splitting, anchor fallbacks, wavefront propagation with
    min-new-area / max-iterations / min-length, corner taper, reconnect, Smart / ZigZag /
    Monotonic patterns, wave_seeds (with the library's own boundary fallback) and the
    bridge-versus-wave heuristic (wave_instead_of_bridges).
    """
    printed = poly.intersection(support.buffer(printer["outer_wall_line_width"] * 0.05))
    result = wave_generate(poly, support, cfg, printer, cancelled)
    if result is None:
        return None
    paths, _ = result
    lines = [LineString(p).intersection(poly) for p in paths if len(p) >= 2 and _path_length(p) > 1e-5]
    lines = [part for line in lines for part in _parts(line, "LineString")]
    anchored = anchor_arc_paths(lines, support, printer["nozzle_diameter"], printer["outer_wall_line_width"])
    if anchored is None:
        return None
    covered = unary_union([printed] + [line.buffer(printer["nozzle_diameter"] / 2) for line in anchored]).intersection(poly)
    coverage = 100 * covered.area / poly.area
    if coverage + 1e-6 < cfg["minimum_coverage_percent"]:
        return None
    return anchored, coverage


def fan_override(lines, index, percent, auxiliary=False):
    """Override exactly the fan channel used by the original G-code."""
    for text in reversed(lines[:index]):
        cmd, words = command(text)
        channel = int(words.get("P", 0))
        if cmd not in ("M106", "M107") or (channel != 2 if auxiliary else channel not in (0, 1)):
            continue
        prefix = f"M106 P{channel}" if "P" in words else "M106"
        old = words.get("S", 255) if cmd == "M106" else 0
        return [f"{prefix} S{round(percent * 2.55)}\n"], [f"{prefix} S{old:g}\n"]
    prefix = "M106 P2" if auxiliary else "M106"
    return [f"{prefix} S{round(percent * 2.55)}\n"], [prefix + " S0\n"]


def wave_wrappers(lines, index, arcs, cfg, state=None, printer=None):
    """G-code run before and after waves; never borrow another tool's temperature."""
    pre, post = [], []
    for auxiliary in (False, True):
        if cfg["wave_aux_fan_override" if auxiliary else "wave_fan_override"]:
            begin, end = fan_override(lines, index, cfg["wave_aux_fan_percent" if auxiliary else "wave_fan_percent"], auxiliary)
            pre.extend(begin)
            post.extend(end)
    if cfg["wave_temperature_c"] and state is not None:
        old = dict(state.modal).get(f"temperature:{state.tool}")
        if old:
            pre.append(f"M104 T{state.tool} S{cfg['wave_temperature_c']:g}\n")
            post.append(old)
    speed = cfg["wave_speed_mm_s"]
    if printer and printer.get("max_volumetric_speed"):
        speed = min(speed, printer["max_volumetric_speed"] /
                    (cfg["wave_flow_mm3_per_mm"] * printer["filament_flow_ratio"]))
    spent = sum(arc.length for arc in arcs) / speed
    if spent < cfg["wave_min_time_s"]:
        post.insert(0, f"G4 P{round((cfg['wave_min_time_s'] - spent) * 1000)}\n")
    return pre, post

# Commands that may sit inside a block the plugin edits. M204 is Orca's acceleration change; G17 selects the
# XY plane before Orca's spiral Z lift (a G3 with Z), which the replaced block does not need.
KEPT_COMMANDS = ("", "G0", "G1", "G2", "G3", "M73", "M204", "G17")

WALL_ROLES = ("outer wall", "inner wall", "overhang wall")
SOLID_ROLES = ("solid infill", "internal solid infill", "bottom surface")

def fan_wrappers(lines, index, cfg):
    """Floor-layer fan overrides with the original fan channels restored."""
    pre, post = [], []
    for auxiliary in (False, True):
        if cfg["wave_floor_aux_fan_override" if auxiliary else "wave_floor_fan_override"]:
            begin, end = fan_override(lines, index, cfg["wave_floor_aux_fan_percent" if auxiliary else "wave_floor_fan_percent"], auxiliary)
            pre.extend(begin)
            post.extend(end)
    return pre, post


def retime_feature(feature, lines, speed_for):
    """Rewrite feed rates of extruding moves. speed_for(move) -> mm/s or None (unchanged). Returns lines or None."""
    if any(command(lines[i])[0] not in KEPT_COMMANDS for i in range(feature.start, feature.end)):
        return None
    if len({m.before.tool for m in feature.moves}) > 1:
        return None
    by_index = {m.index: m for m in feature.moves}
    running = feature.moves[0].before.feed if feature.moves else None
    out, changed = [], False
    for i in range(feature.start, feature.end):
        move = by_index.get(i)
        if move is None:
            out.append(lines[i])
            continue
        speed = speed_for(move) if move.delta_e > 0 else None
        want = speed * 60 if speed else move.after.feed
        reference = move.words["F"] if "F" in move.words else running
        if abs(want - reference) < 1e-6:
            out.append(lines[i])
            running = want
            continue
        body, sep, comment = lines[i].partition(";")
        ending = body[len(body.rstrip("\r\n")):] if not sep else ""
        body = re.sub(r"\s[Ff]\s*" + NUMBER, "", body.rstrip("\r\n")).rstrip()
        text = f"{body} F{want:.1f}"
        out.append(text + (" ;" + comment.rstrip("\r\n") if sep else "") + (ending or "\n"))
        running, changed = want, True
    if feature.moves and running is not None and abs(running - feature.moves[-1].after.feed) > 1e-6:
        out.append(f"G1 F{feature.moves[-1].after.feed:.2f}\n")
        changed = True
    return out if changed else None

def is_retracted(state):
    return state.retracted > 1e-5 or state.firmware_retracted

def emit_arcs(arcs, before, after, cfg, printer, restore_state=None, pre=(), post=()):
    if is_retracted(before) or is_retracted(after):
        raise UnsupportedGCode(
            f"Bridge region starts or ends with unrecovered retraction "
            f"(start {before.retracted:.5f} mm, end {after.retracted:.5f} mm). "
            "The region will not be modified.")
    restore = restore_state or after
    if is_retracted(restore):
        raise UnsupportedGCode("Arc insertion point has an unrecovered retraction.")
    wave = cfg["overhang_mode"] == "wave"
    if wave:
        e_per_mm = cfg["wave_flow_mm3_per_mm"] / (math.pi * (printer["filament_diameter"] / 2) ** 2) * printer["filament_flow_ratio"]
    else:
        e_per_mm = (printer["nozzle_diameter"] / printer["filament_diameter"]) ** 2 * cfg["flow_multiplier"] * printer["filament_flow_ratio"]
    travel = (cfg["wave_travel_speed_mm_s"] if wave else cfg["travel_speed_mm_s"]) * 60
    hop = cfg["z_hop_mm"]
    z = before.z
    retract = cfg["wave_end_retract_mm"] if wave and cfg["wave_end_retract_mm"] else cfg["retract_length_mm"]
    retract_feed = cfg["retract_speed_mm_s"] * 60
    out = [MARKER + "BEGIN\n", ";TYPE:Bridge\n", *pre]
    for i, arc in enumerate(arcs):
        coords = list(arc.coords)
        if len(coords) < 2:
            continue
        if wave:
            # Respect the filament's volumetric limit, as WaveOverhangs does (PR 115).
            speed = cfg["wave_speed_mm_s"]
            if printer.get("max_volumetric_speed"):
                speed = min(speed, printer["max_volumetric_speed"] / (cfg["wave_flow_mm3_per_mm"] * printer["filament_flow_ratio"]))
            speed *= 60
        else:
            speed = max(cfg["minimum_arc_speed_mm_s"], min(cfg["arc_speed_mm_s"], arc.length / cfg["minimum_arc_time_s"])) * 60
        if retract:
            out.append(f"G1 E{-retract:.5f} F{retract_feed:.1f}\n")
        x, y = coords[0]
        if hop:
            out.append(f"G1 Z{z + hop:.5f} F{travel:.1f}\n")
        out.append(f"G1 X{x:.5f} Y{y:.5f} F{travel:.1f}\n")
        if hop:
            out.append(f"G1 Z{z:.5f} F{travel:.1f}\n")
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
    if hop:
        out.append(f"G1 Z{z + hop:.5f} F{travel:.1f}\n")
    out.append(f"G1 X{restore.x:.5f} Y{restore.y:.5f} F{travel:.1f}\n")
    if hop:
        out.append(f"G1 Z{z:.5f} F{travel:.1f}\n")
    if retract:
        out.append(f"G1 E{retract:.5f} F{retract_feed:.1f}\n")
    out.extend(post)
    out.append(f"G92 E{restore.e:.7f}\nG1 F{restore.feed:.2f}\n")
    out.append(MARKER + "END\n")
    return out

def hilbert_xy(index, bits):
    """Return integer Hilbert-grid coordinates for a curve index."""
    x = y = 0
    scale = 1
    while scale < (1 << bits):
        rx = 1 & (index // 2)
        ry = 1 & (index ^ rx)
        if ry == 0:
            if rx == 1:
                x, y = scale - 1 - x, scale - 1 - y
            x, y = y, x
        x += scale * rx
        y += scale * ry
        index //= 4
        scale *= 2
    return x, y

def hilbert_paths(poly, spacing, cancelled=lambda: False):
    """Build Hilbert extrusion strokes inside one polygon, splitting at its boundary."""
    min_x, min_y, max_x, max_y = poly.bounds
    side = max(max_x - min_x, max_y - min_y)
    if side <= 1e-6:
        return []
    intervals = max(1, math.ceil(side / max(spacing, 0.05)))
    size, bits = 1, 0
    while size < intervals + 1:
        size *= 2
        bits += 1
    if bits > 9:
        return []
    step = side / max(1, size - 1)
    paths, run, previous = [], [], None
    def flush():
        if len(run) >= 2:
            clipped = LineString(run).intersection(poly)
            if clipped.geom_type == "LineString" and clipped.length > 1e-5:
                paths.append((clipped, step))
            elif hasattr(clipped, "geoms"):
                paths.extend((g, step) for g in clipped.geoms if g.geom_type == "LineString" and g.length > 1e-5)
        run.clear()
    for index in range(size * size):
        if index % 4096 == 0 and cancelled():
            raise Cancelled("Cancelled.")
        gx, gy = hilbert_xy(index, bits)
        point = (min_x + gx * step, min_y + gy * step)
        if poly.covers(Point(point)):
            if previous is not None and index == previous[0] + 1:
                run.append(point)
            else:
                flush()
                run.append(point)
            previous = (index, point)
        else:
            flush()
            previous = None
    flush()
    return paths

def hilbert_feature_replacement(feature, lines, target, cfg, printer, cancelled, feed=None, density=100.0, pre=(), post=()):
    """Replace infill inside the Arc zone and retain original infill outside it."""
    if feature.role not in ("solid infill", "internal solid infill"):
        return None
    moves = feature.moves
    strokes = [(move, segment(move)) for move in moves]
    # A pure-E move (unretract/prime) has no geometry and is not an extrusion stroke.
    if any(move.delta_e > 1e-9 and line is None and ("X" in move.words or "Y" in move.words)
           for move, line in strokes):
        return None
    strokes = [(move, line) for move, line in strokes if line is not None]
    if not strokes or any(move.before.z != strokes[0][0].before.z or move.after.z != strokes[0][0].after.z for move, _ in strokes):
        return None
    if len({move.before.tool for move in moves}) != 1:
        return None
    first, last = strokes[0][0], strokes[-1][0]
    if any(command(lines[i])[0] not in KEPT_COMMANDS for i in range(first.index, last.index + 1)):
        return None
    # Orca writes ;TYPE before the retract/travel/unretract that opens a feature, so
    # moves inside it are legitimately retracted. Only the replaced extrusion
    # span must be unretracted; its approach and departure remain unchanged.
    if any(is_retracted(move.before) or is_retracted(move.after) for move, _ in strokes):
        return None
    width = printer["outer_wall_line_width"]
    footprints = [line.buffer(width * 0.5) for _, line in strokes]
    footprint = unary_union(footprints)
    fill_zone = target.intersection(footprint)
    fill_polys = [poly for poly in polygons(fill_zone) if poly.area >= width * width * 2]
    if not fill_polys:
        return None
    hilbert = []
    for poly in fill_polys:
        hilbert.extend(hilbert_paths(poly, width * 100.0 / density, cancelled))
    if not hilbert:
        return None

    before, after = first.before, last.after
    filament_area = math.pi * (printer["filament_diameter"] / 2) ** 2
    travel = cfg["travel_speed_mm_s"] * 60
    hilbert_feed = feed * 60 if feed else max(60.0, first.after.feed)
    # Keep the original approach and departure, including Z hops, firmware
    # retracts and state commands outside the replaced extrusion span.
    out = list(lines[feature.start:first.index])
    out.extend(["; FEATURE: Internal solid infill (Hilbert)\n; Hilbert replacement in Arc zone\n", *pre])
    out.extend(lines[i] for i in range(first.index, last.index + 1)
               if command(lines[i])[0] in ("M204", "G17"))
    retract, retract_feed = cfg["retract_length_mm"], cfg["retract_speed_mm_s"] * 60
    def jump(x, y):
        if retract:
            out.append(f"G1 E{-retract:.5f} F{retract_feed:.1f}\n")
        out.append(f"G0 X{x:.5f} Y{y:.5f} F{travel:.1f}\n")
        if retract:
            out.append(f"G1 E{retract:.5f} F{retract_feed:.1f}\n")
    # Preserve the sliced infill outside the replacement zone, clipping only
    # the material footprint that the Hilbert paths will cover.
    cut_zone = unary_union(fill_polys).buffer(0.01)
    for move, line in strokes:
        outside = line.difference(cut_zone)
        parts = [outside] if outside.geom_type == "LineString" else [g for g in getattr(outside, "geoms", ()) if g.geom_type == "LineString"]
        for part in parts:
            coords = list(part.coords)
            if len(coords) < 2 or part.length < width:  # slivers left by the cut are not worth a retract and travel
                continue
            jump(*coords[0])
            out.append(f"G1 F{max(60.0, move.before.feed):.1f}\n")
            e_per_mm = move.delta_e / line.length
            for a, b in zip(coords, coords[1:]):
                distance = math.dist(a, b)
                if distance > 1e-8:
                    out.append(f"G1 X{b[0]:.5f} Y{b[1]:.5f} E{distance * e_per_mm:.7f}\n")
    for path, path_spacing in hilbert:
        coords = list(path.coords)
        if len(coords) < 2:
            continue
        jump(*coords[0])
        out.append(f"G1 F{hilbert_feed:.1f}\n")
        e_per_mm = (path_spacing * density / 100.0 * printer["layer_height"] / filament_area) * printer["filament_flow_ratio"]
        for a, b in zip(coords, coords[1:]):
            distance = math.dist(a, b)
            if distance > 1e-8:
                out.append(f"G1 X{b[0]:.5f} Y{b[1]:.5f} E{distance * e_per_mm:.7f}\n")
    jump(after.x, after.y)
    out.extend(post)
    out.extend(lines[i] for i in range(first.index, last.index + 1) if command(lines[i])[0] == "M73")
    out.append(f"G92 E{after.e:.7f}\nG1 F{after.feed:.2f}\n")
    out.extend(lines[last.index + 1:feature.end])
    return out


def relocate_travel(target, cfg):
    """Restore the state needed by an unchanged block without extruding a path."""
    if is_retracted(target) or None in (target.x, target.y, target.z):
        raise UnsupportedGCode("Cannot safely relocate a retracted or unknown-position block.")
    retract = cfg["retract_length_mm"]
    feed = cfg["retract_speed_mm_s"] * 60
    out = [text for _, text in target.modal]
    if retract:
        out.append(f"G1 E{-retract:.7f} F{feed:.2f}\n")
    out.append(f"G0 X{target.x:.5f} Y{target.y:.5f} Z{target.z:.5f} F{cfg['travel_speed_mm_s'] * 60:.2f}\n")
    if retract:
        out.append(f"G1 E{retract:.7f} F{feed:.2f}\n")
    out.append(f"G92 E{target.e:.7f}\nG1 F{target.feed:.2f}\n")
    return out

def schedule_arc_tails(lines, cfg, cancelled):
    """Schedule support with either the compatible layer tail or the slicer order.

    Tool-selection boundaries stay in place, including their purge macros.
    Every moved block retains its original start coordinates, feed and E state.
    """
    # Emitters may return multiple physical lines per item. Parse G92 and
    # its following feed restore separately before capturing any modal state.
    lines = "".join(lines).splitlines(keepends=True)
    features = parse(lines, cancelled)
    moves = {m.index: m for f in features for m in f.moves}
    boundaries = [0]
    for index, line in enumerate(lines):
        cmd, _ = command(line)
        if re.match(r"^;\s*(?:LAYER_CHANGE|CHANGE_LAYER)\s*$", line) or (cmd.startswith("T") and cmd[1:].isdigit()):
            boundaries.append(index)
    boundaries.append(len(lines))
    boundaries = sorted(set(boundaries))
    def window(index):
        return next((a, b) for a, b in zip(boundaries, boundaries[1:]) if a <= index < b)
    groups = {}
    start = None
    for index, line in enumerate(lines):
        if line.strip() == MARKER + "BEGIN":
            start = index
        elif line.strip() == MARKER + "END" and start is not None:
            block_moves = [m for i, m in moves.items() if start <= i <= index]
            if not block_moves:
                raise UnsupportedGCode("Arc block has no movement state.")
            block_moves.sort(key=lambda m: m.index)
            key = window(start)
            if index >= key[1]:
                raise UnsupportedGCode("Arc block crosses a tool or layer boundary.")
            groups.setdefault(key, {"arcs": [], "walls": []})["arcs"].append(
                (start, index + 1, list(lines[start:index + 1]), block_moves[0].before, block_moves[-1].after))
            start = None
    for feature in features:
        if feature.role not in ("overhang wall", "overhang perimeter"):
            continue
        printed = [m for m in feature.moves if segment(m) is not None]
        if not printed:
            continue
        first, last = printed[0], printed[-1]
        key = window(first.index)
        if key not in groups:
            continue
        if last.index >= key[1]:
            raise UnsupportedGCode("Overhang wall crosses a tool or layer boundary.")
        if any(command(lines[i])[0] not in KEPT_COMMANDS
               for i in range(first.index, last.index + 1)):
            raise UnsupportedGCode("Overhang wall contains a state command that cannot be moved.")
        raw = [lines[feature.start]] + list(lines[first.index:last.index + 1])
        groups[key]["walls"].append((first.index, last.index + 1, raw, first.before, last.after))
    edits = []
    for (lo, hi), group in groups.items():
        if cancelled():
            raise Cancelled("Cancelled.")
        if cfg["print_order"] == "slicer":
            last_arc = max(group["arcs"], key=lambda block: block[1])
            insertion, restore = last_arc[1], last_arc[4]
            blocks = [wall for wall in group["walls"] if wall[0] < insertion]
            if not blocks:
                continue
        else:
            blocks = group["arcs"] + group["walls"]
            remaining = [m for i, m in moves.items() if lo <= i < hi and segment(m) is not None
                         and not any(a <= i < b for a, b, *_ in blocks)]
            if remaining:
                anchor = max(remaining, key=lambda m: m.index)
                insertion, restore = anchor.index + 1, anchor.after
            else:
                first_block = min(blocks, key=lambda b: b[0])
                insertion, restore = first_block[0], first_block[3]
        tail = []
        for start, end, raw, before, after in blocks:
            if is_retracted(before) or is_retracted(after) or before.tool != after.tool:
                raise UnsupportedGCode("Cannot move an Arc/overhang block across an active retraction or tool change.")
            if before.tool != restore.tool:
                raise UnsupportedGCode("Arc tail would require an additional material change.")
            # Keep progress and acceleration state at the original location too.
            kept = [line for line in raw if command(line)[0] in ("M73", "M204", "G17")]
            edits.append((start, end, kept + relocate_travel(after, cfg)))
            tail.extend(relocate_travel(before, cfg))
            tail.extend(line for line in raw if command(line)[0] != "M73")
        tail.extend(relocate_travel(restore, cfg))
        edits.append((insertion, insertion, tail))
    for start, end, replacement in sorted(edits, key=lambda e: (e[0], e[1]), reverse=True):
        lines[start:end] = replacement
    return lines


def floor_speed(cfg, k, override, original):
    """Speed (mm/s) for floor layer k >= 1, ramping linearly back to `original`; None = unchanged."""
    if not override:
        return None
    m = min(cfg["wave_floor_speed_ramp"], cfg["wave_floor_layers"])
    t = min(1.0, (k - 1) / (m - 1)) if m > 1 else 0.0
    return min(original, override + (original - override) * t)

def move_time(move):
    line = segment(move)
    a, b = move.before, move.after
    if line is not None:
        length = line.length
    elif None not in (a.x, a.y, b.x, b.y):
        length = math.dist((a.x, a.y), (b.x, b.y))
    else:
        return 0.0
    return length / max(b.feed / 60, 1e-6)

RE_M73_REMAINING = re.compile(r"^(M73\s+P(\d+)\s+R)(\d+)")
RE_TIME_HEADER = re.compile(r"^(;\s*model printing time:\s*)([0-9hms ]+?)(;\s*total estimated time:\s*)([0-9hms ]+?)\s*$")

def move_seconds(lines):
    """Seconds per line from length / modal feed, plus G4 dwells. Only differences are used."""
    out, x, y, feed = [], 0.0, 0.0, 6000.0
    for line in lines:
        seconds = 0.0
        code = line.split(";")[0]
        if re.match(r"G[0-3]\b", code):
            words = {k: float(v) for k, v in re.findall(r"([XYF])(-?[0-9.]+)", code)}
            feed = words.get("F", feed)
            nx, ny = words.get("X", x), words.get("Y", y)
            # shortcut: G2/G3 count as their chord, close enough for a time difference
            seconds = math.hypot(nx - x, ny - y) / (feed / 60.0) if feed > 0 else 0.0
            x, y = nx, ny
        elif re.match(r"G4\b", code):
            dwell = re.search(r"P([0-9.]+)", code)
            seconds = float(dwell.group(1)) / 1000.0 if dwell else 0.0
        out.append(seconds)
    return out

def format_duration(seconds):
    seconds = max(0, int(round(seconds)))
    h, rest = divmod(seconds, 3600)
    m, sec = divmod(rest, 60)
    return (f"{h}h " if h else "") + (f"{m}m " if h or m else "") + f"{sec}s"

def parse_duration(text):
    return float(sum(int(n) * {"h": 3600, "m": 60, "s": 1}[u] for n, u in re.findall(r"(\d+)([hms])", text)))

def update_time_estimates(old_lines, new_lines):
    """Shift M73 remaining-time lines and the header estimate by the time the edit adds or removes.

    Orca estimated the time before post-processing and the plugin docs do not say it is redone.
    Edits new_lines in place and returns the change in seconds. The k-th M73 of the new text is
    matched to the k-th M73 of the old text and shifted by how much more (or less) time follows it.
    """
    old_time, new_time = move_seconds(old_lines), move_seconds(new_lines)
    total = sum(new_time) - sum(old_time)
    if abs(total) < 0.5:
        return 0.0
    # Pair M73 lines by progress percent (a replaced block may swallow one), in order.
    old_by_percent = {}
    for j, line in enumerate(old_lines):
        match = RE_M73_REMAINING.match(line)
        if match:
            old_by_percent.setdefault(match.group(2), []).append(j)
    old_after = [0.0] * (len(old_time) + 1)
    new_after = [0.0] * (len(new_time) + 1)
    for k in range(len(old_time) - 1, -1, -1):
        old_after[k] = old_after[k + 1] + old_time[k]
    for k in range(len(new_time) - 1, -1, -1):
        new_after[k] = new_after[k + 1] + new_time[k]
    for i, line in enumerate(new_lines):
        match = RE_M73_REMAINING.match(line)
        if match and old_by_percent.get(match.group(2)):
            j = old_by_percent[match.group(2)].pop(0)
            minutes = max(0, round(int(match.group(3)) + (new_after[i] - old_after[j]) / 60.0))
            new_lines[i] = f"{match.group(1)}{minutes}" + line[match.end():]
    for i, line in enumerate(new_lines[:300]):
        body = line.rstrip("\r\n")
        match = RE_TIME_HEADER.match(body)
        if match:
            model = format_duration(parse_duration(match.group(2)) + total)
            whole = format_duration(parse_duration(match.group(4)) + total)
            new_lines[i] = f"{match.group(1)}{model}{match.group(3)}{whole}" + line[len(body):]
            break
    return total

BED_TEMP_KEYS = {"cool plate": "cool_plate_temp", "engineering plate": "eng_plate_temp", "textured pei plate": "textured_plate_temp"}

def config_value_reader(text):
    block = dict(re.findall(r"^; (\w+) = (.*)$", text, re.M))
    return lambda key: block.get(key, "").split(",")[0].strip().strip('"')

def gallery_print_profile(text):
    """Wall, shell and infill settings the site shows under "Print profile"."""
    first = config_value_reader(text)
    density = first("sparse_infill_density").rstrip("%")
    fields = [("wall_loops", first("wall_loops")), ("top_shell_layers", first("top_shell_layers")),
              ("bottom_shell_layers", first("bottom_shell_layers")), ("infill_density", density),
              ("infill_pattern", first("sparse_infill_pattern"))]
    return "".join(f" {key}={value}" for key, value in fields if value)

def gallery_build_info(text):
    """Printer, filament and temperatures from Orca's trailing "; key = value" config block, in the site's key names."""
    first = config_value_reader(text)
    bed = first(BED_TEMP_KEYS.get(first("curr_bed_type").lower(), "hot_plate_temp"))
    support = first("enable_support")
    info = [("printer", first("printer_model")), ("filament_type", first("filament_type")),
            ("layer_height", first("layer_height")), ("nozzle_diameter", first("nozzle_diameter")),
            ("nozzle_temp", first("nozzle_temperature")), ("bed_temp", bed),
            ("filament_flow_ratio", first("filament_flow_ratio")),
            ("support_enabled", "true" if support in ("1", "true") else "false" if support else ""),
            ("support_type", first("support_type") if support in ("1", "true") else "")]
    return "".join(f" {key}=\"{value}\"" if " " in value else f" {key}={value}" for key, value in info if value)

def gallery_header(cfg, text=""):
    """Header comments the waveoverhangs.com upload page reads (first 128 KB, lines starting "; WAVE_OVERHANG_")."""
    if cfg["overhang_mode"] != "wave":
        return ""
    fan = cfg["wave_fan_percent"] if cfg["wave_fan_override"] else -1
    fields = [("spacing", cfg["wave_line_spacing_mm"]), ("flow_mm3_per_mm", cfg["wave_flow_mm3_per_mm"]),
              ("speed", cfg["wave_speed_mm_s"]), ("travel", cfg["wave_travel_speed_mm_s"]), ("fan", fan),
              ("floor_layers", cfg["wave_floor_layers"]), ("min_length", cfg["wave_min_length_mm"]),
              ("max_iterations", cfg["wave_max_iterations"]), ("pattern", cfg["wave_pattern"]),
              ("perimeter_overlap", cfg["wave_perimeter_overlap_mm"]), ("minimum_wave_width", cfg["wave_min_width_mm"]),
              ("min_new_area", cfg["wave_min_new_area_mm2"]), ("corner_enable", int(cfg["wave_corner_taper"])),
              ("corner_spacing", cfg["wave_corner_spacing_mm"]), ("corner_taper", cfg["wave_corner_distance_mm"]),
              ("corner_angle", cfg["wave_corner_angle_deg"]), ("end_retract", cfg["wave_end_retract_mm"]),
              ("nozzle_temp_override", int(cfg["wave_temperature_c"])), ("min_wave_time", cfg["wave_min_time_s"]),
              ("min_layer_time", cfg["wave_min_layer_time_s"]),
              ("instead_of_bridges", int(cfg["wave_instead_of_bridges"]))]
    # No wave_overhangs_version on purpose: the site compares it with the fork's releases.
    return ("; WAVE_OVERHANG_BUILD plugin=orca_arc_overhang-" + VERSION + gallery_build_info(text)
            + "\n; WAVE_OVERHANG_CONFIG region=0 "
            + " ".join(f"{key}={value:g}" if isinstance(value, (int, float)) else f"{key}={value}"
                       for key, value in fields) + gallery_print_profile(text) + "\n")

def export_preview(records, cfg):
    """Bounded, simplified snapshot for the local UI; never used to generate G-code."""
    layers, used = [], 0
    limited = False
    for layer, z, tool, mode, paths, contour in records:
        if len(layers) >= 8 or used >= 10000:
            limited = True
            break
        entry = {"layer": layer + 1, "z": round(z, 4), "tool": tool,
                 "mode": mode, "paths": [], "outlines": []}
        for line in paths:
            if len(entry["paths"]) >= 240 or used >= 10000:
                limited = True
                break
            coords = list(line.simplify(0.04, preserve_topology=False).coords)
            if len(coords) > 96:
                coords = [coords[round(i * (len(coords) - 1) / 95)] for i in range(96)]
                limited = True
            if used + len(coords) > 10000:
                limited = True
                break
            entry["paths"].append([[round(x, 4), round(y, 4)] for x, y in coords])
            used += len(coords)
        outline_budget = 1024
        for poly in polygons(contour.simplify(0.04, preserve_topology=True)):
            for ring in [poly.exterior, *poly.interiors]:
                coords = list(ring.coords)
                if len(coords) > outline_budget:
                    limited = True
                    continue
                entry["outlines"].append([[round(x, 4), round(y, 4)] for x, y in coords])
                outline_budget -= len(coords)
        if entry["paths"]:
            layers.append(entry)
    return {"schema": 1, "layers": layers, "limited": limited, "settings": dict(cfg)}


def process_text(text, overrides=None, resolved=None, cancelled=lambda: False):
    cfg = configuration(overrides)
    report = {"replaced_features": 0, "generated_arcs": 0, "skipped_features": 0, "minimum_coverage_percent": None, "bridge_features": 0, "hilbert_features": 0, "retimed_features": 0, "print_order": cfg["print_order"], "skip_reasons": {}}
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
    printer_by_tool = {}
    by_layer = {}
    for feature in features:
        by_layer.setdefault(feature.layer, []).append(feature)
    shapes = {}
    replacements = []
    preview_records = []
    hilbert_targets = {}
    wave_mode = cfg["overhang_mode"] == "wave"
    wave_regions = {}
    layer_delta = {}
    hilbert_layers = cfg["wave_floor_hilbert_layers"] or cfg["wave_floor_layers"] if wave_mode and cfg["wave_floor_use_hilbert"] else 0
    if cfg["next_layer_pattern"] == "hilbert":
        hilbert_layers = max(hilbert_layers, 1)
    for feature in bridges:
        if cancelled():
            raise Cancelled("Cancelled.")
        moves = [m for m in feature.moves if segment(m) is not None]
        if not moves:
            continue
        selected_tools = {m.before.tool for m in moves}
        if len(selected_tools) != 1:
            skipped("Tool change inside bridge feature")
            continue
        tool_index = selected_tools.pop()
        if tool_index not in printer_by_tool:
            printer_by_tool[tool_index] = printer_settings(lines, resolved, tool_index)
        printer = printer_by_tool[tool_index]
        width = printer["outer_wall_line_width"]
        first, last = moves[0], moves[-1]
        z = first.after.z
        if feature.layer < 1 or z is None or not cfg["z_min_mm"] <= z <= cfg["z_max_mm"]:
            continue
        if any(m.before.z != z or m.after.z != z for m in moves):
            raise UnsupportedGCode("Non-planar bridges are not supported.")
        if is_retracted(first.before) or is_retracted(last.after):
            skipped("Bridge starts or ends during firmware retraction")
            continue
        if any(command(lines[i])[0] not in KEPT_COMMANDS for i in range(first.index, last.index + 1)):
            skipped("State command inside bridge region")
            continue
        for layer in (feature.layer - 1, feature.layer):
            shape_key = (layer, tool_index)
            if shape_key not in shapes:
                shapes[shape_key] = layer_shape(by_layer.get(layer, []), width)
        support, current = shapes[(feature.layer - 1, tool_index)], shapes[(feature.layer, tool_index)]
        if support.is_empty or current.is_empty:
            skipped("No closed contour")
            continue
        # Only real extrusion segments form the region; travel moves cannot join islands.
        arc_width = printer["nozzle_diameter"] * cfg["arc_spacing_nozzle_ratio"]
        region = bridge_region([segment(m) for m in moves], current, width, arc_width, cfg["wall_overlap_mm"])
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
            fill = fill_polygon_wave if cfg["overhang_mode"] == "wave" else fill_polygon
            generated = fill(poly, support, cfg, printer, cancelled)
            if generated is None:
                valid = False
                break
            part, coverage = generated
            arcs.extend(part)
            coverages.append(coverage)
        if not valid or not arcs:
            skipped("Insufficient area, anchoring or coverage")
            continue
        pre, post = wave_wrappers(lines, first.index, arcs, cfg, first.before, printer) if cfg["overhang_mode"] == "wave" else ((), ())
        accel = [lines[i] for i in range(first.index, last.index + 1) if command(lines[i])[0] == "M204"]
        pre = [*pre, *accel]
        replacement = emit_arcs(arcs, first.before, last.after, cfg, printer, pre=pre, post=post)
        replacement.extend(lines[i] for i in range(first.index, last.index + 1)
                           if command(lines[i])[0] in ("M73", "M204"))  # the lift's G17 is dropped with the lift itself
        replacements.append((first.index, last.index + 1, replacement))
        if len(preview_records) < 8:
            preview_records.append((feature.layer, z, tool_index, cfg["overhang_mode"], arcs, current))
        for k in range(1, hilbert_layers + 1):
            hilbert_targets.setdefault((feature.layer + k, tool_index), []).append((k, region))
        if wave_mode:
            wave_regions.setdefault((feature.layer, tool_index), []).append(region)
            speed = cfg["wave_speed_mm_s"]
            layer_delta[feature.layer] = layer_delta.get(feature.layer, 0.0) + sum(a.length for a in arcs) / speed \
                - sum(move_time(m) for m in feature.moves)
        report["replaced_features"] += 1
        report["generated_arcs"] += len(arcs)
        previous = report["minimum_coverage_percent"]
        report["minimum_coverage_percent"] = min(coverages + ([previous] if previous is not None else []))
    floor_done = set()
    if hilbert_targets:
        for feature in features:
            if feature.layer < 0:  # start G-code (purge line) uses absolute E
                continue
            feature_tools = {m.before.tool for m in feature.moves if segment(m) is not None}
            if len(feature_tools) != 1:
                continue
            tool_index = feature_tools.pop()
            matching = hilbert_targets.get((feature.layer, tool_index), [])
            if not matching:
                continue
            if tool_index not in printer_by_tool:
                printer_by_tool[tool_index] = printer_settings(lines, resolved, tool_index)
            k = min(k for k, _ in matching)
            feed, pre, post, density = None, (), (), 100.0
            if wave_mode:
                original = feature.moves[0].before.feed / 60 if feature.moves else 0
                feed = floor_speed(cfg, k, cfg["wave_floor_print_speed_mm_s"], original)
                pre, post = fan_wrappers(lines, feature.start, cfg)
                density = cfg["wave_floor_hilbert_density_percent"]
            replacement = hilbert_feature_replacement(
                feature, lines, unary_union([geom for _, geom in matching]), cfg, printer_by_tool[tool_index],
                cancelled, feed, density, pre, post)
            if replacement is not None:
                replacements.append((feature.start, feature.end, replacement))
                floor_done.add(id(feature))
                report["hilbert_features"] += 1
    if wave_regions and (cfg["wave_perimeter_speed_mm_s"] or cfg["wave_floor_print_speed_mm_s"] or cfg["wave_floor_perimeter_speed_mm_s"]):
        bridge_ids = {id(f) for f in bridges}
        for feature in features:
            wall, solid = feature.role in WALL_ROLES, feature.role in SOLID_ROLES
            if not (wall or solid) or id(feature) in floor_done or id(feature) in bridge_ids:
                continue
            feature_tools = {m.before.tool for m in feature.moves}
            if len(feature_tools) != 1:
                continue
            tool_index = feature_tools.pop()
            zones = [(k, unary_union(wave_regions[(feature.layer - k, tool_index)]))
                     for k in range(cfg["wave_floor_layers"] + 1) if (feature.layer - k, tool_index) in wave_regions]
            if not zones:
                continue
            if tool_index not in printer_by_tool:
                printer_by_tool[tool_index] = printer_settings(lines, resolved, tool_index)
            width = printer_by_tool[tool_index]["outer_wall_line_width"]
            zones = [(k, zone.buffer(2 * width if k == 0 else width / 2)) for k, zone in zones]
            def speed_for(move, zones=zones, wall=wall):
                line = segment(move)
                if line is None:
                    return None
                original = move.after.feed / 60
                for k, zone in zones:
                    if zone.intersects(line):
                        if k == 0:
                            override = cfg["wave_perimeter_speed_mm_s"] if wall else 0
                            return min(original, override) if override else None
                        return floor_speed(cfg, k, cfg["wave_floor_perimeter_speed_mm_s" if wall else "wave_floor_print_speed_mm_s"], original)
                return None
            replacement = retime_feature(feature, lines, speed_for)
            if replacement is not None:
                replacements.append((feature.start, feature.end, replacement))
                report["retimed_features"] += 1
    if wave_mode and cfg["wave_min_layer_time_s"]:
        for layer, delta in layer_delta.items():
            layer_features = by_layer[layer]
            short = cfg["wave_min_layer_time_s"] - delta - sum(move_time(m) for f in layer_features for m in f.moves)
            last = layer_features[-1]
            if short > 0 and last.moves and not is_retracted(last.moves[-1].after):
                replacements.append((last.end, last.end, [f"G4 P{round(short * 1000)}\n"]))
    if not replacements:
        return text, report
    # Zero-width arc insertions can be earlier or later than the Bridge
    # feature they replace. Group coincident insertions and apply every edit
    # from the end of the original file toward its beginning.
    insertions, spans = {}, []
    for start, end, replacement in replacements:
        if start == end:
            insertions.setdefault(start, []).extend(replacement)
        else:
            spans.append((start, end, replacement))
    spans.extend((index, index, replacement) for index, replacement in insertions.items())
    for start, end, replacement in sorted(spans, key=lambda item: (item[0], item[1]), reverse=True):
        lines[start:end] = replacement
    try:
        lines = schedule_arc_tails(lines, cfg, cancelled)
    except UnsupportedGCode as error:
        report["skip_reasons"]["Unsafe Arc tail scheduling: " + str(error)] = report["replaced_features"]
        report["skipped_features"] += report["replaced_features"]
        report["replaced_features"] = report["generated_arcs"] = report["hilbert_features"] = report["retimed_features"] = 0
        report["minimum_coverage_percent"] = None
        return text, report
    lines = "".join(lines).splitlines(keepends=True)
    report["time_change_s"] = update_time_estimates(text.splitlines(keepends=True), lines)
    try:
        report["preview"] = export_preview(preview_records, cfg)
        report["preview"]["limited"] |= report["replaced_features"] > len(report["preview"]["layers"])
    except Exception:
        # A presentation failure must not turn a successful G-code export into
        # a failed print export. Do not log geometry or source paths here.
        report["preview_error"] = "Support was generated, but its UI snapshot is unavailable."
    return MARKER + VERSION + "\n" + gallery_header(cfg, text) + "".join(lines), report

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

# WaveOverhangs (Orca fork) setting -> (plugin setting(s), kind). Keys are wave_overhang_<name>.
WAVE_IMPORT = {
    "pattern": ("wave_pattern", "text"),
    "line_spacing": ("wave_line_spacing_mm", "num"),
    "flow_mm3_per_mm": ("wave_flow_mm3_per_mm", "num"),
    "print_speed": ("wave_speed_mm_s", "num"),
    "travel_speed": ("wave_travel_speed_mm_s", "num"),
    "perimeter_speed": ("wave_perimeter_speed_mm_s", "num"),
    "perimeter_overlap": ("wave_perimeter_overlap_mm", "num"),
    "minimum_width": ("wave_min_width_mm", "num"),
    "min_new_area": ("wave_min_new_area_mm2", "num"),
    "min_length": ("wave_min_length_mm", "num"),
    "max_iterations": ("wave_max_iterations", "num"),
    "corner_taper_enable": ("wave_corner_taper", "bool"),
    "line_spacing_corner": ("wave_corner_spacing_mm", "num"),
    "corner_taper_distance": ("wave_corner_distance_mm", "num"),
    "corner_angle_threshold": ("wave_corner_angle_deg", "num"),
    "fan_speed": (("wave_fan_override", "wave_fan_percent"), "fan"),
    "aux_fan_speed": (("wave_aux_fan_override", "wave_aux_fan_percent"), "fan"),
    "nozzle_temp": ("wave_temperature_c", "num"),
    "min_wave_time": ("wave_min_time_s", "num"),
    "min_layer_time": ("wave_min_layer_time_s", "num"),
    "end_retract_length": ("wave_end_retract_mm", "num"),
    "instead_of_bridges": ("wave_instead_of_bridges", "bool"),
    "floor_layers": ("wave_floor_layers", "num"),
    "floor_print_speed": ("wave_floor_print_speed_mm_s", "num"),
    "floor_perimeter_speed": ("wave_floor_perimeter_speed_mm_s", "num"),
    "floor_speed_ramp": ("wave_floor_speed_ramp", "num"),
    "floor_use_hilbert": ("wave_floor_use_hilbert", "bool"),
    "floor_hilbert_layers": ("wave_floor_hilbert_layers", "num"),
    "floor_hilbert_density": ("wave_floor_hilbert_density_percent", "num"),
    "floor_fan_speed": (("wave_floor_fan_override", "wave_floor_fan_percent"), "fan"),
    "floor_aux_fan_speed": (("wave_floor_aux_fan_override", "wave_floor_aux_fan_percent"), "fan"),
}
# WaveOverhangs settings that need no plugin option: min_angle, spacing_mode and seam_mode do nothing in the fork
# (kept for old profiles), debug_gcode only adds comments, and the plugin keeps whatever walls Orca printed.
WAVE_NO_EFFECT = ("min_angle", "spacing_mode", "seam_mode", "debug_gcode", "outer_perimeters")
# Names used by the one-line "WAVE_OVERHANG_CONFIG key=value ..." comment in WaveOverhangs G-code.
WAVE_MARKER_ALIASES = {
    "spacing": "line_spacing", "flow_mm3_per_mm": "flow_mm3_per_mm", "speed": "print_speed", "travel": "travel_speed",
    "fan": "fan_speed", "minimum_wave_width": "minimum_width", "corner_enable": "corner_taper_enable",
    "corner_spacing": "line_spacing_corner", "corner_taper": "corner_taper_distance",
    "corner_angle": "corner_angle_threshold", "end_retract": "end_retract_length", "nozzle_temp_override": "nozzle_temp",
}

def import_wave_profile(text):
    """Read WaveOverhangs settings from G-code comments, a profile/JSON or a gallery config line.

    Returns (plugin settings, names that have no plugin equivalent)."""
    marker, found = {}, {}
    prefixed = set()
    for line in text.splitlines():
        if "WAVE_OVERHANG_CONFIG" in line:
            for key, value in re.findall(r"(\w+)=(\S+)", line):
                marker[WAVE_MARKER_ALIASES.get(key, key)] = value
        for key, value in re.findall(r"wave_overhang_(\w+?)[\"']?\s*[:=]\s*[\"']?([^\s\"',;]+)", line):
            found[key] = value
            prefixed.add(key)
    found = {**marker, **found}  # explicit wave_overhang_ lines beat the one-line summary
    values, ignored = {"overhang_mode": "wave"}, []
    for key, raw in found.items():
        if key not in WAVE_IMPORT:
            if key in prefixed and key not in WAVE_NO_EFFECT:
                ignored.append("wave_overhang_" + key)
            continue
        target, kind = WAVE_IMPORT[key]
        try:
            if kind == "text":
                if raw.lower() not in CHOICES[target]:
                    ignored.append("wave_overhang_" + key)
                    continue
                values[target] = raw.lower()
            elif kind == "bool":
                values[target] = raw.lower() in ("1", "true")
            elif kind == "fan":
                number = float(raw)
                values[target[0]], values[target[1]] = number >= 0, max(0.0, number)
            else:
                values[target] = float(raw)
        except ValueError:
            ignored.append("wave_overhang_" + key)
    return values, ignored

HELP = {
    "wave_pattern": "Order of the wave lines. Smart follows the wavefront, Zigzag joins neighbouring lines into one path (helps against curling at line ends), Monotonic prints every line separately.",
    "wave_line_spacing_mm": "Distance between neighbouring wave lines. 0.35 mm is the usual value for a 0.4 mm nozzle.",
    "wave_flow_mm3_per_mm": "Plastic pushed out per mm of wave line (an absolute volume, not a multiplier).",
    "wave_speed_mm_s": "Print speed of the wave lines. Very slow on purpose so each line cools in the air.",
    "wave_travel_speed_mm_s": "Speed of moves between wave lines.",
    "wave_perimeter_speed_mm_s": "Speed of the walls on the layer that has waves. 0 keeps the slicer's wall speed.",
    "wave_perimeter_overlap_mm": "How far the waves reach under the wall so the wall bonds to them. Raise it if the wall comes loose from the waves.",
    "wave_min_width_mm": "Necks narrower than this split the wave region so the wavefront does not pinch shut.",
    "wave_min_new_area_mm2": "Stop adding wave lines once a new line would cover less than this area.",
    "wave_min_length_mm": "Overhangs with a shorter outline stay normal bridges. 0 = off.",
    "wave_max_iterations": "Most wave lines grown per overhang region. 0 = no limit.",
    "wave_corner_taper": "Add denser lines near sharp overhang corners, which curl first.",
    "wave_corner_spacing_mm": "Line spacing used near corners (smaller than the normal wave line spacing).",
    "wave_corner_distance_mm": "How far from a corner the denser lines reach.",
    "wave_corner_angle_deg": "Corners sharper than this angle get the reinforcement.",
    "wave_fan_override": "Force the part fan to the speed below while printing waves; the previous fan speed is restored afterwards.",
    "wave_fan_percent": "Part fan speed while printing waves.",
    "minimum_area_mm2": "Smallest bridge area to replace, and also the smallest part of it that hangs in the air. Lower it (for example to 1-5) to get waves or arcs on small overhangs; the default 50 skips them.",
    "minimum_overhang_length_mm": "Smallest length of the unsupported edge. Lower it together with the minimum area for small overhangs.",
    "wave_aux_fan_override": "Force the auxiliary fan (M106 P2) while printing waves; the previous speed is restored afterwards.",
    "wave_aux_fan_percent": "Auxiliary fan speed while printing waves.",
    "wave_temperature_c": "Nozzle temperature while printing waves, restored afterwards. 0 = leave unchanged.",
    "wave_min_time_s": "Pause after the waves so they get at least this much cooling time. 0 = off.",
    "wave_min_layer_time_s": "Pause at the end of a layer with waves so the whole layer takes at least this long. 0 = off.",
    "wave_instead_of_bridges": "On: every overhang found gets waves. Off: spans a normal bridge can handle (anchored on both sides, mostly convex) keep Orca's bridge.",
    "wave_end_retract_mm": "Retraction before each jump between wave lines. 0 = use the general Retraction setting.",
    "wave_floor_layers": "Number of layers above the waves that get the floor settings below. Orca decides how many of them are solid; this only changes how they print.",
    "wave_floor_print_speed_mm_s": "Speed of solid infill on the floor layers. 0 = unchanged.",
    "wave_floor_perimeter_speed_mm_s": "Speed of walls on the floor layers. 0 = unchanged.",
    "wave_floor_speed_ramp": "Floor layers over which the two floor speeds ramp back up to normal. 0 = no ramp.",
    "wave_floor_use_hilbert": "Use an experimental Hilbert pattern for eligible solid floor infill above waves; print quality depends on the material and cooling.",
    "wave_floor_hilbert_layers": "How many of the floor layers use Hilbert. 0 = all of them.",
    "wave_floor_hilbert_density_percent": "Fill density of the Hilbert floor. 100 = solid.",
    "wave_floor_fan_override": "Force the part fan on the Hilbert floor layers (a low fan keeps them warm and reduces curl).",
    "wave_floor_fan_percent": "Part fan speed on the Hilbert floor layers.",
    "wave_floor_aux_fan_override": "Force the auxiliary fan (M106 P2) on the Hilbert floor layers.",
    "wave_floor_aux_fan_percent": "Auxiliary fan speed on the Hilbert floor layers.",
    "z_hop_mm": "Lift the nozzle by this much for jumps between arcs or waves. 0 = off.",
}

def config_page(as_tab=False):
    fields = [
        (None, "Arc mode", ""),
        ("arc_speed_mm_s", "Arc speed", "mm/s"),
        ("minimum_arc_speed_mm_s", "Minimum arc speed", "mm/s"),
        ("arc_spacing_nozzle_ratio", "Arc spacing / nozzle diameter", "Factor"),
        ("wall_overlap_mm", "Inner wall overlap", "mm"),
        ("arc_center_offset_mm", "Arc center offset", "mm"),
        ("max_radius_mm", "Maximum radius", "mm"),
        ("flow_multiplier", "Arc flow", "Factor"),
        ("minimum_arc_time_s", "Minimum time per arc", "s"),
        (None, "Wave mode", ""),
        ("wave_pattern", "Wave pattern", "select"),
        ("wave_line_spacing_mm", "Wave line spacing", "mm"),
        ("wave_flow_mm3_per_mm", "Wave flow", "mm3/mm"),
        ("wave_speed_mm_s", "Wave print speed", "mm/s"),
        ("wave_travel_speed_mm_s", "Wave travel speed", "mm/s"),
        ("wave_perimeter_speed_mm_s", "Wave perimeter speed", "mm/s"),
        ("wave_perimeter_overlap_mm", "Wave perimeter overlap", "mm"),
        ("wave_min_width_mm", "Minimum wave width", "mm"),
        ("wave_min_new_area_mm2", "Minimum new area", "mm2"),
        ("wave_min_length_mm", "Minimum overhang length for waves", "mm"),
        ("wave_max_iterations", "Maximum wave lines per region", "Count"),
        ("wave_instead_of_bridges", "Use waves instead of bridges", "bool"),
        ("wave_corner_taper", "Corner reinforcement", "bool"),
        ("wave_corner_spacing_mm", "Corner line spacing", "mm"),
        ("wave_corner_distance_mm", "Corner reinforcement radius", "mm"),
        ("wave_corner_angle_deg", "Corner angle threshold", "deg"),
        ("wave_fan_override", "Wave fan speed override", "bool"),
        ("wave_fan_percent", "Wave fan speed", "%"),
        ("wave_aux_fan_override", "Wave aux fan speed override", "bool"),
        ("wave_aux_fan_percent", "Wave aux fan speed", "%"),
        ("wave_temperature_c", "Wave nozzle temperature (0 = unchanged)", "C"),
        ("wave_min_time_s", "Minimum wave time", "s"),
        ("wave_min_layer_time_s", "Minimum layer time", "s"),
        ("wave_end_retract_mm", "End-of-line retract length", "mm"),
        (None, "Wave floor (layers above the waves)", ""),
        ("wave_floor_layers", "Floor layers", "Layers"),
        ("wave_floor_print_speed_mm_s", "Floor print speed", "mm/s"),
        ("wave_floor_perimeter_speed_mm_s", "Floor perimeter speed", "mm/s"),
        ("wave_floor_speed_ramp", "Floor speed ramp", "Layers"),
        ("wave_floor_use_hilbert", "Floor: Hilbert curve", "bool"),
        ("wave_floor_hilbert_layers", "Floor: Hilbert layers", "Layers"),
        ("wave_floor_hilbert_density_percent", "Floor: Hilbert density", "%"),
        ("wave_floor_fan_override", "Floor: fan speed override", "bool"),
        ("wave_floor_fan_percent", "Floor: fan speed", "%"),
        ("wave_floor_aux_fan_override", "Floor: aux fan speed override", "bool"),
        ("wave_floor_aux_fan_percent", "Floor: aux fan speed", "%"),
        (None, "Both modes", ""),
        ("z_hop_mm", "Z hop between arcs/waves (0 = off)", "mm"),
        ("max_edge_gap_mm", "Maximum edge gap", "mm"),
        ("minimum_area_mm2", "Minimum overhang area", "mm2"),
        ("minimum_overhang_length_mm", "Minimum overhang length", "mm"),
        ("minimum_coverage_percent", "Required area coverage", "%"),
        ("travel_speed_mm_s", "Travel speed", "mm/s"),
        ("retract_length_mm", "Retraction", "mm"),
        ("retract_speed_mm_s", "Retraction speed", "mm/s"),
        ("points_per_circle", "Points per circle", "16-80"),
        ("max_centers", "Maximum number of centers", "Count"),
        ("z_min_mm", "Minimum Z", "mm"),
        ("z_max_mm", "Maximum Z", "mm"),
    ]
    def escape(value):
        return (str(value).replace("&", "&amp;").replace("<", "&lt;")
                .replace(">", "&gt;").replace('"', "&quot;"))
    names = {target if isinstance(target, str) else target[1]: "wave_overhang_" + source
             for source, (target, _) in WAVE_IMPORT.items()}
    quick = {"arc_speed_mm_s", "arc_spacing_nozzle_ratio", "wall_overlap_mm",
             "wave_speed_mm_s", "wave_line_spacing_mm", "wave_flow_mm3_per_mm"}
    groups = {name: [] for name in ("arc_quick", "wave_quick", "anchor_quick", "arc", "wave", "floor", "shared")}
    section = "arc"
    for key, label, unit in fields:
        if key is None:
            section = {"Arc mode": "arc", "Wave mode": "wave", "Wave floor (layers above the waves)": "floor", "Both modes": "shared"}[label]
            continue
        unit = unit.replace("mm3", "mm³").replace("mm2", "mm²")
        if unit == "bool":
            control = f'<input id="{key}" type="checkbox" aria-describedby="help-{key}">'
        elif unit == "select":
            options = "".join(f'<option value="{c}">{c.capitalize()}</option>' for c in CHOICES[key])
            control = f'<select id="{key}" aria-describedby="help-{key}">{options}</select>'
        else:
            step = "1" if isinstance(DEFAULTS[key], int) else "any"
            control = f'<div class="number-control"><input id="{key}" name="{key}" type="number" step="{step}" min="0" required aria-describedby="help-{key}"><span>{unit}</span></div>'
        hint = HELP.get(key, "")
        if key == "arc_speed_mm_s":
            hint = "Upper speed limit. Short arcs can print more slowly to allow cooling."
        elif key == "arc_spacing_nozzle_ratio":
            hint = "Distance between paths as a nozzle factor. 0.5 with a 0.4 mm nozzle means 0.2 mm spacing."
        elif key == "wall_overlap_mm":
            hint = "How far support can reach into the wall region. Can extend across multiple wall lines; 0 adds no overlap."
        row = (f'<div class="field" data-field="{key}"><label for="{key}">{escape(label)}</label>{control}'
               f'<p class="field-help" id="help-{key}">{escape(hint)}</p></div>')
        group = "anchor_quick" if key == "wall_overlap_mm" else section + "_quick" if key in quick else section
        groups[group].append(row)
    # Retain the legacy ratio setting in the expert controls as well: no saved
    # configuration key silently disappears when the UI is simplified.
    groups["wave"].append('<div class="field" data-field="wave_spacing_nozzle_ratio"><label for="wave_spacing_nozzle_ratio">Fallback spacing / nozzle</label><div class="number-control"><input id="wave_spacing_nozzle_ratio" type="number" min="0.1" max="1.5" step="any"><span>factor</span></div><p class="field-help">Used only when Wave line spacing is 0.</p></div>')
    page = UI_TEMPLATE
    for name, rows in groups.items():
        page = page.replace("__" + name.upper() + "__", "".join(rows))
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
    renderReport(report);
    return response.config;
  },
  saveConfig:config=>requestSettings('save',config)
};
"""
    context = ("You are editing global defaults for the active preset. Existing preset overrides take precedence."
               if as_tab else "Settings belong to this Orca plugin configuration. Save your process preset after editing.")
    return (page.replace("__DEFAULTS__", json.dumps(DEFAULTS)).replace("__IMPORT__", json.dumps(WAVE_IMPORT))
            .replace("__ALIASES__", json.dumps(WAVE_MARKER_ALIASES)).replace("__VERSION__", VERSION)
            .replace("__CONTEXT__", context).replace("__BRIDGE__", bridge))



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
                return orca.ExecutionResult.success(message, json.dumps({k: v for k, v in report.items() if k != "preview"}))
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
