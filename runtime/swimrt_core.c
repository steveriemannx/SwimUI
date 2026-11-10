/* swimrt_core.c -- objects, atomic ARC, value semantics, printing,
 * operators, optionals and conversions for the Swim runtime. */
#include "swimrt_internal.h"

#include <stdlib.h>
#include <string.h>
#include <stdio.h>
#include <math.h>
#include <stdarg.h>
#include <stdatomic.h>
#include <execinfo.h>

/* ================================================================== */
/* Primitive type descriptors                                          */
/* ================================================================== */
SwimType SwimType_Void = { "Void", SWIM_KIND_VOID, 0, 0, 0, 0, 0, 0, 0, 0, 0 };
SwimType SwimType_Int = { "Int", SWIM_KIND_INT, 0, 0, 0, 0, 0, 0, 0, 0, 0 };
SwimType SwimType_Double = { "Double", SWIM_KIND_DOUBLE, 0, 0, 0, 0, 0, 0, 0, 0, 0 };
SwimType SwimType_Bool = { "Bool", SWIM_KIND_BOOL, 0, 0, 0, 0, 0, 0, 0, 0, 0 };
SwimType SwimType_Char = { "Character", SWIM_KIND_CHAR, 0, 0, 0, 0, 0, 0, 0, 0, 0 };
SwimType SwimType_String = { "String", SWIM_KIND_STRING, 0, 0, 0, 0, 0, 0, 0, 0, 0 };
SwimType SwimType_Array = { "Array", SWIM_KIND_ARRAY, 0, 0, 0, 0, 0, 0, 0, 0, 0 };
SwimType SwimType_Dict = { "Dictionary", SWIM_KIND_DICT, 0, 0, 0, 0, 0, 0, 0, 0, 0 };
SwimType SwimType_Set = { "Set", SWIM_KIND_SET, 0, 0, 0, 0, 0, 0, 0, 0, 0 };
SwimType SwimType_Optional = { "Optional", SWIM_KIND_OPTIONAL, 0, 0, 0, 0, 0, 0, 0, 0, 0 };
SwimType SwimType_Tuple = { "Tuple", SWIM_KIND_TUPLE, 0, 0, 0, 0, 0, 0, 0, 0, 0 };
SwimType SwimType_Range = { "Range", SWIM_KIND_RANGE, 0, 0, 0, 0, 0, 0, 0, 0, 0 };
SwimType SwimType_Closure = { "Closure", SWIM_KIND_CLOSURE, 0, 0, 0, 0, 0, 0, 0, 0, 0 };
SwimType SwimType_Any = { "Any", SWIM_KIND_ANY, 0, 0, 0, 0, 0, 0, 0, 0, 0 };
SwimType SwimType_Int8 = { "Int8", SWIM_KIND_INT, 0, 0, 0, 0, 0, 0, 0, 0, 0 };
SwimType SwimType_Int16 = { "Int16", SWIM_KIND_INT, 0, 0, 0, 0, 0, 0, 0, 0, 0 };
SwimType SwimType_Int32 = { "Int32", SWIM_KIND_INT, 0, 0, 0, 0, 0, 0, 0, 0, 0 };
SwimType SwimType_Int64 = { "Int64", SWIM_KIND_INT, 0, 0, 0, 0, 0, 0, 0, 0, 0 };
SwimType SwimType_UInt = { "UInt", SWIM_KIND_INT, 0, 0, 0, 0, 0, 0, 0, 0, 0 };
SwimType SwimType_UInt8 = { "UInt8", SWIM_KIND_INT, 0, 0, 0, 0, 0, 0, 0, 0, 0 };
SwimType SwimType_UInt16 = { "UInt16", SWIM_KIND_INT, 0, 0, 0, 0, 0, 0, 0, 0, 0 };
SwimType SwimType_UInt32 = { "UInt32", SWIM_KIND_INT, 0, 0, 0, 0, 0, 0, 0, 0, 0 };
SwimType SwimType_UInt64 = { "UInt64", SWIM_KIND_INT, 0, 0, 0, 0, 0, 0, 0, 0, 0 };
SwimType SwimType_Float32 = { "Float", SWIM_KIND_DOUBLE, 0, 0, 0, 0, 0, 0, 0, 0, 0 };
SwimType SwimType_Generic = { "T", SWIM_KIND_ANY, 0, 0, 0, 0, 0, 0, 0, 0, 0 };
SwimType SwimType_Frame = { "Frame", SWIM_KIND_FRAME, 0, 0, 0, 0, 0, 0, 0, 0, 0 };
SwimType SwimType_Meta = { "Type", SWIM_KIND_TYPE, 0, 0, 0, 0, 0, 0, 0, 0, 0 };
SwimType SwimType_Weak = { "Weak", SWIM_KIND_WEAK, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0 };
static const SwimFieldDesc swim_kv_fields[] = {
    { "key", &SwimType_Any }, { "value", &SwimType_Any }
};
SwimType SwimType_KeyValue = { "Tuple", SWIM_KIND_TUPLE, 0, 0, 0, 0, 2,
                               swim_kv_fields, 0, 0, 0 };

/* ================================================================== */
/* Allocation, ARC                                                     */
/* ================================================================== */
SwimObj* swim_alloc(SwimType* t, size_t size) {
    SwimObj* o = (SwimObj*)calloc(1, size);
    if (o == NULL) {
        fprintf(stderr, "swim: out of memory\n");
        exit(1);
    }
    atomic_store_explicit(&o->rc, 1, memory_order_relaxed);
    o->type = t;
    return o;
}

static SwimObj* swim_void_singleton = NULL;
SwimValue SwimVoid(void) {
    if (swim_void_singleton == NULL)
        swim_void_singleton = swim_alloc(&SwimType_Void, sizeof(SwimObj));
    SwimRetain((SwimValue)swim_void_singleton);
    return (SwimValue)swim_void_singleton;
}

void SwimRetain(SwimValue v) {
    if (v == NULL) return;
    atomic_fetch_add_explicit(&v->rc, 1, memory_order_relaxed);
}

SwimValue SwimInt(int64_t x) {
    SwimIntObj* o = (SwimIntObj*)swim_alloc(&SwimType_Int, sizeof(SwimIntObj));
    o->v = x;
    return (SwimValue)o;
}
SwimValue SwimDouble(double x) {
    SwimDoubleObj* o =
        (SwimDoubleObj*)swim_alloc(&SwimType_Double, sizeof(SwimDoubleObj));
    o->v = x;
    return (SwimValue)o;
}
SwimValue SwimBool(bool x) {
    SwimBoolObj* o = (SwimBoolObj*)swim_alloc(&SwimType_Bool, sizeof(SwimBoolObj));
    o->v = x ? 1 : 0;
    return (SwimValue)o;
}
SwimValue SwimChar(uint8_t x) {
    SwimCharObj* o = (SwimCharObj*)swim_alloc(&SwimType_Char, sizeof(SwimCharObj));
    o->v = x;
    return (SwimValue)o;
}
SwimValue SwimTypeValue(SwimType* t) {
    SwimTypeObj* o = (SwimTypeObj*)swim_alloc(&SwimType_Meta,
                                              sizeof(SwimTypeObj));
    o->h.type = &SwimType_Meta;
    o->target = t;
    return (SwimValue)o;
}

