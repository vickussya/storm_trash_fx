# AGENTS.md

Guidance for AI agents (Claude Code and friends) working in this repository.
Humans are welcome to read it too — it doubles as the contributor guide.

## What this project is

**Storm Trash FX** is a Blender add-on (Blender 4.2+) that rigs
proximity-driven lift and shake drivers onto selected mesh objects. No package
manager, no dependencies beyond Blender's bundled `bpy` / `mathutils`, and no
build step — the user zips the repo contents and installs that.

```
storm_trash_fx/
    __init__.py     bl_info, submodule reload, register / unregister
    channels.py     the four delta channels the add-on owns, and the only
                    code that writes them
    measure.py      reading the scene: size, resting position, storm
                    underside, weight curve
    rig.py          driver expressions and driver construction
    props.py        panel settings, stored on the scene
    operators.py    Apply / Clear / Bake / Auto-detect - all scene mutation
    ui.py           the N-panel
tools/
    check.py        run the logic without Blender
README.md           user-facing documentation
CHANGELOG.md        Keep a Changelog format, semver, mirrors bl_info["version"]
AGENTS.md           this file
LICENSE             GPL-3.0
.gitignore          Python + Blender + VS Code
```

The layering is one-way: `channels` and `measure` depend on nothing of ours,
`rig` depends on `channels`, `operators` depends on all three, `ui` depends on
none of them (it goes through operator ids). Keep it that way — if a helper
needs to reach back up a layer, it is in the wrong module.

New modules go in the package and export a `CLASSES` tuple if they define
Blender classes; `__init__.py` concatenates those and must also list the module
in its reload loop, dependencies first.

---

## Safety rules

These are hard rules. When in doubt, stop and ask.

### Never touch the user's Blender data

* **Do not open, run, modify, or save `.blend` files.** Not with
  `blender --background file.blend --python ...`, not "just to test". Blender
  scenes are the user's irreplaceable creative work, and a headless script can
  destroy hours of it silently.
* If you genuinely need to verify runtime behaviour, ask first, and then only
  against a **throwaway scene you create yourself**
  (`blender --background --factory-startup --python-expr ...`), never a project
  file.
* Never commit `.blend` files, renders, caches, or any binary artifact.

### The add-on must stay opt-in

* **Nothing may mutate the scene until the user presses a button.** No
  `bpy.app.handlers` registration, no work at import or register time, no
  auto-apply on file load, no timers.
* All scene mutation lives in operators carrying
  `bl_options = {'REGISTER', 'UNDO'}` so the user can Ctrl+Z out of it.
* Report outcomes through `self.report({'INFO'}, ...)` / `{'WARNING'}` /
  `{'ERROR'}` and return `{'CANCELLED'}` on bad input instead of raising.

### Stay inside the channels this add-on owns

* The add-on may only write `delta_location[2]` and
  `delta_rotation_euler[0..2]`, plus `rotation_mode` when it must switch an
  object to Euler.
* **Never** touch `location`, `rotation_euler`, `rotation_quaternion`, `scale`,
  modifiers, materials, or collections.
* Never bulk-delete animation data. `driver_remove` and keyframe removal must
  always be scoped to a specific `data_path` plus `index`.
* Operators act on `context.selected_objects` only — never on `bpy.data.objects`
  at large.

### No outside world

* No network calls, telemetry, update checks, or analytics.
* No `subprocess`, no writing files outside the add-on's own scope, no `eval` /
  `exec` of user-supplied strings.
* Driver expressions are assembled from **numeric** values formatted into the
  string. Never interpolate a user-typed string into a driver expression.

### Git

* Don't `git commit` or `git push` unless the user asks.
* Never force-push, never rewrite history on `main`, never `git reset --hard`
  over uncommitted work.
* Work on a branch for anything beyond a small fix.

---

## Coding conventions

