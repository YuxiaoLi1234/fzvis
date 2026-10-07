#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SPACK_ROOT="${SPACK_ROOT:-"$HOME/.fzvis/spack"}"
SPACK_REPO_DIR="${SPACK_REPO_DIR:-"$HOME/.fzvis/spack_packages"}"
FZVIS_ENV_DIR="${FZVIS_ENV_DIR:-"$ROOT_DIR/.venv"}"
FZVIS_HOST="${FZVIS_HOST:-0.0.0.0}"
FZVIS_PORT="${FZVIS_PORT:-10080}"
SPACK_LIBPRESSIO_SPEC="${SPACK_LIBPRESSIO_SPEC:-libpressio+python+sz3+zfp+fpzip+mgard ^openblas~fortran}"
SPACK_NODE_SPEC="${SPACK_NODE_SPEC:-node-js@20:}"
FZVIS_SKIP_SPACK="${FZVIS_SKIP_SPACK:-0}"
FZVIS_SKIP_NODE="${FZVIS_SKIP_NODE:-0}"
FZVIS_SKIP_FRONTEND_BUILD="${FZVIS_SKIP_FRONTEND_BUILD:-0}"

need_cmd() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "Missing required command: $1" >&2
    exit 1
  fi
}

clone_or_update() {
  local repo_url="$1"
  local target_dir="$2"
  if [ -d "$target_dir/.git" ]; then
    git -C "$target_dir" fetch --depth 1 origin
    git -C "$target_dir" pull --ff-only
  else
    git clone --depth 1 "$repo_url" "$target_dir"
  fi
}

need_cmd git
need_cmd python3

if [ "$FZVIS_SKIP_SPACK" != "1" ]; then
  echo "Installing or updating Spack in $SPACK_ROOT"
  clone_or_update "https://github.com/spack/spack.git" "$SPACK_ROOT"

  # shellcheck source=/dev/null
  . "$SPACK_ROOT/share/spack/setup-env.sh"

  echo "Adding libpressio Spack package repository in $SPACK_REPO_DIR"
  clone_or_update "https://github.com/robertu94/spack_packages.git" "$SPACK_REPO_DIR"
  spack repo add "$SPACK_REPO_DIR" || true

  echo "Installing native compressor dependencies: $SPACK_LIBPRESSIO_SPEC"
  spack install $SPACK_LIBPRESSIO_SPEC
  spack load libpressio

  if [ "$FZVIS_SKIP_NODE" != "1" ]; then
    echo "Installing Node.js through Spack: $SPACK_NODE_SPEC"
    spack install "$SPACK_NODE_SPEC"
    spack load node-js
  fi
elif [ -f "$SPACK_ROOT/share/spack/setup-env.sh" ]; then
  # shellcheck source=/dev/null
  . "$SPACK_ROOT/share/spack/setup-env.sh"
  spack load libpressio || true
  if [ "$FZVIS_SKIP_NODE" != "1" ]; then
    spack load node-js || true
  fi
fi

echo "Creating Python virtual environment in $FZVIS_ENV_DIR"
python3 -m venv "$FZVIS_ENV_DIR"
# shellcheck source=/dev/null
. "$FZVIS_ENV_DIR/bin/activate"
python -m pip install --upgrade pip
python -m pip install -r "$ROOT_DIR/requirements.txt"

if [ "$FZVIS_SKIP_FRONTEND_BUILD" != "1" ]; then
  need_cmd npm
  echo "Installing frontend dependencies"
  (cd "$ROOT_DIR" && npm ci)
  echo "Building frontend"
  (cd "$ROOT_DIR" && npm run build)
fi

cat > "$ROOT_DIR/scripts/run_fzvis.sh" <<RUNEOF
#!/usr/bin/env bash
set -euo pipefail
ROOT_DIR="\$(cd "\$(dirname "\${BASH_SOURCE[0]}")/.." && pwd)"
SPACK_ROOT="\${SPACK_ROOT:-"$SPACK_ROOT"}"
FZVIS_ENV_DIR="\${FZVIS_ENV_DIR:-"$FZVIS_ENV_DIR"}"
if [ -f "\$SPACK_ROOT/share/spack/setup-env.sh" ]; then
  . "\$SPACK_ROOT/share/spack/setup-env.sh"
  spack load libpressio || true
  spack load node-js || true
fi
. "\$FZVIS_ENV_DIR/bin/activate"
cd "\$ROOT_DIR"
python src/server/main.py --HOST "\${FZVIS_HOST:-$FZVIS_HOST}" --PORT "\${FZVIS_PORT:-$FZVIS_PORT}"
RUNEOF
chmod +x "$ROOT_DIR/scripts/run_fzvis.sh"

echo
echo "FZ-VIS installation complete."
echo "Start the app with:"
echo "  $ROOT_DIR/scripts/run_fzvis.sh"
echo
echo "Then open:"
echo "  http://localhost:$FZVIS_PORT"
