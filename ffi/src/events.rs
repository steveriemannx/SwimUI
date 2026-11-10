//! Event subscriptions: the C callbacks the generated program registers on the
//! controls, and the timers it schedules.

use std::time::Duration;

use ferroui_base::threading::{DispatcherPriority, DispatcherTimer};
use ferroui_controls::primitives::{RangeBase, ToggleButton};
use ferroui_controls::{Button, TextBox, Window};

use crate::state::{self, Handle};

// The events of the ABI (include/ferroui_swim.h).
pub const EVENT_TAP: i32 = 1;
pub const EVENT_TEXT_CHANGED: i32 = 2;
pub const EVENT_CHECKED_CHANGED: i32 = 3;
pub const EVENT_VALUE_CHANGED: i32 = 4;
pub const EVENT_OPENED: i32 = 5;
pub const EVENT_CLOSED: i32 = 6;

/// Subscribes `callback` to an event of a control. The subscription lives for
/// as long as the application.
pub fn subscribe(handle: Handle, event: i32, callback: extern "C" fn(i64), user: i64) -> Result<(), String> {
    let control = state::control(handle).ok_or_else(|| format!("invalid handle {handle}"))?;
    let name = || control.get_type().name().to_string();
    match event {
        EVENT_TAP => {
            // A button reports a click (a press and a release on it, or the
            // keyboard activation); any other control reports a tap gesture,
            // so a panel is a tap target as well.
            if let Some(button) = control.cast::<Button>() {
                state::keep_subscription(button.click(move |_, _| callback(user)));
            } else {
                state::keep_subscription(control.tapped(move |_, _| callback(user)));
            }
        }
        EVENT_TEXT_CHANGED => {
            let text_box = control
                .cast::<TextBox>()
                .ok_or_else(|| format!("{} does not raise text changed events", name()))?;
            state::keep_subscription(text_box.text_changed(move |_, _| callback(user)));
        }
        EVENT_CHECKED_CHANGED => {
            let toggle = control
                .cast::<ToggleButton>()
                .ok_or_else(|| format!("{} does not raise checked changed events", name()))?;
            state::keep_subscription(toggle.is_checked_changed(move |_, _| callback(user)));
        }
        EVENT_VALUE_CHANGED => {
            let range = control
                .cast::<RangeBase>()
                .ok_or_else(|| format!("{} does not raise value changed events", name()))?;
            state::keep_subscription(range.value_changed(move |_, _| callback(user)));
        }
        EVENT_OPENED => {
            let window = control
                .cast::<Window>()
                .ok_or_else(|| format!("{} does not open", name()))?;
            state::keep_subscription(window.opened(move || callback(user)));
        }
        EVENT_CLOSED => {
            let window = control
                .cast::<Window>()
                .ok_or_else(|| format!("{} does not close", name()))?;
            state::keep_subscription(window.closed(move || callback(user)));
        }
        other => return Err(format!("unknown event {other}")),
    }
    Ok(())
}

/// Runs `callback` once, after `delay_ms` on the thread of the dispatcher.
pub fn after(delay_ms: f64, callback: extern "C" fn(i64), user: i64) {
    let delay = Duration::from_millis(delay_ms.max(0.0) as u64);
    // The detached timer keeps itself alive until it fires.
    DispatcherTimer::run_once(move || callback(user), delay, DispatcherPriority::NORMAL).detach();
}
