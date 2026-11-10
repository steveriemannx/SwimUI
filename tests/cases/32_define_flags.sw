// Custom compile-time flags from `swim run -D NAME` (see the .flags file).
#if FANCY
print("FANCY enabled")
#else
print("FANCY disabled")
#endif

#if OTHER
print("OTHER enabled")
#endif

#if FANCY && !DEBUG
print("fancy and not debug")
#endif

#if os(macOS) || os(Linux) || os(Windows)
print("known platform")
#endif
