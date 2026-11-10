/* swimrt_call.c -- dispatch, members, subscripts, construction, closures,
 * registration and program start-up for the Swim runtime. */
#include "swimrt_internal.h"

#include <stdlib.h>
#include <string.h>
#include <stdio.h>
#include <stdarg.h>

/* ================================================================== */
/* Registration tables                                                 */
/* ================================================================== */
SwimGlobalEntry* SwimGlobalsTable = NULL;
int SwimGlobalsCount = 0, SwimGlobalsCap = 0;
SwimOperatorEntry* SwimOperatorsTable = NULL;
int SwimOperatorsCount = 0, SwimOperatorsCap = 0;

static SwimType** swim_type_list = NULL;
static int swim_type_count = 0, swim_type_cap = 0;

void SwimRegisterType(SwimType* t) {
    for (int i = 0; i < swim_type_count; i++)
        if (swim_type_list[i] == t) return;
    if (swim_type_count >= swim_type_cap) {
        int nc = swim_type_cap ? swim_type_cap * 2 : 16;
        swim_type_list = (SwimType**)realloc(swim_type_list,
                                             (size_t)nc * sizeof(SwimType*));
        swim_type_cap = nc;
    }
    swim_type_list[swim_type_count++] = t;
}

static void swim_add_method(SwimType* t, const char* name, const char* labels,
                            const SwimType* const* params, int nparams,
                            SwimFn fn, SwimDefaultFn defaults, int variadic,
                            int mutating, int is_static, int has_self,
                            int failable) {
    int* counts = is_static ? &t->static_count : &t->method_count;
    int* caps = is_static ? &t->static_cap : &t->method_cap;
    SwimMethodEntry** arr = is_static ? &t->statics : &t->methods;
    if (*counts >= *caps) {
        int nc = *caps ? *caps * 2 : 8;
        *arr = (SwimMethodEntry*)realloc(*arr,
                                         (size_t)nc * sizeof(SwimMethodEntry));
        if (!*arr) { fprintf(stderr, "swim: out of memory\n"); exit(1); }
        *caps = nc;
    }
    SwimMethodEntry* e = &(*arr)[(*counts)++];
    e->name = name;
    e->labels = labels;
    e->params = params;
    e->nparams = nparams;
    e->fn = fn;
    e->defaults = defaults;
    e->variadic = variadic;
    e->mutating = mutating;
    e->is_static = is_static;
    e->has_self = has_self;
    e->failable = failable;
}

void SwimRegisterMethod(SwimType* t, const char* name, const char* labels,
                        const SwimType* const* params, int nparams, SwimFn fn,
                        SwimDefaultFn defaults, int variadic, int mutating,
                        int is_static, int has_self) {
    swim_add_method(t, name, labels, params, nparams, fn, defaults, variadic,
                    mutating, is_static, has_self, 0);
}
void SwimRegisterInit(SwimType* t, const char* labels,
                      const SwimType* const* params, int nparams, SwimFn fn,
                      SwimDefaultFn defaults, int variadic, int failable) {
    swim_add_method(t, "init", labels, params, nparams, fn, defaults, variadic,
                    0, 1, 1, failable);
}
void SwimRegisterProp(SwimType* t, const char* name, SwimFn getter,
                      SwimFn setter) {
    if (t->prop_count >= t->prop_cap) {
        int nc = t->prop_cap ? t->prop_cap * 2 : 8;
        t->props = (SwimPropDesc*)realloc(t->props,
                                          (size_t)nc * sizeof(SwimPropDesc));
        if (!t->props) { fprintf(stderr, "swim: out of memory\n"); exit(1); }
        t->prop_cap = nc;
    }
    t->props[t->prop_count].name = name;
    t->props[t->prop_count].getter = getter;
    t->props[t->prop_count].setter = setter;
    t->prop_count++;
}
void SwimRegisterStaticProp(SwimType* t, const char* name, SwimFn getter,
                            SwimFn setter) {
    if (t->static_prop_count >= t->static_prop_cap) {
        int nc = t->static_prop_cap ? t->static_prop_cap * 2 : 8;
        t->static_props = (SwimPropDesc*)realloc(
            t->static_props, (size_t)nc * sizeof(SwimPropDesc));
        if (!t->static_props) { fprintf(stderr, "swim: out of memory\n"); exit(1); }
        t->static_prop_cap = nc;
    }
    t->static_props[t->static_prop_count].name = name;
    t->static_props[t->static_prop_count].getter = getter;
    t->static_props[t->static_prop_count].setter = setter;
    t->static_prop_count++;
}
void SwimRegisterEnumRaw(SwimType* t, const char* case_name, SwimValue raw) {
    int idx = -1;
    for (int i = 0; i < t->case_count; i++)
        if (strcmp(t->cases[i].name, case_name) == 0) { idx = i; break; }
    if (idx < 0) return;
    if (idx >= t->raw_cap) {
        int nc = t->raw_cap ? t->raw_cap * 2 : 8;
        while (nc <= idx) nc *= 2;
        t->raws = (SwimValue*)realloc(t->raws, (size_t)nc * sizeof(SwimValue));
        for (int i = t->raw_cap; i < nc; i++) t->raws[i] = NULL;
        t->raw_cap = nc;
    }
    if (t->raws[idx]) SwimRelease(t->raws[idx]);
    t->raws[idx] = SwimCopy(raw);
    if (idx >= t->raw_count) t->raw_count = idx + 1;
}
void SwimRegisterGlobal(const char* name, const char* labels,
                        const SwimType* const* params, int nparams, SwimFn fn,
                        SwimDefaultFn defaults, int variadic) {
    if (SwimGlobalsCount >= SwimGlobalsCap) {
        int nc = SwimGlobalsCap ? SwimGlobalsCap * 2 : 16;
        SwimGlobalsTable = (SwimGlobalEntry*)realloc(
            SwimGlobalsTable, (size_t)nc * sizeof(SwimGlobalEntry));
        if (!SwimGlobalsTable) { fprintf(stderr, "swim: out of memory\n"); exit(1); }
        SwimGlobalsCap = nc;
    }
    SwimGlobalEntry* e = &SwimGlobalsTable[SwimGlobalsCount++];
    e->name = name;
    e->labels = labels;
    e->params = params;
    e->nparams = nparams;
    e->fn = fn;
    e->defaults = defaults;
    e->variadic = variadic;
}
void SwimRegisterOperator(const char* fixity, const char* symbol,
                          const SwimType* const* params, int nparams,
                          SwimFn fn) {
    if (SwimOperatorsCount >= SwimOperatorsCap) {
        int nc = SwimOperatorsCap ? SwimOperatorsCap * 2 : 16;
        SwimOperatorsTable = (SwimOperatorEntry*)realloc(
            SwimOperatorsTable, (size_t)nc * sizeof(SwimOperatorEntry));
        if (!SwimOperatorsTable) { fprintf(stderr, "swim: out of memory\n"); exit(1); }
        SwimOperatorsCap = nc;
    }
    SwimOperatorEntry* e = &SwimOperatorsTable[SwimOperatorsCount++];
    e->fixity = fixity;
    e->symbol = symbol;
    e->params = params;
    e->nparams = nparams;
    e->fn = fn;
}

