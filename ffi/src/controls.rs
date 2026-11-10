//! The control surface of the ABI: creating controls, adding them to the tree
//! and setting their properties.
//!
//! Every property is set through the class that declares it, so that the
//! bridge keeps the type of the value the property takes: a property the given
//! control does not have is reported as an error instead of being swallowed.

use std::rc::Rc;

use ferroui_base::layout::{HorizontalAlignment, Layoutable, Orientation, VerticalAlignment};
use ferroui_base::media::{FontStyle, FontWeight, IBrush, TextAlignment, TextWrapping};
use ferroui_base::interactivity::RoutedEventArgs;
use ferroui_base::{CornerRadius, FerroObject, Ref, Size, Thickness};
use ferroui_controls::primitives::{RangeBase, TemplatedControl, ToggleButton};
use ferroui_controls::{
    Border, Button, Canvas, CheckBox, ContentControl, Control, Decorator, Flex, FlexAlignItems, FlexDirection,
    FlexJustifyContent, FlexPanel, Panel, ProgressBar, ScrollViewer, Slider, StackPanel, TextBlock, TextBox,
    ToggleSwitch, Window,
};

use crate::state::{self, Handle};

// The kinds of the ABI (include/ferroui_swim.h).
pub const KIND_CANVAS: i32 = 1;
pub const KIND_STACK_PANEL: i32 = 2;
pub const KIND_BORDER: i32 = 3;
pub const KIND_TEXT_BLOCK: i32 = 4;
pub const KIND_BUTTON: i32 = 5;
pub const KIND_TEXT_BOX: i32 = 6;
pub const KIND_CHECK_BOX: i32 = 7;
pub const KIND_SLIDER: i32 = 8;
pub const KIND_PROGRESS_BAR: i32 = 9;
pub const KIND_SCROLL_VIEWER: i32 = 10;
pub const KIND_PANEL: i32 = 11;
pub const KIND_FLEX_PANEL: i32 = 12;
pub const KIND_TOGGLE_SWITCH: i32 = 13;

// The double properties.
pub const F64_WIDTH: i32 = 1;
pub const F64_HEIGHT: i32 = 2;
pub const F64_MIN_WIDTH: i32 = 3;
pub const F64_MIN_HEIGHT: i32 = 4;
pub const F64_MAX_WIDTH: i32 = 5;
pub const F64_MAX_HEIGHT: i32 = 6;
pub const F64_FONT_SIZE: i32 = 7;
pub const F64_OPACITY: i32 = 8;
pub const F64_CORNER_RADIUS: i32 = 9;
pub const F64_SPACING: i32 = 10;
pub const F64_MINIMUM: i32 = 11;
pub const F64_MAXIMUM: i32 = 12;
pub const F64_VALUE: i32 = 13;
pub const F64_LINE_HEIGHT: i32 = 14;

// The string properties.
pub const STR_TEXT: i32 = 1;
pub const STR_TITLE: i32 = 2;
pub const STR_WATERMARK: i32 = 3;
pub const STR_CONTENT: i32 = 4;

// The boolean properties.
pub const BOOL_IS_VISIBLE: i32 = 1;
pub const BOOL_IS_CHECKED: i32 = 2;
pub const BOOL_IS_INDETERMINATE: i32 = 3;
pub const BOOL_IS_ENABLED: i32 = 4;
pub const BOOL_CLIP_TO_BOUNDS: i32 = 5;

// The integer properties.
pub const I32_MAX_LINES: i32 = 1;

// The brush properties.
pub const COLOR_BACKGROUND: i32 = 1;
pub const COLOR_FOREGROUND: i32 = 2;
pub const COLOR_BORDER: i32 = 3;

// The thickness properties.
pub const THICKNESS_MARGIN: i32 = 1;
pub const THICKNESS_PADDING: i32 = 2;
pub const THICKNESS_BORDER: i32 = 3;

// The enum properties.
pub const ENUM_HORIZONTAL_ALIGNMENT: i32 = 1;
pub const ENUM_VERTICAL_ALIGNMENT: i32 = 2;
pub const ENUM_ORIENTATION: i32 = 3;
pub const ENUM_TEXT_ALIGNMENT: i32 = 4;
pub const ENUM_TEXT_WRAPPING: i32 = 5;
pub const ENUM_FONT_WEIGHT: i32 = 6;
pub const ENUM_FONT_STYLE: i32 = 7;

