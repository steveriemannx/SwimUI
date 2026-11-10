/* swimrt_builtin.c -- the Swift-style standard library implemented on the
 * dynamic Swim value representation. */
#include "swimrt_internal.h"

#include <stdlib.h>
#include <string.h>
#include <stdio.h>
#include <math.h>

/* ================================================================== */
/* helpers                                                             */
/* ================================================================== */
static int64_t swim_len(SwimValue v) {
    v = SwimDeref(v);
    return ((SwimStringObj*)v)->len;
}
static const char* swim_data(SwimValue v) {
    v = SwimDeref(v);
    return ((SwimStringObj*)v)->data;
}
static SwimValue swim_str_of(SwimValue v) { return SwimStr(v); }

static int swim_closure_arg(int argc, SwimValue* argv, SwimValue* out) {
    if (argc < 1) return 0;
    *out = SwimDeref(argv[argc - 1]);
    if (*out == NULL) return 0;
    return (*out)->type->kind == SWIM_KIND_CLOSURE;
}
static SwimValue swim_call1(SwimValue fn, SwimValue a) {
    SwimValue argv[1] = {a};
    return SwimCallValue(fn, 1, argv);
}
static SwimValue swim_call2(SwimValue fn, SwimValue a, SwimValue b) {
    SwimValue argv[2] = {a, b};
    return SwimCallValue(fn, 2, argv);
}
static int swim_less_with(SwimValue closure, SwimValue a, SwimValue b) {
    if (closure == NULL) return SwimCompare(a, b) < 0;
    SwimValue r = swim_call2(closure, a, b);
    int less = SwimUnboxBool(r);
    SwimRelease(r);
    return less;
}

/* labels parsing: find the position of a labelled argument */
static int swim_arg_index(const char* labels, const char* label, int argc) {
    if (!labels) return -1;
    char buf[512];
    strncpy(buf, labels, sizeof(buf) - 1);
    buf[sizeof(buf) - 1] = '\0';
    char* p = buf;
    int idx = 0;
    while (p && idx < argc) {
        char* comma = strchr(p, ',');
        if (comma) *comma = '\0';
        if (strcmp(p, label) == 0) return idx;
        if (!comma) break;
        p = comma + 1;
        idx++;
    }
    return -1;
}

/* ================================================================== */
/* Properties                                                          */
/* ================================================================== */
SwimValue SwimBuiltinProperty(SwimValue recv, const char* name) {
    recv = SwimDeref(recv);
    if (recv == NULL) return NULL;
    SwimKind k = recv->type->kind;
    if (strcmp(name, "description") == 0) return SwimStr(recv);
    if (strcmp(name, "hashValue") == 0) return SwimInt(SwimHash(recv));
    if (strcmp(name, "count") == 0) {
        if (k == SWIM_KIND_STRING) return SwimInt(((SwimStringObj*)recv)->len);
        if (k == SWIM_KIND_ARRAY) return SwimInt(((SwimArrayObj*)recv)->n);
        if (k == SWIM_KIND_SET) return SwimInt(((SwimSetObj*)recv)->n);
        if (k == SWIM_KIND_DICT) return SwimInt(((SwimDictObj*)recv)->n);
        if (k == SWIM_KIND_RANGE) {
            SwimRangeObj* r = (SwimRangeObj*)recv;
            int64_t lo = SwimToInt(r->lo), hi = SwimToInt(r->hi);
            int64_t n = hi - lo + (r->closed ? 1 : 0);
            return SwimInt(n < 0 ? 0 : n);
        }
    }
    if (strcmp(name, "isEmpty") == 0) {
        if (k == SWIM_KIND_STRING) return SwimBool(((SwimStringObj*)recv)->len == 0);
        if (k == SWIM_KIND_ARRAY) return SwimBool(((SwimArrayObj*)recv)->n == 0);
        if (k == SWIM_KIND_SET) return SwimBool(((SwimSetObj*)recv)->n == 0);
        if (k == SWIM_KIND_DICT) return SwimBool(((SwimDictObj*)recv)->n == 0);
    }
    if (strcmp(name, "keys") == 0 && k == SWIM_KIND_DICT) {
        SwimDictObj* d = (SwimDictObj*)recv;
        SwimValue out = SwimArrayNew(NULL);
        for (int64_t i = 0; i < d->n; i++)
            if (d->entries[i].key) SwimArrayAppendValue(out, d->entries[i].key);
        return out;
    }
    if (strcmp(name, "values") == 0 && k == SWIM_KIND_DICT) {
        SwimDictObj* d = (SwimDictObj*)recv;
        SwimValue out = SwimArrayNew(NULL);
        for (int64_t i = 0; i < d->n; i++)
            if (d->entries[i].key)
                SwimArrayAppendValue(out, d->entries[i].value);
        return out;
    }
    if (strcmp(name, "first") == 0) {
        if (k == SWIM_KIND_ARRAY) {
            SwimArrayObj* a = (SwimArrayObj*)recv;
            if (a->n == 0) return SwimNone();
            SwimValue v = a->items[0];
            SwimRetain(v);
            return SwimSome(v);
        }
        if (k == SWIM_KIND_SET) {
            SwimSetObj* s = (SwimSetObj*)recv;
            for (int64_t i = 0; i < s->n; i++)
                if (s->items[i]) { SwimRetain(s->items[i]); return SwimSome(s->items[i]); }
            return SwimNone();
        }
        if (k == SWIM_KIND_STRING) {
            SwimStringObj* s = (SwimStringObj*)recv;
            if (s->len == 0) return SwimNone();
            return SwimSome(SwimChar((uint8_t)s->data[0]));
        }
    }
    if (strcmp(name, "last") == 0) {
        if (k == SWIM_KIND_ARRAY) {
            SwimArrayObj* a = (SwimArrayObj*)recv;
            if (a->n == 0) return SwimNone();
            SwimValue v = a->items[a->n - 1];
            SwimRetain(v);
            return SwimSome(v);
        }
        if (k == SWIM_KIND_SET) {
            SwimSetObj* s = (SwimSetObj*)recv;
            for (int64_t i = s->n - 1; i >= 0; i--)
                if (s->items[i]) { SwimRetain(s->items[i]); return SwimSome(s->items[i]); }
            return SwimNone();
        }
        if (k == SWIM_KIND_STRING) {
            SwimStringObj* s = (SwimStringObj*)recv;
            if (s->len == 0) return SwimNone();
            return SwimSome(SwimChar((uint8_t)s->data[s->len - 1]));
        }
    }
    if (strcmp(name, "lowerBound") == 0 && k == SWIM_KIND_RANGE) {
        SwimValue v = ((SwimRangeObj*)recv)->lo;
        SwimRetain(v);
        return v;
    }
    if (strcmp(name, "upperBound") == 0 && k == SWIM_KIND_RANGE) {
        SwimValue v = ((SwimRangeObj*)recv)->hi;
        SwimRetain(v);
        return v;
    }
    if ((strcmp(name, "isNaN") == 0) || (strcmp(name, "isFinite") == 0) ||
        (strcmp(name, "isInfinite") == 0)) {
        double d = SwimToDouble(recv);
        if (strcmp(name, "isNaN") == 0) return SwimBool(isnan(d));
        if (strcmp(name, "isFinite") == 0) return SwimBool(isfinite(d));
        return SwimBool(isinf(d));
    }
    if (strcmp(name, "sign") == 0 || strcmp(name, "signum") == 0) {
        double d = SwimToDouble(recv);
        return d > 0 ? SwimInt(1) : (d < 0 ? SwimInt(-1) : SwimInt(0));
    }
    if (strcmp(name, "magnitude") == 0) return SwimDouble(fabs(SwimToDouble(recv)));
    if (strcmp(name, "wholeNumberValue") == 0 && k == SWIM_KIND_CHAR) {
        uint8_t c = ((SwimCharObj*)recv)->v;
        if (c >= '0' && c <= '9') return SwimSome(SwimInt(c - '0'));
        return SwimNone();
    }
    if (strcmp(name, "asciiValue") == 0 && k == SWIM_KIND_CHAR) {
        uint8_t c = ((SwimCharObj*)recv)->v;
        if (c < 128) return SwimSome(SwimInt(c));
        return SwimNone();
    }
    if ((strcmp(name, "isNumber") == 0) && k == SWIM_KIND_CHAR) {
        uint8_t c = ((SwimCharObj*)recv)->v;
        return SwimBool(c >= '0' && c <= '9');
    }
    if (strcmp(name, "isLetter") == 0 && k == SWIM_KIND_CHAR) {
        uint8_t c = ((SwimCharObj*)recv)->v;
        return SwimBool((c >= 'a' && c <= 'z') || (c >= 'A' && c <= 'Z'));
    }
    if (strcmp(name, "isWhitespace") == 0 && k == SWIM_KIND_CHAR) {
        uint8_t c = ((SwimCharObj*)recv)->v;
        return SwimBool(c == ' ' || c == '\t' || c == '\n' || c == '\r' ||
                        c == '\v' || c == '\f');
    }
    if (strcmp(name, "isUppercase") == 0 && k == SWIM_KIND_CHAR) {
        uint8_t c = ((SwimCharObj*)recv)->v;
        return SwimBool(c >= 'A' && c <= 'Z');
    }
    if ((strcmp(name, "uppercased") == 0 || strcmp(name, "lowercased") == 0) &&
        k == SWIM_KIND_CHAR) {
        char c = (char)((SwimCharObj*)recv)->v;
        if (strcmp(name, "uppercased") == 0 && c >= 'a' && c <= 'z')
            c = (char)(c - 32);
        if (strcmp(name, "lowercased") == 0 && c >= 'A' && c <= 'Z')
            c = (char)(c + 32);
        return SwimString(&c, 1);
    }
    if (strcmp(name, "isLowercase") == 0 && k == SWIM_KIND_CHAR) {
        uint8_t c = ((SwimCharObj*)recv)->v;
        return SwimBool(c >= 'a' && c <= 'z');
    }
    return NULL;
}