SwimValue SwimRetainResult(SwimValue v) {
    if (v) SwimRetain(v);
    return v;
}
int SwimTruthy(SwimValue v) { return SwimUnboxBool(v); }
SwimValue SwimTupleGet(SwimValue t, int idx) {
    t = SwimDeref(t);
    if (t->type->kind != SWIM_KIND_TUPLE) SwimFatalFmt("expected a tuple");
    SwimTupleObj* tu = (SwimTupleObj*)t;
    if (idx < 0 || idx >= tu->n) SwimFatalFmt("tuple index out of bounds");
    SwimValue v = tu->slots[idx];
    if (v) SwimRetain(v);
    return v;
}
SwimValue SwimGetFieldRaw(SwimValue obj, const char* name) {
    obj = SwimDeref(obj);
    for (int i = 0; i < obj->type->field_count; i++) {
        if (strcmp(obj->type->fields[i].name, name) == 0) {
            SwimObjectObj* o = (SwimObjectObj*)obj;
            SwimValue v = i < o->n ? o->slots[i] : NULL;
            if (v) SwimRetain(v);
            return v;
        }
    }
    SwimFatalFmt("type '%s' has no field '%s'", obj->type->name, name);
}
void SwimInitField(SwimValue obj, const char* name, SwimValue v) {
    obj = SwimDeref(obj);
    for (int i = 0; i < obj->type->field_count; i++) {
        if (strcmp(obj->type->fields[i].name, name) == 0) {
            SwimObjectObj* o = (SwimObjectObj*)obj;
            if (i < o->n) {
                const SwimFieldDesc* d = &obj->type->fields[i];
                if (d->weak || d->unowned) {
                    SwimValue holder = SwimWeakMake(v, d->unowned ? 1 : 0);
                    SwimStore(&o->slots[i], holder);
                    SwimRelease(holder);
                    return;
                }
                SwimStore(&o->slots[i], v);
                return;
            }
        }
    }
    SwimFatalFmt("type '%s' has no field '%s'", obj->type->name, name);
}
int64_t SwimUnboxInt(SwimValue v) {
    v = SwimDeref(v);
    if (v->type == &SwimType_Int) return ((SwimIntObj*)v)->v;
    if (v->type == &SwimType_Double) return (int64_t)((SwimDoubleObj*)v)->v;
    if (v->type == &SwimType_Bool) return ((SwimBoolObj*)v)->v;
    if (v->type == &SwimType_Char) return ((SwimCharObj*)v)->v;
    SwimFatalFmt("expected a number, got %s", v->type->name);
}
double SwimUnboxDouble(SwimValue v) {
    v = SwimDeref(v);
    if (v->type == &SwimType_Double) return ((SwimDoubleObj*)v)->v;
    if (v->type == &SwimType_Int) return (double)((SwimIntObj*)v)->v;
    SwimFatalFmt("expected a number, got %s", v->type->name);
}
bool SwimUnboxBool(SwimValue v) {
    v = SwimDeref(v);
    if (v == NULL) return false;
    if (v->type == &SwimType_Bool) return ((SwimBoolObj*)v)->v != 0;
    if (v->type == &SwimType_Int) return ((SwimIntObj*)v)->v != 0;
    if (v->type == &SwimType_Double) return ((SwimDoubleObj*)v)->v != 0.0;
    SwimFatalFmt("expected a Bool, got %s", v->type->name);
}
uint8_t SwimUnboxChar(SwimValue v) {
    v = SwimDeref(v);
    if (v->type == &SwimType_Char) return ((SwimCharObj*)v)->v;
    if (v->type == &SwimType_String) {
        SwimStringObj* s = (SwimStringObj*)v;
        if (s->len != 1)
            SwimFatalFmt("a Character must be a single-character string");
        return (uint8_t)s->data[0];
    }
    SwimFatalFmt("expected a Character, got %s", v->type->name);
}
const char* SwimStringData(SwimValue v) {
    v = SwimDeref(v);
    if (v->type != &SwimType_String) SwimFatalFmt("expected a String");
    return ((SwimStringObj*)v)->data;
}
int64_t SwimStringLen(SwimValue v) {
    v = SwimDeref(v);
    if (v->type != &SwimType_String) SwimFatalFmt("expected a String");
    return ((SwimStringObj*)v)->len;
}

SwimValue SwimString(const char* bytes, int64_t len) {
    SwimStringObj* o =
        (SwimStringObj*)swim_alloc(&SwimType_String, sizeof(SwimStringObj));
    o->len = len;
    o->data = (char*)malloc((size_t)len + 1);
    if (o->data == NULL) { fprintf(stderr, "swim: out of memory\n"); exit(1); }
    if (len) memcpy(o->data, bytes, (size_t)len);
    o->data[len] = '\0';
    return (SwimValue)o;
}
SwimValue SwimCStr(const char* s) { return SwimString(s, (int64_t)strlen(s)); }

/* ------------------------------------------------------------------ */
static void swim_zero_weak_refs(SwimObj* o) {
    SwimWeakRef* node = o->weak_head;
    o->weak_head = NULL;
    while (node != NULL) {
        SwimWeakRef* next = node->next;
        if (node->slot) *node->slot = NULL;
        node->next = NULL;
        node = next;
    }
}

static void swim_run_deinit(SwimObj* o) {
    o->destroying = 1;
    for (SwimType* t = o->type; t != NULL; t = (SwimType*)t->parent) {
        if (t->deinit) {
            SwimValue self = (SwimValue)o;
            t->deinit(NULL, 1, &self);
        }
    }
}

void SwimRelease(SwimValue v) {
    if (v == NULL) return;
    if (v == (SwimValue)swim_void_singleton) return;
    if (atomic_fetch_sub_explicit(&v->rc, 1, memory_order_acq_rel) != 1) return;
    if (v->destroying) return; /* a release during this object's own deinit */
    if (v->type->kind == SWIM_KIND_CLASS) {
        /* Swift semantics: weak references are zeroed before deinit runs. */
        swim_zero_weak_refs(v);
        swim_run_deinit(v);
        if (atomic_load_explicit(&v->rc, memory_order_acquire) != 0) {
            v->destroying = 0; /* resurrected by user code: keep it alive */
            return;
        }
    }
    switch (v->type->kind) {
        case SWIM_KIND_STRING: {
            SwimStringObj* s = (SwimStringObj*)v;
            free(s->data);
            break;
        }
        case SWIM_KIND_ARRAY: {
            SwimArrayObj* a = (SwimArrayObj*)v;
            for (int64_t i = 0; i < a->n; i++) SwimRelease(a->items[i]);
            free(a->items);
            break;
        }
        case SWIM_KIND_DICT: {
            SwimDictObj* d = (SwimDictObj*)v;
            for (int64_t i = 0; i < d->n; i++) {
                if (d->entries[i].key) {
                    SwimRelease(d->entries[i].key);
                    SwimRelease(d->entries[i].value);
                }
            }
            free(d->entries);
            break;
        }
        case SWIM_KIND_SET: {
            SwimSetObj* s = (SwimSetObj*)v;
            for (int64_t i = 0; i < s->n; i++)
                if (s->items[i]) SwimRelease(s->items[i]);
            free(s->items);
            break;
        }
        case SWIM_KIND_OPTIONAL: {
            SwimOptionalObj* o = (SwimOptionalObj*)v;
            if (o->has) SwimRelease(o->value);
            break;
        }
        case SWIM_KIND_TUPLE:
        case SWIM_KIND_STRUCT:
        case SWIM_KIND_CLASS: {
            SwimObjectObj* o = (SwimObjectObj*)v;
            for (int64_t i = 0; i < o->n; i++) SwimRelease(o->slots[i]);
            free(o->slots);
            break;
        }
        case SWIM_KIND_ENUM: {
            SwimEnumObj* e = (SwimEnumObj*)v;
            for (int64_t i = 0; i < e->n; i++) SwimRelease(e->slots[i]);
            free(e->slots);
            break;
        }
        case SWIM_KIND_CLOSURE: {
            SwimClosureObj* c = (SwimClosureObj*)v;
            if (c->env) SwimRelease((SwimValue)c->env);
            break;
        }
        case SWIM_KIND_RANGE: {
            SwimRangeObj* r = (SwimRangeObj*)v;
            SwimRelease(r->lo);
            SwimRelease(r->hi);
            break;
        }
        case SWIM_KIND_FRAME: {
            SwimFrameObj* f = (SwimFrameObj*)v;
            for (int64_t i = 0; i < f->n; i++) SwimRelease(f->slots[i]);
            free(f->slots);
            if (f->parent) SwimRelease((SwimValue)f->parent);
            break;
        }
        case SWIM_KIND_WEAK: {
            SwimWeakObj* w = (SwimWeakObj*)v;
            if (w->target != NULL) {
                SwimWeakRef** pp = &w->target->weak_head;
                while (*pp != NULL) {
                    if (*pp == &w->node) {
                        *pp = w->node.next;
                        break;
                    }
                    pp = &(*pp)->next;
                }
                w->target = NULL;
            }
            break;
        }
        case SWIM_KIND_PROXY: {
            SwimProxyObj* p = (SwimProxyObj*)v;
            SwimRelease(p->target);
            break;
        }
        default:
            break;
    }
    free(v);
}

void SwimReleasePtr(SwimValue* slot) {
    if (slot && *slot) { SwimRelease(*slot); *slot = NULL; }
}
void SwimStoreRef(SwimValue* slot, SwimValue v) {
    if (v) SwimRetain(v);
    if (*slot) SwimRelease(*slot);
    *slot = v;
}
void SwimStore(SwimValue* slot, SwimValue v) {
    SwimValue nv = SwimCopy(v);
    if (*slot) SwimRelease(*slot);
    *slot = nv;
}

SwimValue SwimDeref(SwimValue v) {
    while (v != NULL && v->type->kind == SWIM_KIND_PROXY) {
        SwimProxyObj* p = (SwimProxyObj*)v;
        v = SwimGetMemberRaw(p->target, p->member);
    }
    return v;
}
SwimKind SwimKindOf(SwimValue v) {
    v = SwimDeref(v);
    if (v == NULL) return SWIM_KIND_VOID;
    return v->type->kind;
}
SwimType* SwimValueType(SwimValue v) {
    v = SwimDeref(v);
    if (v == NULL) return &SwimType_Void;
    return v->type;
}

