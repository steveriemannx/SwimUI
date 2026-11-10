## swimrt -- the runtime library for the Swim language.
##
## Swim programs are compiled from Swift-style syntax to Nim.  This module
## provides the Swift-like standard library surface (printing, collection
## helpers, optionals, protocols-as-concepts, ...) that generated code uses.
##
## It is imported by every generated program, and it re-exports the Nim
## standard library modules that Swim depends on.

import std/[options, tables, sequtils, strutils, math, algorithm, sets,
            hashes, os, random]

export options, tables, sequtils, strutils, math, algorithm, sets, os,
       hashes


# ---------------------------------------------------------------------------
# Protocols as Nim concepts (so they can be used as generic constraints)
# ---------------------------------------------------------------------------
type
  Equatable* = concept x, y
    x == y is bool
  Comparable* = concept x, y
    (x < y) is bool
  Hashable* = concept x
    hash(x) is Hash
  CustomStringConvertible* = concept x
    $x is string
  CaseIterable* = concept x
    $x is string
  AdditiveArithmetic* = concept x, y
    x + y is typeof(x)
  Numeric* = concept x, y
    x + y is typeof(x)
  SomeNumber* = concept x
    x + x is typeof(x)
    x - x is typeof(x)
  SignedNumeric* = concept x
    x + x is typeof(x)


# ---------------------------------------------------------------------------
# Printing (Swift style ``description`` conversion)
# ---------------------------------------------------------------------------
proc swimStr*(x: string): string = x
proc swimStr*(x: cstring): string = $x
proc swimStr*(x: char): string = $x
proc swimStr*(x: bool): string = (if x: "true" else: "false")
proc swimStr*(x: int): string = $x
proc swimStr*(x: int8): string = $x
proc swimStr*(x: int16): string = $x
proc swimStr*(x: int32): string = $x
proc swimStr*(x: int64): string = $x
proc swimStr*(x: uint): string = $x
proc swimStr*(x: uint8): string = $x
proc swimStr*(x: uint16): string = $x
proc swimStr*(x: uint32): string = $x
proc swimStr*(x: uint64): string = $x
proc swimStr*(x: float): string = $x
proc swimStr*(x: float32): string = $x

proc swimStr*[T](x: seq[T]): string =
  var parts: seq[string]
  for item in x:
    parts.add(swimStr(item))
  "[" & parts.join(", ") & "]"

proc swimStr*[T](x: HashSet[T]): string =
  var parts: seq[string]
  for item in x:
    parts.add(swimStr(item))
  "Set([" & parts.join(", ") & "])"

proc swimStr*[K, V](x: Table[K, V]): string =
  var parts: seq[string]
  for k, v in x.pairs:
    parts.add(swimStr(k) & ": " & swimStr(v))
  "[" & parts.join(", ") & "]"

proc swimStr*[T](x: Option[T]): string =
  if x.isSome:
    "Optional(" & swimStr(x.get) & ")"
  else:
    "nil"

proc swimStr*[T](x: T): string = $x

proc swimPrintSepTo*(args: varargs[string], sep: string,
                     terminator: string) =
  for i in 0 ..< args.len:
    if i > 0:
      stdout.write(sep)
    stdout.write(args[i])
  stdout.write(terminator)

proc swimPrint*(args: varargs[string]) =
  swimPrintSepTo(args, " ", "\n")

proc swimPrintNoNewline*(args: varargs[string]) =
  swimPrintSepTo(args, " ", "")

proc swimPrintTo*(args: varargs[string], terminator: string) =
  swimPrintSepTo(args, " ", terminator)

proc swimPrintSep*(args: varargs[string], sep: string) =
  swimPrintSepTo(args, sep, "\n")

proc swimFatal*(msg: string) {.noreturn.} =
  raise newException(Defect, msg)

proc swimFatal*(msg: string, file: string, line: int) {.noreturn.} =
  raise newException(Defect, msg)

template swimAssert*(cond: bool, msg: string = "") =
  if not cond:
    swimFatal(if msg.len > 0: msg else: "Assertion failed")

proc swimPreconditionFailure*(msg: string) {.noreturn.} =
  raise newException(Defect, msg)

