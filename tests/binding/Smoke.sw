// Smoke.sw -- the smallest program of the FerroUI binding: a window with a
// label and a button, a snapshot and an automatic quit, so a machine can check
// that the whole chain (Swim -> Nim -> Rust bridge -> FerroUI -> window -> PNG)
// works.  tests/binding_test.py runs it.
//
//   tests/binding_test.py
//   ./scripts/run-demo.sh --program tests/binding/Smoke.sw \
//       --snapshot build/smoke/binding.png

import SwimUI

setThemeVariant("dark")

runApp {
    let screen = Screen(width: 390, height: 320, title: "SwimUI smoke",
                        background: 0x0B0C10, borderless: true)
    screen.onReady {
        screen.label(x: 24, y: 24, width: 342, height: 32, text: "Hello, FerroUI",
                     size: 24, bold: true)
        screen.label(x: 24, y: 60, width: 342, height: 20,
                     text: "written in Swim", size: 13, color: 0x8A90A2)
        screen.button(x: 24, y: 104, width: 160, height: 44, title: "Tap me",
                      fill: 0x5B8CFF, titleColor: 0x0B0C10, radius: 12,
                      size: 15) {
            printLog("smoke: button clicked")
        }
        printLog("smoke: client \(screen.clientWidth())x\(screen.clientHeight())")

        let image = imagePath()
        if !image.isEmpty {
            screen.snapshot(after: 400, path: image)
        }
        let quitMs = autoQuitMs()
        if quitMs > 0 {
            after(quitMs) {
                quitApp()
            }
        }
    }
}