/* ================================================================== */
/* Signature matching                                                  */
/* ================================================================== */
static int swim_type_compatible(SwimValue v, SwimType* t);

static void swim_split_labels(const char* labels, char* buf, size_t bufsz,
                              char** parts, int* count) {
    *count = 0;
    if (!labels || !*labels) return;
    strncpy(buf, labels, bufsz - 1);
    buf[bufsz - 1] = '\0';
    char* p = buf;
    while (*p && *count < 32) {
        parts[(*count)++] = p;
        char* comma = strchr(p, ',');
        if (!comma) break;
        *comma = '\0';
        p = comma + 1;
    }
}

static int swim_label_matches(const char* param_label, const char* call_label) {
    if (strcmp(param_label, call_label) == 0) return 1;
    return 0;
}

/* Try to bind a call to the given method entry.  On success, fills
 * provided[param] = argument index (-1 for a defaulted parameter) and the
 * parameter values are type compatible. */
static int swim_bind_entry(SwimMethodEntry* e, const char* call_labels,
                           int argc, SwimValue* argv, int* provided) {
    int np = e->nparams;
    for (int i = 0; i < np; i++) provided[i] = -1;
    char pbuf[512];
    char* pl[32];
    int pcount = 0;
    swim_split_labels(e->labels, pbuf, sizeof(pbuf), pl, &pcount);
    char cbuf[512];
    char* cl[32];
    int ccount = 0;
    swim_split_labels(call_labels, cbuf, sizeof(cbuf), cl, &ccount);
    if (ccount != argc) return 0;
    int pos = 0;
    int variadic = e->variadic;
    int va_param = variadic >= 0 ? variadic : np;
    int saw_variadic = 0;
    for (int j = 0; j < argc; j++) {
        if (saw_variadic) {
            int found = -1;
            if (strcmp(cl[j], "*") == 0) {
                for (int i = np - 1; i > va_param; i--)
                    if (provided[i] < 0) { found = i; break; }
            } else if (strcmp(cl[j], "_") != 0) {
                for (int i = va_param + 1; i < np; i++)
                    if (provided[i] < 0 && i < pcount &&
                        strcmp(pl[i], cl[j]) == 0) { found = i; break; }
            }
            if (found >= 0) { provided[found] = j; continue; }
            if (provided[va_param] < 0) provided[va_param] = j;
            continue;
        }
        if (variadic >= 0 && pos >= va_param) {
            provided[va_param] = j;
            saw_variadic = 1;
            continue;
        }
        int found = -1;
        if (strcmp(cl[j], "*") == 0) {
            for (int i = np - 1; i >= 0; i--) {
                if (i == variadic) continue;
                if (provided[i] < 0) { found = i; break; }
            }
        } else {
            for (int i = pos; i < np; i++) {
                const char* lab = i < pcount ? pl[i] : "_";
                if (swim_label_matches(lab, cl[j])) { found = i; break; }
            }
        }
        if (found < 0) {
            if (variadic >= 0) { provided[va_param] = j; saw_variadic = 1; continue; }
            return 0;
        }
        provided[found] = j;
        if (variadic >= 0 && found == variadic) saw_variadic = 1;
        pos = found + 1;
    }
    /* every remaining parameter needs a default */
    for (int i = 0; i < np; i++) {
        if (provided[i] < 0 && i != variadic) {
            if (!e->defaults) return 0;
        }
    }
    /* type compatibility */
    for (int i = 0; i < np; i++) {
        if (i == variadic) continue;
        SwimType* pt = e->params ? (SwimType*)e->params[i] : NULL;
        if (provided[i] >= 0 && !swim_type_compatible(argv[provided[i]], pt))
            return 0;
    }
    if (variadic >= 0 && e->params) {
        SwimType* vt = (SwimType*)e->params[variadic];
        if (vt && vt->elem) {
            for (int j = 0; j < argc; j++) {
                if (provided[variadic] == j && j >= 0) {
                    if (!swim_type_compatible(argv[j], (SwimType*)vt->elem))
                        return 0;
                }
            }
        }
    }
    return 1;
}

static int swim_bind_global(SwimGlobalEntry* e, const char* call_labels,
                            int argc, SwimValue* argv, int* provided) {
    int np = e->nparams;
    for (int i = 0; i < np; i++) provided[i] = -1;
    char pbuf[512];
    char* pl[32];
    int pcount = 0;
    swim_split_labels(e->labels, pbuf, sizeof(pbuf), pl, &pcount);
    char cbuf[512];
    char* cl[32];
    int ccount = 0;
    swim_split_labels(call_labels, cbuf, sizeof(cbuf), cl, &ccount);
    if (ccount != argc) return 0;
    int pos = 0;
    int variadic = e->variadic;
    int va_param = variadic >= 0 ? variadic : np;
    int saw_variadic = 0;
    for (int j = 0; j < argc; j++) {
        if (saw_variadic) {
            int found = -1;
            if (strcmp(cl[j], "*") == 0) {
                for (int i = np - 1; i > va_param; i--)
                    if (provided[i] < 0) { found = i; break; }
            } else if (strcmp(cl[j], "_") != 0) {
                for (int i = va_param + 1; i < np; i++)
                    if (provided[i] < 0 && i < pcount &&
                        strcmp(pl[i], cl[j]) == 0) { found = i; break; }
            }
            if (found >= 0) { provided[found] = j; continue; }
            if (provided[va_param] < 0) provided[va_param] = j;
            continue;
        }
        if (variadic >= 0 && pos >= va_param) {
            provided[va_param] = j;
            saw_variadic = 1;
            continue;
        }
        int found = -1;
        if (strcmp(cl[j], "*") == 0) {
            for (int i = np - 1; i >= 0; i--) {
                if (i == variadic) continue;
                if (provided[i] < 0) { found = i; break; }
            }
        } else {
            for (int i = pos; i < np; i++) {
                if (i == variadic) continue;
                const char* lab = i < pcount ? pl[i] : "_";
                if (strcmp(lab, cl[j]) == 0) { found = i; break; }
            }
        }
        if (found < 0) {
            if (variadic >= 0) { provided[va_param] = j; saw_variadic = 1; continue; }
            return 0;
        }
        provided[found] = j;
        pos = found + 1;
    }
    for (int i = 0; i < np; i++) {
        if (provided[i] < 0 && i != variadic) {
            if (!e->defaults) return 0;
        }
    }
    for (int i = 0; i < np; i++) {
        if (i == variadic) continue;
        SwimType* pt = e->params ? (SwimType*)e->params[i] : NULL;
        if (provided[i] >= 0 && !swim_type_compatible(argv[provided[i]], pt))
            return 0;
    }
    return 1;
}

