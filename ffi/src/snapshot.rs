//! Writing a PNG of the main window.
//!
//! A test run (or a documentation script) renders the window without a person
//! in front of the screen: the layout of the window is final once it has been
//! shown, so a snapshot scheduled a little after the first frame is what the
//! screen shows.

use ferroui_base::media::imaging::{PngBitmapEncoderOptions, RenderTargetBitmap};
use ferroui_base::{PixelSize, Ref, Vector, Visual};
use ferroui_controls::Control;

/// Renders the main window into `path` as a PNG.
pub fn snapshot_to(path: &str) -> Result<(), String> {
    let window = crate::state::window().ok_or_else(|| "no window to snapshot".to_string())?;
    let root: Ref<Control> = window.clone().upcast::<Control>();
    if root.composition_visual().is_none() {
        return Err("the window has not been shown yet, the snapshot is too early".to_string());
    }

    let bounds = root.bounds();
    let width = bounds.width.max(1.0);
    let height = bounds.height.max(1.0);
    let pixel_size = PixelSize::new(width as i32, height as i32);
    let bitmap = RenderTargetBitmap::with_dpi(pixel_size, Vector::new(96.0, 96.0));
    bitmap.render(&root.clone().upcast::<Visual>());

    let mut file = std::fs::File::create(path).map_err(|error| format!("cannot create {path}: {error}"))?;
    let saved = bitmap
        .save(&mut file, &PngBitmapEncoderOptions::DEFAULT.into())
        .map_err(|error| format!("cannot encode the snapshot {path}: {error}"));
    bitmap.dispose();
    saved
}
