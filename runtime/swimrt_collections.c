/* swimrt_collections.c -- arrays, dictionaries, sets, tuples, ranges,
 * string helpers, iteration and sorting for the Swim runtime. */
#include "swimrt_internal.h"

#include <stdlib.h>
#include <string.h>
#include <stdio.h>

/* ================================================================== */
/* Arrays                                                              */
/* ================================================================== */
static void swim_array_reserve(SwimArrayObj* a, int64_t want) {
    if (want <= a->cap) return;
    int64_t nc = a->cap ? a->cap : 8;
    while (nc < want) nc *= 2;
    a->items = (SwimValue*)realloc(a->items, (size_t)nc * sizeof(SwimValue));
    if (!a->items) { fprintf(stderr, "swim: out of memory\n"); exit(1); }
    for (int64_t i = a->cap; i < nc; i++) a->items[i] = NULL;
    a->cap = nc;
}

SwimValue SwimArrayNew(const SwimType* elem) {
    SwimArrayObj* a =
        (SwimArrayObj*)swim_alloc(&SwimType_Array, sizeof(SwimArrayObj));
    a->h.type = &SwimType_Array;
    a->elem = (SwimType*)elem;
    return (SwimValue)a;
}
SwimValue SwimArrayFrom(int n, SwimValue* items, const SwimType* elem) {
    SwimArrayObj* a = (SwimArrayObj*)SwimArrayNew(elem);
    swim_array_reserve(a, n);
    a->n = n;
    for (int i = 0; i < n; i++) {
        SwimValue v = items[i];
        if (elem) v = SwimCoerce(v, elem);
        a->items[i] = SwimCopy(v);
    }
    return (SwimValue)a;
}
void SwimArrayAppendValue(SwimValue arr, SwimValue v) {
    arr = SwimDeref(arr);
    SwimArrayObj* a = (SwimArrayObj*)arr;
    if (v && a->elem) v = SwimCoerce(v, a->elem);
    swim_array_reserve(a, a->n + 1);
    a->items[a->n++] = SwimCopy(v);
}
int64_t SwimArrayCount(SwimValue arr) {
    arr = SwimDeref(arr);
    return ((SwimArrayObj*)arr)->n;
}
SwimValue SwimArrayAt(SwimValue arr, int64_t i) {
    arr = SwimDeref(arr);
    SwimArrayObj* a = (SwimArrayObj*)arr;
    if (i < 0) i += a->n;
    if (i < 0 || i >= a->n) SwimFatalFmt("index out of bounds");
    SwimRetain(a->items[i]);
    return a->items[i];
}
void SwimArraySetAt(SwimValue arr, int64_t i, SwimValue v) {
    arr = SwimDeref(arr);
    SwimArrayObj* a = (SwimArrayObj*)arr;
    if (i < 0) i += a->n;
    if (i < 0 || i >= a->n) SwimFatalFmt("index out of bounds");
    SwimStore(&a->items[i], v);
}

