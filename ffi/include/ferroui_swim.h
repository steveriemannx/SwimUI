/*
 * ferroui_swim.h -- the C ABI of the FerroUI native module of Swim (SwimUI).
 *
 * The generated Nim program of a `.sw` source that writes `import FerroUI`
 * calls these functions (through `runtime/swimferroui.nim`).  The bridge is a
 * shared library built from the Rust crate in this directory; it owns the
 * FerroUI application, the visual tree and the native window, and it refers to
 * every live control with an opaque 64-bit handle.
 *
 * All calls are made on the thread that called ferro_swim_run: the main thread
 * of the process, which is the UI thread of FerroUI.
 */
#ifndef FERROUI_SWIM_H
#define FERROUI_SWIM_H

#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

/* The version of this ABI; the Nim module refuses a library that disagrees. */
#define FERRO_SWIM_ABI_VERSION 1

/* The kind of a control (ferro_swim_create). */
enum
{
    FERRO_SWIM_KIND_CANVAS = 1,
    FERRO_SWIM_KIND_STACK_PANEL = 2,
    FERRO_SWIM_KIND_BORDER = 3,
    FERRO_SWIM_KIND_TEXT_BLOCK = 4,
    FERRO_SWIM_KIND_BUTTON = 5,
    FERRO_SWIM_KIND_TEXT_BOX = 6,
    FERRO_SWIM_KIND_CHECK_BOX = 7,
    FERRO_SWIM_KIND_SLIDER = 8,
    FERRO_SWIM_KIND_PROGRESS_BAR = 9,
    FERRO_SWIM_KIND_SCROLL_VIEWER = 10
};

/* A double property (ferro_swim_set_f64). */
enum
{
    FERRO_SWIM_F64_WIDTH = 1,
    FERRO_SWIM_F64_HEIGHT = 2,
    FERRO_SWIM_F64_MIN_WIDTH = 3,
    FERRO_SWIM_F64_MIN_HEIGHT = 4,
    FERRO_SWIM_F64_MAX_WIDTH = 5,
    FERRO_SWIM_F64_MAX_HEIGHT = 6,
    FERRO_SWIM_F64_FONT_SIZE = 7,
    FERRO_SWIM_F64_OPACITY = 8,
    FERRO_SWIM_F64_CORNER_RADIUS = 9,
    FERRO_SWIM_F64_SPACING = 10,
    FERRO_SWIM_F64_MINIMUM = 11,
    FERRO_SWIM_F64_MAXIMUM = 12,
    FERRO_SWIM_F64_VALUE = 13,
    FERRO_SWIM_F64_LINE_HEIGHT = 14
};

/* A string property (ferro_swim_set_str). */
enum
{
    FERRO_SWIM_STR_TEXT = 1,
    FERRO_SWIM_STR_TITLE = 2,
    FERRO_SWIM_STR_WATERMARK = 3,
    FERRO_SWIM_STR_CONTENT = 4
};

/* A boolean property (ferro_swim_set_bool). */
enum
{
    FERRO_SWIM_BOOL_IS_VISIBLE = 1,
    FERRO_SWIM_BOOL_IS_CHECKED = 2,
    FERRO_SWIM_BOOL_IS_INDETERMINATE = 3,
    FERRO_SWIM_BOOL_IS_ENABLED = 4
};

/* A brush property (ferro_swim_set_color); the value is 0xAARRGGBB. */
enum
{
    FERRO_SWIM_COLOR_BACKGROUND = 1,
    FERRO_SWIM_COLOR_FOREGROUND = 2,
    FERRO_SWIM_COLOR_BORDER = 3
};

/* A thickness property (ferro_swim_set_thickness). */
enum
{
    FERRO_SWIM_THICKNESS_MARGIN = 1,
    FERRO_SWIM_THICKNESS_PADDING = 2,
    FERRO_SWIM_THICKNESS_BORDER = 3
};

/* An enum property (ferro_swim_set_enum). */
enum
{
    FERRO_SWIM_ENUM_HORIZONTAL_ALIGNMENT = 1,
    FERRO_SWIM_ENUM_VERTICAL_ALIGNMENT = 2,
    FERRO_SWIM_ENUM_ORIENTATION = 3,
    FERRO_SWIM_ENUM_TEXT_ALIGNMENT = 4,
    FERRO_SWIM_ENUM_TEXT_WRAPPING = 5,
    FERRO_SWIM_ENUM_FONT_WEIGHT = 6,
    FERRO_SWIM_ENUM_FONT_STYLE = 7
};

