/* swimferroui.c -- the C shim of the FerroUI native module of Swim.
 *
 * See swimferroui.h for what this is and ffi/include/ferroui_swim.h for the
 * C ABI of the Rust bridge it calls.  Every function converts the dynamic
 * `SwimValue`s of the generated program to the flat values of the bridge and
 * back; nothing here knows about the layout of the UI.
 */

#include "swimferroui.h"
#include "ferroui_swim.h"

#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

/* The compile-time configuration the bridge is checked against. */
static const int swimferroui_expected_abi = FERRO_SWIM_ABI_VERSION;

/* A `() -> Void` closure of the program, kept alive for as long as the bridge
 * holds the callback.  A cell is never freed: the application lives until its
 * window closes, and the callbacks it registered live just as long. */
typedef struct SwimFerroClosure {
    SwimValue fn;
} SwimFerroClosure;

static void swimferroui_report(const char *where) {
    const char *error = ferro_swim_last_error();
    if (error != NULL && error[0] != '\0') {
        fprintf(stderr, "swimferroui: %s: %s\n", where, error);
        fflush(stderr);
    }
}

static SwimFerroClosure *swimferroui_keep(SwimValue fn) {
    SwimFerroClosure *cell = (SwimFerroClosure *)calloc(1, sizeof(*cell));
    if (cell == NULL) return NULL;
    cell->fn = fn;
    SwimRetain(fn);
    return cell;
}

/* The `ferro_swim_cb` the bridge calls: run the Swim closure it stands for. */
static void swimferroui_invoke(int64_t user) {
    SwimFerroClosure *cell = (SwimFerroClosure *)(intptr_t)user;
    if (cell == NULL || cell->fn == NULL) return;
    SwimValue result = SwimCallValue(cell->fn, 0, NULL);
    SwimRelease(result);
}

static void swimferroui_subscribe(int64_t handle, int32_t event, SwimValue action,
                                  const char *where) {
    if (action == NULL) return;
    SwimFerroClosure *cell = swimferroui_keep(action);
    if (cell == NULL) return;
    ferro_swim_on(handle, event, swimferroui_invoke, (int64_t)(intptr_t)cell);
    swimferroui_report(where);
}

static int64_t swimferroui_int(SwimValue value) {
    return (int64_t)SwimUnboxInt(value);
}

static double swimferroui_double(SwimValue value) {
    return SwimUnboxDouble(value);
}

static int32_t swimferroui_i32(SwimValue value) {
    return (int32_t)SwimUnboxInt(value);
}

static int swimferroui_bool(SwimValue value) {
    return SwimUnboxBool(value) ? 1 : 0;
}

/* The bytes of a Swim string, NUL terminated and owned by the caller. */
static char *swimferroui_cstr(SwimValue value) {
    int64_t len = SwimStringLen(value);
    const char *data = SwimStringData(value);
    char *out = (char *)malloc((size_t)len + 1);
    if (out == NULL) return NULL;
    if (len > 0 && data != NULL) memcpy(out, data, (size_t)len);
    out[len] = '\0';
    return out;
}

/* 0xRRGGBB (opaque) or 0xAARRGGBB; a negative value leaves the brush unset. */
static uint32_t swimferroui_argb(int64_t color) {
    if (color > 0xFFFFFF) return (uint32_t)(color & 0xFFFFFFFF);
    return 0xFF000000u | (uint32_t)(color & 0xFFFFFF);
}

static SwimValue swimferroui_string(const char *bytes) {
    if (bytes == NULL) return SwimCStr("");
    return SwimCStr(bytes);
}

/* -- the application ----------------------------------------------------- */

