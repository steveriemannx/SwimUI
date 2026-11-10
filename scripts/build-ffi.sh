#!/usr/bin/env bash
# Build the Rust bridge that the `FerroUI` native module of Swim calls.
#
# Swim compiles a `.sw` program to C; a program that writes `import FerroUI`
# also compiles the C shim `runtime/swimferroui.c` into itself and links the
# shared library this script builds from `ffi/`.  The shim (C) calls the flat
# C ABI of the bridge (`ffi/include/ferroui_swim.h`), which hosts the FerroUI
# application and its controls.
#
#   scripts/build-ffi.sh              build the bridge (debug, fast to iterate)
#   scripts/build-ffi.sh --release    optimised build (slow the first time)
#
# Environment:
#   FERROUI_DIR        the FerroUI checkout to build against
#                      (default: the `FerroUI` next to this checkout)
#   FERROUI_TARGET_DIR the cargo target directory (default: $FERROUI_DIR/target,
#                      so a FerroUI build of the same feature set is reused)
#   CARGO              the cargo executable (default: cargo from PATH)
#   CARGO_INCREMENTAL  cargo incremental compilation (default: 0)
#
# A FerroUI checkout is a Rust workspace of about a hundred crates whose debug
# build takes tens of GB; pointing the target directory at the checkout of
# FerroUI reuses the artifacts it already built, and the first build of the
# bridge then takes minutes instead of an hour.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$HERE/.." && pwd)"
FERROUI_DIR="${FERROUI_DIR:-$(cd "$ROOT/.." && pwd)/FerroUI}"
CARGO="${CARGO:-cargo}"
RELEASE=0

for arg in "$@"; do
  case "$arg" in
    --release) RELEASE=1 ;;
    -h|--help)
      sed -n '2,27p' "$0"; exit 0 ;;
    *)
      echo "build-ffi.sh: unknown option: $arg" >&2; exit 2 ;;
  esac
done

if [ ! -f "$FERROUI_DIR/src/FerroUI.Base/Cargo.toml" ] ||
   [ ! -f "$FERROUI_DIR/src/FerroUI.Desktop/Cargo.toml" ]; then
  echo "build-ffi.sh: no FerroUI checkout at $FERROUI_DIR" >&2
  echo "build-ffi.sh: set FERROUI_DIR to the checkout of FerroUI to build against" >&2
  exit 1
fi
command -v "$CARGO" >/dev/null 2>&1 || {
  echo "build-ffi.sh: cargo not found (install Rust: https://rustup.rs)" >&2
  exit 1
}

MANIFEST="$ROOT/ffi/Cargo.toml"
# The manifest names the checkout next to this one; a checkout somewhere else
# gets a manifest generated into build/ with the same content and that path.
if [ "$(cd "$FERROUI_DIR" && pwd)" != "$(cd "$ROOT/../FerroUI" 2>/dev/null && pwd)" ]; then
  MANIFEST="$ROOT/build/ffi-manifest/Cargo.toml"
  mkdir -p "$(dirname "$MANIFEST")"
  sed -e "s|path = \"../../FerroUI/|path = \"$FERROUI_DIR/|g" \
      -e "s|path = \"src/lib.rs\"|path = \"$ROOT/ffi/src/lib.rs\"|" \
      "$ROOT/ffi/Cargo.toml" > "$MANIFEST"
  echo "build-ffi.sh: FerroUI at $FERROUI_DIR; manifest generated at $MANIFEST"
fi

TARGET_DIR="${FERROUI_TARGET_DIR:-$FERROUI_DIR/target}"
export CARGO_TARGET_DIR="$TARGET_DIR"
export CARGO_INCREMENTAL="${CARGO_INCREMENTAL:-0}"

PROFILE_ARGS=()
PROFILE_DIR="debug"
if [ "$RELEASE" = "1" ]; then
  PROFILE_ARGS=(--release)
  PROFILE_DIR="release"
fi

echo "build-ffi.sh: building the FerroUI bridge against $FERROUI_DIR"
echo "build-ffi.sh: target directory $TARGET_DIR"
"$CARGO" build --manifest-path "$MANIFEST" "${PROFILE_ARGS[@]}"

case "$(uname -s)" in
  Darwin) LIBRARY="libferroui_swim.dylib" ;;
  Linux) LIBRARY="libferroui_swim.so" ;;
  MINGW*|MSYS*|CYGWIN*) LIBRARY="ferroui_swim.dll" ;;
  *) LIBRARY="libferroui_swim.so" ;;
esac

BUILT="$TARGET_DIR/$PROFILE_DIR/$LIBRARY"
if [ ! -f "$BUILT" ]; then
  echo "build-ffi.sh: the build produced no $BUILT" >&2
  exit 1
fi

mkdir -p "$ROOT/build"
cp "$BUILT" "$ROOT/build/$LIBRARY"
echo "build-ffi.sh: installed build/$LIBRARY"
echo "build-ffi.sh: now run: ./scripts/run-demo.sh"