proc swimReadLine*(): Option[string] =
  var line: string
  if readLine(stdin, line):
    some(line)
  else:
    none(string)

proc swimExit*(code: int) {.noreturn.} =
  quit(code)

proc swimRandomInt*(low, high: int): int =
  rand(low .. high)

proc swimRandomDouble*(): float =
  rand(1.0)


# ---------------------------------------------------------------------------
# Optionals
# ---------------------------------------------------------------------------
template swimOptFlatMap*(o: Option, body: untyped): untyped =
  block:
    var swO = o
    var it {.inject.}: typeof(swO.get)
    if swO.isSome:
      it = swO.get
      when typeof(body) is Option:
        body
      else:
        some(body)
    else:
      when typeof(body) is Option:
        none(typeof(body.get))
      else:
        none(typeof(body))

template swimOptMap*(o: Option, body: untyped): untyped =
  block:
    var swO = o
    var it {.inject.}: typeof(swO.get)
    if swO.isSome:
      it = swO.get
      some(body)
    else:
      none(typeof(body))

proc swimUnwrap*[T](o: Option[T]): T = o.get

proc swimToInt*(s: string): Option[int] =
  try:
    some(parseInt(s))
  except ValueError:
    none(int)

proc swimToInt64*(s: string): Option[int64] =
  try:
    some(parseInt(s).int64)
  except ValueError:
    none(int64)

proc swimToDouble*(s: string): Option[float] =
  try:
    some(parseFloat(s))
  except ValueError:
    none(float)


# ---------------------------------------------------------------------------
# Strings
# ---------------------------------------------------------------------------
proc count*(s: string): int = s.len
proc count*[T](s: seq[T]): int = s.len
proc count*[K, V](t: Table[K, V]): int = t.len
proc count*[T](s: HashSet[T]): int = s.len

proc isEmpty*(s: string): bool = s.len == 0
proc isEmpty*[T](s: seq[T]): bool = s.len == 0
proc isEmpty*[K, V](t: Table[K, V]): bool = t.len == 0
proc isEmpty*[T](s: HashSet[T]): bool = s.len == 0

proc firstOpt*[T](s: seq[T]): Option[T] =
  if s.len > 0: some(s[0]) else: none(T)
proc firstOpt*(s: string): Option[char] =
  if s.len > 0: some(s[0]) else: none(char)
proc lastOpt*[T](s: seq[T]): Option[T] =
  if s.len > 0: some(s[^1]) else: none(T)
proc lastOpt*(s: string): Option[char] =
  if s.len > 0: some(s[^1]) else: none(char)

proc append*[T](s: var seq[T], x: T) = s.add(x)
proc append*[T](s: var seq[T], contentsOf: openArray[T]) = s.add(contentsOf)
proc append*(s: var string, x: string) = s.add(x)
proc append*(s: var string, x: char) = s.add(x)

proc removeAt*[T](s: var seq[T], i: int): T =
  result = s[i]
  s.delete(i)
proc removeAt*(s: var string, i: int): char =
  result = s[i]
  s.delete(i, i)
proc popLastOpt*[T](s: var seq[T]): Option[T] =
  if s.len == 0: return none(T)
  else:
    result = some(s[^1])
    s.setLen(s.len - 1)

proc removeFirst*[T](s: var seq[T]): T = s.removeAt(0)
proc removeLast*[T](s: var seq[T]): T = s.removeAt(s.len - 1)
proc removeFirst*(s: var string): char = s.removeAt(0)
proc removeLast*(s: var string): char = s.removeAt(s.len - 1)

template swimRemoveAllIt*(s: var seq, body: untyped) =
  var swNew = newSeq[typeof(s[0])]()
  for it {.inject.} in s:
    if not body:
      swNew.add(it)
  s = swNew

proc removeValue*[K, V](t: var Table[K, V], key: K): Option[V] =
  if t.hasKey(key):
    result = some(t[key])
    t.del(key)
  else:
    result = none(V)

proc updateValue*[K, V](t: var Table[K, V], value: V, key: K): Option[V] =
  if t.hasKey(key):
    result = some(t[key])
  else:
    result = none(V)
  t[key] = value

proc indexOf*(s: string, sub: string): Option[int] =
  let i = s.find(sub)
  if i >= 0: some(i) else: none(int)

