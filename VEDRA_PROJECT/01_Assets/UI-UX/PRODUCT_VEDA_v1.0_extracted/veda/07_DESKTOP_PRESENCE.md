# Product Veda · Deliverable 7 — Desktop Presence

The application's life outside its own window. Every decision here must honour
the same quality register as the window itself: calm, premium, timeless,
intelligent. Nothing here may feel like a Windows utility, a chat-tray app, or
a background daemon.

---

## 7.1 · Taskbar and dock icon

### 7.1.1 · The mark

The tree is the only permitted mark. No wordmark in the icon, no abstract glyph,
no AI orb, no chat bubble, no letterform. The icon is a single silhouette of the
Kalpavriksha tree — the same tree the founder meets on the Founder Surface —
rendered as a minimal icon-weight glyph against the icon canvas.

The silhouette is the tree outline: trunk emerging from the bottom centre,
bifurcating branches rising symmetrically, canopy implied by the branching
structure. It is NOT a photorealistic or particle render — it is a clean 1.5px-
stroke vector that reads as "tree" at every size.

### 7.1.2 · Construction at each size

All sizes share the same geometry; only stroke weight adjusts for legibility.

#### 256 × 256 (App Store / macOS App Catalog, source master)

```
Canvas:        256 × 256
Corner radius: 58px (macOS superellipse — use the platform mask, not manual)
Background:    #05070A (--c-void, dark);  fallback for light contexts: #FAF9F6
Icon area:     196 × 196 (centered, 30px padding on each side)
Stroke:        1.5px
Stroke color:  rgba(160, 215, 245, 0.90)  (--tree-particle value, approximated
               for static icon — no alpha compositing with canvas here)
Fill:          none (silhouette is stroked lines only)
Trunk base:    x = 128, y = 196 (bottom of icon area)
Trunk tip:     x = 128, y = 148
Primary branches: two, symmetric, bifurcating at y = 148, ending at
               x = [88, 168], y = 112
Secondary branches: four, one per primary end, ending at
               x = [72, 104, 152, 184], y = 80
Tertiary twigs: optional at this size — eight, ending at y ≈ 60, 2px shorter
               than primary stroke weight
```

The icon has a subtle inner glow at 256px: a centered radial gradient on the
background layer `rgba(127,211,255,0.06)` at 0%, transparent at 60%. This is
the only ornamentation at 256px.

**Founder Light app icon variant:** Background `#FAF9F6`, strokes
`rgba(28,127,184,0.75)`. Provided as a separate asset; the OS uses the
appropriate one automatically.

#### 64 × 64

```
Canvas:        64 × 64
Background:    #05070A
Icon area:     48 × 48 (8px padding each side)
Stroke:        1.5px (unchanged — at 64px this is still legible)
Tertiary twigs: omitted
Secondary branches: rendered, 2px shorter than at 256
Inner glow:    removed
```

#### 32 × 32

```
Canvas:        32 × 32
Background:    #05070A
Icon area:     24 × 24 (4px padding each side)
Stroke:        1.5px — at 32px this renders at approximately 1–2 physical pixels;
               on 2× Retina this is fine. On 1× displays export with
               stroke 1px.
Tertiary twigs: omitted
Secondary branches: omitted
Primary branches: two only, shortened (no tip twig)
Trunk:         renders clearly as a single vertical stroke
```

#### 16 × 16

The critical minimum. At 16px, detail is the enemy.

```
Canvas:        16 × 16
Background:    #05070A
Icon area:     12 × 12 (2px padding each side)
Stroke:        1px physical (0.5px logical at 2× Retina — sub-pixel rendering
               will average it, do NOT fight this)
Geometry:      Trunk only + two primary branch lines only. The branches end
               at the same y-level as the top of the icon area.
               Trunk: x = 8, from y = 12 to y = 7
               Branch L: from (8,7) to (4,3)
               Branch R: from (8,7) to (12,3)
               Result: a Y-shape. This is legible as a tree silhouette
               at 16px. Any more detail becomes noise.
Fill:          none
```

**16px legibility test:** screenshot the icon at 100% zoom on a 1× display in
both dark and light system appearances and verify the Y-shape is distinct from a
checkmark, a wifi icon, and a gear icon. These are the most common dock
neighbours.

### 7.1.3 · Export checklist