/* ================================================================== */
/* Value-semantics copy                                                */
/* ================================================================== */
static SwimValue swim_copy_shallow(SwimValue v) {
    /* Deep copy of the *structure*; nested values are copied recursively. */
    if (v == NULL) return NULL;
    switch (v->type->kind) {
        case SWIM_KIND_ARRAY: {
            SwimArrayObj* a = (SwimArrayObj*)v;
            SwimArrayObj* c =
                (SwimArrayObj*)swim_alloc(&SwimType_Array, sizeof(SwimArrayObj));
            c->h.type = &SwimType_Array;
            c->cap = a->n;
            c->n = a->n;
            c->elem = a->elem;
            c->items = a->n ? (SwimValue*)calloc((size_t)a->n, sizeof(SwimValue)) : NULL;
            for (int64_t i = 0; i < a->n; i++) c->items[i] = SwimCopy(a->items[i]);
            return (SwimValue)c;
        }
        case SWIM_KIND_DICT: {
            SwimDictObj* d = (SwimDictObj*)v;
            SwimDictObj* c =
                (SwimDictObj*)swim_alloc(&SwimType_Dict, sizeof(SwimDictObj));
            c->h.type = &SwimType_Dict;
            c->cap = d->n;
            c->n = d->n;
            c->key_type = d->key_type;
            c->value_type = d->value_type;
            c->entries = d->n ? (SwimDictEntry*)calloc((size_t)d->n,
                                                      sizeof(SwimDictEntry)) : NULL;
            for (int64_t i = 0; i < d->n; i++) {
                if (d->entries[i].key) {
                    c->entries[i].key = SwimCopy(d->entries[i].key);
                    c->entries[i].value = SwimCopy(d->entries[i].value);
                }
            }
            return (SwimValue)c;
        }
        case SWIM_KIND_SET: {
            SwimSetObj* s = (SwimSetObj*)v;
            SwimSetObj* c =
                (SwimSetObj*)swim_alloc(&SwimType_Set, sizeof(SwimSetObj));
            c->h.type = &SwimType_Set;
            c->cap = s->n;
            c->n = s->n;
            c->elem = s->elem;
            c->items = s->n ? (SwimValue*)calloc((size_t)s->n, sizeof(SwimValue)) : NULL;
            for (int64_t i = 0; i < s->n; i++)
                c->items[i] = s->items[i] ? SwimCopy(s->items[i]) : NULL;
            return (SwimValue)c;
        }
        case SWIM_KIND_OPTIONAL: {
            SwimOptionalObj* o = (SwimOptionalObj*)v;
            SwimOptionalObj* c =
                (SwimOptionalObj*)swim_alloc(&SwimType_Optional, sizeof(SwimOptionalObj));
            c->h.type = &SwimType_Optional;
            c->has = o->has;
            c->value = o->has ? SwimCopy(o->value) : NULL;
            return (SwimValue)c;
        }
        case SWIM_KIND_TUPLE: {
            SwimTupleObj* t = (SwimTupleObj*)v;
            SwimTupleObj* c =
                (SwimTupleObj*)swim_alloc(&SwimType_Tuple, sizeof(SwimTupleObj));
            c->h.type = v->type;
            c->n = t->n;
            c->slots = t->n ? (SwimValue*)calloc((size_t)t->n, sizeof(SwimValue)) : NULL;
            for (int64_t i = 0; i < t->n; i++) c->slots[i] = SwimCopy(t->slots[i]);
            return (SwimValue)c;
        }
        case SWIM_KIND_STRUCT: {
            SwimObjectObj* o = (SwimObjectObj*)v;
            SwimObjectObj* c =
                (SwimObjectObj*)swim_alloc(v->type, sizeof(SwimObjectObj));
            c->h.type = v->type;
            c->n = o->n;
            c->slots = o->n ? (SwimValue*)calloc((size_t)o->n, sizeof(SwimValue)) : NULL;
            for (int64_t i = 0; i < o->n; i++) c->slots[i] = SwimCopy(o->slots[i]);
            return (SwimValue)c;
        }
        case SWIM_KIND_ENUM: {
            SwimEnumObj* e = (SwimEnumObj*)v;
            SwimEnumObj* c =
                (SwimEnumObj*)swim_alloc(v->type, sizeof(SwimEnumObj));
            c->h.type = v->type;
            c->tag = e->tag;
            c->n = e->n;
            c->slots = e->n ? (SwimValue*)calloc((size_t)e->n, sizeof(SwimValue)) : NULL;
            for (int64_t i = 0; i < e->n; i++) c->slots[i] = SwimCopy(e->slots[i]);
            return (SwimValue)c;
        }
        default:
            SwimRetain(v);
            return v;
    }
}

SwimValue SwimCopy(SwimValue v) {
    if (v == NULL) return NULL;
    v = SwimDeref(v);
    if (SwimIsRefKind(v->type->kind)) { SwimRetain(v); return v; }
    return swim_copy_shallow(v);
}

/* ================================================================== */
/* Frames and globals                                                  */
/* ================================================================== */
static SwimFrame* swim_global_frame = NULL;

SwimFrame* SwimFrameNew(SwimFrame* parent, int cap) {
    SwimFrameObj* f = (SwimFrameObj*)swim_alloc(&SwimType_Frame,
                                                sizeof(SwimFrameObj));
    f->h.type = &SwimType_Frame;
    if (cap < 4) cap = 4;
    f->cap = cap;
    f->n = 0;
    f->slots = (SwimValue*)calloc((size_t)cap, sizeof(SwimValue));
    f->parent = parent;
    if (parent) SwimRetain((SwimValue)parent);
    return (SwimFrame*)f;
}
SwimValue SwimFrameGet(SwimFrame* fr, int i) {
    SwimFrameObj* f = (SwimFrameObj*)fr;
    if (i < 0 || i >= f->n) return NULL;
    SwimValue v = f->slots[i];
    if (v) SwimRetain(v);
    return v;
}
SwimValue SwimFramePeek(SwimFrame* fr, int i) {
    SwimFrameObj* f = (SwimFrameObj*)fr;
    if (fr == NULL || i < 0 || i >= f->n) return NULL;
    return f->slots[i];
}

void SwimFrameSet(SwimFrame* fr, int i, SwimValue v) {
    SwimFrameObj* f = (SwimFrameObj*)fr;
    if (i >= f->cap) {
        int nc = f->cap ? f->cap : 4;
        while (nc <= i) nc *= 2;
        f->slots = (SwimValue*)realloc(f->slots, (size_t)nc * sizeof(SwimValue));
        for (int k = f->cap; k < nc; k++) f->slots[k] = NULL;
        f->cap = nc;
    }
    if (i >= f->n) f->n = i + 1;
    SwimStore(&f->slots[i], v);
}
void SwimFrameSetRefAt(SwimFrame* fr, int i, SwimValue v) {
    SwimFrameObj* f = (SwimFrameObj*)fr;
    if (i >= f->cap) {
        int nc = f->cap ? f->cap : 4;
        while (nc <= i) nc *= 2;
        f->slots = (SwimValue*)realloc(f->slots, (size_t)nc * sizeof(SwimValue));
        for (int k = f->cap; k < nc; k++) f->slots[k] = NULL;
        f->cap = nc;
    }
    if (i >= f->n) f->n = i + 1;
    SwimStoreRef(&f->slots[i], v);
}
void SwimFrameSetRef(SwimFrame* fr, int i, SwimValue v) {
    SwimFrameSetRefAt(fr, i, v);
}
void SwimFrameReleasePtr(SwimFrame** f) {
    if (f && *f) { SwimRelease((SwimValue)*f); *f = NULL; }
}
SwimFrame* SwimFrameUp(SwimFrame* f, int levels) {
    while (levels-- > 0 && f) f = f->parent;
    return f;
}
void SwimGlobalsInit(int count) {
    if (swim_global_frame == NULL)
        swim_global_frame = SwimFrameNew(NULL, count + 4);
    SwimFrameObj* f = (SwimFrameObj*)swim_global_frame;
    for (int i = 0; i < count; i++) {
        if (i >= f->n) f->n = i + 1;
        if (i >= f->cap) {
            int nc = f->cap ? f->cap : 8;
            while (nc <= i) nc *= 2;
            f->slots = (SwimValue*)realloc(f->slots, (size_t)nc * sizeof(SwimValue));
            for (int k = f->cap; k < nc; k++) f->slots[k] = NULL;
            f->cap = nc;
        }
    }
}
SwimFrame* SwimGlobals(void) {
    if (swim_global_frame == NULL) SwimGlobalsInit(0);
    return swim_global_frame;
}
SwimValue SwimGlobalGet(int i) { return SwimFrameGet(SwimGlobals(), i); }
void SwimGlobalSet(int i, SwimValue v) { SwimFrameSet(SwimGlobals(), i, v); }
void SwimGlobalSetRef(int i, SwimValue v) { SwimFrameSetRefAt(SwimGlobals(), i, v); }

/* ================================================================== */
/* String builder                                                      */
/* ================================================================== */
void SwimBufInit(SwimBuf* b) { b->data = NULL; b->len = 0; b->cap = 0; }
static void swim_buf_grow(SwimBuf* b, int64_t need) {
    if (b->len + need + 1 <= b->cap) return;
    int64_t nc = b->cap ? b->cap : 32;
    while (nc < b->len + need + 1) nc *= 2;
    b->data = (char*)realloc(b->data, (size_t)nc);
    if (b->data == NULL) { fprintf(stderr, "swim: out of memory\n"); exit(1); }
    b->cap = nc;
}
void SwimBufAddBytes(SwimBuf* b, const char* s, int64_t n) {
    swim_buf_grow(b, n);
    if (n) memcpy(b->data + b->len, s, (size_t)n);
    b->len += n;
    b->data[b->len] = '\0';
}
void SwimBufAddCStr(SwimBuf* b, const char* s) {
    SwimBufAddBytes(b, s, (int64_t)strlen(s));
}
void SwimBufAddChar(SwimBuf* b, char c) { SwimBufAddBytes(b, &c, 1); }
void SwimBufFree(SwimBuf* b) { free(b->data); b->data = NULL; b->len = b->cap = 0; }
SwimValue SwimBufValue(SwimBuf* b) {
    SwimValue s = SwimString(b->data ? b->data : "", b->len);
    SwimBufFree(b);
    return s;
}

