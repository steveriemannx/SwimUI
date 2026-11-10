"""The `FerroUI` native module of SwimUI: the C-level binding of FerroUI.

A `.sw` source that writes ``import FerroUI`` gets the free functions below.
They are not declared anywhere in ``.sw`` source: the compiler knows them from
this table, checks their arguments like those of any other function and emits
a direct call to the C shim in ``runtime/swimferroui.c``.  The shim in turn
calls the Rust bridge ``ferroui-swim`` (``ffi/``), which hosts the FerroUI
application; ``ferro_swim_*`` is the flat C ABI documented in
``ffi/include/ferroui_swim.h``.

The module is the only part of SwimUI that the language implementation has to
know about:

* :mod:`swimc.modules` accepts the import and records it on the project,
* :mod:`swimc.checker` type-checks calls against :data:`FERROUI_FUNCS`,
* :mod:`swimc.codegen_c` emits ``#include "swimferroui.h"`` and the calls,
* :mod:`swimc.cli` compiles ``runtime/swimferroui.c`` into the program and
  links the bridge library.

Keep :data:`FERROUI_FUNCS` in sync with ``runtime/swimferroui.h`` and
``runtime/swimferroui.c``.
"""

from __future__ import annotations

# The name a `.sw` file imports.
MODULE_NAME = "FerroUI"

# What the compiler adds to a program that imports the module.
SHIM_HEADER = "swimferroui.h"
SHIM_SOURCE = "swimferroui.c"

# The Rust bridge: `build/libferroui_swim.<ext>`; `scripts/build-ffi.sh`
# builds it and SWIM_FERROUI_LIB_DIR points a build somewhere else.
LIBRARY_NAME = "ferroui_swim"
LIBRARY_DIR_ENV = "SWIM_FERROUI_LIB_DIR"

# kind -> the Swift type the argument (or the result) has.
KINDS = ("int", "double", "string", "bool", "closure")
RESULT_KINDS = ("int", "double", "string", "bool", "void")

