#!/bin/sh
# Always resolve relative resources against this extracted package, not the cwd.
set -eu
cd -- "$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
if ! command -v python3 >/dev/null 2>&1; then
    command -v kdialog >/dev/null 2>&1 && kdialog --error 'Se necesita Python 3 del sistema para instalar.'
    exit 1
fi
exec python3 ./install.py "$@"
