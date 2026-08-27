# Storm Trash FX

A Blender add-on that builds a reusable **lift + shake rig** for
"storm passes over trash" shots.

For every selected object it creates drivers so that, as a moving storm object
passes over it, the object:

* **rises** on Delta Location Z (lift),
* **tilts and twists** on Delta Rotation (shake), fading in with proximity,
* **tumbles**, keeping the orientation the storm leaves it in, and
* **rattles** slightly sideways on Delta Location X/Y,

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

1. On GitHub: **Code → Download ZIP**
2. In Blender: `Edit > Preferences > Add-ons > Install from Disk...`
3. Pick the zip you downloaded
4. Enable **Animation: Storm Trash FX**

The add-on package *is* the repository root, so GitHub's zip drops straight in
— no unwrapping, no rezipping. Blender will name the installed module after the
zip's folder (`storm_trash_fx-main`); that is normal and harmless.

**While developing**, skip the zip: symlink or copy this repo's `.py` files
into a folder under your Blender `scripts/addons/` directory. Disabling and
re-enabling the add-on reloads the submodules, so you don't have to restart
Blender.

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
| **Falloff** | `2.0` | Shape of the ramp from the radius in to the storm. `1` = straight line; higher keeps the effect weak until the storm is close. |

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
| **Shake** | on | Drive Delta Rotation Euler, and the horizontal rattle. |

### Shake

| Setting | Default | What it does |
| --- | --- | --- |
| **Tilt Amount** | `12.0` | Peak tilt in degrees for the lightest object, on X and Y. |
| **Twist Amount** | `6.0` | Peak twist in degrees for the lightest object, on Z. |
| **Axes X / Y / Z** | X, Y | Which rotation axes move. |
| **Speed** | `1.5` | Base wobble rate in **cycles per second**, converted using the scene fps at Apply time. |
| **Roughness** | `0.35` | How much fast detail rides on the base wobble. `0` = a clean sway, `1` = a busy rattle. |
| **Speed Variation** | `0.3` | Random spread of wobble rate between objects, so a pile doesn't move in lockstep. |
| **Speed by Weight** | `0.5` | How much lighter objects wobble faster than heavy ones. `0` = one rate for everything. |
| **Shake Reach** | `1.4` | Shake radius as a multiple of *Influence Radius*. Above `1`, trash trembles before it starts to rise. |
| **Rattle** | on | Also jitter objects horizontally, not just rotate them. |
| **Rattle Amount** | `0.05` | Peak horizontal jitter for the lightest object, in scene units. |
| **Spin** | on | Let objects tumble as the storm passes, keeping the orientation they're left in. |
| **Spin Turns** | `0.5` | Full rotations the lightest object makes while the storm passes it. |
| **Spin Axis** | Random | Axis objects tumble around. `Z` spins them flat like a coin, `X`/`Y` roll them over. |
| **Spin Variation** | `0.5` | Random spread of how far each object turns. Direction is always random. |
| **Random Seed** | `1` | Change for a different set of per-object phases and speeds. |

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
max(0.0, 1.0 - sqrt((sx - ox)**2 + (sy - oy)**2) * (1/R)) ** falloff
```

`sx` / `sy` are the storm's **world X and Y**, read through native Transform
Channel driver variables. `ox` / `oy` are the object's resting position, baked
into the expression as constants at Apply time. `R` is the influence radius —
multiplied by *Shake Reach* for the shake and rattle, which is how trash starts
trembling before it starts to rise. *Falloff* shapes the ramp; at the default
`2` it eases off instead of hitting the radius edge with a visible kink.

The distance is **horizontal only**. The storm sits several metres above the
scene, so measuring in 3D would mean an object directly underneath never
reaches full effect.

**Lift driver** on `delta_location[2]` — `gate * A`, where `A` is the
weight-scaled, ceiling-capped amplitude.

**Shake driver** on each enabled `delta_rotation_euler[axis]`, and **rattle
drivers** on `delta_location[0]` and `[1]` — all the same shape:

```
gate * A * (sin(frame*F + P) + r*sin(frame*F2 + P2) + r²*sin(frame*F3 + P3))
```

A base sine plus up to two quieter, faster octaves whose amplitudes fall off by
*Roughness* (`r`). At roughness `0` it collapses to a single clean sway; at `1`
the octaves are as loud as the base and it reads as a rattle. The octave ratios
(2.3×, 4.7×) are deliberately not whole numbers — harmonically related octaves
re-align into an obvious repeating pattern. `A` is divided by the sum of the
octave amplitudes, so *Tilt Amount* is the true peak in degrees.

**Spin is the one thing that isn't an oscillation.** A driver has no memory —
it is a pure function of `frame` and where the storm is *right now* — so an
accumulating rotation cannot be integrated from the proximity gate. Gating
`rate * frame` would wind an object up on the way in and unwind it on the way
out, landing it back where it started. Instead, Apply samples the storm's path
across the scene frame range, finds the frames during which it comes within
reach of each object, and emits a ramp that clamps at both ends:

```
min(1.0, max(0.0, (frame - frame_in) * (1/span))) * total_radians
```

Zero before the pass, winding on through it, and holding afterwards — so the
pile settles at new angles, as if it had actually been thrown about. Direction
is randomly signed per object and the amount is weight-scaled, so light pieces
tumble and heavy ones barely turn. This is why Apply steps through the frame
range when Spin is on, and why **spin timing goes stale if you re-time the
storm** — re-apply.

**Speed is in cycles per second.** A driver only knows `frame`, so the scene
frame rate is folded into `F` at Apply time — meaning **if you change the scene
fps, re-apply**, or the shake will speed up or slow down with it. Three things
pull each object's rate away from the panel value: *Speed by Weight* (lighter
objects have a higher natural frequency — a can buzzes, a dumpster lumbers),
*Speed Variation* (a random per-object spread, so a pile doesn't pulse in
unison), and a small per-axis offset so the axes don't trace a straight line.
Every phase and rate is derived from the object's name plus the seed, so they
survive a re-apply unchanged.

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
* The add-on only ever touches `delta_location[0..2]` and
  `delta_rotation_euler[0..2]`. Your regular Location/Rotation animation is
  left alone — but any *existing* drivers or keyframes on those delta channels
  are replaced.
* Baking with a long frame range steps the whole scene frame by frame; on heavy
  scenes it takes a while.

---

## Repository layout

The repository root doubles as the add-on package — that is what makes the
GitHub zip installable as-is.

```
__init__.py     bl_info, submodule reload, register / unregister
channels.py     the six delta channels the add-on owns, and the only code
                that writes them
