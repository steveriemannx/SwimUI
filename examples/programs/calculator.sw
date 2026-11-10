// A small expression calculator: tokenizer + recursive-descent parser + evaluator.
enum Token {
    case number(Double)
    case plus
    case minus
    case times
    case divide
    case leftParen
    case rightParen
}

enum CalcError: Error {
    case unexpectedCharacter(Character)
    case unexpectedEnd
    case syntaxError(String)
}

func tokenize(_ text: String) throws -> [Token] {
    var tokens: [Token] = []
    var index = 0
    let characters = Array(text)
    while index < characters.count {
        let ch = characters[index]
        if ch == " " {
            index += 1
            continue
        }
        if ch.isNumber || ch == "." {
            var numberText = ""
            while index < characters.count && (characters[index].isNumber || characters[index] == ".") {
                numberText.append(characters[index])
                index += 1
            }
            guard let value = Double(numberText) else {
                throw CalcError.syntaxError("bad number: \(numberText)")
            }
            tokens.append(.number(value))
            continue
        }
        switch ch {
        case "+": tokens.append(.plus)
        case "-": tokens.append(.minus)
        case "*": tokens.append(.times)
        case "/": tokens.append(.divide)
        case "(": tokens.append(.leftParen)
        case ")": tokens.append(.rightParen)
        default: throw CalcError.unexpectedCharacter(ch)
        }
        index += 1
    }
    return tokens
}

struct Parser {
    var tokens: [Token]
    var position: Int = 0

    func peek() -> Token? {
        return position < tokens.count ? tokens[position] : nil
    }

    mutating func advance() -> Token? {
        let token = peek()
        position += 1
        return token
    }

    mutating func parseExpression() throws -> Double {
        var value = try parseTerm()
        while let token = peek() {
            switch token {
            case .plus:
                _ = advance()
                value += try parseTerm()
            case .minus:
                _ = advance()
                value -= try parseTerm()
            default:
                return value
            }
        }
        return value
    }

    mutating func parseTerm() throws -> Double {
        var value = try parseFactor()
        while let token = peek() {
            switch token {
            case .times:
                _ = advance()
                value *= try parseFactor()
            case .divide:
                _ = advance()
                let divisor = try parseFactor()
                if divisor == 0 {
                    throw CalcError.syntaxError("division by zero")
                }
                value /= divisor
            default:
                return value
            }
        }
        return value
    }

    mutating func parseFactor() throws -> Double {
        guard let token = advance() else {
            throw CalcError.unexpectedEnd
        }
        switch token {
        case .number(let value):
            return value
        case .minus:
            return -(try parseFactor())
        case .leftParen:
            let value = try parseExpression()
            guard let closing = advance(), case .rightParen = closing else {
                throw CalcError.syntaxError("expected )")
            }
            return value
        default:
            throw CalcError.syntaxError("unexpected token")
        }
    }
}

func evaluate(_ text: String) throws -> Double {
    var parser = Parser(tokens: try tokenize(text))
    let value = try parser.parseExpression()
    guard parser.position == parser.tokens.count else {
        throw CalcError.syntaxError("trailing tokens")
    }
    return value
}

let cases = [
    "1 + 2",
    "2 * (3 + 4)",
    "10 / 4",
    "-(2 + 3) * 4",
    "1 + 2 * (3 - 4) / 2"
]
for expression in cases {
    do {
        let result = try evaluate(expression)
        print("\(expression) = \(result)")
    } catch CalcError.unexpectedCharacter(let ch) {
        print("bad character: \(ch)")
    } catch CalcError.syntaxError(let message) {
        print("syntax error: \(message)")
    } catch {
        print("unexpected end")
    }
}