/* ================================================================== */
/* Double formatting (shortest round-trip, Nim-compatible)             */
/* ================================================================== */
static void swim_format_double(double v, SwimBuf* out) {
    if (isnan(v)) { SwimBufAddCStr(out, "nan"); return; }
    if (isinf(v)) { SwimBufAddCStr(out, v < 0 ? "-inf" : "inf"); return; }
    char tmp[64];
    int prec = 15;
    for (;;) {
        snprintf(tmp, sizeof(tmp), "%.*g", prec, v);
        double back = strtod(tmp, NULL);
        if (back == v || prec >= 17) break;
        prec++;
    }
    /* Nim always shows a decimal point or exponent for floats. */
    if (strpbrk(tmp, ".eE") == NULL) {
        size_t n = strlen(tmp);
        tmp[n] = '.'; tmp[n + 1] = '0'; tmp[n + 2] = '\0';
    }
    /* Normalise an exponent such as e+06 into e+06 (Nim keeps strtod style) */
    for (char* p = tmp; *p; p++) if (*p == 'E') *p = 'e';
    SwimBufAddCStr(out, tmp);
}

/* ================================================================== */
/* Description / printing                                              */
/* ================================================================== */
static SwimValue swim_prop_get(SwimType* t, const char* name) {
    for (int i = 0; i < t->prop_count; i++) {
        if (strcmp(t->props[i].name, name) == 0) return NULL; /* found */
    }
    return NULL;
}

void SwimDescribeWith(SwimValue v, SwimBuf* out, int depth) {
    static int guard = 0;
    v = SwimDeref(v);
    if (v == NULL) { SwimBufAddCStr(out, "nil"); return; }
    SwimType* t = v->type;
    /* user description property / CustomStringConvertible */
    for (int i = 0; i < t->prop_count; i++) {
        if (strcmp(t->props[i].name, "description") == 0 ||
            strcmp(t->props[i].name, "$") == 0) {
            if (t->props[i].getter && guard == 0) {
                guard++;
                SwimValue s = t->props[i].getter(NULL, 1, &v);
                guard--;
                SwimValue d = SwimDeref(s);
                if (d && d->type->kind == SWIM_KIND_STRING) {
                    SwimBufAddBytes(out, ((SwimStringObj*)d)->data,
                                    ((SwimStringObj*)d)->len);
                    SwimRelease(s);
                    return;
                }
                SwimRelease(s);
            }
        }
    }
    switch (t->kind) {
        case SWIM_KIND_VOID:
            break;
        case SWIM_KIND_INT: {
            char tmp[32];
            snprintf(tmp, sizeof(tmp), "%lld", (long long)((SwimIntObj*)v)->v);
            SwimBufAddCStr(out, tmp);
            break;
        }
        case SWIM_KIND_DOUBLE:
            swim_format_double(((SwimDoubleObj*)v)->v, out);
            break;
        case SWIM_KIND_BOOL:
            SwimBufAddCStr(out, ((SwimBoolObj*)v)->v ? "true" : "false");
            break;
        case SWIM_KIND_CHAR: {
            char c = (char)((SwimCharObj*)v)->v;
            SwimBufAddBytes(out, &c, 1);
            break;
        }
        case SWIM_KIND_STRING:
            SwimBufAddBytes(out, ((SwimStringObj*)v)->data,
                            ((SwimStringObj*)v)->len);
            break;
        case SWIM_KIND_ARRAY: {
            SwimArrayObj* a = (SwimArrayObj*)v;
            SwimBufAddChar(out, '[');
            for (int64_t i = 0; i < a->n; i++) {
                if (i) SwimBufAddCStr(out, ", ");
                SwimDescribeWith(a->items[i], out, depth + 1);
            }
            SwimBufAddChar(out, ']');
            break;
        }
        case SWIM_KIND_SET: {
            SwimSetObj* s = (SwimSetObj*)v;
            SwimBufAddCStr(out, "Set([");
            int first = 1;
            for (int64_t i = 0; i < s->n; i++) {
                if (s->items[i] == NULL) continue;
                if (!first) SwimBufAddCStr(out, ", ");
                first = 0;
                SwimDescribeWith(s->items[i], out, depth + 1);
            }
            SwimBufAddCStr(out, "])");
            break;
        }
        case SWIM_KIND_DICT: {
            SwimDictObj* d = (SwimDictObj*)v;
            SwimBufAddChar(out, '[');
            int first = 1;
            for (int64_t i = 0; i < d->n; i++) {
                if (d->entries[i].key == NULL) continue;
                if (!first) SwimBufAddCStr(out, ", ");
                first = 0;
                SwimDescribeWith(d->entries[i].key, out, depth + 1);
                SwimBufAddCStr(out, ": ");
                SwimDescribeWith(d->entries[i].value, out, depth + 1);
            }
            SwimBufAddChar(out, ']');
            break;
        }
        case SWIM_KIND_OPTIONAL: {
            SwimOptionalObj* o = (SwimOptionalObj*)v;
            if (!o->has) { SwimBufAddCStr(out, "nil"); break; }
            SwimBufAddCStr(out, "Optional(");
            SwimDescribeWith(o->value, out, depth + 1);
            SwimBufAddChar(out, ')');
            break;
        }
        case SWIM_KIND_TUPLE: {
            SwimTupleObj* tu = (SwimTupleObj*)v;
            SwimBufAddChar(out, '(');
            for (int64_t i = 0; i < tu->n; i++) {
                if (i) SwimBufAddCStr(out, ", ");
                SwimValue item = SwimDeref(tu->slots[i]);
                if (item && item->type->kind == SWIM_KIND_STRING) {
                    SwimBufAddChar(out, '"');
                    SwimBufAddBytes(out, ((SwimStringObj*)item)->data,
                                    ((SwimStringObj*)item)->len);
                    SwimBufAddChar(out, '"');
                } else {
                    SwimDescribeWith(item, out, depth + 1);
                }
            }
            SwimBufAddChar(out, ')');
            break;
        }
        case SWIM_KIND_RANGE: {
            SwimRangeObj* r = (SwimRangeObj*)v;
            SwimDescribeWith(r->lo, out, depth + 1);
            SwimBufAddCStr(out, r->closed ? "..." : "..<");
            SwimDescribeWith(r->hi, out, depth + 1);
            break;
        }
        case SWIM_KIND_STRUCT: {
            SwimObjectObj* o = (SwimObjectObj*)v;
            SwimBufAddCStr(out, t->name);
            if (o->n == 0) { SwimBufAddCStr(out, "()"); break; }
            SwimBufAddChar(out, '(');
            for (int64_t i = 0; i < o->n; i++) {
                if (i) SwimBufAddCStr(out, ", ");
                if (t->fields && i < t->field_count)
                    SwimBufAddCStr(out, t->fields[i].name);
                else
                    SwimBufAddCStr(out, "?");
                SwimBufAddCStr(out, ": ");
                {
                    const SwimFieldDesc* d =
                        (t->fields && i < t->field_count) ? &t->fields[i]
                                                          : NULL;
                    if (d != NULL && (d->weak || d->unowned)) {
                        SwimValue loaded = SwimWeakLoad(
                            o->slots[i], d->weak ? 1 : 0, d->optional ? 1 : 0);
                        SwimDescribeWith(loaded, out, depth + 1);
                        SwimRelease(loaded);
                    } else {
                        SwimDescribeWith(o->slots[i], out, depth + 1);
                    }
                }
            }
            SwimBufAddChar(out, ')');
            break;
        }
        case SWIM_KIND_ENUM: {
            SwimEnumObj* e = (SwimEnumObj*)v;
            const SwimCaseDesc* cd = NULL;
            if (t->cases && e->tag >= 0 && e->tag < t->case_count)
                cd = &t->cases[e->tag];
            SwimBufAddCStr(out, cd ? cd->name : "?");
            if (cd && cd->payload_count > 0) {
                SwimBufAddChar(out, '(');
                for (int i = 0; i < cd->payload_count; i++) {
                    if (i) SwimBufAddCStr(out, ", ");
                    SwimBufAddCStr(out, cd->payload[i].name);
                    SwimBufAddCStr(out, ": ");
                    SwimDescribeWith(e->slots[i], out, depth + 1);
                }
                SwimBufAddChar(out, ')');
            }
            break;
        }
        case SWIM_KIND_CLASS:
            SwimBufAddCStr(out, t->name);
            break;
        case SWIM_KIND_CLOSURE:
            SwimBufAddCStr(out, "closure");
            break;
        case SWIM_KIND_TYPE:
            SwimBufAddCStr(out, ((SwimTypeObj*)v)->target->name);
            break;
        default:
            SwimBufAddCStr(out, t->name);
            break;
    }
}