/* ================================================================== */
/* Builtin methods                                                     */
/* ================================================================== */
static int swim_builtin_mutator(const char* name) {
    static const char* mutators[] = {
        "append", "insert", "remove", "removeAll", "removeFirst", "removeLast",
        "popLast", "removeValue", "updateValue", "swapAt", "sort", "shuffle",
        "formUnion", "formIntersection", "formSymmetricDifference", NULL
    };
    for (int i = 0; mutators[i]; i++)
        if (strcmp(mutators[i], name) == 0) return 1;
    return 0;
}
int SwimBuiltinIsMutator(const char* name) { return swim_builtin_mutator(name); }

static SwimValue swim_seq_slice(SwimValue recv, int64_t lo, int64_t hi);
static SwimValue swim_array_method(SwimValue recv, const char* name, int argc,
                                   SwimValue* argv);

static SwimValue swim_reversed(SwimValue recv) {
    SwimValue out;
    if (SwimKindOf(recv) == SWIM_KIND_STRING) {
        SwimStringObj* s = (SwimStringObj*)SwimDeref(recv);
        char* buf = (char*)malloc((size_t)s->len + 1);
        for (int64_t i = 0; i < s->len; i++) buf[i] = s->data[s->len - 1 - i];
        buf[s->len] = '\0';
        out = SwimString(buf, s->len);
        free(buf);
        return out;
    }
    SwimArrayObj* a = (SwimArrayObj*)SwimDeref(recv);
    SwimValue out2 = SwimArrayNew(a->elem);
    for (int64_t i = a->n - 1; i >= 0; i--)
        SwimArrayAppendValue(out2, a->items[i]);
    return out2;
}

static SwimValue swim_joined(SwimValue recv, SwimValue sep) {
    SwimValue r = SwimDeref(recv);
    SwimArrayObj* a = (SwimArrayObj*)r;
    SwimBuf b;
    SwimBufInit(&b);
    int64_t seplen = 0;
    const char* sepdata = "";
    if (sep) {
        SwimValue sd = SwimDeref(sep);
        if (sd->type->kind == SWIM_KIND_STRING) {
            sepdata = ((SwimStringObj*)sd)->data;
            seplen = ((SwimStringObj*)sd)->len;
        } else {
            SwimValue s = SwimStr(sep);
            SwimBufAddBytes(&b, ((SwimStringObj*)s)->data,
                            ((SwimStringObj*)s)->len);
            SwimRelease(s);
        }
    }
    SwimBuf tmp;
    SwimBufInit(&tmp);
    for (int64_t i = 0; i < a->n; i++) {
        if (i) SwimBufAddBytes(&b, sepdata, seplen);
        SwimValue s = SwimStr(a->items[i]);
        SwimBufAddBytes(&b, ((SwimStringObj*)s)->data,
                        ((SwimStringObj*)s)->len);
        SwimRelease(s);
    }
    SwimBufFree(&tmp);
    return SwimBufValue(&b);
}

