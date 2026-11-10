// SwimUI.sw -- a declarative, SwiftUI-shaped view layer over the FerroUI
// binding of SwimUI.
//
// A program writes views the SwiftUI way -- containers with trailing-closure
// content, chained modifiers and observable state:
//
//     @main
//     struct LibraryApp {
//         var body: Scene {
//             WindowGroup("Library", width: 390, height: 844) {
//                 LibraryView(model)
//             }
//         }
//         static func main() {
//             launch(LibraryApp().body)
//         }
//     }
//
//     final class LibraryModel {
//         let albums = State(0)
//     }
//
//     func LibraryView(_ model: LibraryModel) -> View {
//         VStack(alignment: .leading, spacing: 16) {
//             Text("Library").font(.largeTitle)
//             HStack(spacing: 8) {
//                 Text("Albums: \(model.albums.value)")
//                 Spacer()
//                 Button("Add") { model.albums.value = model.albums.value + 1 }
//                     .buttonStyle(.borderedProminent)
//             }
//         }
//         .padding(24)
//     }
//
// How it works, in three stages:
//
//   1. *build*: a view expression constructs `View` nodes.  A container pushes
//      a builder, runs its content closure (every view constructed there
//      appends itself to the builder) and keeps the collected children.
//      `Group`/`ForEach` splice their children into the enclosing builder.
//   2. *mount*: a node tree becomes FerroUI controls.  Every node mounts as a
//      `Border` wrapper (padding, background, border, corner radius) around one
//      host control; containers get a child target (FlexPanel for stacks,
//      Panel for ZStack, a scrollable FlexPanel for lists and scroll views).
//   3. *patch* (`sync`): when a `State` changes, the body is built again and
//      walked against the mounted tree in lockstep: the same kind reuses the
//      controls and sets the properties again (identity and focus are kept), a
//      different kind replaces that subtree.
//
// Swim has no property wrappers, so state lives in `State` objects owned by a
// model and views are plain functions of it; a write to `State.value` schedules
// one re-render.  Swim has no result builders, so the builder stack supplies
// what `@ViewBuilder` does in SwiftUI.

import FerroUI

// ---------------------------------------------------------------------------
// The identifiers of the bridge (ffi/include/ferroui_swim.h)
// ---------------------------------------------------------------------------
// control kinds
let kindBorder = 3
let kindTextBlock = 4
let kindButton = 5
let kindTextBox = 6
let kindSlider = 8
let kindProgressBar = 9
let kindScrollViewer = 10
let kindPanel = 11
let kindFlexPanel = 12
let kindToggleSwitch = 13

// double properties
let f64Width = 1
let f64Height = 2
let f64MinWidth = 3
let f64MinHeight = 4
let f64MaxWidth = 5
let f64MaxHeight = 6
let f64FontSize = 7
let f64Opacity = 8
let f64CornerRadius = 9
let f64Minimum = 11
let f64Maximum = 12
let f64Value = 13

// int properties
let i32MaxLines = 1

// string properties
let strText = 1
let strWatermark = 3
let strContent = 4

// bool properties
let boolIsVisible = 1
let boolIsChecked = 2
let boolIsIndeterminate = 3
let boolIsEnabled = 4
let boolClipToBounds = 5

// brush properties
let colorBackground = 1
let colorForeground = 2
let colorBorder = 3

// thickness properties
let thicknessPadding = 2
let thicknessBorder = 3

// enum properties
let enumHorizontalAlignment = 1
let enumVerticalAlignment = 2
let enumTextAlignment = 4
let enumTextWrapping = 5
let enumFontWeight = 6

// alignment values
let hAlignLeading = 1
let hAlignCenter = 2
let hAlignTrailing = 3
let vAlignTop = 1
let vAlignCenter = 2
let vAlignBottom = 3
let textAlignLeading = 0
let textAlignCenter = 1
let textAlignTrailing = 2

// flex values
let flexRow = 0
let flexColumn = 2
let justifyStart = 0
let flexAlignStart = 0
let flexAlignEnd = 1
let flexAlignCenter = 2
let flexAlignStretch = 3

// decorations
let decorationsNone = 0
let decorationsFull = 2

// ---------------------------------------------------------------------------
// The value types of the API
// ---------------------------------------------------------------------------
/// A colour: `Color(0xRRGGBB)` or `Color(0xAARRGGBB)`; `Color.clear` leaves a
/// brush unset.
/// Whether the palette is the dark one; `setThemeVariant` sets it.
var usesDarkPalette = false

struct Color {
    let value: Int

    init(_ hex: Int) {
        self.value = hex
    }

    static let clear = Color(-1)
    static let white = Color(0xFFFFFF)
    static let black = Color(0x000000)
    static let red = Color(0xFF3B30)
    static let orange = Color(0xFF9500)
    static let green = Color(0x34C759)

    // The palette follows the theme: light is the default (the examples use
    // it); `setThemeVariant("dark")` switches to the dark values.
    static var primary: Color { get { return themeColor(0x10131A, 0xF2F3F7) } }
    static var secondary: Color { get { return themeColor(0x6B7280, 0x8A90A2) } }
    static var accent: Color { get { return themeColor(0x2F6BFF, 0x5B8CFF) } }
    static var background: Color { get { return themeColor(0xF2F3F7, 0x0B0C10) } }
    static var surface: Color { get { return themeColor(0xFFFFFF, 0x151824) } }
    static var surface2: Color { get { return themeColor(0xE4E8F0, 0x232838) } }
}

/// The light or the dark value of a palette colour.
func themeColor(_ light: Int, _ dark: Int) -> Color {
    if usesDarkPalette {
        return Color(dark)
    }
    return Color(light)
}

/// A text style; `font(.title)` picks the size and the weight.
enum Font {
    case largeTitle
    case title
    case title2
    case title3
    case headline
    case body
    case callout
    case subheadline
    case footnote
    case caption
    case caption2
}

enum HorizontalAlignment {
    case leading
    case center
    case trailing
}

enum VerticalAlignment {
    case top
    case center
    case bottom
}

enum Alignment {
    case center
    case topLeading
    case top
    case topTrailing
    case leading
    case trailing
    case bottomLeading
    case bottom
    case bottomTrailing
}

