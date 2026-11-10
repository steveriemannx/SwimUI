struct User: Codable {
    var name: String
}
print(User(name: "x").name)