static SwimValue swim_string_method(SwimValue recv, const char* name, int argc,
                                    SwimValue* argv) {
    SwimStringObj* s = (SwimStringObj*)SwimDeref(recv);
    if (strcmp(name, "uppercased") == 0) {
        char* buf = (char*)malloc((size_t)s->len + 1);
        for (int64_t i = 0; i < s->len; i++) {
            char c = s->data[i];
            buf[i] = (c >= 'a' && c <= 'z') ? (char)(c - 32) : c;
        }
        buf[s->len] = '\0';
        SwimValue r = SwimString(buf, s->len);
        free(buf);
        return r;
    }
    if (strcmp(name, "lowercased") == 0) {
        char* buf = (char*)malloc((size_t)s->len + 1);
        for (int64_t i = 0; i < s->len; i++) {
            char c = s->data[i];
            buf[i] = (c >= 'A' && c <= 'Z') ? (char)(c + 32) : c;
        }
        buf[s->len] = '\0';
        SwimValue r = SwimString(buf, s->len);
        free(buf);
        return r;
    }
    if (strcmp(name, "capitalized") == 0) {
        if (s->len == 0) return SwimString("", 0);
        char* buf = (char*)malloc((size_t)s->len + 1);
        memcpy(buf, s->data, (size_t)s->len);
        if (buf[0] >= 'a' && buf[0] <= 'z') buf[0] = (char)(buf[0] - 32);
        buf[s->len] = '\0';
        SwimValue r = SwimString(buf, s->len);
        free(buf);
        return r;
    }
    if (strcmp(name, "hasPrefix") == 0) {
        SwimStringObj* p = (SwimStringObj*)SwimDeref(argv[0]);
        if (p->len > s->len) return SwimBool(false);
        return SwimBool(memcmp(s->data, p->data, (size_t)p->len) == 0);
    }
    if (strcmp(name, "hasSuffix") == 0) {
        SwimStringObj* p = (SwimStringObj*)SwimDeref(argv[0]);
        if (p->len > s->len) return SwimBool(false);
        return SwimBool(memcmp(s->data + s->len - p->len, p->data,
                               (size_t)p->len) == 0);
    }
    if (strcmp(name, "contains") == 0) {
        if (argc < 1) return SwimBool(false);
        SwimValue a0 = SwimDeref(argv[0]);
        if (a0->type->kind == SWIM_KIND_CLOSURE) {
            for (int64_t i = 0; i < s->len; i++) {
                SwimValue r = swim_call1(argv[0], SwimChar((uint8_t)s->data[i]));
                int ok = SwimUnboxBool(r);
                SwimRelease(r);
                if (ok) return SwimBool(true);
            }
            return SwimBool(false);
        }
        SwimValue sub = SwimStr(argv[0]);
        SwimStringObj* p = (SwimStringObj*)SwimDeref(sub);
        int found = 0;
        if (p->len <= s->len) {
            for (int64_t i = 0; i + p->len <= s->len; i++) {
                if (memcmp(s->data + i, p->data, (size_t)p->len) == 0) {
                    found = 1;
                    break;
                }
            }
        }
        SwimRelease(sub);
        return SwimBool(found);
    }
    if (strcmp(name, "replacingOccurrences") == 0) {
        int iof = swim_arg_index("of,with", "of", argc);
        int iwith = swim_arg_index("of,with", "with", argc);
        if (iof >= 0 && iwith >= 0) {
            SwimValue target = SwimStr(argv[iof]);
            SwimValue repl = SwimStr(argv[iwith]);
            SwimStringObj* t = (SwimStringObj*)SwimDeref(target);
            SwimStringObj* r = (SwimStringObj*)SwimDeref(repl);
            SwimBuf b;
            SwimBufInit(&b);
            int64_t i = 0;
            while (i < s->len) {
                if (t->len > 0 && i + t->len <= s->len &&
                    memcmp(s->data + i, t->data, (size_t)t->len) == 0) {
                    SwimBufAddBytes(&b, r->data, r->len);
                    i += t->len;
                } else {
                    SwimBufAddChar(&b, s->data[i]);
                    i++;
                }
            }
            SwimRelease(target);
            SwimRelease(repl);
            return SwimBufValue(&b);
        }
    }
    if (strcmp(name, "trimmingCharacters") == 0) {
        int64_t lo = 0, hi = s->len;
        while (lo < hi && (s->data[lo] == ' ' || s->data[lo] == '\t' ||
                           s->data[lo] == '\n' || s->data[lo] == '\r'))
            lo++;
        while (hi > lo && (s->data[hi - 1] == ' ' || s->data[hi - 1] == '\t' ||
                           s->data[hi - 1] == '\n' || s->data[hi - 1] == '\r'))
            hi--;
        return SwimString(s->data + lo, hi - lo);
    }
    if (strcmp(name, "split") == 0 || strcmp(name, "components") == 0) {
        SwimValue out = SwimArrayNew(NULL);
        if (argc < 1) return out;
        if (argc >= 1 && strcmp(name, "components") != 0) {
            SwimValue sd = SwimDeref(argv[0]);
            if (sd->type->kind == SWIM_KIND_CHAR) {
                char c = (char)SwimUnboxChar(sd);
                int64_t start = 0;
                for (int64_t i = 0; i <= s->len; i++) {
                    if (i == s->len || s->data[i] == c) {
                        if (i > start)
                            SwimArrayAppendValue(out,
                                                 SwimString(s->data + start,
                                                            i - start));
                        start = i + 1;
                    }
                }
                return out;
            }
        }
        SwimStringObj* sep = (SwimStringObj*)SwimDeref(argv[0]);
        if (sep->len == 0) {
            for (int64_t i = 0; i < s->len; i++)
                SwimArrayAppendValue(out, SwimString(s->data + i, 1));
            return out;
        }
        int64_t start = 0, i = 0;
        while (i + sep->len <= s->len) {
            if (memcmp(s->data + i, sep->data, (size_t)sep->len) == 0) {
                if (i > start || strcmp(name, "components") == 0)
                    SwimArrayAppendValue(out,
                                         SwimString(s->data + start, i - start));
                i += sep->len;
                start = i;
            } else {
                i++;
            }
        }
        SwimArrayAppendValue(out, SwimString(s->data + start, s->len - start));
        return out;
    }
    if (strcmp(name, "reversed") == 0) {
        char* buf = (char*)malloc((size_t)s->len + 1);
        for (int64_t i = 0; i < s->len; i++)
            buf[i] = s->data[s->len - 1 - i];
        buf[s->len] = '\0';
        SwimValue r = SwimString(buf, s->len);
        free(buf);
        return r;
    }
    if (strcmp(name, "prefix") == 0) return swim_seq_slice(recv, 0, SwimToInt(argv[0]));
    if (strcmp(name, "suffix") == 0) {
        int64_t n = SwimToInt(argv[0]);
        if (n > s->len) n = s->len;
        return swim_seq_slice(recv, s->len - n, s->len);
    }
    if (strcmp(name, "dropFirst") == 0) {
        int64_t n = argc ? SwimToInt(argv[0]) : 1;
        if (n > s->len) n = s->len;
        return SwimString(s->data + n, s->len - n);
    }
    if (strcmp(name, "dropLast") == 0) {
        int64_t n = argc ? SwimToInt(argv[0]) : 1;
        if (n > s->len) n = s->len;
        return SwimString(s->data, s->len - n);
    }
    if (strcmp(name, "index") == 0 || strcmp(name, "firstIndex") == 0 ||
        strcmp(name, "lastIndex") == 0) {
        int64_t found = -1;
        if (argc >= 1) {
            SwimValue sub = SwimStr(argv[argc - 1]);
            SwimStringObj* p = (SwimStringObj*)SwimDeref(sub);
            if (p->len <= s->len) {
                for (int64_t i = 0; i + p->len <= s->len; i++) {
                    if (memcmp(s->data + i, p->data, (size_t)p->len) == 0) {
                        found = i;
                        if (strcmp(name, "lastIndex") != 0) break;
                    }
                }
            }
            SwimRelease(sub);
        }
        if (found < 0) return SwimNone();
        return SwimSome(SwimInt(found));
    }
    if (strcmp(name, "append") == 0) {
        SwimValue s2 = SwimStr(argv[0]);
        return s2;
    }
    if (strcmp(name, "repeat") == 0) {
        int64_t n = SwimToInt(argv[0]);
        SwimBuf b;
        SwimBufInit(&b);
        for (int64_t i = 0; i < n; i++) SwimBufAddBytes(&b, s->data, s->len);
        return SwimBufValue(&b);
    }
    if (strcmp(name, "enumerated") == 0 || strcmp(name, "map") == 0 ||
        strcmp(name, "compactMap") == 0 || strcmp(name, "filter") == 0 ||
        strcmp(name, "forEach") == 0 || strcmp(name, "allSatisfy") == 0 ||
        strcmp(name, "contains") == 0 || strcmp(name, "sorted") == 0 ||
        strcmp(name, "first") == 0 ||
        strcmp(name, "last") == 0 || strcmp(name, "firstIndex") == 0 ||
        strcmp(name, "min") == 0 || strcmp(name, "max") == 0 ||
        strcmp(name, "reduce") == 0 || strcmp(name, "joined") == 0) {
        SwimValue arr = SwimArrayNew(NULL);
        for (int64_t i = 0; i < s->len; i++)
            SwimArrayAppendValue(arr, SwimChar((uint8_t)s->data[i]));
        SwimValue out = swim_array_method(arr, name, argc, argv);
        SwimRelease(arr);
        if (out == NULL && strcmp(name, "contains") == 0) return SwimBool(false);
        return out;
    }
    if (strcmp(name, "starts") == 0) {
        SwimStringObj* p = (SwimStringObj*)SwimDeref(argv[0]);
        if (p->len > s->len) return SwimBool(false);
        return SwimBool(memcmp(s->data, p->data, (size_t)p->len) == 0);
    }
    return NULL;
}

static SwimValue swim_seq_slice(SwimValue recv, int64_t lo, int64_t hi) {
    SwimValue r = SwimDeref(recv);
    if (r->type->kind == SWIM_KIND_STRING) {
        SwimStringObj* s = (SwimStringObj*)r;
        if (lo < 0) lo = 0;
        if (hi > s->len) hi = s->len;
        if (hi < lo) hi = lo;
        return SwimString(s->data + lo, hi - lo);
    }
    SwimArrayObj* a = (SwimArrayObj*)r;
    int64_t n = a->n;
    if (lo < 0) lo = 0;
    if (hi > n) hi = n;
    if (hi < lo) hi = lo;
    return SwimArrayFrom((int)(hi - lo), a->items + lo, a->elem);
}

