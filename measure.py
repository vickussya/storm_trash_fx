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


def storm_track(scene, storm, depsgraph_get=None, max_samples=120):
    """Sample the storm's world XY across the scene frame range.

    Used to work out when the storm passes each object, which is what lets the
    spin accumulate and then hold - a driver is a pure function of `frame` and
    the storm's current position, so it has no memory of its own.

    Steps the scene, which is not free, so only call it when spin is enabled.
    The current frame is restored afterwards.
    """
    f0, f1 = scene.frame_start, scene.frame_end
    if f1 < f0:
        f0, f1 = f1, f0
    step = max(1, int(math.ceil((f1 - f0 + 1) / float(max(1, max_samples)))))
    original = scene.frame_current
    track = []
    try:
        frames = list(range(f0, f1 + 1, step))
        if frames and frames[-1] != f1:
            frames.append(f1)
        for f in frames:
            scene.frame_set(f)
            ob = storm
            if depsgraph_get is not None:
                try:
                    ob = storm.evaluated_get(depsgraph_get())
                except Exception:
                    ob = storm
            p = ob.matrix_world.translation
            track.append((float(f), p.x, p.y))
    finally:
        scene.frame_set(original)
    return track


def pass_window(track, cx, cy, reach):
    """``(first_frame, last_frame)`` the storm spends within ``reach`` of a point.

    ``None`` if it never comes close enough.  Widened to the track's sampling
    step when the storm crosses in a single sample, so a fast pass still gets a
    window to spin over rather than an instant snap.
    """
    if not track:
        return None
    limit = reach * reach
    inside = [f for (f, x, y) in track
              if (x - cx) ** 2 + (y - cy) ** 2 <= limit]
    if not inside:
        return None
    first, last = min(inside), max(inside)
    step = (track[1][0] - track[0][0]) if len(track) > 1 else 1.0
    if last - first < step:
        half = max(step, 1.0) * 0.5
        first, last = first - half, last + half
    return (first, last)
