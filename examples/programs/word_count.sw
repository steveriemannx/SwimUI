// Count word frequencies
let text = "the quick brown fox jumps over the lazy dog the fox"

var counts: [String: Int] = [:]
for word in text.split(separator: " ") {
    let key = word.lowercased()
    counts[key] = (counts[key] ?? 0) + 1
}

let sortedKeys = counts.keys.sorted(by: { left, right in
    let leftCount = counts[left]!
    let rightCount = counts[right]!
    if leftCount == rightCount {
        return left < right
    }
    return leftCount > rightCount
})

for key in sortedKeys {
    print("\(key): \(counts[key]!)")
}
