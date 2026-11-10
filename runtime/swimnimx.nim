## swimnimx -- optional nimx GUI bridge for Swim.
##
## This module is **not** part of the core runtime: it is only compiled into a
## program that writes ``import Nimx`` (the compiler then emits
## ``import swimnimx`` into the generated Nim).  It keeps every nimx detail on
## the Nim side and exposes a small, flat, Swift-friendly surface built from
## ``Int`` handles (an opaque pointer to a nimx view), plain ``Int`` / ``String``
## / ``Bool`` parameters and ``proc()`` callbacks, so that a ``.sw`` source
## never needs to mention a Nim type.
##
## The Swim-facing names of these procedures are declared in
## ``swimc/codegen.py`` (``NIMX_FUNCS``); keep both sides in sync.

import std/os

import nimx / [ view, control, text_field, formatted_text, font, window, context,
               color, timer, layout, gesture_detector, event, app,
               linkage_details ]
import nimx / write_image_impl
import nimx / portable_gl
import nimx / private/windows/sdl_window
import sdl2 except Event, Rect, Point, Color, EventFilter
import opengl


# ---------------------------------------------------------------------------
# Handles
# ---------------------------------------------------------------------------
proc handleOf(v: View): int =
  cast[int](cast[pointer](v))

proc viewOf(handle: int): View =
  if handle == 0: return nil
  cast[View](cast[pointer](handle))


# ---------------------------------------------------------------------------
# Colors and fonts
# ---------------------------------------------------------------------------
const
  textAlignLeft = 0
  textAlignCenter = 1
  textAlignRight = 2

proc colorFromInt(value: int): Color =
  ## ``0xRRGGBB`` (opaque) or ``0xAARRGGBB``.
  var r, g, b, a: float32
  if value > 0xFFFFFF or value < 0:
    let v = value and 0xFFFFFFFF
    a = float32((v shr 24) and 0xFF) / 255.0
    r = float32((v shr 16) and 0xFF) / 255.0
    g = float32((v shr 8) and 0xFF) / 255.0
    b = float32(v and 0xFF) / 255.0
  else:
    a = 1.0
    r = float32((value shr 16) and 0xFF) / 255.0
    g = float32((value shr 8) and 0xFF) / 255.0
    b = float32(value and 0xFF) / 255.0
  result = newColor(r, g, b, a)

proc candidateFontFiles(bold: bool): seq[string] =
  ## nimx's stb_truetype glyph provider needs an actual .ttf.  Prefer a system
  ## font and fall back to a font shipped next to the executable.
  let style = if bold: "Bold" else: "Regular"
  result = @[]
  when defined(macosx):
    result.add "/System/Library/Fonts/Supplemental/Arial " & style & ".ttf"
    result.add "/System/Library/Fonts/Supplemental/Arial.ttf"
  result.add getAppDir() / "fonts" / ("App-" & style & ".ttf")
  result.add getAppDir() / "res" / ("App-" & style & ".ttf")
  result.add getAppDir() / ".." / "Resources" / ("App-" & style & ".ttf")
  when not defined(macosx):
    result.add "/usr/share/fonts/truetype/dejavu/DejaVuSans" &
               (if bold: "-Bold" else: "") & ".ttf"
    result.add "/usr/share/fonts/truetype/liberation/LiberationSans-" &
               style & ".ttf"

type FontKey = tuple[bold: bool, size: int]
var fontCache {.threadvar.}: seq[(FontKey, Font)]

proc swimFont(size: int, bold: bool): Font =
  let key: FontKey = (bold: bold, size: size)
  for (k, f) in fontCache:
    if k == key and not f.isNil:
      return f
  var font: Font
  for path in candidateFontFiles(bold):
    if fileExists(path):
      font = newFontWithFile(path, float32(size))
      break
  if font.isNil:
    when defined(macosx):
      font = newFontWithFace("Arial" & (if bold: "-Bold" else: ""),
                            float32(size))
  if font.isNil:
    font = systemFontOfSize(float32(size))
  fontCache.add((key, font))
  result = font


# ---------------------------------------------------------------------------
# View types
# ---------------------------------------------------------------------------
type
  SwimFill* = ref object of Control
    fillColor*: Color
    cornerRadius*: Coord

  SwimLabel* = ref object of Label

  SwimProgress* = ref object of View
    trackColor*: Color
    fillColor*: Color
    cornerRadius*: Coord
    percent*: int

  SwimSnapshotOverlay* = ref object of View
    pendingPath*: string
    snapshotting*: bool