* Python 3.11 (Blender 4.2's interpreter), 4-space indent, stdlib only.
* Naming follows Blender's required prefixes:
  * Operators: `STORMFX_OT_<verb>` with `bl_idname = "stormfx.<verb>"`
  * Panels: `STORMFX_PT_<name>`
  * Property group: `StormFXProps`
  * Module-private helpers: `_leading_underscore`
* Every Blender class must be listed in its module's `CLASSES` tuple, which
  `__init__.py` concatenates and registers, unregistering in reverse.
* Every property needs a `name` and a plain-language `description` — that
  description is the tooltip an artist reads.
* Keep the code defensive: helpers wrap fragile Blender calls in `try/except`
  and fall back to a safe default rather than breaking a rig mid-apply.

### Driver performance — do not regress this

The lift and shake expressions deliberately stay on Blender's **fast
simple-expression path**: only arithmetic, `max`, `sin`, numeric literals, the
`frame` symbol, and native driver variables.

* Do **not** set `use_self = True`.
* Do **not** call into Python from a driver expression, register driver
  namespace functions, or reference `bpy` from an expression.
* Proximity must come from native driver variables, never from a
  Python-computed distance.

A driver that falls off the fast path costs a Python call per object, per
channel, per frame — and these rigs run on hundreds of objects.

### No self-referencing driver variables

A driver on an object's transform must **never** take a variable that reads
that same object's transform — and that includes a `LOC_DIFF` (Distance)
variable with the driven object as one of its two targets. It is a dependency
cycle: Blender detects it, breaks it with stale data, and the rig freezes or
jitters. This was the 1.0.0 bug.

Driver variables may read the **storm**, or any other independent object. The
driven object's own position belongs in the expression as a constant, captured
at Apply time.

### Removing a driver leaves its last value behind

`driver_remove()` does not reset the property. Any code path that stops driving
one of the owned channels — Lift toggled off, a shake axis deselected, a zero
amplitude, Clear — must also write `0.0` back to that channel, or objects stay
floating or tilted. Use `channels.reset_channel()` / `channels.reset_all()`
rather than calling `driver_remove` at the call site.

---

## Verifying changes

`import bpy` fails outside Blender, so the checker stubs `bpy` and `mathutils`
into `sys.modules`, imports the package, and exercises the pure logic:

```bash
python tools/check.py     # always run this
```

That catches import errors and typos across every module, and asserts the real
behaviour of the driver expressions, the weight curve, the phase seeding and
the channel ownership list. Expressions are evaluated with only
`{sqrt, max, sin, sx, sy, frame}` in scope — the same names Blender's
simple-expression evaluator exposes — so if one evaluates there, it is on the
fast path. **Extend `tools/check.py` when you add logic it could cover.**

Beyond that, static review is the bar: check `bl_info`, that every Blender
class is in its module's `CLASSES`, that `register` / `unregister` are
symmetric, and that every property referenced in the panel actually exists on
`StormFXProps`.

Anything requiring a real Blender session — registration, depsgraph behaviour,
bake — is the **user's** job to test. Say so plainly rather than claiming a
change is verified.

---

## Checklist for a change

1. `python tools/check.py` passes.
2. New or renamed settings are reflected in the README settings tables.
3. User-visible changes get a `CHANGELOG.md` entry under `[Unreleased]`.
4. On release: bump `bl_info["version"]` and the CHANGELOG version heading
   together — they must never disagree.
5. Report honestly what you did and did not test in Blender.

---

## Known gotchas

* **Apply resets before it measures.** Ceilings and rest positions are read
  after `channels.reset_all()` plus a `view_layer.update()`, so re-applying with the
  storm parked overhead still reads true resting values. Keep that order.
* **The rig is anchored to a baked-in rest position**, so it goes stale if the
  user moves the trash afterwards. That is the deliberate cost of being
  cycle-free — don't "fix" it by reintroducing a self-referencing variable.
* **Bake reads the evaluated object** (`obj.evaluated_get(depsgraph)`). Drivers
  are evaluated on the depsgraph copy; reading the original is unreliable.
* **Bake holds object references, not names.** Name lookups break on renames
  and on collisions between linked libraries.
* **Bake calls `scene.frame_set` per frame** across the whole range — it is slow
  by nature and it moves the playhead. The original frame is restored at the
  end; keep that restore.
* `measure.bbox_stats` uses the *evaluated* object so geometry nodes and modifiers
  count; the `dimensions` fallback exists for objects with no evaluable
  geometry.
* **Size is the bbox diagonal, not the volume.** Volume is zero for flat or thin
  pieces, which dumps them at the lightest end of the scale and squashes
  everything else toward *Heaviest Effect*.
* Size weighting is on a **log** scale — switching it to linear would make every
  mid-sized piece behave like a heavy one.
* Weight is **relative to the current selection**, so the same object reacts
  differently depending on what it was applied alongside. That is intended.
* **Driver expressions cap at 256 characters.** The gate is ~75 characters and
  is inlined into every driver; check the length before adding terms.
* `channels.ensure_euler` converts the orientation *before* switching
  `rotation_mode` —
  flipping the mode bare makes the object jump.