enum TextAlignment {
    case leading
    case center
    case trailing
}

enum Axis {
    case vertical
    case horizontal
}

enum ButtonStyle {
    case plain
    case bordered
    case borderedProminent
}

enum Edge {
    case top
    case bottom
    case leading
    case trailing
    case horizontal
    case vertical
    case all
}

func fontSizeOf(_ font: Font) -> Int {
    switch font {
    case .largeTitle: return 34
    case .title: return 28
    case .title2: return 22
    case .title3: return 20
    case .headline: return 17
    case .body: return 17
    case .callout: return 16
    case .subheadline: return 15
    case .footnote: return 13
    case .caption: return 12
    case .caption2: return 11
    }
}

func isBoldFont(_ font: Font) -> Bool {
    switch font {
    case .largeTitle: return true
    case .title: return true
    case .title2: return true
    case .title3: return true
    case .headline: return true
    default: return false
    }
}

// ---------------------------------------------------------------------------
// The render state (one window per program)
// ---------------------------------------------------------------------------
var rootContent: (() -> Void)? = nil
var rootItems: [View] = []
var builderStack: [Builder] = []
var mountedRoot: Mounted? = nil
var appWindow = 0
var isRendering = false
var renderScheduled = false
var renderPending = false
var themeVariantName = "system"

/// A piece of application state.  Writing `value` invalidates the window: the
/// body is built again and the mounted controls are patched.
class State<T> {
    var value: T {
        didSet {
            invalidate()
        }
    }

    init(_ initial: T) {
        self.value = initial
    }
}

/// Ask for a re-render after the current pass (coalesced into one pass).
func invalidate() {
    if appWindow == 0 {
        return
    }
    if isRendering {
        renderPending = true
        return
    }
    if renderScheduled {
        return
    }
    renderScheduled = true
    ferrouiAfter(ms: 0) {
        renderScheduled = false
        renderNow()
    }
}

// ---------------------------------------------------------------------------
// Building a view tree
// ---------------------------------------------------------------------------
/// The children collected while the content closure of a container runs.
class Builder {
    var items: [View] = []
}

func pushBuilder() -> Builder {
    let builder = Builder()
    builderStack.append(builder)
    return builder
}

func popBuilder() -> Builder {
    return builderStack.removeLast()
}

/// Appends a constructed view to the enclosing builder (or to the root when
/// there is none).  Every view constructor ends with this call: that is what
/// makes `VStack { Text("a"); Text("b") }` collect its children without a
/// result builder in the language.
func emit(_ view: View) -> View {
    if builderStack.count > 0 {
        let builder = builderStack[builderStack.count - 1]
        builder.items.append(view)
    } else {
        rootItems.append(view)
    }
    return view
}

// ---------------------------------------------------------------------------
// The view node
// ---------------------------------------------------------------------------
let viewText = 1
let viewButton = 2
let viewTextField = 3
let viewToggle = 4
let viewSlider = 5
let viewProgress = 6
let viewVStack = 7
let viewHStack = 8
let viewZStack = 9
let viewSpacer = 10
let viewDivider = 11
let viewShape = 12
let viewList = 13
let viewScroll = 14

/// A view of the declarative tree: kind, properties and children.  The FerroUI
/// controls are created from it by `mount` and updated by `sync`.
class View {
    let kind: Int
    var children: [View] = []

    // text
    var text = ""
    var font = Font.body
    var fontSize = -1
    var isBold = false
    var foreground = -1
    var textAlignment = TextAlignment.leading
    var lineLimit = 0

    // appearance
    var paddingTop = 0
    var paddingBottom = 0
    var paddingLeading = 0
    var paddingTrailing = 0
    var background = -1
    var radius = 0
    var borderColor = -1
    var borderWidth = 0
    var width = -1
    var height = -1
    var minWidth = -1
    var minHeight = -1
    var maxWidth = -1
    var maxHeight = -1
    var opacityValue = 1.0
    var isHidden = false
    var isEnabled = true
    var clips = false
    var grow = 0.0
    var expanded = false

    // containers
    var spacing = 8
    var horizontalAlignment = HorizontalAlignment.center
    var verticalAlignment = VerticalAlignment.center
    var alignment = Alignment.center
    var axis = Axis.vertical

    // controls
    var placeholder = ""
    var textState: State<String>? = nil
    var boolState: State<Bool>? = nil
    var doubleState: State<Double>? = nil
    var sliderMinimum = 0.0
    var sliderMaximum = 1.0
    var progressValue = 0.0
    var progressTotal = 100.0
    var style = ButtonStyle.plain

    // actions
    var tapAction: (() -> Void)? = nil

    init(_ kind: Int) {
        self.kind = kind
    }

    // ------------------------------------------------------------- modifiers
    /// Space around the content.
    func padding(_ value: Int = 16) -> View {
        self.paddingTop = value
        self.paddingBottom = value
        self.paddingLeading = value
        self.paddingTrailing = value
        return self
    }

    /// Horizontal and vertical space around the content.
    func padding(_ horizontal: Int, _ vertical: Int) -> View {
        self.paddingTop = vertical
        self.paddingBottom = vertical
        self.paddingLeading = horizontal
        self.paddingTrailing = horizontal
        return self
    }

    /// Space on one edge (or on the pairs and all edges) of the content.
    func padding(_ edge: Edge, _ value: Int) -> View {
        if edge == .top {
            self.paddingTop = value
        } else if edge == .bottom {
            self.paddingBottom = value
        } else if edge == .leading {
            self.paddingLeading = value
        } else if edge == .trailing {
            self.paddingTrailing = value
        } else if edge == .horizontal {
            self.paddingLeading = value
            self.paddingTrailing = value
        } else if edge == .vertical {
            self.paddingTop = value
            self.paddingBottom = value
        } else {
            self.paddingTop = value
            self.paddingBottom = value
            self.paddingLeading = value
            self.paddingTrailing = value
        }
        return self
    }

    /// A fill colour behind the content.
    func background(_ color: Color) -> View {
        self.background = color.value
        return self
    }