SwimValue swimferroui_run(SwimValue build) {
    int abi = ferro_swim_abi_version();
    if (abi != swimferroui_expected_abi) {
        fprintf(stderr,
                "swimferroui: the FerroUI bridge has ABI version %d, this "
                "runtime needs %d; rebuild it with scripts/build-ffi.sh\n",
                abi, swimferroui_expected_abi);
        fflush(stderr);
        exit(1);
    }
    SwimFerroClosure *cell = swimferroui_keep(build);
    ferro_swim_run(swimferroui_invoke, (int64_t)(intptr_t)cell);
    swimferroui_report("run");
    return SwimVoid();
}

SwimValue swimferroui_quit(void) {
    ferro_swim_quit();
    swimferroui_report("quit");
    return SwimVoid();
}

SwimValue swimferroui_after(SwimValue ms, SwimValue action) {
    if (action != NULL) {
        SwimFerroClosure *cell = swimferroui_keep(action);
        if (cell != NULL) {
            ferro_swim_after(swimferroui_double(ms), swimferroui_invoke,
                             (int64_t)(intptr_t)cell);
            swimferroui_report("after");
        }
    }
    return SwimVoid();
}

SwimValue swimferroui_log(SwimValue message) {
    char *text = swimferroui_cstr(message);
    if (text != NULL) {
        fprintf(stderr, "%s\n", text);
        fflush(stderr);
        free(text);
    }
    return SwimVoid();
}

SwimValue swimferroui_version(void) {
    return swimferroui_string(ferro_swim_version());
}

SwimValue swimferroui_set_theme_variant(SwimValue name) {
    char *text = swimferroui_cstr(name);
    if (text != NULL) {
        ferro_swim_set_theme_variant(text);
        free(text);
        swimferroui_report("set theme variant");
    }
    return SwimVoid();
}

/* -- tests and documentation --------------------------------------------- */

SwimValue swimferroui_image_path(void) {
    const char *path = getenv("SWIMUI_IMAGE");
    return swimferroui_string(path != NULL ? path : "");
}

SwimValue swimferroui_auto_quit_ms(void) {
    const char *value = getenv("SWIMUI_QUIT_MS");
    return SwimInt(value != NULL ? (int64_t)atoll(value) : 0);
}

SwimValue swimferroui_snapshot(SwimValue delay_ms, SwimValue path) {
    char *text = swimferroui_cstr(path);
    if (text != NULL) {
        ferro_swim_snapshot(swimferroui_double(delay_ms), text);
        swimferroui_report("snapshot");
        free(text);
    }
    return SwimVoid();
}

/* -- the window ----------------------------------------------------------- */

SwimValue swimferroui_window(SwimValue width, SwimValue height, SwimValue title,
                             SwimValue background, SwimValue on_closed) {
    char *text = swimferroui_cstr(title);
    int64_t handle = ferro_swim_window(swimferroui_double(width),
                                       swimferroui_double(height));
    swimferroui_report("window");
    if (text != NULL) {
        ferro_swim_set_str(handle, FERRO_SWIM_STR_TITLE, text);
        free(text);
        swimferroui_report("window title");
    }
    if (swimferroui_int(background) >= 0) {
        ferro_swim_set_color(handle, FERRO_SWIM_COLOR_BACKGROUND,
                             swimferroui_argb(swimferroui_int(background)));
        swimferroui_report("window background");
    }
    swimferroui_subscribe(handle, FERRO_SWIM_EVENT_CLOSED, on_closed,
                          "window closed");
    return SwimInt(handle);
}

SwimValue swimferroui_client_width(void) {
    return SwimInt((int64_t)ferro_swim_client_width());
}

SwimValue swimferroui_client_height(void) {
    return SwimInt((int64_t)ferro_swim_client_height());
}

SwimValue swimferroui_set_decorations(SwimValue window, SwimValue mode) {
    ferro_swim_set_decorations(swimferroui_int(window),
                               swimferroui_i32(mode));
    swimferroui_report("set decorations");
    return SwimVoid();
}

SwimValue swimferroui_on_ready(SwimValue window, SwimValue on_ready) {
    swimferroui_subscribe(swimferroui_int(window), FERRO_SWIM_EVENT_OPENED,
                          on_ready, "on ready");
    return SwimVoid();
}

