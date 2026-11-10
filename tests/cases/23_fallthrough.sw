// switch fallthrough: chains, fallthrough into default, inside loops and
// with enum payload cases.
func classify(_ value: Int) -> String {
    var result = ""
    switch value {
    case 0:
        result += "zero"
        fallthrough
    case 1:
        result += "-one"
        fallthrough
    case 2:
        result += "-two"
    default:
        result += "-many"
    }
    return result
}
for value in 0...4 {
    print(classify(value))
}

// fallthrough into default
func category(_ value: Int) -> String {
    switch value {
    case 1:
        return "one"
    case 2:
        fallthrough
    default:
        return "other"
    }
}
print(category(1), category(2), category(3))

// fallthrough is independent of the next case's where clause
func parity(_ value: Int) -> String {
    var label = ""
    switch value {
    case 0:
        label = "even"
        fallthrough
    case let other where other > 0:
        label += "+positive"
    default:
        label += "+other"
    }
    return label
}
print(parity(0), parity(1), parity(-1))

// break still exits the switch from a fallen-into case
func stop(_ value: Int) -> String {
    var trace = ""
    switch value {
    case 0:
        trace += "start"
        fallthrough
    case 1:
        trace += "-next"
        break
    default:
        trace += "-default"
    }
    trace += "!"
    return trace
}
print(stop(0), stop(1), stop(5))

// fallthrough inside a loop with nested switch
for value in 0..<3 {
    switch value {
    case 0:
        print("loop start")
        fallthrough
    case 1:
        print("loop middle")
    case 2:
        print("loop end")
    default:
        break
    }
}