static SwimValue swim_array_method(SwimValue recv, const char* name, int argc,
                                   SwimValue* argv) {
    SwimArrayObj* a = (SwimArrayObj*)SwimDeref(recv);
    if (strcmp(name, "append") == 0) {
        if (argc >= 1) {
            SwimValue v = SwimDeref(argv[argc - 1]);
            if (v->type->kind == SWIM_KIND_ARRAY) {
                SwimArrayObj* other = (SwimArrayObj*)v;
                for (int64_t i = 0; i < other->n; i++)
                    SwimArrayAppendValue(recv, other->items[i]);
                return SwimVoid();
            }
            SwimArrayAppendValue(recv, v);
        }
        return SwimVoid();
    }
    if (strcmp(name, "insert") == 0) {
        int iat = swim_arg_index("_,at", "at", argc);
        if (iat < 0) iat = argc - 1;
        int ival = (iat == 0) ? (argc > 1 ? 1 : 0) : 0;
        if (argc < 2) return SwimVoid();
        int64_t idx = SwimToInt(argv[iat]);
        SwimValue v = argv[ival];
        if (idx < 0) idx = 0;
        if (idx > a->n) idx = a->n;
        if (a->n + 1 > a->cap) {
            int64_t nc = a->cap ? a->cap : 8;
            while (nc < a->n + 1) nc *= 2;
            a->items = (SwimValue*)realloc(a->items,
                                           (size_t)nc * sizeof(SwimValue));
            for (int64_t k = a->cap; k < nc; k++) a->items[k] = NULL;
            a->cap = nc;
        }
        for (int64_t k = a->n; k > idx; k--) a->items[k] = a->items[k - 1];
        a->items[idx] = SwimCopy(v);
        a->n++;
        return SwimVoid();
    }
    if (strcmp(name, "remove") == 0) {
        int64_t idx = argc ? SwimToInt(argv[argc - 1]) : 0;
        if (idx < 0) idx += a->n;
        if (idx < 0 || idx >= a->n) SwimFatalFmt("index out of bounds");
        SwimValue out = a->items[idx];
        for (int64_t k = idx; k + 1 < a->n; k++) a->items[k] = a->items[k + 1];
        a->n--;
        a->items[a->n] = NULL;
        return out;
    }
    if (strcmp(name, "removeAll") == 0) {
        if (argc >= 1 && SwimDeref(argv[argc - 1])->type->kind ==
                             SWIM_KIND_CLOSURE) {
            SwimValue keep = SwimArrayNew(a->elem);
            for (int64_t i = 0; i < a->n; i++) {
                SwimValue r = swim_call1(argv[argc - 1], a->items[i]);
                int drop = SwimUnboxBool(r);
                SwimRelease(r);
                if (!drop) SwimArrayAppendValue(keep, a->items[i]);
            }
            SwimArrayObj* k = (SwimArrayObj*)keep;
            for (int64_t i = 0; i < a->n; i++) SwimRelease(a->items[i]);
            free(a->items);
            a->items = k->items;
            a->n = k->n;
            a->cap = k->cap;
            k->items = NULL;
            k->n = k->cap = 0;
            SwimRelease(keep);
            return SwimVoid();
        }
        for (int64_t i = 0; i < a->n; i++) SwimRelease(a->items[i]);
        a->n = 0;
        return SwimVoid();
    }
    if (strcmp(name, "removeLast") == 0) {
        if (a->n == 0) SwimFatalFmt("removeLast on empty array");
        SwimValue out = a->items[a->n - 1];
        a->n--;
        a->items[a->n] = NULL;
        return out;
    }
    if (strcmp(name, "removeFirst") == 0) {
        if (a->n == 0) SwimFatalFmt("removeFirst on empty array");
        SwimValue out = a->items[0];
        for (int64_t i = 0; i + 1 < a->n; i++) a->items[i] = a->items[i + 1];
        a->n--;
        a->items[a->n] = NULL;
        return out;
    }
    if (strcmp(name, "popLast") == 0) {
        if (a->n == 0) return SwimNone();
        SwimValue out = a->items[a->n - 1];
        a->n--;
        a->items[a->n] = NULL;
        return SwimSome(out);
    }
    if (strcmp(name, "contains") == 0) {
        if (argc < 1) return SwimBool(false);
        SwimValue arg = SwimDeref(argv[argc - 1]);
        if (arg->type->kind == SWIM_KIND_CLOSURE) {
            for (int64_t i = 0; i < a->n; i++) {
                SwimValue r = swim_call1(argv[argc - 1], a->items[i]);
                int ok = SwimUnboxBool(r);
                SwimRelease(r);
                if (ok) return SwimBool(true);
            }
            return SwimBool(false);
        }
        for (int64_t i = 0; i < a->n; i++)
            if (SwimValuesEqual(a->items[i], argv[argc - 1])) return SwimBool(true);
        return SwimBool(false);
    }
    if (strcmp(name, "map") == 0) return SwimArrayMap(recv, argv[argc - 1]);
    if (strcmp(name, "filter") == 0) return SwimArrayFilter(recv, argv[argc - 1]);
    if (strcmp(name, "forEach") == 0) {
        for (int64_t i = 0; i < a->n; i++) {
            SwimValue r = swim_call1(argv[argc - 1], a->items[i]);
            if (r) SwimRelease(r);
        }
        return SwimVoid();
    }
    if (strcmp(name, "compactMap") == 0) {
        SwimValue out = SwimArrayNew(NULL);
        for (int64_t i = 0; i < a->n; i++) {
            SwimValue r = swim_call1(argv[argc - 1], a->items[i]);
            SwimValue d = SwimDeref(r);
            if (d && d->type->kind == SWIM_KIND_OPTIONAL) {
                if (SwimIsSome(d)) SwimArrayAppendValue(out, SwimOptionalGet(d));
            } else if (d) {
                SwimArrayAppendValue(out, d);
            }
            SwimRelease(r);
        }
        return out;
    }
    if (strcmp(name, "flatMap") == 0) {
        SwimValue out = SwimArrayNew(NULL);
        for (int64_t i = 0; i < a->n; i++) {
            SwimValue r = swim_call1(argv[argc - 1], a->items[i]);
            SwimValue d = SwimDeref(r);
            if (d && d->type->kind == SWIM_KIND_ARRAY) {
                SwimArrayObj* inner = (SwimArrayObj*)d;
                for (int64_t k = 0; k < inner->n; k++)
                    SwimArrayAppendValue(out, inner->items[k]);
            } else if (d && d->type->kind == SWIM_KIND_OPTIONAL) {
                if (SwimIsSome(d)) SwimArrayAppendValue(out, SwimOptionalGet(d));
            } else if (d) {
                SwimArrayAppendValue(out, d);
            }
            SwimRelease(r);
        }
        return out;
    }
    if (strcmp(name, "reduce") == 0) {
        SwimValue acc;
        if (argc >= 2 && SwimDeref(argv[argc - 1])->type->kind == SWIM_KIND_CLOSURE) {
            acc = SwimCopy(argv[0]);
            for (int64_t i = 0; i < a->n; i++) {
                SwimValue r = swim_call2(argv[argc - 1], acc, a->items[i]);
                SwimRelease(acc);
                acc = r;
            }
            return acc;
        }
        return SwimNone();
    }
    if (strcmp(name, "allSatisfy") == 0) {
        for (int64_t i = 0; i < a->n; i++) {
            SwimValue r = swim_call1(argv[argc - 1], a->items[i]);
            int ok = SwimUnboxBool(r);
            SwimRelease(r);
            if (!ok) return SwimBool(false);
        }
        return SwimBool(true);
    }
    if (strcmp(name, "sorted") == 0) {
        SwimValue closure = NULL;
        if (argc >= 1) {
            SwimValue arg = SwimDeref(argv[argc - 1]);
            if (arg->type->kind == SWIM_KIND_CLOSURE) closure = argv[argc - 1];
        }
        return SwimArraySort(recv, closure, 0);
    }
    if (strcmp(name, "sort") == 0) {
        SwimValue sorted = SwimArraySort(recv, argc ? argv[argc - 1] : NULL, 0);
        SwimArrayObj* so = (SwimArrayObj*)sorted;
        for (int64_t i = 0; i < a->n; i++) SwimRelease(a->items[i]);
        free(a->items);
        a->items = so->items; a->n = so->n; a->cap = so->cap;
        so->items = NULL; so->n = so->cap = 0;
        SwimRelease(sorted);
        return SwimVoid();
    }
    if (strcmp(name, "shuffled") == 0) {
        SwimValue out = SwimArrayFrom((int)a->n, a->items, a->elem);
        SwimArrayObj* o = (SwimArrayObj*)out;
        for (int64_t i = o->n - 1; i > 0; i--) {
            int64_t j = (int64_t)(rand() % (i + 1));
            SwimValue t = o->items[i];
            o->items[i] = o->items[j];
            o->items[j] = t;
        }
        return out;
    }
    if (strcmp(name, "shuffle") == 0) {
        for (int64_t i = a->n - 1; i > 0; i--) {
            int64_t j = (int64_t)(rand() % (i + 1));
            SwimValue t = a->items[i];
            a->items[i] = a->items[j];
            a->items[j] = t;
        }
        return SwimVoid();
    }
    if (strcmp(name, "reversed") == 0) return swim_reversed(recv);
    if (strcmp(name, "joined") == 0) {
        SwimValue sep = SwimCStr("");
        if (argc >= 1) sep = argv[argc - 1];
        SwimValue r = swim_joined(recv, sep);
        return r;
    }
    if (strcmp(name, "firstIndex") == 0 || strcmp(name, "index") == 0 ||
        strcmp(name, "lastIndex") == 0) {
        if (argc < 1) return SwimNone();
        SwimValue arg = SwimDeref(argv[argc - 1]);
        if (arg->type->kind == SWIM_KIND_CLOSURE) {
            int64_t found = -1;
            for (int64_t i = 0; i < a->n; i++) {
                SwimValue r = swim_call1(argv[argc - 1], a->items[i]);
                int ok = SwimUnboxBool(r);
                SwimRelease(r);
                if (ok) { found = i; if (strcmp(name, "lastIndex") != 0) break; }
            }
            return found < 0 ? SwimNone() : SwimSome(SwimInt(found));
        }
        int64_t found = -1;
        for (int64_t i = 0; i < a->n; i++)
            if (SwimValuesEqual(a->items[i], argv[argc - 1])) {
                found = i;
                if (strcmp(name, "lastIndex") != 0) break;
            }
        return found < 0 ? SwimNone() : SwimSome(SwimInt(found));
    }
    if (strcmp(name, "first") == 0 || strcmp(name, "last") == 0) {
        if (argc >= 1 && SwimDeref(argv[argc - 1])->type->kind == SWIM_KIND_CLOSURE) {
            int want_last = strcmp(name, "last") == 0;
            int64_t found = -1;
            for (int64_t i = 0; i < a->n; i++) {
                SwimValue r = swim_call1(argv[argc - 1], a->items[i]);
                int ok = SwimUnboxBool(r);
                SwimRelease(r);
                if (ok) { found = i; if (!want_last) break; }
            }
            if (found < 0) return SwimNone();
            return SwimSome(a->items[found]);
        }
        return NULL;
    }
    if (strcmp(name, "prefix") == 0) {
        int64_t n = SwimToInt(argv[0]);
        if (n > a->n) n = a->n;
        return swim_seq_slice(recv, 0, n);
    }
    if (strcmp(name, "suffix") == 0) {
        int64_t n = SwimToInt(argv[0]);
        if (n > a->n) n = a->n;
        return swim_seq_slice(recv, a->n - n, a->n);
    }
    if (strcmp(name, "dropFirst") == 0) {
        int64_t n = argc ? SwimToInt(argv[0]) : 1;
        if (n > a->n) n = a->n;
        return swim_seq_slice(recv, n, a->n);
    }
    if (strcmp(name, "dropLast") == 0) {
        int64_t n = argc ? SwimToInt(argv[0]) : 1;
        if (n > a->n) n = a->n;
        return swim_seq_slice(recv, 0, a->n - n);
    }
    if (strcmp(name, "min") == 0 || strcmp(name, "max") == 0) {
        int want_max = strcmp(name, "max") == 0;
        if (a->n == 0) return SwimNone();
        SwimValue best = a->items[0];
        SwimValue closure = NULL;
        if (argc >= 1 && SwimDeref(argv[argc - 1])->type->kind == SWIM_KIND_CLOSURE)
            closure = argv[argc - 1];
        for (int64_t i = 1; i < a->n; i++) {
            if (closure) {
                int less = swim_less_with(closure, a->items[i], best);
                if (want_max ? !less && !SwimValuesEqual(a->items[i], best)
                             : less)
                    best = a->items[i];
            } else if (want_max ? SwimCompare(a->items[i], best) > 0
                                : SwimCompare(a->items[i], best) < 0) {
                best = a->items[i];
            }
        }
        SwimRetain(best);
        return SwimSome(best);
    }
    if (strcmp(name, "randomElement") == 0) {
        if (a->n == 0) return SwimNone();
        return SwimSome(a->items[rand() % a->n]);
    }
    if (strcmp(name, "swapAt") == 0) {
        int64_t i = SwimToInt(argv[0]), j = SwimToInt(argv[1]);
        SwimValue t = a->items[i];
        a->items[i] = a->items[j];
        a->items[j] = t;
        return SwimVoid();
    }
    if (strcmp(name, "enumerated") == 0) {
        SwimValue out = SwimArrayNew(NULL);
        for (int64_t i = 0; i < a->n; i++) {
            SwimValue pair[2] = {SwimInt(i), a->items[i]};
            SwimArrayAppendValue(out, SwimTupleFrom(2, pair));
        }
        return out;
    }
    if (strcmp(name, "elementsEqual") == 0) {
        SwimValue other = SwimDeref(argv[0]);
        if (other->type->kind != SWIM_KIND_ARRAY) return SwimBool(false);
        SwimArrayObj* b = (SwimArrayObj*)other;
        if (a->n != b->n) return SwimBool(false);
        for (int64_t i = 0; i < a->n; i++)
            if (!SwimValuesEqual(a->items[i], b->items[i])) return SwimBool(false);
        return SwimBool(true);
    }
    if (strcmp(name, "starts") == 0) {
        SwimValue other = SwimDeref(argv[0]);
        if (other->type->kind != SWIM_KIND_ARRAY) return SwimBool(false);
        SwimArrayObj* b = (SwimArrayObj*)other;
        if (b->n > a->n) return SwimBool(false);
        for (int64_t i = 0; i < b->n; i++)
            if (!SwimValuesEqual(a->items[i], b->items[i])) return SwimBool(false);
        return SwimBool(true);
    }
    if (strcmp(name, "mapValues") == 0) return NULL;
    return NULL;
}

