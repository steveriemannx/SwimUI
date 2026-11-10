// SwimUI.sw -- a small, Swift-style view layer over the `FerroUI` binding.
//
// `import FerroUI` gives Swim the low-level `ferroui*` free functions (window,
// box, label, button, ...).  They all speak in `Int` handles, which is exactly
// what the Nim side understands, but it is not very Swift-like to pass handles
// around.  This file wraps each handle in a tiny `View` class, so an
// application is written with ordinary method calls -- the same shape as
// `NimxUI.sw` of the nimx binding, with FerroUI controls under the surface.
//
// FerroUI builds its controls once the framework of the application is
// initialized, so the view tree is created inside `runApp { ... }`:
//
//     runApp {
//         let screen = Screen(width: 390, height: 844, title: "Library",
//                             background: 0x0B0C10)
//         let header = screen.label(x: 24, y: 54, width: 260, height: 42,
//                                   text: "Library", size: 30, bold: true)
//         screen.button(x: 326, y: 58, width: 40, height: 40, title: "+",
//                       fill: 0x232838, titleColor: 0x5B8CFF, radius: 20,
//                       size: 22, bold: true) {
//             header.setText("Albums")
//         }
//     }

import FerroUI

// MARK: - Text alignment

/// Text alignment values accepted by `label(...)`.
let alignLeft = 0
let alignCenter = 1
let alignRight = 2

/// The colour value that leaves a control without a brush.
let clearColor = -1

// MARK: - The view wrapper

/// A handle to a view of the FerroUI window hierarchy.
///
/// `handle` is the control a property is set on.  `content` is the canvas its
/// children are created in for a container (`panel`, `scrollView`); it is `0`
/// when the view lays its children out itself (`stack`) or takes none
/// (`label`, `button`).
class View {
    let handle: Int
    let content: Int

    init(handle: Int, content: Int = 0) {
        self.handle = handle
        self.content = content
    }

    /// The handle a child of this view is created with.
    func childParent() -> Int {
        if content != 0 {
            return content
        }
        return handle
    }

    // MARK: properties

    /// Move and resize the view (the position applies in a canvas).
    func setFrame(x: Int, y: Int, width: Int, height: Int) {
        ferrouiSetFrame(handle: handle, x: x, y: y, width: width, height: height)
    }

    /// Change the text of a label, a field or the title of a button.
    func setText(_ text: String) {
        ferrouiSetText(handle: handle, text: text)
    }

    /// Change the fill colour of a panel or a button.
    func setColor(_ color: Int) {
        ferrouiSetColor(handle: handle, color: color)
    }

    /// Change the text colour of a label, a field or a button title.
    func setTextColor(_ color: Int) {
        ferrouiSetTextColor(handle: handle, color: color)
    }

    /// Change the border colour and width of a panel.
    func setBorder(color: Int, width: Int) {
        ferrouiSetBorder(handle: handle, color: color, width: width)
    }

    /// The corner radius of a panel, a button or a field.
    func setRadius(_ radius: Int) {
        ferrouiSetRadius(handle: handle, radius: radius)
    }

    /// The font size of a text control.
    func setFontSize(_ size: Int) {
        ferrouiSetFontSize(handle: handle, size: size)
    }

    /// The weight of the text of a text control.
    func setBold(_ bold: Bool) {
        ferrouiSetBold(handle: handle, bold: bold)
    }

    /// The horizontal alignment of the text of a text control.
    func setAlignment(_ align: Int) {
        ferrouiSetAlignment(handle: handle, align: align)
    }

    /// Update a progress bar; `percent` is 0...100.
    func setProgress(_ percent: Int) {
        ferrouiSetProgress(handle: handle, percent: percent)
    }

    /// Update the value of a slider.
    func setValue(_ value: Double) {
        ferrouiSetValue(handle: handle, value: value)
    }

    /// Check or uncheck a check box.
    func setChecked(_ checked: Bool) {
        ferrouiSetChecked(handle: handle, checked: checked)
    }

