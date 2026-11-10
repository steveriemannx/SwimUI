// BindingTest.sw -- drives the whole SwimUI surface of the FerroUI binding and
// reports what it sees, so a machine can check it without a person clicking.
//
// The program builds one of every control and then, once the window is up,
// changes properties, reads them back, raises the click event of a button as a
// pointer would, and writes two snapshots: before and after the changes (the
// second path is the first with ".after.png" appended).  Every observation is
// printed as "check: <name>=<value>"; tests/binding_test.py compares them.
//
//   ./scripts/run-demo.sh --program tests/binding/BindingTest.sw \
//       --snapshot build/binding-before.png
//
// (or tests/binding_test.py, which sets that up and checks the output).

import SwimUI

let bg = 0x0B0C10
let surface = 0x151824
let surface2 = 0x232838
let ink = 0xF2F3F7
let muted = 0x8A90A2
let accent = 0x5B8CFF

var labelView = View(handle: 0)
var buttonView = View(handle: 0)
var barView = View(handle: 0)
var checkBoxView = View(handle: 0)
var sliderView = View(handle: 0)
var fieldView = View(handle: 0)
var cardView = View(handle: 0)
var stackView = View(handle: 0)
var scrollViewControl = View(handle: 0)
var taps = 0
var toggles = 0
var movement = 0.0

/// Print one observation for the test runner.
func check(_ name: String, _ value: String) {
    printLog("check: \(name)=\(value)")
}

func checkBool(_ name: String, _ value: Bool) {
    if value {
        printLog("check: \(name)=true")
    } else {
        printLog("check: \(name)=false")
    }
}

setThemeVariant("dark")

runApp {
    let screen = Screen(width: 320, height: 480, title: "SwimUI binding test",
                        background: bg, borderless: true)

    screen.onReady {
        printLog("check: ready=true")
        check("clientWidth", "\(screen.clientWidth())")
        check("clientHeight", "\(screen.clientHeight())")

        // One of every control; the frames of a painter are checked below.
        labelView = screen.label(x: 16, y: 16, width: 288, height: 24,
                             text: "before", size: 16, bold: true)
        buttonView = screen.button(x: 16, y: 48, width: 140, height: 36,
                               title: "tap", fill: accent, titleColor: ink,
                               radius: 10, size: 14) {
            taps += 1
            labelView.setText("taps=\(taps)")
        }
        barView = screen.progressBar(x: 16, y: 92, width: 288, height: 8,
                                 percent: 10)
        checkBoxView = screen.checkBox(x: 16, y: 108, width: 160, height: 24,
                                   text: "check", checked: false) {
            toggles += 1
        }
        sliderView = screen.slider(x: 16, y: 136, width: 240, height: 24,
                               minimum: 0, maximum: 100, value: 10) {
            movement = sliderView.value()
        }
        fieldView = screen.textField(x: 16, y: 168, width: 288, height: 36,
                                 text: "field", placeholder: "write here",
                                 size: 14) {
        }
        cardView = screen.panel(x: 16, y: 212, width: 140, height: 72,
                             color: surface, radius: 12)
        cardView.label(x: 8, y: 8, width: 124, height: 20, text: "panel",
                    size: 13)
        stackView = screen.stack(x: 168, y: 212, width: 136, height: 72,
                             vertical: true, spacing: 4)
        stackView.label(x: 0, y: 0, width: 136, height: 20, text: "stack one",
                    size: 12)
        stackView.label(x: 0, y: 0, width: 136, height: 20, text: "stack two",
                    size: 12)
        scrollViewControl = screen.scrollView(x: 16, y: 292, width: 288, height: 96,
                                   color: surface, radius: 12)
        var row = 0
        while row < 8 {
            scrollViewControl.label(x: 8, y: 4 + row * 24, width: 260, height: 20,
                         text: "scroll row \(row)", size: 12, color: muted)
            row += 1
        }
        screen.label(x: 16, y: 400, width: 288, height: 20,
                     text: "SwimUI / FerroUI binding test", size: 11,
                     color: surface2)

        // What a program can read back.
        check("labelText", labelView.text())
        check("buttonText", buttonView.text())
        check("fieldText", fieldView.text())
        check("sliderValue", "\(sliderView.value())")
        check("barValue", "\(barView.value())")
        checkBool("checkboxBefore", checkBoxView.isChecked())
        checkBool("visibleBefore", labelView.isVisible())

        // The first frame: what the window looks like before the changes.
        let image = imagePath()
        if !image.isEmpty {
            screen.snapshot(after: 400, path: image)
            screen.snapshot(after: 1400, path: image + ".after.png")
        }

        // Programmatic changes, the way the callbacks of an application make
        // them.
        after(600) {
            labelView.setText("after")
            buttonView.setText("tapped")
            buttonView.setColor(surface2)
            barView.setProgress(75)
            sliderView.setValue(55.0)
            checkBoxView.setChecked(true)
            cardView.setColor(surface2)
            cardView.setBorder(color: accent, width: 2)
            fieldView.setText("changed")
            labelView.setTextColor(accent)
            stackView.setSpacing(10)
            screen.setBackground(0x101218)
            check("labelTextAfter", labelView.text())
            check("buttonTextAfter", buttonView.text())
            check("fieldTextAfter", fieldView.text())
            check("sliderValueAfter", "\(sliderView.value())")
            check("barValueAfter", "\(barView.value())")
            checkBool("checkboxAfter", checkBoxView.isChecked())

            // A pointer-less click: the handler of the button runs.
            buttonView.raiseTap()
            check("tapsAfterRaise", "\(taps)")

            // Visibility toggles travel to the platform.
            labelView.setVisible(false)
            checkBool("visibleHidden", labelView.isVisible())
            labelView.setVisible(true)
            checkBool("visibleShown", labelView.isVisible())
        }

        after(1200) {
            buttonView.raiseTap()
            check("tapsAfterSecondRaise", "\(taps)")
            check("movedValue", "\(movement)")
        }

        let quitMs = autoQuitMs()
        if quitMs > 0 {
            after(quitMs) {
                printLog("check: quitting=true")
                quitApp()
            }
        }
    }
}