proc indexOf*[T](s: seq[T], x: T): Option[int] =
  let i = s.find(x)
  if i >= 0: some(i) else: none(int)

proc firstIndex*[T](s: seq[T], x: T): Option[int] = indexOf(s, x)
proc firstIndex*(s: string, sub: string): Option[int] = indexOf(s, sub)

proc replacedOccurrences*(s: string, target: string, with: string): string =
  s.replace(target, with)

proc trimmingWhitespace*(s: string): string = s.strip

proc prefixLen*(s: string, n: int): string =
  s[0 ..< min(n, s.len)]
proc prefixLen*[T](s: seq[T], n: int): seq[T] =
  s[0 ..< min(n, s.len)]
proc suffixLen*(s: string, n: int): string =
  let start = max(0, s.len - n)
  s[start .. ^1]
proc suffixLen*[T](s: seq[T], n: int): seq[T] =
  let start = max(0, s.len - n)
  s[start .. ^1]

proc dropFirst*(s: string): string = s[1 .. ^1]
proc dropFirst*(s: string, n: int): string = s[min(n, s.len) .. ^1]
proc dropFirst*[T](s: seq[T]): seq[T] = s[1 .. ^1]
proc dropFirst*[T](s: seq[T], n: int): seq[T] = s[min(n, s.len) .. ^1]
proc dropLast*(s: string): string = s[0 ..< max(0, s.len - 1)]
proc dropLast*(s: string, n: int): string = s[0 ..< max(0, s.len - n)]
proc dropLast*[T](s: seq[T]): seq[T] = s[0 ..< max(0, s.len - 1)]
proc dropLast*[T](s: seq[T], n: int): seq[T] = s[0 ..< max(0, s.len - n)]

proc reversedStr*(s: string): string =
  for i in countdown(s.len - 1, 0):
    result.add(s[i])
proc reversedSeq*[T](s: seq[T]): seq[T] = s.reversed

proc joinedSep*(s: seq[string], sep: string): string = s.join(sep)

proc splitSep*(s: string, sep: string): seq[string] =
  if sep.len == 0:
    result = @[]
    for c in s: result.add($c)
  else:
    result = s.split(sep)
proc splitSep*(s: string, sep: char): seq[string] = s.split(sep)
proc splitSep*(s: string): seq[string] =
  var parts: seq[string]
  for part in s.splitWhitespace():
    parts.add(part)
  parts

proc components*(s: string, sep: string): seq[string] = s.split(sep)
proc components*(s: string, sep: char): seq[string] = s.split(sep)

proc capitalized*(s: string): string =
  if s.len == 0: return s
  result = $s[0].toUpperAscii
  if s.len > 1: result.add(s[1 .. ^1])

proc isNumber*(c: char): bool = c in {'0' .. '9'}
proc isLetter*(c: char): bool = c.isAlphaAscii
proc isWhitespace*(c: char): bool = c in {' ', '\t', '\n', '\r', '\v', '\f'}
proc isUppercase*(c: char): bool = c.isUpperAscii
proc isLowercase*(c: char): bool = c.isLowerAscii
proc uppercased*(c: char): string = $c.toUpperAscii
proc lowercased*(c: char): string = $c.toLowerAscii
proc wholeNumberValue*(c: char): Option[int] =
  if c in {'0' .. '9'}: some(ord(c) - ord('0')) else: none(int)

proc stringRepeating*(s: string, n: int): string = s.repeat(n)

proc enumerated*[T](s: seq[T]): seq[(int, T)] =
  result = newSeq[(int, T)](s.len)
  for i, item in s:
    result[i] = (i, item)
proc enumerated*(s: string): seq[(int, char)] =
  result = newSeq[(int, char)](s.len)
  for i, item in s:
    result[i] = (i, item)

proc swapAt*[T](s: var seq[T], i, j: int) =
  let tmp = s[i]
  s[i] = s[j]
  s[j] = tmp
proc swapAt*(s: var string, i, j: int) =
  let tmp = s[i]
  s[i] = s[j]
  s[j] = tmp

proc minOpt*[T](s: seq[T]): Option[T] =
  if s.len == 0: return none(T)
  var best = s[0]
  for i in 1 ..< s.len:
    if s[i] < best: best = s[i]
  some(best)