void SwimDescribe(SwimValue v, SwimBuf* out) { SwimDescribeWith(v, out, 0); }

SwimValue SwimStr(SwimValue v) {
    SwimBuf b;
    SwimBufInit(&b);
    SwimDescribe(v, &b);
    return SwimBufValue(&b);
}

void SwimPrintValues(int argc, SwimValue* argv, const char* sep,
                     const char* term) {
    for (int i = 0; i < argc; i++) {
        if (i && sep) fputs(sep, stdout);
        SwimValue s = SwimStr(argv[i]);
        fwrite(((SwimStringObj*)s)->data, 1, (size_t)((SwimStringObj*)s)->len,
               stdout);
        SwimRelease(s);
    }
    if (term) fputs(term, stdout);
    fflush(stdout);
}

SwimValue SwimConcat(int count, ...) {
    va_list ap;
    va_start(ap, count);
    SwimValue parts[64];
    int converted[64];
    int64_t total = 0;
    for (int i = 0; i < count && i < 64; i++) {
        parts[i] = va_arg(ap, SwimValue);
        converted[i] = 0;
        if (parts[i]) {
            SwimValue d = SwimDeref(parts[i]);
            if (d->type->kind == SWIM_KIND_STRING) {
                total += ((SwimStringObj*)d)->len;
            } else {
                parts[i] = SwimStr(parts[i]);
                converted[i] = 1;
                total += ((SwimStringObj*)parts[i])->len;
            }
        }
    }
    va_end(ap);
    char* buf = (char*)malloc((size_t)total + 1);
    int64_t at = 0;
    for (int i = 0; i < count && i < 64; i++) {
        if (!parts[i]) continue;
        SwimValue d = SwimDeref(parts[i]);
        int64_t n = ((SwimStringObj*)d)->len;
        memcpy(buf + at, ((SwimStringObj*)d)->data, (size_t)n);
        at += n;
        if (converted[i]) SwimRelease(parts[i]);
    }
    buf[at] = '\0';
    SwimValue s = SwimString(buf, at);
    free(buf);
    return s;
}

/* ================================================================== */
/* Numeric helpers                                                     */
/* ================================================================== */
int SwimIsNumeric(SwimValue v) {
    v = SwimDeref(v);
    return v && SwimIsNumericKind(v->type->kind);
}
int64_t SwimToInt(SwimValue v) {
    v = SwimDeref(v);
    if (v->type->kind == SWIM_KIND_INT) return ((SwimIntObj*)v)->v;
    if (v->type->kind == SWIM_KIND_DOUBLE) return (int64_t)((SwimDoubleObj*)v)->v;
    if (v->type->kind == SWIM_KIND_BOOL) return ((SwimBoolObj*)v)->v;
    if (v->type->kind == SWIM_KIND_CHAR) return ((SwimCharObj*)v)->v;
    SwimFatalFmt("expected a number, got %s", v->type->name);
}
double SwimToDouble(SwimValue v) {
    v = SwimDeref(v);
    if (v->type->kind == SWIM_KIND_DOUBLE) return ((SwimDoubleObj*)v)->v;
    if (v->type->kind == SWIM_KIND_INT) return (double)((SwimIntObj*)v)->v;
    SwimFatalFmt("expected a number, got %s", v->type->name);
}

/* ================================================================== */
/* Equality, ordering, hashing                                         */
/* ================================================================== */
static int swim_compare_classes(SwimValue a, SwimValue b);

int SwimCompareValues(SwimValue a, SwimValue b) { return SwimCompare(a, b); }

int SwimValuesEqual(SwimValue a, SwimValue b) {
    a = SwimDeref(a);
    b = SwimDeref(b);
    if (a == b) return 1;
    if (a == NULL || b == NULL) return 0;
    SwimKind ka = a->type->kind, kb = b->type->kind;
    if (ka == SWIM_KIND_INT && kb == SWIM_KIND_INT)
        return ((SwimIntObj*)a)->v == ((SwimIntObj*)b)->v;
    if ((ka == SWIM_KIND_INT || ka == SWIM_KIND_DOUBLE) &&
        (kb == SWIM_KIND_INT || kb == SWIM_KIND_DOUBLE))
        return SwimToDouble(a) == SwimToDouble(b);
    if ((ka == SWIM_KIND_CHAR && kb == SWIM_KIND_STRING) ||
        (ka == SWIM_KIND_STRING && kb == SWIM_KIND_CHAR)) {
        SwimKind ck = ka == SWIM_KIND_CHAR ? ka : kb;
        SwimValue cv = ka == SWIM_KIND_CHAR ? a : b;
        SwimValue sv = ka == SWIM_KIND_CHAR ? b : a;
        if (((SwimStringObj*)sv)->len == 1)
            return ((SwimCharObj*)cv)->v ==
                   (uint8_t)((SwimStringObj*)sv)->data[0];
        return 0;
    }
    if (ka != kb) return 0;
    switch (ka) {
        case SWIM_KIND_VOID: return 1;
        case SWIM_KIND_DOUBLE:
            return ((SwimDoubleObj*)a)->v == ((SwimDoubleObj*)b)->v;
        case SWIM_KIND_BOOL:
            return ((SwimBoolObj*)a)->v == ((SwimBoolObj*)b)->v;
        case SWIM_KIND_CHAR:
            return ((SwimCharObj*)a)->v == ((SwimCharObj*)b)->v;
        case SWIM_KIND_STRING: {
            SwimStringObj* sa = (SwimStringObj*)a;
            SwimStringObj* sb = (SwimStringObj*)b;
            return sa->len == sb->len &&
                   memcmp(sa->data, sb->data, (size_t)sa->len) == 0;
        }
        case SWIM_KIND_ARRAY: {
            SwimArrayObj* x = (SwimArrayObj*)a;
            SwimArrayObj* y = (SwimArrayObj*)b;
            if (x->n != y->n) return 0;
            for (int64_t i = 0; i < x->n; i++)
                if (!SwimValuesEqual(x->items[i], y->items[i])) return 0;
            return 1;
        }
        case SWIM_KIND_SET: {
            SwimSetObj* x = (SwimSetObj*)a;
            SwimSetObj* y = (SwimSetObj*)b;
            if (x->n != y->n) return 0;
            for (int64_t i = 0; i < x->n; i++) {
                if (x->items[i] == NULL) continue;
                if (!SwimUnboxBool(SwimSetLookup(b, x->items[i]))) return 0;
            }
            return 1;
        }
        case SWIM_KIND_DICT: {
            SwimDictObj* x = (SwimDictObj*)a;
            SwimDictObj* y = (SwimDictObj*)b;
            if (x->n != y->n) return 0;
            for (int64_t i = 0; i < x->n; i++) {
                if (x->entries[i].key == NULL) continue;
                SwimValue other = SwimDictLookup(b, x->entries[i].key);
                if (!SwimIsSome(other)) { SwimRelease(other); return 0; }
                int eq = SwimValuesEqual(x->entries[i].value, SwimOptionalGet(other));
                SwimRelease(other);
                if (!eq) return 0;
            }
            return 1;
        }
        case SWIM_KIND_OPTIONAL: {
            SwimOptionalObj* x = (SwimOptionalObj*)a;
            SwimOptionalObj* y = (SwimOptionalObj*)b;
            if (!x->has && !y->has) return 1;
            if (x->has != y->has) return 0;
            return SwimValuesEqual(x->value, y->value);
        }
        case SWIM_KIND_TUPLE: {
            SwimTupleObj* x = (SwimTupleObj*)a;
            SwimTupleObj* y = (SwimTupleObj*)b;
            if (x->n != y->n) return 0;
            for (int64_t i = 0; i < x->n; i++)
                if (!SwimValuesEqual(x->slots[i], y->slots[i])) return 0;
            return 1;
        }
        case SWIM_KIND_RANGE: {
            SwimRangeObj* x = (SwimRangeObj*)a;
            SwimRangeObj* y = (SwimRangeObj*)b;
            return x->closed == y->closed && SwimValuesEqual(x->lo, y->lo) &&
                   SwimValuesEqual(x->hi, y->hi);
        }
        case SWIM_KIND_STRUCT:
        case SWIM_KIND_ENUM: {
            if (a->type != b->type) return 0;
            if (ka == SWIM_KIND_ENUM) {
                SwimEnumObj* x = (SwimEnumObj*)a;
                SwimEnumObj* y = (SwimEnumObj*)b;
                if (x->tag != y->tag) return 0;
                for (int64_t i = 0; i < x->n; i++)
                    if (!SwimValuesEqual(x->slots[i], y->slots[i])) return 0;
                return 1;
            }
            SwimObjectObj* x = (SwimObjectObj*)a;
            SwimObjectObj* y = (SwimObjectObj*)b;
            if (x->n != y->n) return 0;
            for (int64_t i = 0; i < x->n; i++) {
                int idx = (int)i;
                if (a->type->fields && idx < a->type->field_count &&
                    (a->type->fields[idx].weak ||
                     a->type->fields[idx].unowned)) {
                    const SwimFieldDesc* d = &a->type->fields[idx];
                    SwimValue va = SwimWeakLoad(x->slots[i],
                                                d->weak ? 1 : 0, 1);
                    SwimValue vb = SwimWeakLoad(y->slots[i],
                                                d->weak ? 1 : 0, 1);
                    int eq = SwimValuesEqual(va, vb);
                    SwimRelease(va);
                    SwimRelease(vb);
                    if (!eq) return 0;
                    continue;
                }
                if (!SwimValuesEqual(x->slots[i], y->slots[i])) return 0;
            }
            return 1;
        }
        case SWIM_KIND_TYPE: {
            SwimTypeObj* x = (SwimTypeObj*)a;
            SwimTypeObj* y = (SwimTypeObj*)b;
            return x->target == y->target;
        }
        default:
            return 0;
    }
}

