#!/usr/bin/env bash
# Shell environment for the design-report build.
# Both TeX (TinyTeX, user-level) and Node (nvm) are installed outside the
# default PATH, so every build script sources this first.

set -euo pipefail

TEXBIN="$HOME/Library/TinyTeX/bin/universal-darwin"
if [ -d "$TEXBIN" ]; then
  case ":$PATH:" in
    *":$TEXBIN:"*) ;;
    *) PATH="$TEXBIN:$PATH" ;;
  esac
fi
export PATH

export NVM_DIR="${NVM_DIR:-$HOME/.nvm}"
if [ -s "$NVM_DIR/nvm.sh" ]; then
  # shellcheck disable=SC1091
  . "$NVM_DIR/nvm.sh" >/dev/null 2>&1 || true
  nvm use 22 >/dev/null 2>&1 || true
fi
