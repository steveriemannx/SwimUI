//! `ferroui-swim` -- the C ABI behind the FerroUI native module of Swim.
//!
//! The Swim compiler emits `import swimferroui` for a `.sw` source that writes
//! `import FerroUI`; the Nim module in `runtime/` declares these functions with
//! `{.importc, cdecl, dynlib.}` and wraps them behind a small, Swift-friendly
//! surface of `Int` handles.  This crate is the other side: it owns the
//! FerroUI application and the visual tree, refers to every live control with
//! an opaque 64-bit handle and reports what failed through
//! [`ferro_swim_last_error`].
//!
//! The ABI is documented in `include/ferroui_swim.h`; it is a flat one because
//! a `.sw` source never mentions a Rust or a Nim type.  All calls are made on
//! the thread that called [`ferro_swim_run`] -- the main thread of the
//! generated program, which is the UI thread of FerroUI.
//!
//! Build it with `scripts/build-ffi.sh`, which reuses the target directory of
//! the FerroUI checkout the crates come from.

mod app;
mod controls;
mod events;
mod snapshot;
mod state;

use std::cell::RefCell;
use std::ffi::{c_char, c_int, CStr, CString};
use std::sync::OnceLock;

/// The version of this ABI; the Nim module refuses a library that disagrees.
pub const ABI_VERSION: i32 = 1;

fn version_string() -> &'static CString {
    static VERSION: OnceLock<CString> = OnceLock::new();
    VERSION.get_or_init(|| {
        CString::new(format!(
            "ferroui-swim {} (FerroUI 0.5.0-preview.1, ABI {ABI_VERSION})",
            env!("CARGO_PKG_VERSION")
        ))
        .expect("the version string has no NUL")
    })
}

fn c_string(value: *const c_char) -> Result<String, String> {
    if value.is_null() {
        return Err("a null string was passed".to_string());
    }
    // SAFETY: the caller passes a NUL-terminated string for the lifetime of the
    // call, as the C ABI documents.
    unsafe { CStr::from_ptr(value) }
        .to_str()
        .map(|value| value.to_string())
        .map_err(|error| format!("the string is not valid UTF-8: {error}"))
}

fn report(result: Result<(), String>) {
    match result {
        Ok(()) => state::clear_error(),
        Err(message) => state::set_error(message),
    }
}

fn report_handle(result: Result<state::Handle, String>) -> i64 {
    match result {
        Ok(handle) => {
            state::clear_error();
            handle
        }
        Err(message) => {
            state::set_error(message);
            0
        }
    }
}

// ---------------------------------------------------------------- the library

#[no_mangle]
pub extern "C" fn ferro_swim_abi_version() -> i32 {
    ABI_VERSION
}

#[no_mangle]
pub extern "C" fn ferro_swim_version() -> *const c_char {
    version_string().as_ptr()
}

#[no_mangle]
pub extern "C" fn ferro_swim_last_error() -> *const c_char {
    state::last_error_ptr()
}

// ------------------------------------------------------------- the application

/// Starts the application; `ready` runs once the framework is initialized and
/// the program builds its main window there.  Blocks until the window closes.
#[no_mangle]
pub extern "C" fn ferro_swim_run(ready: Option<extern "C" fn(i64)>, user: i64) {
    state::clear_error();
    app::run(ready, user);
}

/// Ends the application by closing its main window.
#[no_mangle]
pub extern "C" fn ferro_swim_quit() {
    report(app::quit());
}

/// Creates the main window and returns its handle.
#[no_mangle]
pub extern "C" fn ferro_swim_window(width: f64, height: f64) -> i64 {
    report_handle(controls::create_window(width, height))
}

/// The width of the client area of the main window; 0 when there is none yet.
#[no_mangle]
pub extern "C" fn ferro_swim_client_width() -> f64 {
    match app::client_size() {
        Ok((width, _)) => width,
        Err(message) => {
            state::set_error(message);
            0.0
        }
    }
}

/// The height of the client area of the main window; 0 when there is none yet.
#[no_mangle]
pub extern "C" fn ferro_swim_client_height() -> f64 {
    match app::client_size() {
        Ok((_, height)) => height,
        Err(message) => {
            state::set_error(message);
            0.0
        }
    }
}

