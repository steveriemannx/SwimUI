infix operator +=: AssignmentPrecedence
func += (lhs: inout Int, rhs: Int) {
    lhs = lhs + rhs
}
var value = 1
value += 2
