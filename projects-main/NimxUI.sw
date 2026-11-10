// NimxUI.sw -- a small, Swift-style wrapper around the `Nimx` bridge.
//
// `import Nimx` gives Swim the low-level `nimx*` free functions (window,
// panel, label, button, ...).  They all speak in `Int` handles, which is
// exactly what the Nim side understands, but it is not very Swift-like to
// pass handles around.  This file wraps each handle in a tiny `View` class so
// the demo can be written with ordinary method calls.
//
// The class is managed by Swim's ARC, just like a Swift class.  The handle
// keeps the underlying nimx view alive as long as the Nim window hierarchy
// holds it.

import Nimx

// Text alignment values accepted by `nimxLabel` (matches the Nim bridge).
let alignLeft = 0
let alignCenter = 1
let alignRight = 2

/// A handle to a view in the nimx window hierarchy.
class View {
    let handle: Int

    init(handle: Int) {
        self.handle = handle
    }

    /// Change the text of a label (or of the label inside a button).
    func setText(_ text: String) {
        nimxSetText(handle: handle, text: text)
    }

    /// Change the fill colour of a panel/button, or the text colour of a label.
    func setColor(_ color: Int) {
        nimxSetColor(handle: handle, color: color)
    }

    /// Change the text colour of a label (or of a button title).
    func setTextColor(_ color: Int) {
        nimxSetTextColor(handle: handle, color: color)
    }

    /// Update the value of a progress bar; `percent` is 0...100.
    func setProgress(_ percent: Int) {
        nimxSetProgress(handle: handle, percent: percent)
    }

    /// Show or hide the view (and its subviews).
    func setVisible(_ visible: Bool) {
        nimxSetHidden(handle: handle, hidden: !visible)
    }

    /// Run `action` whenever the view is tapped / clicked.
    func onTap(_ action: () -> Void) {
        nimxOnTap(handle: handle, onTap: action)
    }
}

// MARK: - View factories

extension View {
    /// A rounded rectangle filled with `color`.
    func panel(x: Int, y: Int, width: Int, height: Int, color: Int,
               radius: Int = 0) -> View {
        let h = nimxPanel(parent: handle, x: x, y: y, width: width,
                          height: height, color: color, radius: radius)
        return View(handle: h)
    }

    /// A single line of text.
    func label(x: Int, y: Int, width: Int, height: Int, text: String,
               size: Int = 14, color: Int = 0xF2F3F7,
               align: Int = 0, bold: Bool = false) -> View {
        let h = nimxLabel(parent: handle, x: x, y: y, width: width,
                          height: height, size: size, color: color,
                          align: align, bold: bold, text: text)
        return View(handle: h)
    }

    /// A tappable rounded rectangle with a centred title.
    func button(x: Int, y: Int, width: Int, height: Int, title: String,
                fill: Int, titleColor: Int, radius: Int = 0,
                size: Int = 14, bold: Bool = false,
                onTap: () -> Void) -> View {
        let h = nimxButton(parent: handle, x: x, y: y, width: width,
                           height: height, fill: fill, titleColor: titleColor,
                           radius: radius, size: size, bold: bold, title: title,
                           onTap: onTap)
        return View(handle: h)
    }

    /// A thin progress bar; `percent` is 0...100.
    func progressBar(x: Int, y: Int, width: Int, height: Int, track: Int,
                     fill: Int, radius: Int = 3, percent: Int = 0) -> View {
        let h = nimxProgressBar(parent: handle, x: x, y: y, width: width,
                                height: height, track: track, fill: fill,
                                radius: radius, percent: percent)
        return View(handle: h)
    }
}

// MARK: - Application helpers

/// Open a phone-sized window and return its root view.
func nimxScreen(width: Int, height: Int, title: String,
                background: Int = 0x0B0C10) -> View {
    let h = nimxWindow(width: width, height: height, title: title,
                       background: background)
    return View(handle: h)
}

/// Run the nimx event loop (blocks until the window is closed).
func runApp() {
    nimxRun()
}

/// Run `action` once, after `milliseconds`.
func after(_ milliseconds: Int, action: () -> Void) {
    nimxAfter(ms: milliseconds, action: action)
}

/// Render the current window to a PNG file (useful for docs and CI).
func snapshot(after milliseconds: Int, path: String) {
    nimxSnapshot(delayMs: milliseconds, path: path)
}
