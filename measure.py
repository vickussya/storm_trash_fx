# -*- coding: utf-8 -*-
"""Reading the scene: object size, resting position, and the storm underside.

Nothing here writes anything.  All measurements come from the *evaluated*
object where possible, so geometry nodes and modifier output are included.
"""

import math

from mathutils import Vector


def world_corners(obj, depsgraph=None):
    """World-space bounding-box corners of the evaluated object.

    Falls back to the original object if evaluation is unavailable.
    """
    if depsgraph is not None:
        try:
            ob_eval = obj.evaluated_get(depsgraph)
            mw = ob_eval.matrix_world
            return [mw @ Vector(c) for c in ob_eval.bound_box]
        except Exception:
            pass
    mw = obj.matrix_world
    return [mw @ Vector(c) for c in obj.bound_box]


def bbox_stats(obj, depsgraph=None):
    """Return ``(center_x, center_y, top_z, size)`` in world space.

    ``size`` is the bounding-box diagonal length - a linear measure of "how big
    is this object".  The diagonal is used instead of the volume because flat
    or single-axis pieces have zero volume and would otherwise all collapse to
    the "lightest possible" end of the weight scale.
    """
    corners = world_corners(obj, depsgraph)
    xs = [c.x for c in corners]
    ys = [c.y for c in corners]
    zs = [c.z for c in corners]
    dx, dy, dz = max(xs) - min(xs), max(ys) - min(ys), max(zs) - min(zs)
    size = math.sqrt(dx * dx + dy * dy + dz * dz)
    if size <= 1e-6:
        d = obj.dimensions
        size = math.sqrt(d.x * d.x + d.y * d.y + d.z * d.z)
    return (
        (max(xs) + min(xs)) * 0.5,
        (max(ys) + min(ys)) * 0.5,
        max(zs),
        max(size, 1e-4),
    )


def storm_bottom_z(props, depsgraph=None):
    """World Z of the storm underside, used for the ceiling."""
    if props.use_manual_bottom:
        return props.storm_bottom_z
    ref = props.storm_bottom_object or props.storm_object
    if ref is not None:
        try:
            return min(c.z for c in world_corners(ref, depsgraph))
        except Exception:
            pass
    return props.storm_bottom_z


def lightness(size, size_min, size_max):
    """How light this object is, relative to the selection: 1.0 .. 0.0.

    Smallest object in the selection -> 1.0, largest -> 0.0.  Log scale,
    because trash sizes span a wide range.  Note the range is relative to the
    current selection, so the same object reacts differently depending on what
    it was applied alongside - that is intended.

    Kept separate from :func:`light_factor` because amplitude and shake speed
    read the same lightness through different curves.
    """
    if size_max <= size_min * 1.0001:
        return 1.0
    lo, hi = math.log(size_min), math.log(size_max)
    t = (hi - math.log(min(max(size, size_min), size_max))) / (hi - lo)
    return max(0.0, min(1.0, t))


def light_factor(lightness_value, min_factor):
    """Map lightness -> amplitude factor in ``[min_factor, 1]``."""
    return min_factor + (1.0 - min_factor) * max(0.0, min(1.0, lightness_value))
