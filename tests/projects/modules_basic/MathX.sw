// A reusable math module.
func triple(_ value: Int) -> Int {
    return value * 3
}

func clamp(_ value: Int, low: Int, high: Int) -> Int {
    if value < low { return low }
    if value > high { return high }
    return value
}

print("MathX loaded")