    /// The colour of the text (and, on a shape, its fill).
    func foregroundColor(_ color: Color) -> View {
        self.foreground = color.value
        if self.kind == viewShape {
            self.background = color.value
        }
        return self
    }

    /// The fill of a shape.
    func fill(_ color: Color) -> View {
        self.background = color.value
        return self
    }

    /// Rounded corners of the background.
    func cornerRadius(_ value: Int) -> View {
        self.radius = value
        return self
    }

    /// A border around the view.
    func border(_ color: Color, width: Int = 1) -> View {
        self.borderColor = color.value
        self.borderWidth = width
        return self
    }

    /// The size of the view (`frame(width:)`, `frame(height:)`,
    /// `frame(width:height:)`, `frame(minWidth:...)`, `frame(maxWidth:...)`).
    /// One method with defaults rather than overloads: the runtime picks the
    /// first method of a name whose labels it can bind, so two `frame`
    /// overloads would make `.frame(height:)` bind the wrong one.
    func frame(width: Int = -1, height: Int = -1, minWidth: Int = -1,
               minHeight: Int = -1, maxWidth: Int = -1,
               maxHeight: Int = -1) -> View {
        self.width = width
        self.height = height
        self.minWidth = minWidth
        self.minHeight = minHeight
        self.maxWidth = maxWidth
        self.maxHeight = maxHeight
        return self
    }

    /// A text style.
    func font(_ font: Font) -> View {
        self.font = font
        return self
    }

    /// A font size in points.
    func font(size: Int) -> View {
        self.fontSize = size
        return self
    }

    /// A bold weight.
    func bold() -> View {
        self.isBold = true
        return self
    }

    /// The opacity of the view, from 0 to 1.
    func opacity(_ value: Double) -> View {
        self.opacityValue = value
        return self
    }

    /// Hide the view; it takes no room.
    func hidden() -> View {
        self.isHidden = true
        return self
    }

    /// Enable or disable the controls of the view.
    func disabled(_ flag: Bool = true) -> View {
        self.isEnabled = !flag
        return self
    }

    /// Cut the content at the bounds of the view.
    func clipped() -> View {
        self.clips = true
        return self
    }

    /// At most `count` lines of text (0: as many as fit).
    func lineLimit(_ count: Int) -> View {
        self.lineLimit = count
        return self
    }

    /// The alignment of the lines of text.
    func multilineTextAlignment(_ alignment: TextAlignment) -> View {
        self.textAlignment = alignment
        return self
    }

    /// Run `action` when the view is tapped (a button clicks).
    func onTapGesture(_ action: () -> Void) -> View {
        self.tapAction = action
        return self
    }

    /// The look of a button.
    func buttonStyle(_ style: ButtonStyle) -> View {
        self.style = style
        return self
    }

    /// The factor by which a flexible view grows in its container.
    func layoutGrow(_ factor: Double) -> View {
        self.grow = factor
        return self
    }

    /// Fill the room the container gives the view (SwiftUI writes
    /// `.frame(maxWidth: .infinity)` for this).
    func expand() -> View {
        self.expanded = true
        return self
    }
}

// ---------------------------------------------------------------------------
// Constructors
// ---------------------------------------------------------------------------
/// A line of text.
func Text(_ content: String) -> View {
    let node = View(viewText)
    node.text = content
    return emit(node)
}

/// A themed button.
func Button(_ title: String, _ action: () -> Void) -> View {
    let node = View(viewButton)
    node.text = title
    node.tapAction = action
    return emit(node)
}

/// An editable field bound to `text`.
func TextField(_ placeholder: String, text: State<String>) -> View {
    let node = View(viewTextField)
    node.placeholder = placeholder
    node.textState = text
    return emit(node)
}

/// A switch bound to `isOn`, with `title` next to it.
func Toggle(_ title: String, isOn: State<Bool>) -> View {
    let node = View(viewToggle)
    node.text = title
    node.boolState = isOn
    return emit(node)
}

/// A slider bound to `value`, between `minimum` and `maximum` (`in` is a
/// keyword of the language, so the bounds are named rather than carried by a
/// range).
func Slider(value: State<Double>, minimum: Double = 0.0,
            maximum: Double = 1.0) -> View {
    let node = View(viewSlider)
    node.doubleState = value
    node.sliderMinimum = minimum
    node.sliderMaximum = maximum
    return emit(node)
}

/// A progress bar: `value` of `total`; `ProgressView()` alone is the
/// indeterminate one (one function with defaults rather than two overloads,
/// for the same dispatch reason as `frame`).
func ProgressView(value: Double = -1.0, total: Double = 100.0) -> View {
    let node = View(viewProgress)
    node.progressValue = value
    node.progressTotal = total
    return emit(node)
}

/// A vertical stack of views.
func VStack(alignment: HorizontalAlignment = .center, spacing: Int = 8,
            _ content: () -> Void) -> View {
    let node = View(viewVStack)
    node.horizontalAlignment = alignment
    node.spacing = spacing
    let _ = pushBuilder()
    content()
    node.children = popBuilder().items
    return emit(node)
}

/// A horizontal stack of views.
func HStack(alignment: VerticalAlignment = .center, spacing: Int = 8,
            _ content: () -> Void) -> View {
    let node = View(viewHStack)
    node.verticalAlignment = alignment
    node.spacing = spacing
    let _ = pushBuilder()
    content()
    node.children = popBuilder().items
    return emit(node)
}

/// Views stacked on top of each other.
func ZStack(alignment: Alignment = .center, _ content: () -> Void) -> View {
    let node = View(viewZStack)
    node.alignment = alignment
    let _ = pushBuilder()
    content()
    node.children = popBuilder().items
    return emit(node)
}

/// A scrollable column of rows.
func List(_ content: () -> Void) -> View {
    let node = View(viewList)
    node.spacing = 0
    let _ = pushBuilder()
    content()
    node.children = popBuilder().items
    return emit(node)
}

/// A scrollable area along `axis`.
func ScrollView(_ axis: Axis = .vertical, _ content: () -> Void) -> View {
    let node = View(viewScroll)
    node.axis = axis
    let _ = pushBuilder()
    content()
    node.children = popBuilder().items
    return emit(node)
}

