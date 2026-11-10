# examples/ui/ — the SwiftUI-shaped layer over the FerroUI binding

| File | What it is |
| --- | --- |
| [`SwiftUI.sw`](SwiftUI.sw) | the declarative layer (the library the examples import): `View`, `State`, the containers, the controls, the modifiers, `Scene`/`WindowGroup`/`launch`, and the re-render/patch pass |
| [`LibraryApp.sw`](LibraryApp.sw) | the demo: a phone-sized (390 × 844) photo library, fully interactive |
| [`CounterApp.sw`](CounterApp.sw) | the smallest layer app: a counter with two buttons |
| [`shots/demo.png`](shots/demo.png) | the demo's snapshot, written by `snapshot(...)` |

A program imports the layer as a Swim module:

```swift
import SwiftUI
```

`SwiftUI.sw` itself imports `FerroUI`, so the merged program also has the flat
module available.  The layer sits next to the programs that import it, so no
`SWIM_PATH` is needed for them; programs elsewhere (the tests) find it through
`SWIM_PATH=examples/ui` (`scripts/run-demo.sh` exports it).

## Shape of an application

```swift
import SwiftUI

final class Model {
    let count = State(0)
}

let model = Model()

func CounterView(_ model: Model) -> View {
    VStack(spacing: 16) {
        Text("Count: \(model.count.value)").font(.largeTitle)
        Button("Add") { model.count.value = model.count.value + 1 }
            .buttonStyle(.borderedProminent)
    }
    .padding(24)
}

@main
struct CounterApp {
    var body: Scene {
        WindowGroup("Counter", width: 390, height: 500) {
            CounterView(model)
        }
    }

    static func main() {
        setThemeVariant("dark")
        launch(CounterApp().body)
    }
}
```

- **State** lives in a model object as `State<T>` values; writing
  `model.count.value = …` re-renders the window and patches the mounted
  FerroUI controls (identity and focus survive).
- **Views** are functions returning `View` (`func CounterView(_:) -> View`),
  composed with the SwiftUI syntax: containers with trailing closures,
  `.modifiers`, `ForEach`, `if`/`else`.
- **The application** is `@main struct` with `var body: Scene` and a
  `static func main()` that calls `launch(...)` — Swim's `@main` requires the
  static entry point, and the scene is passed to `launch`.

The full reference is [docs/swiftui.md](../../docs/swiftui.md); the flat module
under it is [docs/ferroui.md](../../docs/ferroui.md).

## Running

```console
$ ../../scripts/run-demo.sh                   # build and run the demo
$ ../../scripts/run-demo.sh --snapshot shots/demo.png
$ ../../scripts/run-demo.sh --smoke           # one frame, then quit
$ ../../scripts/run-demo.sh --program examples/ui/CounterApp.sw
```

The programs read `SWIMUI_IMAGE` (snapshot path) and `SWIMUI_QUIT_MS` (close
after that many milliseconds) at run time, which is how a test or a
documentation run drives them; `run-demo.sh --snapshot` sets both.  That is how
`shots/demo.png` and `tests/binding_test.py` work.