/// The class of a handle, for error messages.
fn name_of(control: &Ref<Control>) -> String {
    control.get_type().name().to_string()
}

/// A control of `kind`, not yet attached to the tree.
pub fn create(kind: i32) -> Result<Ref<Control>, String> {
    let control: Ref<Control> = match kind {
        KIND_CANVAS => Canvas::new().upcast::<Control>(),
        KIND_STACK_PANEL => StackPanel::new().upcast::<Control>(),
        KIND_BORDER => Border::new().upcast::<Control>(),
        KIND_TEXT_BLOCK => TextBlock::new().upcast::<Control>(),
        KIND_BUTTON => Button::new().upcast::<Control>(),
        KIND_TEXT_BOX => TextBox::new().upcast::<Control>(),
        KIND_CHECK_BOX => CheckBox::new().upcast::<Control>(),
        KIND_SLIDER => Slider::new().upcast::<Control>(),
        KIND_PROGRESS_BAR => ProgressBar::new().upcast::<Control>(),
        KIND_SCROLL_VIEWER => ScrollViewer::new().upcast::<Control>(),
        // A panel arranges its children on top of each other: the overlay of a
        // ZStack.
        KIND_PANEL => Panel::new().upcast::<Control>(),
        KIND_FLEX_PANEL => FlexPanel::new().upcast::<Control>(),
        KIND_TOGGLE_SWITCH => ToggleSwitch::new().upcast::<Control>(),
        other => return Err(format!("unknown control kind {other}")),
    };
    Ok(control)
}

/// Creates the main window of the application.
pub fn create_window(width: f64, height: f64) -> Result<Handle, String> {
    let window = Window::new();
    window.set_width(width);
    window.set_height(height);
    // The size of the window is its frame, the size of the canvas the client
    // area: ask for both, so that a phone-sized layout is laid out in a
    // phone-sized client area whatever the window decorations are.
    window.set_client_size(Size::new(width, height));
    if std::env::var_os("SWIMUI_DEBUG").is_some() {
        eprintln!(
            "swimui: window requested {width}x{height}, client {:?}, frame {:?}",
            window.client_size(),
            window.frame_size()
        );
        let probe = window.clone();
        state::keep_subscription(window.opened(move || {
            eprintln!(
                "swimui: opened: client {:?}, frame {:?}, bounds {:?}",
                probe.client_size(),
                probe.frame_size(),
                probe.bounds()
            );
        }));
    }
    let handle = state::register(window.clone().upcast::<Control>());
    state::with_state(|state| state.window = Some(window));
    Ok(handle)
}

/// Adds `child` to `parent`: to the children of a panel, or as the content of
/// a content control (window, border, content control).
pub fn add_child(parent: Handle, child: Handle) -> Result<(), String> {
    if parent == 0 {
        return Ok(());
    }
    let parent_control = state::control(parent).ok_or_else(|| format!("invalid parent handle {parent}"))?;
    let child_control = state::control(child).ok_or_else(|| format!("invalid child handle {child}"))?;

    if let Some(panel) = parent_control.cast::<Panel>() {
        panel.children().add(child_control);
        return Ok(());
    }
    if let Some(decorator) = parent_control.cast::<Decorator>() {
        decorator.set_child(child_control);
        return Ok(());
    }
    if let Some(content) = parent_control.cast::<ContentControl>() {
        content.set_content(Some(Control::boxed(&child_control)));
        return Ok(());
    }
    Err(format!("{} cannot hold a child", name_of(&parent_control)))
}

