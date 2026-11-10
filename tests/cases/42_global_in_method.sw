// A global read from a method and from a closure inside a method.
// Regression: an unqualified name inside a method used to resolve to a member
// of `self` (nil at run time) instead of the global with that name.

let greeting = "global"
let counter = 41

class Greeter {
    let prefix = "member"

    func describe() -> String {
        let say = {
            print("closure sees \(greeting)")
        }
        say()
        print("method sees \(greeting)")
        let value = counter
        print("member still wins: \(prefix)")
        return "\(prefix)/\(value)"
    }
}

struct Reporter {
    func report() -> String {
        let bump = {
            print("closure counter=\(counter)")
        }
        bump()
        return "counter=\(counter)"
    }
}

print(Greeter().describe())
print(Reporter().report())
