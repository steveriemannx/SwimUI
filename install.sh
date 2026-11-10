#!/usr/bin/env bash
# Install the Swim compiler by symlinking bin/Swim into PREFIX/bin.
#
#   ./install.sh                          # /usr/local/bin/Swim
#   PREFIX=$HOME/.local ./install.sh      # ~/.local/bin/Swim
#
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PREFIX="${PREFIX:-/usr/local}"
BINDIR="$PREFIX/bin"

if ! command -v python3 >/dev/null 2>&1; then
  echo "error: python3 is required (the Swim compiler is written in Python)." >&2
  exit 1
fi
if ! command -v nim >/dev/null 2>&1; then
  echo "warning: 'nim' was not found in PATH; Swim needs it to compile programs." >&2
  echo "         install Nim from https://nim-lang.org/install.html" >&2
fi

if ! mkdir -p "$BINDIR" 2>/dev/null; then
  echo "error: cannot create $BINDIR" >&2
  echo "try: sudo PREFIX=$PREFIX $0" >&2
  exit 1
fi
if [ ! -w "$BINDIR" ]; then
  echo "error: $BINDIR is not writable" >&2
  echo "try: sudo PREFIX=$PREFIX $0" >&2
  exit 1
fi

ln -sf "$ROOT/bin/Swim" "$BINDIR/Swim"
echo "installed: $BINDIR/Swim"
"$BINDIR/Swim" version
echo "try: Swim run $ROOT/examples/hello.sw"
