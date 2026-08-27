# -*- coding: utf-8 -*-
"""Check the add-on without Blender.

    python tools/check.py

Stubs `bpy` and `mathutils`, imports every module (so import errors and typos
surface), then exercises the pure logic: the driver expressions, the shake
speed and reach, the weight curve, and the per-object phase seeding.

The expressions are evaluated with only the names Blender's fast
simple-expression evaluator exposes - sqrt, min, max, sin, the driver
variables and `frame`.  If an expression evaluates here, it is on the fast path.

Registration, depsgraph behaviour and Bake cannot be checked this way; those
need a real Blender session.
"""

import math
import os
import sys
import types

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

#: exactly what Blender's simple-expression evaluator exposes to a driver
DRIVER_SCOPE = {"sqrt": math.sqrt, "max": max, "min": min, "sin": math.sin}

#: Blender refuses driver expressions longer than this
MAX_EXPR_LEN = 256

#: a far-from-origin object, to keep the formatted constants long
OX, OY, RADIUS, FPS = -1234.5678, 9876.5432, 21.0, 24.0


class FakeProps(object):
    """Panel defaults, so the checker exercises what the artist actually gets."""
    radius = 21.0
    falloff = 2.0
    min_factor = 0.15
    do_lift = True
    do_shake = True
    tilt_degrees = 12.0
    twist_degrees = 6.0
    shake_x = True
    shake_y = True
    shake_z = False
    shake_speed = 1.5
    shake_roughness = 0.35
    shake_speed_variation = 0.3
    shake_speed_by_weight = 0.5
    shake_reach = 1.4
    do_rattle = True
    rattle_distance = 0.05
    do_spin = True
    spin_turns = 0.5
    spin_axis = 'RANDOM'
    spin_variation = 0.5
    seed = 1


def install_stubs():
    """Minimal fake bpy / mathutils, enough to import the add-on."""
    def _prop(*args, **kwargs):
        return None

    class _Base(object):
        pass

    bpy = types.ModuleType("bpy")
    bpy.props = types.SimpleNamespace(**{n: _prop for n in (
        "PointerProperty", "FloatProperty", "BoolProperty", "IntProperty",
        "EnumProperty")})
    bpy.types = types.SimpleNamespace(
        PropertyGroup=_Base, Operator=_Base, Panel=_Base,
        Object=object, Scene=types.SimpleNamespace())
    bpy.utils = types.SimpleNamespace(
        register_class=lambda c: None, unregister_class=lambda c: None)
    bpy.data = types.SimpleNamespace(objects={})
    sys.modules["bpy"] = bpy

    class Vector(tuple):
        def __new__(cls, values):
            return super(Vector, cls).__new__(cls, tuple(values))

    mathutils = types.ModuleType("mathutils")
    mathutils.Vector = Vector
    mathutils.Quaternion = object
    sys.modules["mathutils"] = mathutils


def load_addon():
    """Import the add-on package that lives at the repository root.

    Loaded by path under a synthetic name rather than by directory name: the
    repo root doubles as the add-on package, so its folder is called whatever
    the clone or GitHub zip happened to name it (`storm_trash_fx-main`, and so
    on).  `submodule_search_locations` is what makes `from . import channels`
    resolve.
    """
    import importlib.util

    name = "_storm_trash_fx_under_test"
    spec = importlib.util.spec_from_file_location(
        name, os.path.join(ROOT, "__init__.py"),
        submodule_search_locations=[ROOT])
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def evaluate(expr, sx, sy, frame=1):
    scope = dict(DRIVER_SCOPE, sx=sx, sy=sy, frame=frame)
    return eval(expr, {"__builtins__": {}}, scope)  # noqa: S307 - fixed scope


