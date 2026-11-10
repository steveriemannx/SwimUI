/* swimferroui.h -- the C shim of the FerroUI native module of Swim.
 *
 * A `.sw` source that writes `import FerroUI` calls the `ferroui*` free
 * functions; the compiler knows them from `src/swimc/native_ferroui.py` and
 * emits calls to the `swimferroui_*` functions declared here.  This shim turns
 * the dynamic `SwimValue`s of the generated program into the flat C ABI of the
 * Rust bridge (`ferro_swim_*`, ffi/include/ferroui_swim.h), and the values the
 * bridge returns back into `SwimValue`s.
 *
 * Why a shim at all: the generated program speaks `SwimValue` (an untyped,
 * reference-counted object), while the bridge speaks numbers, C strings and
 * plain C function pointers.  The shim is also where closures cross: a
 * `() -> Void` closure of the program becomes a `ferro_swim_cb` plus an
 * opaque id, and the bridge calls it back on the UI thread.
 *
 * The shim is compiled into every program that imports the module
 * (`runtime/swimferroui.c`, added by the compiler); the Rust bridge is a
 * shared library built once with `scripts/build-ffi.sh` into `build/`.
 *
 * Keep this file in sync with `src/swimc/native_ferroui.py`.
 */
#ifndef SWIMFErroui_H
#define SWIMFErroui_H

#include "swimrt.h"

#ifdef __cplusplus
extern "C" {
#endif

/* -- the application ----------------------------------------------------- */
SwimValue swimferroui_run(SwimValue build);
SwimValue swimferroui_quit(void);
SwimValue swimferroui_after(SwimValue ms, SwimValue action);
SwimValue swimferroui_log(SwimValue message);
SwimValue swimferroui_version(void);
SwimValue swimferroui_set_theme_variant(SwimValue name);

/* -- tests and documentation --------------------------------------------- */
SwimValue swimferroui_image_path(void);
SwimValue swimferroui_auto_quit_ms(void);
SwimValue swimferroui_snapshot(SwimValue delay_ms, SwimValue path);

/* -- the window ----------------------------------------------------------- */
SwimValue swimferroui_window(SwimValue width, SwimValue height,
                             SwimValue title, SwimValue background,
                             SwimValue on_closed);
SwimValue swimferroui_client_width(void);
SwimValue swimferroui_client_height(void);
SwimValue swimferroui_set_decorations(SwimValue window, SwimValue mode);
SwimValue swimferroui_on_ready(SwimValue window, SwimValue on_ready);
SwimValue swimferroui_close(SwimValue window);

/* -- the tree ------------------------------------------------------------- */
SwimValue swimferroui_create(SwimValue parent, SwimValue kind);
SwimValue swimferroui_add_child(SwimValue parent, SwimValue child);
SwimValue swimferroui_insert_child(SwimValue parent, SwimValue index,
                                   SwimValue child);
SwimValue swimferroui_remove_child(SwimValue parent, SwimValue child);
SwimValue swimferroui_clear_children(SwimValue parent);
SwimValue swimferroui_destroy(SwimValue handle);

/* -- properties ----------------------------------------------------------- */
SwimValue swimferroui_set_f64(SwimValue handle, SwimValue property,
                              SwimValue value);
SwimValue swimferroui_set_i32(SwimValue handle, SwimValue property,
                              SwimValue value);
SwimValue swimferroui_set_string(SwimValue handle, SwimValue property,
                                 SwimValue value);
SwimValue swimferroui_set_bool(SwimValue handle, SwimValue property,
                               SwimValue value);
SwimValue swimferroui_set_color(SwimValue handle, SwimValue property,
                                SwimValue argb);
SwimValue swimferroui_set_thickness(SwimValue handle, SwimValue property,
                                    SwimValue left, SwimValue top,
                                    SwimValue right, SwimValue bottom);
SwimValue swimferroui_set_enum(SwimValue handle, SwimValue property,
                               SwimValue value);
SwimValue swimferroui_set_flex(SwimValue handle, SwimValue direction,
                               SwimValue justify, SwimValue align,
                               SwimValue column_spacing,
                               SwimValue row_spacing);
SwimValue swimferroui_set_grow(SwimValue handle, SwimValue grow);
SwimValue swimferroui_set_frame(SwimValue handle, SwimValue x, SwimValue y,
                                SwimValue width, SwimValue height);

/* -- events --------------------------------------------------------------- */
SwimValue swimferroui_on_tap(SwimValue handle, SwimValue action);
SwimValue swimferroui_on_text_changed(SwimValue handle, SwimValue action);
SwimValue swimferroui_on_checked_changed(SwimValue handle, SwimValue action);
SwimValue swimferroui_on_value_changed(SwimValue handle, SwimValue action);

/* -- reading values back -------------------------------------------------- */
SwimValue swimferroui_get_value(SwimValue handle);
SwimValue swimferroui_get_text(SwimValue handle);
SwimValue swimferroui_get_checked(SwimValue handle);
SwimValue swimferroui_get_visible(SwimValue handle);

/* -- tests ---------------------------------------------------------------- */
SwimValue swimferroui_raise_click(SwimValue handle);

#ifdef __cplusplus
}
#endif

#endif /* SWIMFErroui_H */
