// LibraryApp.sw -- the SwimUI demo: a phone-sized photo library written in
// Swim with the SwiftUI-shaped layer over FerroUI.
//
//   import SwiftUI    declarative views, State, stacks, lists, controls
//   canvas            390 x 844 points, a borderless window
//   run               ./scripts/run-demo.sh
//
// The app is interactive: the segmented control swaps the hero file, the
// slider moves the upload percent, the switch toggles the backup mode, tapping
// a photo row selects it, the two "+" buttons change the album and photo
// counts, the bottom tabs switch and a toast reports what happened.

import SwiftUI

// ---------------------------------------------------------------------------
// The model: observable state, owned by the app and read by the views
// ---------------------------------------------------------------------------
final class PhotoRow {
    let title: String
    let details: String
    let color: Color
    let selected = State(false)

    init(_ title: String, _ details: String, _ color: Color) {
        self.title = title
        self.details = details
        self.color = color
    }
}

final class LibraryModel {
    let segment = State(0)
    let albums = State(12)
    let photos = State(384)
    let autoBackup = State(true)
    let upload = State(68.0)
    let query = State("")
    let tab = State(0)
    let toastText = State("")
    let toastVisible = State(false)

    let rows = [
        PhotoRow("IMG_0032.HEIC", "Today - 2.8 MB", Color.orange),
        PhotoRow("mountain_vlog.mov", "Yesterday - 48.2 MB", Color.green),
        PhotoRow("portrait_light.jpg", "Yesterday - 4.1 MB", Color.accent),
    ]
}

let library = LibraryModel()

// ---------------------------------------------------------------------------
// Small helpers
// ---------------------------------------------------------------------------
func segmentTitle(_ index: Int) -> String {
    if index == 0 {
        return "All photos"
    }
    if index == 1 {
        return "Favourites"
    }
    return "Recent"
}

func heroName(_ index: Int) -> String {
    if index == 0 {
        return "sunset_beach.heic"
    }
    if index == 1 {
        return "mountain_vlog.mov"
    }
    return "portrait_light.jpg"
}

func heroMeta(_ index: Int) -> String {
    if index == 0 {
        return "4032 x 3024 - 12.4 MB"
    }
    if index == 1 {
        return "1920 x 1080 - 48.2 MB"
    }
    return "3024 x 4032 - 4.1 MB"
}

func heroUpload(_ index: Int) -> Double {
    if index == 0 {
        return 68.0
    }
    if index == 1 {
        return 92.0
    }
    return 34.0
}

func selectedPhotos(_ model: LibraryModel) -> Int {
    var count = 0
    for row in model.rows {
        if row.selected.value {
            count += 1
        }
    }
    return count
}

/// A toast at the bottom of the screen, hidden after a moment.
func showToast(_ model: LibraryModel, _ message: String) {
    model.toastText.value = message
    model.toastVisible.value = true
    after(1600) {
        model.toastVisible.value = false
    }
}

// ---------------------------------------------------------------------------
// The views
// ---------------------------------------------------------------------------
func StatusBar() -> View {
    HStack(spacing: 0) {
        Text("9:41").font(.caption).bold()
        Spacer()
        Text("5G   100%").font(.caption).foregroundColor(Color.secondary)
    }
    .expand()
}

func Header(_ model: LibraryModel) -> View {
    HStack(alignment: .center, spacing: 12) {
        VStack(alignment: .leading, spacing: 4) {
            Text("Library").font(.largeTitle)
            Text("\(model.photos.value) photos - \(model.albums.value) albums")
                .font(.caption)
                .foregroundColor(Color.secondary)
        }
        Spacer()
        var plus = Text("+")
            .font(.title2)
            .foregroundColor(Color.accent)
            .background(Color.surface2)
            .padding(12, 8)
            .cornerRadius(22)
            .frame(width: 44, height: 44)
        plus = plus.onTapGesture {
            model.albums.value = model.albums.value + 1
            showToast(model, "Album \(model.albums.value) created")
        }
    }
    .expand()
}

func SearchField(_ model: LibraryModel) -> View {
    TextField("Search photos, people, places", text: model.query)
        .font(.footnote)
        .padding(12, 10)
        .background(Color.surface)
        .cornerRadius(12)
        .expand()
}

func Chip(_ title: String, _ active: Bool, _ action: () -> Void) -> View {
    var node = Text(title).font(.footnote)
    if active {
        node = node.foregroundColor(Color.background).background(Color.accent)
    } else {
        node = node.foregroundColor(Color.secondary).background(Color.clear)
    }
    node = node.padding(12, 9).cornerRadius(18)
    return node.onTapGesture(action)
}

func SegmentRow(_ model: LibraryModel) -> View {
    HStack(spacing: 0) {
        Chip("All", model.segment.value == 0) {
            model.segment.value = 0
            model.upload.value = heroUpload(0)
            showToast(model, "Segment: All photos")
        }
        .frame(width: 104)
        Chip("Favourites", model.segment.value == 1) {
            model.segment.value = 1
            model.upload.value = heroUpload(1)
            showToast(model, "Segment: Favourites")
        }
        .frame(width: 104)
        Chip("Recent", model.segment.value == 2) {
            model.segment.value = 2
            model.upload.value = heroUpload(2)
            showToast(model, "Segment: Recent")
        }
        .layoutGrow(1.0)
    }
    .padding(4)
    .background(Color.surface)
    .cornerRadius(20)
    .expand()
}

