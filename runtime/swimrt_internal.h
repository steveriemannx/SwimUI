/* swimrt_internal.h -- shared internals of the Swim runtime (not public). */
#ifndef SWIMRT_INTERNAL_H
#define SWIMRT_INTERNAL_H

#include "swimrt.h"

#include <stdlib.h>
#include <string.h>
#include <stdio.h>
#include <math.h>
#include <stdatomic.h>

#define SWIM_NONE ((SwimValue)0)

/* ---- dynamic string builder ---------------------------------------- */
typedef struct SwimBuf {
    char* data;
    int64_t len;
    int64_t cap;
} SwimBuf;

void SwimBufInit(SwimBuf* b);
void SwimBufAddBytes(SwimBuf* b, const char* s, int64_t n);
void SwimBufAddCStr(SwimBuf* b, const char* s);
void SwimBufAddChar(SwimBuf* b, char c);
void SwimBufFree(SwimBuf* b);
SwimValue SwimBufValue(SwimBuf* b);

/* ---- kind helpers --------------------------------------------------- */
static inline int SwimIsRefKind(SwimKind k) {
    return k == SWIM_KIND_CLASS || k == SWIM_KIND_CLOSURE ||
           k == SWIM_KIND_FRAME || k == SWIM_KIND_TYPE;
}
static inline int SwimIsNumericKind(SwimKind k) {
    return k == SWIM_KIND_INT || k == SWIM_KIND_DOUBLE;
}
SwimValue SwimDeref(SwimValue v);
SwimObj* swim_alloc(SwimType* t, size_t size);
SwimType* SwimValueType(SwimValue v);
SwimKind SwimKindOf(SwimValue v);
SwimValue SwimDeref(SwimValue v);
SwimObj* swim_alloc(SwimType* t, size_t size);

/* ---- printing / description ---------------------------------------- */
void SwimDescribe(SwimValue v, SwimBuf* out);
void SwimDescribeWith(SwimValue v, SwimBuf* out, int depth);

/* ---- value semantics ----------------------------------------------- */
int SwimValuesEqual(SwimValue a, SwimValue b);
int SwimCompare(SwimValue a, SwimValue b); /* -1, 0, 1 */
int64_t SwimHash(SwimValue v);
int SwimIsNumeric(SwimValue v);
int64_t SwimToInt(SwimValue v);
double SwimToDouble(SwimValue v);

/* ---- collections ---------------------------------------------------- */
SwimValue SwimArrayAt(SwimValue arr, int64_t i);
void SwimArraySetAt(SwimValue arr, int64_t i, SwimValue v);
int64_t SwimArrayCount(SwimValue arr);
SwimValue SwimDictLookup(SwimValue dict, SwimValue key); /* Optional */
void SwimDictSet(SwimValue dict, SwimValue key, SwimValue value);
SwimValue SwimSetLookup(SwimValue set, SwimValue key);   /* Bool */
void SwimSetAdd(SwimValue set, SwimValue key);
void SwimSetRemoveValue(SwimValue set, SwimValue key);
SwimValue SwimStringSubstr(SwimValue s, int64_t lo, int64_t hi);
SwimValue SwimStringByteAt(SwimValue s, int64_t i);
SwimValue SwimMakeString(const char* s, int64_t n);
SwimValue SwimConcatValues(SwimValue* vals, int n);
int64_t SwimRangeLower(SwimValue r);
int64_t SwimRangeUpper(SwimValue r);
SwimValue SwimRangeStep(SwimValue start, SwimValue stop, SwimValue step,
                        int closed);
SwimValue SwimArraySort(SwimValue arr, SwimValue closure, int descending);
SwimValue SwimArrayMap(SwimValue arr, SwimValue closure);
SwimValue SwimArrayFilter(SwimValue arr, SwimValue closure);

/* ---- dispatch ------------------------------------------------------- */
SwimMethodEntry* SwimFindMethodEntry(SwimType* t, const char* name,
                                     const char* labels, int argc,
                                     SwimValue* argv, int want_static);
SwimValue SwimInvokeEntry(SwimMethodEntry* e, SwimValue self,
                          const char* labels, int argc, SwimValue* argv);
SwimValue SwimInvokeGlobal(const char* name, const char* labels, int argc,
                           SwimValue* argv);
SwimValue SwimInvokeMethod(SwimValue recv, const char* name,
                           const char* labels, int argc, SwimValue* argv);
SwimValue SwimInvokeBuiltin(SwimValue recv, const char* name,
                            const char* labels, int argc, SwimValue* argv);
SwimValue SwimBuiltinStatic(SwimType* t, const char* name, const char* labels,
                            int argc, SwimValue* argv);
SwimValue SwimCallStatic(SwimType* t, const char* name, const char* labels,
                         int argc, SwimValue* argv);
SwimValue SwimEnumFromRaw(SwimType* t, const char* labels, int argc,
                          SwimValue* argv);
SwimValue SwimBindStatic(SwimType* t, const char* name, const char* labels);
SwimValue SwimBindGlobalFn(const char* name, const char* labels);

/* ---- errors --------------------------------------------------------- */
void SwimFatalFmt(const char* fmt, ...) __attribute__((noreturn));
void SwimThrowError(SwimType* t, const char* msg) __attribute__((noreturn));
int SwimValueIsErrorType(SwimValue v, SwimType* t);

/* ---- registration storage ------------------------------------------ */
typedef struct SwimGlobalEntry {
    const char* name;
    const char* labels;
    const SwimType* const* params;
    int nparams;
    SwimFn fn;
    SwimDefaultFn defaults;
    int variadic;
} SwimGlobalEntry;

extern SwimGlobalEntry* SwimGlobalsTable;
extern int SwimGlobalsCount, SwimGlobalsCap;

typedef struct SwimOperatorEntry {
    const char* fixity;
    const char* symbol;
    const SwimType* const* params;
    int nparams;
    SwimFn fn;
} SwimOperatorEntry;

extern SwimOperatorEntry* SwimOperatorsTable;
extern int SwimOperatorsCount, SwimOperatorsCap;
SwimFn SwimFindOperator(const char* fixity, const char* symbol, int argc,
                        SwimValue* argv);

/* Builtin static constructors: Int(...), String(...), Array(...), etc. */
int SwimBuiltinStaticExists(SwimType* t, const char* name);
SwimValue SwimBuiltinProperty(SwimValue recv, const char* name);
SwimValue SwimGetMemberRaw(SwimValue obj, const char* name);
int SwimBuiltinIsMutator(const char* name);
void SwimRegisterInit(SwimType* t, const char* labels,
                      const SwimType* const* params, int nparams, SwimFn fn,
                      SwimDefaultFn defaults, int variadic, int failable);
int SwimProgramArgc(void);
char** SwimProgramArgv(void);

#endif /* SWIMRT_INTERNAL_H */