/// Inserts `child` into `parent` at `index`.
///
/// A panel keeps an ordered list of children, so the index is where the child
/// lands (an index past the end appends it); a decorator holds one child, so
/// the index has to be 0; a content control holds one boxed content, which the
/// child replaces.
pub fn insert_child(parent: Handle, index: i32, child: Handle) -> Result<(), String> {
    if parent == 0 {
        return Ok(());
    }
    let parent_control = state::control(parent).ok_or_else(|| format!("invalid parent handle {parent}"))?;
    let child_control = state::control(child).ok_or_else(|| format!("invalid child handle {child}"))?;
    if index < 0 {
        return Err(format!("the index of a child must not be negative, not {index}"));
    }
    let index = index as usize;

    if let Some(panel) = parent_control.cast::<Panel>() {
        let children = panel.children();
        // `FerroList::insert` needs a slot that exists: an index past the end
        // appends the child, as the collection's `add` would.
        let index = index.min(children.count());
        children.insert(index, child_control);
        return Ok(());
    }
    if let Some(decorator) = parent_control.cast::<Decorator>() {
        if index != 0 {
            return Err(format!(
                "{} holds a single child, so the index must be 0, not {index}",
                name_of(&parent_control)
            ));
        }
        decorator.set_child(child_control);
        return Ok(());
    }
    if let Some(content) = parent_control.cast::<ContentControl>() {
        // A content control holds a single boxed value: an index cannot place
        // a second child, so it is ignored.
        content.set_content(Some(Control::boxed(&child_control)));
        return Ok(());
    }
    Err(format!("{} cannot hold a child", name_of(&parent_control)))
}

/// Removes `child` from `parent`; a child that is not in `parent` is a no-op
/// for a panel, and clears the single child of a decorator, or the content of
/// a content control.
pub fn remove_child(parent: Handle, child: Handle) -> Result<(), String> {
    if parent == 0 {
        return Ok(());
    }
    let parent_control = state::control(parent).ok_or_else(|| format!("invalid parent handle {parent}"))?;
    let child_control = state::control(child).ok_or_else(|| format!("invalid child handle {child}"))?;

    if let Some(panel) = parent_control.cast::<Panel>() {
        panel.children().remove(child_control);
        return Ok(());
    }
    if let Some(decorator) = parent_control.cast::<Decorator>() {
        decorator.set_child(None::<Ref<Control>>);
        return Ok(());
    }
    if let Some(content) = parent_control.cast::<ContentControl>() {
        content.set_content(None);
        return Ok(());
    }
    Err(format!("{} cannot hold a child", name_of(&parent_control)))
}

/// Removes every child of `parent`.
pub fn clear_children(parent: Handle) -> Result<(), String> {
    if parent == 0 {
        return Ok(());
    }
    let parent_control = state::control(parent).ok_or_else(|| format!("invalid parent handle {parent}"))?;

    if let Some(panel) = parent_control.cast::<Panel>() {
        let children = panel.children();
        // The snapshot is taken first: removing mutates the collection the
        // snapshot was taken from.
        for child in children.snapshot().iter() {
            children.remove(child);
        }
        return Ok(());
    }
    if let Some(decorator) = parent_control.cast::<Decorator>() {
        decorator.set_child(None::<Ref<Control>>);
        return Ok(());
    }
    if let Some(content) = parent_control.cast::<ContentControl>() {
        content.set_content(None);
        return Ok(());
    }
    Err(format!("{} cannot hold a child", name_of(&parent_control)))
}

/// The direction, the two alignments and the two spacings of a flex panel.
pub fn set_flex(
    handle: Handle,
    direction: i32,
    justify: i32,
    align: i32,
    column_spacing: f64,
    row_spacing: f64,
) -> Result<(), String> {
    let control = state::control(handle).ok_or_else(|| format!("invalid handle {handle}"))?;
    let panel = control
        .cast::<FlexPanel>()
        .ok_or_else(|| format!("{} is not a flex panel", name_of(&control)))?;
    // The values are checked before any of them is set, so a call with an
    // unknown value leaves the panel as it was.
    let direction = match direction {
        0 => FlexDirection::Row,
        1 => FlexDirection::RowReverse,
        2 => FlexDirection::Column,
        3 => FlexDirection::ColumnReverse,
        other => return Err(format!("unknown flex direction {other}")),
    };
    let justify = match justify {
        0 => FlexJustifyContent::FlexStart,
        1 => FlexJustifyContent::FlexEnd,
        2 => FlexJustifyContent::Center,
        3 => FlexJustifyContent::SpaceBetween,
        4 => FlexJustifyContent::SpaceAround,
        5 => FlexJustifyContent::SpaceEvenly,
        other => return Err(format!("unknown flex justify content {other}")),
    };
    let align = match align {
        0 => FlexAlignItems::FlexStart,
        1 => FlexAlignItems::FlexEnd,
        2 => FlexAlignItems::Center,
        3 => FlexAlignItems::Stretch,
        other => return Err(format!("unknown flex align items {other}")),
    };
    panel.set_direction(direction);
    panel.set_justify_content(justify);
    panel.set_align_items(align);
    panel.set_column_spacing(column_spacing);
    panel.set_row_spacing(row_spacing);
    Ok(())
}