/* ================================================================== */
/* Dictionaries                                                        */
/* ================================================================== */
static int64_t swim_dict_find(SwimDictObj* d, SwimValue key) {
    for (int64_t i = 0; i < d->n; i++) {
        if (d->entries[i].key &&
            SwimValuesEqual(d->entries[i].key, key)) return i;
    }
    return -1;
}
SwimValue SwimDictNew(const SwimType* key, const SwimType* value) {
    SwimDictObj* d =
        (SwimDictObj*)swim_alloc(&SwimType_Dict, sizeof(SwimDictObj));
    d->h.type = &SwimType_Dict;
    d->key_type = (SwimType*)key;
    d->value_type = (SwimType*)value;
    return (SwimValue)d;
}
void SwimDictSet(SwimValue dict, SwimValue key, SwimValue value) {
    dict = SwimDeref(dict);
    SwimDictObj* d = (SwimDictObj*)dict;
    key = SwimDeref(key);
    if (d->key_type) key = SwimCoerce(key, d->key_type);
    if (d->value_type) value = SwimCoerce(value, d->value_type);
    int64_t idx = swim_dict_find(d, key);
    if (idx >= 0) {
        SwimStore(&d->entries[idx].value, value);
        return;
    }
    if (d->n >= d->cap) {
        int64_t nc = d->cap ? d->cap * 2 : 8;
        d->entries = (SwimDictEntry*)realloc(d->entries,
                                             (size_t)nc * sizeof(SwimDictEntry));
        if (!d->entries) { fprintf(stderr, "swim: out of memory\n"); exit(1); }
        for (int64_t i = d->cap; i < nc; i++) {
            d->entries[i].key = NULL;
            d->entries[i].value = NULL;
        }
        d->cap = nc;
    }
    d->entries[d->n].key = SwimCopy(key);
    d->entries[d->n].value = SwimCopy(value);
    d->n++;
}
SwimValue SwimDictLookup(SwimValue dict, SwimValue key) {
    dict = SwimDeref(dict);
    key = SwimDeref(key);
    SwimDictObj* d = (SwimDictObj*)dict;
    int64_t idx = swim_dict_find(d, key);
    if (idx < 0) return SwimNone();
    SwimValue v = d->entries[idx].value;
    SwimRetain(v);
    return SwimSome(v);
}
SwimValue SwimDictFrom(int n, SwimValue* keys, SwimValue* values,
                       const SwimType* key, const SwimType* value) {
    SwimValue d = SwimDictNew(key, value);
    for (int i = 0; i < n; i++) SwimDictSet(d, keys[i], values[i]);
    return d;
}

/* ================================================================== */
/* Sets                                                                */
/* ================================================================== */
static int64_t swim_set_find(SwimSetObj* s, SwimValue key) {
    for (int64_t i = 0; i < s->n; i++) {
        if (s->items[i] && SwimValuesEqual(s->items[i], key)) return i;
    }
    return -1;
}
SwimValue SwimSetNew(const SwimType* elem) {
    SwimSetObj* s =
        (SwimSetObj*)swim_alloc(&SwimType_Set, sizeof(SwimSetObj));
    s->h.type = &SwimType_Set;
    s->elem = (SwimType*)elem;
    return (SwimValue)s;
}
void SwimSetAdd(SwimValue set, SwimValue key) {
    set = SwimDeref(set);
    key = SwimDeref(key);
    SwimSetObj* s = (SwimSetObj*)set;
    if (s->elem) key = SwimCoerce(key, s->elem);
    if (swim_set_find(s, key) >= 0) return;
    if (s->n >= s->cap) {
        int64_t nc = s->cap ? s->cap * 2 : 8;
        s->items = (SwimValue*)realloc(s->items, (size_t)nc * sizeof(SwimValue));
        if (!s->items) { fprintf(stderr, "swim: out of memory\n"); exit(1); }
        for (int64_t i = s->cap; i < nc; i++) s->items[i] = NULL;
        s->cap = nc;
    }
    s->items[s->n++] = SwimCopy(key);
}
void SwimSetRemoveValue(SwimValue set, SwimValue key) {
    set = SwimDeref(set);
    key = SwimDeref(key);
    SwimSetObj* s = (SwimSetObj*)set;
    int64_t idx = swim_set_find(s, key);
    if (idx < 0) return;
    SwimRelease(s->items[idx]);
    memmove(s->items + idx, s->items + idx + 1,
            (size_t)(s->n - idx - 1) * sizeof(SwimValue));
    s->n--;
}
SwimValue SwimSetLookup(SwimValue set, SwimValue key) {
    set = SwimDeref(set);
    key = SwimDeref(key);
    SwimSetObj* s = (SwimSetObj*)set;
    return SwimBool(swim_set_find(s, key) >= 0);
}
SwimValue SwimSetFrom(int n, SwimValue* items, const SwimType* elem) {
    SwimValue s = SwimSetNew(elem);
    for (int i = 0; i < n; i++) SwimSetAdd(s, items[i]);
    return s;
}