    /// The spacing of a stack panel.
    func setSpacing(_ spacing: Int) {
        ferrouiSetSpacing(handle: handle, spacing: spacing)
    }

    /// Show or hide the view (and its subviews).
    func setVisible(_ visible: Bool) {
        ferrouiSetHidden(handle: handle, hidden: !visible)
    }

    /// The opacity of the view, in percent.
    func setOpacity(_ percent: Int) {
        ferrouiSetOpacity(handle: handle, percent: percent)
    }

    // MARK: reading properties back

    /// The value of a slider or a progress bar.
    func value() -> Double {
        return ferrouiGetValue(handle: handle)
    }

    /// The text of a label or a field, or the title of a button.
    func text() -> String {
        return ferrouiGetText(handle: handle)
    }

    /// Whether a check box is checked.
    func isChecked() -> Bool {
        return ferrouiGetChecked(handle: handle)
    }

    /// Whether the view is visible.
    func isVisible() -> Bool {
        return ferrouiGetVisible(handle: handle)
    }

    // MARK: events

    /// Run `action` whenever the view is clicked or tapped.
    func onTap(_ action: () -> Void) {
        ferrouiOnTap(handle: handle, onTap: action)
    }

    /// Run `action` whenever the text of a text field changes.
    func onTextChanged(_ action: () -> Void) {
        ferrouiOnTextChanged(handle: handle, onChanged: action)
    }

    /// Run `action` whenever the value of a slider changes.
    func onValueChanged(_ action: () -> Void) {
        ferrouiOnValueChanged(handle: handle, onChanged: action)
    }

    /// Run `action` whenever a check box is checked or unchecked.
    func onCheckedChanged(_ action: () -> Void) {
        ferrouiOnCheckedChanged(handle: handle, onChanged: action)
    }

    /// Raise the click event of a button, as a pointer would.  A test helper:
    /// a program uses it to drive its own controls.
    func raiseTap() {
        ferrouiRaiseClick(handle: handle)
    }

    /// Add a child the view keeps alive but does not have to lay out.
    func add(_ child: View) {
        ferrouiLog(message: "add: children are created through the view that holds them")
    }
}

// MARK: - View factories

extension View {
    /// A rounded rectangle filled with `color`.  Its children are positioned
    /// in its canvas, so `panel(...).label(...)` places a label at the
    /// coordinates of the panel.
    func panel(x: Int, y: Int, width: Int, height: Int, color: Int,
               radius: Int = 0, borderColor: Int = clearColor,
               borderWidth: Int = 0) -> View {
        let box = ferrouiBox(parent: childParent(), x: x, y: y, width: width,
                             height: height, fill: color, radius: radius,
                             borderColor: borderColor, borderWidth: borderWidth)
        let children = ferrouiContent(container: box)
        return View(handle: box, content: children)
    }

    /// A scrollable viewport whose children are positioned in its canvas.
    func scrollView(x: Int, y: Int, width: Int, height: Int,
                    color: Int = clearColor, radius: Int = 0) -> View {
        let view = ferrouiScrollView(parent: childParent(), x: x, y: y,
                                     width: width, height: height, fill: color,
                                     radius: radius)
        let children = ferrouiContent(container: view)
        return View(handle: view, content: children)
    }

    /// A panel that lays its children out one after the other.
    func stack(x: Int, y: Int, width: Int, height: Int, vertical: Bool = true,
               spacing: Int = 0) -> View {
        let view = ferrouiStack(parent: childParent(), vertical: vertical,
                                spacing: spacing)
        ferrouiSetFrame(handle: view, x: x, y: y, width: width, height: height)
        return View(handle: view)
    }

    /// A single line of text.
    func label(x: Int, y: Int, width: Int, height: Int, text: String,
               size: Int = 14, color: Int = 0xF2F3F7, align: Int = alignLeft,
               bold: Bool = false) -> View {
        let view = ferrouiLabel(parent: childParent(), x: x, y: y,
                                width: width, height: height, text: text,
                                size: size, color: color, align: align,
                                bold: bold)
        return View(handle: view)
    }