proc maxOpt*[T](s: seq[T]): Option[T] =
  if s.len == 0: return none(T)
  var best = s[0]
  for i in 1 ..< s.len:
    if s[i] > best: best = s[i]
  some(best)

proc dictPairs*[K, V](t: Table[K, V]):
    seq[tuple[key: K, value: V]] =
  result = newSeq[tuple[key: K, value: V]](t.len)
  var i = 0
  for k, v in t.pairs:
    result[i] = (key: k, value: v)
    inc i

proc tableOpt*[K, V](t: Table[K, V], key: K): Option[V] =
  if t.hasKey(key): some(t[key]) else: none(V)

proc keysSeq*[K, V](t: Table[K, V]): seq[K] =
  result = newSeq[K](t.len)
  var i = 0
  for k in t.keys:
    result[i] = k
    inc i

proc valuesSeq*[K, V](t: Table[K, V]): seq[V] =
  result = newSeq[V](t.len)
  var i = 0
  for v in t.values:
    result[i] = v
    inc i

proc removeAllItems*[T](s: var seq[T]) =
  s.setLen(0)

proc swimAsOpt*[T: ref object](T2: typedesc[T], x: RootRef): Option[T] =
  if x of T: some(T(x)) else: none(T)

template swimTryOpt*(T: typedesc, body: untyped): untyped =
  (try: some(body) except CatchableError: none(T))

proc arrayRepeating*[T](value: T, count: int): seq[T] =
  result = newSeq[T](count)
  for i in 0 ..< count:
    result[i] = value

proc intIsMultiple*(x: int, divisor: int): bool = x mod divisor == 0

proc sortedDesc*[T](s: seq[T]): seq[T] =
  result = s.sorted(SortOrder.Descending)

proc sortedAsc*[T](s: seq[T]): seq[T] =
  result = s.sorted(SortOrder.Ascending)


# ---------------------------------------------------------------------------
# Higher order helpers (used for trailing closure syntax)
# ---------------------------------------------------------------------------
template forEachIt*(s: untyped, body: untyped) =
  for it {.inject.} in s:
    body

template firstWhereIt*(s: untyped, body: untyped): untyped =
  block:
    var swFound: Option[typeof(s[0])] = none(typeof(s[0]))
    for it {.inject.} in s:
      if body:
        swFound = some(it)
        break
    swFound

template firstIndexWhereIt*(s: untyped, body: untyped): untyped =
  block:
    var swIdx = 0
    var swFound: Option[int] = none(int)
    for it {.inject.} in s:
      if body:
        swFound = some(swIdx)
        break
      inc swIdx
    swFound

template lastWhereIt*(s: untyped, body: untyped): untyped =
  block:
    var swFound: Option[typeof(s[0])] = none(typeof(s[0]))
    for it {.inject.} in s:
      if body:
        swFound = some(it)
    swFound

proc swimSortedByImpl*[T](s: seq[T], less: proc(a, b: T): bool): seq[T] =
  if s.len < 2:
    return s
  let mid = s.len div 2
  let left = swimSortedByImpl(s[0 ..< mid], less)
  let right = swimSortedByImpl(s[mid .. ^1], less)
  result = newSeq[T](s.len)
  var i = 0
  var j = 0
  var k = 0
  while i < left.len and j < right.len:
    if less(right[j], left[i]):
      result[k] = right[j]
      inc j
    else:
      result[k] = left[i]
      inc i
    inc k
  while i < left.len:
    result[k] = left[i]
    inc i
    inc k
  while j < right.len:
    result[k] = right[j]
    inc j
    inc k

template swimSortedByIt*(s: untyped, body: untyped): untyped =
  block:
    var swS = s
    type SwSortT = typeof(swS[0])
    var a {.inject.}, b {.inject.}: SwSortT
    swimSortedByImpl(swS, proc(x, y: SwSortT): bool =
      block:
        a = x
        b = y
        body)

proc swimSortByImpl*[T](s: var seq[T], less: proc(a, b: T): bool) =
  s = swimSortedByImpl(s, less)

