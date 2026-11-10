// Compiler literals: #file, #line, #column and #function.
func report() -> String {
    return "\(#file):\(#line):\(#column):\(#function)"
}
let reportText = report()
print(reportText.hasPrefix("26_magic_literals.sw:"))
print(reportText.hasSuffix(":report()"))

func currentLine() -> Int {
    return #line
}
print(currentLine() > 0)

print(#function)
print(#file == "26_magic_literals.sw")

struct Reporter {
    func name() -> String {
        return #function
    }
    static func make() -> Reporter {
        return Reporter()
    }
}
print(Reporter().name())
