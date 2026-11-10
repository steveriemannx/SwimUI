// PhoneDemo.sw -- a phone-sized GUI written in Swim and drawn with nimx.
//
//   import NimxUI      Swift-style wrapper around the nimx bridge
//   phone canvas      390 x 844 points (iPhone-sized)
//   memory            ARC (--mm:atomicArc, Swift-style atomic reference counts)
//
// The demo is interactive: switch tabs, tap list rows, tap the action button
// and the floating button.  Run it with projects-main/run.sh.

import NimxUI

// ---------------------------------------------------------------------------
// Layout constants (an iPhone-sized canvas, drawn 1:1 in points)
// ---------------------------------------------------------------------------
let screenWidth = 390
let screenHeight = 844

let bg = 0x0B0C10
let surface = 0x151824
let surface2 = 0x232838
let ink = 0xF2F3F7
let muted = 0x8A90A2
let accent = 0x5B8CFF
let green = 0x34C759
let orange = 0xFF9F0A
let red = 0xFF453A

// ---------------------------------------------------------------------------
// Demo state (plain Swim globals, like properties on an app delegate)
// ---------------------------------------------------------------------------
var activeSegment = 0
var photoCount = 3
var albumCount = 12
var selectedCount = 0
var selectedRows = [false, false, false]

// ---------------------------------------------------------------------------
// Window and view tree
// ---------------------------------------------------------------------------
let screen = nimxScreen(width: screenWidth, height: screenHeight,
                        title: "Swim x nimx - Library", background: bg)

// Status bar ----------------------------------------------------------------
screen.panel(x: 135, y: 8, width: 120, height: 30, color: 0x000000, radius: 15)
screen.label(x: 24, y: 12, width: 70, height: 20, text: "9:41", size: 13,
             bold: true)
screen.label(x: 270, y: 12, width: 96, height: 20, text: "5G   100%",
             size: 12, color: muted, align: alignRight)

// Header --------------------------------------------------------------------
let header = screen.label(x: 24, y: 54, width: 260, height: 42,
                          text: "Library", size: 30, bold: true)
let subtitle = screen.label(x: 24, y: 96, width: 280, height: 18,
                            text: "384 photos - 12 albums", size: 12,
                            color: muted)
let plusButton = screen.button(x: 326, y: 58, width: 40, height: 40,
                               title: "+", fill: surface2, titleColor: accent,
                               radius: 20, size: 22, bold: true) {
    albumCount += 1
    subtitle.setText("384 photos - \(albumCount) albums")
    showToast("Album \(albumCount) created")
}

// Search field --------------------------------------------------------------
screen.panel(x: 24, y: 122, width: 342, height: 40, color: surface, radius: 12)
screen.label(x: 44, y: 122, width: 280, height: 40,
             text: "Search photos, people, places", size: 13, color: muted)

// Segmented control ---------------------------------------------------------
screen.panel(x: 24, y: 176, width: 342, height: 36, color: surface, radius: 18)
let allTab = screen.button(x: 24, y: 176, width: 114, height: 36,
                           title: "All", fill: accent, titleColor: bg,
                           radius: 18, size: 13, bold: true) {
    selectSegment(0)
}
let favouritesTab = screen.button(x: 138, y: 176, width: 114, height: 36,
                                  title: "Favourites", fill: surface,
                                  titleColor: muted, radius: 18, size: 13) {
    selectSegment(1)
}
let recentTab = screen.button(x: 252, y: 176, width: 114, height: 36,
                              title: "Recent", fill: surface,
                              titleColor: muted, radius: 18, size: 13) {
    selectSegment(2)
}

// Hero card -----------------------------------------------------------------
screen.panel(x: 24, y: 228, width: 342, height: 188, color: surface, radius: 20)
screen.panel(x: 40, y: 244, width: 64, height: 64, color: orange, radius: 16)
let heroTitle = screen.label(x: 118, y: 244, width: 210, height: 22,
                             text: "sunset_beach.heic", size: 16, bold: true)
screen.label(x: 118, y: 268, width: 220, height: 18,
             text: "4032 x 3024 - 12.4 MB", size: 12, color: muted)
screen.panel(x: 288, y: 244, width: 62, height: 22, color: surface2, radius: 11)
screen.label(x: 288, y: 244, width: 62, height: 22, text: "PHOTO", size: 10,
             color: muted, align: alignCenter, bold: true)
screen.label(x: 40, y: 326, width: 220, height: 18,
             text: "Uploading to iCloud", size: 12, color: muted)
let percentLabel = screen.label(x: 300, y: 326, width: 50, height: 18,
                                text: "68%", size: 12, color: accent,
                                align: alignRight, bold: true)
let uploadBar = screen.progressBar(x: 40, y: 350, width: 310, height: 6,
                                   track: surface2, fill: accent, radius: 3,
                                   percent: 68)

// Section header ------------------------------------------------------------
screen.label(x: 24, y: 436, width: 160, height: 18, text: "RECENT", size: 11,
             color: muted, bold: true)
let countedLabel = screen.label(x: 250, y: 436, width: 116, height: 18,
                                text: "3 items", size: 11, color: muted,
                                align: alignRight)

// Recent list ---------------------------------------------------------------
makeRow(index: 0, y: 462, title: "IMG_0032.HEIC",
        details: "Today - 2.8 MB", iconColor: orange)
makeRow(index: 1, y: 536, title: "mountain_vlog.mov",
        details: "Yesterday - 48.2 MB", iconColor: green)
makeRow(index: 2, y: 610, title: "portrait_light.jpg",
        details: "Yesterday - 4.1 MB", iconColor: accent)

