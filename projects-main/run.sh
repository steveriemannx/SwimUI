#!/usr/bin/env bash
# Build and run the Swim + nimx phone demo.
#
#   ./run.sh                       build and show the window
#   ./run.sh --bundle              build and launch as a macOS .app
#   ./run.sh --snapshot shot.png   render one frame to a PNG, then quit
#   ./run.sh --bundle --snapshot shot.png
#
# Environment:
#   NIMX_PATH    path to a nimx checkout         (default: ~/projects-main/nimx)
#   NIMX_DEPS    path to the cloned nimx deps    (default: ./.deps/pkgs)
#   SWIM_MM      memory management mode          (default: atomicArc)
#   SDL2_LIBDIR  directory containing libSDL2.*  (auto-detected)
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
SWIM_ROOT="$(cd "$HERE/.." && pwd)"
SWIM="$SWIM_ROOT/bin/Swim"

NIMX_PATH="${NIMX_PATH:-$HOME/projects-main/nimx}"
DEPS_PKGS="${NIMX_DEPS:-$HERE/.deps/pkgs}"
# Swift uses atomically refcounted ARC; Nim's equivalent is --mm:atomicArc.
MM="${SWIM_MM:-atomicArc}"
OUT_DIR="$HERE/build"
BINARY="$OUT_DIR/PhoneDemo"

BUNDLE=0
SNAPSHOT=""
while [ $# -gt 0 ]; do
  case "$1" in
    --bundle) BUNDLE=1; shift ;;
    --snapshot)
      SNAPSHOT="$2"; shift 2 ;;
    --snapshot=*)
      SNAPSHOT="${1#--snapshot=}"; shift ;;
    --no-run) NO_RUN=1; shift ;;
    -h|--help)
      sed -n '2,16p' "$0"; exit 0 ;;
    *)
      echo "unknown option: $1" >&2; exit 2 ;;
  esac
done

if [ ! -x "$SWIM" ]; then
  echo "error: Swim launcher not found at $SWIM" >&2
  exit 1
fi
if [ ! -d "$NIMX_PATH" ]; then
  echo "error: nimx checkout not found at $NIMX_PATH" >&2
  echo "       set NIMX_PATH or clone https://github.com/yglukhov/nimx" >&2
  exit 1
fi
if [ ! -d "$DEPS_PKGS" ]; then
  echo "error: nimx dependencies not found at $DEPS_PKGS" >&2
  echo "       run $HERE/fetch-deps.sh first" >&2
  exit 1
fi

# nim's SDL2 binding loads libSDL2 dynamically at run time.
SDL2_LIBDIR="${SDL2_LIBDIR:-}"
if [ -z "$SDL2_LIBDIR" ]; then
  for dir in /opt/homebrew/lib /usr/local/lib /usr/lib/aarch64-linux-gnu \
             /usr/lib/x86_64-linux-gnu /usr/lib; do
    if [ -e "$dir/libSDL2.dylib" ] || [ -e "$dir/libSDL2.so" ]; then
      SDL2_LIBDIR="$dir"; break
    fi
  done
fi
if [ -n "$SDL2_LIBDIR" ]; then
  export DYLD_LIBRARY_PATH="$SDL2_LIBDIR${DYLD_LIBRARY_PATH:+:$DYLD_LIBRARY_PATH}"
  export LD_LIBRARY_PATH="$SDL2_LIBDIR${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
fi

# nimx and its dependencies are ordinary Nim packages: pass them as --path.
NIM_ARGS=("--nim-arg:--path:$NIMX_PATH")
for pkg in sdl2/src opengl/src ttf kiwi variant rect_packer nimwebp/src clurp \
           os_files clipboard async_http_request darwin jsbind plists nimsl \
           wasmrt nester; do
  NIM_ARGS+=("--nim-arg:--path:$DEPS_PKGS/$pkg")
done
# Bake the SDL2 directory into the binary's rpath so it also starts from a
# .app bundle (which does not inherit this shell's environment).
if [ -n "$SDL2_LIBDIR" ]; then
  NIM_ARGS+=("--nim-arg:--passL:-Wl,-rpath,$SDL2_LIBDIR")
fi
if [ -n "${SWIM_NIM_ARGS:-}" ]; then
  # shellcheck disable=SC2206
  NIM_ARGS+=($SWIM_NIM_ARGS)
fi
if [ -n "$SNAPSHOT" ]; then
  SNAP_DIR="$(dirname "$SNAPSHOT")"
  mkdir -p "$SNAP_DIR"
  SNAPSHOT="$(cd "$SNAP_DIR" && pwd)/$(basename "$SNAPSHOT")"
  NIM_ARGS+=("--nim-arg:-d:swimNimxSnapshotPath=$SNAPSHOT")
fi

mkdir -p "$OUT_DIR"
echo "building PhoneDemo (--mm:$MM) ..."
"$SWIM" build "$HERE/PhoneDemo.sw" -o "$BINARY" --mm "$MM" "${NIM_ARGS[@]}"
echo "built $BINARY"

[ -n "${NO_RUN:-}" ] && exit 0

if [ "$BUNDLE" = "1" ]; then
  if [ "$(uname -s)" != "Darwin" ]; then
    echo "--bundle is only supported on macOS" >&2
    exit 1
  fi
  APP="$OUT_DIR/PhoneDemo.app"
  rm -rf "$APP"
  mkdir -p "$APP/Contents/MacOS"
  cp "$BINARY" "$APP/Contents/MacOS/PhoneDemo"
  cat > "$APP/Contents/Info.plist" <<'PLIST'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>CFBundleExecutable</key><string>PhoneDemo</string>
  <key>CFBundleIdentifier</key><string>dev.Swim.nimx.phonedemo</string>
  <key>CFBundleName</key><string>Swim nimx PhoneDemo</string>
  <key>CFBundlePackageType</key><string>APPL</string>
  <key>CFBundleShortVersionString</key><string>1.0</string>
  <key>NSHighResolutionCapable</key><true/>
  <key>NSPrincipalClass</key><string>NSApplication</string>
</dict></plist>
PLIST
  echo "launching $APP ..."
  open -W "$APP"
  if [ -n "$SNAPSHOT" ] && [ -f "$SNAPSHOT" ]; then
    echo "snapshot: $SNAPSHOT"
  fi
else
  exec "$BINARY"
fi