    /// A tappable rounded rectangle with a title.
    func button(x: Int, y: Int, width: Int, height: Int, title: String,
                fill: Int, titleColor: Int, radius: Int = 0, size: Int = 14,
                bold: Bool = false, onTap: () -> Void) -> View {
        let view = ferrouiButton(parent: childParent(), x: x, y: y,
                                 width: width, height: height, title: title,
                                 size: size, bold: bold, fill: fill,
                                 titleColor: titleColor, radius: radius,
                                 onTap: onTap)
        return View(handle: view)
    }

    /// An editable field of text.
    func textField(x: Int, y: Int, width: Int, height: Int, text: String = "",
                   placeholder: String = "", size: Int = 14,
                   onChanged: () -> Void = {}) -> View {
        let view = ferrouiTextField(parent: childParent(), x: x, y: y,
                                    width: width, height: height, text: text,
                                    placeholder: placeholder, size: size,
                                    onChanged: onChanged)
        return View(handle: view)
    }

    /// A check box with a title next to it.
    func checkBox(x: Int, y: Int, width: Int, height: Int, text: String,
                  checked: Bool = false, onChanged: () -> Void = {}) -> View {
        let view = ferrouiCheckBox(parent: childParent(), x: x, y: y,
                                   width: width, height: height, text: text,
                                   checked: checked, onChanged: onChanged)
        return View(handle: view)
    }

    /// A slider between `minimum` and `maximum`.
    func slider(x: Int, y: Int, width: Int, height: Int, minimum: Int = 0,
                maximum: Int = 100, value: Int = 0,
                onChanged: () -> Void = {}) -> View {
        let view = ferrouiSlider(parent: childParent(), x: x, y: y,
                                 width: width, height: height,
                                 minimum: minimum, maximum: maximum,
                                 value: value, onChanged: onChanged)
        return View(handle: view)
    }

    /// A thin progress bar; `percent` is 0...100.
    func progressBar(x: Int, y: Int, width: Int, height: Int,
                     percent: Int = 0) -> View {
        let view = ferrouiProgressBar(parent: childParent(), x: x, y: y,
                                      width: width, height: height,
                                      percent: percent)
        return View(handle: view)
    }
}

// MARK: - The screen

/// The window of a SwimUI application and the canvas its views are placed in.
class Screen {
    let window: Int
    let root: View

    init(width: Int, height: Int, title: String, background: Int,
         borderless: Bool = false) {
        self.window = ferrouiWindow(width: width, height: height, title: title,
                                     background: background, onClosed: {})
        ferrouiSetDecorations(handle: self.window, mode: 0)
        if !borderless {
            ferrouiSetDecorations(handle: self.window, mode: 2)
        }
        let canvas = ferrouiCanvas(parent: self.window)
        self.root = View(handle: self.window, content: canvas)
    }

    /// The view that holds the whole window.
    func content() -> View {
        return root
    }

    /// The width of the client area: the width the layout has to fit in.
    func clientWidth() -> Int {
        return ferrouiClientWidth()
    }

    /// The height of the client area: the height the layout has to fit in.
    /// It is smaller than the requested height when the decorations or the
    /// screen take room from it.
    func clientHeight() -> Int {
        return ferrouiClientHeight()
    }

    /// Run `action` once the window is shown and its client area is known, so
    /// the layout of the program can be fitted to `clientWidth()` and
    /// `clientHeight()`.
    func onReady(_ action: () -> Void) {
        ferrouiOnReady(handle: self.window, onReady: action)
    }

    func panel(x: Int, y: Int, width: Int, height: Int, color: Int,
               radius: Int = 0, borderColor: Int = clearColor,
               borderWidth: Int = 0) -> View {
        return root.panel(x: x, y: y, width: width, height: height,
                          color: color, radius: radius,
                          borderColor: borderColor, borderWidth: borderWidth)
    }

    func scrollView(x: Int, y: Int, width: Int, height: Int,
                    color: Int = clearColor, radius: Int = 0) -> View {
        return root.scrollView(x: x, y: y, width: width, height: height,
                               color: color, radius: radius)
    }

