struct Wrapper {
    var value: Int
}
struct Holder {
    @Wrapper var number: Int = 0
}
print(Holder().number)
