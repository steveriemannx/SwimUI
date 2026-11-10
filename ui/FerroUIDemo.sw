// FerroUIDemo.sw -- the SwimUI demo: a phone-sized photo library written in
// Swim and drawn by FerroUI.
//
//   import SwimUI      the Swift-style views over the FerroUI binding
//   canvas            390 x 844 points (an iPhone-sized, borderless window)
//   run               ./scripts/run-demo.sh
//
// The view is interactive: the segmented control swaps the hero file, the
// slider moves the upload percent, the check box switches the backup mode,
// tapping a row selects it, the two "+" buttons change the album and photo
// counts, the tab bar switches the bottom tab and a toast reports what
// happened.
//
//   ./scripts/run-demo.sh --snapshot ui/shots/demo.png
//   ./scripts/run-demo.sh --smoke          (one frame, then exit)

import SwimUI

// ---------------------------------------------------------------------------
// Palette
// ---------------------------------------------------------------------------
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
// Demo state (plain Swim globals, like properties of an app delegate)
// ---------------------------------------------------------------------------
var albumCount = 12
var photoCount = 3
var selectedCount = 0
var selectedRows = [false, false, false]
var segmentIndex = 0
var tabIndex = 0

// The views the callbacks update once the layout exists.
var header = View(handle: 0)
var subtitle = View(handle: 0)
var heroTitle = View(handle: 0)
var heroMeta = View(handle: 0)
var percentLabel = View(handle: 0)
var uploadBar = View(handle: 0)
var uploadSlider = View(handle: 0)
var autoBackup = View(handle: 0)
var countedLabel = View(handle: 0)
var badgeLabel = View(handle: 0)
var toast = View(handle: 0)
var toastLabel = View(handle: 0)
var allTab = View(handle: 0)
var favouritesTab = View(handle: 0)
var recentTab = View(handle: 0)
var homeTab = View(handle: 0)
var searchTab = View(handle: 0)
var profileTab = View(handle: 0)
var searchField = View(handle: 0)

// ---------------------------------------------------------------------------
// Behaviour (all callbacks run on the UI thread of FerroUI)
// ---------------------------------------------------------------------------

/// Show a short message at the bottom of the screen and hide it again.
func showToast(_ message: String) {
    toastLabel.setText(message)
    toast.setVisible(true)
    after(1500) {
        toast.setVisible(false)
    }
}

/// Paint the segment buttons for the active segment.
func updateSegments() {
    allTab.setColor(surface)
    favouritesTab.setColor(surface)
    recentTab.setColor(surface)
    allTab.setTextColor(muted)
    favouritesTab.setTextColor(muted)
    recentTab.setTextColor(muted)

    if activeSegment() == 0 {
        allTab.setColor(accent)
        allTab.setTextColor(bg)
    } else if activeSegment() == 1 {
        favouritesTab.setColor(accent)
        favouritesTab.setTextColor(bg)
    } else {
        recentTab.setColor(accent)
        recentTab.setTextColor(bg)
    }
}

func activeSegment() -> Int {
    return segmentIndex
}

func selectSegment(_ index: Int) {
    segmentIndex = index

    let titles = ["All photos", "Favourites", "Recent"]
    let heroes = ["sunset_beach.heic", "mountain_vlog.mov", "portrait_light.jpg"]
    let metas = ["4032 x 3024 - 12.4 MB", "1920 x 1080 - 48.2 MB", "3024 x 4032 - 4.1 MB"]
    let progress = [68, 92, 34]

    header.setText(titles[index])
    heroTitle.setText(heroes[index])
    heroMeta.setText(metas[index])
    uploadSlider.setValue(Float(progress[index]))
    uploadBar.setProgress(progress[index])
    percentLabel.setText("\(progress[index])%")

    updateSegments()
    showToast("Segment: \(titles[index])")
}