# Swift name -> (C function, [(argument label, kind)], result kind).
FERROUI_FUNCS = {
    # -- the application ----------------------------------------------------
    "ferrouiRun": ("swimferroui_run", [("build", "closure")], "void"),
    "ferrouiQuit": ("swimferroui_quit", [], "void"),
    "ferrouiAfter": ("swimferroui_after",
                     [("ms", "int"), ("action", "closure")], "void"),
    "ferrouiLog": ("swimferroui_log", [("message", "string")], "void"),
    "ferrouiVersion": ("swimferroui_version", [], "string"),
    "ferrouiSetThemeVariant": ("swimferroui_set_theme_variant",
                               [("name", "string")], "void"),
    # -- tests and documentation -------------------------------------------
    "ferrouiImagePath": ("swimferroui_image_path", [], "string"),
    "ferrouiAutoQuitMs": ("swimferroui_auto_quit_ms", [], "int"),
    "ferrouiSnapshot": ("swimferroui_snapshot",
                        [("delayMs", "int"), ("path", "string")], "void"),
    # -- the window ---------------------------------------------------------
    "ferrouiWindow": ("swimferroui_window",
                      [("width", "int"), ("height", "int"),
                       ("title", "string"), ("background", "int"),
                       ("onClosed", "closure")], "int"),
    "ferrouiClientWidth": ("swimferroui_client_width", [], "int"),
    "ferrouiClientHeight": ("swimferroui_client_height", [], "int"),
    "ferrouiSetDecorations": ("swimferroui_set_decorations",
                              [("window", "int"), ("mode", "int")], "void"),
    "ferrouiOnReady": ("swimferroui_on_ready",
                       [("window", "int"), ("onReady", "closure")], "void"),
    "ferrouiClose": ("swimferroui_close", [("window", "int")], "void"),
    # -- the tree -----------------------------------------------------------
    "ferrouiCreate": ("swimferroui_create",
                      [("parent", "int"), ("kind", "int")], "int"),
    "ferrouiAddChild": ("swimferroui_add_child",
                        [("parent", "int"), ("child", "int")], "void"),
    "ferrouiInsertChild": ("swimferroui_insert_child",
                           [("parent", "int"), ("index", "int"),
                            ("child", "int")], "void"),
    "ferrouiRemoveChild": ("swimferroui_remove_child",
                           [("parent", "int"), ("child", "int")], "void"),
    "ferrouiClearChildren": ("swimferroui_clear_children",
                             [("parent", "int")], "void"),
    "ferrouiDestroy": ("swimferroui_destroy", [("handle", "int")], "void"),
    # -- properties ---------------------------------------------------------
    "ferrouiSetF64": ("swimferroui_set_f64",
                      [("handle", "int"), ("property", "int"),
                       ("value", "double")], "void"),
    "ferrouiSetI32": ("swimferroui_set_i32",
                      [("handle", "int"), ("property", "int"),
                       ("value", "int")], "void"),
    "ferrouiSetString": ("swimferroui_set_string",
                         [("handle", "int"), ("property", "int"),
                          ("value", "string")], "void"),
    "ferrouiSetBool": ("swimferroui_set_bool",
                       [("handle", "int"), ("property", "int"),
                        ("value", "bool")], "void"),
    "ferrouiSetColor": ("swimferroui_set_color",
                        [("handle", "int"), ("property", "int"),
                         ("argb", "int")], "void"),
    "ferrouiSetThickness": ("swimferroui_set_thickness",
                            [("handle", "int"), ("property", "int"),
                             ("left", "int"), ("top", "int"),
                             ("right", "int"), ("bottom", "int")], "void"),
    "ferrouiSetEnum": ("swimferroui_set_enum",
                       [("handle", "int"), ("property", "int"),
                        ("value", "int")], "void"),
    "ferrouiSetFlex": ("swimferroui_set_flex",
                       [("handle", "int"), ("direction", "int"),
                        ("justify", "int"), ("align", "int"),
                        ("columnSpacing", "int"), ("rowSpacing", "int")],
                       "void"),
    "ferrouiSetGrow": ("swimferroui_set_grow",
                       [("handle", "int"), ("grow", "double")], "void"),
    "ferrouiSetFrame": ("swimferroui_set_frame",
                        [("handle", "int"), ("x", "int"), ("y", "int"),
                         ("width", "int"), ("height", "int")], "void"),
    # -- events -------------------------------------------------------------
    "ferrouiOnTap": ("swimferroui_on_tap",
                     [("handle", "int"), ("action", "closure")], "void"),
    "ferrouiOnTextChanged": ("swimferroui_on_text_changed",
                             [("handle", "int"), ("action", "closure")],
                             "void"),
    "ferrouiOnCheckedChanged": ("swimferroui_on_checked_changed",
                                [("handle", "int"), ("action", "closure")],
                                "void"),
    "ferrouiOnValueChanged": ("swimferroui_on_value_changed",
                              [("handle", "int"), ("action", "closure")],
                              "void"),
    # -- reading values back ------------------------------------------------
    "ferrouiGetValue": ("swimferroui_get_value", [("handle", "int")],
                        "double"),
    "ferrouiGetText": ("swimferroui_get_text", [("handle", "int")], "string"),
    "ferrouiGetChecked": ("swimferroui_get_checked", [("handle", "int")],
                          "bool"),
    "ferrouiGetVisible": ("swimferroui_get_visible", [("handle", "int")],
                          "bool"),
    # -- tests --------------------------------------------------------------
    "ferrouiRaiseClick": ("swimferroui_raise_click", [("handle", "int")],
                          "void"),
}


def is_ferroui_function(name: str) -> bool:
    """Whether `name` is a free function of the module."""
    return name in FERROUI_FUNCS
