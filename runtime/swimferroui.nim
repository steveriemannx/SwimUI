## swimferroui -- the FerroUI GUI bridge of Swim.
##
## This module is **not** part of the core runtime: it is only compiled into a
## program whose sources write ``import FerroUI`` (the compiler then emits
## ``import swimferroui`` into the generated Nim).  It keeps every FerroUI
## detail on the Nim side and exposes a small, flat, Swift-friendly surface
## built from ``Int`` handles (an opaque reference to a FerroUI control),
## plain ``Int`` / ``Double`` / ``String`` / ``Bool`` parameters and
## ``proc()`` callbacks, so that a ``.sw`` source never needs to mention a Nim
## or a Rust type.
##
## The Swift-facing names of these procedures are declared in
## ``swimc/codegen.py`` (``FERROUI_FUNCS``); keep both sides in sync.
##
## The FerroUI side of the bridge is a shared library built from the Rust crate
## in ``ffi/`` (``scripts/build-ffi.sh`` builds it into ``build/``); it hosts
## the FerroUI application, the visual tree and the native window.  This module
## declares its C ABI (``ffi/include/ferroui_swim.h``) and turns the bridge's
## callbacks into Nim closures.

import std/[os, strutils, tables]

# ---------------------------------------------------------------------------
# The shared library of the bridge
# ---------------------------------------------------------------------------
const
  ## The directory the bridge library is looked up in; `scripts/build-ffi.sh`
  ## writes it to `build/`, and `-d:swimFerroUILibDir=<dir>` overrides it.
  swimFerroUILibDir {.strdefine.} = ""

  bridgeFileName =
    when defined(windows): "ferroui_swim.dll"
    elif defined(macosx): "libferroui_swim.dylib"
    else: "libferroui_swim.so"

  swimRootDir = currentSourcePath().parentDir.parentDir
  bridgeLibPath =
    if swimFerroUILibDir.len > 0: swimFerroUILibDir / bridgeFileName
    else: swimRootDir / "build" / bridgeFileName

  bridgeAbiVersion = 1

  ## `-d:swimFerroUIImage=<png>`: where the program should write a snapshot of
  ## its window (a test or documentation run); empty means none.
  swimFerroUIImage {.strdefine.} = ""

  ## `-d:swimFerroUIQuitMs=<ms>`: close the window after that many
  ## milliseconds (a test run without a person in front of the screen); 0 means
  ## never.
  swimFerroUIQuitMs {.intdefine.} = 0

# The C ABI of the bridge (ffi/include/ferroui_swim.h).
type
  FerroSwimCallback = proc (user: int64) {.cdecl.}

proc cAbiVersion(): cint {.importc: "ferro_swim_abi_version", cdecl,
                           dynlib: bridgeLibPath.}
proc cVersion(): cstring {.importc: "ferro_swim_version", cdecl,
                           dynlib: bridgeLibPath.}
proc cLastError(): cstring {.importc: "ferro_swim_last_error", cdecl,
                             dynlib: bridgeLibPath.}
proc cRun(ready: FerroSwimCallback; user: int64)
  {.importc: "ferro_swim_run", cdecl, dynlib: bridgeLibPath.}
proc cQuit() {.importc: "ferro_swim_quit", cdecl, dynlib: bridgeLibPath.}
proc cWindow(width, height: cdouble): int64
  {.importc: "ferro_swim_window", cdecl, dynlib: bridgeLibPath.}
proc cCreate(kind: int32; parent: int64): int64
  {.importc: "ferro_swim_create", cdecl, dynlib: bridgeLibPath.}
proc cAddChild(parent, child: int64)
  {.importc: "ferro_swim_add_child", cdecl, dynlib: bridgeLibPath.}
proc cSetF64(handle: int64; property: int32; value: cdouble)
  {.importc: "ferro_swim_set_f64", cdecl, dynlib: bridgeLibPath.}