var snapshotTarget {.threadvar.}: SwimSnapshotOverlay
var quitAfterSnapshot {.threadvar.}: bool
var mainWindow {.threadvar.}: Window

# nimx stores UI callbacks as `{.gcsafe.}` procs, while Swim closures are plain
# closures.  There is a single UI thread, so lifting a callback to gcsafe is
# sound; a cast keeps the closure environment intact.
proc asGcsafe(cb: proc(): void): proc(): void {.gcsafe.} =
  cast[proc(): void {.gcsafe.}](cb)

proc asGcsafeTap(cb: proc(point: Point): void): OnTapListener =
  cast[OnTapListener](cb)


proc captureFrameToPng(path: string) {.gcsafe.}


# ---------------------------------------------------------------------------
# View behaviour
# ---------------------------------------------------------------------------
method init(v: SwimFill) {.gcsafe.} =
  procCall v.Control.init()
  v.clickable = false
  v.fillColor = newColor(1, 1, 1, 1)
  v.cornerRadius = 0

method draw(v: SwimFill, r: Rect) {.gcsafe.} =
  let c = currentContext()
  if v.fillColor.a > 0.001:
    c.fillColor = v.fillColor
    c.strokeWidth = 0
    let radius = min(v.cornerRadius, min(v.bounds.width, v.bounds.height) / 2.0)
    if radius > 0.5:
      c.drawRoundedRect(v.bounds, radius)
    else:
      c.drawRect(v.bounds)

method init(v: SwimLabel) {.gcsafe.} =
  procCall v.Label.init()
  v.backgroundColor = clearColor()
  v.hasBezel = false
  v.editable = false
  v.selectable = false
  v.verticalAlignment = vaCenter

method init(v: SwimProgress) {.gcsafe.} =
  procCall v.View.init()
  v.trackColor = newColor(1, 1, 1, 0.08)
  v.fillColor = newColor(0.36, 0.55, 1.0, 1.0)
  v.cornerRadius = 3
  v.percent = 0

method draw(v: SwimProgress, r: Rect) {.gcsafe.} =
  let c = currentContext()
  let radius = min(v.cornerRadius, v.bounds.height / 2.0)
  c.strokeWidth = 0
  c.fillColor = v.trackColor
  c.drawRoundedRect(v.bounds, radius)
  let value = min(max(float32(v.percent) / 100.0, 0.0), 1.0)
  let fillWidth = v.bounds.width * value
  if fillWidth > 1:
    c.fillColor = v.fillColor
    c.drawRoundedRect(newRect(0, 0, max(fillWidth, radius * 2),
                              v.bounds.height), radius)

method draw(v: SwimSnapshotOverlay, r: Rect) {.gcsafe.} =
  if v.snapshotting or v.pendingPath.len == 0: return
  v.snapshotting = true
  let path = v.pendingPath
  v.pendingPath = ""
  captureFrameToPng(path)
  v.snapshotting = false
  if quitAfterSnapshot:
    discard setTimeout(0.15, asGcsafe(proc() = quit(0)))


proc captureFrameToPng(path: string) {.gcsafe.} =
  ## Read the window's OpenGL back buffer (the frame that was just drawn) and
  ## write it out as a PNG.
  let c = currentContext()
  if c.isNil: return
  let vp = c.gl.getViewport()
  let width = int(vp[2])
  let height = int(vp[3])
  if width <= 0 or height <= 0: return
  var pixels = newSeq[uint8](width * height * 4)
  glPixelStorei(GL_PACK_ALIGNMENT, 1)
  glReadPixels(0, 0, GLsizei(width), GLsizei(height), GLenum(GL_RGBA),
               GLenum(GL_UNSIGNED_BYTE), addr pixels[0])
  # OpenGL's origin is bottom-left; PNG wants top-left.
  var flipped = newSeq[uint8](width * height * 4)
  for y in 0 ..< height:
    let src = (height - 1 - y) * width * 4
    let dst = y * width * 4
    copyMem(addr flipped[dst], addr pixels[src], width * 4)
  let dir = parentDir(path)
  if dir.len != 0: createDir(dir)
  discard stbi_write_png(path.cstring, cint(width), cint(height), 4,
                         addr flipped[0], cint(width * 4))