/// Sets the factor by which a control grows along the main axis of the flex
/// panel it is a child of; 0 keeps its size, 1 and more share the free space.
pub fn set_grow(handle: Handle, grow: f64) -> Result<(), String> {
    let control = state::control(handle).ok_or_else(|| format!("invalid handle {handle}"))?;
    let layoutable = control
        .cast::<Layoutable>()
        .ok_or_else(|| format!("{} is not laid out", name_of(&control)))?;
    Flex::set_grow(&layoutable, grow);
    Ok(())
}

/// Sets the size and, for a child of a canvas, the position of a control.
pub fn set_frame(handle: Handle, x: f64, y: f64, width: f64, height: f64) -> Result<(), String> {
    let control = state::control(handle).ok_or_else(|| format!("invalid handle {handle}"))?;
    control.set_width(width);
    control.set_height(height);
    let object = control.clone().upcast::<FerroObject>();
    if !x.is_nan() {
        Canvas::set_left(&object, x);
    }
    if !y.is_nan() {
        Canvas::set_top(&object, y);
    }
    Ok(())
}

/// Sets a double property of a control.
pub fn set_f64(handle: Handle, property: i32, value: f64) -> Result<(), String> {
    let control = state::control(handle).ok_or_else(|| format!("invalid handle {handle}"))?;
    match property {
        F64_WIDTH => control.set_width(value),
        F64_HEIGHT => control.set_height(value),
        F64_MIN_WIDTH => control.set_min_width(value),
        F64_MIN_HEIGHT => control.set_min_height(value),
        F64_MAX_WIDTH => control.set_max_width(value),
        F64_MAX_HEIGHT => control.set_max_height(value),
        F64_OPACITY => control.set_opacity(value),
        F64_FONT_SIZE => {
            if let Some(text) = control.cast::<TextBlock>() {
                text.set_font_size(value);
            } else if let Some(templated) = control.cast::<TemplatedControl>() {
                templated.set_font_size(value);
            } else {
                return Err(format!("{} has no font size", name_of(&control)));
            }
        }
        F64_LINE_HEIGHT => {
            let text = control
                .cast::<TextBlock>()
                .ok_or_else(|| format!("{} has no line height", name_of(&control)))?;
            text.set_line_height(value);
        }
        F64_CORNER_RADIUS => {
            let radius = CornerRadius::uniform(value);
            if let Some(border) = control.cast::<Border>() {
                border.set_corner_radius(radius);
            } else if let Some(templated) = control.cast::<TemplatedControl>() {
                templated.set_corner_radius(radius);
            } else {
                return Err(format!("{} has no corner radius", name_of(&control)));
            }
        }
        F64_SPACING => {
            let panel = control
                .cast::<StackPanel>()
                .ok_or_else(|| format!("{} has no spacing", name_of(&control)))?;
            panel.set_spacing(value);
        }
        F64_MINIMUM => range_base(&control)?.set_minimum(value),
        F64_MAXIMUM => range_base(&control)?.set_maximum(value),
        F64_VALUE => range_base(&control)?.set_range_value(value),
        other => return Err(format!("unknown double property {other}")),
    }
    Ok(())
}

fn range_base(control: &Ref<Control>) -> Result<Ref<RangeBase>, String> {
    control.cast::<RangeBase>().ok_or_else(|| format!("{} has no range", name_of(control)))
}