// Bottom tab bar ------------------------------------------------------------
screen.panel(x: 24, y: 748, width: 342, height: 72, color: surface, radius: 24)
let homeTab = screen.button(x: 24, y: 748, width: 114, height: 72,
                            title: "Home", fill: surface2, titleColor: accent,
                            radius: 24, size: 13) {
    selectBottomTab(0)
}
let searchTab = screen.button(x: 138, y: 748, width: 114, height: 72,
                              title: "Search", fill: surface,
                              titleColor: muted, radius: 24, size: 13) {
    selectBottomTab(1)
}
let profileTab = screen.button(x: 252, y: 748, width: 114, height: 72,
                               title: "Profile", fill: surface,
                               titleColor: muted, radius: 24, size: 13) {
    selectBottomTab(2)
}

// Home indicator (the little bar at the bottom of modern phones) -------------
screen.panel(x: 128, y: 830, width: 134, height: 5, color: 0x2E3340, radius: 3)

// Floating action button ----------------------------------------------------
let addButton = screen.button(x: 310, y: 686, width: 56, height: 56,
                              title: "+", fill: accent, titleColor: ink,
                              radius: 28, size: 28) {
    photoCount += 1
    badgeLabel.setText("\(photoCount)")
    showToast("Added photo - \(photoCount) in album")
}
let badge = screen.panel(x: 348, y: 678, width: 24, height: 24, color: red,
                         radius: 12)
let badgeLabel = badge.label(x: 0, y: 0, width: 24, height: 24, text: "3",
                             size: 11, color: ink, align: alignCenter,
                             bold: true)

// Toast (hidden until something happens) ------------------------------------
let toast = screen.panel(x: 95, y: 700, width: 200, height: 40,
                         color: surface2, radius: 20)
let toastLabel = toast.label(x: 0, y: 0, width: 200, height: 40,
                             text: "Saved", size: 12, color: ink,
                             align: alignCenter)
toast.setVisible(false)

// ---------------------------------------------------------------------------
// Behaviour (all callbacks run on the nimx UI thread)
// ---------------------------------------------------------------------------
func showToast(_ message: String) {
    toastLabel.setText(message)
    toast.setVisible(true)
    after(1200) {
        toast.setVisible(false)
    }
}

func selectSegment(_ index: Int) {
    activeSegment = index

    let titles = ["All photos", "Favourites", "Recent"]
    let heroes = ["sunset_beach.heic", "mountain_vlog.mov", "portrait_light.jpg"]
    let progress = [68, 92, 34]

    header.setText(titles[index])
    heroTitle.setText(heroes[index])
    uploadBar.setProgress(progress[index])
    percentLabel.setText("\(progress[index])%")

    allTab.setColor(surface)
    favouritesTab.setColor(surface)
    recentTab.setColor(surface)
    allTab.setTextColor(muted)
    favouritesTab.setTextColor(muted)
    recentTab.setTextColor(muted)

    if index == 0 {
        allTab.setColor(accent)
        allTab.setTextColor(bg)
    } else if index == 1 {
        favouritesTab.setColor(accent)
        favouritesTab.setTextColor(bg)
    } else {
        recentTab.setColor(accent)
        recentTab.setTextColor(bg)
    }

    showToast("Segment: \(titles[index])")
}

func selectBottomTab(_ index: Int) {
    let names = ["Home", "Search", "Profile"]

    homeTab.setColor(surface)
    searchTab.setColor(surface)
    profileTab.setColor(surface)
    homeTab.setTextColor(muted)
    searchTab.setTextColor(muted)
    profileTab.setTextColor(muted)

    if index == 0 {
        homeTab.setColor(surface2)
        homeTab.setTextColor(accent)
    } else if index == 1 {
        searchTab.setColor(surface2)
        searchTab.setTextColor(accent)
    } else {
        profileTab.setColor(surface2)
        profileTab.setTextColor(accent)
    }

    subtitle.setText("Bottom tab: \(names[index])")
    showToast("Tab: \(names[index])")
}

func toggleSelection(_ index: Int, dot: View, innerDot: View) {
    selectedRows[index] = !selectedRows[index]

    if selectedRows[index] {
        selectedCount += 1
        dot.setColor(accent)
        innerDot.setVisible(true)
    } else {
        selectedCount -= 1
        dot.setColor(surface2)
        innerDot.setVisible(false)
    }

    if selectedCount == 0 {
        countedLabel.setText("3 items")
    } else {
        countedLabel.setText("\(selectedCount) selected")
    }

    showToast("Toggled row \(index)")
}

func makeRow(index: Int, y: Int, title: String, details: String,
             iconColor: Int) {
    let row = screen.panel(x: 24, y: y, width: 342, height: 66,
                           color: surface, radius: 16)
    row.panel(x: 12, y: 14, width: 40, height: 40, color: iconColor,
              radius: 12)
    row.label(x: 68, y: 12, width: 200, height: 20, text: title, size: 15,
              bold: true)
    row.label(x: 68, y: 34, width: 200, height: 18, text: details, size: 12,
              color: muted)

    let dot = row.panel(x: 294, y: 20, width: 28, height: 28,
                        color: surface2, radius: 14)
    let innerDot = dot.panel(x: 9, y: 9, width: 10, height: 10,
                             color: ink, radius: 5)
    innerDot.setVisible(false)

    row.onTap {
        toggleSelection(index, dot: dot, innerDot: innerDot)
    }
}

// ---------------------------------------------------------------------------
// Run
// ---------------------------------------------------------------------------
runApp()
