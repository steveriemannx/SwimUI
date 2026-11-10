# The `FerroUI` native module

This document is the reference of the binding at the centre of SwimUI: what a
`.sw` program sees when it writes `import FerroUI`, what the Nim side
(`runtime/swimferroui.nim`) adds, and what the Rust bridge (`ffi/`) does.

- [The three sides](#the-three-sides)
- [Building the bridge](#building-the-bridge)
- [A program's lifecycle](#a-programs-lifecycle)
- [The Swift-facing functions](#the-swift-facing-functions)
- [Colours, alignment and handles](#colours-alignment-and-handles)
- [Reading properties back](#reading-properties-back)
- [Timers, snapshots and test builds](#timers-snapshots-and-test-builds)
- [The Swift-style view layer (ui/SwimUI.sw)](#the-swift-style-view-layer-uiswimuisw)
- [The C ABI of the bridge](#the-c-abi-of-the-bridge)
- [Adding a control](#adding-a-control)
- [Limitations](#limitations)

---

## The three sides

```
  .sw source        import FerroUI  →  the compiler emits `import swimferroui`
      │              and turns `ferrouiLabel(...)` into `swimFerroUILabel(...)`
  runtime/swimferroui.nim           Int handles, colours, closures, composition
      │              calls the C ABI with {.importc, cdecl, dynlib.}
  ffi/ (Rust, cdylib)               hosts FerroUI: AppBuilder, controls, window
      │
  FerroUI (Rust crates)             the framework itself
```

The compiler's table of the module is `FERROUI_FUNCS` in
`src/swimc/codegen.py`; its kinds are `int`, `double`, `string`, `bool` and
`closure` (`() -> Void`, which also accepts the trailing-closure syntax).  The
Nim file and the table must stay in sync: the anonymous name and the argument
list of each entry are the Nim procedure the call becomes.

## Building the bridge

```console
$ ./scripts/build-ffi.sh                # debug build, into build/
$ ./scripts/build-ffi.sh --release      # optimised build
```

The script builds `ffi/Cargo.toml` (a `cdylib` crate, `ferroui-swim`) and copies
the library into `build/`, where `runtime/swimferroui.nim` looks for it:

| Platform | The library |
| --- | --- |
| macOS | `build/libferroui_swim.dylib` |
| Linux | `build/libferroui_swim.so` |
| Windows | `build/ferroui_swim.dll` |

Environment:

- `FERROUI_DIR` — the FerroUI checkout to build against (default `../FerroUI`
  next to this repository).  A checkout somewhere else is written into a
  generated manifest under `build/ffi-manifest/`, so `ffi/Cargo.toml` keeps
  working as it is.
- `FERROUI_TARGET_DIR` — cargo's target directory (default
  `$FERROUI_DIR/target`, which reuses a FerroUI build that already exists).
- `CARGO`, `CARGO_INCREMENTAL`.

`-d:swimFerroUILibDir=<dir>` at *Swim* build time makes the runtime look for the
library in `<dir>` instead of `build/` (useful for a packaged application).

The FerroUI crates come from `FERROUI_DIR/src/*` as ordinary path dependencies;
`ferroui-swim` itself uses `ferroui-base`, `ferroui-controls`, `ferroui-desktop`
(the platform entry point: windowing, Skia, HarfBuzz) and
`ferroui-themes-simple`.

## A program's lifecycle

FerroUI is an application framework: the platform exists only after the
application starts, and controls and windows are created after that.  A program
therefore starts the application with

```swift
ferrouiRun {
    // the framework is initialized here: build the window and the views
}
```

`ferrouiRun` blocks until the window closes.  Inside the block the program makes
the window with `ferrouiWindow(...)` (one window per program) and the controls
with `ferrouiCanvas`, `ferrouiBox`, `ferrouiLabel`, `ferrouiButton`,
`ferrouiTextField`, `ferrouiCheckBox`, `ferrouiSlider`, `ferrouiProgressBar`,
`ferrouiScrollView` and `ferrouiStack`.

The window's *client* area may be smaller than the size that was asked for: the
window decorations take room, and a display that is not tall enough shortens the
window.  The bridge reports what the client area really is, and the ready
callback fires once the window is up:

```swift
ferrouiRun {
    let window = ferrouiWindow(width: 390, height: 844, title: "Library",
                               background: 0x0B0C10, onClosed: {})
    let canvas = ferrouiCanvas(parent: window)
    ferrouiOnReady(handle: window) {
        let height = ferrouiClientHeight()   // what the layout must fit in
        ...
    }
}
```

The `SwiftUI.sw` layer wraps this shape as `runApp { ... }` +
`screen.onReady { ... }`.

## The Swift-facing functions

The names below are the ones a `.sw` source uses (`FERROUI_FUNCS`); the Nim
procedure is what they become.

### Application and window

| Swift | Nim | Returns |
| --- | --- | --- |
| `ferrouiRun(build:)` / trailing closure | `swimFerroUIRun` | — |
| `ferrouiQuit()` | `swimFerroUIQuit` | — |
| `ferrouiWindow(width:height:title:background:onClosed:)` | `swimFerroUIWindow` | window handle |
| `ferrouiClientWidth()`, `ferrouiClientHeight()` | `swimFerroUIClientWidth`, `…Height` | width/height in points |
| `ferrouiSetDecorations(handle:mode:)` | `swimFerroUISetDecorations` | — |
| `ferrouiSetThemeVariant(name:)` | `swimFerroUISetThemeVariant` | — |
| `ferrouiOnReady(handle:onReady:)` | `swimFerroUIOnReady` | — |
| `ferrouiClose(window:)` | `swimFerroUIClose` | — |

`ferrouiSetThemeVariant` is called before `ferrouiRun`: `"dark"`, `"light"` or
anything else (follow the system; the environment variable
`SWIMUI_THEME_VARIANT` does the same).  `ferrouiSetDecorations` takes `0` for a
borderless window (a phone look), `1` for a border, `2` for the full
decorations.

### Containers

| Swift | Nim | What it makes |
| --- | --- | --- |
| `ferrouiCanvas(parent:)` | `swimFerroUICanvas` | `Canvas`: children at absolute positions |
| `ferrouiStack(parent:vertical:spacing:)` | `swimFerroUIStack` | `StackPanel` |
| `ferrouiBox(parent:x:y:width:height:fill:radius:borderColor:borderWidth:)` | `swimFerroUIBox` | `Border` (fill, radius, border) with a `Canvas` for its children |
| `ferrouiScrollView(parent:x:y:width:height:fill:radius:)` | `swimFerroUIScrollView` | `ScrollViewer` around a `Canvas` |
| `ferrouiContent(container:)` | `swimFerroUIContent` | the canvas of a box or a scroll view (0 for others) |

A control created with `parent:` is added to it: a `Canvas`/`StackPanel` gets
the control as a child, a `Border`/`ScrollViewer`/`Window`/`Button` as its
content.

### Controls

| Swift | Nim | Control |
| --- | --- | --- |
| `ferrouiLabel(parent:x:y:width:height:text:size:color:align:bold:)` | `swimFerroUILabel` | `TextBlock` |
| `ferrouiButton(parent:x:y:width:height:title:size:bold:fill:titleColor:radius:onTap:)` | `swimFerroUIButton` | `Button` |
| `ferrouiTextField(parent:x:y:width:height:text:placeholder:size:onChanged:)` | `swimFerroUITextField` | `TextBox` |
| `ferrouiCheckBox(parent:x:y:width:height:text:checked:onChanged:)` | `swimFerroUICheckBox` | `CheckBox` |
| `ferrouiSlider(parent:x:y:width:height:minimum:maximum:value:onChanged:)` | `swimFerroUISlider` | `Slider` |
| `ferrouiProgressBar(parent:x:y:width:height:percent:)` | `swimFerroUIProgressBar` | `ProgressBar` |

### Properties

| Swift | Nim | Sets |
| --- | --- | --- |
| `ferrouiSetFrame(handle:x:y:width:height:)` | `swimFerroUISetFrame` | size, and in a canvas the position |
| `ferrouiSetText(handle:text:)` | `swimFerroUISetText` | text/label/field/title |
| `ferrouiSetColor(handle:color:)` | `swimFerroUISetColor` | background/fill |
| `ferrouiSetTextColor(handle:color:)` | `swimFerroUISetTextColor` | foreground |
| `ferrouiSetBorder(handle:color:width:)` | `swimFerroUISetBorder` | border brush and thickness |
| `ferrouiSetRadius(handle:radius:)` | `swimFerroUISetRadius` | corner radius |
| `ferrouiSetFontSize(handle:size:)` | `swimFerroUISetFontSize` | font size |
| `ferrouiSetBold(handle:bold:)` | `swimFerroUISetBold` | font weight (400/700) |
| `ferrouiSetAlignment(handle:align:)` | `swimFerroUISetAlignment` | text alignment |
| `ferrouiSetHidden(handle:hidden:)` | `swimFerroUISetHidden` | visibility |
| `ferrouiSetOpacity(handle:percent:)` | `swimFerroUISetOpacity` | opacity |
| `ferrouiSetProgress(handle:percent:)` | `swimFerroUISetProgress` | value of a bar/slider (0…100) |
| `ferrouiSetValue(handle:value:)` | `swimFerroUISetValue` | value of a slider (0…100) |
| `ferrouiSetChecked(handle:checked:)` | `swimFerroUISetChecked` | check state |
| `ferrouiSetSpacing(handle:spacing:)` | `swimFerroUISetSpacing` | stack spacing |

### Events and timers

| Swift | Nim | Event |
| --- | --- | --- |
| `ferrouiOnTap(handle:onTap:)` | `swimFerroUIOnTap` | a click of a button, a tap of any other control |
| `ferrouiOnTextChanged(handle:onChanged:)` | `swimFerroUIOnTextChanged` | a text field changed |
| `ferrouiOnCheckedChanged(handle:onChanged:)` | `swimFerroUIOnCheckedChanged` | a check box changed |
| `ferrouiOnValueChanged(handle:onChanged:)` | `swimFerroUIOnValueChanged` | a slider/bar value changed |
| `ferrouiAfter(ms:action:)` | `swimFerroUIAfter` | runs once, `ms` later, on the UI thread |
| `ferrouiRaiseClick(handle:)` | `swimFerroUIRaiseClick` | runs the click handlers as a pointer would (test helper) |

Every subscription lives until the application ends.  All callbacks run on the
UI thread, so they may set properties directly.

### Diagnostics

| Swift | Nim | What it returns |
| --- | --- | --- |
| `ferrouiVersion()` | `swimFerroUIVersion` | the bridge and FerroUI version |
| `ferrouiBridgePath()` | `swimFerroUIBridgePath` | where the bridge library was found |
| `ferrouiLog(message:)` | `swimFerroUILog` | prints a line to the console |
| `ferrouiRelease(handle:)` | `swimFerroUIRelease` | drops the reference a handle holds |

## Colours, alignment and handles

- **Colours** are `Int`s: `0xRRGGBB` for an opaque colour, `0xAARRGGBB` for one
  with alpha.  `-1` (`clearColor` in the view layer) leaves a brush unset, so a
  panel stays transparent.
- **Alignment** of text: `alignLeft = 0`, `alignCenter = 1`, `alignRight = 2`.
- **Handles** are `Int`s; `0` is the null handle.  A handle keeps its control
  alive; a control of the visual tree is also kept alive by its parent.  A
  handle of the window stays valid until the application ends.

## Reading properties back

| Swift | Nim | Reads |
| --- | --- | --- |
| `ferrouiGetValue(handle:)` | `swimFerroUIGetValue` | the value of a slider/progress bar (`Double`) |
| `ferrouiGetText(handle:)` | `swimFerroUIGetText` | the text of a label/field or the title of a button |
| `ferrouiGetChecked(handle:)` | `swimFerroUIGetChecked` | whether a check box is checked |
| `ferrouiGetVisible(handle:)` | `swimFerroUIGetVisible` | whether a control is visible |

A failed call of the bridge (a property a control does not have, an invalid
handle) is reported on the error stream as
`swimferroui: <where>: <what failed>` and the program continues; the tests fail
on such a line.

## Timers, snapshots and test builds

`ferrouiAfter(ms:action:)` runs a closure once on the UI thread.  For automated
checks the runtime understands two compile-time defines (pass them with
`--nim-arg:-d:<name>=<value>`):

| Define | Meaning |
| --- | --- |
| `swimFerroUIImage=<path>` | `ferrouiImagePath()` returns `<path>`; the program writes a PNG of its window there with `ferrouiSnapshot(after:path:)` |
| `swimFerroUIQuitMs=<ms>` | `ferrouiAutoQuitMs()` returns `<ms>`; `scripts/run-demo.sh --snapshot` passes it so the window closes by itself |

`ferrouiSnapshot(after:path:)` renders the window into a PNG off the main
layout: the window must have been shown (schedule it from `onReady`, not before),
and the delay lets the layout and the styles settle.  This is what produced
[`ui/shots/demo.png`](../ui/shots/demo.png) and what
`tests/binding_test.py` checks.

## The Swift-style view layer (ui/SwimUI.sw)

`ui/SwimUI.sw` is a Swim module (not part of the compiler) that wraps the flat
functions in a `View` class and a `Screen` class.  A program imports it with
`import SwimUI`; it imports `FerroUI` itself.

```swift
import SwimUI

setThemeVariant("dark")

runApp {
    let screen = Screen(width: 390, height: 844, title: "Library",
                        background: 0x0B0C10, borderless: true)
    screen.onReady {
        let row = screen.panel(x: 24, y: 466, width: 342, height: 66,
                               color: 0x151824, radius: 16)
        row.label(x: 68, y: 12, width: 200, height: 20, text: "IMG_0032",
                  size: 15, bold: true)
        row.label(x: 68, y: 34, width: 200, height: 18, text: "Today - 2.8 MB",
                  size: 12, color: 0x8A90A2)
        row.onTap { printLog("row tapped") }
    }
}
```

- `Screen(width:height:title:background:borderless:)` — the window; `onReady`
  runs once it is up (`clientWidth()`/`clientHeight()` give the client area,
  `snapshot(after:path:)` writes a PNG, `close()` closes the window).
- `View` factories (all return a `View`): `panel(x:y:width:height:color:radius:
  borderColor:borderWidth:)`, `scrollView(...)`, `stack(x:y:width:height:
  vertical:spacing:)`, `label(x:y:width:height:text:size:color:align:bold:)`,
  `button(x:y:width:height:title:fill:titleColor:radius:size:bold:onTap:)`,
  `textField(x:y:width:height:text:placeholder:size:onChanged:)`,
  `checkBox(x:y:width:height:text:checked:onChanged:)`,
  `slider(x:y:width:height:minimum:maximum:value:onChanged:)`,
  `progressBar(x:y:width:height:percent:)`.
- `View` methods: `setText`, `setColor`, `setTextColor`, `setBorder`,
  `setRadius`, `setFontSize`, `setBold`, `setAlignment`, `setProgress`,
  `setValue`, `setChecked`, `setSpacing`, `setVisible`, `setOpacity`,
  `setFrame`, `text()`, `value()`, `isChecked()`, `isVisible()`, `onTap`,
  `onTextChanged`, `onCheckedChanged`, `onValueChanged`, `raiseTap`.
- Free functions: `runApp { ... }`, `after(ms) { ... }`, `quitApp()`,
  `printLog(...)`, `setThemeVariant(...)`, `imagePath()`, `autoQuitMs()`,
  `swimUIVersion()`.

The view layer is deliberately small: it is the shape the nimx demo used, so
the two GUI demos of the repository are comparable.

## The C ABI of the bridge

`ffi/include/ferroui_swim.h` is the contract between the Nim module and the
Rust crate.  It is flat and free of Rust types:

- **Kinds** (`ferro_swim_create`): canvas, stack panel, border, text block,
  button, text box, check box, slider, progress bar, scroll viewer.
- **Double properties** (`ferro_swim_set_f64`): width, height, min/max width
  and height, font size, opacity, corner radius, spacing, minimum, maximum,
  value, line height.
- **String properties** (`ferro_swim_set_str`): text, title, watermark,
  content.
- **Boolean properties** (`ferro_swim_set_bool`): visible, checked,
  indeterminate, enabled.
- **Brush properties** (`ferro_swim_set_color`, `0xAARRGGBB`): background,
  foreground, border.
- **Thickness properties** (`ferro_swim_set_thickness`): margin, padding,
  border thickness.
- **Enum properties** (`ferro_swim_set_enum`): horizontal/vertical alignment,
  orientation, text alignment, text wrapping, font weight, font style.
- **Events** (`ferro_swim_on`): tap, text changed, checked changed, value
  changed, opened, closed.
- **Reads** (`ferro_swim_get_f64` / `_str` / `_bool`).

Other functions: `ferro_swim_run`, `ferro_swim_quit`,
`ferro_swim_set_theme_variant`, `ferro_swim_window`,
`ferro_swim_client_width`/`_height`, `ferro_swim_set_decorations`,
`ferro_swim_add_child`, `ferro_swim_set_frame`, `ferro_swim_after`,
`ferro_swim_snapshot`, `ferro_swim_raise_click`, `ferro_swim_release`,
`ferro_swim_version`, `ferro_swim_abi_version`, `ferro_swim_last_error`.

The Nim side checks `ferro_swim_abi_version` on the first call and refuses a
library whose ABI it does not know.

## Adding a control

The four sides of a new control, by the example of a toggle switch:

1. **Rust** — in `ffi/src/controls.rs`, add a kind constant, a constructor in
   `create()`, and the setters the control needs in `set_f64` / `set_str` /
   … (cast the handle to the FerroUI class and call its typed setter, so a
   property the control lacks is a reported error, not a silent no-op).  Add a
   `ferro_swim_*` export in `ffi/src/lib.rs` only for a new kind of operation.
2. **Nim** — in `runtime/swimferroui.nim`, add the Swift-facing procedure that
   composes the C calls (a constructor is usually `newControl` + frame + the
   property calls), next to the others.
3. **Compiler** — add the entry to `FERROUI_FUNCS` in `src/swimc/codegen.py`:
   the Swift name, the Nim procedure, `[(label, kind)]` in positional order and
   the return kind.  The kinds are `int`, `double`, `string`, `bool` and
   `closure`.
4. **View layer** — add the factory/method in `ui/SwimUI.sw`.
5. **Tests** — add the control to `tests/binding/BindingTest.sw` (create it,
   change a property, read it back) and, if it has an event, raise it.

`make test-binding` then checks the whole chain.

## Limitations

- One window per program, created inside the `ferrouiRun` block.
- The binding exposes a curated set of controls (the ones above).  FerroUI has
  many more — grids, lists, menus, pickers, charts — and each one needs the
  four steps above.
- Layout: a canvas with absolute positions, plus stack panels.  FerroUI's
  `Grid`, alignments and margins are available through the ABI's enum and
  thickness properties but are not surfaced by the view layer.
- No data binding, no styles/selectors from the program, no XAML, no
  animations or transitions, no dialogs, no clipboard/drag-and-drop.
- Custom drawing (a `Canvas`-painted scene) is not exposed; a control's
  appearance comes from its theme.
- The bridge is debug-built by default (fast to iterate, large and slower than
  a release build).  `scripts/build-ffi.sh --release` builds the optimised one.
- Interactions are real FerroUI input events; the automated test drives events
  by raising a click, not by synthesising pointer input.