/* An event (ferro_swim_on). */
enum
{
    FERRO_SWIM_EVENT_TAP = 1,
    FERRO_SWIM_EVENT_TEXT_CHANGED = 2,
    FERRO_SWIM_EVENT_CHECKED_CHANGED = 3,
    FERRO_SWIM_EVENT_VALUE_CHANGED = 4,
    FERRO_SWIM_EVENT_OPENED = 5,
    FERRO_SWIM_EVENT_CLOSED = 6
};

/* A `ferro_swim_cb` receives the `user` value it was registered with. */
typedef void (*ferro_swim_cb)(int64_t user);

/* The ABI version and the version of the bridge and of FerroUI. */
int32_t ferro_swim_abi_version(void);
const char *ferro_swim_version(void);

/* What the last call of this thread failed with; "" after a successful call. */
const char *ferro_swim_last_error(void);

/* Starts the application and blocks until it exits. `ready` runs once the
 * framework is initialized; the `.sw` program builds the window there. */
void ferro_swim_run(ferro_swim_cb ready, int64_t user);

/* Ends the application: the window closes and ferro_swim_run returns. */
void ferro_swim_quit(void);

/* Creates the main window (only inside `ready`). */
int64_t ferro_swim_window(double width, double height);

/* Creates a control of `kind`; `parent` may be 0 and be set later. */
int64_t ferro_swim_create(int32_t kind, int64_t parent);

/* The client area of the main window: what the layout of a program has to fit
 * in, which is smaller than the requested size when the decorations or the
 * screen take room from it. 0 while there is no window. */
double ferro_swim_client_width(void);
double ferro_swim_client_height(void);

/* The theme variant of the application: "dark", "light" or anything else to
 * follow the system.  Call it before ferro_swim_run. */
void ferro_swim_set_theme_variant(const char *name);

/* The decorations of a window: 0 none, 1 border only, 2 full. */
void ferro_swim_set_decorations(int64_t handle, int32_t mode);

/* Adds a control to a panel or sets it as the content of a content control
 * (window, border, button, scroll viewer); `parent` 0 is a no-op. */
void ferro_swim_add_child(int64_t parent, int64_t child);

void ferro_swim_set_f64(int64_t handle, int32_t property, double value);
void ferro_swim_set_str(int64_t handle, int32_t property, const char *value);
void ferro_swim_set_bool(int64_t handle, int32_t property, int32_t value);
void ferro_swim_set_color(int64_t handle, int32_t property, uint32_t argb);
void ferro_swim_set_thickness(int64_t handle, int32_t property, double left, double top, double right, double bottom);
void ferro_swim_set_enum(int64_t handle, int32_t property, int32_t value);

/* Reads a property back; a failing read is 0 or "", see
 * ferro_swim_last_error.  The string of ferro_swim_get_str is valid until the
 * next call of it on this thread. */
double ferro_swim_get_f64(int64_t handle, int32_t property);
const char *ferro_swim_get_str(int64_t handle, int32_t property);
int32_t ferro_swim_get_bool(int64_t handle, int32_t property);

/* Sets the size and, when the control is a child of a canvas, its position. */
void ferro_swim_set_frame(int64_t handle, double x, double y, double width, double height);

/* Subscribes to an event; the subscription lives until the application ends. */
void ferro_swim_on(int64_t handle, int32_t event, ferro_swim_cb cb, int64_t user);

/* Closes the main window. */
void ferro_swim_close(int64_t handle);

/* Writes a PNG of the main window to `path` after `delay_ms` (as the layout
 * and the styles settle). */
void ferro_swim_snapshot(double delay_ms, const char *path);

/* Raises the click event of a button, as a pointer would; the program's own
 * handlers run, so a program can drive its controls in a test. */
void ferro_swim_raise_click(int64_t handle);

/* Releases a handle. The control stays alive while the visual tree holds it;
 * a handle of the window stays valid until the application ends. */
void ferro_swim_release(int64_t handle);

#ifdef __cplusplus
}
#endif

#endif /* FERROUI_SWIM_H */