template swimSortByIt*(s: var seq, body: untyped) =
  block:
    var swTmp = s
    type SwSortT2 = typeof(swTmp[0])
    var a {.inject.}, b {.inject.}: SwSortT2
    s = swimSortedByImpl(swTmp, proc(x, y: SwSortT2): bool =
      block:
        a = x
        b = y
        body)

template swimMapIt*(s: untyped, body: untyped): untyped = mapIt(s, body)
template swimFilterIt*(s: untyped, body: untyped): untyped = filterIt(s, body)
template swimAllIt*(s: untyped, body: untyped): untyped = allIt(s, body)
template swimAnyIt*(s: untyped, body: untyped): untyped = anyIt(s, body)


# ---------------------------------------------------------------------------
# Ranges / strides
# ---------------------------------------------------------------------------
iterator swimStride*(start, stop, step: int): int =
  var i = start
  if step > 0:
    while i <= stop:
      yield i
      i += step
  elif step < 0:
    while i >= stop:
      yield i
      i += step

iterator swimStrideTo*(start, stop, step: int): int =
  var i = start
  if step > 0:
    while i < stop:
      yield i
      i += step
  elif step < 0:
    while i > stop:
      yield i
      i += step


# ---------------------------------------------------------------------------
# Misc helpers
# ---------------------------------------------------------------------------
proc swimInRange*(x, low, high: int): bool = x >= low and x <= high

template swimInSet*(x: untyped, s: untyped): bool = x in s


# ---------------------------------------------------------------------------
# Slicing, zip and additional Swift-style collection APIs
# ---------------------------------------------------------------------------
proc swimSlice*[T](s: seq[T], low, high: int): seq[T] =
  s[low ..< high]
proc swimSliceInclusive*[T](s: seq[T], low, high: int): seq[T] =
  s[low .. high]
proc swimSliceStr*(s: string, low, high: int): string =
  s[low ..< high]
proc swimSliceStrInclusive*(s: string, low, high: int): string =
  s[low .. high]

proc swimZip*[A, B](a: seq[A], b: seq[B]): seq[(A, B)] =
  let n = min(a.len, b.len)
  result = newSeq[(A, B)](n)
  for i in 0 ..< n:
    result[i] = (a[i], b[i])
proc swimZip*[A](a: seq[A], b: string): seq[(A, char)] =
  let n = min(a.len, b.len)
  result = newSeq[(A, char)](n)
  for i in 0 ..< n:
    result[i] = (a[i], b[i])
proc swimZip*(a: string, b: string): seq[(char, char)] =
  let n = min(a.len, b.len)
  result = newSeq[(char, char)](n)
  for i in 0 ..< n:
    result[i] = (a[i], b[i])

template swimCompactMapIt*(s: untyped, body: untyped): untyped =
  mapIt(s, body).filterIt(it.isSome).mapIt(it.get)

proc swimFlatMap*[A, T](s: seq[A], f: proc(x: A): seq[T]): seq[T] =
  result = @[]
  for item in s:
    result.add(f(item))
template swimFlatMapIt*(s: untyped, body: untyped): untyped =
  concat(mapIt(s, body))

proc swimCompactMap*[A, T](s: seq[A], f: proc(x: A): Option[T]): seq[T] =
  result = @[]
  for item in s:
    let mapped = f(item)
    if mapped.isSome:
      result.add(mapped.get)

proc lastIndex*[T](s: seq[T], x: T): Option[int] =
  var found = none(int)
  for i, item in s:
    if item == x:
      found = some(i)
  found
proc lastIndex*(s: string, sub: string): Option[int] =
  let i = s.rfind(sub)
  if i >= 0: some(i) else: none(int)

proc elementsEqual*[T](a, b: seq[T]): bool =
  if a.len != b.len: return false
  for i in 0 ..< a.len:
    if a[i] != b[i]: return false
  true
proc elementsEqual*(a, b: string): bool = a == b

proc startsWith*[T](s: seq[T], prefix: seq[T]): bool =
  if prefix.len > s.len: return false
  for i in 0 ..< prefix.len:
    if s[i] != prefix[i]: return false
  true

proc randomElement*[T](s: seq[T]): Option[T] =
  if s.len == 0: return none(T)
  some(s[rand(s.len - 1)])