    func stack(x: Int, y: Int, width: Int, height: Int, vertical: Bool = true,
               spacing: Int = 0) -> View {
        return root.stack(x: x, y: y, width: width, height: height,
                          vertical: vertical, spacing: spacing)
    }

    func label(x: Int, y: Int, width: Int, height: Int, text: String,
               size: Int = 14, color: Int = 0xF2F3F7, align: Int = alignLeft,
               bold: Bool = false) -> View {
        return root.label(x: x, y: y, width: width, height: height, text: text,
                          size: size, color: color, align: align, bold: bold)
    }

    func button(x: Int, y: Int, width: Int, height: Int, title: String,
                fill: Int, titleColor: Int, radius: Int = 0, size: Int = 14,
                bold: Bool = false, onTap: () -> Void) -> View {
        return root.button(x: x, y: y, width: width, height: height,
                           title: title, fill: fill, titleColor: titleColor,
                           radius: radius, size: size, bold: bold,
                           onTap: onTap)
    }

    func textField(x: Int, y: Int, width: Int, height: Int, text: String = "",
                   placeholder: String = "", size: Int = 14,
                   onChanged: () -> Void = {}) -> View {
        return root.textField(x: x, y: y, width: width, height: height,
                              text: text, placeholder: placeholder, size: size,
                              onChanged: onChanged)
    }

    func checkBox(x: Int, y: Int, width: Int, height: Int, text: String,
                  checked: Bool = false, onChanged: () -> Void = {}) -> View {
        return root.checkBox(x: x, y: y, width: width, height: height,
                             text: text, checked: checked, onChanged: onChanged)
    }

    func slider(x: Int, y: Int, width: Int, height: Int, minimum: Int = 0,
                maximum: Int = 100, value: Int = 0,
                onChanged: () -> Void = {}) -> View {
        return root.slider(x: x, y: y, width: width, height: height,
                           minimum: minimum, maximum: maximum, value: value,
                           onChanged: onChanged)
    }

    func progressBar(x: Int, y: Int, width: Int, height: Int,
                     percent: Int = 0) -> View {
        return root.progressBar(x: x, y: y, width: width, height: height,
                                percent: percent)
    }

    /// The background of the window.
    func setBackground(_ color: Int) {
        ferrouiSetColor(handle: window, color: color)
    }

    /// Render the window to a PNG file, `after` milliseconds from now.
    func snapshot(after milliseconds: Int, path: String) {
        ferrouiSnapshot(delayMs: milliseconds, path: path)
    }

    /// Close the window (and end the application).
    func close() {
        ferrouiClose(window: window)
    }
}

// MARK: - Application helpers

/// The theme variant of the application: "dark", "light" or "system".
/// Call it before `runApp`.
func setThemeVariant(_ name: String) {
    ferrouiSetThemeVariant(name: name)
}

/// Start the application; `build` runs once the framework is initialized and
/// creates the window and the view tree.  Blocks until the window closes.
func runApp(_ build: () -> Void) {
    ferrouiRun {
        build()
    }
}

/// Run `action` once, after `milliseconds`, on the UI thread.
func after(_ milliseconds: Int, action: () -> Void) {
    ferrouiAfter(ms: milliseconds, action: action)
}

/// End the application.
func quitApp() {
    ferrouiQuit()
}

/// Print a line to the console of the application.
///
/// Named `printLog` rather than `log`, which Swim maps to the natural logarithm.
func printLog(_ message: String) {
    ferrouiLog(message: message)
}

/// The version of the FerroUI bridge and of FerroUI itself.
func swimUIVersion() -> String {
    return "SwimUI " + ferrouiVersion()
}

/// The PNG a test or documentation run asked the program to snapshot its
/// window into (`-d:swimFerroUIImage=<path>`); empty when it did not.
func imagePath() -> String {
    return ferrouiImagePath()
}

/// Close the window after that many milliseconds (`-d:swimFerroUIQuitMs=<ms>`)
/// in a test run; 0 means the program stays open until it is closed.
func autoQuitMs() -> Int {
    return ferrouiAutoQuitMs()
}