/// The theme variant of the application: "dark", "light" or "system".
#[no_mangle]
pub extern "C" fn ferro_swim_set_theme_variant(name: *const c_char) {
    let result = c_string(name).map(|name| {
        let name = name.to_ascii_lowercase();
        let variant = match name.as_str() {
            "dark" | "light" => Some(name),
            _ => None,
        };
        state::with_state(|state| state.theme_variant = variant);
    });
    report(result);
}

/// The decorations of a window: 0 none, 1 border only, 2 full.
#[no_mangle]
pub extern "C" fn ferro_swim_set_decorations(handle: i64, mode: i32) {
    report(controls::set_decorations(handle, mode));
}

// ------------------------------------------------------------------ the tree

/// Creates a control of `kind`; `parent` 0 leaves it detached.
#[no_mangle]
pub extern "C" fn ferro_swim_create(kind: i32, parent: i64) -> i64 {
    let handle = report_handle(controls::create(kind).map(state::register));
    if handle != 0 {
        report(controls::add_child(parent, handle));
    }
    handle
}

/// Adds a control to a panel or sets it as the content of a content control.
#[no_mangle]
pub extern "C" fn ferro_swim_add_child(parent: i64, child: i64) {
    report(controls::add_child(parent, child));
}

/// Inserts a control into a panel at `index`, replaces the child of a border
/// (index 0) or the content of a content control.
#[no_mangle]
pub extern "C" fn ferro_swim_insert_child(parent: i64, index: i32, child: i64) {
    report(controls::insert_child(parent, index, child));
}

/// Removes a control from a panel, or clears the child of a border or the
/// content of a content control.
#[no_mangle]
pub extern "C" fn ferro_swim_remove_child(parent: i64, child: i64) {
    report(controls::remove_child(parent, child));
}

/// Removes every child of a panel, or clears the single child of a border or
/// content control.
#[no_mangle]
pub extern "C" fn ferro_swim_clear_children(parent: i64) {
    report(controls::clear_children(parent));
}

/// Destroys the control a handle refers to once no other reference holds it:
/// the handle stops being valid for the calls that take a handle of that
/// control, and the control itself goes away with the last reference (the
/// visual tree, or another handle).  Destroying a handle that is already gone
/// is a no-op.
#[no_mangle]
pub extern "C" fn ferro_swim_destroy(handle: i64) {
    state::release(handle);
    state::clear_error();
}

/// Sets the direction, the two alignments and the two spacings of a flex panel.
#[no_mangle]
pub extern "C" fn ferro_swim_set_flex(
    handle: i64,
    direction: i32,
    justify: i32,
    align: i32,
    column_spacing: f64,
    row_spacing: f64,
) {
    report(controls::set_flex(handle, direction, justify, align, column_spacing, row_spacing));
}

/// Sets the flex grow factor of a control: how it shares the free space of the
/// flex panel it is a child of.
#[no_mangle]
pub extern "C" fn ferro_swim_set_grow(handle: i64, grow: f64) {
    report(controls::set_grow(handle, grow));
}

/// Sets the size and, in a canvas, the position of a control.
#[no_mangle]
pub extern "C" fn ferro_swim_set_frame(handle: i64, x: f64, y: f64, width: f64, height: f64) {
    report(controls::set_frame(handle, x, y, width, height));
}

// -------------------------------------------------------------- the properties

#[no_mangle]
pub extern "C" fn ferro_swim_set_f64(handle: i64, property: i32, value: f64) {
    report(controls::set_f64(handle, property, value));
}

#[no_mangle]
pub extern "C" fn ferro_swim_set_str(handle: i64, property: i32, value: *const c_char) {
    let result = c_string(value).and_then(|value| controls::set_str(handle, property, &value));
    report(result);
}

#[no_mangle]
pub extern "C" fn ferro_swim_set_bool(handle: i64, property: i32, value: c_int) {
    report(controls::set_bool(handle, property, value != 0));
}

#[no_mangle]
pub extern "C" fn ferro_swim_set_i32(handle: i64, property: i32, value: i32) {
    report(controls::set_i32(handle, property, value));
}

#[no_mangle]
pub extern "C" fn ferro_swim_set_color(handle: i64, property: i32, argb: u32) {
    report(controls::set_color(handle, property, argb));
}

#[no_mangle]
pub extern "C" fn ferro_swim_set_thickness(handle: i64, property: i32, left: f64, top: f64, right: f64, bottom: f64) {
    report(controls::set_thickness(handle, property, left, top, right, bottom));
}