| Asset | Size | Format | Colour |
|---|---|---|---|
| `icon_256.png` | 256×256 | PNG-32 | Dark variant |
| `icon_256_light.png` | 256×256 | PNG-32 | Light variant |
| `icon_64.png` | 64×64 | PNG-32 | Dark |
| `icon_32.png` | 32×32 | PNG-32 | Dark |
| `icon_16.png` | 16×16 | PNG-32 | Dark |
| `icon.icns` | macOS bundle | ICNS | All sizes packed |
| `icon.ico` | Windows bundle | ICO | 16, 32, 256 |

The macOS Retina variants (`@2x`) are produced automatically by the ICNS
packer from the 256px master. Do not produce `@2x` exports manually.

---

## 7.2 · System tray

**The system tray / menu bar icon exists on macOS and Windows, but it is
minimal and does not duplicate the window.**

### 7.2.1 · Decision and justification

The system tray icon is present because Kalpavriksha is a companion that runs
continuously. The founder may need to know it is running and may need to return
focus to it from any application without hunting for a window. The tray icon is
the low-friction reopen surface. It is NOT a mini-dashboard, NOT a
notification hub, NOT a status panel.

### 7.2.2 · Tray icon mark

Same Y-shape as the 16px dock icon, white on macOS menu bar (system-managed
template image — `isTemplate: true` on macOS so the OS handles dark/light
menu bar colouration automatically).

On Windows, the 16px icon asset is used directly.

**The tray icon has no badge, no count overlay, no dot.** It is always the
same mark regardless of notification state. Badging the tray would make the
mark feel like a task manager — that is forbidden.

### 7.2.3 · Tray menu

Triggered by left-click (Windows) or click (macOS). The menu is a native OS
context menu (not a custom web-rendered menu — native menus are accessible,
keyboard-navigable, and fast without engineering cost).

Menu items, in order:

```
Open Kalpavriksha                  ← always first; default action on double-click
─────────────────────────────────
Mute Microphone                    ← toggles; label switches to "Unmute Microphone"
─────────────────────────────────
Quit                               ← always last
```

That is the complete menu. Three items, one separator group. No submenus. No
status display in the menu. No "About", no "Preferences" (those are in the
dashboard overlay).

**Rule against burying:** Nothing that the founder regularly needs is in the
tray menu. "Open" returns focus. "Mute" is a quick-access shortcut for the mic.
"Quit" is standard. Settings, history, and all other features are in the
application window itself. The tray must never grow beyond these three items
without an explicit product decision revision.

### 7.2.4 · Tray right-click

Same menu as left-click. On macOS this is automatic; on Windows implement
identically to left-click. There is no separate right-click-only item.

---

## 7.3 · OS-level notification behaviour

**Kalpavriksha does not use OS toast notifications as a default. The tree is
the notification surface** (see 09_NOTIFICATION_SYSTEM).

### 7.3.1 · Strong default: no OS toasts

The application does not request `Notification` permission at launch or at
any prompt. It does not call `new Notification()` or the platform notification
API in normal operation.

Justification: the product promises "calm, respectful, intelligent." OS toast
notifications violate all three — they are intrusive, they escape the
application's visual language, and they cannot be styled to match the product's
feel. The tree's ambient signals are always available when the window is visible.
When the window is not visible, the founder has not been interrupted.

### 7.3.2 · Narrow exceptions

OS notifications are permitted ONLY for:

| Exception | Condition | Copy |
|---|---|---|
| Calendar-anchored alert | A consequential item has a hard deadline that is NOW (not approaching — now), and the window is minimized or the application is in `blurred` state AND the system clock matches the deadline within 60 seconds. | `"Kalpavriksha — [item title]"` (no body text, no badge count, no action buttons) |

One exception. No others.

The notification is delivered with `requireInteraction: false` on web and with
no sound (`silent: true`) on all platforms.

The notification fires at most **once per consequential item**. If the founder
dismisses it, it does not re-fire. If the founder ignores it, it auto-dismisses
after the OS default timeout (the product does not set a custom timeout).

Cross-reference: 09_NOTIFICATION_SYSTEM §9.6 (notification persistence rule)
governs how the notification state is preserved inside the application after
the OS toast disappears.

---

## 7.4 · Minimize

### 7.4.1 · What happens to the tree on minimize

When the window enters the minimized state:

1. The tree canvas rendering loop **pauses** — `requestAnimationFrame` is
   cancelled. No particles move. No breathing occurs.