/// Sets a string property of a control.
pub fn set_str(handle: Handle, property: i32, value: &str) -> Result<(), String> {
    let control = state::control(handle).ok_or_else(|| format!("invalid handle {handle}"))?;
    match property {
        STR_TEXT => {
            if let Some(text) = control.cast::<TextBlock>() {
                text.set_text(Some(value));
            } else if let Some(text) = control.cast::<TextBox>() {
                text.set_text(Some(value));
            } else if let Some(content) = control.cast::<ContentControl>() {
                content.set_content(Some(Rc::new(value.to_string())));
            } else {
                return Err(format!("{} has no text", name_of(&control)));
            }
        }
        STR_TITLE => {
            let window = control
                .cast::<Window>()
                .ok_or_else(|| format!("{} has no title", name_of(&control)))?;
            window.set_title(Some(value.to_string()));
        }
        STR_WATERMARK => {
            let text_box = control
                .cast::<TextBox>()
                .ok_or_else(|| format!("{} has no watermark", name_of(&control)))?;
            text_box.set_placeholder_text(Some(value));
        }
        STR_CONTENT => {
            let content = control
                .cast::<ContentControl>()
                .ok_or_else(|| format!("{} has no content", name_of(&control)))?;
            content.set_content(Some(Rc::new(value.to_string())));
        }
        other => return Err(format!("unknown string property {other}")),
    }
    Ok(())
}

/// Sets a boolean property of a control.
pub fn set_bool(handle: Handle, property: i32, value: bool) -> Result<(), String> {
    let control = state::control(handle).ok_or_else(|| format!("invalid handle {handle}"))?;
    match property {
        BOOL_IS_VISIBLE => control.set_is_visible(value),
        BOOL_IS_CHECKED => {
            let toggle = control
                .cast::<ToggleButton>()
                .ok_or_else(|| format!("{} is not a toggle", name_of(&control)))?;
            toggle.set_is_checked(Some(value));
        }
        BOOL_IS_INDETERMINATE => {
            let progress = control
                .cast::<ProgressBar>()
                .ok_or_else(|| format!("{} has no indeterminate mode", name_of(&control)))?;
            progress.set_is_indeterminate(value);
        }
        BOOL_IS_ENABLED => control.set_is_enabled(value),
        BOOL_CLIP_TO_BOUNDS => control.set_clip_to_bounds(value),
        other => return Err(format!("unknown boolean property {other}")),
    }
    Ok(())
}

/// Sets an integer property of a control.
pub fn set_i32(handle: Handle, property: i32, value: i32) -> Result<(), String> {
    let control = state::control(handle).ok_or_else(|| format!("invalid handle {handle}"))?;
    match property {
        I32_MAX_LINES => {
            let text = control
                .cast::<TextBlock>()
                .ok_or_else(|| format!("{} has no maximum number of lines", name_of(&control)))?;
            text.set_max_lines(value);
        }
        other => return Err(format!("unknown integer property {other}")),
    }
    Ok(())
}

/// Sets a brush property of a control; `argb` is `0xAARRGGBB`.
pub fn set_color(handle: Handle, property: i32, argb: u32) -> Result<(), String> {
    let control = state::control(handle).ok_or_else(|| format!("invalid handle {handle}"))?;
    let brush: Option<Rc<dyn IBrush>> = Some(state::brush(argb));
    match property {
        COLOR_BACKGROUND => {
            if let Some(border) = control.cast::<Border>() {
                border.set_background(brush);
            } else if let Some(panel) = control.cast::<Panel>() {
                panel.set_background(brush);
            } else if let Some(text) = control.cast::<TextBlock>() {
                text.set_background(brush);
            } else if let Some(templated) = control.cast::<TemplatedControl>() {
                templated.set_background(brush);
            } else {
                return Err(format!("{} has no background", name_of(&control)));
            }
        }
        COLOR_FOREGROUND => {
            if let Some(text) = control.cast::<TextBlock>() {
                text.set_foreground(brush);
            } else if let Some(templated) = control.cast::<TemplatedControl>() {
                templated.set_foreground(brush);
            } else {
                return Err(format!("{} has no foreground", name_of(&control)));
            }
        }
        COLOR_BORDER => {
            let border = control
                .cast::<Border>()
                .ok_or_else(|| format!("{} has no border brush", name_of(&control)))?;
            border.set_border_brush(brush);
        }
        other => return Err(format!("unknown brush property {other}")),
    }
    Ok(())
}