#[no_mangle]
pub extern "C" fn ferro_swim_set_enum(handle: i64, property: i32, value: i32) {
    report(controls::set_enum(handle, property, value));
}

#[no_mangle]
pub extern "C" fn ferro_swim_get_f64(handle: i64, property: i32) -> f64 {
    match controls::get_f64(handle, property) {
        Ok(value) => {
            state::clear_error();
            value
        }
        Err(message) => {
            state::set_error(message);
            0.0
        }
    }
}

thread_local! {
    static LAST_STRING: RefCell<CString> = RefCell::new(CString::default());
}

/// The last string read with [`ferro_swim_get_str`]; valid until the next
/// call on this thread.
#[no_mangle]
pub extern "C" fn ferro_swim_get_str(handle: i64, property: i32) -> *const c_char {
    let value = match controls::get_str(handle, property) {
        Ok(value) => {
            state::clear_error();
            value
        }
        Err(message) => {
            state::set_error(message);
            String::new()
        }
    };
    let value = CString::new(value).unwrap_or_else(|_| CString::new("").expect("empty CString"));
    LAST_STRING.with(|last| {
        *last.borrow_mut() = value;
        last.borrow().as_ptr()
    })
}

#[no_mangle]
pub extern "C" fn ferro_swim_get_bool(handle: i64, property: i32) -> c_int {
    match controls::get_bool(handle, property) {
        Ok(value) => {
            state::clear_error();
            if value {
                1
            } else {
                0
            }
        }
        Err(message) => {
            state::set_error(message);
            0
        }
    }
}

// -------------------------------------------------------------------- the events

/// Subscribes to an event; the subscription lives until the application ends.
#[no_mangle]
pub extern "C" fn ferro_swim_on(handle: i64, event: i32, callback: Option<extern "C" fn(i64)>, user: i64) {
    let Some(callback) = callback else {
        state::set_error("ferro_swim_on needs a callback");
        return;
    };
    report(events::subscribe(handle, event, callback, user));
}

/// Runs `callback(user)` once after `delay_ms`.
#[no_mangle]
pub extern "C" fn ferro_swim_after(delay_ms: f64, callback: Option<extern "C" fn(i64)>, user: i64) {
    match callback {
        Some(callback) => {
            state::clear_error();
            events::after(delay_ms, callback, user);
        }
        None => state::set_error("ferro_swim_after needs a callback"),
    }
}

// ------------------------------------------------------------- the window itself

/// Closes the main window.
#[no_mangle]
pub extern "C" fn ferro_swim_close(handle: i64) {
    report(controls::close(handle));
}

/// Writes a PNG of the main window to `path` after `delay_ms`, when the layout
/// and the styles have settled.
#[no_mangle]
pub extern "C" fn ferro_swim_snapshot(delay_ms: f64, path: *const c_char) {
    let result = c_string(path).map(|path| {
        // The path is kept on the bridge side: the pointer of the caller is of
        // the call only, and the timer fires long after it returned.  Every
        // snapshot takes the next slot, so a program may schedule several.
        let index = SNAPSHOT_PATHS.with(|paths| {
            let mut paths = paths.borrow_mut();
            paths.push(path);
            paths.len() - 1
        });
        events::after(delay_ms, snapshot_callback, index as i64);
    });
    report(result);
}

thread_local! {
    /// The paths of the scheduled snapshots, by the index the timer fires with.
    static SNAPSHOT_PATHS: RefCell<Vec<String>> = const { RefCell::new(Vec::new()) };
}

extern "C" fn snapshot_callback(index: i64) {
    let path = SNAPSHOT_PATHS.with(|paths| paths.borrow().get(index as usize).cloned());
    if let Some(path) = path {
        report(snapshot::snapshot_to(&path));
    }
}

/// Raises the click event of a button, as a pointer would: a test helper for a
/// program that drives its own controls.
#[no_mangle]
pub extern "C" fn ferro_swim_raise_click(handle: i64) {
    report(controls::raise_click(handle));
}

// ------------------------------------------------------------------- the handles

/// Releases the reference a handle holds: the control stays alive while the
/// visual tree holds it.
#[no_mangle]
pub extern "C" fn ferro_swim_release(handle: i64) {
    state::release(handle);
    state::clear_error();
}