static int swim_compare_classes(SwimValue a, SwimValue b) {
    (void)a; (void)b;
    return 0;
}

int SwimCompare(SwimValue a, SwimValue b) {
    a = SwimDeref(a);
    b = SwimDeref(b);
    SwimKind ka = a ? a->type->kind : SWIM_KIND_VOID;
    SwimKind kb = b ? b->type->kind : SWIM_KIND_VOID;
    if (SwimIsNumericKind(ka) || SwimIsNumericKind(kb)) {
        double x = SwimToDouble(a), y = SwimToDouble(b);
        if (x < y) return -1;
        if (x > y) return 1;
        return 0;
    }
    if (ka != kb) return (int)ka - (int)kb;
    switch (ka) {
        case SWIM_KIND_STRING: {
            SwimStringObj* x = (SwimStringObj*)a;
            SwimStringObj* y = (SwimStringObj*)b;
            int64_t n = x->len < y->len ? x->len : y->len;
            int c = memcmp(x->data, y->data, (size_t)n);
            if (c) return c < 0 ? -1 : 1;
            return x->len == y->len ? 0 : (x->len < y->len ? -1 : 1);
        }
        case SWIM_KIND_CHAR: {
            uint8_t x = ((SwimCharObj*)a)->v, y = ((SwimCharObj*)b)->v;
            return x == y ? 0 : (x < y ? -1 : 1);
        }
        case SWIM_KIND_BOOL: {
            int x = ((SwimBoolObj*)a)->v, y = ((SwimBoolObj*)b)->v;
            return x == y ? 0 : (x < y ? -1 : 1);
        }
        case SWIM_KIND_ARRAY: {
            SwimArrayObj* x = (SwimArrayObj*)a;
            SwimArrayObj* y = (SwimArrayObj*)b;
            int64_t n = x->n < y->n ? x->n : y->n;
            for (int64_t i = 0; i < n; i++) {
                int c = SwimCompare(x->items[i], y->items[i]);
                if (c) return c;
            }
            return x->n == y->n ? 0 : (x->n < y->n ? -1 : 1);
        }
        case SWIM_KIND_TUPLE: {
            SwimTupleObj* x = (SwimTupleObj*)a;
            SwimTupleObj* y = (SwimTupleObj*)b;
            int64_t n = x->n < y->n ? x->n : y->n;
            for (int64_t i = 0; i < n; i++) {
                int c = SwimCompare(x->slots[i], y->slots[i]);
                if (c) return c;
            }
            return x->n == y->n ? 0 : (x->n < y->n ? -1 : 1);
        }
        case SWIM_KIND_ENUM: {
            SwimEnumObj* x = (SwimEnumObj*)a;
            SwimEnumObj* y = (SwimEnumObj*)b;
            if (x->tag != y->tag) return x->tag < y->tag ? -1 : 1;
            return 0;
        }
        case SWIM_KIND_DOUBLE:
            return ((SwimDoubleObj*)a)->v == ((SwimDoubleObj*)b)->v ? 0 :
                   (((SwimDoubleObj*)a)->v < ((SwimDoubleObj*)b)->v ? -1 : 1);
        case SWIM_KIND_INT: {
            int64_t x = ((SwimIntObj*)a)->v, y = ((SwimIntObj*)b)->v;
            return x == y ? 0 : (x < y ? -1 : 1);
        }
        default:
            return swim_compare_classes(a, b);
    }
}

static uint64_t swim_hash_bytes(const char* data, int64_t len) {
    uint64_t h = 1469598103934665603ULL;
    for (int64_t i = 0; i < len; i++) {
        h ^= (uint64_t)(uint8_t)data[i];
        h *= 1099511628211ULL;
    }
    return h;
}

int64_t SwimHash(SwimValue v) {
    v = SwimDeref(v);
    if (v == NULL) return 0;
    switch (v->type->kind) {
        case SWIM_KIND_INT: return (int64_t)((SwimIntObj*)v)->v;
        case SWIM_KIND_DOUBLE: {
            double d = ((SwimDoubleObj*)v)->v;
            if (d == (double)(int64_t)d) return (int64_t)d;
            uint64_t bits;
            memcpy(&bits, &d, sizeof(bits));
            return (int64_t)bits;
        }
        case SWIM_KIND_BOOL: return ((SwimBoolObj*)v)->v;
        case SWIM_KIND_CHAR: return ((SwimCharObj*)v)->v;
        case SWIM_KIND_STRING: {
            SwimStringObj* s = (SwimStringObj*)v;
            return (int64_t)swim_hash_bytes(s->data, s->len);
        }
        case SWIM_KIND_ARRAY: {
            SwimArrayObj* a = (SwimArrayObj*)v;
            uint64_t h = 0x9e3779b97f4a7c15ULL;
            for (int64_t i = 0; i < a->n; i++)
                h = h * 31 + (uint64_t)SwimHash(a->items[i]);
            return (int64_t)h;
        }
        case SWIM_KIND_SET: {
            SwimSetObj* s = (SwimSetObj*)v;
            uint64_t h = 0x9e3779b97f4a7c15ULL;
            for (int64_t i = 0; i < s->n; i++)
                if (s->items[i]) h ^= (uint64_t)SwimHash(s->items[i]);
            return (int64_t)h;
        }
        case SWIM_KIND_TUPLE: {
            SwimTupleObj* t = (SwimTupleObj*)v;
            uint64_t h = 0x9e3779b97f4a7c15ULL;
            for (int64_t i = 0; i < t->n; i++)
                h = h * 31 + (uint64_t)SwimHash(t->slots[i]);
            return (int64_t)h;
        }
        case SWIM_KIND_ENUM: {
            SwimEnumObj* e = (SwimEnumObj*)v;
            uint64_t h = (uint64_t)e->tag * 31 + 7;
            for (int64_t i = 0; i < e->n; i++)
                h = h * 31 + (uint64_t)SwimHash(e->slots[i]);
            return (int64_t)h;
        }
        case SWIM_KIND_STRUCT: {
            SwimObjectObj* o = (SwimObjectObj*)v;
            uint64_t h = 0x9e3779b97f4a7c15ULL;
            for (int64_t i = 0; i < o->n; i++)
                h = h * 31 + (uint64_t)SwimHash(o->slots[i]);
            return (int64_t)h;
        }
        case SWIM_KIND_OPTIONAL: {
            SwimOptionalObj* o = (SwimOptionalObj*)v;
            return o->has ? SwimHash(o->value) : 0;
        }
        case SWIM_KIND_CLASS:
            return (int64_t)(uintptr_t)v;
        default:
            return 0;
    }
}

/* ================================================================== */
/* Operators                                                           */
/* ================================================================== */
static int swim_is_string(SwimValue v) {
    v = SwimDeref(v);
    return v && v->type->kind == SWIM_KIND_STRING;
}