/// Sets a thickness property of a control.
pub fn set_thickness(handle: Handle, property: i32, left: f64, top: f64, right: f64, bottom: f64) -> Result<(), String> {
    let control = state::control(handle).ok_or_else(|| format!("invalid handle {handle}"))?;
    let thickness = Thickness::new(left, top, right, bottom);
    match property {
        THICKNESS_MARGIN => control.set_margin(thickness),
        THICKNESS_PADDING => {
            if let Some(decorator) = control.cast::<Decorator>() {
                decorator.set_padding(thickness);
            } else if let Some(text) = control.cast::<TextBlock>() {
                text.set_padding(thickness);
            } else if let Some(templated) = control.cast::<TemplatedControl>() {
                templated.set_padding(thickness);
            } else {
                return Err(format!("{} has no padding", name_of(&control)));
            }
        }
        THICKNESS_BORDER => {
            let border = control
                .cast::<Border>()
                .ok_or_else(|| format!("{} has no border thickness", name_of(&control)))?;
            border.set_border_thickness(thickness);
        }
        other => return Err(format!("unknown thickness property {other}")),
    }
    Ok(())
}

/// Sets an enum property of a control.
pub fn set_enum(handle: Handle, property: i32, value: i32) -> Result<(), String> {
    let control = state::control(handle).ok_or_else(|| format!("invalid handle {handle}"))?;
    match property {
        ENUM_HORIZONTAL_ALIGNMENT => control.set_horizontal_alignment(match value {
            0 => HorizontalAlignment::Stretch,
            1 => HorizontalAlignment::Left,
            2 => HorizontalAlignment::Center,
            3 => HorizontalAlignment::Right,
            other => return Err(format!("unknown horizontal alignment {other}")),
        }),
        ENUM_VERTICAL_ALIGNMENT => control.set_vertical_alignment(match value {
            0 => VerticalAlignment::Stretch,
            1 => VerticalAlignment::Top,
            2 => VerticalAlignment::Center,
            3 => VerticalAlignment::Bottom,
            other => return Err(format!("unknown vertical alignment {other}")),
        }),
        ENUM_ORIENTATION => {
            let orientation = if value == 0 { Orientation::Horizontal } else { Orientation::Vertical };
            if let Some(panel) = control.cast::<StackPanel>() {
                panel.set_orientation(orientation);
            } else if let Some(progress) = control.cast::<ProgressBar>() {
                progress.set_orientation(orientation);
            } else {
                return Err(format!("{} has no orientation", name_of(&control)));
            }
        }
        ENUM_TEXT_ALIGNMENT => {
            let alignment = match value {
                0 => TextAlignment::Left,
                1 => TextAlignment::Center,
                2 => TextAlignment::Right,
                other => return Err(format!("unknown text alignment {other}")),
            };
            if let Some(text) = control.cast::<TextBlock>() {
                text.set_text_alignment(alignment);
            } else if let Some(text) = control.cast::<TextBox>() {
                text.set_text_alignment(alignment);
            } else {
                return Err(format!("{} has no text alignment", name_of(&control)));
            }
        }
        ENUM_TEXT_WRAPPING => {
            let wrapping = match value {
                0 => TextWrapping::NoWrap,
                1 => TextWrapping::Wrap,
                2 => TextWrapping::WrapWithOverflow,
                other => return Err(format!("unknown text wrapping {other}")),
            };
            if let Some(text) = control.cast::<TextBlock>() {
                text.set_text_wrapping(wrapping);
            } else if let Some(text) = control.cast::<TextBox>() {
                text.set_text_wrapping(wrapping);
            } else {
                return Err(format!("{} has no text wrapping", name_of(&control)));
            }
        }
        ENUM_FONT_WEIGHT => {
            let weight = FontWeight(value);
            if let Some(text) = control.cast::<TextBlock>() {
                text.set_font_weight(weight);
            } else if let Some(templated) = control.cast::<TemplatedControl>() {
                templated.set_font_weight(weight);
            } else {
                return Err(format!("{} has no font weight", name_of(&control)));
            }
        }
        ENUM_FONT_STYLE => {
            let style = match value {
                0 => FontStyle::Normal,
                1 => FontStyle::Italic,
                2 => FontStyle::Oblique,
                other => return Err(format!("unknown font style {other}")),
            };
            if let Some(text) = control.cast::<TextBlock>() {
                text.set_font_style(style);
            } else if let Some(templated) = control.cast::<TemplatedControl>() {
                templated.set_font_style(style);
            } else {
                return Err(format!("{} has no font style", name_of(&control)));
            }
        }
        other => return Err(format!("unknown enum property {other}")),
    }
    Ok(())
}

