struct ReadOnly {
    var cells: [Int]
    subscript(index: Int) -> Int { get { cells[index] } }
}
var r = ReadOnly(cells: [1, 2])
r[0] = 5