def check_expressions(addon):
    rig = addon.rig
    props = FakeProps()
    gate = rig.gate_expr(OX, OY, 1.0 / RADIUS, props.falloff)
    lift = rig.lift_expr(gate, 4.25)
    rng = rig.object_rng(props.seed, "can_01", "shake0")
    freq = rig.frame_frequency(props.shake_speed, FPS)
    shake = rig.wobble_expr(gate, math.radians(props.tilt_degrees), freq,
                            props.shake_roughness, rng)

    print("expression lengths: gate %d, lift %d, shake %d (limit %d)"
          % (len(gate), len(lift), len(shake), MAX_EXPR_LEN))
    assert len(shake) < MAX_EXPR_LEN, "expression too long for Blender"

    print("lift, amplitude 4.25 over radius 21:")
    for d in (0.0, 5.0, 10.5, 20.0, 21.0, 30.0):
        print("  storm %5.1f m away -> %7.4f" % (d, evaluate(lift, OX + d, OY)))

    assert abs(evaluate(lift, OX, OY) - 4.25) < 1e-6, "full lift under the storm"
    assert evaluate(lift, OX + RADIUS, OY) == 0.0, "zero at the radius"
    assert evaluate(lift, OX + 40.0, OY) == 0.0, "settles to zero past the radius"
    assert evaluate(lift, OX, OY, 999) == evaluate(lift, OX, OY, 1), \
        "lift must not depend on frame"

    peak = max(abs(evaluate(shake, OX, OY, f)) for f in range(1, 6000))
    print("shake peak under the storm: %.3f deg (Tilt Amount is %.0f)"
          % (math.degrees(peak), props.tilt_degrees))
    assert math.degrees(peak) <= props.tilt_degrees + 0.01, "overshoots Tilt Amount"
    assert math.degrees(peak) > props.tilt_degrees * 0.8, "never reaches Tilt Amount"
    assert evaluate(shake, OX + 40.0, OY, 123) == 0.0, "shake zero out of range"

    clean, clean_peak = rig.oscillator_expr(freq, 0.0, rng)
    rough, rough_peak = rig.oscillator_expr(freq, 0.35, rng)
    print("octaves: roughness 0 -> %d chars peak %.2f, roughness 0.35 -> %d peak %.2f"
          % (len(clean), clean_peak, len(rough), rough_peak))
    assert len(rough) > len(clean), "roughness must add octaves"
    assert clean_peak == 1.0, "a clean sway peaks at 1"
    assert rough_peak > 1.0


def check_speed(addon):
    """Speed is in Hz, so the wobble must survive a frame-rate change."""
    rig = addon.rig
    props = FakeProps()

    for fps in (24.0, 30.0, 60.0):
        freq = rig.frame_frequency(2.0, fps)
        period_frames = 2.0 * math.pi / freq
        print("  2 Hz at %2.0f fps -> %.2f frames per cycle" % (fps, period_frames))
        assert abs(period_frames - fps / 2.0) < 1e-6, "period must track fps"

    # the old behaviour: Speed 0.9 was radians per frame, a 3.4 Hz buzz at 24fps
    old_hz = 0.9 * 24.0 / (2.0 * math.pi)
    print("  for reference, the old Speed 0.9 was %.1f Hz at 24 fps" % old_hz)
    assert old_hz > 3.0

    light = rig.object_speed_hz(props, 1.0, rig.object_rng(1, "a", "speed"))
    heavy = rig.object_speed_hz(props, 0.0, rig.object_rng(1, "a", "speed"))
    print("  same object, lightest %.2f Hz vs heaviest %.2f Hz" % (light, heavy))
    assert light > heavy, "lighter objects must wobble faster"

    props.shake_speed_by_weight = 1.0
    frozen = rig.object_speed_hz(props, 0.0, rig.object_rng(1, "a", "speed"))
    assert frozen > 0.0, "heaviest must still move at full Speed by Weight"

    props.shake_speed_by_weight = 0.0
    props.shake_speed_variation = 0.0
    a = rig.object_speed_hz(props, 1.0, rig.object_rng(1, "a", "speed"))
    b = rig.object_speed_hz(props, 0.0, rig.object_rng(1, "b", "speed"))
    assert a == b == props.shake_speed, "both controls at 0 means a uniform rate"

    props.shake_speed_variation = 0.3
    spread = set()
    for i in range(8):
        spread.add(round(rig.object_speed_hz(
            props, 0.5, rig.object_rng(1, "o%d" % i, "speed")), 4))
    print("  8 objects at mid weight spread across %d distinct rates" % len(spread))
    assert len(spread) == 8, "objects must not share a rate"


