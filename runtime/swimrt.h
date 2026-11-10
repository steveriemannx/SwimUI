/* swimrt.h -- the Swim language runtime (direct C backend).
 *
 * Memory model: Swift-style automatic reference counting (ARC).  Every heap
 * object starts with an atomically updated reference count (`SwimObj.rc`).
 * Reference types (classes, closures, frames) are shared by retaining them;
 * value types (strings, arrays, dictionaries, sets, tuples, structs, enums,
 * optionals, ranges) are copied on store so the language keeps Swift value
 * semantics.  There is no tracing garbage collector and no cycle collector.
 */
#ifndef SWIMRT_H
#define SWIMRT_H

#include <stdint.h>
#include <stdbool.h>
#include <stddef.h>

#ifdef __cplusplus
extern "C" {
#endif

typedef struct SwimObj SwimObj;
typedef struct SwimType SwimType;
typedef struct SwimFrameObj SwimFrame;
typedef struct SwimIterator SwimIterator;
typedef SwimObj* SwimValue;

/* A generated function or closure body. */
typedef SwimValue (*SwimFn)(SwimFrame* up, int argc, SwimValue* argv);
/* Computes default arguments for a call; see runtime dispatch. */
typedef void (*SwimDefaultFn)(SwimFrame* up, int argc, SwimValue* argv,
                              const int* provided, SwimValue* out);

typedef enum SwimKind {
    SWIM_KIND_VOID = 0,
    SWIM_KIND_INT,
    SWIM_KIND_DOUBLE,
    SWIM_KIND_BOOL,
    SWIM_KIND_CHAR,
    SWIM_KIND_STRING,
    SWIM_KIND_ARRAY,
    SWIM_KIND_DICT,
    SWIM_KIND_SET,
    SWIM_KIND_OPTIONAL,
    SWIM_KIND_TUPLE,
    SWIM_KIND_STRUCT,
    SWIM_KIND_CLASS,
    SWIM_KIND_ENUM,
    SWIM_KIND_CLOSURE,
    SWIM_KIND_RANGE,
    SWIM_KIND_FRAME,
    SWIM_KIND_TYPE,
    SWIM_KIND_ANY,
    SWIM_KIND_WEAK,
    SWIM_KIND_PROXY
} SwimKind;

typedef struct SwimFieldDesc {
    const char* name;
    const SwimType* type;
    int weak;       /* stored as a zeroing weak reference */
    int unowned;    /* stored as a non-owning (trapping) reference */
    int optional;   /* declared as Optional<Class> */
} SwimFieldDesc;

typedef struct SwimCaseDesc {
    const char* name;
    int payload_count;
    const SwimFieldDesc* payload;
} SwimCaseDesc;

typedef struct SwimMethodEntry {
    const char* name;
    const char* labels;            /* comma separated, "_" = unlabeled */
    const SwimType* const* params;
    int nparams;
    SwimFn fn;
    SwimDefaultFn defaults;        /* NULL when every parameter is required */
    int variadic;                  /* -1 or index of the variadic parameter */
    int mutating;                  /* mutating method on a value type */
    int is_static;
    int has_self;
    int failable;
} SwimMethodEntry;

typedef struct SwimPropDesc {
    const char* name;
    SwimFn getter;                 /* fn(self=obj) -> value */
    SwimFn setter;                 /* fn(self=obj, argc=1, argv={value}) */
} SwimPropDesc;

struct SwimType {
    const char* name;
    SwimKind kind;
    const SwimType* parent;        /* superclass */
    const SwimType* elem;          /* array/set element, optional wrapped */
    const SwimType* key;           /* dictionary key */
    const SwimType* value;         /* dictionary value */
    int field_count;
    const SwimFieldDesc* fields;
    int case_count;
    const SwimCaseDesc* cases;
    int is_error;
    int is_protocol;
    int is_generic;
    /* filled in by the generated program registration */
    int method_count, method_cap;
    SwimMethodEntry* methods;
    int static_count, static_cap;
    SwimMethodEntry* statics;
    int prop_count, prop_cap;
    SwimPropDesc* props;
    int static_prop_count, static_prop_cap;
    SwimPropDesc* static_props;
    int raw_count, raw_cap;
    SwimValue* raws;
    /* ARC: optional class deinitializer (inherited ones run first). */
    struct SwimObj* (*deinit)(SwimFrame* up, int argc, SwimValue* argv);
};

typedef struct SwimWeakRef {
    struct SwimWeakRef* next;
    SwimValue* slot;
} SwimWeakRef;

struct SwimObj {
    _Atomic int64_t rc;
    SwimType* type;
    SwimWeakRef* weak_head;
    int destroying;
};

/* Object layout shared with the runtime implementation. */
typedef struct SwimIntObj { SwimObj h; int64_t v; } SwimIntObj;
typedef struct SwimDoubleObj { SwimObj h; double v; } SwimDoubleObj;
typedef struct SwimBoolObj { SwimObj h; int v; } SwimBoolObj;
typedef struct SwimCharObj { SwimObj h; uint8_t v; } SwimCharObj;
typedef struct SwimStringObj { SwimObj h; int64_t len; char* data; } SwimStringObj;
typedef struct SwimArrayObj {
    SwimObj h;
    int64_t n, cap;
    SwimValue* items;
    SwimType* elem;
} SwimArrayObj;
typedef struct SwimDictEntry {
    SwimValue key;                 /* NULL marks a deleted slot */
    SwimValue value;
} SwimDictEntry;
typedef struct SwimDictObj {
    SwimObj h;
    int64_t n, cap;
    SwimDictEntry* entries;
    SwimType* key_type;
    SwimType* value_type;
} SwimDictObj;
typedef struct SwimSetObj {
    SwimObj h;
    int64_t n, cap;
    SwimValue* items;
    SwimType* elem;
} SwimSetObj;
typedef struct SwimOptionalObj { SwimObj h; int has; SwimValue value; } SwimOptionalObj;
typedef struct SwimTupleObj { SwimObj h; int64_t n; SwimValue* slots; } SwimTupleObj;
typedef struct SwimObjectObj { SwimObj h; int64_t n; SwimValue* slots; } SwimObjectObj;
typedef struct SwimEnumObj {
    SwimObj h;
    int64_t tag;
    int64_t n;
    SwimValue* slots;
} SwimEnumObj;
typedef struct SwimClosureObj {
    SwimObj h;
    SwimFn fn;
    SwimFrame* env;
} SwimClosureObj;
typedef struct SwimRangeObj {
    SwimObj h;
    SwimValue lo, hi;
    int closed;
} SwimRangeObj;
typedef struct SwimFrameObj {
    SwimObj h;
    int64_t n, cap;
    SwimValue* slots;
    SwimFrame* parent;
} SwimFrameObj;
typedef struct SwimTypeObj { SwimObj h; SwimType* target; } SwimTypeObj;
typedef struct SwimProxyObj {
    SwimObj h;
    SwimValue target;
    const char* member;
} SwimProxyObj;
typedef struct SwimWeakObj {
    SwimObj h;
    SwimValue target;      /* non-owning */
    SwimWeakRef node;      /* intrusive link in the target's weak list */
    int unowned;
} SwimWeakObj;

/* ------------------------------------------------------------------ */
/* Primitive constructors and accessors                                */
/* ------------------------------------------------------------------ */
extern SwimType SwimType_Void;
extern SwimType SwimType_Int;
extern SwimType SwimType_Double;
extern SwimType SwimType_Bool;
extern SwimType SwimType_Char;
extern SwimType SwimType_String;
extern SwimType SwimType_Array;
extern SwimType SwimType_Dict;
extern SwimType SwimType_Set;
extern SwimType SwimType_Optional;
extern SwimType SwimType_Tuple;
extern SwimType SwimType_Range;
extern SwimType SwimType_Closure;
extern SwimType SwimType_Any;
extern SwimType SwimType_Int8;
extern SwimType SwimType_Int16;
extern SwimType SwimType_Int32;
extern SwimType SwimType_Int64;
extern SwimType SwimType_UInt;
extern SwimType SwimType_UInt8;
extern SwimType SwimType_UInt16;
extern SwimType SwimType_UInt32;
extern SwimType SwimType_UInt64;
extern SwimType SwimType_Float32;
extern SwimType SwimType_Generic;
extern SwimType SwimType_Frame;
extern SwimType SwimType_Meta;
extern SwimType SwimType_Weak;
extern SwimType SwimType_KeyValue;

#define SWIM_TEMP(v) SwimValue v __attribute__((cleanup(SwimReleasePtr))) = NULL
#define SWIM_FRAME_TEMP(v) SwimFrame* v __attribute__((cleanup(SwimFrameReleasePtr))) = NULL
#define SWIM_DEFFERRUN(s) SwimDeferScope s __attribute__((cleanup(SwimDeferScopeCleanup)))
#define SWIM_ITER_TEMP(v) SwimIterator* v __attribute__((cleanup(SwimIterFreePtr))) = NULL

SwimValue SwimVoid(void);
SwimValue SwimRetainResult(SwimValue v);
int SwimTruthy(SwimValue v);
SwimValue SwimTupleGet(SwimValue t, int idx);
SwimValue SwimGetFieldRaw(SwimValue obj, const char* name);
void SwimInitField(SwimValue obj, const char* name, SwimValue v);
void SwimIterFreePtr(SwimIterator** it);
void SwimFrameReleasePtr(SwimFrame** f);
SwimValue SwimInt(int64_t v);
SwimValue SwimDouble(double v);
SwimValue SwimBool(bool v);
SwimValue SwimChar(uint8_t v);
SwimValue SwimString(const char* bytes, int64_t len);
SwimValue SwimCStr(const char* s);
SwimValue SwimTypeValue(SwimType* t);

int64_t SwimUnboxInt(SwimValue v);
double SwimUnboxDouble(SwimValue v);
bool SwimUnboxBool(SwimValue v);
uint8_t SwimUnboxChar(SwimValue v);
const char* SwimStringData(SwimValue v);
int64_t SwimStringLen(SwimValue v);

/* ------------------------------------------------------------------ */
/* ARC                                                                  */
/* ------------------------------------------------------------------ */
void SwimRetain(SwimValue v);
void SwimRelease(SwimValue v);
void SwimReleasePtr(SwimValue* slot);
/* Deep copy for value semantics (classes/closures are retained instead). */
SwimValue SwimCopy(SwimValue v);
/* Store into a slot: releases the old value and applies value semantics. */
void SwimStore(SwimValue* slot, SwimValue v);
/* Store a reference without copying (method `self`, inout cells). */
void SwimStoreRef(SwimValue* slot, SwimValue v);
/* Unwrap proxies (observers) to the underlying value. */
SwimValue SwimUnwrapProxy(SwimValue v);

/* ------------------------------------------------------------------ */
/* Weak / unowned references and class deinitializers                   */
/* ------------------------------------------------------------------ */
/* Wrap a strong value (or Optional of one) into a weak/unowned holder.
 * ``unowned`` holders trap on access after the target was deallocated. */
SwimValue SwimWeakMake(SwimValue v, int unowned);
/* Load the referent: weak -> Optional<T>, unowned -> T (or Optional<T>
 * when the property was declared optional). */
SwimValue SwimWeakLoad(SwimValue holder, int weak, int optional);
void SwimRegisterDeinit(SwimType* t, SwimFn fn);

/* ------------------------------------------------------------------ */
/* Frames (activation records / closures' environments)                 */
/* ------------------------------------------------------------------ */
SwimFrame* SwimFrameNew(SwimFrame* parent, int cap);
SwimValue SwimFrameGet(SwimFrame* f, int i);
void SwimFrameSet(SwimFrame* f, int i, SwimValue v);
void SwimFrameSetRef(SwimFrame* f, int i, SwimValue v);
SwimFrame* SwimFrameUp(SwimFrame* f, int levels);
/* Borrowed (non-retaining) slot read, used for receiver expressions. */
SwimValue SwimFramePeek(SwimFrame* f, int i);
SwimFrame* SwimGlobals(void);
void SwimGlobalsInit(int count);
SwimValue SwimGlobalGet(int i);
void SwimGlobalSet(int i, SwimValue v);
void SwimGlobalSetRef(int i, SwimValue v);

/* ------------------------------------------------------------------ */
/* Descriptions / printing                                              */
/* ------------------------------------------------------------------ */
SwimValue SwimStr(SwimValue v);
void SwimPrintValues(int argc, SwimValue* argv, const char* sep,
                     const char* term);
SwimValue SwimConcat(int count, ...);
SwimValue SwimFatal(const char* msg);            /* does not return */
void SwimFatalV(SwimValue msg) __attribute__((noreturn));
SwimValue SwimExit(int64_t code);

/* ------------------------------------------------------------------ */
/* Operators and conversions                                            */
/* ------------------------------------------------------------------ */
SwimValue SwimBinary(const char* op, SwimValue a, SwimValue b);
SwimValue SwimUnary(const char* op, SwimValue a);
SwimValue SwimEqualsValue(SwimValue a, SwimValue b);
int SwimValuesEqual(SwimValue a, SwimValue b);
int SwimCompareValues(SwimValue a, SwimValue b);
SwimValue SwimCoerce(SwimValue v, const SwimType* t);
/* Like SwimCoerce, but always returns a reference the caller owns. */
SwimValue SwimCoerceOwned(SwimValue v, const SwimType* t);
SwimValue SwimConvert(SwimType* t, int argc, SwimValue* argv);
SwimValue SwimCast(SwimValue v, const SwimType* t, int mode);
SwimValue SwimUnwrap(SwimValue opt);
SwimValue SwimCoalesce(SwimValue opt, SwimValue fallback);
SwimValue SwimSome(SwimValue v);
SwimValue SwimNone(void);
int SwimIsSome(SwimValue opt);
SwimValue SwimOptionalGet(SwimValue opt);

/* ------------------------------------------------------------------ */
/* Collections                                                          */
/* ------------------------------------------------------------------ */
SwimValue SwimArrayNew(const SwimType* elem);
SwimValue SwimArrayFrom(int n, SwimValue* items, const SwimType* elem);
void SwimArrayAppendValue(SwimValue arr, SwimValue v);
SwimValue SwimDictNew(const SwimType* key, const SwimType* value);
SwimValue SwimDictFrom(int n, SwimValue* keys, SwimValue* values,
                       const SwimType* key, const SwimType* value);
SwimValue SwimSetNew(const SwimType* elem);
SwimValue SwimSetFrom(int n, SwimValue* items, const SwimType* elem);
SwimValue SwimArrayInit(SwimType* elem, int argc, SwimValue* argv);
SwimValue SwimTupleFrom(int n, SwimValue* items);
SwimValue SwimEnumFrom(SwimType* t, const char* case_name, int argc,
                       SwimValue* argv);
SwimValue SwimRangeFrom(SwimValue lo, SwimValue hi, int closed);

/* Iteration: `while (SwimIterNext(it, &v)) { ... }`. */
SwimIterator* SwimIterate(SwimValue v);
int SwimIterNext(SwimIterator* it, SwimValue* out);
void SwimIterFree(SwimIterator* it);

/* ------------------------------------------------------------------ */
/* Calls, members, dispatch                                             */
/* ------------------------------------------------------------------ */
SwimValue SwimGetMember(SwimValue obj, const char* name);
void SwimSetMember(SwimValue obj, const char* name, SwimValue v);
SwimValue SwimGetStatic(SwimType* t, const char* name);
void SwimSetStatic(SwimType* t, const char* name, SwimValue v);
SwimValue SwimSubscriptGet(SwimValue obj, int argc, SwimValue* argv);
void SwimSubscriptSet(SwimValue obj, int argc, SwimValue* argv, SwimValue v);
SwimValue SwimCallMethod(SwimValue obj, const char* name, const char* labels,
                         int argc, SwimValue* argv);
SwimValue SwimCallMethodFrom(SwimValue obj, SwimType* start,
                             const char* name, const char* labels, int argc,
                             SwimValue* argv);
SwimValue SwimCallGlobal(const char* name, const char* labels, int argc,
                         SwimValue* argv);
SwimValue SwimCallValue(SwimValue fn, int argc, SwimValue* argv);
SwimValue SwimCallStatic(SwimType* t, const char* name, const char* labels,
                         int argc, SwimValue* argv);
SwimValue SwimConstruct(SwimType* t, const char* labels, int argc,
                        SwimValue* argv);
SwimValue SwimConstructOpt(SwimType* t, const char* labels, int argc,
                           SwimValue* argv);
SwimValue SwimAllocObject(SwimType* t);
SwimValue SwimEnumRaw(SwimType* t, const char* labels, int argc,
                      SwimValue* argv);
SwimValue SwimEnumCase(SwimType* t, const char* case_name, int argc,
                       SwimValue* argv);
SwimValue SwimEnumCaseAny(const char* case_name, int argc, SwimValue* argv);
SwimValue SwimBindMethod(SwimValue obj, const char* name, const char* labels);
SwimValue SwimMakeClosure(SwimFn fn, SwimFrame* env);
SwimValue SwimBuiltinCall(const char* name, const char* labels, int argc,
                          SwimValue* argv);
SwimValue SwimBuiltinStatic(SwimType* t, const char* name, const char* labels,
                            int argc, SwimValue* argv);
SwimValue SwimBuiltinMethod(SwimValue recv, const char* name,
                            const char* labels, int argc, SwimValue* argv);
SwimValue SwimOptionalMember(SwimValue opt, const char* name);
SwimValue SwimOptionalCall(SwimValue opt, const char* name, const char* labels,
                           int argc, SwimValue* argv);
SwimValue SwimOptionalSubscript(SwimValue opt, int argc, SwimValue* argv);

/* Program registration. */
void SwimRegisterMethod(SwimType* t, const char* name, const char* labels,
                        const SwimType* const* params, int nparams, SwimFn fn,
                        SwimDefaultFn defaults, int variadic, int mutating,
                        int is_static, int has_self);
void SwimRegisterProp(SwimType* t, const char* name, SwimFn getter,
                      SwimFn setter);
void SwimRegisterStaticProp(SwimType* t, const char* name, SwimFn getter,
                            SwimFn setter);
void SwimRegisterType(SwimType* t);
void SwimRegisterEnumRaw(SwimType* t, const char* case_name, SwimValue raw);
void SwimRegisterInit(SwimType* t, const char* labels,
                      const SwimType* const* params, int nparams, SwimFn fn,
                      SwimDefaultFn defaults, int variadic, int failable);
void SwimRegisterGlobal(const char* name, const char* labels,
                        const SwimType* const* params, int nparams, SwimFn fn,
                        SwimDefaultFn defaults, int variadic);
void SwimRegisterOperator(const char* fixity, const char* symbol,
                          const SwimType* const* params, int nparams,
                          SwimFn fn);

void SwimRegisterAll(void);
void SwimProgramStart(int argc, char** argv);
void SwimProgramFinish(void);

/* ------------------------------------------------------------------ */
/* Pattern matching helpers                                             */
/* ------------------------------------------------------------------ */
SwimValue SwimEnumIs(SwimValue e, const char* case_name);
SwimValue SwimEnumPayload(SwimValue e, const char* case_name, int index);
SwimValue SwimEnumPayloadNamed(SwimValue e, const char* case_name,
                               const char* field);
SwimValue SwimIsType(SwimValue v, SwimType* t);

/* ------------------------------------------------------------------ */
/* Exceptions and defer                                                 */
/* ------------------------------------------------------------------ */
#include <setjmp.h>
typedef struct SwimDeferScope SwimDeferScope;
typedef struct SwimTryFrame {
    jmp_buf buf;
    struct SwimTryFrame* prev;
    SwimValue error;
    SwimDeferScope* defer_top;
} SwimTryFrame;

void SwimTryBegin(SwimTryFrame* f);
void SwimTryEnd(SwimTryFrame* f);
void SwimThrow(SwimValue err) __attribute__((noreturn));
void SwimRethrow(void) __attribute__((noreturn));

struct SwimDeferScope {
    SwimDeferScope* prev;
    int count, cap;
    SwimValue* blocks;
};
void SwimDeferBegin(SwimDeferScope* s);
void SwimDeferAdd(SwimDeferScope* s, SwimValue closure);
void SwimDeferRun(SwimDeferScope* s);
void SwimDeferScopeCleanup(SwimDeferScope* s);

/* Error values. */
SwimValue SwimErrorMake(SwimType* t);
SwimValue SwimErrorMakeMsg(SwimType* t, SwimValue msg);

#ifdef __cplusplus
}
#endif
#endif /* SWIMRT_H */
