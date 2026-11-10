// CounterApp.sw -- the smallest SwiftUI-shaped SwimUI program.

import SwimUI

final class CounterModel {
    let count = State(0)
}

let counterModel = CounterModel()

func CounterView(_ model: CounterModel) -> View {
    VStack(spacing: 12) {
        Text("Count: \(model.count.value)")
            .font(.title)
        HStack(spacing: 8) {
            Button("Add") {
                model.count.value = model.count.value + 1
            }
            .buttonStyle(.borderedProminent)
            Button("Reset") {
                model.count.value = 0
            }
        }
    }
    .padding(20)
}

@main
struct CounterApp {
    var body: Scene {
        WindowGroup("Counter", width: 390, height: 500,
                    background: Color.surface) {
            CounterView(counterModel)
        }
    }

    static func main() {
        setThemeVariant("light")
        launch(CounterApp().body)
    }
}
