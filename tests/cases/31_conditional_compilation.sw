// Conditional compilation: #if / #elseif / #else / #endif with built-in
// flags, version checks and #available.

#if true
print("true branch")
#else
print("wrong branch")
#endif

#if false
print("wrong branch")
#elseif true
print("elseif branch")
#else
print("wrong branch")
#endif

#if SWIM
print("SWIM defined")
#endif

#if DEBUG
print("wrong: DEBUG is not defined by default")
#else
print("DEBUG not defined")
#endif

#if swift(>=5.0)
print("swift >= 5.0")
#endif

#if swift(<4.0)
print("wrong: swift < 4.0")
#endif

#if canImport(Foundation)
print("can import Foundation")
#endif

#if !false && (true || false)
print("boolean expressions")
#endif

#if false
#if true
print("wrong nested branch")
#endif
#else
print("nested else branch")
#endif

#if false
#error "inactive #error does not fire"
#endif

let supportsModernAPI = #available(iOS 13, macOS 10.15, *)
print(supportsModernAPI)

if #available(iOS 13, *) {
    print("available branch")
} else {
    print("unavailable branch")
}