static int swim_type_compatible(SwimValue v, SwimType* t) {
    v = SwimDeref(v);
    if (v && v->type->kind == SWIM_KIND_FRAME) return 1; /* inout cell */
    if (!t) return 1;
    if (t->kind == SWIM_KIND_ANY || t == &SwimType_Generic) return 1;
    if (!v) return 1;
    switch (t->kind) {
        case SWIM_KIND_INT:
            return v->type->kind == SWIM_KIND_INT ||
                   v->type->kind == SWIM_KIND_CHAR ||
                   v->type->kind == SWIM_KIND_BOOL;
        case SWIM_KIND_DOUBLE:
            return v->type->kind == SWIM_KIND_DOUBLE ||
                   v->type->kind == SWIM_KIND_INT;
        case SWIM_KIND_BOOL:
            return v->type->kind == SWIM_KIND_BOOL;
        case SWIM_KIND_CHAR:
            return v->type->kind == SWIM_KIND_CHAR ||
                   v->type->kind == SWIM_KIND_STRING;
        case SWIM_KIND_STRING:
            return v->type->kind == SWIM_KIND_STRING;
        case SWIM_KIND_OPTIONAL:
            if (v->type->kind == SWIM_KIND_OPTIONAL) return 1;
            return swim_type_compatible(v, (SwimType*)t->elem);
        case SWIM_KIND_ARRAY:
            return v->type->kind == SWIM_KIND_ARRAY;
        case SWIM_KIND_DICT:
            return v->type->kind == SWIM_KIND_DICT;
        case SWIM_KIND_SET:
            return v->type->kind == SWIM_KIND_SET;
        case SWIM_KIND_RANGE:
            return v->type->kind == SWIM_KIND_RANGE;
        case SWIM_KIND_TUPLE:
            return v->type->kind == SWIM_KIND_TUPLE;
        case SWIM_KIND_STRUCT:
        case SWIM_KIND_ENUM:
        case SWIM_KIND_CLASS: {
            SwimType* cur = v->type;
            while (cur) {
                if (cur == t) return 1;
                cur = (SwimType*)cur->parent;
            }
            return 0;
        }
        case SWIM_KIND_CLOSURE:
            return v->type->kind == SWIM_KIND_CLOSURE ||
                   v->type->kind == SWIM_KIND_CLASS;
        case SWIM_KIND_VOID:
            return v->type->kind == SWIM_KIND_VOID;
        default:
            return 1;
    }
}

int SwimTypeIsCompatible(SwimValue v, SwimType* t) { return swim_type_compatible(v, t); }

/* ================================================================== */
/* Invocation                                                          */
/* ================================================================== */
static SwimValue swim_invoke_args(SwimFn fn, SwimDefaultFn defaults,
                                  SwimValue self, int has_self,
                                  const SwimType* const* ptypes, int nparams,
                                  int variadic, const char* param_labels,
                                  const char* labels, int argc,
                                  SwimValue* argv) {
    (void)fn;
    SwimMethodEntry e;
    memset(&e, 0, sizeof(e));
    e.labels = param_labels;
    e.params = ptypes;
    e.nparams = nparams;
    e.defaults = defaults;
    e.variadic = variadic;
    e.has_self = has_self;
    int* provided = (int*)calloc((size_t)nparams + 1, sizeof(int));
    for (int i = 0; i <= nparams; i++) provided[i] = -1;
    if (!swim_bind_entry(&e, labels, argc, argv, provided)) {
        for (int i = 0; i < nparams; i++) provided[i] = i < argc ? i : -1;
    }
    SwimValue* vals = (SwimValue*)calloc((size_t)nparams + 1, sizeof(SwimValue));
    int missing = 0;
    for (int i = 0; i < nparams; i++)
        if (provided[i] < 0 && i != variadic) missing = 1;
    if (defaults && missing) {
        SwimValue* defs = (SwimValue*)calloc((size_t)nparams, sizeof(SwimValue));
        defaults(NULL, argc, argv, provided, defs);
        for (int i = 0; i < nparams; i++) {
            if (i == variadic) continue;
            if (provided[i] >= 0) {
                vals[i] = argv[provided[i]];
                if (vals[i]) SwimRetain(vals[i]);
            } else {
                vals[i] = defs[i];
            }
        }
        free(defs);
    } else {
        for (int i = 0; i < nparams; i++) {
            if (i == variadic) continue;
            if (provided[i] >= 0) {
                vals[i] = argv[provided[i]];
                if (vals[i]) SwimRetain(vals[i]);
            }
        }
    }
    if (variadic >= 0) {
        SwimValue arr = SwimArrayNew(ptypes && ptypes[variadic]
                                        ? (SwimType*)ptypes[variadic]->elem
                                        : NULL);
        int start = provided[variadic];
        int end = argc;
        for (int i = variadic + 1; i < nparams; i++) {
            if (provided[i] > start && provided[i] < end) end = provided[i];
        }
        if (start >= 0) {
            for (int j = start; j < end; j++)
                SwimArrayAppendValue(arr, argv[j]);
        }
        vals[variadic] = arr;
    }
    for (int i = 0; i < nparams; i++) {
        SwimType* pt = ptypes ? (SwimType*)ptypes[i] : NULL;
        if (!vals[i] && pt && pt->kind == SWIM_KIND_OPTIONAL) {
            vals[i] = SwimNone();
            continue;
        }
        if (vals[i] && pt && vals[i]->type->kind != SWIM_KIND_FRAME) {
            SwimValue cv = SwimCoerce(vals[i], pt);
            if (cv != vals[i]) {
                SwimRelease(vals[i]);
                vals[i] = cv;
            }
        }
    }
    int total = nparams + (has_self ? 1 : 0);
    SwimValue* callargv = (SwimValue*)calloc((size_t)total + 1,
                                             sizeof(SwimValue));
    int at = 0;
    if (has_self) {
        callargv[at++] = self;
        if (self) SwimRetain(self);
    }
    for (int i = 0; i < nparams; i++) callargv[at++] = vals[i];
    SwimValue result = ((SwimFn)fn)(NULL, total, callargv);
    for (int i = 0; i < total; i++) {
        if (callargv[i]) SwimRelease(callargv[i]);
    }
    free(callargv);
    free(vals);
    free(provided);
    return result;
}