static SwimValue swim_dict_method(SwimValue recv, const char* name, int argc,
                                  SwimValue* argv) {
    SwimDictObj* d = (SwimDictObj*)SwimDeref(recv);
    if (strcmp(name, "updateValue") == 0) {
        int iv = swim_arg_index("_,forKey", "_", argc);
        int ik = swim_arg_index("_,forKey", "forKey", argc);
        if (ik < 0) ik = argc - 1;
        if (iv < 0) iv = 0;
        SwimValue old = SwimDictLookup(recv, argv[ik]);
        SwimDictSet(recv, argv[ik], argv[iv]);
        return old;
    }
    if (strcmp(name, "removeValue") == 0) {
        int ik = argc ? argc - 1 : 0;
        SwimValue old = SwimDictLookup(recv, argv[ik]);
        for (int64_t i = 0; i < d->n; i++) {
            if (d->entries[i].key && SwimValuesEqual(d->entries[i].key, argv[ik])) {
                SwimRelease(d->entries[i].key);
                SwimRelease(d->entries[i].value);
                d->entries[i].key = NULL;
                d->entries[i].value = NULL;
                break;
            }
        }
        return old;
    }
    if (strcmp(name, "mapValues") == 0) {
        SwimValue out = SwimDictNew(d->key_type, NULL);
        for (int64_t i = 0; i < d->n; i++) {
            if (!d->entries[i].key) continue;
            SwimValue r = swim_call1(argv[argc - 1], d->entries[i].value);
            SwimDictSet(out, d->entries[i].key, r);
            SwimRelease(r);
        }
        return out;
    }
    if (strcmp(name, "filter") == 0) {
        SwimValue out = SwimDictNew(d->key_type, d->value_type);
        for (int64_t i = 0; i < d->n; i++) {
            if (!d->entries[i].key) continue;
            SwimValue pair[2] = {d->entries[i].key, d->entries[i].value};
            SwimValue tup = SwimTupleFrom(2, pair);
            tup->type = &SwimType_KeyValue;
            SwimValue r = swim_call1(argv[argc - 1], tup);
            int keep = SwimUnboxBool(r);
            SwimRelease(r);
            SwimRelease(tup);
            if (keep) SwimDictSet(out, d->entries[i].key, d->entries[i].value);
        }
        return out;
    }
    if (strcmp(name, "contains") == 0) {
        return SwimBool(SwimIsSome(SwimDictLookup(recv, argv[0])));
    }
    if (strcmp(name, "sorted") == 0) {
        SwimValue pairs = SwimArrayNew(NULL);
        for (int64_t i = 0; i < d->n; i++) {
            if (!d->entries[i].key) continue;
            SwimValue pair[2] = {d->entries[i].key, d->entries[i].value};
            SwimValue tp = SwimTupleFrom(2, pair);
            tp->type = &SwimType_KeyValue;
            SwimArrayAppendValue(pairs, tp);
        }
        return SwimArraySort(pairs, NULL, 0);
    }
    return NULL;
}