proc cSetStr(handle: int64; property: int32; value: cstring)
  {.importc: "ferro_swim_set_str", cdecl, dynlib: bridgeLibPath.}
proc cSetBool(handle: int64; property: int32; value: cint)
  {.importc: "ferro_swim_set_bool", cdecl, dynlib: bridgeLibPath.}
proc cSetColor(handle: int64; property: int32; argb: uint32)
  {.importc: "ferro_swim_set_color", cdecl, dynlib: bridgeLibPath.}
proc cSetThickness(handle: int64; property: int32; left, top, right, bottom: cdouble)
  {.importc: "ferro_swim_set_thickness", cdecl, dynlib: bridgeLibPath.}
proc cSetEnum(handle: int64; property: int32; value: int32)
  {.importc: "ferro_swim_set_enum", cdecl, dynlib: bridgeLibPath.}
proc cClientWidth(): cdouble
  {.importc: "ferro_swim_client_width", cdecl, dynlib: bridgeLibPath.}
proc cClientHeight(): cdouble
  {.importc: "ferro_swim_client_height", cdecl, dynlib: bridgeLibPath.}
proc cSetThemeVariant(name: cstring)
  {.importc: "ferro_swim_set_theme_variant", cdecl, dynlib: bridgeLibPath.}
proc cSetDecorations(handle: int64; mode: int32)
  {.importc: "ferro_swim_set_decorations", cdecl, dynlib: bridgeLibPath.}
proc cGetF64(handle: int64; property: int32): cdouble
  {.importc: "ferro_swim_get_f64", cdecl, dynlib: bridgeLibPath.}
proc cGetStr(handle: int64; property: int32): cstring
  {.importc: "ferro_swim_get_str", cdecl, dynlib: bridgeLibPath.}
proc cGetBool(handle: int64; property: int32): cint
  {.importc: "ferro_swim_get_bool", cdecl, dynlib: bridgeLibPath.}
proc cSetFrame(handle: int64; x, y, width, height: cdouble)
  {.importc: "ferro_swim_set_frame", cdecl, dynlib: bridgeLibPath.}
proc cOn(handle: int64; event: int32; callback: FerroSwimCallback; user: int64)
  {.importc: "ferro_swim_on", cdecl, dynlib: bridgeLibPath.}
proc cAfter(delayMs: cdouble; callback: FerroSwimCallback; user: int64)
  {.importc: "ferro_swim_after", cdecl, dynlib: bridgeLibPath.}
proc cClose(handle: int64)
  {.importc: "ferro_swim_close", cdecl, dynlib: bridgeLibPath.}
proc cRaiseClick(handle: int64)
  {.importc: "ferro_swim_raise_click", cdecl, dynlib: bridgeLibPath.}
proc cSnapshot(delayMs: cdouble; path: cstring)
  {.importc: "ferro_swim_snapshot", cdecl, dynlib: bridgeLibPath.}
proc cRelease(handle: int64)
  {.importc: "ferro_swim_release", cdecl, dynlib: bridgeLibPath.}

# ---------------------------------------------------------------------------
# The identifiers of the C ABI
# ---------------------------------------------------------------------------
const
  kindCanvas = 1
  kindStackPanel = 2
  kindBorder = 3
  kindTextBlock = 4
  kindButton = 5
  kindTextBox = 6
  kindCheckBox = 7
  kindSlider = 8
  kindProgressBar = 9
  kindScrollViewer = 10

  f64Width = 1
  f64Height = 2
  f64FontSize = 7
  f64Opacity = 8
  f64CornerRadius = 9
  f64Spacing = 10
  f64Minimum = 11
  f64Maximum = 12
  f64Value = 13

  strText = 1
  strTitle = 2
  strWatermark = 3
  strContent = 4

  boolIsVisible = 1
  boolIsChecked = 2
  boolIsIndeterminate = 3
  boolIsEnabled = 4

  colorBackground = 1
  colorForeground = 2
  colorBorder = 3

  thicknessMargin = 1
  thicknessPadding = 2
  thicknessBorder = 3

  enumHorizontalAlignment = 1
  enumVerticalAlignment = 2
  enumOrientation = 3
  enumTextAlignment = 4
  enumTextWrapping = 5
  enumFontWeight = 6
  enumFontStyle = 7

  eventTap = 1
  eventTextChanged = 2
  eventCheckedChanged = 3
  eventValueChanged = 4
  eventOpened = 5
  eventClosed = 6