SwimValue SwimInvokeEntry(SwimMethodEntry* e, SwimValue self,
                          const char* labels, int argc, SwimValue* argv) {
    return swim_invoke_args(e->fn, e->defaults, self, e->has_self, e->params,
                            e->nparams, e->variadic, e->labels, labels, argc,
                            argv);
}

static SwimMethodEntry* swim_find_in(SwimType* t, const char* name,
                                     const char* labels, int argc,
                                     SwimValue* argv, int is_static,
                                     int want_mutating, int* out_index) {
    for (SwimType* cur = t; cur != NULL; cur = (SwimType*)cur->parent) {
        int count = is_static ? cur->static_count : cur->method_count;
        SwimMethodEntry* arr = is_static ? cur->statics : cur->methods;
        for (int i = 0; i < count; i++) {
            if (strcmp(arr[i].name, name) != 0) continue;
            if (arr[i].has_self != !is_static) continue;
            if (want_mutating && !arr[i].mutating) continue;
            if (cur == t || t->kind == SWIM_KIND_CLASS) {
                int provided[33];
                if (swim_bind_entry(&arr[i], labels, argc, argv, provided)) {
                    if (out_index) *out_index = i;
                    return &arr[i];
                }
            }
        }
    }
    return NULL;
}

SwimValue SwimGetMemberRaw(SwimValue obj, const char* name);

SwimValue SwimInvokeMethod(SwimValue recv, const char* name,
                           const char* labels, int argc, SwimValue* argv) {
    if (recv != NULL && recv->type->kind == SWIM_KIND_PROXY) {
        SwimProxyObj* p = (SwimProxyObj*)recv;
        SwimValue cur = SwimGetMemberRaw(p->target, p->member);
        SwimMethodEntry* pe = cur ? swim_find_in(cur->type, name, labels, argc,
                                                 argv, 0, 0, NULL) : NULL;
        int mutates = SwimBuiltinIsMutator(name) || (pe && pe->mutating);
        if (mutates) {
            SwimValue copyv = SwimCopy(cur);
            SwimRelease(cur);
            SwimValue r = pe ? SwimInvokeEntry(pe, copyv, labels, argc, argv)
                             : SwimBuiltinMethod(copyv, name, labels, argc, argv);
            if (r == NULL) {
                SwimRelease(copyv);
                SwimFatalFmt("type has no member '%s'", name);
            }
            SwimSetMember(p->target, p->member, copyv);
            SwimRelease(copyv);
            return r;
        }
        SwimValue r = pe ? SwimInvokeEntry(pe, cur, labels, argc, argv)
                         : SwimBuiltinMethod(cur, name, labels, argc, argv);
        SwimRelease(cur);
        if (r == NULL) SwimFatalFmt("value has no member '%s'", name);
        return r;
    }
    recv = SwimDeref(recv);
    if (recv == NULL) SwimFatalFmt("cannot call '%s' on nil", name);
    if (recv->type->kind == SWIM_KIND_TYPE) {
        SwimType* t = ((SwimTypeObj*)recv)->target;
        for (SwimType* cur = t; cur != NULL; cur = (SwimType*)cur->parent) {
            for (int i = 0; i < cur->static_count; i++) {
                SwimMethodEntry* e = &cur->statics[i];
                if (strcmp(e->name, name) != 0) continue;
                int provided[33];
                if (swim_bind_entry(e, labels, argc, argv, provided))
                    return swim_invoke_args(e->fn, e->defaults, NULL, 0,
                                            e->params, e->nparams,
                                            e->variadic, e->labels, labels,
                                            argc, argv);
            }
        }
        return SwimBuiltinStatic(t, name, labels, argc, argv);
    }
    SwimMethodEntry* e = swim_find_in(recv->type, name, labels, argc, argv, 0,
                                      0, NULL);
    if (e) return SwimInvokeEntry(e, recv, labels, argc, argv);
    return SwimBuiltinMethod(recv, name, labels, argc, argv);
}

SwimValue SwimInvokeGlobal(const char* name, const char* labels, int argc,
                           SwimValue* argv) {
    for (int i = 0; i < SwimGlobalsCount; i++) {
        SwimGlobalEntry* e = &SwimGlobalsTable[i];
        if (strcmp(e->name, name) != 0) continue;
        int provided[33];
        if (swim_bind_global(e, labels, argc, argv, provided))
            return swim_invoke_args(e->fn, e->defaults, NULL, 0, e->params,
                                    e->nparams, e->variadic, e->labels, labels, argc, argv);
    }
    return SwimBuiltinCall(name, labels, argc, argv);
}

SwimValue SwimCallGlobal(const char* name, const char* labels, int argc,
                         SwimValue* argv) {
    return SwimInvokeGlobal(name, labels, argc, argv);
}

SwimValue SwimCallMethod(SwimValue obj, const char* name, const char* labels,
                         int argc, SwimValue* argv) {
    return SwimInvokeMethod(obj, name, labels, argc, argv);
}
SwimValue SwimCallMethodFrom(SwimValue obj, SwimType* start, const char* name,
                             const char* labels, int argc, SwimValue* argv) {
    obj = SwimDeref(obj);
    start = start ? start : (obj ? obj->type : NULL);
    for (SwimType* cur = start; cur != NULL; cur = (SwimType*)cur->parent) {
        for (int i = 0; i < cur->method_count; i++) {
            SwimMethodEntry* e = &cur->methods[i];
            if (strcmp(e->name, name) != 0) continue;
            int provided[33];
            if (swim_bind_entry(e, labels, argc, argv, provided))
                return swim_invoke_args(e->fn, e->defaults, obj, 1, e->params,
                                        e->nparams, e->variadic, e->labels, labels, argc,
                                        argv);
        }
    }
    SwimFatalFmt("method '%s' not found", name);
}