static SwimValue swim_set_method(SwimValue recv, const char* name, int argc,
                                 SwimValue* argv) {
    SwimSetObj* s = (SwimSetObj*)SwimDeref(recv);
    if (strcmp(name, "insert") == 0) {
        int had = SwimUnboxBool(SwimSetLookup(recv, argv[0]));
        SwimSetAdd(recv, argv[0]);
        SwimValue pair[1] = {argv[0]};
        SwimValue tup = SwimTupleFrom(1, pair);
        (void)had;
        return tup;
    }
    if (strcmp(name, "remove") == 0) {
        SwimValue old = SwimSetLookup(recv, argv[0]);
        SwimSetRemoveValue(recv, argv[0]);
        return old;
    }
    if (strcmp(name, "union") == 0) {
        SwimValue out = SwimSetFrom(0, NULL, s->elem);
        for (int64_t i = 0; i < s->n; i++)
            if (s->items[i]) SwimSetAdd(out, s->items[i]);
        SwimValue other = SwimDeref(argv[0]);
        SwimSetObj* o = (SwimSetObj*)other;
        for (int64_t i = 0; i < o->n; i++)
            if (o->items[i]) SwimSetAdd(out, o->items[i]);
        return out;
    }
    if (strcmp(name, "intersection") == 0) {
        SwimValue out = SwimSetNew(s->elem);
        SwimValue other = SwimDeref(argv[0]);
        for (int64_t i = 0; i < s->n; i++) {
            if (!s->items[i]) continue;
            if (SwimUnboxBool(SwimSetLookup(other, s->items[i])))
                SwimSetAdd(out, s->items[i]);
        }
        return out;
    }
    if (strcmp(name, "subtracting") == 0) {
        SwimValue out = SwimSetNew(s->elem);
        SwimValue other = SwimDeref(argv[0]);
        for (int64_t i = 0; i < s->n; i++) {
            if (!s->items[i]) continue;
            if (!SwimUnboxBool(SwimSetLookup(other, s->items[i])))
                SwimSetAdd(out, s->items[i]);
        }
        return out;
    }
    if (strcmp(name, "symmetricDifference") == 0) {
        SwimValue other = SwimDeref(argv[0]);
        SwimValue out = SwimSetNew(s->elem);
        for (int64_t i = 0; i < s->n; i++) {
            if (!s->items[i]) continue;
            if (!SwimUnboxBool(SwimSetLookup(other, s->items[i])))
                SwimSetAdd(out, s->items[i]);
        }
        SwimSetObj* o = (SwimSetObj*)other;
        for (int64_t i = 0; i < o->n; i++) {
            if (!o->items[i]) continue;
            if (!SwimUnboxBool(SwimSetLookup(recv, o->items[i])))
                SwimSetAdd(out, o->items[i]);
        }
        return out;
    }
    if (strcmp(name, "isSubset") == 0) {
        SwimValue other = SwimDeref(argv[0]);
        for (int64_t i = 0; i < s->n; i++) {
            if (!s->items[i]) continue;
            if (!SwimUnboxBool(SwimSetLookup(other, s->items[i])))
                return SwimBool(false);
        }
        return SwimBool(true);
    }
    if (strcmp(name, "isSuperset") == 0) {
        SwimValue other = SwimDeref(argv[0]);
        SwimSetObj* o = (SwimSetObj*)other;
        for (int64_t i = 0; i < o->n; i++) {
            if (!o->items[i]) continue;
            if (!SwimUnboxBool(SwimSetLookup(recv, o->items[i])))
                return SwimBool(false);
        }
        return SwimBool(true);
    }
    if (strcmp(name, "isDisjoint") == 0) {
        SwimValue other = SwimDeref(argv[0]);
        for (int64_t i = 0; i < s->n; i++) {
            if (!s->items[i]) continue;
            if (SwimUnboxBool(SwimSetLookup(other, s->items[i])))
                return SwimBool(false);
        }
        return SwimBool(true);
    }
    if (strcmp(name, "formUnion") == 0) {
        SwimValue other = SwimDeref(argv[0]);
        SwimSetObj* o = (SwimSetObj*)other;
        for (int64_t i = 0; i < o->n; i++)
            if (o->items[i]) SwimSetAdd(recv, o->items[i]);
        return SwimVoid();
    }
    if (strcmp(name, "formIntersection") == 0) {
        SwimValue other = SwimDeref(argv[0]);
        for (int64_t i = 0; i < s->n; i++) {
            if (!s->items[i]) continue;
            if (!SwimUnboxBool(SwimSetLookup(other, s->items[i]))) {
                SwimSetRemoveValue(recv, s->items[i]);
                i--;
            }
        }
        return SwimVoid();
    }
    if (strcmp(name, "formSymmetricDifference") == 0) {
        SwimValue tmp = swim_set_method(recv, "symmetricDifference", argc, argv);
        SwimSetObj* to = (SwimSetObj*)tmp;
        for (int64_t i = 0; i < s->n; i++) SwimRelease(s->items[i]);
        s->n = 0;
        for (int64_t i = 0; i < to->n; i++)
            if (to->items[i]) SwimSetAdd(recv, to->items[i]);
        SwimRelease(tmp);
        return SwimVoid();
    }
    if (strcmp(name, "sorted") == 0) {
        SwimValue arr = SwimArrayNew(s->elem);
        for (int64_t i = 0; i < s->n; i++)
            if (s->items[i]) SwimArrayAppendValue(arr, s->items[i]);
        return SwimArraySort(arr, NULL, 0);
    }
    if (strcmp(name, "map") == 0 || strcmp(name, "compactMap") == 0 ||
        strcmp(name, "filter") == 0 || strcmp(name, "forEach") == 0 ||
        strcmp(name, "allSatisfy") == 0 || strcmp(name, "first") == 0 ||
        strcmp(name, "contains") == 0 || strcmp(name, "min") == 0 ||
        strcmp(name, "max") == 0 || strcmp(name, "randomElement") == 0 ||
        strcmp(name, "enumerated") == 0) {
        SwimValue arr = SwimArrayNew(s->elem);
        for (int64_t i = 0; i < s->n; i++)
            if (s->items[i]) SwimArrayAppendValue(arr, s->items[i]);
        SwimValue r = swim_array_method(arr, name, argc, argv);
        SwimRelease(arr);
        return r;
    }
    return NULL;
}

static SwimValue swim_optional_method(SwimValue recv, const char* name, int argc,
                                      SwimValue* argv) {
    SwimValue d = SwimDeref(recv);
    int has = SwimIsSome(d);
    if (strcmp(name, "map") == 0) {
        if (!has) return SwimNone();
        SwimValue r = swim_call1(argv[argc - 1], SwimOptionalGet(d));
        SwimValue out = SwimSome(r);
        SwimRelease(r);
        return out;
    }
    if (strcmp(name, "flatMap") == 0) {
        if (!has) return SwimNone();
        return swim_call1(argv[argc - 1], SwimOptionalGet(d));
    }
    return NULL;
}

static SwimValue swim_numeric_method(SwimValue recv, const char* name, int argc,
                                     SwimValue* argv) {
    double d = SwimToDouble(SwimDeref(recv));
    int is_float = SwimDeref(recv)->type->kind == SWIM_KIND_DOUBLE;
    if (strcmp(name, "advanced") == 0) {
        double by = SwimToDouble(argv[0]);
        return is_float ? SwimDouble(d + by) : SwimInt(SwimToInt(recv) + (int64_t)by);
    }
    if (strcmp(name, "truncatingRemainder") == 0) {
        double by = SwimToDouble(argv[argc - 1]);
        double r = d - trunc(d / by) * by;
        return is_float ? SwimDouble(r) : SwimInt((int64_t)r);
    }
    if (strcmp(name, "signum") == 0)
        return is_float ? SwimDouble(d > 0 ? 1.0 : (d < 0 ? -1.0 : 0.0))
                        : SwimInt(d > 0 ? 1 : (d < 0 ? -1 : 0));
    if (strcmp(name, "rounded") == 0) {
        double r = round(d);
        return is_float ? SwimDouble(r) : SwimInt((int64_t)r);
    }
    if (strcmp(name, "isMultiple") == 0) {
        int64_t other = SwimToInt(argv[argc - 1]);
        if (other == 0) return SwimBool(false);
        return SwimBool(SwimToInt(recv) % other == 0);
    }
    return NULL;
}

static SwimValue swim_range_as_array_method(SwimValue recv, const char* name,
                                            int argc, SwimValue* argv) {
    SwimValue arr = SwimArrayNew(NULL);
    SwimRangeObj* r = (SwimRangeObj*)SwimDeref(recv);
    int64_t lo = SwimToInt(r->lo), hi = SwimToInt(r->hi);
    for (int64_t i = lo; r->closed ? i <= hi : i < hi; i++)
        SwimArrayAppendValue(arr, SwimInt(i));
    SwimValue out = swim_array_method(arr, name, argc, argv);
    SwimRelease(arr);
    return out;
}

static SwimValue swim_range_method(SwimValue recv, const char* name, int argc,
                                   SwimValue* argv) {
    SwimRangeObj* r = (SwimRangeObj*)SwimDeref(recv);
    if (strcmp(name, "contains") == 0) {
        int64_t v = SwimToInt(argv[0]);
        int64_t lo = SwimToInt(r->lo), hi = SwimToInt(r->hi);
        if (r->closed) return SwimBool(v >= lo && v <= hi);
        return SwimBool(v >= lo && v < hi);
    }
    return NULL;
}

