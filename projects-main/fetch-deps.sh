#!/usr/bin/env bash
# Fetch nimx and the Nim packages it needs into ./.deps/pkgs.
#
# The demo (and any other Swim program using `import Nimx`) builds against a
# local nimx checkout plus these packages.  Nothing is installed globally and
# nothing is written outside this directory.
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
DEST="${NIMX_DEPS:-$HERE/.deps/pkgs}"
mkdir -p "$DEST"
cd "$DEST"

repos=(
  nim-lang/sdl2
  nim-lang/opengl
  yglukhov/ttf
  yglukhov/kiwi
  yglukhov/variant
  yglukhov/rect_packer
  yglukhov/nimwebp
  yglukhov/clurp
  yglukhov/os_files
  yglukhov/clipboard
  yglukhov/async_http_request
  yglukhov/darwin
  yglukhov/jsbind
  yglukhov/plists
  yglukhov/nimsl
  yglukhov/wasmrt
  yglukhov/nester
)

for repo in "${repos[@]}"; do
  name="${repo##*/}"
  if [ -d "$name/.git" ]; then
    echo "already present: $name"
    continue
  fi
  echo "cloning $repo"
  git clone --depth 1 "https://github.com/$repo" "$name"
done

# nimwebp vendors libwebp as a git submodule (used by nimx/image.nim).
if [ -d nimwebp ] && [ -f nimwebp/.gitmodules ]; then
  echo "initialising nimwebp/libwebp submodule"
  git -C nimwebp submodule update --init --depth 1 --recursive
fi

echo
echo "dependencies are in $DEST"
echo "now run: NIMX_PATH=/path/to/nimx ./run.sh"