SwimValue SwimCallValue(SwimValue fn, int argc, SwimValue* argv) {
    fn = SwimDeref(fn);
    if (fn == NULL) SwimFatalFmt("cannot call nil");
    if (fn->type->kind == SWIM_KIND_CLOSURE) {
        SwimClosureObj* c = (SwimClosureObj*)fn;
        return c->fn(c->env, argc, argv);
    }
    if (fn->type->kind == SWIM_KIND_TYPE) {
        SwimType* t = ((SwimTypeObj*)fn)->target;
        return SwimConstruct(t, "", argc, argv);
    }
    SwimFatalFmt("value of type '%s' is not callable", fn->type->name);
}

SwimValue SwimMakeClosure(SwimFn f, SwimFrame* env) {
    SwimClosureObj* c =
        (SwimClosureObj*)swim_alloc(&SwimType_Closure, sizeof(SwimClosureObj));
    c->h.type = &SwimType_Closure;
    c->fn = f;
    c->env = env;
    if (env) SwimRetain((SwimValue)env);
    return (SwimValue)c;
}

/* ================================================================== */
/* Members                                                             */
/* ================================================================== */
static SwimPropDesc* swim_find_prop(SwimType* t, const char* name, int is_static) {
    for (SwimType* cur = t; cur != NULL; cur = (SwimType*)cur->parent) {
        int count = is_static ? cur->static_prop_count : cur->prop_count;
        SwimPropDesc* arr = is_static ? cur->static_props : cur->props;
        for (int i = 0; i < count; i++)
            if (strcmp(arr[i].name, name) == 0) return &arr[i];
    }
    return NULL;
}

static SwimValue swim_prop_value(SwimValue obj, const char* name,
                                 SwimPropDesc* p) {
    SwimValue argv[1] = {obj};
    return p->getter(NULL, 1, argv);
}


static int swim_field_index(SwimType* t, const char* name) {
    for (int i = 0; i < t->field_count; i++)
        if (strcmp(t->fields[i].name, name) == 0) return i;
    return -1;
}

static int swim_field_is_weak_ref(SwimType* t, int idx) {
    return t->fields != NULL && idx >= 0 && idx < t->field_count &&
           (t->fields[idx].weak || t->fields[idx].unowned);
}

static SwimValue swim_make_weak_field_value(SwimType* t, int idx,
                                            SwimValue v) {
    return SwimWeakMake(v, t->fields[idx].unowned ? 1 : 0);
}

static SwimValue swim_load_weak_field(SwimType* t, int idx, SwimValue holder) {
    SwimFieldDesc* d = (SwimFieldDesc*)&t->fields[idx];
    return SwimWeakLoad(holder, d->weak ? 1 : 0, d->optional ? 1 : 0);
}

SwimValue SwimGetMemberRaw(SwimValue obj, const char* name) {
    SwimType* t = obj->type;
    SwimPropDesc* p = swim_find_prop(t, name, 0);
    if (p && p->getter) return swim_prop_value(obj, name, p);
    int idx = swim_field_index(t, name);
    if (idx >= 0) {
        SwimObjectObj* o = (SwimObjectObj*)obj;
        if (idx >= o->n) return SwimNone();
        if (swim_field_is_weak_ref(t, idx))
            return swim_load_weak_field(t, idx, o->slots[idx]);
        SwimValue v = o->slots[idx];
        if (v) SwimRetain(v);
        return v;
    }
    if (t->kind == SWIM_KIND_TUPLE) {
        for (int i = 0; i < t->field_count; i++) {
            if (t->fields && strcmp(t->fields[i].name, name) == 0) {
                SwimTupleObj* tu = (SwimTupleObj*)obj;
                SwimValue v = i < tu->n ? tu->slots[i] : NULL;
                if (v) SwimRetain(v);
                return v;
            }
        }
        char* end = NULL;
        long idx = strtol(name, &end, 10);
        if (end != name && *end == '\0') {
            SwimTupleObj* tu = (SwimTupleObj*)obj;
            if (idx >= 0 && idx < tu->n) {
                SwimValue v = tu->slots[idx];
                if (v) SwimRetain(v);
                return v;
            }
            return SwimNone();
        }
    }
    if (t->kind == SWIM_KIND_ENUM) {
        SwimEnumObj* e = (SwimEnumObj*)obj;
        if (strcmp(name, "rawValue") == 0) {
            if (t->raws && e->tag >= 0 && e->tag < t->raw_count && t->raws[e->tag]) {
                SwimRetain(t->raws[e->tag]);
                return t->raws[e->tag];
            }
            return SwimInt(e->tag);
        }
        if (strcmp(name, "hashValue") == 0) return SwimInt(SwimHash(obj));
    }
    if (strcmp(name, "hashValue") == 0) return SwimInt(SwimHash(obj));
    return SwimBuiltinProperty(obj, name);
}

SwimValue SwimGetMember(SwimValue obj, const char* name) {
    obj = SwimDeref(obj);
    if (obj == NULL) SwimFatalFmt("cannot read '%s' of nil", name);
    if (obj->type->kind == SWIM_KIND_TYPE) {
        SwimType* t = ((SwimTypeObj*)obj)->target;
        SwimPropDesc* p = swim_find_prop(t, name, 1);
        if (p && p->getter) {
            SwimValue argv[1] = {obj};
            return p->getter(NULL, 1, argv);
        }
        return SwimBuiltinStatic(t, name, "", 0, NULL);
    }
    SwimPropDesc* p = swim_find_prop(obj->type, name, 0);
    if (p && p->setter) {
        SwimProxyObj* proxy =
            (SwimProxyObj*)swim_alloc(&SwimType_Any, sizeof(SwimProxyObj));
        proxy->h.type = &SwimType_Any;
        proxy->target = obj;
        SwimRetain(obj);
        proxy->member = name;
        /* The proxy needs a type descriptor that identifies it as a proxy. */
        proxy->h.type = (SwimType*)&SwimType_Optional;
        /* Mark via a dedicated descriptor to keep kind checks simple. */
        {
            static SwimType proxy_type = { "Proxy", SWIM_KIND_PROXY, 0, 0, 0, 0,
                                           0, 0, 0, 0, 0 };
            proxy->h.type = &proxy_type;
        }
        return (SwimValue)proxy;
    }
    return SwimGetMemberRaw(obj, name);
}

