# Storm Trash FX

A Blender add-on that builds a reusable **lift + shake rig** for
"storm passes over trash" shots.

For every selected object it creates drivers so that, as a moving storm object
passes over it, the object:

* **rises** on Delta Location Z (lift), and
* **trembles** on Delta Rotation (shake), fading in with proximity,

and settles back to rest as the storm moves on. The effect is strongest right
under the storm and fades to nothing at the edge of its reach.

Three things decide how strongly each object reacts, all worked out
automatically:

* **Proximity** — how near the storm is right now. Full effect underneath it,
  zero past the influence radius, a smooth ramp in between.
* **Weight** — read from each object's real mesh size, on a log scale. Small,
  light pieces (cans, scatter) fly up and rattle hard; big, heavy ones (the
  dumpster) barely stir. Nothing is tagged by hand — size *is* the weight.
* **Ceiling** — a per-object height cap. It reads the storm's underside,
  subtracts a margin, and works out how much headroom each object has from its
  own resting top. Whatever proximity and weight would produce, the object is
  never allowed to rise into the storm.

Everything lands on **delta** channels, so your real placement and any base
animation stay untouched — the effect layers on top and reads as zero when the
storm is far away.

Nothing in your scene changes until you press a button.

* **Blender:** 4.2 or newer
* **Category:** Animation
* **Panel:** 3D View → N-panel → **Storm FX** tab
* **License:** GPL-3.0

---

## Install

**From a zip**

1. Zip this repository's **contents** — the archive must have
   [`storm_trash_fx/`](storm_trash_fx/) at its root
2. `Edit > Preferences > Add-ons > Install from Disk...`
3. Pick the zip
4. Enable **Animation: Storm Trash FX**

> Don't zip the repo *folder*. An archive laid out as
> `storm_trash_fx-main/storm_trash_fx/...` won't register — Blender looks for
> the add-on package at the zip root, and the wrapper folder hides it. Zipping
> just the `storm_trash_fx/` folder on its own works too.

**From the folder**

Copy the [`storm_trash_fx/`](storm_trash_fx/) package folder into your Blender
`scripts/addons/` directory and enable it in Preferences. Handy while editing:
disabling and re-enabling the add-on reloads the submodules, so you don't have
to restart Blender.

---

## Workflow

1. Park the storm away from the trash, so resting heights read correctly.
2. Set **Storm Object** — the thing the trash reacts to. The magnifier button
   next to it auto-detects one by name (`palachinka_mask_toroid_line_0`,
   `Empty_storm`, or anything with "storm" in its name).
3. Select your trash (mesh objects only; the storm object itself is skipped).
4. Press **Apply to Selected**.
5. Scrub the storm across and refine the settings.
6. **Bake to Keyframes** at the end if you want lighter playback.

Re-running **Apply** refreshes the rig — it resets the delta channels before it
measures, so re-applying is safe even with the storm sitting over a pile.
**Clear on Selected** removes the rig (drivers *and* baked keyframes) and puts
the objects back at rest.

> **Apply while the piles are at rest.** The ceiling is measured from each
> object's resting top, and the rig anchors to each object's resting position.
> If a piece has its own keyframed animation, apply on a frame where it is at
> rest — and if you move trash around afterwards, re-apply.

---

## Settings

### Storm

| Setting | Default | What it does |
| --- | --- | --- |
| **Storm Object** | — | The object trash reacts to. Required. |
| **Influence Radius** | `21.0` | Horizontal distance at which the storm starts to affect an object. |

### Ceiling (don't enter storm)

| Setting | Default | What it does |
| --- | --- | --- |
| **Manual Ceiling Height** | off | Type the storm underside Z directly instead of reading it from an object. |
| **Ceiling From** | — | Object whose bounding-box bottom defines the storm underside. Falls back to the Storm Object. |
| **Storm Bottom Z** | `5.18` | World Z of the storm underside, used when *Manual Ceiling Height* is on. |
| **Ceiling Margin** | `0.5` | Safety gap kept between an object's top and the storm underside. |

### Weight response

| Setting | Default | What it does |
| --- | --- | --- |
| **Heaviest Effect** | `0.15` | Fraction of the effect the biggest object still gets. `0` = it never moves. |

### Effect

| Setting | Default | What it does |
| --- | --- | --- |
| **Lift** | on | Drive Delta Location Z. |
| **Shake** | on | Drive Delta Rotation Euler. |
| **Shake Amount** | `12.0°` | Peak wobble for the *lightest* object. |
| **Shake Speed** | `0.9` | How fast the trembling is. |
| **Axes X / Y / Z** | X, Y | Which rotation axes shake. |
| **Random Seed** | `1` | Change for a different set of per-object shake phases. |

### Bake

| Setting | Default | What it does |
| --- | --- | --- |
| **Use Scene Frame Range** | on | Bake over the scene's start..end frames. |
| **Bake Start / Bake End** | `1` / `250` | Custom range when the above is off. |