SwimValue SwimBinary(const char* op, SwimValue a, SwimValue b) {
    a = SwimDeref(a);
    b = SwimDeref(b);
    if (a && b) {
        SwimFn user = SwimFindOperator("infix", op, 2,
                                       (SwimValue[]){a, b});
        if (user) {
            SwimValue argv[2] = {a, b};
            return user(NULL, 2, argv);
        }
    }
    if (strcmp(op, "==") == 0) return SwimBool(SwimValuesEqual(a, b));
    if (strcmp(op, "!=") == 0) return SwimBool(!SwimValuesEqual(a, b));
    if (strcmp(op, "<") == 0) return SwimBool(SwimCompare(a, b) < 0);
    if (strcmp(op, "<=") == 0) return SwimBool(SwimCompare(a, b) <= 0);
    if (strcmp(op, ">") == 0) return SwimBool(SwimCompare(a, b) > 0);
    if (strcmp(op, ">=") == 0) return SwimBool(SwimCompare(a, b) >= 0);
    if (strcmp(op, "&&") == 0)
        return SwimBool(SwimUnboxBool(a) && SwimUnboxBool(b));
    if (strcmp(op, "||") == 0)
        return SwimBool(SwimUnboxBool(a) || SwimUnboxBool(b));
    if (strcmp(op, "+") == 0 && (swim_is_string(a) || swim_is_string(b))) {
        SwimValue parts[2] = {a, b};
        return SwimConcatValues(parts, 2);
    }
    if (strcmp(op, "+") == 0 && a && b &&
        a->type->kind == SWIM_KIND_ARRAY && b->type->kind == SWIM_KIND_ARRAY) {
        SwimArrayObj* x = (SwimArrayObj*)a;
        SwimArrayObj* y = (SwimArrayObj*)b;
        SwimValue out = SwimArrayNew(x->elem);
        for (int64_t i = 0; i < x->n; i++)
            SwimArrayAppendValue(out, x->items[i]);
        for (int64_t j = 0; j < y->n; j++)
            SwimArrayAppendValue(out, y->items[j]);
        return out;
    }
    int ai = a && a->type->kind == SWIM_KIND_INT;
    int bi = b && b->type->kind == SWIM_KIND_INT;
    if (ai && bi) {
        int64_t x = ((SwimIntObj*)a)->v, y = ((SwimIntObj*)b)->v;
        if (strcmp(op, "+") == 0) return SwimInt(x + y);
        if (strcmp(op, "-") == 0) return SwimInt(x - y);
        if (strcmp(op, "*") == 0) return SwimInt(x * y);
        if (strcmp(op, "/") == 0) {
            if (y == 0) SwimFatalFmt("division by zero");
            return SwimInt(x / y);
        }
        if (strcmp(op, "%") == 0) {
            if (y == 0) SwimFatalFmt("division by zero");
            return SwimInt(x % y);
        }
        if (strcmp(op, "&") == 0) return SwimInt(x & y);
        if (strcmp(op, "|") == 0) return SwimInt(x | y);
        if (strcmp(op, "^") == 0) return SwimInt(x ^ y);
        if (strcmp(op, "<<") == 0) return SwimInt(x << y);
        if (strcmp(op, ">>") == 0) return SwimInt(x >> y);
    }
    if ((a && a->type->kind == SWIM_KIND_DOUBLE) ||
        (b && b->type->kind == SWIM_KIND_DOUBLE) ||
        (SwimIsNumeric(a) && SwimIsNumeric(b))) {
        double x = SwimToDouble(a), y = SwimToDouble(b);
        if (strcmp(op, "+") == 0) return SwimDouble(x + y);
        if (strcmp(op, "-") == 0) return SwimDouble(x - y);
        if (strcmp(op, "*") == 0) return SwimDouble(x * y);
        if (strcmp(op, "/") == 0) return SwimDouble(x / y);
        if (strcmp(op, "%") == 0) return SwimDouble(fmod(x, y));
    }
    SwimFatalFmt("unsupported operator '%s'", op);
}

SwimValue SwimUnary(const char* op, SwimValue a) {
    a = SwimDeref(a);
    if (strcmp(op, "!") == 0) return SwimBool(!SwimUnboxBool(a));
    if (strcmp(op, "-") == 0) {
        if (a->type->kind == SWIM_KIND_INT)
            return SwimInt(-((SwimIntObj*)a)->v);
        if (a->type->kind == SWIM_KIND_DOUBLE)
            return SwimDouble(-((SwimDoubleObj*)a)->v);
    }
    if (strcmp(op, "+") == 0) return a;
    SwimFn user = SwimFindOperator("prefix", op, 1, &a);
    if (user) return user(NULL, 1, &a);
    user = SwimFindOperator("postfix", op, 1, &a);
    if (user) return user(NULL, 1, &a);
    SwimFatalFmt("unsupported unary operator '%s'", op);
}

/* ================================================================== */
/* Optionals                                                           */
/* ================================================================== */
static SwimOptionalObj* swim_make_optional(int has, SwimValue v) {
    SwimOptionalObj* o =
        (SwimOptionalObj*)swim_alloc(&SwimType_Optional, sizeof(SwimOptionalObj));
    o->h.type = &SwimType_Optional;
    o->has = has;
    o->value = has ? v : NULL;
    return o;
}
SwimValue SwimSome(SwimValue v) {
    if (v == NULL) v = SwimVoid();
    SwimRetain(v);
    return (SwimValue)swim_make_optional(1, v);
}
SwimValue SwimNone(void) {
    static SwimValue none = NULL;
    if (none == NULL) none = (SwimValue)swim_make_optional(0, NULL);
    SwimRetain(none);
    return none;
}
int SwimIsSome(SwimValue opt) {
    opt = SwimDeref(opt);
    if (!opt) return 0;
    if (opt->type->kind != SWIM_KIND_OPTIONAL) return 1;
    return ((SwimOptionalObj*)opt)->has;
}
SwimValue SwimOptionalGet(SwimValue opt) {
    opt = SwimDeref(opt);
    if (!opt) return NULL;
    if (opt->type->kind != SWIM_KIND_OPTIONAL) return opt;
    SwimOptionalObj* o = (SwimOptionalObj*)opt;
    if (!o->has) SwimFatalFmt("Can't obtain a value from a `none`");
    return o->value;
}
SwimValue SwimUnwrap(SwimValue opt) {
    SwimValue v = SwimOptionalGet(opt);
    SwimRetain(v);
    return v;
}
SwimValue SwimCoalesce(SwimValue opt, SwimValue fallback) {
    opt = SwimDeref(opt);
    if (opt && opt->type->kind == SWIM_KIND_OPTIONAL) {
        SwimOptionalObj* o = (SwimOptionalObj*)opt;
        SwimValue r = o->has ? o->value : fallback;
        SwimRetain(r);
        return r;
    }
    SwimRetain(opt);
    return opt;
}

/* ================================================================== */
/* Coercion and casts                                                  */
/* ================================================================== */
SwimValue SwimCoerce(SwimValue v, const SwimType* t) {
    if (v == NULL) return NULL;
    if (t == NULL || t == &SwimType_Any || t == &SwimType_Generic) {
        return v;
    }
    v = SwimDeref(v);
    switch (t->kind) {
        case SWIM_KIND_INT:
            if (v->type->kind == SWIM_KIND_DOUBLE)
                return SwimInt((int64_t)((SwimDoubleObj*)v)->v);
            return v;
        case SWIM_KIND_DOUBLE:
            if (v->type->kind == SWIM_KIND_INT)
                return SwimDouble((double)((SwimIntObj*)v)->v);
            return v;
        case SWIM_KIND_BOOL:
            return v;
        case SWIM_KIND_CHAR:
            if (v->type->kind == SWIM_KIND_STRING) {
                SwimStringObj* s = (SwimStringObj*)v;
                if (s->len >= 1) return SwimChar((uint8_t)s->data[0]);
            }
            return v;
        case SWIM_KIND_STRING:
            return v;
        case SWIM_KIND_OPTIONAL: {
            if (v->type->kind == SWIM_KIND_OPTIONAL) return v;
            SwimValue inner = SwimCoerce(v, t->elem);
            SwimRetain(inner);
            return (SwimValue)swim_make_optional(1, inner);
        }
        case SWIM_KIND_ARRAY:
            if (v->type->kind == SWIM_KIND_ARRAY) {
                SwimArrayObj* a = (SwimArrayObj*)v;
                if (t->elem) a->elem = (SwimType*)t->elem;
                return v;
            }
            if (v->type->kind == SWIM_KIND_SET) {
                SwimSetObj* s = (SwimSetObj*)v;
                SwimValue out = SwimArrayNew(t->elem);
                for (int64_t i = 0; i < s->n; i++)
                    if (s->items[i]) SwimArrayAppendValue(out, s->items[i]);
                return out;
            }
            return v;
        case SWIM_KIND_TUPLE: {
            if (v->type->kind != SWIM_KIND_TUPLE) return v;
            if (t->field_count > 0) {
                SwimTupleObj* tu = (SwimTupleObj*)v;
                v->type = (SwimType*)t;
                for (int64_t i = 0; i < tu->n; i++) {
                    if (i < t->field_count && t->fields && tu->slots[i]) {
                        SwimValue cv = SwimCoerce(tu->slots[i],
                                                  t->fields[i].type);
                        if (cv != tu->slots[i]) {
                            SwimRelease(tu->slots[i]);
                            tu->slots[i] = cv;
                        }
                    }
                }
            }
            return v;
        }
        case SWIM_KIND_DICT:
            if (v->type->kind == SWIM_KIND_DICT) {
                SwimDictObj* d = (SwimDictObj*)v;
                if (t->key) d->key_type = (SwimType*)t->key;
                if (t->value) d->value_type = (SwimType*)t->value;
                return v;
            }
            return v;
        case SWIM_KIND_SET:
            if (v->type->kind == SWIM_KIND_SET) {
                SwimSetObj* s = (SwimSetObj*)v;
                if (t->elem) s->elem = (SwimType*)t->elem;
                return v;
            }
            if (v->type->kind == SWIM_KIND_ARRAY) {
                SwimArrayObj* a = (SwimArrayObj*)v;
                SwimValue out = SwimSetNew(t->elem);
                for (int64_t i = 0; i < a->n; i++)
                    SwimSetAdd(out, a->items[i]);
                return out;
            }
            return v;
        default:
            return v;
    }
}