void SwimSetMember(SwimValue obj, const char* name, SwimValue v) {
    obj = SwimDeref(obj);
    if (obj == NULL) SwimFatalFmt("cannot set '%s' of nil", name);
    if (obj->type->kind == SWIM_KIND_TYPE) {
        SwimType* t = ((SwimTypeObj*)obj)->target;
        SwimPropDesc* p = swim_find_prop(t, name, 1);
        if (p && p->setter) {
            SwimValue argv[2] = {obj, v};
            SwimValue r = p->setter(NULL, 2, argv);
            if (r) SwimRelease(r);
            return;
        }
        SwimFatalFmt("cannot assign to static member '%s'", name);
    }
    SwimPropDesc* p = swim_find_prop(obj->type, name, 0);
    if (p && p->setter) {
        SwimValue argv[2] = {obj, v};
        SwimValue r = p->setter(NULL, 2, argv);
        if (r) SwimRelease(r);
        return;
    }
    int idx = swim_field_index(obj->type, name);
    if (idx < 0) SwimFatalFmt("type '%s' has no member '%s'",
                              obj->type->name, name);
    SwimObjectObj* o = (SwimObjectObj*)obj;
    if (idx >= o->n) SwimFatalFmt("type '%s' has no member '%s'",
                                  obj->type->name, name);
    if (swim_field_is_weak_ref(obj->type, idx)) {
        SwimValue holder = swim_make_weak_field_value(obj->type, idx, v);
        SwimStore(&o->slots[idx], holder);
        SwimRelease(holder);
        return;
    }
    SwimStore(&o->slots[idx], v);
}

/* ================================================================== */
/* Static members                                                      */
/* ================================================================== */
SwimValue SwimGetStatic(SwimType* t, const char* name) {
    SwimPropDesc* p = swim_find_prop(t, name, 1);
    if (p && p->getter) {
        SwimValue argv[1] = {SwimTypeValue(t)};
        SwimValue r = p->getter(NULL, 1, argv);
        SwimRelease(argv[0]);
        return r;
    }
    return SwimBuiltinStatic(t, name, "", 0, NULL);
}
void SwimSetStatic(SwimType* t, const char* name, SwimValue v) {
    SwimPropDesc* p = swim_find_prop(t, name, 1);
    if (p && p->setter) {
        SwimValue argv[2] = {SwimTypeValue(t), v};
        SwimValue r = p->setter(NULL, 2, argv);
        if (r) SwimRelease(r);
        SwimRelease(argv[0]);
        return;
    }
    SwimFatalFmt("cannot assign to static member '%s'", name);
}
SwimValue SwimCallStatic(SwimType* t, const char* name, const char* labels,
                         int argc, SwimValue* argv) {
    for (SwimType* cur = t; cur != NULL; cur = (SwimType*)cur->parent) {
        for (int i = 0; i < cur->static_count; i++) {
            SwimMethodEntry* e = &cur->statics[i];
            if (strcmp(e->name, name) != 0) continue;
            int provided[33];
            if (swim_bind_entry(e, labels, argc, argv, provided))
                return swim_invoke_args(e->fn, e->defaults, NULL, 0, e->params,
                                        e->nparams, e->variadic, e->labels, labels, argc,
                                        argv);
        }
    }
    return SwimBuiltinStatic(t, name, labels, argc, argv);
}

/* ================================================================== */
/* Construction                                                        */
/* ================================================================== */
SwimValue SwimAllocObject(SwimType* t) {
    SwimObjectObj* o = (SwimObjectObj*)swim_alloc(t, sizeof(SwimObjectObj));
    o->h.type = t;
    o->n = t->field_count;
    o->slots = t->field_count
                   ? (SwimValue*)calloc((size_t)t->field_count, sizeof(SwimValue))
                   : NULL;
    return (SwimValue)o;
}

static SwimValue swim_construct_impl(SwimType* t, const char* labels, int argc,
                                     SwimValue* argv) {
    SwimMethodEntry* init = NULL;
    for (int i = 0; i < t->static_count; i++) {
        if (strcmp(t->statics[i].name, "init") != 0) continue;
        int provided[33];
        if (swim_bind_entry(&t->statics[i], labels, argc, argv, provided)) {
            init = &t->statics[i];
            break;
        }
    }
    SwimValue obj = SwimAllocObject(t);
    if (init == NULL) return obj; /* synthesized default init: all zeroed */
    SwimValue r = swim_invoke_args(init->fn, init->defaults, obj, 1,
                                   init->params, init->nparams, init->variadic,
                                   init->labels, labels, argc, argv);
    if (init->failable) {
        int ok = r ? SwimUnboxBool(r) : 1;
        if (r) SwimRelease(r);
        if (!ok) { SwimRelease(obj); return SwimNone(); }
        return obj;
    }
    if (r) SwimRelease(r);
    return obj;
}
SwimValue SwimConstruct(SwimType* t, const char* labels, int argc,
                        SwimValue* argv) {
    return swim_construct_impl(t, labels, argc, argv);
}
SwimValue SwimConstructOpt(SwimType* t, const char* labels, int argc,
                           SwimValue* argv) {
    return swim_construct_impl(t, labels, argc, argv);
}