func HeroCard(_ model: LibraryModel) -> View {
    let percent = Int(model.upload.value)
    return VStack(alignment: .leading, spacing: 12) {
        HStack(alignment: .center, spacing: 12) {
            RoundedRectangle(cornerRadius: 16)
                .fill(Color.orange)
                .frame(width: 64, height: 64)
            VStack(alignment: .leading, spacing: 3) {
                Text(heroName(model.segment.value)).font(.headline)
                Text(heroMeta(model.segment.value))
                    .font(.caption)
                    .foregroundColor(Color.secondary)
            }
            Spacer()
            Text("PHOTO")
                .font(.caption2)
                .foregroundColor(Color.secondary)
                .padding(9, 4)
                .background(Color.surface2)
                .cornerRadius(11)
        }
        .expand()
        HStack(spacing: 8) {
            Text("Uploading to iCloud")
                .font(.caption)
                .foregroundColor(Color.secondary)
            Spacer()
            Text("\(percent)%")
                .font(.caption)
                .bold()
                .foregroundColor(Color.accent)
        }
        .expand()
        ProgressView(value: model.upload.value).frame(height: 6).expand()
        HStack(alignment: .center, spacing: 12) {
            Slider(value: model.upload, minimum: 0.0, maximum: 100.0)
                .frame(height: 24)
                .layoutGrow(1.0)
            Toggle("Auto-backup", isOn: model.autoBackup).font(.caption)
        }
        .expand()
    }
    .padding(16)
    .background(Color.surface)
    .cornerRadius(20)
    .expand()
}

func RecentHeader(_ model: LibraryModel) -> View {
    let selected = selectedPhotos(model)
    var summary = "\(model.photos.value) photos"
    if selected > 0 {
        summary = "\(selected) selected"
    }
    return HStack(spacing: 0) {
        Text("RECENT").font(.caption2).foregroundColor(Color.secondary)
        Spacer()
        Text(summary).font(.caption2).foregroundColor(Color.secondary)
    }
    .expand()
}

func PhotoRowView(_ model: LibraryModel, _ row: PhotoRow) -> View {
    HStack(alignment: .center, spacing: 12) {
        RoundedRectangle(cornerRadius: 12)
            .fill(row.color)
            .frame(width: 40, height: 40)
        VStack(alignment: .leading, spacing: 2) {
            Text(row.title).font(.subheadline)
            Text(row.details).font(.caption).foregroundColor(Color.secondary)
        }
        Spacer()
        if row.selected.value {
            Circle().fill(Color.accent).frame(width: 26, height: 26)
        } else {
            Circle().fill(Color.surface2).frame(width: 26, height: 26)
        }
    }
    .padding(12)
    .background(Color.surface)
    .cornerRadius(16)
    .expand()
    .onTapGesture {
        row.selected.value = !row.selected.value
        if row.selected.value {
            showToast(model, "Selected \(row.title)")
        } else {
            showToast(model, "Deselected \(row.title)")
        }
    }
}

func TabButton(_ model: LibraryModel, _ index: Int, _ title: String) -> View {
    let active = model.tab.value == index
    var node = Text(title).font(.footnote)
    if active {
        node = node.foregroundColor(Color.accent).background(Color.surface2)
    } else {
        node = node.foregroundColor(Color.secondary).background(Color.clear)
    }
    node = node.padding(16, 12).cornerRadius(18).frame(width: 108)
    return node.onTapGesture {
        model.tab.value = index
        showToast(model, "Tab: \(title)")
    }
}

func TabBar(_ model: LibraryModel) -> View {
    return HStack(spacing: 4) {
        TabButton(model, 0, "Home")
        TabButton(model, 1, "Search")
        TabButton(model, 2, "Profile")
    }
    .padding(6)
    .background(Color.surface)
    .cornerRadius(24)
    .expand()
}

func ToastView(_ model: LibraryModel) -> View {
    var node = Text(model.toastText.value)
        .font(.footnote)
        .foregroundColor(Color.primary)
    node = node.padding(18, 10).background(Color.surface2).cornerRadius(20)
    if !model.toastVisible.value {
        node = node.hidden()
    }
    return node
}

func LibraryView(_ model: LibraryModel) -> View {
    return ZStack(alignment: .bottom) {
        VStack(spacing: 0) {
            ScrollView {
                VStack(alignment: .leading, spacing: 14) {
                    StatusBar()
                    Header(model)
                    SearchField(model)
                    SegmentRow(model)
                    HeroCard(model)
                    RecentHeader(model)
                    ForEach(model.rows) { row in
                        PhotoRowView(model, row)
                    }
                    Spacer(minLength: 16)
                }
                .padding(22, 12)
                .expand()
            }
            .layoutGrow(1.0)
            .expand()
            TabBar(model)
        }
        .expand()
        .background(Color.background)
        ToastView(model)
            .padding(.bottom, 96)
    }
    .expand()
    .background(Color.background)
}

// ---------------------------------------------------------------------------
// The application
// ---------------------------------------------------------------------------
@main
struct LibraryApp {
    var body: Scene {
        WindowGroup("SwimUI - Library", width: 390, height: 844,
                    background: Color.background) {
            LibraryView(library)
        }
    }

    static func main() {
        setThemeVariant("dark")
        launch(LibraryApp().body)
    }
}
