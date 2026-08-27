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
alone is ~75 characters and is inlined into every driver, so
:func:`oscillator_expr` counts its octaves against a budget.
"""

import math
import random
import zlib

from . import channels, measure

#: Frequency ratios between the octaves of the shake, and how much each
#: octave's frequency is jittered per object.  Deliberately not whole numbers:
#: harmonically related octaves re-align into an obvious repeating pattern.
_OCTAVE_RATIOS = (2.3, 4.7)
_OCTAVE_JITTER = 0.12

#: Leave room for the gate and the amplitude when adding octaves.
_EXPRESSION_BUDGET = 250

#: Speed multiplier floor, so "Speed by Weight" at full strength slows the
#: heaviest object down rather than freezing it.
_MIN_SPEED_SCALE = 0.2


def object_rng(seed, name, salt=""):
    """Deterministic per-object RNG.

    Keyed on the object's name rather than on iteration order, so re-applying
    reproduces the same phases even though selection order is not stable.
    crc32 is used instead of ``hash()`` because Python randomises string
    hashing between sessions.  ``salt`` separates independent streams (tilt,
    twist, rattle) for the same object.
    """
    key = zlib.crc32((name + "|" + salt).encode("utf-8")) & 0xFFFFFFFF
    return random.Random((int(seed) * 2654435761) ^ key)


# ----------------------------------------------------------------------------
# Expression fragments
# ----------------------------------------------------------------------------

def gate_expr(cx, cy, inv_radius, falloff=2.0):
    """Proximity gate: 1.0 under the storm, 0.0 at the influence radius.

    Raised to ``falloff`` so it eases off instead of hitting the radius with a
    hard kink; 1.0 is a straight linear ramp.  Horizontal distance only - the
    storm sits above the scene, so measuring in 3D would mean an object
    directly underneath never reaches full effect.
    """
    ramp = ("max(0.0,1.0-sqrt((sx-({X:.4f}))**2+(sy-({Y:.4f}))**2)*{K:.8f})"
            .format(X=cx, Y=cy, K=inv_radius))
    if abs(falloff - 1.0) < 1e-6:
        return ramp
    return "{R}**{E:.2f}".format(R=ramp, E=falloff)


def frame_frequency(hz, fps):
    """Radians per frame for a wobble of ``hz`` cycles per second.

    Blender drivers only know ``frame``, so the scene's frame rate is folded
    into the constant at Apply time.  Change the scene fps and you must
    re-apply - otherwise the shake speeds up or slows down with it.
    """
    return 2.0 * math.pi * hz / max(1e-6, fps)


def oscillator_expr(base_freq, roughness, rng, budget=_EXPRESSION_BUDGET):
    """A layered sine wobble, and the peak value it can reach.

    One base sine plus up to two quieter, faster octaves whose amplitudes fall
    off by ``roughness``.  At roughness 0 it is a single clean sway; at 1 the
    octaves are as loud as the base and it reads as a rattle.  Returns
    ``(expression, peak)`` so the caller can normalise the amplitude - the
    peak is the sum of the octave amplitudes, since all the sines can crest
    together.
    """
    terms = ["sin(frame*{F:.5f}+{P:.4f})".format(
        F=base_freq, P=rng.uniform(0.0, 6.2831853))]
    peak = 1.0
    amp = roughness
    for ratio in _OCTAVE_RATIOS:
        if amp < 0.02:
            break
        freq = base_freq * ratio * (1.0 + _OCTAVE_JITTER * rng.uniform(-1.0, 1.0))
        term = "{A:.3f}*sin(frame*{F:.5f}+{P:.4f})".format(
            A=amp, F=freq, P=rng.uniform(0.0, 6.2831853))
        if sum(len(t) for t in terms) + len(term) + 4 > budget:
            break
        terms.append(term)
        peak += amp
        amp *= roughness
    return "(" + "+".join(terms) + ")", peak


def wobble_expr(gate, amplitude, base_freq, roughness, rng,
                budget=_EXPRESSION_BUDGET):
    """Gate * amplitude * a layered wobble, normalised to peak at amplitude.

    ``budget`` is the room left for the whole expression; the octaves are what
    give way when a spin term has to share the channel.
    """
    osc, peak = oscillator_expr(base_freq, roughness, rng,
                                budget=max(30, budget - len(gate) - 12))
    return "{G}*{A:.6f}*{O}".format(G=gate, A=amplitude / peak, O=osc)


def spin_expr(frame_in, frame_out, radians):
    """Rotation that winds on as the storm passes, then holds.

    A driver has no memory - it is a pure function of `frame` and where the
    storm is right now - so an accumulating spin cannot be integrated from the
    proximity gate: gating `rate * frame` would wind the object up on the way
    in and unwind it on the way out.  Instead the frames during which the storm
    is within reach of this object are found at Apply time, and the rotation
    ramps between them and clamps at both ends.  Before the pass it is 0, after
    it the object keeps the orientation it was left in.
    """
    span = max(1.0, float(frame_out) - float(frame_in))
    return "min(1.0,max(0.0,(frame-{A:.1f})*{B:.6f}))*{T:.6f}".format(
        A=frame_in, B=1.0 / span, T=radians)


def lift_expr(gate, amplitude):
    """Gate scaled by the weight-scaled, ceiling-capped lift amplitude."""
    return "{G}*{A:.6f}".format(G=gate, A=amplitude)


# ----------------------------------------------------------------------------
# Per-object values
# ----------------------------------------------------------------------------

def object_speed_hz(props, lightness, rng):
    """This object's base wobble frequency, in cycles per second.

    Two things pull it away from the panel value: lighter objects have a
    higher natural frequency (a can buzzes, a dumpster lumbers), and a random
    per-object spread keeps a pile from wobbling in lockstep.
    """
    scale = 1.0 + props.shake_speed_by_weight * (2.0 * lightness - 1.0)
    if props.shake_speed_variation > 0.0:
        scale *= 1.0 + props.shake_speed_variation * rng.uniform(-1.0, 1.0)
    return max(0.0, props.shake_speed) * max(_MIN_SPEED_SCALE, scale)


_SPIN_AXIS_INDEX = {'X': 0, 'Y': 1, 'Z': 2}


def object_spin_axis(props, rng):
    """Which axis this object tumbles around."""
    if props.spin_axis == 'RANDOM':
        return rng.choice((0, 1, 2))
    return _SPIN_AXIS_INDEX.get(props.spin_axis, 2)


def object_spin_radians(props, factor, rng):
    """Total rotation this object picks up over the pass, in radians.

    Weight-scaled, spread by Spin Variation, and randomly signed - half the
    pile tumbling one way and half the other is most of what sells it.
    """
    turns = props.spin_turns * factor
    if props.spin_variation > 0.0:
        turns *= 1.0 + props.spin_variation * rng.uniform(-1.0, 1.0)
    if rng.random() < 0.5:
        turns = -turns
    return turns * 2.0 * math.pi


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


def axis_degrees(props, axis):
    """Peak wobble for one axis: X/Y tilt the object, Z twists it."""
    return props.twist_degrees if axis == 2 else props.tilt_degrees


# ----------------------------------------------------------------------------
# Driver construction
# ----------------------------------------------------------------------------

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


def apply_to_object(obj, storm, props, lightness, rest, ceiling, fps,
                    spin_window=None):
    """Build the rig on one object.

    ``lightness`` is 1.0 for the smallest object in the selection and 0.0 for
    the largest, ``rest`` is the object's resting ``(center_x, center_y)``, and
    ``ceiling`` its available headroom under the storm, and ``spin_window`` the
    ``(first_frame, last_frame)`` during which the storm passes it - ``None``
    if spin is off or the storm never comes near.  Channels that end up
    undriven are reset, not just left alone.
    """
    factor = measure.light_factor(lightness, props.min_factor)
    radius = max(0.0001, props.radius)
    lift_gate = gate_expr(rest[0], rest[1], 1.0 / radius, props.falloff)
    # shake reaches further than lift, so trash rattles before it rises
    shake_gate = gate_expr(
        rest[0], rest[1], 1.0 / (radius * max(0.01, props.shake_reach)),
        props.falloff)

    _apply_lift(obj, storm, props, factor, ceiling, lift_gate)
    _apply_shake(obj, storm, props, factor, lightness, shake_gate, fps,
                 spin_window)
    _apply_rattle(obj, storm, props, factor, lightness, shake_gate, fps)


def _apply_lift(obj, storm, props, factor, ceiling, gate):
    amp = max(0.0, ceiling) * factor
    if props.do_lift and amp > 1e-6:
        add_driver(obj, channels.LIFT_PATH, channels.LIFT_INDEX, storm,
                   lift_expr(gate, amp))
    else:
        channels.reset_channel(obj, channels.LIFT_PATH, channels.LIFT_INDEX)


def _apply_shake(obj, storm, props, factor, lightness, gate, fps, spin_window):
    axes = shake_axes(props)

    spin_axis = None
    spin_radians = 0.0
    if props.do_shake and props.do_spin and spin_window is not None:
        spin_rng = object_rng(props.seed, obj.name, "spin")
        spin_axis = object_spin_axis(props, spin_rng)
        spin_radians = object_spin_radians(props, factor, spin_rng)
        if abs(spin_radians) < 1e-9:
            spin_axis = None

    if not axes and spin_axis is None:
        for a in (0, 1, 2):
            channels.reset_channel(obj, channels.SHAKE_PATH, a)
        return

    channels.ensure_euler(obj)
    hz = object_speed_hz(props, lightness, object_rng(props.seed, obj.name, "speed"))
    for a in (0, 1, 2):
        terms = []
        spin_term = ""
        if a == spin_axis:
            spin_term = spin_expr(spin_window[0], spin_window[1], spin_radians)

        amplitude = math.radians(axis_degrees(props, a)) * factor
        if a in axes and amplitude > 1e-9 and hz > 0.0:
            rng = object_rng(props.seed, obj.name, "shake%d" % a)
            # a slight per-axis frequency offset stops the axes tracing a line
            freq = frame_frequency(hz * (1.0 + 0.17 * a), fps)
            terms.append(wobble_expr(
                gate, amplitude, freq, props.shake_roughness, rng,
                budget=_EXPRESSION_BUDGET - len(spin_term) - 2))
        if spin_term:
            terms.append(spin_term)

        if not terms:
            channels.reset_channel(obj, channels.SHAKE_PATH, a)
            continue
        add_driver(obj, channels.SHAKE_PATH, a, storm, "+".join(terms))


def _apply_rattle(obj, storm, props, factor, lightness, gate, fps):
    """Small horizontal jitter on Delta Location X/Y."""
    amplitude = props.rattle_distance * factor
    on = props.do_shake and props.do_rattle and amplitude > 1e-9
    speed_rng = object_rng(props.seed, obj.name, "speed")
    hz = object_speed_hz(props, lightness, speed_rng)
    for a in channels.RATTLE_INDICES:
        if not on or hz <= 0.0:
            channels.reset_channel(obj, channels.RATTLE_PATH, a)
            continue
        rng = object_rng(props.seed, obj.name, "rattle%d" % a)
        freq = frame_frequency(hz * (1.0 + 0.23 * a), fps)
        add_driver(obj, channels.RATTLE_PATH, a, storm,
                   wobble_expr(gate, amplitude, freq, props.shake_roughness, rng))