static int swim_type_matches(SwimValue v, SwimType* t) {
    v = SwimDeref(v);
    if (!v) return 0;
    if (v->type == t) return 1;
    if (!t) return 1;
    if (t->kind == SWIM_KIND_ANY) return 1;
    SwimType* cur = v->type;
    if (v->type->kind == SWIM_KIND_CLASS) {
        cur = v->type;
        while (cur) {
            if (cur == t) return 1;
            cur = (SwimType*)cur->parent;
        }
        return 0;
    }
    if (v->type->kind == SWIM_KIND_OPTIONAL) {
        SwimOptionalObj* o = (SwimOptionalObj*)v;
        if (!o->has) return t->kind == SWIM_KIND_OPTIONAL;
        return swim_type_matches(o->value, t);
    }
    if (t->kind == SWIM_KIND_STRUCT || t->kind == SWIM_KIND_ENUM)
        return v->type == t;
    if (t->kind == SWIM_KIND_STRING) return v->type->kind == SWIM_KIND_STRING;
    if (t->kind == SWIM_KIND_INT) return v->type->kind == SWIM_KIND_INT;
    if (t->kind == SWIM_KIND_DOUBLE) return v->type->kind == SWIM_KIND_DOUBLE;
    if (t->kind == SWIM_KIND_BOOL) return v->type->kind == SWIM_KIND_BOOL;
    if (t->kind == SWIM_KIND_CHAR) return v->type->kind == SWIM_KIND_CHAR;
    if (t->kind == SWIM_KIND_ARRAY) return v->type->kind == SWIM_KIND_ARRAY;
    if (t->kind == SWIM_KIND_DICT) return v->type->kind == SWIM_KIND_DICT;
    if (t->kind == SWIM_KIND_SET) return v->type->kind == SWIM_KIND_SET;
    if (t->kind == SWIM_KIND_OPTIONAL) return v->type->kind == SWIM_KIND_OPTIONAL;
    return v->type == t;
}

SwimValue SwimCoerceOwned(SwimValue v, const SwimType* t) {
    SwimValue out = SwimCoerce(v, t);
    if (out == v) SwimRetain(out);
    return out;
}

SwimValue SwimCast(SwimValue v, const SwimType* t, int mode) {
    v = SwimDeref(v);
    int ok = swim_type_matches(v, (SwimType*)t);
    if (mode == 0) return SwimBool(ok);        /* is */
    if (!ok) {
        if (mode == 2) SwimFatalFmt("could not cast value of type '%s' to '%s'",
                                    v ? v->type->name : "nil", t->name);
        return SwimNone();
    }
    if (mode == 2) { SwimRetain(v); return v; }
    SwimRetain(v);
    return SwimSome(v);
}

/* ================================================================== */
/* Weak / unowned references and class deinitializers                  */
/* ================================================================== */
SwimValue SwimWeakMake(SwimValue v, int unowned) {
    SwimValue target = v;
    if (target != NULL) {
        target = SwimDeref(target);
        if (target != NULL && target->type->kind == SWIM_KIND_OPTIONAL) {
            SwimOptionalObj* o = (SwimOptionalObj*)target;
            target = o->has ? o->value : NULL;
        }
    }
    SwimWeakObj* w = (SwimWeakObj*)swim_alloc(&SwimType_Any,
                                              sizeof(SwimWeakObj));
    w->h.type = &SwimType_Weak;
    w->target = target;
    w->unowned = unowned;
    w->node.slot = &w->target;
    w->node.next = NULL;
    if (target != NULL) {
        w->node.next = target->weak_head;
        target->weak_head = &w->node;
    }
    return (SwimValue)w;
}

SwimValue SwimWeakLoad(SwimValue holder, int weak, int optional) {
    if (holder == NULL)
        return optional || weak ? SwimNone() : NULL;
    holder = SwimDeref(holder);
    if (holder == NULL)
        return optional || weak ? SwimNone() : NULL;
    if (holder->type->kind == SWIM_KIND_OPTIONAL) {
        SwimOptionalObj* o = (SwimOptionalObj*)holder;
        if (!o->has)
            return optional || weak ? SwimNone() : NULL;
        holder = o->value;
    }
    if (holder == NULL)
        return optional || weak ? SwimNone() : NULL;
    if (holder->type->kind != SWIM_KIND_WEAK) {
        if (weak || optional) return SwimSome(holder);
        SwimRetain(holder);
        return holder;
    }
    SwimWeakObj* w = (SwimWeakObj*)holder;
    if (w->target == NULL) {
        if (!weak && !optional)
            SwimFatalFmt("unowned reference was deallocated");
        return SwimNone();
    }
    if (weak || optional) return SwimSome(w->target);
    SwimRetain(w->target);
    return w->target;
}

void SwimRegisterDeinit(SwimType* t, SwimFn fn) { t->deinit = fn; }

/* ================================================================== */
/* Fatal helpers                                                       */
/* ================================================================== */
void SwimFatalFmt(const char* fmt, ...) {
    fflush(stdout);
    if (getenv("SWIM_TRACE")) {
        void* frames[32];
        int n = backtrace(frames, 32);
        backtrace_symbols_fd(frames, n, 2);
    }
    va_list ap;
    va_start(ap, fmt);
    fputs("Error: unhandled exception: ", stderr);
    vfprintf(stderr, fmt, ap);
    fputc('\n', stderr);
    va_end(ap);
    exit(1);
}

SwimValue SwimFatal(const char* msg) {
    SwimFatalFmt("%s", msg);
}
void SwimFatalV(SwimValue msg) {
    SwimValue s = SwimStr(msg);
    fflush(stdout);
    fputs("Error: unhandled exception: ", stderr);
    fwrite(((SwimStringObj*)s)->data, 1, (size_t)((SwimStringObj*)s)->len,
           stderr);
    fputc('\n', stderr);
    exit(1);
}
SwimValue SwimExit(int64_t code) {
    fflush(stdout);
    exit((int)code);
}

/* ================================================================== */
/* Pattern matching helpers (public)                                   */
/* ================================================================== */
SwimValue SwimEqualsValue(SwimValue a, SwimValue b) {
    return SwimBool(SwimValuesEqual(a, b));
}
static int swim_enum_tag(SwimValue e, const char* case_name) {
    e = SwimDeref(e);
    if (e == NULL || e->type->kind != SWIM_KIND_ENUM) return -1;
    SwimType* t = e->type;
    for (int i = 0; i < t->case_count; i++)
        if (strcmp(t->cases[i].name, case_name) == 0) return i;
    return -1;
}
SwimValue SwimEnumIs(SwimValue e, const char* case_name) {
    e = SwimDeref(e);
    if (e != NULL && e->type->kind == SWIM_KIND_OPTIONAL) {
        SwimOptionalObj* o = (SwimOptionalObj*)e;
        if (strcmp(case_name, "some") == 0) return SwimBool(o->has);
        if (strcmp(case_name, "none") == 0) return SwimBool(!o->has);
        return SwimBool(false);
    }
    if (e == NULL || e->type->kind != SWIM_KIND_ENUM) return SwimBool(false);
    int tag = swim_enum_tag(e, case_name);
    return SwimBool(tag >= 0 && ((SwimEnumObj*)e)->tag == tag);
}
SwimValue SwimEnumPayload(SwimValue e, const char* case_name, int index) {
    e = SwimDeref(e);
    if (e != NULL && e->type->kind == SWIM_KIND_OPTIONAL) {
        SwimOptionalObj* o = (SwimOptionalObj*)e;
        if (strcmp(case_name, "some") == 0 && o->has && index == 0) {
            SwimRetain(o->value);
            return o->value;
        }
        return SwimNone();
    }
    if (e == NULL || e->type->kind != SWIM_KIND_ENUM) return SwimNone();
    int tag = swim_enum_tag(e, case_name);
    if (tag < 0 || ((SwimEnumObj*)e)->tag != tag) return SwimNone();
    SwimEnumObj* eo = (SwimEnumObj*)e;
    if (index < 0 || index >= eo->n) return SwimNone();
    SwimValue v = eo->slots[index];
    if (v) SwimRetain(v);
    return v;
}
SwimValue SwimEnumPayloadNamed(SwimValue e, const char* case_name,
                               const char* field) {
    e = SwimDeref(e);
    if (e == NULL || e->type->kind != SWIM_KIND_ENUM) return SwimNone();
    SwimType* t = e->type;
    int tag = swim_enum_tag(e, case_name);
    if (tag < 0) return SwimNone();
    const SwimCaseDesc* cd = &t->cases[tag];
    for (int i = 0; i < cd->payload_count; i++) {
        if (strcmp(cd->payload[i].name, field) == 0)
            return SwimEnumPayload(e, case_name, i);
    }
    return SwimNone();
}
SwimValue SwimIsType(SwimValue v, SwimType* t) {
    v = SwimDeref(v);
    if (!v) return SwimBool(false);
    SwimType* cur = v->type;
    while (cur) {
        if (cur == t) return SwimBool(true);
        cur = (SwimType*)cur->parent;
    }
    return SwimBool(false);
}
