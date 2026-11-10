//! The state the bridge keeps between C calls: the registry of live handles,
//! the application state and the message of the last error.
//!
//! Everything lives in thread locals because FerroUI objects are not `Send`:
//! the whole bridge runs on the thread that called [`ferro_swim_run`], which is
//! the main thread of the generated program and the UI thread of FerroUI.

use std::any::Any;
use std::cell::RefCell;
use std::ffi::CString;
use std::rc::Rc;

use ferroui_base::media::Color;
use ferroui_base::media::immutable::ImmutableSolidColorBrush;
use ferroui_base::media::IBrush;
use ferroui_controls::{Control, Window};

/// An opaque reference to a control of the application.
pub type Handle = i64;

/// The state of the application the bridge hosts.
pub struct AppState {
    /// The callback the `.sw` program builds the window in, taken once.
    pub ready: Option<extern "C" fn(i64)>,
    /// The value the ready callback is called with.
    pub user: i64,
    /// The main window of the application, once the ready callback made it.
    pub window: Option<ferroui_base::Ref<Window>>,
    /// What the classic desktop lifetime returned.
    pub exit_code: i32,
    /// The theme variant the program asked for before it started: "dark" or
    /// "light"; empty follows the system.
    pub theme_variant: Option<String>,
}

impl Default for AppState {
    fn default() -> Self {
        Self { ready: None, user: 0, window: None, exit_code: 0, theme_variant: None }
    }
}

thread_local! {
    /// Handles by index; index 0 is the null handle. The entries keep the
    /// controls alive for as long as the program holds a handle: a control of
    /// the visual tree stays alive through its parent, a detached one does
    /// not, and the binding may keep a handle of a detached control.
    static CONTROLS: RefCell<Vec<Option<ferroui_base::Ref<Control>>>> = const { RefCell::new(Vec::new()) };

    static STATE: RefCell<AppState> = const { RefCell::new(AppState { ready: None, user: 0, window: None, exit_code: 0, theme_variant: None }) };

    /// The subscriptions of the events; dropping one unsubscribes, so they are
    /// kept for the lifetime of the application.
    static SUBSCRIPTIONS: RefCell<Vec<Box<dyn Any>>> = const { RefCell::new(Vec::new()) };

    static LAST_ERROR: RefCell<CString> = RefCell::new(CString::new("").expect("empty CString"));
}

/// Runs `f` with the application state.
pub fn with_state<R>(f: impl FnOnce(&mut AppState) -> R) -> R {
    STATE.with(|state| f(&mut state.borrow_mut()))
}

/// Stores the message of a failed call; the C side reads it with
/// `ferro_swim_last_error`.
pub fn set_error(message: impl Into<String>) {
    let message = CString::new(message.into()).unwrap_or_else(|_| CString::new("error").expect("valid"));
    LAST_ERROR.with(|last| *last.borrow_mut() = message);
}

/// Clears the message of the last error.
pub fn clear_error() {
    LAST_ERROR.with(|last| *last.borrow_mut() = CString::new("").expect("empty CString"));
}

/// The message of the last error of this thread.
pub fn last_error_ptr() -> *const std::ffi::c_char {
    LAST_ERROR.with(|last| last.borrow().as_ptr())
}

/// Registers a control and returns its handle.
pub fn register(control: ferroui_base::Ref<Control>) -> Handle {
    CONTROLS.with(|controls| {
        let mut controls = controls.borrow_mut();
        if controls.is_empty() {
            controls.push(None); // the null handle
        }
        controls.push(Some(control));
        (controls.len() - 1) as Handle
    })
}

/// A strong handle of a control, or `None` for an unknown handle.
pub fn control(handle: Handle) -> Option<ferroui_base::Ref<Control>> {
    if handle <= 0 {
        return None;
    }
    CONTROLS.with(|controls| {
        let controls = controls.borrow();
        controls.get(handle as usize).and_then(|entry| entry.clone())
    })
}

/// Drops the reference a handle holds; the control stays alive while the
/// visual tree holds it.
pub fn release(handle: Handle) {
    if handle <= 0 {
        return;
    }
    CONTROLS.with(|controls| {
        let mut controls = controls.borrow_mut();
        if let Some(entry) = controls.get_mut(handle as usize) {
            *entry = None;
        }
    });
}

/// Keeps an event subscription alive for the lifetime of the application.
pub fn keep_subscription(subscription: impl Any) {
    SUBSCRIPTIONS.with(|subscriptions| subscriptions.borrow_mut().push(Box::new(subscription)));
}

/// A view of the handle registry, for callbacks that outlive the call that
/// created them.
pub fn window() -> Option<ferroui_base::Ref<Window>> {
    with_state(|state| state.window.clone())
}

/// `0xAARRGGBB` (or `0xRRGGBB` for an opaque colour) to a solid brush.
pub fn brush(argb: u32) -> Rc<dyn IBrush> {
    let a = ((argb >> 24) & 0xFF) as u8;
    let r = ((argb >> 16) & 0xFF) as u8;
    let g = ((argb >> 8) & 0xFF) as u8;
    let b = (argb & 0xFF) as u8;
    Rc::new(ImmutableSolidColorBrush::new(Color::from_argb(a, r, g, b)))
}