# ---------------------------------------------------------------------------
# Error reporting
# ---------------------------------------------------------------------------
proc bridgeError(where: string) =
  ## Reports what the last bridge call failed with, if anything.  The bridge
  ## is best effort about what it cannot do (a theme that lacks a property,
  ## for one), so a failure is reported and programming continues.
  let message = cLastError()
  if message != nil:
    let text = $message
    if text.len > 0:
      stderr.writeLine("swimferroui: " & where & ": " & text)
      stderr.flushFile()

proc checkBridge() =
  ## Fails with an explanation when the bridge library is missing, instead of
  ## letting the C library loader report a path.
  if not fileExists(bridgeLibPath):
    stderr.writeLine("swimferroui: the FerroUI bridge is not built:")
    stderr.writeLine("swimferroui:   " & bridgeLibPath)
    stderr.writeLine("swimferroui: run scripts/build-ffi.sh in the SwimUI checkout first")
    stderr.flushFile()
    quit(1)
  if int(cAbiVersion()) != bridgeAbiVersion:
    stderr.writeLine("swimferroui: the FerroUI bridge has ABI version " &
                     $int(cAbiVersion()) & ", this runtime needs " &
                     $bridgeAbiVersion)
    stderr.writeLine("swimferroui: rebuild it with scripts/build-ffi.sh")
    stderr.flushFile()
    quit(1)

# ---------------------------------------------------------------------------
# Callbacks
# ---------------------------------------------------------------------------
## The bridge calls back with a plain C function pointer and an `Int`; the
## closures live here, keyed by the number the pointer is called with, so the
## `.sw` side can write ordinary trailing closures.
var ferroCallbacks: seq[proc()] = @[]
var ferroBuild: proc() = nil

proc invokeCallback(user: int64) {.cdecl.} =
  let index = int(user) - 1
  if index >= 0 and index < ferroCallbacks.len:
    let callback = ferroCallbacks[index]
    if callback != nil:
      callback()

proc invokeBuild(user: int64) {.cdecl.} =
  let build = ferroBuild
  ferroBuild = nil
  if build != nil:
    build()

proc registerCallback(callback: proc()): int64 =
  if callback == nil:
    return 0
  ferroCallbacks.add(callback)
  int64(ferroCallbacks.len)

# ---------------------------------------------------------------------------
# Colours and other conversions
# ---------------------------------------------------------------------------
const
  noColor = -1

proc argb(color: int): uint32 =
  ## `0xRRGGBB` (opaque) or `0xAARRGGBB`.
  if color > 0xFFFFFF:
    result = uint32(color and 0xFFFFFFFF)
  else:
    result = 0xFF000000'u32 or uint32(color and 0xFFFFFF)

proc applyColor(handle, property, color: int) =
  if color >= 0:
    cSetColor(int64(handle), int32(property), argb(color))
    bridgeError("set color")

proc applyFrame(handle, x, y, width, height: int) =
  cSetFrame(int64(handle), cdouble(x), cdouble(y), cdouble(width), cdouble(height))
  bridgeError("set frame")

proc applyText(handle: int; text: string) =
  cSetStr(int64(handle), int32(strText), text)
  bridgeError("set text")

proc applyFont(handle, size: int; bold: bool) =
  if size > 0:
    cSetF64(int64(handle), int32(f64FontSize), cdouble(size))
    bridgeError("set font size")
  cSetEnum(int64(handle), int32(enumFontWeight), int32(if bold: 700 else: 400))
  bridgeError("set font weight")

