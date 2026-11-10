// SwimUITest.sw -- drives the SwimUI (SwiftUI-shaped) layer: state changes, the
// re-render/patch pass, a button click raised as a pointer would, the text of
// the mounted controls and two snapshots.  tests/binding_test.py runs it.
//
//   tests/binding_test.py
//   SWIMUI_IMAGE=build/test/swiftui.png SWIMUI_QUIT_MS=1300 \
//       ./build/test/SwimUITest
//
// Environment: SWIMUI_IMAGE is the base of `<path>.before.png` and
// `<path>.after.png`, SWIMUI_QUIT_MS when to close the window.

import SwimUI

final class TestRow {
    let title: String
    let selected = State(false)

    init(_ title: String) {
        self.title = title
    }
}

final class TestModel {
    let count = State(0)
    let toggle = State(false)
    let slider = State(25.0)
    let text = State("")
    let rows = [TestRow("row one"), TestRow("row two")]
}

let testModel = TestModel()
var testScheduled = false

func selectedRows() -> Int {
    var count = 0
    for row in testModel.rows {
        if row.selected.value {
            count += 1
        }
    }
    return count
}

func scheduleTests() {
    let image = imagePath()
    after(200) {
        if !image.isEmpty {
            snapshot(after: 0, path: image + ".before.png")
        }
    }
    after(320) {
        // The writes a program makes in its callbacks; one re-render pass.
        testModel.count.value = 5
        testModel.toggle.value = true
        testModel.slider.value = 80.0
        testModel.text.value = "typed"
        testModel.rows[0].selected.value = true
    }
    after(560) {
        let tapped = tapButton("Add")
        printLog("check: tapped=\(tapped)")
    }
    after(800) {
        let texts = renderedTexts()
        printLog("check: texts=\(texts)")
        printLog("check: slider=\(controlValue(5))")
        if !image.isEmpty {
            snapshot(after: 100, path: image + ".after.png")
        }
    }
    after(1100) {
        printLog("check: done=true")
    }
    let quit = autoQuitMs()
    if quit > 0 {
        after(quit) {
            quitApp()
        }
    }
}

func TestView() -> View {
    if !testScheduled {
        testScheduled = true
        scheduleTests()
    }
    let model = testModel
    return VStack(alignment: .leading, spacing: 10) {
        Text("count=\(model.count.value)").font(.headline)
        Text("toggle=\(model.toggle.value)").font(.caption)
        Text("slider=\(Int(model.slider.value))").font(.caption)
        Text("text=\(model.text.value)").font(.caption)
        HStack(spacing: 8) {
            Button("Add") {
                model.count.value = model.count.value + 1
            }
            .buttonStyle(.borderedProminent)
            Button("Flip") {
                model.toggle.value = !model.toggle.value
            }
            .buttonStyle(.bordered)
        }
        Slider(value: model.slider, minimum: 0.0, maximum: 100.0)
            .frame(height: 20)
        Toggle("Switch", isOn: model.toggle)
        TextField("Type here", text: model.text)
        ForEach(model.rows) { row in
            Button(row.title) {
                row.selected.value = !row.selected.value
            }
            .buttonStyle(.plain)
            .padding(8)
            .background(Color.surface)
            .cornerRadius(8)
        }
        Text("rows=\(selectedRows())").font(.caption)
        Spacer()
    }
    .padding(16)
    .expand()
    .background(Color.background)
}

@main
struct SwimUITestApp {
    var body: Scene {
        WindowGroup("SwimUI test", width: 320, height: 560,
                    background: Color.background) {
            TestView()
        }
    }

    static func main() {
        setThemeVariant("dark")
        launch(SwimUITestApp().body)
    }
}