/* ================================================================== */
/* Tuples, enums, ranges                                               */
/* ================================================================== */
SwimValue SwimTupleFrom(int n, SwimValue* items) {
    SwimTupleObj* t =
        (SwimTupleObj*)swim_alloc(&SwimType_Tuple, sizeof(SwimTupleObj));
    t->h.type = &SwimType_Tuple;
    t->n = n;
    t->slots = n ? (SwimValue*)calloc((size_t)n, sizeof(SwimValue)) : NULL;
    for (int i = 0; i < n; i++) t->slots[i] = SwimCopy(items[i]);
    return (SwimValue)t;
}
SwimValue SwimRangeFrom(SwimValue lo, SwimValue hi, int closed) {
    SwimRangeObj* r =
        (SwimRangeObj*)swim_alloc(&SwimType_Range, sizeof(SwimRangeObj));
    r->h.type = &SwimType_Range;
    r->lo = SwimCopy(lo);
    r->hi = SwimCopy(hi);
    r->closed = closed;
    return (SwimValue)r;
}
int64_t SwimRangeLower(SwimValue r) {
    r = SwimDeref(r);
    return SwimToInt(((SwimRangeObj*)r)->lo);
}
int64_t SwimRangeUpper(SwimValue r) {
    r = SwimDeref(r);
    return SwimToInt(((SwimRangeObj*)r)->hi);
}

/* ================================================================== */
/* Strings                                                             */
/* ================================================================== */
SwimValue SwimMakeString(const char* s, int64_t n) { return SwimString(s, n); }
SwimValue SwimStringByteAt(SwimValue s, int64_t i) {
    s = SwimDeref(s);
    SwimStringObj* so = (SwimStringObj*)s;
    if (i < 0) i += so->len;
    if (i < 0 || i >= so->len) SwimFatalFmt("string index out of bounds");
    return SwimChar((uint8_t)so->data[i]);
}
SwimValue SwimStringSubstr(SwimValue s, int64_t lo, int64_t hi) {
    s = SwimDeref(s);
    SwimStringObj* so = (SwimStringObj*)s;
    if (lo < 0) lo = 0;
    if (hi > so->len) hi = so->len;
    if (hi < lo) hi = lo;
    return SwimString(so->data + lo, hi - lo);
}
SwimValue SwimConcatValues(SwimValue* vals, int n) {
    int64_t total = 0;
    for (int i = 0; i < n; i++) {
        SwimValue s = SwimStr(vals[i]);
        total += ((SwimStringObj*)s)->len;
        SwimRelease(s);
    }
    char* buf = (char*)malloc((size_t)total + 1);
    int64_t at = 0;
    for (int i = 0; i < n; i++) {
        SwimValue s = SwimStr(vals[i]);
        int64_t len = ((SwimStringObj*)s)->len;
        memcpy(buf + at, ((SwimStringObj*)s)->data, (size_t)len);
        at += len;
        SwimRelease(s);
    }
    buf[at] = '\0';
    SwimValue out = SwimString(buf, at);
    free(buf);
    return out;
}

/* ================================================================== */
/* Iteration                                                           */
/* ================================================================== */
enum {
    SWIM_ITER_DONE = 0,
    SWIM_ITER_ARRAY,
    SWIM_ITER_STRING,
    SWIM_ITER_DICT,
    SWIM_ITER_SET,
    SWIM_ITER_RANGE
};

struct SwimIterator {
    int mode;
    SwimValue src;
    int64_t idx;
    int64_t cur, stop, step;
    int closed;
};