2. The canvas is NOT cleared. It holds its last painted frame, frozen.
3. All timers that drive tree animation are suspended (not reset).
4. Voice: if the microphone is `listening`, it continues to receive audio input
   in the background (platform permitting). The microphone state is preserved.
   On platforms where mic access requires a visible window, the mic is muted
   and a state variable records `was-listening-before-minimize = true`.

### 7.4.2 · State preserved across minimize

All application state is preserved exactly:

- Tree animation state (which state in the state machine from
  02_ANIMATION_SYSTEM — the named state is preserved, not the animation progress)
- Microphone arm/mute state
- Text composer content (if any was being typed)
- Dashboard overlay state: if the dashboard was open on minimize, it remains
  open on restore

The application does NOT use minimize as an opportunity to save-and-reset.
Minimize is a temporary interruption, not a soft quit.

---

## 7.5 · Restore

### 7.5.1 · Restore sequence

When the window returns from minimized state, the sequence is:

1. The OS returns the window to its previous size and position.
2. The application resumes the warm-start path defined in
   **06_STARTUP_EXPERIENCE** (the document specifying the warm-start sequence).
   Reference that document's warm-start section for the exact animation sequence
   and greeting refresh logic. Do not restate those internals here.
3. The tree canvas rendering loop restarts. `requestAnimationFrame` is
   re-registered.
4. The tree immediately resumes the state it was in before minimize (not the
   idle state). If the tree was `listening` before minimize, it returns to
   `listening`. The transition is instantaneous — there is no re-entry
   animation from idle.
5. If `was-listening-before-minimize = true` and the platform allows background
   mic access, resume is seamless. If the mic was paused (platform limitation),
   the mic returns to `armed` state and the label reads `TAP TO SPEAK`.

### 7.5.2 · What restore does NOT do

- Restore does not re-run the cold-start or warm-start animation in full.
  Restore is faster than warm-start.
- Restore does not change the greeting. The greeting already shown is preserved.
- Restore does not trigger a new session or reset conversation history.

---

## 7.6 · Reopen when already running

**If the founder launches a second instance, the existing window is focused.
A second window is never spawned.**

Mechanism (Electron/Tauri-style):

```
app.on('second-instance', () => {
  if (mainWindow.isMinimized()) mainWindow.restore();
  mainWindow.focus();
});
app.requestSingleInstanceLock();
// If lock not acquired: quit immediately, no UI shown.
```

On macOS, clicking the dock icon when the window exists (even if minimized)
focuses and unminimizes the window. This is the standard macOS behaviour and
requires no custom code beyond ensuring the window is not destroyed on hide.

On Windows, clicking the taskbar button when the window is minimized restores
it. If the window is already visible, clicking the taskbar button minimizes it
(OS-native behaviour — do not override this with custom logic).

---

## 7.7 · Window focus and blur

### 7.7.1 · On blur (window loses OS focus)

When another application receives focus:

```css
/* Applied to the window root when OS blur fires */
.app-root[data-focus="blurred"] {
  /* No CSS opacity change on root — only targeted dimming */
}
.app-root[data-focus="blurred"] .veil {
  /* The veil deepens by exactly one step */
  --veil-extra-opacity: 0.12;   /* added to the radial gradient stops */
  transition: opacity var(--d-3) var(--e-settle);
}
.app-root[data-focus="blurred"] .ui-chrome {
  opacity: 0.72;
  transition: opacity var(--d-3) var(--e-settle);
}
```

**The tree continues to breathe while blurred.** Justification: the tree is a
living presence, not a screensaver that pauses. A tree that freezes when you
look away would feel like a widget. The tree is always alive; it does not
require the founder's attention to exist.

Specific changes on blur:

| Element | Focused | Blurred |
|---|---|---|
| Tree canvas | Full rendering, all particles | Rendering continues; particle count reduced to 60% of active budget (no animation pause) |
| Greeting text | `--c-ink` | `opacity: 0.72` → effective `--c-ink` at reduced opacity |
| Composer capsule | Visible, interactive | `opacity: 0.72`, pointer events still registered |
| Chevron control | Visible | `opacity: 0.72` |
| Wordmark | `--c-ink-3` | `opacity: 0.72` |
| Bloom layer | Full opacity per state | Opacity reduced by `× 0.7` |
| Microphone ring | State-coloured | Ring opacity reduced to 60% |

The dimming transition is `var(--d-3)` (240ms) `var(--e-settle)` in.
The brightening transition on focus-return is `var(--d-2)` (180ms)
`var(--e-settle)`.