/// Paint the bottom tab buttons for the active tab.
func selectBottomTab(_ index: Int) {
    tabIndex = index
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

/// Toggle the selection dot of a recent row.
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

/// Add one recent row: an icon, two lines of text and a selection dot.
func makeRow(_ parent: View, _ index: Int, _ y: Int, _ title: String,
             _ details: String, _ iconColor: Int) {
    let row = parent.panel(x: 24, y: y, width: 342, height: 66, color: surface,
                           radius: 16)
    row.panel(x: 12, y: 14, width: 40, height: 40, color: iconColor,
              radius: 12)
    row.label(x: 68, y: 12, width: 200, height: 20, text: title, size: 15,
              bold: true)
    row.label(x: 68, y: 34, width: 200, height: 18, text: details, size: 12,
              color: muted)

    let dot = row.panel(x: 294, y: 20, width: 28, height: 28, color: surface2,
                        radius: 14)
    let innerDot = dot.panel(x: 9, y: 9, width: 10, height: 10, color: ink,
                             radius: 5)
    innerDot.setVisible(false)

    row.onTap {
        toggleSelection(index, dot: dot, innerDot: innerDot)
    }
}

// ---------------------------------------------------------------------------
// The application
// ---------------------------------------------------------------------------
setThemeVariant("dark")

runApp {
    let screen = Screen(width: 390, height: 844, title: "SwimUI - Library",
                        background: bg, borderless: true)

    screen.onReady {
        let height = screen.clientHeight()

        // Status bar -------------------------------------------------------
        screen.panel(x: 135, y: 8, width: 120, height: 30, color: 0x000000,
                     radius: 15)
        screen.label(x: 24, y: 12, width: 70, height: 20, text: "9:41",
                     size: 13, bold: true)
        screen.label(x: 270, y: 12, width: 96, height: 20, text: "5G   100%",
                     size: 12, color: muted, align: alignRight)

        // Header -----------------------------------------------------------
        header = screen.label(x: 24, y: 54, width: 260, height: 42,
                              text: "Library", size: 30, bold: true)
        subtitle = screen.label(x: 24, y: 96, width: 290, height: 18,
                                text: "384 photos - 12 albums", size: 12,
                                color: muted)
        screen.button(x: 326, y: 58, width: 40, height: 40, title: "+",
                      fill: surface2, titleColor: accent, radius: 20, size: 22,
                      bold: true) {
            albumCount += 1
            subtitle.setText("384 photos - \(albumCount) albums")
            showToast("Album \(albumCount) created")
        }

        // Search field -----------------------------------------------------
        searchField = screen.textField(x: 24, y: 122, width: 342, height: 40,
                                       placeholder: "Search photos, people, places",
                                       size: 13) {
            let text = searchField.text()
            if !text.isEmpty {
                subtitle.setText("Searching: \(text)")
            } else {
                subtitle.setText("384 photos - \(albumCount) albums")
            }
        }

        // Segmented control ------------------------------------------------
        screen.panel(x: 24, y: 176, width: 342, height: 36, color: surface,
                     radius: 18)
        allTab = screen.button(x: 24, y: 176, width: 114, height: 36,
                               title: "All", fill: accent, titleColor: bg,
                               radius: 18, size: 13, bold: true) {
            selectSegment(0)
        }
        favouritesTab = screen.button(x: 138, y: 176, width: 114, height: 36,
                                      title: "Favourites", fill: surface,
                                      titleColor: muted, radius: 18, size: 13) {
            selectSegment(1)
        }
        recentTab = screen.button(x: 252, y: 176, width: 114, height: 36,
                                  title: "Recent", fill: surface,
                                  titleColor: muted, radius: 18, size: 13) {
            selectSegment(2)
        }

        // Hero card --------------------------------------------------------
        let hero = screen.panel(x: 24, y: 228, width: 342, height: 200,
                                color: surface, radius: 20)
        hero.panel(x: 16, y: 16, width: 64, height: 64, color: orange,
                   radius: 16)
        heroTitle = hero.label(x: 94, y: 16, width: 190, height: 22,
                               text: "sunset_beach.heic", size: 16, bold: true)
        heroMeta = hero.label(x: 94, y: 40, width: 200, height: 18,
                              text: "4032 x 3024 - 12.4 MB", size: 12,
                              color: muted)
        let kindBadge = hero.panel(x: 264, y: 16, width: 62, height: 22,
                                   color: surface2, radius: 11)
        kindBadge.label(x: 0, y: 0, width: 62, height: 22, text: "PHOTO",
                        size: 10, color: muted, align: alignCenter, bold: true)
        hero.label(x: 16, y: 92, width: 220, height: 18,
                   text: "Uploading to iCloud", size: 12, color: muted)
        percentLabel = hero.label(x: 276, y: 92, width: 50, height: 18,
                                  text: "68%", size: 12, color: accent,
                                  align: alignRight, bold: true)
        uploadBar = hero.progressBar(x: 16, y: 118, width: 310, height: 6,
                                     percent: 68)
        uploadSlider = hero.slider(x: 16, y: 136, width: 172, height: 24,
                                   minimum: 0, maximum: 100, value: 68) {
            let percent = Int(uploadSlider.value())
            uploadBar.setProgress(percent)
            percentLabel.setText("\(percent)%")
        }
        autoBackup = hero.checkBox(x: 206, y: 136, width: 140, height: 24,
                                   text: "Auto-backup", checked: true) {
            if autoBackup.isChecked() {
                showToast("Auto-backup on")
            } else {
                showToast("Auto-backup off")
            }
        }

        // Section header ---------------------------------------------------
        screen.label(x: 24, y: 444, width: 160, height: 18, text: "RECENT",
                     size: 11, color: muted, bold: true)
        countedLabel = screen.label(x: 236, y: 444, width: 130, height: 18,
                                    text: "3 items", size: 11, color: muted,
                                    align: alignRight)

        // Recent list ------------------------------------------------------
        makeRow(screen.content(), 0, 466, "IMG_0032.HEIC", "Today - 2.8 MB",
                orange)
        makeRow(screen.content(), 1, 540, "mountain_vlog.mov",
                "Yesterday - 48.2 MB", green)
        makeRow(screen.content(), 2, 614, "portrait_light.jpg",
                "Yesterday - 4.1 MB", accent)

        // Floating action button -------------------------------------------
        screen.button(x: 310, y: height - 158, width: 56, height: 56,
                      title: "+", fill: accent, titleColor: ink, radius: 28,
                      size: 28) {
            photoCount += 1
            badgeLabel.setText("\(photoCount)")
            showToast("Added photo - \(photoCount) in album")
        }
        let badge = screen.panel(x: 348, y: height - 166, width: 24, height: 24,
                                 color: red, radius: 12)
        badgeLabel = badge.label(x: 0, y: 0, width: 24, height: 24, text: "3",
                                 size: 11, color: ink, align: alignCenter,
                                 bold: true)

        // Bottom tab bar ---------------------------------------------------
        screen.panel(x: 24, y: height - 96, width: 342, height: 72,
                     color: surface, radius: 24)
        homeTab = screen.button(x: 24, y: height - 96, width: 114, height: 72,
                                title: "Home", fill: surface2, titleColor: accent,
                                radius: 24, size: 13) {
            selectBottomTab(0)
        }
        searchTab = screen.button(x: 138, y: height - 96, width: 114, height: 72,
                                  title: "Search", fill: surface,
                                  titleColor: muted, radius: 24, size: 13) {
            selectBottomTab(1)
        }
        profileTab = screen.button(x: 252, y: height - 96, width: 114, height: 72,
                                   title: "Profile", fill: surface,
                                   titleColor: muted, radius: 24, size: 13) {
            selectBottomTab(2)
        }

        // Home indicator (the bar at the bottom of a modern phone) ---------
        screen.panel(x: 128, y: height - 14, width: 134, height: 5,
                     color: 0x2E3340, radius: 3)

        // Toast (hidden until something happens) ---------------------------
        toast = screen.panel(x: 95, y: height - 144, width: 200, height: 40,
                             color: surface2, radius: 20)
        toastLabel = toast.label(x: 0, y: 0, width: 200, height: 40,
                                 text: "", size: 12, color: ink,
                                 align: alignCenter)
        toast.setVisible(false)

        // A test or documentation run snapshots the window and quits -------
        let image = imagePath()
        if !image.isEmpty {
            screen.snapshot(after: 900, path: image)
        }
        let quitMs = autoQuitMs()
        if quitMs > 0 {
            after(quitMs) {
                quitApp()
            }
        }
        after(1500) {
            showToast("Welcome to SwimUI on FerroUI")
        }
    }
}
