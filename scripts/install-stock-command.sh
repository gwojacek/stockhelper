#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
INSTALL_DIR="${HOME}/.local/bin"
TARGET="${INSTALL_DIR}/stock"
SOURCE="${PROJECT_ROOT}/stock"
mkdir -p "${INSTALL_DIR}"

if ln -sfn "${SOURCE}" "${TARGET}" 2>/dev/null; then
  INSTALL_KIND="symlinked"
else
  cp "${SOURCE}" "${TARGET}"
  chmod +x "${TARGET}"
  INSTALL_KIND="copied"
fi

cat <<MSG
Installed StockHelper Docker shortcut (${INSTALL_KIND}):
  ${TARGET}

If 'stock' is not found, add this to your shell config and restart the terminal:
  export PATH="\$HOME/.local/bin:\$PATH"

README/PyCharm commands are copy-ready `stock ...` commands:
  stock -allsearch all
  stock --help

Terminal commands can use either:
  stock --help
  ./stock --help

Try:
  stock --help
  stock -allsearch all
  stock --open-allsearch-report all
  stock --cleanup
  stock --fix-permissions
MSG
