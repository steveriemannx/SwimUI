/* swimrt_error.c -- exceptions (setjmp based) and `defer` scopes. */
#include "swimrt_internal.h"

#include <stdlib.h>
#include <string.h>
#include <stdio.h>

static SwimTryFrame* swim_try_top = NULL;
static SwimDeferScope* swim_defer_top = NULL;

void SwimTryBegin(SwimTryFrame* f) {
    f->prev = swim_try_top;
    f->error = NULL;
    f->defer_top = swim_defer_top;
    swim_try_top = f;
}
void SwimTryEnd(SwimTryFrame* f) {
    if (swim_try_top == f) swim_try_top = f->prev;
}

void SwimDeferBegin(SwimDeferScope* s) {
    s->prev = swim_defer_top;
    s->count = 0;
    s->cap = 0;
    s->blocks = NULL;
    swim_defer_top = s;
}
void SwimDeferAdd(SwimDeferScope* s, SwimValue closure) {
    if (s->count >= s->cap) {
        int nc = s->cap ? s->cap * 2 : 4;
        s->blocks = (SwimValue*)realloc(s->blocks,
                                        (size_t)nc * sizeof(SwimValue));
        if (!s->blocks) { fprintf(stderr, "swim: out of memory\n"); exit(1); }
        s->cap = nc;
    }
    if (closure) SwimRetain(closure);
    s->blocks[s->count++] = closure;
}
void SwimDeferRun(SwimDeferScope* s) {
    if (s == NULL) return;
    if (swim_defer_top == s) swim_defer_top = s->prev;
    for (int i = s->count - 1; i >= 0; i--) {
        SwimValue block = s->blocks[i];
        if (block) {
            SwimValue r = SwimCallValue(block, 0, NULL);
            if (r) SwimRelease(r);
            SwimRelease(block);
        }
    }
    s->count = 0;
    free(s->blocks);
    s->blocks = NULL;
    s->cap = 0;
}
void SwimDeferScopeCleanup(SwimDeferScope* s) { SwimDeferRun(s); }

static void swim_run_defers_until(SwimDeferScope* stop) {
    while (swim_defer_top != NULL && swim_defer_top != stop) {
        SwimDeferScope* s = swim_defer_top;
        SwimDeferRun(s);
    }
}

void SwimThrow(SwimValue err) {
    /* Run pending deferred blocks in scopes being unwound. */
    if (swim_try_top == NULL) {
        SwimValue d = SwimStr(err);
        fflush(stdout);
        fputs("Error: unhandled exception: ", stderr);
        fwrite(((SwimStringObj*)d)->data, 1, (size_t)((SwimStringObj*)d)->len,
               stderr);
        fputc('\n', stderr);
        exit(1);
    }
    swim_run_defers_until(swim_try_top->defer_top);
    SwimTryFrame* f = swim_try_top;
    swim_try_top = f->prev;
    f->error = err;
    longjmp(f->buf, 1);
}

void SwimRethrow(void) { SwimThrow(NULL); }

SwimValue SwimErrorMake(SwimType* t) {
    if (t->kind == SWIM_KIND_CLASS) {
        SwimObjectObj* o = (SwimObjectObj*)swim_alloc(t, sizeof(SwimObjectObj));
        o->h.type = t;
        o->n = t->field_count;
        o->slots = t->field_count
                       ? (SwimValue*)calloc((size_t)t->field_count,
                                            sizeof(SwimValue))
                       : NULL;
        return (SwimValue)o;
    }
    if (t->kind == SWIM_KIND_ENUM) {
        SwimEnumObj* e = (SwimEnumObj*)swim_alloc(t, sizeof(SwimEnumObj));
        e->h.type = t;
        e->tag = 0;
        e->n = 0;
        e->slots = NULL;
        return (SwimValue)e;
    }
    SwimObjectObj* o = (SwimObjectObj*)swim_alloc(t, sizeof(SwimObjectObj));
    o->h.type = t;
    o->n = t->field_count;
    o->slots = t->field_count
                   ? (SwimValue*)calloc((size_t)t->field_count,
                                        sizeof(SwimValue))
                   : NULL;
    return (SwimValue)o;
}
SwimValue SwimErrorMakeMsg(SwimType* t, SwimValue msg) {
    SwimValue e = SwimErrorMake(t);
    (void)msg;
    return e;
}
void SwimThrowError(SwimType* t, const char* msg) {
    SwimFatalFmt("%s", msg);
}

int SwimValueIsErrorType(SwimValue v, SwimType* t) {
    v = SwimDeref(v);
    if (!v) return 0;
    if (t == NULL) return 1;
    SwimType* cur = v->type;
    if (cur->kind == SWIM_KIND_CLASS) {
        while (cur) {
            if (cur == t) return 1;
            cur = (SwimType*)cur->parent;
        }
        return 0;
    }
    return cur == t;
}