/* ================================================================== */
/* Enums                                                               */
/* ================================================================== */
static int swim_enum_case_index(SwimType* t, const char* name) {
    for (int i = 0; i < t->case_count; i++)
        if (strcmp(t->cases[i].name, name) == 0) return i;
    return -1;
}
SwimValue SwimEnumCase(SwimType* t, const char* case_name, int argc,
                       SwimValue* argv) {
    int idx = swim_enum_case_index(t, case_name);
    if (idx < 0) SwimFatalFmt("enum '%s' has no case '%s'", t->name, case_name);
    const SwimCaseDesc* cd = &t->cases[idx];
    SwimEnumObj* e = (SwimEnumObj*)swim_alloc(t, sizeof(SwimEnumObj));
    e->h.type = t;
    e->tag = idx;
    e->n = cd->payload_count;
    e->slots = cd->payload_count
                   ? (SwimValue*)calloc((size_t)cd->payload_count,
                                        sizeof(SwimValue))
                   : NULL;
    for (int i = 0; i < cd->payload_count && i < argc; i++) {
        SwimValue v = argv[i];
        if (cd->payload[i].type) v = SwimCoerce(v, cd->payload[i].type);
        e->slots[i] = SwimCopy(v);
    }
    return (SwimValue)e;
}
SwimValue SwimEnumCaseAny(const char* case_name, int argc, SwimValue* argv) {
    /* CharacterSet-style shorthands such as ``.whitespaces`` */
    if (strcmp(case_name, "whitespaces") == 0 ||
        strcmp(case_name, "newlines") == 0 ||
        strcmp(case_name, "decimalDigits") == 0 ||
        strcmp(case_name, "letters") == 0 ||
        strcmp(case_name, "alphanumerics") == 0 ||
        strcmp(case_name, "punctuationCharacters") == 0)
        return SwimCStr(case_name);
    SwimType* found = NULL;
    int idx = -1;
    for (int i = 0; i < swim_type_count; i++) {
        SwimType* t = swim_type_list[i];
        if (t->kind != SWIM_KIND_ENUM) continue;
        int ci = swim_enum_case_index(t, case_name);
        if (ci < 0) continue;
        if (t->cases[ci].payload_count != argc) continue;
        if (found != NULL) {
            /* prefer an exact payload match */
            found = t; idx = ci;
            break;
        }
        found = t;
        idx = ci;
    }
    if (!found) SwimFatalFmt("no enum case named '%s'", case_name);
    (void)idx;
    return SwimEnumCase(found, case_name, argc, argv);
}
SwimValue SwimEnumFromRaw(SwimType* t, const char* labels, int argc,
                          SwimValue* argv) {
    (void)labels;
    if (argc < 1) return SwimNone();
    SwimValue raw = SwimDeref(argv[0]);
    for (int i = 0; i < t->raw_count; i++) {
        if (t->raws[i] && SwimValuesEqual(t->raws[i], raw)) {
            SwimValue e = SwimEnumCase(t, t->cases[i].name, 0, NULL);
            return SwimSome(e);
        }
    }
    return SwimNone();
}
SwimValue SwimEnumRaw(SwimType* t, const char* labels, int argc,
                      SwimValue* argv) {
    return SwimEnumFromRaw(t, labels, argc, argv);
}

/* ================================================================== */
/* Subscripts                                                          */
/* ================================================================== */
static void swim_sub_labels(char* buf, int argc) {
    int at = 0;
    for (int i = 0; i < argc; i++) {
        if (i) buf[at++] = ',';
        buf[at++] = '_';
    }
    buf[at] = '\0';
}

static SwimValue swim_do_subscript_get(SwimValue obj, int argc,
                                       SwimValue* argv) {
    char slab[128];
    swim_sub_labels(slab, argc);
    obj = SwimDeref(obj);
    SwimKind k = obj->type->kind;
    if (k == SWIM_KIND_TYPE) {
        SwimType* t = ((SwimTypeObj*)obj)->target;
        for (int i = 0; i < t->static_count; i++) {
            SwimMethodEntry* e = &t->statics[i];
            if (strcmp(e->name, "__sub_get") != 0) continue;
            int provided[33];
            if (swim_bind_entry(e, slab, argc, argv, provided))
                return swim_invoke_args(e->fn, e->defaults, NULL, 0, e->params,
                                        e->nparams, e->variadic, e->labels, slab, argc,
                                        argv);
        }
        SwimFatalFmt("static subscript not found");
    }
    if (k == SWIM_KIND_ARRAY) {
        if (argc == 1) {
            SwimValue a0 = SwimDeref(argv[0]);
            if (a0->type->kind == SWIM_KIND_RANGE) {
                SwimRangeObj* r = (SwimRangeObj*)a0;
                int64_t lo = SwimToInt(r->lo);
                int64_t hi = SwimToInt(r->hi) + (r->closed ? 1 : 0);
                int64_t n = SwimArrayCount(obj);
                if (lo < 0) lo = 0;
                if (hi > n) hi = n;
                if (hi < lo) hi = lo;
                SwimArrayObj* arr = (SwimArrayObj*)obj;
                return SwimArrayFrom((int)(hi - lo), arr->items + lo, arr->elem);
            }
            return SwimArrayAt(obj, SwimToInt(argv[0]));
        }
        SwimFatalFmt("array subscript expects one index");
    }
    if (k == SWIM_KIND_STRING) {
        if (argc == 1) {
            SwimValue a0 = SwimDeref(argv[0]);
            if (a0->type->kind == SWIM_KIND_RANGE) {
                SwimRangeObj* r = (SwimRangeObj*)a0;
                int64_t lo = SwimToInt(r->lo);
                int64_t hi = SwimToInt(r->hi) + (r->closed ? 1 : 0);
                return SwimStringSubstr(obj, lo, hi);
            }
            return SwimStringByteAt(obj, SwimToInt(argv[0]));
        }
        SwimFatalFmt("string subscript expects one index");
    }
    if (k == SWIM_KIND_DICT) {
        return SwimDictLookup(obj, argv[0]);
    }
    if (k == SWIM_KIND_RANGE) {
        return SwimBool(SwimCompare(argv[0], ((SwimRangeObj*)obj)->lo) >= 0 &&
                        SwimCompare(argv[0], ((SwimRangeObj*)obj)->hi) <= 0);
    }
    for (SwimType* cur = obj->type; cur != NULL; cur = (SwimType*)cur->parent) {
        for (int i = 0; i < cur->method_count; i++) {
            SwimMethodEntry* e = &cur->methods[i];
            if (strcmp(e->name, "__sub_get") != 0) continue;
            int provided[33];
            if (swim_bind_entry(e, slab, argc, argv, provided))
                return swim_invoke_args(e->fn, e->defaults, obj, 1, e->params,
                                        e->nparams, e->variadic, e->labels, slab, argc,
                                        argv);
        }
    }
    SwimFatalFmt("type '%s' has no subscript", obj->type->name);
}
SwimValue SwimSubscriptGet(SwimValue obj, int argc, SwimValue* argv) {
    obj = SwimDeref(obj);
    if (obj && obj->type->kind == SWIM_KIND_PROXY) {
        return swim_do_subscript_get(obj, argc, argv);
    }
    return swim_do_subscript_get(obj, argc, argv);
}
void SwimSubscriptSet(SwimValue obj, int argc, SwimValue* argv, SwimValue v) {
    char slab[128];
    swim_sub_labels(slab, argc + 1);
    obj = SwimDeref(obj);
    SwimKind k = obj->type->kind;
    if (k == SWIM_KIND_TYPE) {
        SwimType* t = ((SwimTypeObj*)obj)->target;
        for (int i = 0; i < t->static_count; i++) {
            SwimMethodEntry* e = &t->statics[i];
            if (strcmp(e->name, "__sub_set") != 0) continue;
            SwimValue* args = (SwimValue*)calloc((size_t)argc + 1,
                                                 sizeof(SwimValue));
            for (int j = 0; j < argc; j++) args[j] = argv[j];
            args[argc] = v;
            SwimValue r = swim_invoke_args(e->fn, e->defaults, NULL, 0,
                                           e->params, e->nparams, e->variadic,
                                           e->labels, slab, argc + 1, args);
            free(args);
            if (r) SwimRelease(r);
            return;
        }
        SwimFatalFmt("static subscript setter not found");
    }
    if (k == SWIM_KIND_ARRAY) {
        SwimArraySetAt(obj, SwimToInt(argv[0]), v);
        return;
    }
    if (k == SWIM_KIND_DICT) {
        SwimDictSet(obj, argv[0], v);
        return;
    }
    for (SwimType* cur = obj->type; cur != NULL; cur = (SwimType*)cur->parent) {
        for (int i = 0; i < cur->method_count; i++) {
            SwimMethodEntry* e = &cur->methods[i];
            if (strcmp(e->name, "__sub_set") != 0) continue;
            SwimValue* args = (SwimValue*)calloc((size_t)argc + 1,
                                                 sizeof(SwimValue));
            for (int j = 0; j < argc; j++) args[j] = argv[j];
            args[argc] = v;
            SwimValue r = swim_invoke_args(e->fn, e->defaults, obj, 1, e->params,
                                           e->nparams, e->variadic, e->labels, slab,
                                           argc + 1, args);
            free(args);
            if (r) SwimRelease(r);
            return;
        }
    }
    SwimFatalFmt("type '%s' has no subscript setter", obj->type->name);
}

