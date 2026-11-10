# The SwiftUI-shaped layer (`examples/ui/SwimUI.sw`)

`import SwimUI` (the module `examples/ui/SwimUI.sw`) gives a declarative,
SwiftUI-shaped API on top of the
`FerroUI` native module.  It is an ordinary Swim module — the compiler knows
nothing about it — and it works in three stages: **build** a view tree, **mount**
it as FerroUI controls, and **patch** the mounted controls when state changes.

- [A first app](#a-first-app)
- [How it works](#how-it-works)
- [The API](#the-api)
- [State and re-rendering](#state-and-re-rendering)
- [Layout](#layout)
- [Test helpers](#test-helpers)
- [Where it differs from SwiftUI](#where-it-differs-from-swiftui)
- [Gotchas](#gotchas)
- [Adding a view](#adding-a-view)

## A first app

```swift
import SwimUI

final class CounterModel {
    let count = State(0)
}

let counterModel = CounterModel()

func CounterView(_ model: CounterModel) -> View {
    VStack(spacing: 16) {
        Text("Count: \(model.count.value)").font(.largeTitle)
        HStack(spacing: 8) {
            Button("Add") {
                model.count.value = model.count.value + 1
            }
            .buttonStyle(.borderedProminent)
            Button("Reset") {
                model.count.value = 0
            }
        }
    }
    .padding(24)
}

@main
struct CounterApp {
    var body: Scene {
        WindowGroup("Counter", width: 390, height: 500,
                    background: Color.surface) {
            CounterView(counterModel)
        }
    }

    static func main() {
        setThemeVariant("light")
        launch(CounterApp().body)
    }
}
```

`examples/ui/CounterApp.sw` is this program; `examples/ui/LibraryApp.sw` is the
full demo.

## How it works

**Build.**  A view expression constructs `View` nodes.  A container pushes a
*builder* (a small collection), runs its content closure, and every view
constructed inside appends itself to the innermost builder; the container then
keeps the collected children.  `Group` and `ForEach` splice their children into
the enclosing builder instead of adding a node of their own, so `ForEach` and
`if`/`else` inside a container produce the expected children without a result
builder in the language:

```swift
VStack {
    ForEach(model.rows) { row in
        if row.selected.value {
            Text("selected")
        } else {
            Text(row.title)
        }
    }
}
```

`emit(_:)` (called by every constructor) is what appends a node; modifiers are
plain methods that set fields on the node and return the same node, so
`Text("a").font(.title).bold()` stays one node.

**Mount.**  A node becomes controls.  Every node mounts as a FerroUI `Border`
wrapper (its padding, background, border and corner radius) around one *host*
control: `Text` → `TextBlock`, `Button` → `Button`, `TextField` → `TextBox`,
`Toggle` → `ToggleSwitch`, `Slider` → `Slider`, `ProgressView` →
`ProgressBar`, `VStack`/`HStack` → a `FlexPanel`, `ZStack` → a `Panel`,
`List`/`ScrollView` → a `ScrollViewer` containing a `FlexPanel`, shapes,
`Spacer`, `Divider` → an empty `Panel`.  Children are added to the host (or to
the inner panel of a list).

**Patch.**  `State.value` writes schedule one re-render.  The render builds the
tree again and walks it against the mounted tree in lockstep: the same kind at
the same position keeps its controls and only its properties are set again
(identity and focus survive), a different kind replaces that subtree.  This is
why a `TextField` keeps its focus while another part of the screen changes, and
why the tests can read the text back out of the mounted controls.

## The API

### Types

| Type | Use |
| --- | --- |
| `View` | a view node; every constructor returns one, every modifier returns it |
| `State<T>` | observable state: `let count = State(0)`, read `count.value` |
| `Color` | `Color(0xRRGGBB)` / `Color(0xAARRGGBB)`; static colours: `.clear`, `.white`, `.black`, `.red`, `.orange`, `.green`, and the theme-aware `.primary`, `.secondary`, `.accent`, `.background`, `.surface`, `.surface2` (light values by default, dark after `setThemeVariant("dark")`) |
| `Font` | `.largeTitle`, `.title`, `.title2`, `.title3`, `.headline`, `.body`, `.callout`, `.subheadline`, `.footnote`, `.caption`, `.caption2` |
| `HorizontalAlignment` | `.leading`, `.center`, `.trailing` (VStack) |
| `VerticalAlignment` | `.top`, `.center`, `.bottom` (HStack) |
| `Alignment` | `.center`, `.topLeading`, `.top`, `.topTrailing`, `.leading`, `.trailing`, `.bottomLeading`, `.bottom`, `.bottomTrailing` (ZStack) |
| `TextAlignment` | `.leading`, `.center`, `.trailing` |
| `Axis` | `.vertical`, `.horizontal` |
| `ButtonStyle` | `.plain`, `.bordered`, `.borderedProminent` |
| `Edge` | `.top`, `.bottom`, `.leading`, `.trailing`, `.horizontal`, `.vertical`, `.all` |
| `Scene` | the window description; `WindowGroup(...)` returns one |

### Views

| Constructor | What it is |
| --- | --- |
| `Text(_ content: String)` | a line of text |
| `Button(_ title: String, _ action: () -> Void)` | a themed button |
| `TextField(_ placeholder: String, text: State<String>)` | an editable field bound to state |
| `Toggle(_ title: String, isOn: State<Bool>)` | a switch with a title |
| `Slider(value: State<Double>, minimum: Double = 0.0, maximum: Double = 1.0)` | a slider bound to state |
| `ProgressView(value: Double = -1.0, total: Double = 100.0)` | a progress bar; `ProgressView()` is indeterminate |
| `VStack(alignment: HorizontalAlignment = .center, spacing: Int = 8) { }` | a vertical stack |
| `HStack(alignment: VerticalAlignment = .center, spacing: Int = 8) { }` | a horizontal stack |
| `ZStack(alignment: Alignment = .center) { }` | views on top of each other |
| `List { }` | a scrollable column of rows |
| `ScrollView(_ axis: Axis = .vertical) { }` | a scrollable area |
| `Spacer(minLength: Int = 0)` | flexible space in a stack |
| `Divider()` | a one-point separator |
| `RoundedRectangle(cornerRadius: Int = 8)`, `Rectangle()`, `Circle()` | shapes; give them a frame and a fill |
| `Group { }`, `ForEach(items) { item in }` | children without a view of their own |

### Modifiers

| Modifier | Effect |
| --- | --- |
| `.padding(_ value: Int = 16)` / `.padding(_ horizontal: Int, _ vertical: Int)` / `.padding(_ edge: Edge, _ value: Int)` | space around the content |
| `.background(_ color: Color)` | a fill behind the content |
| `.foregroundColor(_ color: Color)` | the colour of the text (and of a shape's fill); inherited by children |
| `.fill(_ color: Color)` | the fill of a shape |
| `.cornerRadius(_ radius: Int)` | rounded corners of the background |
| `.border(_ color: Color, width: Int = 1)` | a border |
| `.frame(width:height:minWidth:minHeight:maxWidth:maxHeight:)` | the size of the view; `-1` leaves a dimension to the layout |
| `.font(_ font: Font)` / `.font(size: Int)` | the text style or size |
| `.bold()` | a bold weight |
| `.opacity(_ value: Double)` | opacity, 0…1 |
| `.hidden()` | hide the view |
| `.disabled(_ flag: Bool = true)` | disable the controls of the view |
| `.clipped()` | cut the content at the bounds |
| `.lineLimit(_ count: Int)` | at most `count` lines of text |
| `.multilineTextAlignment(_ alignment: TextAlignment)` | the alignment of the lines |
| `.onTapGesture(_ action: () -> Void)` | run `action` when the view is tapped |
| `.buttonStyle(_ style: ButtonStyle)` | the look of a button |
| `.layoutGrow(_ factor: Double)` | the flex grow factor of the view in its stack |
| `.expand()` | fill the room the container gives the view |

### Application and helpers

| Function | Use |
| --- | --- |
| `WindowGroup(_ title: String, width: Int, height: Int, background: Color, borderless: Bool, _ content: () -> Void) -> Scene` | the window |
| `launch(_ scene: Scene)` | start the application (blocks until the window closes) |
| `runApp(_ title:width:height:_ content:)` | a shortcut for small programs |
| `setThemeVariant(_ name: String)` | `"light"` (the default of the examples), `"dark"` or `"system"`; switches the FerroUI theme and the palette; call before `launch` |
| `clientWidth()`, `clientHeight()` | the client area of the window |
| `snapshot(after:path:)` | a PNG of the window, `milliseconds` from now |
| `after(_ milliseconds: Int, _ action: () -> Void)` | run once, later, on the UI thread |
| `quitApp()` | end the application |
| `printLog(_ message: String)` | a line on the console |
| `swimUIVersion()`, `imagePath()`, `autoQuitMs()` | diagnostics and test-run settings |

## State and re-rendering

State lives in `State<T>` objects.  A write to `value` calls `invalidate()`,
which schedules one re-render (coalesced: many writes in one callback cause one
pass).  The app's content closure is built again and the mounted tree is
patched, so the controls keep their identity:

```swift
final class LibraryModel {
    let albums = State(12)
    let rows = [PhotoRow("IMG_0032.HEIC"), PhotoRow("portrait.jpg")]
}

Button("+") { model.albums.value = model.albums.value + 1 }
Text("\(model.albums.value) albums")            // updates by itself
```

Writes made while a render is running are collected and applied in one more
pass, so assigning state from a view body never re-enters the render.  Writes
before the window exists are ignored (nothing is mounted yet).

## Layout

Layout is FerroUI's: stacks are `FlexPanel`s (main axis by direction, cross axis
by `align_items`, spacing, child grow), and every view is a `Border` wrapper
whose desired size is its content plus padding.

- `.expand()` fills the room the parent gives the view.  In a `VStack` it makes
  the child full width; in an `HStack` full height; in a stack with an expanded
  child, the whole line stretches on the cross axis.  This is the stand-in for
  SwiftUI's `.frame(maxWidth: .infinity)`.
- `Spacer()` grows in the main axis of the stack (flex `grow: 1`), which is how
  a row pushes its ends apart.
- `.frame(width:)` / `.frame(height:)` fix a dimension; `.frame(minWidth:…)` /
  `.frame(maxWidth:…)` bound it.
- Text wraps at the width the layout gives it, since the layer always enables
  wrapping.

Known limitations of the mapping: there is no baseline alignment, no
`.frame(alignment:)`, no per-child cross-axis stretch other than `.expand()`,
and grid layout is not exposed (FerroUI has it behind the bridge; the layer does
not use it).

## Test helpers

The layer can be driven by a machine, which is what `tests/binding_test.py`
uses:

| Function | Use |
| --- | --- |
| `renderedTexts() -> String` | the text of every label, field and button in the mounted tree, separated by `\|` |
| `tapButton(_ title: String) -> Bool` | raise the click of the first button with that title, as a pointer would |
| `tapKind(_ kind: Int) -> Bool` | raise the tap of the first view of that kind |
| `controlValue(_ kind: Int) -> Double` | the value of the first slider/progress bar (`viewSlider` is 5, `viewProgress` is 6) |

Plus the run-time environment variables `SWIMUI_IMAGE` (where the program
snapshots itself) and `SWIMUI_QUIT_MS` (when it closes).

## Where it differs from SwiftUI

| SwiftUI | Here | Why |
| --- | --- | --- |
| `struct ContentView: View { var body: some View { … } }` | `func ContentView(_ model: Model) -> View { … }` | Swim protocols have no associated types, so a protocol-typed `body` cannot be expressed; usage inside a stack is the same |
| `@State`, `@Binding`, `@ObservedObject` | `State<T>` objects, passed as parameters | no property wrappers in the language |
| `@main struct App: App { var body: some Scene }` | `@main struct App { var body: Scene { WindowGroup(...) } ; static func main() { launch(App().body) } }` | `@main` calls a `static func main()`; the `App` protocol has no default implementation |
| `.frame(maxWidth: .infinity)` | `.expand()` | no infinity literal in the layer |
| `Slider(value: $x, in: 0...100)` | `Slider(value: model.x, minimum: 0.0, maximum: 100.0)` | `in` is a keyword; `$` projections do not exist |
| `.animation`, transitions, `.transition` | — | no animation API in the binding |
| `NavigationStack`, sheets, alerts | — | one window, no navigation |
| `Grid`, `LazyVGrid`, `.overlay(alignment:)` | — | not exposed |
| result builders (`@ViewBuilder`) | the same trailing-closure syntax | the layer uses a builder stack behind the closure |

## Gotchas

These come from the language and the runtime, not from the idea of the layer:

- **Do not call a closure stored in a property directly** (`node.action()`):
  the generated call becomes a method lookup and silently does nothing.  Bind it
  to a local first (`let action = node.action!; action()`); the layer does this
  everywhere.
- **Do not overload two methods with the same name where one has defaulted
  parameters.**  The runtime binds the first entry whose labels it can satisfy,
  so `.frame(height: 6)` would bind `frame(width:height:)` with a defaulted
  width.  The layer therefore declares one `frame`, one `padding` pair and one
  `ProgressView` with defaults.
- **Enum cases as arguments** need the compiler fix of this fork
  (`tests/cases/43_enum_case_argument.sw`), otherwise `.leading` is emitted
  untyped and the dynamic call fails.
- State writes from inside a view body are collected for the next pass; do not
  rely on them being visible in the same pass.
- Text fields write their state on every keystroke and the patch reuses the same
  `TextBox`, so the focus and the caret survive; a brand new `TextBox` at a
  changed position loses the focus.

## Adding a view

1. **Node kind** — add a `viewX` constant next to the others in
   `examples/ui/SwimUI.sw`.
2. **Constructor** — a function that creates `View(viewX)`, sets its fields and
   calls `emit` (that is what appends it to the enclosing container).
3. **Host** — map the kind in `createHost` to a FerroUI kind of the bridge
   (`ffi/include/ferroui_swim.h`).
4. **Properties** — set them in `applyView` (and any event subscription in
   `wireEvents`).
5. **Tests** — extend `tests/binding/SwimUITest.sw` with the view and the
   state it shows.
