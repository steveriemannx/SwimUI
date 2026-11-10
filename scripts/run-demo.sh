#!/usr/bin/env bash
# Build and run a Swim program that uses the `FerroUI` native module.
#
# The bridge library (`scripts/build-ffi.sh`) is built on demand; the program
# is compiled with Swim and started in this terminal.  The default program is
# the SwimUI demo (`ui/FerroUIDemo.sw`).
#
#   scripts/run-demo.sh                       run the demo
#   scripts/run-demo.sh --snapshot ui/shots/demo.png
#                                             snapshot the window, then quit
#   scripts/run-demo.sh --smoke               one frame, then quit (for tests)
#   scripts/run-demo.sh --no-run              build only
#   scripts/run-demo.sh --program ui/Other.sw
#   scripts/run-demo.sh -- <arg> ...          pass arguments to the program
#
# Environment:
#   SWIMUI_MM          Swim memory management (default: arc)
#   SWIMUI_TIMEOUT_MS  how long the window stays open in a snapshot/smoke run
#   FERROUI_DIR        the FerroUI checkout to build the bridge against
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$HERE/.." && pwd)"
SWIM="$ROOT/bin/Swim"

PROGRAM="$ROOT/ui/FerroUIDemo.sw"
OUT="$ROOT/build/FerroUIDemo"
SNAPSHOT=""
SMOKE=0
NO_RUN=0
MM="${SWIMUI_MM:-arc}"
TIMEOUT_MS="${SWIMUI_TIMEOUT_MS:-}"

while [ $# -gt 0 ]; do
  case "$1" in
    --snapshot)
      SNAPSHOT="$2"; shift 2 ;;
    --snapshot=*)
      SNAPSHOT="${1#--snapshot=}"; shift ;;
    --smoke)
      SMOKE=1; shift ;;
    --no-run)
      NO_RUN=1; shift ;;
    --program)
      PROGRAM="$2"; shift 2 ;;
    --program=*)
      PROGRAM="${1#--program=}"; shift ;;
    --mm)
      MM="$2"; shift 2 ;;
    -h|--help)
      sed -n '2,22p' "$0"; exit 0 ;;
    --)
      shift; break ;;
    *)
      echo "run-demo.sh: unknown option: $1" >&2; exit 2 ;;
  esac
done

[ -x "$SWIM" ] || { echo "run-demo.sh: no Swim launcher at $SWIM" >&2; exit 1; }
# The SwimUI view layer is a Swim module of ui/; programs elsewhere (the tests)
# find it through SWIM_PATH.
export SWIM_PATH="$ROOT/ui${SWIM_PATH:+:$SWIM_PATH}"
PROGRAM="$(cd "$(dirname "$PROGRAM")" && pwd)/$(basename "$PROGRAM")"
[ -f "$PROGRAM" ] || { echo "run-demo.sh: no program at $PROGRAM" >&2; exit 1; }
case "$(uname -s)" in
  Darwin) BRIDGE="$ROOT/build/libferroui_swim.dylib" ;;
  *) BRIDGE="$ROOT/build/libferroui_swim.so" ;;
esac
if [ ! -f "$BRIDGE" ]; then
  echo "run-demo.sh: the bridge is not built; building it (this takes a while the first time)"
  "$HERE/build-ffi.sh"
fi

NIM_ARGS=()
mkdir -p "$ROOT/build"
if [ "$SMOKE" = "1" ] && [ -z "$SNAPSHOT" ]; then
  SNAPSHOT="$ROOT/build/smoke.png"
fi
if [ -n "$SNAPSHOT" ]; then
  SNAPSHOT_DIR="$(dirname "$SNAPSHOT")"
  mkdir -p "$SNAPSHOT_DIR"
  SNAPSHOT="$(cd "$SNAPSHOT_DIR" && pwd)/$(basename "$SNAPSHOT")"
  NIM_ARGS+=("--nim-arg:-d:swimFerroUIImage=$SNAPSHOT")
  if [ -z "$TIMEOUT_MS" ]; then
    TIMEOUT_MS=2400
  fi
fi
if [ "$SMOKE" = "1" ] && [ -z "${SWIMUI_TIMEOUT_MS:-}" ]; then
  TIMEOUT_MS="${TIMEOUT_MS:-2400}"
fi
if [ -n "$TIMEOUT_MS" ] && [ "$TIMEOUT_MS" != "0" ]; then
  NIM_ARGS+=("--nim-arg:-d:swimFerroUIQuitMs=$TIMEOUT_MS")
fi

echo "run-demo.sh: building $(basename "$PROGRAM")"
"$SWIM" build "$PROGRAM" -o "$OUT" --mm "$MM" "${NIM_ARGS[@]}"

if [ "$NO_RUN" = "1" ]; then
  echo "run-demo.sh: built $OUT"
  exit 0
fi

echo "run-demo.sh: running $OUT"
"$OUT" "$@"
if [ -n "$SNAPSHOT" ] && [ -f "$SNAPSHOT" ]; then
  echo "run-demo.sh: snapshot: $SNAPSHOT"
fi