SwimValue swimferroui_close(SwimValue window) {
    ferro_swim_close(swimferroui_int(window));
    swimferroui_report("close");
    return SwimVoid();
}

/* -- the tree ------------------------------------------------------------- */

SwimValue swimferroui_create(SwimValue parent, SwimValue kind) {
    int64_t handle = ferro_swim_create(swimferroui_i32(kind),
                                       swimferroui_int(parent));
    swimferroui_report("create");
    return SwimInt(handle);
}

SwimValue swimferroui_add_child(SwimValue parent, SwimValue child) {
    ferro_swim_add_child(swimferroui_int(parent), swimferroui_int(child));
    swimferroui_report("add child");
    return SwimVoid();
}

SwimValue swimferroui_insert_child(SwimValue parent, SwimValue index,
                                   SwimValue child) {
    ferro_swim_insert_child(swimferroui_int(parent), swimferroui_i32(index),
                            swimferroui_int(child));
    swimferroui_report("insert child");
    return SwimVoid();
}

SwimValue swimferroui_remove_child(SwimValue parent, SwimValue child) {
    ferro_swim_remove_child(swimferroui_int(parent), swimferroui_int(child));
    swimferroui_report("remove child");
    return SwimVoid();
}

SwimValue swimferroui_clear_children(SwimValue parent) {
    ferro_swim_clear_children(swimferroui_int(parent));
    swimferroui_report("clear children");
    return SwimVoid();
}

SwimValue swimferroui_destroy(SwimValue handle) {
    ferro_swim_destroy(swimferroui_int(handle));
    swimferroui_report("destroy");
    return SwimVoid();
}

/* -- properties ----------------------------------------------------------- */

SwimValue swimferroui_set_f64(SwimValue handle, SwimValue property,
                              SwimValue value) {
    ferro_swim_set_f64(swimferroui_int(handle), swimferroui_i32(property),
                       swimferroui_double(value));
    swimferroui_report("set f64");
    return SwimVoid();
}

SwimValue swimferroui_set_i32(SwimValue handle, SwimValue property,
                              SwimValue value) {
    ferro_swim_set_i32(swimferroui_int(handle), swimferroui_i32(property),
                       swimferroui_i32(value));
    swimferroui_report("set i32");
    return SwimVoid();
}

SwimValue swimferroui_set_string(SwimValue handle, SwimValue property,
                                 SwimValue value) {
    char *text = swimferroui_cstr(value);
    if (text != NULL) {
        ferro_swim_set_str(swimferroui_int(handle), swimferroui_i32(property),
                           text);
        swimferroui_report("set string");
        free(text);
    }
    return SwimVoid();
}

SwimValue swimferroui_set_bool(SwimValue handle, SwimValue property,
                               SwimValue value) {
    ferro_swim_set_bool(swimferroui_int(handle), swimferroui_i32(property),
                        swimferroui_bool(value));
    swimferroui_report("set bool");
    return SwimVoid();
}

SwimValue swimferroui_set_color(SwimValue handle, SwimValue property,
                                SwimValue argb) {
    int64_t color = swimferroui_int(argb);
    if (color >= 0) {
        ferro_swim_set_color(swimferroui_int(handle),
                             swimferroui_i32(property),
                             swimferroui_argb(color));
        swimferroui_report("set color");
    }
    return SwimVoid();
}

SwimValue swimferroui_set_thickness(SwimValue handle, SwimValue property,
                                    SwimValue left, SwimValue top,
                                    SwimValue right, SwimValue bottom) {
    ferro_swim_set_thickness(swimferroui_int(handle),
                             swimferroui_i32(property),
                             swimferroui_double(left),
                             swimferroui_double(top),
                             swimferroui_double(right),
                             swimferroui_double(bottom));
    swimferroui_report("set thickness");
    return SwimVoid();
}