**No element is hidden on blur.** Dimming only. The window remains fully
legible and accessible if the founder glances at it while in another app.

### 7.7.2 · On focus return

All dimming reverses with `var(--d-2)` (180ms) `var(--e-settle)`. Particle
count returns to the active budget over `var(--d-5)` (420ms) to avoid a sudden
particle surge. The tree does not re-enter; it was never paused.

---

## 7.8 · Application state table

| State | Tree renders | Tree animates | Mic | Voice output | UI interactive | Network |
|---|---|---|---|---|---|---|
| `cold` | No | No | Off | Off | No | Minimal bootstrap |
| `starting` | Growing (per 06_STARTUP_EXPERIENCE) | Startup sequence only | Off | Off | No | Active |
| `ready` | Full | Idle breathing | Armed | Ready | Yes | Ready |
| `idle` | Full | Slow breathing | Armed | Ready | Yes | Background only |
| `active` | Full | State-driven | Armed/Listening | Active | Yes | Active |
| `minimized` | Frozen (last frame) | No | Preserved / paused (see §7.4.1) | Off | No | Background only |
| `blurred` | Full, 60% particle budget | Continues | Armed (background) | Continues | Yes (pointer inert until re-focused) | Active |
| `suspended` | Frozen | No | Off | Off | No | None (OS-suspended) |
| `quitting` | Fades to 0 opacity `--d-3` | No | Off | Off | No | Flush pending, then disconnect |

**suspended** applies when the OS suspends the process (sleep/hibernate). On
resume, the application follows the warm-start path from
**06_STARTUP_EXPERIENCE**.

---

## 7.9 · Window sizing, minimum size, and position memory

### 7.9.1 · Minimum window size

```
min-width:  834px
min-height: 600px
```

Below these values the OS resize handle stops (the user cannot drag smaller).
At exactly the minimum, the tablet breakpoint rules from 01_FOUNDER_SURFACE §1.8
apply.

### 7.9.2 · Default initial window size

```
default-width:  1280px
default-height: 800px
```

Centred on the primary display at first launch.

### 7.9.3 · Position and size memory

The window's size (`width`, `height`) and position (`x`, `y`) are persisted to
local application storage on every `move` and `resize` event, debounced at
500ms. On next launch (warm or cold), the stored values are applied before the
window is made visible, so the window does not reposition visibly after
appearing.

If the stored position would place the window entirely off-screen (display
configuration has changed), fall back to the default centered position.

Fullscreen state is persisted independently. If the founder was in fullscreen
before quit, restore to fullscreen.

### 7.9.4 · Fullscreen

Native fullscreen is supported. In fullscreen, the OS chrome (traffic lights /
window controls) hides per platform standard. The Kalpavriksha UI does not add
custom window chrome to compensate — the wordmark and chevron remain in their
positions at `--frame-margin`.

---

## 7.10 · Quit versus close behaviour

### 7.10.1 · Window close button (red traffic light / X button)

**Closes the window but does NOT quit the application.**

The application continues running in the background (tray icon remains). This
is the macOS convention for companion apps and is correct here — Kalpavriksha
is a continuous presence, not a document editor that should save-and-quit.

On Windows, the X button also hides the window (does not quit) to match this
behaviour. This is a deliberate override of the Windows convention. A tray
tooltip `"Kalpavriksha is still running"` appears once per session when the
founder first uses the X button, then never again.

The tooltip text is: `"Kalpavriksha is still running. Find it in the system
tray."` Displayed as a native OS balloon tooltip, not a custom toast. Shown
only once per installation (persisted flag).

### 7.10.2 · Quit

`Cmd+Q` (macOS) / `Alt+F4` / tray "Quit" quits the application.

**There is no quit confirmation dialog.** A confirmation would imply the
founder might quit by accident, which patronises them. There is nothing to
save (state is continuous). Quit is immediate.

Exception: if Somesh is actively mid-utterance (voice output is playing) at
the moment of quit, the audio is cut immediately. There is no "wait for Somesh
to finish" guard.

The quit sequence:
1. Flush any pending local state writes (≤ 200ms timeout).
2. Set `data-quitting="true"` on the root — fades all UI to `opacity: 0` over
   `var(--d-3)` (240ms).
3. Tree canvas: `opacity` to `0` over `var(--d-3)`.
4. After `--d-3`, close the window and terminate.

Total quit-to-close: ≤ 440ms. No lingering splash, no "goodbye" copy, no save
prompt.