proc place(v: View, x, y, width, height: int) =
  ## Absolute placement through nimx's kiwi layout solver.
  v.addConstraints([
    selfPHS.x == superPHS.x + float32(x),
    selfPHS.y == superPHS.y + float32(y),
    selfPHS.width == float32(width),
    selfPHS.height == float32(height),
  ])

proc setLabelProperties(v: SwimLabel, text: string, size, textColor, align: int,
                        bold: bool) =
  v.font = swimFont(size, bold)
  v.textColor = colorFromInt(textColor)
  case align
  of textAlignCenter: v.horizontalAlignment = haCenter
  of textAlignRight: v.horizontalAlignment = haRight
  else: v.horizontalAlignment = haLeft
  v.text = text


# ---------------------------------------------------------------------------
# Public bridge surface (called from Swim's `Nimx` module functions)
# ---------------------------------------------------------------------------
proc swimNimxWindow*(width, height: int, title: string,
                     background: int): int =
  let w = newWindow(newRect(80, 80, Coord(width), Coord(height)))
  # A phone-sized canvas: strip the desktop window decorations so the whole
  # window is exactly `width` x `height` points of UI, like a phone screen.
  when defined(macosx) or defined(linux) or defined(windows):
    let sdlWin = getSDLWindow(cast[SdlWindow](w))
    if not sdlWin.isNil:
      sdlWin.setBordered(False32)
      sdlWin.setPosition(120, 60)
      sdlWin.setSize(cint(width), cint(height))
  w.title = title
  mainWindow = w
  # The window is borderless (see above), so provide a keyboard way out.
  let quitFilter: EventFilter = proc(evt: var Event,
                                     control: var EventFilterControl): bool =
    if evt.kind == etKeyboard and evt.keyCode == VirtualKey.Escape and
        evt.buttonState == bsDown:
      quit(0)
    false
  mainApplication().pushEventFilter(quitFilter)
  let root = View.new()
  root.backgroundColor = colorFromInt(background)
  w.addSubview(root)
  root.addConstraints([
    selfPHS.x == superPHS.x,
    selfPHS.y == superPHS.y,
    selfPHS.width == superPHS.width,
    selfPHS.height == superPHS.height,
  ])

  # The snapshot overlay must draw last, after the whole UI, so that it can
  # read the finished frame back from the OpenGL buffer.
  snapshotTarget = SwimSnapshotOverlay.new()
  root.addSubview(snapshotTarget)
  snapshotTarget.addConstraints([
    selfPHS.x == superPHS.x,
    selfPHS.y == superPHS.y,
    selfPHS.width == superPHS.width,
    selfPHS.height == superPHS.height,
  ])

  # `-d:swimNimxSnapshotPath=/path/to.png` renders one frame to a PNG (and
  # quits) -- handy for CI and for previewing the UI without a screenshot tool.
  const swimNimxSnapshotPath {.strdefine.} = ""
  if swimNimxSnapshotPath.len > 0:
    quitAfterSnapshot = true
    discard setTimeout(0.9, asGcsafe(proc() =
      if not snapshotTarget.isNil:
        snapshotTarget.moveToFront()
        snapshotTarget.pendingPath = swimNimxSnapshotPath
        if not mainWindow.isNil: mainWindow.drawWindow()
    ))

  result = handleOf(root)


proc swimNimxPanel*(parent, x, y, width, height, fillColor,
                    radius: int): int =
  let p = SwimFill.new()
  p.fillColor = colorFromInt(fillColor)
  p.cornerRadius = Coord(radius)
  viewOf(parent).addSubview(p)
  place(p, x, y, width, height)
  result = handleOf(p)


proc swimNimxLabel*(parent, x, y, width, height, size, textColor, align: int,
                    bold: bool, text: string): int =
  let l = SwimLabel.new()
  l.setLabelProperties(text, size, textColor, align, bold)
  viewOf(parent).addSubview(l)
  place(l, x, y, width, height)
  result = handleOf(l)