SwimIterator* SwimIterate(SwimValue v) {
    v = SwimDeref(v);
    if (v == NULL) SwimFatalFmt("cannot iterate over nil");
    SwimIterator* it = (SwimIterator*)calloc(1, sizeof(SwimIterator));
    it->src = v;
    SwimRetain(v);
    switch (v->type->kind) {
        case SWIM_KIND_ARRAY: it->mode = SWIM_ITER_ARRAY; break;
        case SWIM_KIND_STRING: it->mode = SWIM_ITER_STRING; break;
        case SWIM_KIND_DICT: it->mode = SWIM_ITER_DICT; break;
        case SWIM_KIND_SET: it->mode = SWIM_ITER_SET; break;
        case SWIM_KIND_RANGE: {
            SwimRangeObj* r = (SwimRangeObj*)v;
            it->mode = SWIM_ITER_RANGE;
            it->cur = SwimToInt(r->lo);
            it->stop = SwimToInt(r->hi);
            it->step = 1;
            it->closed = r->closed;
            break;
        }
        default:
            SwimFatalFmt("type '%s' is not iterable", v->type->name);
    }
    return it;
}
int SwimIterNext(SwimIterator* it, SwimValue* out) {
    if (it->mode == SWIM_ITER_DONE) return 0;
    if (it->mode == SWIM_ITER_ARRAY) {
        SwimArrayObj* a = (SwimArrayObj*)it->src;
        if (it->idx >= a->n) { it->mode = SWIM_ITER_DONE; return 0; }
        *out = SwimCopy(a->items[it->idx++]);
        return 1;
    }
    if (it->mode == SWIM_ITER_STRING) {
        SwimStringObj* s = (SwimStringObj*)it->src;
        if (it->idx >= s->len) { it->mode = SWIM_ITER_DONE; return 0; }
        *out = SwimChar((uint8_t)s->data[it->idx++]);
        return 1;
    }
    if (it->mode == SWIM_ITER_DICT) {
        SwimDictObj* d = (SwimDictObj*)it->src;
        while (it->idx < d->n && d->entries[it->idx].key == NULL) it->idx++;
        if (it->idx >= d->n) { it->mode = SWIM_ITER_DONE; return 0; }
        SwimValue pair[2];
        pair[0] = d->entries[it->idx].key;
        pair[1] = d->entries[it->idx].value;
        it->idx++;
        *out = SwimTupleFrom(2, pair);
        (*out)->type = &SwimType_KeyValue;
        return 1;
    }
    if (it->mode == SWIM_ITER_SET) {
        SwimSetObj* s = (SwimSetObj*)it->src;
        while (it->idx < s->n && s->items[it->idx] == NULL) it->idx++;
        if (it->idx >= s->n) { it->mode = SWIM_ITER_DONE; return 0; }
        *out = SwimCopy(s->items[it->idx++]);
        return 1;
    }
    /* range */
    {
        if (it->step > 0) {
            if (it->closed ? it->cur > it->stop : it->cur >= it->stop) {
                it->mode = SWIM_ITER_DONE;
                return 0;
            }
        } else {
            if (it->closed ? it->cur < it->stop : it->cur <= it->stop) {
                it->mode = SWIM_ITER_DONE;
                return 0;
            }
        }
        *out = SwimInt(it->cur);
        it->cur += it->step;
        return 1;
    }
}
void SwimIterFree(SwimIterator* it) {
    if (!it) return;
    SwimRelease(it->src);
    free(it);
}
SwimValue SwimRangeStep(SwimValue start, SwimValue stop, SwimValue step,
                        int closed) {
    SwimRangeObj* r =
        (SwimRangeObj*)swim_alloc(&SwimType_Range, sizeof(SwimRangeObj));
    r->h.type = &SwimType_Range;
    r->lo = SwimCopy(start);
    r->hi = SwimCopy(stop);
    r->closed = closed | 2; /* bit 1 marks a stepped range */
    /* store step in a hidden slot by wrapping: use closed flag bit for step? */
    (void)step;
    return (SwimValue)r;
}

/* ================================================================== */
/* Sorting / transform helpers used by the builtin library             */
/* ================================================================== */
static int swim_call_less(SwimValue closure, SwimValue a, SwimValue b) {
    if (closure == NULL) return SwimCompare(a, b) < 0;
    SwimValue argv[2] = {a, b};
    SwimValue r = SwimCallValue(closure, 2, argv);
    int less = SwimUnboxBool(r);
    SwimRelease(r);
    return less;
}