SwimValue SwimBuiltinMethod(SwimValue recv, const char* name, const char* labels,
                            int argc, SwimValue* argv) {
    (void)labels;
    recv = SwimDeref(recv);
    if (recv == NULL) return NULL;
    SwimKind k = recv->type->kind;
    SwimValue r = NULL;
    if (k == SWIM_KIND_STRING) r = swim_string_method(recv, name, argc, argv);
    else if (k == SWIM_KIND_ARRAY) r = swim_array_method(recv, name, argc, argv);
    else if (k == SWIM_KIND_DICT) r = swim_dict_method(recv, name, argc, argv);
    else if (k == SWIM_KIND_SET) r = swim_set_method(recv, name, argc, argv);
    else if (k == SWIM_KIND_OPTIONAL) r = swim_optional_method(recv, name, argc, argv);
    else if (SwimIsNumeric(recv)) r = swim_numeric_method(recv, name, argc, argv);
    else if (k == SWIM_KIND_RANGE) {
        r = swim_range_method(recv, name, argc, argv);
        if (r == NULL) r = swim_range_as_array_method(recv, name, argc, argv);
    }
    if (r != NULL) return r;
    /* fall back to properties used as method calls (count(), isEmpty(), ...) */
    if (argc == 0) {
        SwimValue p = SwimBuiltinProperty(recv, name);
        if (p) return p;
    }
    return NULL;
}

/* ================================================================== */
/* Conversions                                                         */
/* ================================================================== */
static int swim_parse_int(const char* data, int64_t len, int64_t* out) {
    char buf[128];
    if (len <= 0 || len >= (int64_t)sizeof(buf)) return 0;
    memcpy(buf, data, (size_t)len);
    buf[len] = '\0';
    char* end = NULL;
    long long v = strtoll(buf, &end, 10);
    if (end == buf || *end != '\0') return 0;
    *out = (int64_t)v;
    return 1;
}
static int swim_parse_double(const char* data, int64_t len, double* out) {
    char buf[256];
    if (len <= 0 || len >= (int64_t)sizeof(buf)) return 0;
    memcpy(buf, data, (size_t)len);
    buf[len] = '\0';
    char* end = NULL;
    double v = strtod(buf, &end);
    if (end == buf || *end != '\0') return 0;
    *out = v;
    return 1;
}

SwimValue SwimConvert(SwimType* t, int argc, SwimValue* argv) {
    if (argc < 1) return SwimVoid();
    SwimValue v = SwimDeref(argv[argc - 1]);
    if (v == NULL) return SwimNone();
    if (t == &SwimType_Int) {
        if (v->type->kind == SWIM_KIND_STRING) {
            int64_t out;
            if (swim_parse_int(((SwimStringObj*)v)->data,
                               ((SwimStringObj*)v)->len, &out))
                return SwimSome(SwimInt(out));
            return SwimNone();
        }
        if (v->type->kind == SWIM_KIND_CHAR) return SwimInt(((SwimCharObj*)v)->v);
        if (v->type->kind == SWIM_KIND_BOOL) return SwimInt(((SwimBoolObj*)v)->v);
        return SwimInt(SwimToInt(v));
    }
    if (t == &SwimType_Double) {
        if (v->type->kind == SWIM_KIND_STRING) {
            double out;
            if (swim_parse_double(((SwimStringObj*)v)->data,
                                  ((SwimStringObj*)v)->len, &out))
                return SwimSome(SwimDouble(out));
            return SwimNone();
        }
        return SwimDouble(SwimToDouble(v));
    }
    if (t == &SwimType_Bool) return SwimBool(SwimUnboxBool(v));
    if (t == &SwimType_Char) {
        if (v->type->kind == SWIM_KIND_STRING) {
            SwimStringObj* s = (SwimStringObj*)v;
            if (s->len == 1) return SwimChar((uint8_t)s->data[0]);
            return SwimChar((uint8_t)(s->len ? s->data[0] : 0));
        }
        return SwimChar((uint8_t)SwimToInt(v));
    }
    if (t->kind == SWIM_KIND_STRING) return SwimStr(v);
    if (t->kind == SWIM_KIND_ARRAY) {
        SwimValue out = SwimArrayNew(NULL);
        if (v->type->kind == SWIM_KIND_STRING) {
            SwimStringObj* s = (SwimStringObj*)v;
            for (int64_t i = 0; i < s->len; i++)
                SwimArrayAppendValue(out, SwimChar((uint8_t)s->data[i]));
        }
        return out;
    }
    if (t->kind == SWIM_KIND_SET) {
        SwimValue out = SwimSetNew(NULL);
        if (v->type->kind == SWIM_KIND_ARRAY) {
            SwimArrayObj* a = (SwimArrayObj*)v;
            for (int64_t i = 0; i < a->n; i++) SwimSetAdd(out, a->items[i]);
        }
        return out;
    }
    return SwimCopy(v);
}

/* ================================================================== */
/* Free functions                                                      */
/* ================================================================== */
static SwimValue swim_number_builtin(const char* name, int argc,
                                     SwimValue* argv) {
    double a = argc > 0 ? SwimToDouble(argv[0]) : 0;
    if (strcmp(name, "abs") == 0) {
        if (SwimDeref(argv[0])->type->kind == SWIM_KIND_INT)
            return SwimInt(llabs((long long)SwimToInt(argv[0])));
        return SwimDouble(fabs(a));
    }
    if (strcmp(name, "sqrt") == 0) return SwimDouble(sqrt(a));
    if (strcmp(name, "floor") == 0) return SwimDouble(floor(a));
    if (strcmp(name, "ceil") == 0) return SwimDouble(ceil(a));
    if (strcmp(name, "round") == 0) return SwimDouble(round(a));
    if (strcmp(name, "pow") == 0)
        return SwimDouble(pow(a, argc > 1 ? SwimToDouble(argv[1]) : 1));
    return NULL;
}

static SwimValue swim_minmax_builtin(const char* name, int argc,
                                     SwimValue* argv) {
    int want_max = strcmp(name, "max") == 0;
    if (argc == 1) {
        SwimValue a = SwimDeref(argv[0]);
        if (a->type->kind == SWIM_KIND_ARRAY) {
            SwimArrayObj* arr = (SwimArrayObj*)a;
            if (arr->n == 0) return SwimNone();
            SwimValue best = arr->items[0];
            for (int64_t i = 1; i < arr->n; i++) {
                int c = SwimCompare(arr->items[i], best);
                if (want_max ? c > 0 : c < 0) best = arr->items[i];
            }
            SwimRetain(best);
            return best;
        }
    }
    if (argc >= 2) {
        int c = SwimCompare(argv[0], argv[1]);
        SwimValue best = (want_max ? (c >= 0 ? argv[0] : argv[1])
                                   : (c <= 0 ? argv[0] : argv[1]));
        SwimRetain(best);
        return best;
    }
    return SwimNone();
}