SwimValue swimferroui_set_enum(SwimValue handle, SwimValue property,
                               SwimValue value) {
    ferro_swim_set_enum(swimferroui_int(handle), swimferroui_i32(property),
                        swimferroui_i32(value));
    swimferroui_report("set enum");
    return SwimVoid();
}

SwimValue swimferroui_set_flex(SwimValue handle, SwimValue direction,
                               SwimValue justify, SwimValue align,
                               SwimValue column_spacing,
                               SwimValue row_spacing) {
    ferro_swim_set_flex(swimferroui_int(handle), swimferroui_i32(direction),
                        swimferroui_i32(justify), swimferroui_i32(align),
                        swimferroui_double(column_spacing),
                        swimferroui_double(row_spacing));
    swimferroui_report("set flex");
    return SwimVoid();
}

SwimValue swimferroui_set_grow(SwimValue handle, SwimValue grow) {
    ferro_swim_set_grow(swimferroui_int(handle), swimferroui_double(grow));
    swimferroui_report("set grow");
    return SwimVoid();
}

SwimValue swimferroui_set_frame(SwimValue handle, SwimValue x, SwimValue y,
                                SwimValue width, SwimValue height) {
    ferro_swim_set_frame(swimferroui_int(handle), swimferroui_double(x),
                         swimferroui_double(y), swimferroui_double(width),
                         swimferroui_double(height));
    swimferroui_report("set frame");
    return SwimVoid();
}

/* -- events --------------------------------------------------------------- */

SwimValue swimferroui_on_tap(SwimValue handle, SwimValue action) {
    swimferroui_subscribe(swimferroui_int(handle), FERRO_SWIM_EVENT_TAP,
                          action, "on tap");
    return SwimVoid();
}

SwimValue swimferroui_on_text_changed(SwimValue handle, SwimValue action) {
    swimferroui_subscribe(swimferroui_int(handle),
                          FERRO_SWIM_EVENT_TEXT_CHANGED, action,
                          "on text changed");
    return SwimVoid();
}

SwimValue swimferroui_on_checked_changed(SwimValue handle, SwimValue action) {
    swimferroui_subscribe(swimferroui_int(handle),
                          FERRO_SWIM_EVENT_CHECKED_CHANGED, action,
                          "on checked changed");
    return SwimVoid();
}

SwimValue swimferroui_on_value_changed(SwimValue handle, SwimValue action) {
    swimferroui_subscribe(swimferroui_int(handle),
                          FERRO_SWIM_EVENT_VALUE_CHANGED, action,
                          "on value changed");
    return SwimVoid();
}

/* -- reading values back -------------------------------------------------- */

SwimValue swimferroui_get_value(SwimValue handle) {
    double value = ferro_swim_get_f64(swimferroui_int(handle),
                                      FERRO_SWIM_F64_VALUE);
    swimferroui_report("get value");
    return SwimDouble(value);
}

SwimValue swimferroui_get_text(SwimValue handle) {
    const char *text = ferro_swim_get_str(swimferroui_int(handle),
                                          FERRO_SWIM_STR_TEXT);
    swimferroui_report("get text");
    return swimferroui_string(text);
}

SwimValue swimferroui_get_checked(SwimValue handle) {
    int checked = ferro_swim_get_bool(swimferroui_int(handle),
                                      FERRO_SWIM_BOOL_IS_CHECKED);
    swimferroui_report("get checked");
    return SwimBool(checked != 0);
}

SwimValue swimferroui_get_visible(SwimValue handle) {
    int visible = ferro_swim_get_bool(swimferroui_int(handle),
                                      FERRO_SWIM_BOOL_IS_VISIBLE);
    swimferroui_report("get visible");
    return SwimBool(visible != 0);
}

/* -- tests ---------------------------------------------------------------- */

SwimValue swimferroui_raise_click(SwimValue handle) {
    ferro_swim_raise_click(swimferroui_int(handle));
    swimferroui_report("raise click");
    return SwimVoid();
}