proc newControl(parent, kind: int): int =
  result = int(cCreate(int32(kind), int64(parent)))
  bridgeError("create control " & $kind)

## The content canvas of a container: the child the `.sw` side adds to.
var containerContents: Table[int, int] = initTable[int, int]()

# ---------------------------------------------------------------------------
# The application
# ---------------------------------------------------------------------------
proc swimFerroUIRun*(build: proc()) =
  ## Starts the application; `build` runs once the framework is initialized and
  ## creates the window and the view tree of the program.  Blocks until the
  ## window closes.
  checkBridge()
  ferroBuild = build
  cRun(invokeBuild, 0)
  bridgeError("run")

proc swimFerroUIQuit*() =
  ## Ends the application: the window closes and `ferrouiRun` returns.
  cQuit()
  bridgeError("quit")

proc swimFerroUIClose*(window: int) =
  cClose(int64(window))
  bridgeError("close window")

proc swimFerroUIWindow*(width, height: int; title: string; background: int;
                        onClosed: proc()): int =
  checkBridge()
  result = int(cWindow(cdouble(width), cdouble(height)))
  bridgeError("create window")
  if result == 0:
    return
  if title.len > 0:
    cSetStr(int64(result), int32(strTitle), title)
    bridgeError("set window title")
  applyColor(result, colorBackground, background)
  let closed = registerCallback(onClosed)
  if closed != 0:
    cOn(int64(result), int32(eventClosed), invokeCallback, closed)
    bridgeError("subscribe window closed")

# ---------------------------------------------------------------------------
# Containers
# ---------------------------------------------------------------------------
proc swimFerroUICanvas*(parent: int): int =
  ## A panel that positions its children at the coordinates it is given.
  result = newControl(parent, kindCanvas)

proc swimFerroUIStack*(parent: int; vertical: bool; spacing: int): int =
  ## A panel that lays its children out one after the other.
  result = newControl(parent, kindStackPanel)
  if result != 0:
    cSetEnum(int64(result), int32(enumOrientation),
             int32(if vertical: 1 else: 0))
    bridgeError("set stack orientation")
    cSetF64(int64(result), int32(f64Spacing), cdouble(spacing))
    bridgeError("set stack spacing")

proc swimFerroUIBox*(parent, x, y, width, height, fill, radius,
                     borderColor, borderWidth: int): int =
  ## A rounded, optionally bordered background with a canvas for children.
  let border = newControl(parent, kindBorder)
  if border == 0:
    return 0
  applyFrame(border, x, y, width, height)
  applyColor(border, colorBackground, fill)
  if radius > 0:
    cSetF64(int64(border), int32(f64CornerRadius), cdouble(radius))
    bridgeError("set corner radius")
  if borderColor >= 0 and borderWidth > 0:
    applyColor(border, colorBorder, borderColor)
    cSetThickness(int64(border), int32(thicknessBorder), cdouble(borderWidth),
                  cdouble(borderWidth), cdouble(borderWidth), cdouble(borderWidth))
    bridgeError("set border thickness")
  let canvas = newControl(border, kindCanvas)
  if canvas != 0:
    # The canvas fills the box; a canvas has no size of its own.
    cSetF64(int64(canvas), int32(f64Width), cdouble(width))
    cSetF64(int64(canvas), int32(f64Height), cdouble(height))
    bridgeError("size box canvas")
    containerContents[border] = canvas
  result = border

proc swimFerroUIScrollView*(parent, x, y, width, height, fill, radius: int): int =
  ## A scrollable viewport that positions the children of its canvas.
  let viewer = newControl(parent, kindScrollViewer)
  if viewer == 0:
    return 0
  applyFrame(viewer, x, y, width, height)
  applyColor(viewer, colorBackground, fill)
  if radius > 0:
    cSetF64(int64(viewer), int32(f64CornerRadius), cdouble(radius))
    bridgeError("set scroll viewer radius")
  let canvas = newControl(viewer, kindCanvas)
  if canvas != 0:
    containerContents[viewer] = canvas
  result = viewer