measure.py      reading the scene: size, resting position, storm underside,
                weight curve
rig.py          driver expressions and driver construction
props.py        panel settings, stored on the scene
operators.py    Apply / Clear / Bake / Auto-detect - all scene mutation
ui.py           the N-panel
tools/check.py  run the logic without Blender
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
converts them, but check the axis toggles (Z is off by default) and that *Tilt
Amount* isn't zero.

**The shake looks like fast vibration.** Drop *Speed* — it is in cycles per
second, so `1.5` is a slow sway and `6` is a buzz. *Roughness* at `0` removes
the fast detail layer entirely. Also check the scene fps hasn't changed since
you applied.

**Everything shakes in unison.** Raise *Speed Variation*, and *Speed by Weight*
if the pile has a mix of sizes.

**Nothing spins.** Apply reports *"no spin — the storm never passes within
reach"* when the storm's path never brings it within *Influence Radius* x
*Shake Reach* of any selected object. Check the storm is actually animated
across the scene frame range, and that the range covers the pass.

**Spin happens at the wrong time.** The pass window is baked at Apply time from
the storm's path. Re-time or move the storm and you need to re-apply.

**Rotation makes objects bob up and down.** Delta rotation pivots on the object
origin, so an origin at the object's centre swings the geometry vertically. Set
the origin to the base (`Object > Set Origin > Origin to Geometry`, or place the
3D cursor at the base and use *Origin to 3D Cursor*) and the same tilt reads as
rocking on the ground instead.

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
