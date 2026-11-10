//! The FerroUI application the generated program runs in.
//!
//! `ferro_swim_run` starts the application; once the framework is initialized
//! the bridge calls back into the `.sw` program, which builds the main window
//! with the rest of the ABI, and then hands that window to the classic desktop
//! lifetime, which shows it and runs the message loop until it closes.

use ferroui_base::styling::{Styles, ThemeVariant};
use ferroui_base::{ferro_class, ferro_impl_classes, instantiate, FerroObjectImpl, Ref};
use ferroui_controls::{AppBuilder, Application, ApplicationImpl, ApplicationImplExt, NewApplication};
use ferroui_desktop::AppBuilderDesktopExtensions;
use ferroui_themes_simple::SimpleTheme;

use crate::state;

/// The application class of a bridge-owned process.
#[repr(C)]
pub struct SwimApp {
    base: Application,
}

ferro_class!(SwimApp: Application);
ferroui_base::ferro_impl_classes!(SwimApp: FerroObjectImpl);

impl NewApplication for SwimApp {
    fn new_application() -> Ref<Self> {
        instantiate(Self { base: Application::construct() })
    }
}

impl ApplicationImpl for SwimApp {
    fn initialize(this: &Self) {
        Self::parent_initialize(this);
        this.set_name(Some("SwimUI".to_string()));
        // The variant the program asked for wins over the environment.
        let requested = state::with_state(|state| state.theme_variant.clone())
            .or_else(|| std::env::var("SWIMUI_THEME_VARIANT").ok());
        match requested.as_deref() {
            Some("dark") => this.set_requested_theme_variant(Some(ThemeVariant::dark())),
            Some("light") => this.set_requested_theme_variant(Some(ThemeVariant::light())),
            _ => {}
        }
        // The theme gives the controls their templates and their colours. The
        // simple theme is the one the bridge links; it themes every control.
        this.styles().add(SimpleTheme::new().upcast::<Styles>());
    }

    fn on_framework_initialization_completed(this: &Self) {
        // The program builds its window here: the framework exists, so the
        // controls and the window it makes are live.
        let ready = state::with_state(|state| (state.ready.take(), state.user));
        if let Some(callback) = ready.0 {
            callback(ready.1);
        }

        // Hand the window the program made to the lifetime, which shows it.
        if let Some(desktop) =
            this.application_lifetime().as_ref().and_then(|lifetime| lifetime.as_classic_desktop_style_application_lifetime())
        {
            match state::window() {
                Some(window) => desktop.set_main_window(Some(window)),
                None => state::set_error("the program did not create a window in its build closure"),
            }
        }

        Self::parent_on_framework_initialization_completed(this);
    }
}

/// Starts the application; blocks until the window closes.
pub fn run(ready: Option<extern "C" fn(i64)>, user: i64) -> i32 {
    state::with_state(|state| {
        state.ready = ready;
        state.user = user;
    });
    let args: Vec<String> = std::env::args().skip(1).collect();
    let code = AppBuilder::configure::<SwimApp>().use_platform_detect().start_with_classic_desktop_lifetime(&args);
    state::with_state(|state| state.exit_code = code);
    code
}

/// Ends the application by closing its main window.
pub fn quit() -> Result<(), String> {
    match state::window() {
        Some(window) => {
            window.close();
            Ok(())
        }
        None => Err("no window: ferro_swim_run has not made one".to_string()),
    }
}

/// The main window, or an error when the program has not made one.
pub fn main_window() -> Result<Ref<ferroui_controls::Window>, String> {
    state::window().ok_or_else(|| "no window: the program builds one inside ferro_swim_run".to_string())
}

/// The client size of the main window: the size the layout of the program has
/// to fit in, which is smaller than the requested size when the window
/// decorations or the screen take room from it.
pub fn client_size() -> Result<(f64, f64), String> {
    let window = main_window()?;
    let size = window.client_size();
    Ok((size.width, size.height))
}
