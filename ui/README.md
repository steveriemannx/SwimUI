# ui/ — the Swift-style layer over the FerroUI binding

| File | What it is |
| --- | --- |
| [`SwimUI.sw`](SwimUI.sw) | the view layer: `Screen`, `View`, the factories and the application helpers, all over `import FerroUI` |
| [`FerroUIDemo.sw`](FerroUIDemo.sw) | the demo: a phone-sized (390 × 844) photo library, fully interactive |
| [`shots/demo.png`](shots/demo.png) | the demo's snapshot, written by `screen.snapshot(...)` |

A program of this directory imports the layer as a Swim module:

```swift
import SwimUI
```

`SwimUI.sw` starts with `import FerroUI`, so the merged program also gets the
flat FerroUI functions.  Because `SwimUI.sw` sits next to the programs that
import it, no `SWIM_PATH` is needed for them; programs elsewhere (the tests)
find it through `SWIM_PATH=ui` (`scripts/run-demo.sh` exports it).

## The shape of an application

```swift
import SwimUI

setThemeVariant("dark")

runApp {
    let screen = Screen(width: 390, height: 844, title: "Library",
                        background: 0x0B0C10, borderless: true)
    screen.onReady {
        let height = screen.clientHeight()     // fit the layout to the window
        screen.label(x: 24, y: 54, width: 260, height: 42, text: "Library",
                     size: 30, bold: true)
        screen.button(x: 326, y: 58, width: 40, height: 40, title: "+",
                      fill: 0x232838, titleColor: 0x5B8CFF, radius: 20,
                      size: 22, bold: true) {
            printLog("album created")
        }
    }
}
```

- Everything is pixel-positioned in a canvas.  `screen.panel(...)` returns a
  rounded panel with its own canvas: a child of it is placed relative to the
  panel, which is what makes the demo's rows and cards.
- A callback (`onTap`, `onChanged`, …) runs on the UI thread and may set
  properties directly (`setText`, `setColor`, `setProgress`, …).
- `screen.onReady` is where the view tree is built: FerroUI has created its
  framework by then, and the client area of the window is final.  Views are
  created there, so views that a callback needs afterwards are kept in global
  variables (`var header = View(handle: 0)` at the top, assigned in `onReady`).
- `after(ms) { ... }` schedules work later (the demo's toast), `quitApp()` ends
  the application, `screen.snapshot(after:path:)` writes a PNG.

## Running the demo

```console
$ ../scripts/run-demo.sh                      # build and run
$ ../scripts/run-demo.sh --snapshot shots/demo.png
$ ../scripts/run-demo.sh --smoke              # one frame, then quit
```

The demo sets `-d:swimFerroUIImage`/`-d:swimFerroUIQuitMs` support itself: when
`scripts/run-demo.sh --snapshot` passes them, the program snapshots its window
and quits, which is how `shots/demo.png` and `tests/binding_test.py` work.