/// A flexible space that pushes the views of a stack apart.
func Spacer(minLength: Int = 0) -> View {
    let node = View(viewSpacer)
    node.grow = 1.0
    node.minHeight = minLength
    return emit(node)
}

/// A one-point separator line.
func Divider() -> View {
    let node = View(viewDivider)
    return emit(node)
}

/// A rounded rectangle shape; give it a frame and a fill.
func RoundedRectangle(cornerRadius: Int = 8) -> View {
    let node = View(viewShape)
    node.radius = cornerRadius
    return emit(node)
}

/// A rectangle shape; give it a frame and a fill.
func Rectangle() -> View {
    let node = View(viewShape)
    return emit(node)
}

/// A circle shape; give it a frame and a fill.
func Circle() -> View {
    let node = View(viewShape)
    node.radius = 500
    return emit(node)
}

/// The children of the closure, without a view of their own.
func Group(_ content: () -> Void) {
    let _ = pushBuilder()
    content()
    let items = popBuilder().items
    var index = 0
    while index < items.count {
        let _ = emit(items[index])
        index += 1
    }
}

/// One view per element of `items`, without a view of their own.
func ForEach<T>(_ items: [T], _ content: (T) -> Void) {
    for item in items {
        content(item)
    }
}

// ---------------------------------------------------------------------------
// The mounted tree
// ---------------------------------------------------------------------------
/// One mounted view: the border wrapper (`outer`), the host control and the
/// handle its children are added to (`childTarget`).
class Mounted {
    var kind = 0
    var outer = 0
    var host = 0
    var childTarget = 0
    var children: [Mounted] = []
    var view: View? = nil
    var pushedText = ""
}

func destroyTree(_ mounted: Mounted) {
    var index = 0
    while index < mounted.children.count {
        destroyTree(mounted.children[index])
        index += 1
    }
    mounted.children = []
    if mounted.childTarget != 0 && mounted.childTarget != mounted.host {
        ferrouiDestroy(handle: mounted.childTarget)
    }
    if mounted.host != 0 {
        ferrouiDestroy(handle: mounted.host)
    }
    if mounted.outer != 0 && mounted.outer != mounted.host {
        ferrouiDestroy(handle: mounted.outer)
    }
}

// ---------------------------------------------------------------------------
// Mounting: view tree -> FerroUI controls
// ---------------------------------------------------------------------------
func createControl(_ parent: Int, _ kind: Int) -> Int {
    return ferrouiCreate(parent: parent, kind: kind)
}

/// The Border wrapper that carries padding, background, corners and border.
func createWrapper(_ view: View) -> Int {
    let wrapper = createControl(0, kindBorder)
    applyStyle(view, wrapper)
    return wrapper
}

func applyStyle(_ view: View, _ wrapper: Int) {
    if view.paddingTop > 0 || view.paddingBottom > 0 ||
            view.paddingLeading > 0 || view.paddingTrailing > 0 {
        ferrouiSetThickness(handle: wrapper, property: thicknessPadding,
                            left: view.paddingLeading, top: view.paddingTop,
                            right: view.paddingTrailing,
                            bottom: view.paddingBottom)
    } else {
        ferrouiSetThickness(handle: wrapper, property: thicknessPadding,
                            left: 0, top: 0, right: 0, bottom: 0)
    }
    if view.background >= 0 {
        ferrouiSetColor(handle: wrapper, property: colorBackground,
                        argb: view.background)
    }
    if view.radius > 0 {
        ferrouiSetF64(handle: wrapper, property: f64CornerRadius,
                      value: Double(view.radius))
    }
    if view.borderColor >= 0 && view.borderWidth > 0 {
        ferrouiSetColor(handle: wrapper, property: colorBorder,
                        argb: view.borderColor)
        ferrouiSetThickness(handle: wrapper, property: thicknessBorder,
                            left: view.borderWidth, top: view.borderWidth,
                            right: view.borderWidth, bottom: view.borderWidth)
    }
}

/// The host control a view kind maps to.
func createHost(_ view: View) -> Int {
    if view.kind == viewText {
        return createControl(0, kindTextBlock)
    }
    if view.kind == viewButton {
        return createControl(0, kindButton)
    }
    if view.kind == viewTextField {
        return createControl(0, kindTextBox)
    }
    if view.kind == viewToggle {
        return createControl(0, kindToggleSwitch)
    }
    if view.kind == viewSlider {
        return createControl(0, kindSlider)
    }
    if view.kind == viewProgress {
        return createControl(0, kindProgressBar)
    }
    if view.kind == viewVStack || view.kind == viewHStack {
        return createControl(0, kindFlexPanel)
    }
    if view.kind == viewList || view.kind == viewScroll {
        return createControl(0, kindScrollViewer)
    }
    return createControl(0, kindPanel)
}

/// The control the children of a container mount into.
func createChildTarget(_ view: View, _ host: Int) -> Int {
    if view.kind == viewList || view.kind == viewScroll {
        let panel = createControl(host, kindFlexPanel)
        if view.kind == viewList || view.axis == .vertical {
            ferrouiSetFlex(handle: panel, direction: flexColumn,
                           justify: justifyStart, align: flexAlignStart,
                           columnSpacing: 0, rowSpacing: view.spacing)
        } else {
            ferrouiSetFlex(handle: panel, direction: flexRow,
                           justify: justifyStart, align: flexAlignStart,
                           columnSpacing: view.spacing, rowSpacing: 0)
        }
        return panel
    }
    if view.kind == viewVStack || view.kind == viewHStack ||
            view.kind == viewZStack {
        return host
    }
    return 0
}

func mount(_ view: View, _ inheritedColor: Int) -> Mounted {
    let mounted = Mounted()
    mounted.kind = view.kind
    mounted.view = view
    mounted.outer = createWrapper(view)
    mounted.host = createHost(view)
    mounted.childTarget = createChildTarget(view, mounted.host)
    ferrouiAddChild(parent: mounted.outer, child: mounted.host)
    applyView(view, mounted, inheritedColor)
    wireEvents(view, mounted)
    mountChildren(view, mounted, inheritedColor)
    return mounted
}