def check_reach(addon):
    """Shake reaches further than lift, so trash trembles before it rises."""
    rig = addon.rig
    props = FakeProps()
    lift_gate = rig.gate_expr(OX, OY, 1.0 / RADIUS, props.falloff)
    shake_gate = rig.gate_expr(OX, OY, 1.0 / (RADIUS * props.shake_reach),
                               props.falloff)
    edge = RADIUS + 2.0
    lift_at_edge = evaluate(lift_gate, OX + edge, OY)
    shake_at_edge = evaluate(shake_gate, OX + edge, OY)
    print("  %.0f m out: lift gate %.4f, shake gate %.4f"
          % (edge, lift_at_edge, shake_at_edge))
    assert lift_at_edge == 0.0, "lift must be done at the influence radius"
    assert shake_at_edge > 0.0, "shake must still reach past it"
    assert evaluate(shake_gate, OX + RADIUS * props.shake_reach, OY) == 0.0

    linear = rig.gate_expr(OX, OY, 1.0 / RADIUS, 1.0)
    curved = rig.gate_expr(OX, OY, 1.0 / RADIUS, 3.0)
    half = OX + RADIUS / 2.0
    print("  halfway in: falloff 1 -> %.3f, falloff 2 -> %.3f, falloff 3 -> %.3f"
          % (evaluate(linear, half, OY), evaluate(lift_gate, half, OY),
             evaluate(curved, half, OY)))
    assert evaluate(linear, half, OY) > evaluate(lift_gate, half, OY), \
        "higher falloff must stay weaker for longer"
    assert evaluate(lift_gate, half, OY) > evaluate(curved, half, OY)
    # (the squares inside the distance term are always there; what falloff 1
    # must not add is a trailing exponent on the whole ramp)
    assert linear.endswith(")"), "falloff 1 should not append an exponent"
    assert lift_gate.endswith("**2.00"), "falloff 2 should append one"


def check_spin(addon):
    """Spin must wind on across the pass and then hold, never unwind."""
    rig = addon.rig
    props = FakeProps()
    turns = 1.5
    spin = rig.spin_expr(40.0, 90.0, turns * 2.0 * math.pi)
    print("  %s" % spin)

    def turns_at(frame):
        return evaluate(spin, OX, OY, frame) / (2.0 * math.pi)

    for f in (1, 40, 52, 65, 90, 140, 500):
        print("  frame %3d -> %+.3f turns" % (f, turns_at(f)))

    assert turns_at(1) == 0.0, "no rotation before the storm arrives"
    assert turns_at(40) == 0.0, "no rotation at the moment it arrives"
    assert abs(turns_at(90) - turns) < 1e-6, "full rotation by the end of the pass"
    assert abs(turns_at(500) - turns) < 1e-6, "must HOLD, not unwind"
    seq = [turns_at(f) for f in range(1, 200)]
    assert all(b >= a - 1e-12 for a, b in zip(seq, seq[1:])),         "rotation must never run backwards"
    assert abs(turns_at(65) - turns / 2.0) < 0.02, "halfway through, half turned"

    # spin does not care where the storm is, only when - the window already
    # encodes the pass, so a far-away storm position must not change it
    assert evaluate(spin, OX, OY, 65) == evaluate(spin, OX + 500.0, OY + 500.0, 65)

    # direction is randomly signed, so a pile does not turn as one
    signs = set()
    for i in range(12):
        rng = rig.object_rng(1, "o%d" % i, "spin")
        signs.add(rig.object_spin_radians(props, 1.0, rng) > 0)
    assert signs == {True, False}, "objects must tumble both ways"

    axes = set()
    for i in range(12):
        axes.add(rig.object_spin_axis(props, rig.object_rng(1, "o%d" % i, "spin")))
    print("  random axis assignment covers %s" % sorted(axes))
    assert axes == {0, 1, 2}, "Random should use all three axes"

    props.spin_axis = 'Z'
    assert rig.object_spin_axis(props, rig.object_rng(1, "a", "spin")) == 2

    props.spin_turns = 0.0
    assert rig.object_spin_radians(props, 1.0, rig.object_rng(1, "a", "spin")) == 0.0

    # worst case: wobble and spin share one axis, with long coordinates and
    # full roughness.  The octave budget is what has to give, not the limit.
    props = FakeProps()
    gate = rig.gate_expr(-98765.4321, 12345.6789, 1.0 / RADIUS, 2.75)
    spin_term = rig.spin_expr(1234.0, 1299.0, -12.566371)
    wob = rig.wobble_expr(gate, math.radians(90.0),
                          rig.frame_frequency(8.0, FPS), 1.0,
                          rig.object_rng(1, "worst", "shake1"),
                          budget=rig._EXPRESSION_BUDGET - len(spin_term) - 2)
    combined = wob + "+" + spin_term
    print("  worst-case wobble+spin on one axis: %d chars (limit %d)"
          % (len(combined), MAX_EXPR_LEN))
    assert len(combined) < MAX_EXPR_LEN, combined
    peak = max(abs(evaluate(combined, -98765.4321, 12345.6789, f))
               for f in range(1200, 1400))
    print("  and it still evaluates, peaking at %.3f rad" % peak)


