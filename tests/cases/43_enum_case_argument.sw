// Enum case shorthand passed to a free function: the argument must be typed
// with the parameter's enum, not guessed among the enums that share the case
// name.
//
// Regression: `.leading` and friends were emitted as an untyped enum case, and
// the dynamic dispatcher then could not bind the call (the value belonged to
// another enum) and reported "unknown function".

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

func describe(alignment: HorizontalAlignment, spacing: Int = 8) -> String {
    if alignment == .leading {
        return "leading spacing=\(spacing)"
    }
    if alignment == .trailing {
        return "trailing spacing=\(spacing)"
    }
    return "center spacing=\(spacing)"
}

func describe(vertical: VerticalAlignment) -> String {
    if vertical == .top {
        return "top"
    }
    if vertical == .bottom {
        return "bottom"
    }
    return "middle"
}

print(describe(alignment: .leading))
print(describe(alignment: .trailing, spacing: 4))
print(describe(vertical: .top))
print(describe(vertical: .bottom))
print(describe(alignment: .center))