func mountChildren(_ view: View, _ mounted: Mounted, _ inheritedColor: Int) {
    let target = mounted.childTarget
    if target == 0 {
        return
    }
    let childColor = effectiveForeground(view, inheritedColor)
    var index = 0
    while index < view.children.count {
        let child = view.children[index]
        let childMounted = mount(child, childColor)
        applyChildAlignment(view, childMounted)
        ferrouiAddChild(parent: target, child: childMounted.outer)
        mounted.children.append(childMounted)
        index += 1
    }
}

/// Whether a container holds a child that fills the container.
func hasExpandedChild(_ view: View) -> Bool {
    var index = 0
    while index < view.children.count {
        if view.children[index].expanded {
            return true
        }
        index += 1
    }
    return false
}

func effectiveForeground(_ view: View, _ inheritedColor: Int) -> Int {
    if view.foreground >= 0 {
        return view.foreground
    }
    return inheritedColor
}

/// The alignment of a stack/ZStack becomes the alignment of the child wrapper,
/// which is what the parent arranges.
func applyChildAlignment(_ parent: View, _ mounted: Mounted) {
    if parent.kind == viewVStack {
        if mounted.view != nil && mounted.view!.expanded {
            ferrouiSetEnum(handle: mounted.outer,
                           property: enumHorizontalAlignment, value: 0)
            return
        }
        if parent.horizontalAlignment == .leading {
            ferrouiSetEnum(handle: mounted.outer,
                           property: enumHorizontalAlignment,
                           value: hAlignLeading)
        } else if parent.horizontalAlignment == .trailing {
            ferrouiSetEnum(handle: mounted.outer,
                           property: enumHorizontalAlignment,
                           value: hAlignTrailing)
        } else {
            ferrouiSetEnum(handle: mounted.outer,
                           property: enumHorizontalAlignment,
                           value: hAlignCenter)
        }
        return
    }
    if parent.kind == viewHStack {
        if parent.verticalAlignment == .top {
            ferrouiSetEnum(handle: mounted.outer, property: enumVerticalAlignment,
                           value: vAlignTop)
        } else if parent.verticalAlignment == .bottom {
            ferrouiSetEnum(handle: mounted.outer, property: enumVerticalAlignment,
                           value: vAlignBottom)
        } else {
            ferrouiSetEnum(handle: mounted.outer, property: enumVerticalAlignment,
                           value: vAlignCenter)
        }
        return
    }
    if parent.kind == viewZStack {
        ferrouiSetEnum(handle: mounted.outer, property: enumHorizontalAlignment,
                       value: alignmentHorizontal(parent.alignment))
        ferrouiSetEnum(handle: mounted.outer, property: enumVerticalAlignment,
                       value: alignmentVertical(parent.alignment))
    }
}

func alignmentHorizontal(_ alignment: Alignment) -> Int {
    switch alignment {
    case .center: return hAlignCenter
    case .topLeading: return hAlignLeading
    case .top: return hAlignCenter
    case .topTrailing: return hAlignTrailing
    case .leading: return hAlignLeading
    case .trailing: return hAlignTrailing
    case .bottomLeading: return hAlignLeading
    case .bottom: return hAlignCenter
    case .bottomTrailing: return hAlignTrailing
    }
}

func alignmentVertical(_ alignment: Alignment) -> Int {
    switch alignment {
    case .center: return vAlignCenter
    case .topLeading: return vAlignTop
    case .top: return vAlignTop
    case .topTrailing: return vAlignTop
    case .leading: return vAlignCenter
    case .trailing: return vAlignCenter
    case .bottomLeading: return vAlignBottom
    case .bottom: return vAlignBottom
    case .bottomTrailing: return vAlignBottom
    }
}

/// The properties of a view, set again on every pass (which also patches an
/// existing mounted view).
func applyView(_ view: View, _ mounted: Mounted, _ inheritedColor: Int) {
    let wrapper = mounted.outer
    let host = mounted.host
    let inherited = effectiveForeground(view, inheritedColor)

    // the outer box: size, visibility, opacity
    if view.width >= 0 {
        ferrouiSetF64(handle: wrapper, property: f64Width,
                      value: Double(view.width))
    }
    if view.height >= 0 {
        ferrouiSetF64(handle: wrapper, property: f64Height,
                      value: Double(view.height))
    }
    if view.minWidth >= 0 {
        ferrouiSetF64(handle: wrapper, property: f64MinWidth,
                      value: Double(view.minWidth))
    }
    if view.minHeight >= 0 {
        ferrouiSetF64(handle: wrapper, property: f64MinHeight,
                      value: Double(view.minHeight))
    }
    if view.maxWidth >= 0 {
        ferrouiSetF64(handle: wrapper, property: f64MaxWidth,
                      value: Double(view.maxWidth))
    }
    if view.maxHeight >= 0 {
        ferrouiSetF64(handle: wrapper, property: f64MaxHeight,
                      value: Double(view.maxHeight))
    }
    ferrouiSetBool(handle: wrapper, property: boolIsVisible,
                   value: !view.isHidden)
    ferrouiSetF64(handle: wrapper, property: f64Opacity, value: view.opacityValue)
    if view.clips {
        ferrouiSetBool(handle: wrapper, property: boolClipToBounds, value: true)
    }
    if view.grow > 0.0 {
        ferrouiSetGrow(handle: wrapper, grow: view.grow)
    }
    if view.expanded {
        ferrouiSetEnum(handle: wrapper, property: enumHorizontalAlignment,
                       value: 0)
        ferrouiSetEnum(handle: wrapper, property: enumVerticalAlignment,
                       value: 0)
    }

    // text and the controls
    if view.kind == viewText {
        ferrouiSetString(handle: host, property: strText, value: view.text)
        applyTextStyle(view, host, inherited)
    } else if view.kind == viewButton {
        ferrouiSetString(handle: host, property: strContent, value: view.text)
        applyTextStyle(view, host, inherited)
        applyButtonStyle(view, host, wrapper)
        ferrouiSetBool(handle: host, property: boolIsEnabled,
                       value: view.isEnabled)
    } else if view.kind == viewTextField {
        applyTextField(view, mounted, inherited)
    } else if view.kind == viewToggle {
        applyToggle(view, mounted)
    } else if view.kind == viewSlider {
        applySlider(view, host)
    } else if view.kind == viewProgress {
        applyProgress(view, host)
    }

    // containers with layout of their own
    if view.kind == viewVStack {
        var align = flexAlignmentOf(view)
        if hasExpandedChild(view) {
            align = flexAlignStretch
        }
        ferrouiSetFlex(handle: host, direction: flexColumn,
                       justify: justifyStart, align: align,
                       columnSpacing: 0, rowSpacing: view.spacing)
    } else if view.kind == viewHStack {
        var align = viewAlignOf(view)
        if hasExpandedChild(view) {
            align = flexAlignStretch
        }
        ferrouiSetFlex(handle: host, direction: flexRow,
                       justify: justifyStart, align: align,
                       columnSpacing: view.spacing, rowSpacing: 0)
    } else if view.kind == viewList {
        ferrouiSetFlex(handle: mounted.childTarget, direction: flexColumn,
                       justify: justifyStart, align: flexAlignStart,
                       columnSpacing: 0, rowSpacing: view.spacing)
    } else if view.kind == viewScroll {
        if view.axis == .vertical {
            ferrouiSetFlex(handle: mounted.childTarget, direction: flexColumn,
                           justify: justifyStart, align: flexAlignStart,
                           columnSpacing: 0, rowSpacing: view.spacing)
        } else {
            ferrouiSetFlex(handle: mounted.childTarget, direction: flexRow,
                           justify: justifyStart, align: flexAlignStart,
                           columnSpacing: view.spacing, rowSpacing: 0)
        }
    } else if view.kind == viewDivider {
        ferrouiSetF64(handle: wrapper, property: f64Height, value: 1.0)
        ferrouiSetColor(handle: wrapper, property: colorBackground,
                        argb: 0x2E3340)
    } else if view.kind == viewSpacer {
        ferrouiSetGrow(handle: wrapper, grow: 1.0)
    }
}

