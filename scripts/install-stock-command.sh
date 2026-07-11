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

if [[ "\${1:-}" == "--cleanup" ]]; then
  echo "Stopping StockHelper report containers..."
  docker ps -aq --filter "name=stockhelper" | xargs -r docker rm -f
  echo "Removing dangling Docker images..."
  docker image prune -f
  echo "Removing unused build cache..."
  docker builder prune -f
  echo "Done. Current StockHelper images:"
  docker images 'stockhelper*'
  exit 0
fi

if [[ "\${1:-}" == "--fix-permissions" ]]; then
  echo "Fixing ownership for StockHelper generated files..."
  paths=(data charts chart_program/data Trojpolowki debug configs .docker-home)
  existing=()
  for path in "\${paths[@]}"; do
    [[ -e "\$path" ]] && existing+=("\$path")
  done
  if [[ "\${#existing[@]}" -eq 0 ]]; then
    echo "No generated StockHelper paths found."
    exit 0
  fi
  if chown -R "\$(id -u):\$(id -g)" "\${existing[@]}" 2>/dev/null; then
    echo "Permissions fixed."
  else
    echo "Could not change every file as your user. Run this once:"
    printf '  sudo chown -R %q:%q' "\$(id -u)" "\$(id -g)"
    printf ' %q' "\${existing[@]}"
    printf '\n'
    exit 1
  fi
  exit 0
fi

export STOCKHELPER_UID="\${STOCKHELPER_UID:-\$(id -u)}"
export STOCKHELPER_GID="\${STOCKHELPER_GID:-\$(id -g)}"

_stop_old_report_containers() {
  if [[ "\${STOCKHELPER_KEEP_OLD_REPORTS:-0}" == "1" ]]; then
    return 0
  fi
  docker ps -aq --filter "name=stockhelper" --filter "ancestor=stockhelper:latest" | xargs -r docker rm -f >/dev/null 2>&1 || true
}

_should_watch_for_report_url=0
for arg in "\$@"; do
  case "\$arg" in
    -allsearch|--open-allsearch-report|--journal-html|--journal-pdf)
      _should_watch_for_report_url=1
      ;;
  esac
done

if [[ "\$_should_watch_for_report_url" == "1" ]]; then
  _stop_old_report_containers
  _opened_url=""
  docker compose run --rm --no-deps stockhelper "\$@" 2>&1 | while IFS= read -r line; do
    printf '%s\n' "\$line"
    if [[ -z "\$_opened_url" && "\$line" =~ (https?://(127\.0\.0\.1|localhost):[0-9]+[^[:space:]]*) ]]; then
      _opened_url="\${BASH_REMATCH[1]}"
      if command -v google-chrome >/dev/null 2>&1; then
        google-chrome --new-window "\$_opened_url" >/dev/null 2>&1 &
      elif command -v chromium >/dev/null 2>&1; then
        chromium --new-window "\$_opened_url" >/dev/null 2>&1 &
      elif command -v chromium-browser >/dev/null 2>&1; then
        chromium-browser --new-window "\$_opened_url" >/dev/null 2>&1 &
      elif command -v xdg-open >/dev/null 2>&1; then
        xdg-open "\$_opened_url" >/dev/null 2>&1 &
      elif command -v gio >/dev/null 2>&1; then
        gio open "\$_opened_url" >/dev/null 2>&1 &
      fi
    fi
  done
  exit "\${PIPESTATUS[0]}"
fi

exec docker compose run --rm --no-deps stockhelper "\$@"
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
  stock --cleanup
  stock --fix-permissions
MSG
