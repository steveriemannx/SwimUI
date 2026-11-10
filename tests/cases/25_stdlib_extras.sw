// Swift standard-library gaps: slicing, zip, compactMap/flatMap, Set
// algebra, Dictionary helpers, min/max(by:), random/shuffle, numeric helpers.
let numbers = [1, 2, 3, 4, 5]
print(numbers[1..<3])
print(numbers[1...3])
print("swimming"[0..<3])
print(numbers[0..<numbers.count])

print(zip([1, 2, 3], ["a", "b"]))
var pairs = ""
for (number, letter) in zip([1, 2], ["x", "y"]) {
    pairs += "\(number)\(letter)"
}
print(pairs)

print(numbers.compactMap { $0 % 2 == 0 ? Optional($0) : nil })
print([[1, 2], [3], []].flatMap { $0 })
print(["1", "x", "3"].compactMap { Int($0) })

let set: Set<Int> = [1, 2, 3]
print(set.union([3, 4]).sorted())
print(set.intersection([2, 3, 9]).sorted())
print(set.subtracting([1]).sorted())
print(set.isSubset(of: [1, 2, 3, 4]), set.isSuperset(of: [1, 2]))
print(set.isDisjoint(with: [7, 8]))
var mutableSet: Set<Int> = [1, 2]
mutableSet.formUnion([3])
mutableSet.formIntersection([2, 3, 4])
print(mutableSet.sorted())

let scores = ["alice": 3, "bob": 7]
let doubled = scores.mapValues { $0 * 2 }
print(doubled["alice"]!, doubled["bob"]!)
let highScores = scores.filter { $0.value > 5 }
print(highScores.count, highScores["bob"]!)

let sortedAscending = numbers.sorted { $0 < $1 }
print(numbers.min(by: { $0 < $1 })!, numbers.max(by: { $0 < $1 })!)
print(sortedAscending.first!, sortedAscending.last!)
print(numbers.lastIndex(of: 4)!, numbers.firstIndex(of: 2)!)
print(numbers.elementsEqual([1, 2, 3, 4, 5]), numbers.elementsEqual([1, 2]))
print(numbers.starts(with: [1, 2]))
print(numbers.randomElement() != nil, numbers.randomElement() != nil)
print(numbers.shuffled().sorted() == numbers)

print(0.0.isNaN, 1.0.isFinite, (1.0 / 0.0).isInfinite)
print(7.5.truncatingRemainder(dividingBy: 2.0))
print(3.0.advanced(by: 2.5), 5.advanced(by: -2))
print((-4).signum, 0.signum, 4.signum)
let letter: Character = "A"
print(letter.asciiValue!, letter.isLetter)

// generic initializer type inference
struct Box<T> {
    var value: T
}
let box = Box(value: 21)
print(box.value)
let nested = Box(value: ["a", "b"])
print(nested.value)

// Optional inference for ternaries with nil
let label = numbers.count > 0 ? "some" : nil
print(label ?? "none")

print(set.map { $0 + 10 }.sorted())
print(set.filter { $0 > 1 }.sorted())
let randomDouble = Double.random(in: 0.0...1.0)
print(randomDouble >= 0.0 && randomDouble <= 1.0)