func flexAlignmentOf(_ view: View) -> Int {
    if view.horizontalAlignment == .leading {
        return flexAlignStart
    }
    if view.horizontalAlignment == .trailing {
        return flexAlignEnd
    }
    return flexAlignCenter
}

func viewAlignOf(_ view: View) -> Int {
    if view.verticalAlignment == .top {
        return flexAlignStart
    }
    if view.verticalAlignment == .bottom {
        return flexAlignEnd
    }
    return flexAlignCenter
}

func applyTextStyle(_ view: View, _ host: Int, _ inheritedColor: Int) {
    var size = fontSizeOf(view.font)
    if view.fontSize > 0 {
        size = view.fontSize
    }
    ferrouiSetF64(handle: host, property: f64FontSize, value: Double(size))
    var weight = 400
    if view.isBold || isBoldFont(view.font) {
        weight = 700
    }
    ferrouiSetEnum(handle: host, property: enumFontWeight, value: weight)
    if inheritedColor >= 0 {
        ferrouiSetColor(handle: host, property: colorForeground,
                        argb: inheritedColor)
    }
    if view.kind == viewText {
        ferrouiSetEnum(handle: host, property: enumTextAlignment,
                       value: textAlignmentValue(view.textAlignment))
        ferrouiSetEnum(handle: host, property: enumTextWrapping, value: 1)
        if view.lineLimit > 0 {
            ferrouiSetI32(handle: host, property: i32MaxLines,
                          value: view.lineLimit)
        }
    }
}

func textAlignmentValue(_ alignment: TextAlignment) -> Int {
    switch alignment {
    case .leading: return textAlignLeading
    case .center: return textAlignCenter
    case .trailing: return textAlignTrailing
    }
}

func applyButtonStyle(_ view: View, _ host: Int, _ wrapper: Int) {
    if view.style == .borderedProminent {
        ferrouiSetColor(handle: host, property: colorBackground,
                        argb: Color.accent.value)
        ferrouiSetColor(handle: host, property: colorForeground,
                        argb: Color.background.value)
        ferrouiSetF64(handle: host, property: f64CornerRadius, value: 12.0)
        ferrouiSetThickness(handle: wrapper, property: thicknessPadding,
                            left: 14, top: 8, right: 14, bottom: 8)
    } else if view.style == .bordered {
        ferrouiSetColor(handle: wrapper, property: colorBorder,
                        argb: Color.accent.value)
        ferrouiSetThickness(handle: wrapper, property: thicknessBorder,
                            left: 1, top: 1, right: 1, bottom: 1)
        ferrouiSetF64(handle: wrapper, property: f64CornerRadius, value: 12.0)
        ferrouiSetThickness(handle: wrapper, property: thicknessPadding,
                            left: 14, top: 8, right: 14, bottom: 8)
        ferrouiSetColor(handle: host, property: colorForeground,
                        argb: Color.accent.value)
    }
}

func applyTextField(_ view: View, _ mounted: Mounted, _ inherited: Int) {
    let host = mounted.host
    ferrouiSetString(handle: host, property: strWatermark,
                     value: view.placeholder)
    if view.textState != nil {
        let state = view.textState!
        if state.value != mounted.pushedText {
            ferrouiSetString(handle: host, property: strText, value: state.value)
            mounted.pushedText = state.value
        }
    }
    var size = fontSizeOf(view.font)
    if view.fontSize > 0 {
        size = view.fontSize
    }
    ferrouiSetF64(handle: host, property: f64FontSize, value: Double(size))
    if inherited >= 0 {
        ferrouiSetColor(handle: host, property: colorForeground,
                        argb: inherited)
    }
    ferrouiSetBool(handle: host, property: boolIsEnabled, value: view.isEnabled)
}

func applyToggle(_ view: View, _ mounted: Mounted) {
    let host = mounted.host
    ferrouiSetString(handle: host, property: strContent, value: view.text)
    if view.boolState != nil {
        let state = view.boolState!
        ferrouiSetBool(handle: host, property: boolIsChecked, value: state.value)
    }
    ferrouiSetBool(handle: host, property: boolIsEnabled, value: view.isEnabled)
}