/* ================================================================== */
/* Optional chaining                                                   */
/* ================================================================== */
SwimValue SwimOptionalMember(SwimValue opt, const char* name) {
    if (!SwimIsSome(opt)) return SwimNone();
    SwimValue inner = SwimOptionalGet(opt);
    SwimValue r = SwimGetMember(inner, name);
    r = SwimDeref(r);
    if (r && r->type->kind == SWIM_KIND_OPTIONAL) {
        SwimRetain(r);
        return r;
    }
    return SwimSome(r);
}
SwimValue SwimOptionalCall(SwimValue opt, const char* name, const char* labels,
                           int argc, SwimValue* argv) {
    if (!SwimIsSome(opt)) return SwimNone();
    SwimValue inner = SwimOptionalGet(opt);
    SwimValue r = SwimInvokeMethod(inner, name, labels, argc, argv);
    r = SwimDeref(r);
    if (r && r->type->kind == SWIM_KIND_OPTIONAL) { SwimRetain(r); return r; }
    return SwimSome(r);
}
SwimValue SwimOptionalSubscript(SwimValue opt, int argc, SwimValue* argv) {
    if (!SwimIsSome(opt)) return SwimNone();
    SwimValue inner = SwimOptionalGet(opt);
    SwimValue r = SwimSubscriptGet(inner, argc, argv);
    r = SwimDeref(r);
    if (r && r->type->kind == SWIM_KIND_OPTIONAL) { SwimRetain(r); return r; }
    return SwimSome(r);
}

/* ================================================================== */
/* Bindings (method / function references as values)                   */
/* ================================================================== */
static SwimValue swim_bound_trampoline(SwimFrame* up, int argc,
                                       SwimValue* argv) {
    /* env slots: 0 = receiver, 1 = name, 2 = labels, 3 = mode */
    SwimValue receiver = SwimFrameGet(up, 0);
    SwimValue namev = SwimFrameGet(up, 1);
    SwimValue labelsv = SwimFrameGet(up, 2);
    SwimValue modev = SwimFrameGet(up, 3);
    const char* name = namev ? ((SwimStringObj*)SwimDeref(namev))->data : "";
    const char* labels = labelsv ? ((SwimStringObj*)SwimDeref(labelsv))->data
                                 : "";
    int mode = modev ? (int)SwimUnboxInt(modev) : 0;
    SwimValue result;
    if (mode == 0) {
        result = SwimCallMethod(receiver, name, labels, argc, argv);
    } else if (mode == 1) {
        result = SwimCallStatic(((SwimTypeObj*)receiver)->target, name, labels,
                                argc, argv);
    } else {
        result = SwimCallGlobal(name, labels, argc, argv);
    }
    SwimRelease(receiver);
    SwimRelease(namev);
    SwimRelease(labelsv);
    SwimRelease(modev);
    return result;
}
static SwimValue swim_make_binding(SwimValue receiver, const char* name,
                                   const char* labels, int mode) {
    SwimFrame* env = SwimFrameNew(NULL, 4);
    if (receiver) SwimFrameSetRef(env, 0, receiver);
    SwimFrameSetRef(env, 1, SwimCStr(name));
    SwimFrameSetRef(env, 2, SwimCStr(labels ? labels : ""));
    SwimFrameSetRef(env, 3, SwimInt(mode));
    SwimValue closure = SwimMakeClosure(swim_bound_trampoline, env);
    SwimRelease((SwimValue)env);
    return closure;
}
SwimValue SwimBindMethod(SwimValue obj, const char* name, const char* labels) {
    return swim_make_binding(obj, name, labels, 0);
}
SwimValue SwimBindStatic(SwimType* t, const char* name, const char* labels) {
    return swim_make_binding(SwimTypeValue(t), name, labels, 1);
}
SwimValue SwimBindGlobalFn(const char* name, const char* labels) {
    return swim_make_binding(NULL, name, labels, 2);
}

/* ================================================================== */
/* Operators                                                           */
/* ================================================================== */
SwimFn SwimFindOperator(const char* fixity, const char* symbol, int argc,
                        SwimValue* argv) {
    for (int i = 0; i < SwimOperatorsCount; i++) {
        SwimOperatorEntry* e = &SwimOperatorsTable[i];
        if (strcmp(e->fixity, fixity) != 0) continue;
        if (strcmp(e->symbol, symbol) != 0) continue;
        if (e->nparams != argc) continue;
        int ok = 1;
        for (int j = 0; j < argc; j++) {
            if (e->params && e->params[j] &&
                !swim_type_compatible(argv[j], (SwimType*)e->params[j])) {
                ok = 0;
                break;
            }
        }
        if (ok) return e->fn;
    }
    return NULL;
}

/* ================================================================== */
/* Program start-up                                                    */
/* ================================================================== */
static int swim_argc = 0;
static char** swim_argv = NULL;
void SwimProgramStart(int argc, char** argv) {
    swim_argc = argc;
    swim_argv = argv;
}
void SwimProgramFinish(void) {}
int SwimProgramArgc(void) { return swim_argc; }
char** SwimProgramArgv(void) { return swim_argv; }