/// Reads a double property of a control.
pub fn get_f64(handle: Handle, property: i32) -> Result<f64, String> {
    let control = state::control(handle).ok_or_else(|| format!("invalid handle {handle}"))?;
    match property {
        F64_VALUE => Ok(range_base(&control)?.value()),
        F64_MINIMUM => Ok(range_base(&control)?.minimum()),
        F64_MAXIMUM => Ok(range_base(&control)?.maximum()),
        other => Err(format!("unknown readable double property {other}")),
    }
}

/// Reads a string property of a control.
pub fn get_str(handle: Handle, property: i32) -> Result<String, String> {
    let control = state::control(handle).ok_or_else(|| format!("invalid handle {handle}"))?;
    match property {
        STR_TEXT => {
            if let Some(text) = control.cast::<TextBlock>() {
                Ok(text.text().unwrap_or_default())
            } else if let Some(text) = control.cast::<TextBox>() {
                Ok(text.text().unwrap_or_default())
            } else if let Some(content) = control.cast::<ContentControl>() {
                // The content of a button or a check box is a boxed value: the
                // text of the title the program set is a string in it.
                Ok(content
                    .content()
                    .and_then(|value| value.downcast_ref::<String>().cloned())
                    .unwrap_or_default())
            } else {
                Err(format!("{} has no readable text", name_of(&control)))
            }
        }
        STR_TITLE => {
            let window = control
                .cast::<Window>()
                .ok_or_else(|| format!("{} has no title", name_of(&control)))?;
            Ok(window.title().unwrap_or_default())
        }
        other => Err(format!("unknown readable string property {other}")),
    }
}

/// Reads a boolean property of a control.
pub fn get_bool(handle: Handle, property: i32) -> Result<bool, String> {
    let control = state::control(handle).ok_or_else(|| format!("invalid handle {handle}"))?;
    match property {
        BOOL_IS_VISIBLE => Ok(control.is_visible()),
        BOOL_IS_CHECKED => {
            let toggle = control
                .cast::<ToggleButton>()
                .ok_or_else(|| format!("{} is not a toggle", name_of(&control)))?;
            Ok(toggle.is_checked().unwrap_or(false))
        }
        other => Err(format!("unknown readable boolean property {other}")),
    }
}

/// Raises the click event of a button, as a pointer would: a test helper for a
/// program that drives its own controls.
pub fn raise_click(handle: Handle) -> Result<(), String> {
    let control = state::control(handle).ok_or_else(|| format!("invalid handle {handle}"))?;
    let button = control
        .cast::<Button>()
        .ok_or_else(|| format!("{} is not a button", name_of(&control)))?;
    let args = RoutedEventArgs::with_event(Button::click_event());
    button.raise_event(&args);
    Ok(())
}

/// Sets the decorations of a window: 0 none, 1 border only, 2 full.
pub fn set_decorations(handle: Handle, mode: i32) -> Result<(), String> {
    let window = state::control(handle)
        .ok_or_else(|| format!("invalid handle {handle}"))?
        .cast::<Window>()
        .ok_or_else(|| "the handle is not a window".to_string())?;
    let decorations = match mode {
        0 => ferroui_controls::WindowDecorations::None,
        1 => ferroui_controls::WindowDecorations::BorderOnly,
        2 => ferroui_controls::WindowDecorations::Full,
        other => return Err(format!("unknown window decorations {other}")),
    };
    window.set_window_decorations(decorations);
    Ok(())
}

/// Closes the main window.
pub fn close(handle: Handle) -> Result<(), String> {
    let window = state::control(handle)
        .ok_or_else(|| format!("invalid handle {handle}"))?
        .cast::<Window>()
        .ok_or_else(|| "the handle is not a window".to_string())?;
    window.close();
    Ok(())
}