func applySlider(_ view: View, _ host: Int) {
    ferrouiSetF64(handle: host, property: f64Minimum, value: view.sliderMinimum)
    ferrouiSetF64(handle: host, property: f64Maximum, value: view.sliderMaximum)
    if view.doubleState != nil {
        let state = view.doubleState!
        ferrouiSetF64(handle: host, property: f64Value, value: state.value)
    }
    ferrouiSetBool(handle: host, property: boolIsEnabled, value: view.isEnabled)
}

func applyProgress(_ view: View, _ host: Int) {
    if view.progressValue < 0.0 {
        ferrouiSetBool(handle: host, property: boolIsIndeterminate, value: true)
        return
    }
    ferrouiSetBool(handle: host, property: boolIsIndeterminate, value: false)
    ferrouiSetF64(handle: host, property: f64Minimum, value: 0.0)
    ferrouiSetF64(handle: host, property: f64Maximum, value: view.progressTotal)
    ferrouiSetF64(handle: host, property: f64Value, value: view.progressValue)
}

// ---------------------------------------------------------------------------
// Patching: build again, walk the mounted tree in lockstep
// ---------------------------------------------------------------------------
func sync(_ mounted: Mounted?, _ view: View, _ inheritedColor: Int) -> Mounted {
    if mounted == nil {
        return mount(view, inheritedColor)
    }
    let existing = mounted!
    if existing.kind != view.kind {
        return mount(view, inheritedColor)
    }
    existing.view = view
    applyView(view, existing, inheritedColor)
    syncChildren(view, existing, inheritedColor)
    return existing
}

func syncChildren(_ view: View, _ mounted: Mounted, _ inheritedColor: Int) {
    let target = mounted.childTarget
    if target == 0 {
        return
    }
    let previous = mounted.children
    var children: [Mounted] = []
    let childColor = effectiveForeground(view, inheritedColor)
    var index = 0
    let shared = min(previous.count, view.children.count)
    while index < shared {
        let child = view.children[index]
        let old = previous[index]
        let updated = sync(old, child, childColor)
        if updated != old {
            ferrouiRemoveChild(parent: target, child: old.outer)
            ferrouiInsertChild(parent: target, index: index,
                               child: updated.outer)
            destroyTree(old)
        }
        applyChildAlignment(view, updated)
        if updated.kind == viewSpacer {
            ferrouiSetGrow(handle: updated.outer, grow: 1.0)
        } else {
            ferrouiSetGrow(handle: updated.outer, grow: 0.0)
        }
        children.append(updated)
        index += 1
    }
    while index < view.children.count {
        let child = view.children[index]
        let childMounted = mount(child, childColor)
        applyChildAlignment(view, childMounted)
        ferrouiAddChild(parent: target, child: childMounted.outer)
        children.append(childMounted)
        index += 1
    }
    while children.count < previous.count {
        let removed = previous[previous.count - 1]
        ferrouiRemoveChild(parent: target, child: removed.outer)
        destroyTree(removed)
        let _ = previous.removeLast()
    }
    mounted.children = children
}

// ---------------------------------------------------------------------------
// Event wiring (one subscription per mounted control; the handler reads the
// current view through the mounted node, so a patch never needs to re-subscribe)
// ---------------------------------------------------------------------------
func wireEvents(_ view: View, _ mounted: Mounted) {
    if view.tapAction != nil {
        let target = mounted
        ferrouiOnTap(handle: mounted.host) {
            if target.view != nil {
                let current = target.view!
                if current.tapAction != nil {
                    let action = current.tapAction!
                    action()
                }
            }
        }
    }
    if view.kind == viewTextField {
        let target = mounted
        let host = mounted.host
        ferrouiOnTextChanged(handle: host) {
            if target.view != nil {
                let current = target.view!
                if current.textState != nil {
                    let currentText = ferrouiGetText(handle: host)
                    target.pushedText = currentText
                    let state = current.textState!
                    state.value = currentText
                }
            }
        }
    }
    if view.kind == viewToggle {
        let target = mounted
        let host = mounted.host
        ferrouiOnCheckedChanged(handle: host) {
            if target.view != nil {
                let current = target.view!
                if current.boolState != nil {
                    let state = current.boolState!
                    state.value = ferrouiGetChecked(handle: host)
                }
            }
        }
    }
    if view.kind == viewSlider {
        let target = mounted
        let host = mounted.host
        ferrouiOnValueChanged(handle: host) {
            if target.view != nil {
                let current = target.view!
                if current.doubleState != nil {
                    let state = current.doubleState!
                    state.value = ferrouiGetValue(handle: host)
                }
            }
        }
    }
}

// ---------------------------------------------------------------------------
// The application
// ---------------------------------------------------------------------------
/// The scene of an application: the window it opens and its content.  It is
/// what `WindowGroup { ... }` returns, so an app body reads
/// `var body: Scene { WindowGroup(...) { ContentView() } }` like SwiftUI.
class Scene {
    let title: String
    let width: Int
    let height: Int
    let background: Color
    let borderless: Bool
    let content: () -> Void

    init(_ title: String = "", width: Int = 390, height: Int = 844,
         background: Color = Color(0x0B0C10), borderless: Bool = true,
         _ content: () -> Void) {
        self.title = title
        self.width = width
        self.height = height
        self.background = background
        self.borderless = borderless
        self.content = content
    }
}

/// The window of an application (a scene in the SwiftUI vocabulary).
func WindowGroup(_ title: String = "", width: Int = 390, height: Int = 844,
                 background: Color = Color(0x0B0C10),
                 borderless: Bool = true, _ content: () -> Void) -> Scene {
    return Scene(title, width: width, height: height, background: background,
                 borderless: borderless) {
        content()
    }
}

/// The theme variant of the application ("dark", "light" or "system"); call it
/// before `launch`.
/// Pick the theme: `"light"` (the default of the examples), `"dark"` or
/// `"system"`.  Call it before `launch`.
func setThemeVariant(_ name: String) {
    themeVariantName = name
    if name == "dark" {
        usesDarkPalette = true
    } else {
        usesDarkPalette = false
    }
}

