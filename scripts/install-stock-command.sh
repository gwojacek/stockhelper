#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
INSTALL_DIR="${HOME}/.local/bin"
TARGET="${INSTALL_DIR}/stock"
mkdir -p "${INSTALL_DIR}"

cat > "${TARGET}" <<WRAPPER
#!/usr/bin/env bash
set -o pipefail
PROJECT_ROOT=${PROJECT_ROOT@Q}
cd "\$PROJECT_ROOT" || exit 1

_should_watch_for_report_url=0
for arg in "\$@"; do
  case "\$arg" in
    -allsearch|--open-allsearch-report|--journal-html|--journal-pdf)
      _should_watch_for_report_url=1
      ;;
  esac
done

if [[ "\$_should_watch_for_report_url" == "1" ]]; then
  _opened_url=""
  docker compose run --rm stockhelper "\$@" 2>&1 | while IFS= read -r line; do
    printf '%s\n' "\$line"
    if [[ -z "\$_opened_url" && "\$line" =~ (https?://[^[:space:]]+) ]]; then
      _opened_url="\${BASH_REMATCH[1]}"
      if command -v xdg-open >/dev/null 2>&1; then
        xdg-open "\$_opened_url" >/dev/null 2>&1 &
      elif command -v gio >/dev/null 2>&1; then
        gio open "\$_opened_url" >/dev/null 2>&1 &
      fi
    fi
  done
  exit "\${PIPESTATUS[0]}"
fi

exec docker compose run --rm stockhelper "\$@"
WRAPPER

chmod +x "${TARGET}"

cat <<MSG
Installed StockHelper Docker shortcut:
  ${TARGET}

If 'stock' is not found, add this to your shell config and restart the terminal:
  export PATH="\$HOME/.local/bin:\$PATH"

Try:
  stock --help
  stock -allsearch all
  stock --open-allsearch-report all
MSG