def check_pass_window(addon):
    """The pass window is what makes the spin land in the right frames."""
    pass_window = addon.measure.pass_window
    # a storm crossing the origin from -100 to +100 over frames 1..101
    track = [(float(f), -100.0 + 2.0 * (f - 1), 0.0) for f in range(1, 102)]

    win = pass_window(track, 0.0, 0.0, 20.0)
    print("  storm crossing the origin, reach 20 -> frames %s" % (win,))
    assert win == (41.0, 61.0), win

    off = pass_window(track, 0.0, 15.0, 20.0)
    print("  object 15 m off the path -> frames %s (shorter window)" % (off,))
    assert off is not None and (off[1] - off[0]) < (win[1] - win[0])

    assert pass_window(track, 0.0, 500.0, 20.0) is None, "out of reach -> no spin"
    assert pass_window([], 0.0, 0.0, 20.0) is None, "empty track -> no spin"

    # a coarse track where the storm crosses inside one sample must still
    # produce a window with width, not an instant snap
    coarse = [(float(f), -100.0 + 25.0 * f, 0.0) for f in range(0, 9)]
    tight = pass_window(coarse, 0.0, 0.0, 5.0)
    print("  single-sample crossing -> frames %s" % (tight,))
    assert tight is not None and tight[1] > tight[0], tight


def check_weight_curve(addon):
    lightness = addon.measure.lightness
    light_factor = addon.measure.light_factor
    print("weight curve, Heaviest Effect 0.15, sizes 0.1 .. 10:")
    for size in (0.1, 0.5, 1.0, 3.0, 10.0):
        t = lightness(size, 0.1, 10.0)
        print("  size %5.1f -> lightness %.3f -> factor %.3f"
              % (size, t, light_factor(t, 0.15)))
    assert abs(lightness(0.1, 0.1, 10.0) - 1.0) < 1e-9
    assert abs(lightness(10.0, 0.1, 10.0) - 0.0) < 1e-9
    assert lightness(5.0, 5.0, 5.0) == 1.0, "single object -> full effect"
    assert 0.0 <= lightness(0.01, 0.1, 10.0) <= 1.0, "out of range clamps"
    assert abs(light_factor(1.0, 0.15) - 1.0) < 1e-9
    assert abs(light_factor(0.0, 0.15) - 0.15) < 1e-9


def check_phases(addon):
    rng = addon.rig.object_rng
    a1 = rng(1, "can_01", "shake0").uniform(0.0, 6.28)
    a2 = rng(1, "can_01", "shake0").uniform(0.0, 6.28)
    b1 = rng(1, "can_02", "shake0").uniform(0.0, 6.28)
    c1 = rng(2, "can_01", "shake0").uniform(0.0, 6.28)
    d1 = rng(1, "can_01", "rattle0").uniform(0.0, 6.28)
    print("phases: can_01/seed1 %.4f, can_02/seed1 %.4f, can_01/seed2 %.4f"
          % (a1, b1, c1))
    assert a1 == a2, "same object + seed must reproduce"
    assert a1 != b1, "different objects must differ"
    assert a1 != c1, "different seeds must differ"
    assert a1 != d1, "tilt and rattle must not share a phase stream"


def check_ownership(addon):
    owned = addon.channels.OWNED_CHANNELS
    print("owned channels: %s" % (owned,))
    for forbidden in (("location", 0), ("location", 2), ("rotation_euler", 0),
                      ("scale", 0), ("delta_scale", 0)):
        assert forbidden not in owned, forbidden
    assert all(("delta_location", a) in owned for a in (0, 1, 2))
    assert all(("delta_rotation_euler", a) in owned for a in (0, 1, 2))
    assert len(owned) == 6


def main():
    install_stubs()
    addon = load_addon()

    print("add-on version: %s"
          % ".".join(str(n) for n in addon.bl_info["version"]))
    print("modules imported: channels, measure, rig, props, operators, ui")
    print("registered classes: %d\n" % len(addon._CLASSES))

    for section, fn in (("expressions", check_expressions),
                        ("shake speed", check_speed),
                        ("shake reach and falloff", check_reach),
                        ("spin", check_spin),
                        ("pass window", check_pass_window),
                        ("weight curve", check_weight_curve),
                        ("phase seeding", check_phases),
                        ("channel ownership", check_ownership)):
        print("-- %s --" % section)
        fn(addon)
        print("")

    print("ALL CHECKS PASSED")


if __name__ == "__main__":
    main()