/// The size the layout has to fit in: the client area of the window.
func clientWidth() -> Int {
    return ferrouiClientWidth()
}

func clientHeight() -> Int {
    return ferrouiClientHeight()
}

/// A PNG of the window, `milliseconds` from now (docs and tests).
func snapshot(after milliseconds: Int, path: String) {
    ferrouiSnapshot(delayMs: milliseconds, path: path)
}

/// Run `action` once, `milliseconds` from now, on the UI thread.
func after(_ milliseconds: Int, _ action: () -> Void) {
    ferrouiAfter(ms: milliseconds, action: action)
}

/// End the application.
func quitApp() {
    ferrouiQuit()
}

/// Print a line to the console.
func printLog(_ message: String) {
    ferrouiLog(message: message)
}

/// The version of the bridge and of FerroUI.
func swimUIVersion() -> String {
    return "SwimUI " + ferrouiVersion()
}

/// The PNG a test run asked for (`SWIMUI_IMAGE`), or "".
func imagePath() -> String {
    return ferrouiImagePath()
}

/// The time a test run keeps the window open (`SWIMUI_QUIT_MS`), or 0.
func autoQuitMs() -> Int {
    return ferrouiAutoQuitMs()
}

/// Start the application of a scene (the second half of a SwiftUI `@main`).
func launch(_ scene: Scene) {
    let window = scene
    rootContent = window.content
    ferrouiSetThemeVariant(name: themeVariantName)
    ferrouiRun {
        let handle = ferrouiWindow(width: window.width, height: window.height,
                                   title: window.title,
                                   background: window.background.value,
                                   onClosed: {})
        if window.borderless {
            ferrouiSetDecorations(window: handle, mode: decorationsNone)
        } else {
            ferrouiSetDecorations(window: handle, mode: decorationsFull)
        }
        ferrouiOnReady(window: handle) {
            appWindow = handle
            renderNow()
            let quit = autoQuitMs()
            if quit > 0 {
                ferrouiAfter(ms: quit) {
                    ferrouiQuit()
                }
            }
            let image = imagePath()
            if !image.isEmpty {
                ferrouiSnapshot(delayMs: 900, path: image)
            }
        }
    }
}

/// Run an application with a window built from a closure (a shortcut for small
/// programs; `launch(WindowGroup(...))` is the SwiftUI shape).
func runApp(_ title: String = "SwimUI", width: Int = 390, height: Int = 844,
            _ content: () -> Void) {
    launch(WindowGroup(title, width: width, height: height) {
        content()
    })
}

/// Build the view tree of the window again and patch the mounted controls.
func renderNow() {
    if isRendering || appWindow == 0 {
        return
    }
    isRendering = true
    rootItems = []
    if let build = rootContent {
        build()
    }
    if rootItems.count > 0 {
        let node = rootItems[0]
        let previous = mountedRoot
        let next = sync(previous, node, -1)
        if previous == nil {
            ferrouiAddChild(parent: appWindow, child: next.outer)
        } else if previous!.outer != next.outer {
            // A new root (the kind at the root changed): attach it and drop the
            // old tree.  Handles are compared rather than the objects: an
            // `Optional` compared with a value makes a new box, which is never
            // the same object as the one it holds.
            ferrouiAddChild(parent: appWindow, child: next.outer)
            destroyTree(previous!)
        }
        mountedRoot = next
    }
    rootItems = []
    isRendering = false
    if renderPending {
        renderPending = false
        renderNow()
    }
}

// ---------------------------------------------------------------------------
// Test helpers (a machine drives the UI without a pointer)
// ---------------------------------------------------------------------------
/// The text of every label, field and button of the mounted tree, separated by
/// `|`: what the last render left on the screen.
func renderedTexts() -> String {
    return collectTexts(mountedRoot, "")
}

func collectTexts(_ mounted: Mounted?, _ collected: String) -> String {
    if mounted == nil {
        return collected
    }
    let node = mounted!
    var text = collected
    if node.kind == viewText || node.kind == viewButton {
        text = text + ferrouiGetText(handle: node.host) + "|"
    }
    var index = 0
    while index < node.children.count {
        text = collectTexts(node.children[index], text)
        index += 1
    }
    return text
}

/// Raise the click event of the first button whose title is `title`, as a
/// pointer would; returns whether such a button is on the screen.
func tapButton(_ title: String) -> Bool {
    return tapButtonIn(mountedRoot, title)
}

func tapButtonIn(_ mounted: Mounted?, _ title: String) -> Bool {
    if mounted == nil {
        return false
    }
    let node = mounted!
    if node.kind == viewButton {
        if ferrouiGetText(handle: node.host) == title {
            ferrouiRaiseClick(handle: node.host)
            return true
        }
    }
    var index = 0
    while index < node.children.count {
        if tapButtonIn(node.children[index], title) {
            return true
        }
        index += 1
    }
    return false
}

/// Raise the tap gesture of the first view of `kind` (the tests use it for the
/// rows of a list, which are not buttons).
func tapKind(_ kind: Int) -> Bool {
    return tapKindIn(mountedRoot, kind)
}

func tapKindIn(_ mounted: Mounted?, _ kind: Int) -> Bool {
    if mounted == nil {
        return false
    }
    let node = mounted!
    if node.kind == kind {
        ferrouiRaiseClick(handle: node.host)
        return true
    }
    var index = 0
    while index < node.children.count {
        if tapKindIn(node.children[index], kind) {
            return true
        }
        index += 1
    }
    return false
}

/// Read the value of a control back (a slider or a progress bar).
func controlValue(_ kind: Int) -> Double {
    return controlValueIn(mountedRoot, kind)
}

func controlValueIn(_ mounted: Mounted?, _ kind: Int) -> Double {
    if mounted == nil {
        return -1.0
    }
    let node = mounted!
    if node.kind == kind {
        return ferrouiGetValue(handle: node.host)
    }
    var index = 0
    while index < node.children.count {
        let value = controlValueIn(node.children[index], kind)
        if value >= 0.0 {
            return value
        }
        index += 1
    }
    return -1.0
}
