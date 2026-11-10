# The `FerroUI` native module

This document is the reference of the binding at the centre of SwimUI: what a
`.sw` program sees when it writes `import FerroUI`, how the compiler knows the
module, what the C shim and the Rust bridge do, and how to add a function.

- [The four sides](#the-four-sides)
- [The compiler's part](#the-compilers-part)
- [The functions](#the-functions)
- [Identifiers and values](#identifiers-and-values)
- [The application lifecycle](#the-application-lifecycle)
- [Closures](#closures)
- [Errors](#errors)
- [Tests and documentation runs](#tests-and-documentation-runs)
- [The C shim](#the-c-shim)
- [The Rust bridge](#the-rust-bridge)
- [Adding a function](#adding-a-function)
- [Limitations](#limitations)

---

## The four sides

```
  .sw source        import FerroUI  →  the compiler emits `#include
        │              "swimferroui.h"` and calls of the `swimferroui_*` shim
  runtime/swimferroui.c           the C shim: SwimValue ↔ the flat C ABI,
        │                         colours, closure cells, error reporting
  build/libferroui_swim.dylib     the Rust bridge (ffi/): application, tree,
        │                         window, properties, events
  FerroUI (Rust)                  the framework itself
```

The language itself never sees C: a `.sw` file uses `Int`, `Double`, `String`,
`Bool` and `() -> Void` and the `ferroui*` names of the module.

## The compiler's part

`import FerroUI` is a *native module* of the SwimUI fork of Swim.  Four places
know about it:

| Place | What it does |
| --- | --- |
| `src/swimc/modules.py` | `NATIVE_MODULES = {"FerroUI": ...}`; the import is recorded on the project and the Nim-era `Nimx`/`Zeta` are rejected with an explanation |
| `src/swimc/native_ferroui.py` | `FERROUI_FUNCS`: the table of the module — Swift name → (C function, `[(label, kind)]`, result kind), plus the shim file names and the library name |
| `src/swimc/checker.py` | `infer_native_call`: the import is required, labels must exist, arguments must be present once and have the kind's type (`int`, `double`, `string`, `bool`, `closure`) |
| `src/swimc/codegen_c.py` | emits `#include "swimferroui.h"` when the module is imported and turns each call into a direct C call with the arguments in the table's order |
| `src/swimc/cli.py` | compiles `runtime/swimferroui.c` into the program, adds `ffi/include` to the include path, links `-L build -lferroui_swim` (plus an rpath) and covers the shim and headers in the build cache key |

So a program needs no manual C flags: `Swim build app.sw -o app` produces an
executable that loads `build/libferroui_swim.dylib` next to it (or
`$SWIM_FERROUI_LIB_DIR`).  `Swim emit` shows the C, including the shim calls.

## The functions

The Swift names are the ones in `native_ferroui.FERROUI_FUNCS`; each maps to the
C function of the shim of the same name (`ferrouiRun` → `swimferroui_run`).

### Application

| Swift | Arguments | Result |
| --- | --- | --- |
| `ferrouiRun` | `build: () -> Void` (trailing closure allowed) | — |
| `ferrouiQuit` | — | — |
| `ferrouiAfter` | `ms: Int`, `action: () -> Void` | — |
| `ferrouiLog` | `message: String` | — |
| `ferrouiVersion` | — | `String` |
| `ferrouiSetThemeVariant` | `name: String` (`"dark"`, `"light"`, `"system"`); call before `ferrouiRun` | — |

### Window

| Swift | Arguments | Result |
| --- | --- | --- |
| `ferrouiWindow` | `width: Int`, `height: Int`, `title: String`, `background: Int`, `onClosed: () -> Void` | `Int` (handle) |
| `ferrouiClientWidth` / `ferrouiClientHeight` | — | `Int` |
| `ferrouiSetDecorations` | `window: Int`, `mode: Int` (0 none, 2 full) | — |
| `ferrouiOnReady` | `window: Int`, `onReady: () -> Void` | — |
| `ferrouiClose` | `window: Int` | — |
| `ferrouiSnapshot` | `delayMs: Int`, `path: String` | — |

### Tree

| Swift | Arguments | Result |
| --- | --- | --- |
| `ferrouiCreate` | `parent: Int`, `kind: Int` | `Int` |
| `ferrouiAddChild` | `parent: Int`, `child: Int` | — |
| `ferrouiInsertChild` | `parent: Int`, `index: Int`, `child: Int` | — |
| `ferrouiRemoveChild` | `parent: Int`, `child: Int` | — |
| `ferrouiClearChildren` | `parent: Int` | — |
| `ferrouiDestroy` | `handle: Int` | — |

A control created with a `parent` is added to it: a panel gets a child, a
border/scroll view/window/button gets its content.  `ferrouiAddChild` on the
window sets the window's content.

### Properties

| Swift | Arguments |
| --- | --- |
| `ferrouiSetF64` | `handle: Int`, `property: Int`, `value: Double` |
| `ferrouiSetI32` | `handle: Int`, `property: Int`, `value: Int` |
| `ferrouiSetString` | `handle: Int`, `property: Int`, `value: String` |
| `ferrouiSetBool` | `handle: Int`, `property: Int`, `value: Bool` |
| `ferrouiSetColor` | `handle: Int`, `property: Int`, `argb: Int` |
| `ferrouiSetThickness` | `handle: Int`, `property: Int`, `left/top/right/bottom: Int` |
| `ferrouiSetEnum` | `handle: Int`, `property: Int`, `value: Int` |
| `ferrouiSetFlex` | `handle: Int`, `direction/justify/align: Int`, `columnSpacing/rowSpacing: Int` |
| `ferrouiSetGrow` | `handle: Int`, `grow: Double` |
| `ferrouiSetFrame` | `handle: Int`, `x/y/width/height: Int` (a canvas position and size) |

Reads: `ferrouiGetValue(handle:) -> Double`, `ferrouiGetText(handle:) -> String`,
`ferrouiGetChecked(handle:) -> Bool`, `ferrouiGetVisible(handle:) -> Bool`.

### Events

| Swift | Arguments |
| --- | --- |
| `ferrouiOnTap` | `handle: Int`, `action: () -> Void` (a button click, or a tap on any other control) |
| `ferrouiOnTextChanged` | `handle: Int`, `action: () -> Void` |
| `ferrouiOnCheckedChanged` | `handle: Int`, `action: () -> Void` |
| `ferrouiOnValueChanged` | `handle: Int`, `action: () -> Void` |

All callbacks run on the UI thread.  A subscription lives until the application
ends.

### Tests

| Swift | Arguments | Result |
| --- | --- | --- |
| `ferrouiRaiseClick` | `handle: Int` | — (raises a button click as a pointer would) |
| `ferrouiImagePath` | — | `String` (the `SWIMUI_IMAGE` environment variable) |
| `ferrouiAutoQuitMs` | — | `Int` (the `SWIMUI_QUIT_MS` environment variable) |

## Identifiers and values

### Control kinds (`ferrouiCreate`)

| Value | Control |
| --- | --- |
| 1 | `Canvas` (children at absolute positions) |
| 2 | `StackPanel` |
| 3 | `Border` (single content; background, corners, border, padding) |
| 4 | `TextBlock` |
| 5 | `Button` |
| 6 | `TextBox` |
| 7 | `CheckBox` |
| 8 | `Slider` |
| 9 | `ProgressBar` |
| 10 | `ScrollViewer` |
| 11 | `Panel` (children on top of each other) |
| 12 | `FlexPanel` (row/column flex layout) |
| 13 | `ToggleSwitch` |

### Double properties (`ferrouiSetF64`)

`1` width, `2` height, `3` min width, `4` min height, `5` max width, `6` max
height, `7` font size, `8` opacity, `9` corner radius, `10` spacing, `11`
minimum, `12` maximum, `13` value, `14` line height.

### Int properties (`ferrouiSetI32`)

`1` max lines (text blocks).

### String properties (`ferrouiSetString`)

`1` text, `2` title, `3` watermark/placeholder, `4` content (a button or check
box title).

### Bool properties (`ferrouiSetBool`)

`1` visible, `2` checked, `3` indeterminate, `4` enabled, `5` clip to bounds.

### Brush properties (`ferrouiSetColor`)

`1` background, `2` foreground, `3` border.  The value is `0xRRGGBB` or
`0xAARRGGBB`; a negative value leaves the brush unset.

### Thickness properties (`ferrouiSetThickness`)

`1` margin, `2` padding, `3` border thickness.

### Enum properties (`ferrouiSetEnum`)

| Property | Values |
| --- | --- |
| 1 horizontal alignment | 0 stretch, 1 left, 2 center, 3 right |
| 2 vertical alignment | 0 stretch, 1 top, 2 center, 3 bottom |
| 3 orientation | 0 horizontal, 1 vertical |
| 4 text alignment | 0 leading, 1 center, 2 trailing |
| 5 text wrapping | 0 no wrap, 1 wrap, 2 wrap with overflow |
| 6 font weight | 100…900 (`400` regular, `700` bold) |
| 7 font style | 0 normal, 1 italic, 2 oblique |

### Flex (`ferrouiSetFlex`, `ferrouiSetGrow`)

Direction `0` row, `1` row-reverse, `2` column, `3` column-reverse; justify `0`
start, `1` end, `2` center, `3` space-between, `4` space-around, `5`
space-evenly; align-items `0` start, `1` end, `2` center, `3` stretch.
`ferrouiSetGrow` sets the flex grow factor of a child of a flex panel — that is
how a `Spacer` pushes the ends of a row apart.

## The application lifecycle

FerroUI is an application framework: the platform exists only after the
application starts, and controls and windows are created after that.  A program
starts it with

```swift
ferrouiSetThemeVariant(name: "dark")   // optional, before run

ferrouiRun {
    // the framework is initialized here: build the window and the controls
}
```

`ferrouiRun` blocks until the window closes.  Inside the block the program makes
the window with `ferrouiWindow` (one window per program) and everything else
with `ferrouiCreate`.

The *client* area of the window may be smaller than the size that was asked for
(the decorations and the screen take room), and the final size is known when the
window is open:

```swift
ferrouiOnReady(window: handle) {
    let height = ferrouiClientHeight()   // what the layout must fit in
}
```

The SwiftUI-shaped layer wraps this shape as `launch(WindowGroup(...))`: it
calls `ferrouiOnReady` itself and renders the view tree there.

## Closures

A closure argument (`() -> Void`, the last parameter, so a trailing closure
works) becomes a `SwimValue` closure that the shim retains and the bridge calls
back on the UI thread.  A subscription lives until the application ends.

One language trap: a closure *stored in a property* must be bound to a local
before it is called, otherwise the call compiles to a method lookup and does
nothing:

```swift
let action = view.tapAction!   // read it into a local…
action()                       // …then call it
```

## Errors

A failed bridge call (a property a control does not have, an invalid handle, a
wrong kind) is reported on the error stream as

```
swimferroui: <where>: <what failed>
```

and the program continues.  The tests fail on any such line.  A missing bridge
library fails at link time with the library path; a mismatched bridge ABI is
reported at start-up by the shim and exits with status 1.

## Tests and documentation runs

A program reads the environment at run time to drive itself without a person:

| Variable | Use |
| --- | --- |
| `SWIMUI_IMAGE` | `ferrouiImagePath()` returns it; a program writes a PNG of the window there with `ferrouiSnapshot` |
| `SWIMUI_QUIT_MS` | `ferrouiAutoQuitMs()` returns it; a program closes the window after that time |
| `SWIMUI_THEME_VARIANT` | the theme variant, read by the bridge at start-up |

That is what produced [`ui/shots/demo.png`](../ui/shots/demo.png) and what
`tests/binding_test.py` uses.

## The C shim

`runtime/swimferroui.h` declares one `SwimValue` function per table entry (all
arguments and results are `SwimValue`, void functions return `SwimVoid()`); the
compiler emits those calls.  `runtime/swimferroui.c` implements them:

- it unboxes numbers (`SwimUnboxInt`, `SwimUnboxDouble`, `SwimUnboxBool`), copies
  string bytes out with a NUL (`SwimStringData`/`SwimStringLen`) and turns
  colours into `0xAARRGGBB`;
- it keeps a `() -> Void` closure in a heap cell and passes a C trampoline plus
  the cell's address to the bridge (`ferro_swim_cb` with an `int64_t user`);
  the trampoline runs the closure with `SwimCallValue`;
- it reports what the bridge complains about (`ferro_swim_last_error`), checks
  the ABI version at start-up, and implements the environment-variable test
  hooks.

The shim is compiled into every program that imports the module, so it costs one
translation unit; the bridge is a shared library built once.

## The Rust bridge

`ffi/` is the crate `ferroui-swim`, a `cdylib` with a flat C ABI described in
`ffi/include/ferroui_swim.h`:

- the application (`AppBuilder` + the simple theme, `ferroui_base`/`ferroui_controls`/
  `ferroui_desktop`), the main window, the classic desktop lifetime;
- a handle registry: every live control has an opaque `int64_t` handle; the
  registry keeps it alive while the handle is not destroyed;
- typed property setters that cast the handle to the FerroUI class that declares
  the property (a property the control lacks is an error, not a silent no-op);
- events (tap/click, text changed, checked changed, value changed, opened,
  closed) and timers (`DispatcherTimer`), with subscriptions kept alive for the
  application's lifetime;
- flex layout (`FlexPanel` + the `Flex` attached properties), tree operations
  (insert/remove/clear/destroy), panels and toggle switches;
- snapshots: `RenderTargetBitmap` renders the window into a PNG;
- `ferro_swim_version`, `ferro_swim_abi_version`, `ferro_swim_last_error`.

Build it with `scripts/build-ffi.sh`; `FERROUI_DIR` selects the checkout it is
built against and the cargo target directory defaults to that checkout's, so the
artifacts of a FerroUI build are reused.  The header documents every function,
kind and property value.

## Adding a function

The four sides, by the example of a new property:

1. **Rust** — if the operation is new (not a property through the existing
   setters), add a `ferro_swim_*` export in `ffi/src/lib.rs` and implement it in
   `ffi/src/controls.rs`, `events.rs`, `app.rs` or `snapshot.rs`; update
   `ffi/include/ferroui_swim.h` (the ABI version stays 1 for additions that the
   shim checks).
2. **C shim** — declare `swimferroui_<name>` in `runtime/swimferroui.h` and
   implement it in `runtime/swimferroui.c`: convert the `SwimValue`s, call the
   bridge, return `SwimValue`; use `swimferroui_report` after the call.
3. **Compiler** — add the entry to `src/swimc/native_ferroui.py`'s
   `FERROUI_FUNCS`: Swift name, C function, labels and kinds, result kind.  The
   checker and the code generator pick it up automatically.
4. **Tests** — add the call to `tests/binding/NativeTest.sw` (and the expected
   line to `tests/binding_test.py`), or to the SwiftUI layer test if the layer
   uses it.

## Limitations

- one window per program, created inside `ferrouiRun`;
- a curated set of controls: no `Grid`, `ItemsControl`/`ListBox`, menus,
  pickers, charts, dialogs, media;
- no data binding, styles/selectors from the program, XAML, animations or
  transitions;
- no custom drawing: a control's look comes from its theme (the simple theme by
  default; the bridge adds it, and the variant is dark/light/system);
- all calls and callbacks run on the UI thread (the thread that called
  `ferrouiRun`); there is no thread-safe handle API;
- the bridge is debug-built by default (fast to iterate, large); build it with
  `scripts/build-ffi.sh --release` for an optimised one.