proc swimFerroUIContent*(container: int): int =
  ## The canvas the children of a box or a scroll view go to.
  containerContents.getOrDefault(container, 0)

# ---------------------------------------------------------------------------
# Controls
# ---------------------------------------------------------------------------
proc swimFerroUILabel*(parent, x, y, width, height: int; text: string;
                       size, color, align: int; bold: bool): int =
  result = newControl(parent, kindTextBlock)
  if result == 0:
    return
  applyFrame(result, x, y, width, height)
  applyText(result, text)
  applyFont(result, size, bold)
  applyColor(result, colorForeground, color)
  cSetEnum(int64(result), int32(enumTextAlignment), int32(align))
  bridgeError("set label alignment")
  cSetEnum(int64(result), int32(enumTextWrapping), 1)
  bridgeError("set label wrapping")

proc swimFerroUIButton*(parent, x, y, width, height: int; title: string;
                        size: int; bold: bool; fill, titleColor, radius: int;
                        onTap: proc()): int =
  result = newControl(parent, kindButton)
  if result == 0:
    return
  applyFrame(result, x, y, width, height)
  cSetStr(int64(result), int32(strContent), title)
  bridgeError("set button title")
  applyFont(result, size, bold)
  applyColor(result, colorBackground, fill)
  applyColor(result, colorForeground, titleColor)
  if radius > 0:
    cSetF64(int64(result), int32(f64CornerRadius), cdouble(radius))
    bridgeError("set button radius")
  let tapped = registerCallback(onTap)
  if tapped != 0:
    cOn(int64(result), int32(eventTap), invokeCallback, tapped)
    bridgeError("subscribe tap")

proc swimFerroUITextField*(parent, x, y, width, height: int; text: string;
                           placeholder: string; size: int;
                           onChanged: proc()): int =
  result = newControl(parent, kindTextBox)
  if result == 0:
    return
  applyFrame(result, x, y, width, height)
  if text.len > 0:
    cSetStr(int64(result), int32(strText), text)
    bridgeError("set text field text")
  if placeholder.len > 0:
    cSetStr(int64(result), int32(strWatermark), placeholder)
    bridgeError("set text field placeholder")
  applyFont(result, size, false)
  let changed = registerCallback(onChanged)
  if changed != 0:
    cOn(int64(result), int32(eventTextChanged), invokeCallback, changed)
    bridgeError("subscribe text changed")

proc swimFerroUICheckBox*(parent, x, y, width, height: int; text: string;
                          checked: bool; onChanged: proc()): int =
  result = newControl(parent, kindCheckBox)
  if result == 0:
    return
  applyFrame(result, x, y, width, height)
  cSetStr(int64(result), int32(strContent), text)
  bridgeError("set check box title")
  cSetBool(int64(result), int32(boolIsChecked), cint(if checked: 1 else: 0))
  bridgeError("set check box state")
  let changed = registerCallback(onChanged)
  if changed != 0:
    cOn(int64(result), int32(eventCheckedChanged), invokeCallback, changed)
    bridgeError("subscribe checked changed")

proc swimFerroUISlider*(parent, x, y, width, height: int; minimum, maximum,
                        value: int; onChanged: proc()): int =
  result = newControl(parent, kindSlider)
  if result == 0:
    return
  applyFrame(result, x, y, width, height)
  cSetF64(int64(result), int32(f64Minimum), cdouble(minimum))
  cSetF64(int64(result), int32(f64Maximum), cdouble(maximum))
  cSetF64(int64(result), int32(f64Value), cdouble(value))
  bridgeError("set slider range")
  let changed = registerCallback(onChanged)
  if changed != 0:
    cOn(int64(result), int32(eventValueChanged), invokeCallback, changed)
    bridgeError("subscribe value changed")

