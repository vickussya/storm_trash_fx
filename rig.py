# -*- coding: utf-8 -*-
"""Building the drivers.

The proximity gate reads the STORM's world position through two native
Transform Channel variables, and compares it against the object's resting
position, which is baked into the expression as a constant.

It deliberately does NOT use a Distance (``LOC_DIFF``) variable between the
object and the storm: that makes the object's own transform an input to a
driver on its own transform, which is a dependency cycle.  Blender then breaks
the cycle with stale data, so the rig either freezes or jitters.

Everything built here stays inside Blender's fast simple-expression evaluator
(arithmetic, ``sqrt``, ``max``, ``sin``, ``frame``) - no Python callback per
frame.  Expressions also have to fit Blender's 256-character limit; the gate
alone is ~75 characters and is inlined into every driver.
"""

import math
import random
import zlib

from . import channels

#: The sine pair below peaks at 1.5, so amplitudes are normalised by this to
#: make Shake Amount the actual peak wobble.
_SINE_SUM_PEAK = 1.5


def object_rng(seed, name):
    """Deterministic per-object RNG.

    Keyed on the object's name rather than on iteration order, so re-applying
    reproduces the same phases even though selection order is not stable.
    crc32 is used instead of ``hash()`` because Python randomises string
    hashing between sessions.
    """
    key = zlib.crc32(name.encode("utf-8")) & 0xFFFFFFFF
    return random.Random((int(seed) * 2654435761) ^ key)


def gate_expr(cx, cy, inv_radius):
    """Proximity gate: 1.0 under the storm, 0.0 at the influence radius.

    Squared so it eases off instead of hitting the radius with a hard kink.
    Horizontal distance only - the storm sits above the scene, so measuring in
    3D would mean an object directly underneath never reaches full effect.
    """
    return ("max(0.0,1.0-sqrt((sx-({X:.4f}))**2+(sy-({Y:.4f}))**2)*{K:.8f})**2"
            .format(X=cx, Y=cy, K=inv_radius))


def lift_expr(gate, amplitude):
    """Gate scaled by the weight-scaled, ceiling-capped lift amplitude."""
    return "{G}*{A:.6f}".format(G=gate, A=amplitude)


def shake_expr(gate, amplitude, freq, phase):
    """Gate scaled by two offset sines - cheap pseudo-noise, never in sync."""
    return ("{G}*{S:.6f}*(sin(frame*{F:.5f}+{P:.4f})"
            "+0.5*sin(frame*{F2:.5f}+{P2:.4f}))").format(
        G=gate, S=amplitude, F=freq, P=phase,
        F2=freq * 2.3, P2=phase * 1.7)


def _add_storm_vars(drv, storm):
    """(Re)create the two world-space location variables for the storm."""
    for v in list(drv.variables):
        drv.variables.remove(v)
    for name, channel in (("sx", 'LOC_X'), ("sy", 'LOC_Y')):
        var = drv.variables.new()
        var.name = name
        var.type = 'TRANSFORMS'
        tgt = var.targets[0]
        tgt.id = storm
        tgt.transform_type = channel
        tgt.transform_space = 'WORLD_SPACE'


def _strip_fcurve(fc):
    """Clear anything on the F-curve that would remap the driver's output.

    A generator modifier or a stray keyframe on a driver F-curve overrides the
    raw driver value, so both are cleared.  Removing from a live Blender
    collection reallocates it, which invalidates a snapshot taken with
    ``list()`` - "Keyframe not in F-Curve" - so always remove the *current*
    first element instead.  This is a nicety, not load-bearing: it must never
    be able to abort an Apply, hence the blanket except.
    """
    try:
        while fc.modifiers:
            fc.modifiers.remove(fc.modifiers[0])
    except Exception:
        pass
    try:
        fc.keyframe_points.clear()
    except AttributeError:
        try:
            while fc.keyframe_points:
                fc.keyframe_points.remove(fc.keyframe_points[0])
        except Exception:
            pass
    except Exception:
        pass


def add_driver(obj, data_path, index, storm, expression):
    """Create one scripted driver, replacing whatever was on the channel."""
    channels.remove_driver(obj, data_path, index)
    channels.remove_keyframes(obj, data_path, index)
    fc = obj.driver_add(data_path, index)
    _strip_fcurve(fc)
    fc.mute = False
    drv = fc.driver
    drv.type = 'SCRIPTED'
    drv.use_self = False
    _add_storm_vars(drv, storm)
    drv.expression = expression
    return fc


def shake_axes(props):
    """The rotation axis indices the user has enabled."""
    if not props.do_shake:
        return set()
    axes = set()
    if props.shake_x:
        axes.add(0)
    if props.shake_y:
        axes.add(1)
    if props.shake_z:
        axes.add(2)
    return axes


def apply_to_object(obj, storm, props, factor, rest, ceiling):
    """Build the rig on one object.

    ``factor`` is the object's weight response, ``rest`` its resting
    ``(center_x, center_y)``, and ``ceiling`` its available headroom under the
    storm.  Channels that end up undriven are reset, not just left alone.
    """
    inv_r = 1.0 / max(0.0001, props.radius)
    gate = gate_expr(rest[0], rest[1], inv_r)

    # ---- LIFT on delta_location Z ----
    amp = max(0.0, ceiling) * factor
    if props.do_lift and amp > 1e-6:
        add_driver(obj, channels.LIFT_PATH, channels.LIFT_INDEX, storm,
                   lift_expr(gate, amp))
    else:
        channels.reset_channel(obj, channels.LIFT_PATH, channels.LIFT_INDEX)

    # ---- SHAKE on delta_rotation_euler ----
    axes = shake_axes(props)
    if axes:
        channels.ensure_euler(obj)
        amplitude = math.radians(props.shake_degrees) * factor / _SINE_SUM_PEAK
        rng = object_rng(props.seed, obj.name)
        for a in (0, 1, 2):
            if a not in axes:
                channels.reset_channel(obj, channels.SHAKE_PATH, a)
                continue
            freq = props.shake_speed * (1.0 + 0.17 * a)
            phase = rng.uniform(0.0, 6.2831853)
            add_driver(obj, channels.SHAKE_PATH, a, storm,
                       shake_expr(gate, amplitude, freq, phase))
    else:
        for a in (0, 1, 2):
            channels.reset_channel(obj, channels.SHAKE_PATH, a)
