# -*- coding: utf-8 -*-
"""Check the add-on without Blender.

    python tools/check.py

Stubs `bpy` and `mathutils`, imports every module (so import errors and typos
surface), then exercises the pure logic: the driver expressions, the weight
curve, and the per-object phase seeding.

The expressions are evaluated with only the names Blender's fast
simple-expression evaluator exposes - sqrt, max, sin, the driver variables and
`frame`.  If an expression evaluates here, it is on the fast path.

Registration, depsgraph behaviour and Bake cannot be checked this way; those
need a real Blender session.
"""

import math
import os
import sys
import types

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

#: exactly what Blender's simple-expression evaluator exposes to a driver
DRIVER_SCOPE = {"sqrt": math.sqrt, "max": max, "sin": math.sin}

#: Blender refuses driver expressions longer than this
MAX_EXPR_LEN = 256


def install_stubs():
    """Minimal fake bpy / mathutils, enough to import the add-on."""
    def _prop(*args, **kwargs):
        return None

    class _Base(object):
        pass

    bpy = types.ModuleType("bpy")
    bpy.props = types.SimpleNamespace(**{n: _prop for n in (
        "PointerProperty", "FloatProperty", "BoolProperty", "IntProperty")})
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


def evaluate(expr, sx, sy, frame=1):
    scope = dict(DRIVER_SCOPE, sx=sx, sy=sy, frame=frame)
    return eval(expr, {"__builtins__": {}}, scope)  # noqa: S307 - fixed scope


def check_expressions(addon):
    rig = addon.rig
    # a far-from-origin object, to keep the formatted constants long
    ox, oy, radius = -1234.5678, 9876.5432, 21.0
    gate = rig.gate_expr(ox, oy, 1.0 / radius)
    lift = rig.lift_expr(gate, 4.25)
    shake = rig.shake_expr(gate, math.radians(12.0) / 1.5, 0.9, 3.1416)

    print("expression lengths: gate %d, lift %d, shake %d (limit %d)"
          % (len(gate), len(lift), len(shake), MAX_EXPR_LEN))
    assert len(shake) < MAX_EXPR_LEN, "expression too long for Blender"

    print("lift, amplitude 4.25 over radius 21:")
    for d in (0.0, 5.0, 10.5, 20.0, 21.0, 30.0):
        print("  storm %5.1f m away -> %7.4f" % (d, evaluate(lift, ox + d, oy)))

    assert abs(evaluate(lift, ox, oy) - 4.25) < 1e-6, "full lift under the storm"
    assert evaluate(lift, ox + radius, oy) == 0.0, "zero at the radius"
    assert evaluate(lift, ox + 40.0, oy) == 0.0, "settles to zero past the radius"
    assert evaluate(lift, ox, oy, 999) == evaluate(lift, ox, oy, 1), \
        "lift must not depend on frame"

    peak = max(abs(evaluate(shake, ox, oy, f)) for f in range(1, 4000))
    print("shake peak under the storm: %.3f deg (Shake Amount was 12)"
          % math.degrees(peak))
    assert 11.0 < math.degrees(peak) <= 12.01, math.degrees(peak)
    assert evaluate(shake, ox + 25.0, oy, 123) == 0.0, "shake zero out of range"


def check_weight_curve(addon):
    light_factor = addon.measure.light_factor
    print("weight curve, Heaviest Effect 0.15, sizes 0.1 .. 10:")
    for size in (0.1, 0.5, 1.0, 3.0, 10.0):
        print("  size %5.1f -> factor %.3f"
              % (size, light_factor(size, 0.1, 10.0, 0.15)))
    assert abs(light_factor(0.1, 0.1, 10.0, 0.15) - 1.0) < 1e-9
    assert abs(light_factor(10.0, 0.1, 10.0, 0.15) - 0.15) < 1e-9
    assert light_factor(5.0, 5.0, 5.0, 0.15) == 1.0, "single object -> full effect"
    assert 0.15 <= light_factor(0.01, 0.1, 10.0, 0.15) <= 1.0, "out of range clamps"


def check_phases(addon):
    rng = addon.rig.object_rng
    a1 = rng(1, "can_01").uniform(0.0, 6.28)
    a2 = rng(1, "can_01").uniform(0.0, 6.28)
    b1 = rng(1, "can_02").uniform(0.0, 6.28)
    c1 = rng(2, "can_01").uniform(0.0, 6.28)
    print("phases: can_01/seed1 %.4f, can_02/seed1 %.4f, can_01/seed2 %.4f"
          % (a1, b1, c1))
    assert a1 == a2, "same object + seed must reproduce"
    assert a1 != b1, "different objects must differ"
    assert a1 != c1, "different seeds must differ"


def check_ownership(addon):
    owned = addon.channels.OWNED_CHANNELS
    print("owned channels: %s" % (owned,))
    for forbidden in (("location", 2), ("rotation_euler", 0), ("scale", 0)):
        assert forbidden not in owned, forbidden
    assert ("delta_location", 2) in owned
    assert all(("delta_rotation_euler", a) in owned for a in (0, 1, 2))


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


def main():
    install_stubs()
    addon = load_addon()

    print("add-on version: %s"
          % ".".join(str(n) for n in addon.bl_info["version"]))
    print("modules imported: channels, measure, rig, props, operators, ui")
    print("registered classes: %d\n" % len(addon._CLASSES))

    for section, fn in (("expressions", check_expressions),
                        ("weight curve", check_weight_curve),
                        ("phase seeding", check_phases),
                        ("channel ownership", check_ownership)):
        print("-- %s --" % section)
        fn(addon)
        print("")

    print("ALL CHECKS PASSED")


if __name__ == "__main__":
    main()