proc swimFerroUIProgressBar*(parent, x, y, width, height, percent: int): int =
  result = newControl(parent, kindProgressBar)
  if result == 0:
    return
  applyFrame(result, x, y, width, height)
  cSetF64(int64(result), int32(f64Minimum), 0.0)
  cSetF64(int64(result), int32(f64Maximum), 100.0)
  cSetF64(int64(result), int32(f64Value), cdouble(percent))
  bridgeError("set progress")
  if height > 0:
    cSetF64(int64(result), int32(f64CornerRadius), cdouble(height / 2))
    bridgeError("set progress radius")

# ---------------------------------------------------------------------------
# Properties
# ---------------------------------------------------------------------------
proc swimFerroUIClientWidth*(): int =
  ## The width of the client area of the window: the width the layout has to
  ## fit in, which is smaller than the requested width when the decorations or
  ## the screen take room from it.
  result = int(cClientWidth())
  bridgeError("client width")

proc swimFerroUIClientHeight*(): int =
  ## The height of the client area of the window.
  result = int(cClientHeight())
  bridgeError("client height")

proc swimFerroUISetThemeVariant*(name: string) =
  ## The theme variant of the application: "dark", "light" or "system".
  ## Call it before `ferrouiRun`.
  checkBridge()
  cSetThemeVariant(name)
  bridgeError("set theme variant")

proc swimFerroUISetDecorations*(handle, mode: int) =
  ## The decorations of a window: 0 none, 1 border only, 2 full.
  cSetDecorations(int64(handle), int32(mode))
  bridgeError("set decorations")

proc swimFerroUISetFrame*(handle, x, y, width, height: int) =
  applyFrame(handle, x, y, width, height)

proc swimFerroUISetText*(handle: int; text: string) =
  applyText(handle, text)

proc swimFerroUISetColor*(handle, color: int) =
  applyColor(handle, colorBackground, color)

proc swimFerroUISetTextColor*(handle, color: int) =
  applyColor(handle, colorForeground, color)

proc swimFerroUISetBorder*(handle, color, width: int) =
  applyColor(handle, colorBorder, color)
  if width > 0:
    cSetThickness(int64(handle), int32(thicknessBorder), cdouble(width),
                  cdouble(width), cdouble(width), cdouble(width))
    bridgeError("set border thickness")

proc swimFerroUISetHidden*(handle: int; hidden: bool) =
  cSetBool(int64(handle), int32(boolIsVisible), cint(if hidden: 0 else: 1))
  bridgeError("set visible")

proc swimFerroUISetOpacity*(handle, percent: int) =
  cSetF64(int64(handle), int32(f64Opacity), cdouble(percent) / 100.0)
  bridgeError("set opacity")

proc swimFerroUISetRadius*(handle, radius: int) =
  cSetF64(int64(handle), int32(f64CornerRadius), cdouble(radius))
  bridgeError("set corner radius")

proc swimFerroUISetFontSize*(handle, size: int) =
  cSetF64(int64(handle), int32(f64FontSize), cdouble(size))
  bridgeError("set font size")

proc swimFerroUISetBold*(handle: int; bold: bool) =
  cSetEnum(int64(handle), int32(enumFontWeight), int32(if bold: 700 else: 400))
  bridgeError("set font weight")

proc swimFerroUISetAlignment*(handle, align: int) =
  cSetEnum(int64(handle), int32(enumTextAlignment), int32(align))
  bridgeError("set text alignment")

proc swimFerroUISetProgress*(handle, percent: int) =
  cSetF64(int64(handle), int32(f64Value), cdouble(percent))
  bridgeError("set progress")

proc swimFerroUISetValue*(handle: int; value: float) =
  cSetF64(int64(handle), int32(f64Value), cdouble(value))
  bridgeError("set value")

proc swimFerroUISetChecked*(handle: int; checked: bool) =
  cSetBool(int64(handle), int32(boolIsChecked), cint(if checked: 1 else: 0))
  bridgeError("set checked")