static void swim_merge(SwimValue* dst, SwimValue* left, int64_t ln,
                       SwimValue* right, int64_t rn, SwimValue closure) {
    int64_t i = 0, j = 0, k = 0;
    while (i < ln && j < rn) {
        if (swim_call_less(closure, right[j], left[i]))
            dst[k++] = right[j++];
        else
            dst[k++] = left[i++];
    }
    while (i < ln) dst[k++] = left[i++];
    while (j < rn) dst[k++] = right[j++];
}

static void swim_msort(SwimValue* items, int64_t n, SwimValue closure) {
    if (n < 2) return;
    int64_t mid = n / 2;
    SwimValue* left = (SwimValue*)calloc((size_t)mid, sizeof(SwimValue));
    SwimValue* right = (SwimValue*)calloc((size_t)(n - mid), sizeof(SwimValue));
    for (int64_t i = 0; i < mid; i++) left[i] = items[i];
    for (int64_t i = mid; i < n; i++) right[i - mid] = items[i];
    swim_msort(left, mid, closure);
    swim_msort(right, n - mid, closure);
    swim_merge(items, left, mid, right, n - mid, closure);
    free(left);
    free(right);
}

SwimValue SwimArraySort(SwimValue arr, SwimValue closure, int descending) {
    arr = SwimDeref(arr);
    SwimArrayObj* a = (SwimArrayObj*)arr;
    SwimValue copy = SwimArrayFrom((int)a->n, a->items, NULL);
    SwimArrayObj* c = (SwimArrayObj*)copy;
    swim_msort(c->items, c->n, closure);
    if (descending) {
        for (int64_t i = 0, j = c->n - 1; i < j; i++, j--) {
            SwimValue t = c->items[i];
            c->items[i] = c->items[j];
            c->items[j] = t;
        }
    }
    return copy;
}

SwimValue SwimArrayMap(SwimValue arr, SwimValue closure) {
    arr = SwimDeref(arr);
    SwimArrayObj* a = (SwimArrayObj*)arr;
    SwimArrayObj* out = (SwimArrayObj*)SwimArrayNew(NULL);
    for (int64_t i = 0; i < a->n; i++) {
        SwimValue argv[1] = {a->items[i]};
        SwimValue r = SwimCallValue(closure, 1, argv);
        SwimArrayAppendValue((SwimValue)out, r);
        SwimRelease(r);
    }
    return (SwimValue)out;
}

SwimValue SwimArrayFilter(SwimValue arr, SwimValue closure) {
    arr = SwimDeref(arr);
    SwimArrayObj* a = (SwimArrayObj*)arr;
    SwimArrayObj* out = (SwimArrayObj*)SwimArrayNew(NULL);
    for (int64_t i = 0; i < a->n; i++) {
        SwimValue argv[1] = {a->items[i]};
        SwimValue r = SwimCallValue(closure, 1, argv);
        int keep = SwimUnboxBool(r);
        SwimRelease(r);
        if (keep) SwimArrayAppendValue((SwimValue)out, a->items[i]);
    }
    return (SwimValue)out;
}

void SwimIterFreePtr(SwimIterator** it) {
    if (it && *it) { SwimIterFree(*it); *it = NULL; }
}

/* [T](repeating:count:) and [T](arrayLiteral:) constructors. */
SwimValue SwimArrayInit(SwimType* elem, int argc, SwimValue* argv);
SwimValue SwimArrayInit(SwimType* elem, int argc, SwimValue* argv) {
    SwimValue arr = SwimArrayNew(elem);
    for (int i = 0; i < argc; i++) {
        SwimValue a = SwimDeref(argv[i]);
        if (a && a->type->kind == SWIM_KIND_ARRAY) {
            SwimArrayObj* src = (SwimArrayObj*)a;
            for (int64_t k = 0; k < src->n; k++)
                SwimArrayAppendValue(arr, src->items[k]);
            return arr;
        }
    }
    return arr;
}