proc randomElement*(s: string): Option[char] =
  if s.len == 0: return none(char)
  some(s[rand(s.len - 1)])
proc shuffled*[T](s: seq[T]): seq[T] =
  result = s
  for i in countdown(result.len - 1, 1):
    let j = rand(i)
    swap(result[i], result[j])
proc shuffle*[T](s: var seq[T]) =
  for i in countdown(s.len - 1, 1):
    let j = rand(i)
    swap(s[i], s[j])

template swimMinByIt*(s: untyped, body: untyped): untyped =
  block:
    var swMinSrc = s
    if swMinSrc.len == 0:
      none(typeof(swMinSrc[0]))
    else:
      some(swimSortedByIt(swMinSrc, body)[0])
template swimMaxByIt*(s: untyped, body: untyped): untyped =
  block:
    var swMaxSrc = s
    if swMaxSrc.len == 0:
      none(typeof(swMaxSrc[0]))
    else:
      some(swimSortedByIt(swMaxSrc, body)[^1])
proc swimMinBy*[T](s: seq[T], less: proc(a, b: T): bool): Option[T] =
  if s.len == 0: none(T) else: some(swimSortedByImpl(s, less)[0])
proc swimMaxBy*[T](s: seq[T], less: proc(a, b: T): bool): Option[T] =
  if s.len == 0: none(T) else: some(swimSortedByImpl(s, less)[^1])

proc swimDictMapValues*[K, V, T](t: Table[K, V],
                                 f: proc(v: V): T): Table[K, T] =
  result = initTable[K, T]()
  for k, v in t.pairs:
    result[k] = f(v)

proc swimDictFilter*[K, V](t: Table[K, V],
                           f: proc(pair: tuple[key: K, value: V]): bool):
    Table[K, V] =
  result = initTable[K, V]()
  for k, v in t.pairs:
    if f((key: k, value: v)):
      result[k] = v
# ---------------------------------------------------------------------------
# Set algebra
# ---------------------------------------------------------------------------
proc swimUnion*[T](a, b: HashSet[T]): HashSet[T] = a + b
proc swimIntersection*[T](a, b: HashSet[T]): HashSet[T] = a * b
proc swimSubtracting*[T](a, b: HashSet[T]): HashSet[T] = a - b
proc swimIsSubset*[T](a, b: HashSet[T]): bool = a <= b
proc swimIsSuperset*[T](a, b: HashSet[T]): bool = a >= b
template swimSetFilterIt*(s: untyped, body: untyped): untyped =
  toHashSet(filterIt(toSeq(s), body))
proc swimSetFilter*[T](s: HashSet[T], f: proc(x: T): bool): HashSet[T] =
  result = initHashSet[T]()
  for item in s:
    if f(item):
      result.incl(item)
proc swimRandomDoubleRange*(low, high: float): float =
  low + rand(1.0) * (high - low)
proc swimIsDisjoint*[T](a, b: HashSet[T]): bool =
  for item in a:
    if item in b: return false
  true
proc swimFormUnion*[T](a: var HashSet[T], b: HashSet[T]) = a = a + b
proc swimFormIntersection*[T](a: var HashSet[T], b: HashSet[T]) = a = a * b
proc swimFormSymmetricDifference*[T](a: var HashSet[T], b: HashSet[T]) =
  a = a - b + (b - a)

# ---------------------------------------------------------------------------
# Numeric helpers
# ---------------------------------------------------------------------------
proc isNaN*(x: float): bool = x != x
proc isNaN*(x: float32): bool = x != x
proc isInfinite*(x: float): bool = x == Inf or x == -Inf
proc isInfinite*(x: float32): bool = isInfinite(float64(x))
proc isFinite*(x: float): bool = not (isNaN(x) or isInfinite(x))
proc isFinite*(x: float32): bool = isFinite(float64(x))
proc truncatingRemainder*[T](x, divisor: T): T = x - trunc(x / divisor) * divisor
proc advanced*[T](x: T, by: T): T = x + by
proc asciiValue*(c: char): Option[int] =
  if ord(c) < 128: some(ord(c)) else: none(int)
proc signum*[T](x: T): T =
  if x > T(0): T(1)
  elif x < T(0): T(-1)
  else: T(0)
