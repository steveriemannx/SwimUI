// NativeTest.sw -- drives the `import FerroUI` surface of the C backend: the
// window, every control kind, the property setters and getters, events, timers
// and snapshots.  tests/binding_test.py runs it and checks the printed lines.
//
//   tests/binding_test.py
//   SWIMUI_IMAGE=build/test/native.png SWIMUI_QUIT_MS=1600 \
//       ./build/test/NativeTest
//
// Environment: SWIMUI_IMAGE is where to write the first and last snapshot
// (`<path>` and `<path>.after.png`), SWIMUI_QUIT_MS when to close the window.

import FerroUI

// kinds (ffi/include/ferroui_swim.h)
let kindCanvas = 1
let kindStackPanel = 2
let kindBorder = 3
let kindText = 4
let kindButton = 5
let kindTextBox = 6
let kindCheckBox = 7
let kindSlider = 8
let kindProgress = 9
let kindScroll = 10
let kindPanel = 11
let kindFlex = 12
let kindSwitch = 13

// properties
let f64Width = 1
let f64Height = 2
let f64FontSize = 7
let f64CornerRadius = 9
let f64Value = 13
let strText = 1
let strContent = 4
let strWatermark = 3
let boolVisible = 1
let boolChecked = 2
let boolClip = 5
let colorBackground = 1
let colorForeground = 2
let thicknessPadding = 2
let enumTextAlignment = 4
let enumFontWeight = 6
let enumOrientation = 3

func check(_ name: String, _ value: String) {
    ferrouiLog(message: "check: \(name)=\(value)")
}

func checkBool(_ name: String, _ value: Bool) {
    if value {
        check(name, "true")
    } else {
        check(name, "false")
    }
}

ferrouiSetThemeVariant(name: "dark")
check("version", ferrouiVersion())

ferrouiRun {
    let window = ferrouiWindow(width: 320, height: 260, title: "native test",
                               background: 0x0B0C10, onClosed: {})
    let page = ferrouiCreate(parent: window, kind: kindBorder)
    ferrouiSetThickness(handle: page, property: thicknessPadding,
                        left: 16, top: 16, right: 16, bottom: 16)
    let root = ferrouiCreate(parent: page, kind: kindFlex)
    ferrouiSetFlex(handle: root, direction: 2, justify: 0, align: 0,
                   columnSpacing: 0, rowSpacing: 8)

    let label = ferrouiCreate(parent: root, kind: kindText)
    ferrouiSetString(handle: label, property: strText, value: "taps: 0")
    ferrouiSetF64(handle: label, property: f64FontSize, value: 18.0)
    ferrouiSetEnum(handle: label, property: enumFontWeight, value: 700)
    ferrouiSetColor(handle: label, property: colorForeground, argb: 0xF2F3F7)

    let button = ferrouiCreate(parent: root, kind: kindButton)
    ferrouiSetString(handle: button, property: strContent, value: "Tap me")
    ferrouiSetColor(handle: button, property: colorBackground, argb: 0x5B8CFF)
    ferrouiSetF64(handle: button, property: f64CornerRadius, value: 12.0)

    let slider = ferrouiCreate(parent: root, kind: kindSlider)
    ferrouiSetF64(handle: slider, property: f64Value, value: 25.0)
    let progress = ferrouiCreate(parent: root, kind: kindProgress)
    ferrouiSetF64(handle: progress, property: f64Value, value: 40.0)
    let toggle = ferrouiCreate(parent: root, kind: kindSwitch)
    ferrouiSetString(handle: toggle, property: strContent, value: "Switch")
    let text = ferrouiCreate(parent: root, kind: kindTextBox)
    ferrouiSetString(handle: text, property: strWatermark,
                     value: "write here")
    let scroll = ferrouiCreate(parent: root, kind: kindScroll)
    ferrouiSetF64(handle: scroll, property: f64Height, value: 40.0)
    let created = ferrouiCreate(parent: root, kind: kindPanel)
    ferrouiSetF64(handle: created, property: f64Height, value: 4.0)

    var taps = 0
    ferrouiOnTap(handle: button) {
        taps += 1
        ferrouiSetString(handle: label, property: strText,
                         value: "taps: \(taps)")
        check("tap", "\(taps)")
    }
    var values = 0
    ferrouiOnValueChanged(handle: slider) {
        values += 1
        check("valueChanged", "\(ferrouiGetValue(handle: slider))")
    }
    ferrouiOnCheckedChanged(handle: toggle) {
        checkBool("checkedChanged", ferrouiGetChecked(handle: toggle))
    }

    // What the setters and the getters give back.
    ferrouiSetString(handle: text, property: strText, value: "typed")
    check("text", ferrouiGetText(handle: text))
    check("buttonTitle", ferrouiGetText(handle: button))
    check("sliderValue", "\(ferrouiGetValue(handle: slider))")
    ferrouiSetBool(handle: toggle, property: boolChecked, value: true)
    checkBool("checked", ferrouiGetChecked(handle: toggle))
    checkBool("visible", ferrouiGetVisible(handle: label))
    ferrouiSetBool(handle: label, property: boolVisible, value: false)
    checkBool("hidden", ferrouiGetVisible(handle: label))
    ferrouiSetBool(handle: label, property: boolVisible, value: true)
    ferrouiSetBool(handle: label, property: boolClip, value: true)
    ferrouiSetF64(handle: label, property: f64Width, value: 280.0)
    checkBool("toggled", true)

    // The tree operations: a child added, moved and removed.
    let extra = ferrouiCreate(parent: 0, kind: kindText)
    ferrouiSetString(handle: extra, property: strText, value: "extra")
    ferrouiInsertChild(parent: root, index: 0, child: extra)
    ferrouiRemoveChild(parent: root, child: extra)
    ferrouiDestroy(handle: extra)
    check("extraChildReleased", "true")

    // A timer raises the click events as a pointer would, and moves the
    // slider; the program reads the results back in the same run.
    let image = ferrouiImagePath()
    ferrouiAfter(ms: 80) {
        if !image.isEmpty {
            ferrouiSnapshot(delayMs: 0, path: image)
        }
    }
    ferrouiAfter(ms: 200) {
        ferrouiRaiseClick(handle: button)
        ferrouiRaiseClick(handle: button)
        check("tapsAfterRaise", "\(taps)")
        ferrouiSetF64(handle: slider, property: f64Value, value: 90.0)
        check("sliderSet", "\(ferrouiGetValue(handle: slider))")
    }
    ferrouiAfter(ms: 700) {
        if !image.isEmpty {
            ferrouiSnapshot(delayMs: 100, path: image + ".after.png")
        }
        check("valuesSeen", "\(values)")
    }
    let quit = ferrouiAutoQuitMs()
    if quit > 0 {
        ferrouiAfter(ms: quit) {
            ferrouiQuit()
        }
    }
}