SwimValue SwimBuiltinCall(const char* name, const char* labels, int argc,
                          SwimValue* argv) {
    if (strcmp(name, "print") == 0) {
        const char* sep = " ";
        const char* term = "\n";
        int n = argc;
        int isep = swim_arg_index(labels, "separator", argc);
        int iterm = swim_arg_index(labels, "terminator", argc);
        SwimValue seps[1], terms[1];
        if (isep >= 0) {
            seps[0] = SwimStr(argv[isep]);
            sep = ((SwimStringObj*)seps[0])->data;
        }
        if (iterm >= 0) {
            terms[0] = SwimStr(argv[iterm]);
            term = ((SwimStringObj*)terms[0])->data;
        }
        SwimValue* vals = (SwimValue*)calloc((size_t)n + 1, sizeof(SwimValue));
        int at = 0;
        for (int i = 0; i < argc; i++) {
            if (i == isep || i == iterm) continue;
            vals[at++] = argv[i];
        }
        SwimPrintValues(at, vals, sep, term);
        free(vals);
        if (isep >= 0) SwimRelease(seps[0]);
        if (iterm >= 0) SwimRelease(terms[0]);
        return SwimVoid();
    }
    if (strcmp(name, "debugPrint") == 0) return SwimBuiltinCall("print", labels, argc, argv);
    if (strcmp(name, "abs") == 0 || strcmp(name, "sqrt") == 0 ||
        strcmp(name, "floor") == 0 || strcmp(name, "ceil") == 0 ||
        strcmp(name, "round") == 0 || strcmp(name, "pow") == 0) {
        SwimValue r = swim_number_builtin(name, argc, argv);
        if (r) return r;
    }
    if (strcmp(name, "min") == 0 || strcmp(name, "max") == 0) {
        return swim_minmax_builtin(name, argc, argv);
    }
    if (strcmp(name, "zip") == 0) {
        SwimValue a = SwimDeref(argv[0]), b = SwimDeref(argv[1]);
        SwimValue out = SwimArrayNew(NULL);
        if (a->type->kind == SWIM_KIND_ARRAY && b->type->kind == SWIM_KIND_ARRAY) {
            SwimArrayObj* aa = (SwimArrayObj*)a;
            SwimArrayObj* bb = (SwimArrayObj*)b;
            int64_t n = aa->n < bb->n ? aa->n : bb->n;
            for (int64_t i = 0; i < n; i++) {
                SwimValue pair[2] = {aa->items[i], bb->items[i]};
                SwimArrayAppendValue(out, SwimTupleFrom(2, pair));
            }
        }
        return out;
    }
    if (strcmp(name, "readLine") == 0) {
        char* line = NULL;
        size_t cap = 0;
        ssize_t n = getline(&line, &cap, stdin);
        if (n < 0) { free(line); return SwimNone(); }
        while (n > 0 && (line[n - 1] == '\n' || line[n - 1] == '\r')) n--;
        SwimValue out = SwimSome(SwimString(line, (int64_t)n));
        free(line);
        return out;
    }
    if (strcmp(name, "exit") == 0) {
        fflush(stdout);
        exit(argc ? (int)SwimToInt(argv[0]) : 0);
    }
    if (strcmp(name, "fatalError") == 0 || strcmp(name, "preconditionFailure") == 0) {
        if (argc) SwimFatalV(argv[0]);
        SwimFatal("fatal error");
    }
    if (strcmp(name, "assert") == 0 || strcmp(name, "precondition") == 0) {
        int ok = argc ? SwimUnboxBool(argv[0]) : 1;
        if (!ok) {
            if (argc > 1) SwimFatalV(argv[1]);
            SwimFatal("Assertion failed");
        }
        return SwimVoid();
    }
    if (strcmp(name, "random") == 0) {
        return SwimDouble((double)rand() / (double)RAND_MAX);
    }
    if (strcmp(name, "stride") == 0) {
        int ifrom = swim_arg_index(labels, "from", argc);
        int ito = swim_arg_index(labels, "to", argc);
        int ithrough = swim_arg_index(labels, "through", argc);
        int iby = swim_arg_index(labels, "by", argc);
        if (ifrom < 0) ifrom = 0;
        int64_t from = SwimToInt(argv[ifrom]);
        int64_t to = ithrough >= 0 ? SwimToInt(argv[ithrough])
                                   : (ito >= 0 ? SwimToInt(argv[ito]) : from);
        int64_t by = iby >= 0 ? SwimToInt(argv[iby]) : 1;
        if (by == 0) by = 1;
        SwimValue out = SwimArrayNew(NULL);
        if (by > 0) {
            int64_t stop = ithrough >= 0 ? to + 1 : to;
            for (int64_t i = from; i < stop; i += by)
                SwimArrayAppendValue(out, SwimInt(i));
        } else {
            int64_t stop = ithrough >= 0 ? to - 1 : to;
            for (int64_t i = from; i > stop; i += by)
                SwimArrayAppendValue(out, SwimInt(i));
        }
        return out;
    }
    if (strcmp(name, "String") == 0) {
        return SwimConvert(&SwimType_String, argc, argv);
    }
    if (strcmp(name, "type") == 0) return SwimCStr("Any");
    /* free-function form of methods on the first argument */
    SwimValue r = SwimBuiltinMethod(argv[0], name, labels, argc - 1, argv + 1);
    if (r) return r;
    SwimFatalFmt("unknown function '%s'", name);
}

/* ================================================================== */
/* Static members                                                      */
/* ================================================================== */
int SwimBuiltinStaticExists(SwimType* t, const char* name) {
    (void)t;
    (void)name;
    return 1;
}

SwimValue SwimBuiltinStatic(SwimType* t, const char* name, const char* labels,
                            int argc, SwimValue* argv) {
    /* conversions and constructors */
    if (strcmp(name, "init") == 0 || strcmp(name, "__convert__") == 0) {
        if (t == &SwimType_Int || t == &SwimType_Double || t == &SwimType_Bool ||
            t == &SwimType_Char || t == &SwimType_String) {
            /* String(repeating:count:) */
            if (t == &SwimType_String && swim_arg_index(labels, "repeating", argc) >= 0) {
                int irep = swim_arg_index(labels, "repeating", argc);
                int icnt = swim_arg_index(labels, "count", argc);
                SwimValue s = SwimStr(argv[irep]);
                int64_t cnt = SwimToInt(argv[icnt]);
                SwimStringObj* so = (SwimStringObj*)SwimDeref(s);
                SwimBuf b;
                SwimBufInit(&b);
                for (int64_t i = 0; i < cnt; i++)
                    SwimBufAddBytes(&b, so->data, so->len);
                SwimRelease(s);
                return SwimBufValue(&b);
            }
            return SwimConvert(t, argc, argv);
        }
        if (t->kind == SWIM_KIND_ARRAY || t->kind == SWIM_KIND_SET) {
            int irep = swim_arg_index(labels, "repeating", argc);
            int icnt = swim_arg_index(labels, "count", argc);
            if (irep >= 0 && icnt >= 0) {
                int64_t cnt = SwimToInt(argv[icnt]);
                SwimValue arr = SwimArrayNew(t->elem);
                for (int64_t i = 0; i < cnt; i++)
                    SwimArrayAppendValue(arr, argv[irep]);
                return arr;
            }
            if (argc >= 1) return SwimConvert(t, argc, argv);
            SwimValue arr = SwimArrayNew(NULL);
            return arr;
        }
        if (t->kind == SWIM_KIND_DICT) {
            if (argc >= 1) return SwimConvert(t, argc, argv);
            return SwimDictNew(NULL, NULL);
        }
        if (t->kind == SWIM_KIND_ENUM) {
            if (swim_arg_index(labels, "rawValue", argc) >= 0) {
                int iraw = swim_arg_index(labels, "rawValue", argc);
                SwimValue raw = argv[iraw];
                return SwimEnumFromRaw(t, labels, 1, &raw);
            }
            return SwimEnumCase(t, "init", argc, argv);
        }
        return SwimConstruct(t, labels, argc, argv);
    }
    if (t->kind == SWIM_KIND_ENUM) {
        if (strcmp(name, "allCases") == 0) {
            SwimValue out = SwimArrayNew(NULL);
            for (int i = 0; i < t->case_count; i++) {
                if (t->cases[i].payload_count != 0) continue;
                SwimArrayAppendValue(out, SwimEnumCase(t, t->cases[i].name, 0, NULL));
            }
            return out;
        }
        if (strcmp(name, "fromRaw") == 0) return SwimEnumFromRaw(t, labels, argc, argv);
    }
    if (t == &SwimType_Int || t == &SwimType_Double || t == &SwimType_Bool ||
        t == &SwimType_String || t == &SwimType_Char) {
        if (strcmp(name, "max") == 0) return SwimInt(INT64_MAX);
        if (strcmp(name, "min") == 0) return SwimInt(INT64_MIN);
        if (strcmp(name, "pi") == 0) return SwimDouble(M_PI);
        if (strcmp(name, "random") == 0) {
            if (swim_arg_index(labels, "in", argc) >= 0) {
                SwimValue r = argv[swim_arg_index(labels, "in", argc)];
                SwimRangeObj* rr = (SwimRangeObj*)SwimDeref(r);
                int64_t lo = SwimToInt(rr->lo), hi = SwimToInt(rr->hi);
                if (t == &SwimType_Double)
                    return SwimDouble(lo + ((double)rand() / (double)RAND_MAX) *
                                               (double)(hi - lo));
                return SwimInt(lo + rand() % (hi - lo + 1));
            }
            return SwimDouble((double)rand() / (double)RAND_MAX);
        }
        if (strcmp(name, "description") == 0) return SwimCStr(t->name);
    }
    /* static methods of user types live in the registered tables */
    SwimFatalFmt("unknown static member '%s' of '%s'", name, t->name);
}