---

## How it works

**Weighting.** Each object's size is the world-space bounding-box *diagonal* of
its **evaluated** mesh, so geometry nodes and modifiers count. Sizes map on a
log scale (trash sizes span a wide range) to an influence factor between
*Heaviest Effect* and `1.0` — the smallest object in the selection gets `1.0`.
The diagonal is used rather than the volume so that flat or thin pieces, whose
bounding volume is zero, don't all pile up at the "lightest possible" end.

**Ceiling.** `ceiling = (storm_bottom_z - ceiling_margin) - object_top_z`,
measured at Apply time with the rig reset to rest. Lift amplitude is that
headroom scaled by the object's weight factor, so nothing can rise into the
storm volume. Objects already at or above the ceiling get shake only, and the
operator reports how many.

**Proximity gate.** Both effects are gated by the same term:

```
max(0.0, 1.0 - sqrt((sx - ox)**2 + (sy - oy)**2) * (1/R)) ** 2
```

`sx` / `sy` are the storm's **world X and Y**, read through native Transform
Channel driver variables. `ox` / `oy` are the object's resting position, baked
into the expression as constants at Apply time. `R` is the influence radius.
Squaring gives the smooth ramp — it eases off instead of hitting the radius
edge with a visible kink.

The distance is **horizontal only**. The storm sits several metres above the
scene, so measuring in 3D would mean an object directly underneath never
reaches full effect.

**Lift driver** on `delta_location[2]` — `gate * A`, where `A` is the
weight-scaled, ceiling-capped amplitude.

**Shake driver** on each enabled `delta_rotation_euler[axis]`:

```
gate * S * (sin(frame*F + P) + 0.5*sin(frame*F2 + P2))
```

Two sines at incommensurate frequencies give cheap pseudo-noise; `F` differs
per axis and the phase `P` is randomised per object (derived from the object's
name and the seed, so it's stable across re-applies) — nothing shakes in sync.
`S` is normalised by the sine sum's peak of 1.5, so *Shake Amount* is the
actual peak wobble in degrees.

**Why it's fast — and why it isn't a Distance variable.** These expressions use
only arithmetic, `sqrt`, `max`, `sin` and the `frame` symbol, so they run on
Blender's fast simple-expression path rather than falling back to a per-frame
Python evaluation (`use_self` is off).

They deliberately avoid a **Distance (`LOC_DIFF`) variable between the object
and the storm**, which is the obvious way to write this and is a trap: it makes
the object's own transform an input to a driver on that same object's
transform. Blender flags a dependency cycle and breaks it with stale data, so
the rig freezes or jitters. Reading the storm's position and comparing it to a
baked-in resting position keeps the dependency one-way.

**Baking.** The bake operator steps the scene through the frame range, samples
every driven channel from the **evaluated** object, removes the drivers, then
writes the sampled values back as keyframes. The current frame is restored
afterwards.

---

## Notes and limits

* Only **mesh** objects are affected; other object types in the selection are
  ignored.
* The rig is anchored to each object's resting XY position at Apply time. Move
  the trash and the gate goes stale — **re-apply**. (This is the trade for
  being cycle-free; see above.)
* Applying converts objects in Quaternion or Axis-Angle rotation mode to Euler
  XYZ, preserving their current orientation, because the shake drives
  `delta_rotation_euler`.
* The add-on only ever touches `delta_location[2]` and
  `delta_rotation_euler[0..2]`. Your regular Location/Rotation animation is
  left alone — but any *existing* drivers or keyframes on those delta channels
  are replaced.
* Baking with a long frame range steps the whole scene frame by frame; on heavy
  scenes it takes a while.

---

## Repository layout

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
```

`python tools/check.py` stubs `bpy` and `mathutils`, imports every module, and
asserts the driver expressions, weight curve and phase seeding behave — useful
before you install a change. Anything involving registration, the depsgraph or
baking still needs a real Blender session.

---

## Troubleshooting

**Nothing moves.** Check the storm object is set and the trash is within the
influence radius *horizontally* — the gate hits zero at exactly `R` metres. Also
confirm the objects are meshes and were selected when you pressed Apply.

**Objects lift but don't shake.** Shake needs an Euler rotation mode; Apply
converts them, but check the axis toggles (Z is off by default) and that *Shake
Amount* isn't zero.

**Objects only twitch a little.** They're being read as heavy. Weight is
relative to the selection, so a large object in the selection compresses
everything else — apply to piles of comparable pieces, or raise *Heaviest
Effect*.

**They barely rise.** Lift is capped by the headroom under the storm. Raise the
storm, lower *Ceiling Margin*, or check the storm underside is being read from
the right object.

**Something stayed floating or tilted.** Select it and press **Clear on
Selected** — that removes drivers and baked keys and zeroes the delta channels.

---

## License

GPL-3.0. See [LICENSE](LICENSE).