proc swimNimxButton*(parent, x, y, width, height, fillColor, titleColor,
                     radius, size: int, bold: bool, title: string,
                     onTap: proc()): int =
  let b = SwimFill.new()
  b.fillColor = colorFromInt(fillColor)
  b.cornerRadius = Coord(radius)
  b.clickable = true
  b.onAction(asGcsafe(onTap))
  viewOf(parent).addSubview(b)
  place(b, x, y, width, height)
  let l = SwimLabel.new()
  l.setLabelProperties(title, size, titleColor, textAlignCenter, bold)
  b.addSubview(l)
  place(l, 0, 0, width, height)
  result = handleOf(b)


proc swimNimxOnTap*(handle: int, onTap: proc()) =
  let v = viewOf(handle)
  if v.isNil: return
  if v of Control:
    let c = Control(v)
    c.clickable = true
    c.onAction(asGcsafe(onTap))
    return
  let listener = asGcsafeTap(proc(tapPoint: Point) = onTap())
  let gd = newTapGestureDetector(listener)
  v.addGestureDetector(gd)


proc swimNimxSetText*(handle: int, text: string) =
  let v = viewOf(handle)
  if v.isNil: return
  if v of TextField:
    TextField(v).text = text
    return
  for s in v.subviews:
    if s of TextField:
      TextField(s).text = text
      return


proc swimNimxSetColor*(handle, colorValue: int) =
  let v = viewOf(handle)
  if v.isNil: return
  let c = colorFromInt(colorValue)
  if v of SwimLabel:
    SwimLabel(v).textColor = c
    SwimLabel(v).setNeedsDisplay()
  elif v of SwimFill:
    SwimFill(v).fillColor = c
    SwimFill(v).setNeedsDisplay()
  elif v of SwimProgress:
    SwimProgress(v).fillColor = c
    SwimProgress(v).setNeedsDisplay()
  elif v of TextField:
    TextField(v).textColor = c
    TextField(v).setNeedsDisplay()
  else:
    v.backgroundColor = c
    v.setNeedsDisplay()


proc swimNimxSetTextColor*(handle, colorValue: int) =
  let v = viewOf(handle)
  if v.isNil: return
  let c = colorFromInt(colorValue)
  if v of TextField:
    TextField(v).textColor = c
    TextField(v).setNeedsDisplay()
    return
  for s in v.subviews:
    if s of TextField:
      TextField(s).textColor = c
      TextField(s).setNeedsDisplay()
      return


proc swimNimxSetHidden*(handle: int, hidden: bool) =
  let v = viewOf(handle)
  if v.isNil: return
  v.hidden = hidden
  v.setNeedsDisplay()


proc swimNimxProgressBar*(parent, x, y, width, height, trackColor, fillColor,
                          radius, percent: int): int =
  let p = SwimProgress.new()
  p.trackColor = colorFromInt(trackColor)
  p.fillColor = colorFromInt(fillColor)
  p.cornerRadius = Coord(radius)
  p.percent = min(max(percent, 0), 100)
  viewOf(parent).addSubview(p)
  place(p, x, y, width, height)
  result = handleOf(p)


proc swimNimxSetProgress*(handle, percent: int) =
  let v = viewOf(handle)
  if v.isNil: return
  if v of SwimProgress:
    SwimProgress(v).percent = min(max(percent, 0), 100)
    SwimProgress(v).setNeedsDisplay()


proc swimNimxAfter*(ms: int, action: proc()) =
  discard setTimeout(float(ms) / 1000.0, asGcsafe(proc() = action()))


proc swimNimxSnapshot*(delayMs: int, path: string) =
  if snapshotTarget.isNil: return
  quitAfterSnapshot = true
  discard setTimeout(float(delayMs) / 1000.0, asGcsafe(proc() =
    if snapshotTarget.isNil: return
    snapshotTarget.moveToFront()
    snapshotTarget.pendingPath = path
    if not mainWindow.isNil: mainWindow.drawWindow()
  ))


# ---------------------------------------------------------------------------
# Application loop
# ---------------------------------------------------------------------------
# `sdlMain` contributes the macOS framework link flags nimx needs; on desktop
# platforms it has no run-time effect (the loop lives in `runUntilQuit`).
sdlMain()


proc swimNimxRun*() =
  # All views and layout constraints exist now: solve the layout once before
  # entering the event loop (nimx only re-solves when a window asks for it).
  if not mainWindow.isNil:
    mainWindow.needsLayout = true
    mainWindow.updateWindowLayout()
  runUntilQuit()


proc swimNimxQuit*() =
  quit(0)