proc swimFerroUISetSpacing*(handle, spacing: int) =
  cSetF64(int64(handle), int32(f64Spacing), cdouble(spacing))
  bridgeError("set spacing")

# ---------------------------------------------------------------------------
# Reading properties back
# ---------------------------------------------------------------------------
proc swimFerroUIGetValue*(handle: int): float =
  ## The value of a slider or a progress bar.
  result = float(cGetF64(int64(handle), int32(f64Value)))
  bridgeError("get value")

proc swimFerroUIGetText*(handle: int): string =
  ## The text of a label or a field, or the title of a button.
  let text = cGetStr(int64(handle), int32(strText))
  if text != nil:
    result = $text
  bridgeError("get text")

proc swimFerroUIGetVisible*(handle: int): bool =
  ## Whether a control is visible.
  result = cGetBool(int64(handle), int32(boolIsVisible)) != 0
  bridgeError("get visible")

proc swimFerroUIGetChecked*(handle: int): bool =
  ## Whether a check box is checked.
  result = cGetBool(int64(handle), int32(boolIsChecked)) != 0
  bridgeError("get checked")

# ---------------------------------------------------------------------------
# Events and timers
# ---------------------------------------------------------------------------
proc subscribe(handle, event: int; action: proc()) =
  let callback = registerCallback(action)
  if callback != 0:
    cOn(int64(handle), int32(event), invokeCallback, callback)
    bridgeError("subscribe event " & $event)

proc swimFerroUIOnReady*(handle: int; onReady: proc()) =
  ## Runs `onReady` once the window is shown, when its client area is known.
  subscribe(handle, eventOpened, onReady)

proc swimFerroUIOnTap*(handle: int; onTap: proc()) =
  subscribe(handle, eventTap, onTap)

proc swimFerroUIOnTextChanged*(handle: int; onChanged: proc()) =
  subscribe(handle, eventTextChanged, onChanged)

proc swimFerroUIOnCheckedChanged*(handle: int; onChanged: proc()) =
  subscribe(handle, eventCheckedChanged, onChanged)

proc swimFerroUIOnValueChanged*(handle: int; onChanged: proc()) =
  subscribe(handle, eventValueChanged, onChanged)

proc swimFerroUIAfter*(ms: int; action: proc()) =
  ## Runs `action` once, after `ms` milliseconds on the UI thread.
  let callback = registerCallback(action)
  if callback != 0:
    cAfter(cdouble(ms), invokeCallback, callback)
    bridgeError("schedule action")

proc swimFerroUIRaiseClick*(handle: int) =
  ## Raises the click event of a button, as a pointer would: a test helper for a
  ## program that drives its own controls.
  cRaiseClick(int64(handle))
  bridgeError("raise click")

proc swimFerroUISnapshot*(delayMs: int; path: string) =
  ## Writes a PNG of the window to `path`, `delayMs` after the call.
  cSnapshot(cdouble(delayMs), path)
  bridgeError("snapshot")

# ---------------------------------------------------------------------------
# Diagnostics
# ---------------------------------------------------------------------------
proc swimFerroUIVersion*(): string =
  ## The version of the bridge library and of FerroUI.
  checkBridge()
  $cVersion()

proc swimFerroUIBridgePath*(): string =
  bridgeLibPath

proc swimFerroUIImagePath*(): string =
  ## The PNG the program should snapshot its window into, from
  ## `-d:swimFerroUIImage=<path>`; empty when the build did not ask for one.
  swimFerroUIImage

proc swimFerroUIAutoQuitMs*(): int =
  ## How long the window stays open in a test run, from
  ## `-d:swimFerroUIQuitMs=<ms>`; 0 when the build did not ask for a limit.
  swimFerroUIQuitMs

proc swimFerroUILog*(message: string) =
  stderr.writeLine(message)
  stderr.flushFile()

proc swimFerroUIRelease*(handle: int) =
  cRelease(int64(handle))
  bridgeError("release handle")
