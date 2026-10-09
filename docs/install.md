# Installation

FZ-VIS can be installed from source with the helper script below. The script installs Spack locally, uses Spack to install the native compressor stack, creates a Python virtual environment, installs frontend dependencies, builds the Vue app, and writes a small launcher script.

## Prerequisites

Install these system tools first:

- `git`
- `python3` with `venv`
- a working compiler toolchain for Spack builds
- `npm`, unless you let Spack install Node.js for you

The native compression dependencies are installed through Spack:

- `libpressio` with Python bindings
- SZ3, ZFP, FPZIP, MGARD support through libpressio

## Quick Install

From the repository root:

```sh
./scripts/install_fzvis.sh
```

Then start FZ-VIS with:

```sh
./scripts/run_fzvis.sh
```

Open the app at:

```text
http://localhost:10080
```

## Useful Options

The installer can be customized with environment variables:

```sh
SPACK_ROOT=$HOME/spack ./scripts/install_fzvis.sh
FZVIS_ENV_DIR=$PWD/.venv ./scripts/install_fzvis.sh
FZVIS_PORT=5001 ./scripts/install_fzvis.sh
FZVIS_SKIP_SPACK=1 ./scripts/install_fzvis.sh
FZVIS_SKIP_NODE=1 ./scripts/install_fzvis.sh
FZVIS_SKIP_FRONTEND_BUILD=1 ./scripts/install_fzvis.sh
```

`FZVIS_SKIP_SPACK=1` assumes Spack/libpressio are already installed or available in your environment.

## Manual Developer Install

If you prefer to install each layer yourself:

```sh
git clone https://github.com/YuxiaoLi1234/fzvis.git
cd fzvis

python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

npm ci
npm run build
```

Load a libpressio installation with Python bindings before starting the server. For example, if you installed it with Spack:

```sh
source $SPACK_ROOT/share/spack/setup-env.sh
spack load libpressio
```

Then run:

```sh
python src/server/main.py --HOST 0.0.0.0 --PORT 10080
```

## Environment Variables

Copy `.env.example` to `.env` and edit as needed:

```sh
cp .env.example .env
```

Important values:

- `FLASK_SECRET_KEY`: secret used to sign tokens and protect sessions
- `FLASK_PASSCODE`: optional passcode; leave blank to skip passcode auth
- `LLM_API_KEY` / `NVIDIA_API_KEY`: optional API key for LLM features from https://build.nvidia.com/models
- `FZVIS_CACHE_SIZE`: default item limit for in-memory LRU caches (default: 50)
- `FZVIS_INPUT_CACHE_SIZE`: item limit for uploaded input datasets cache (default: 50)
- `FZVIS_DECOMPRESSED_CACHE_SIZE`: item limit for decompressed data cache (default: 50)
- `FZVIS_MAX_COMPRESSOR_INSTANCES`: maximum concurrent compressor instances per session (default: 10)
- `FZVIS_MAX_UPLOAD_SIZE`: maximum file upload size (e.g. `100MB`, `500MB`, `2GB`; default: `100MB`)
- `FZVIS_CASE_STUDY_ROOT`: directory path for saved case studies (default: `./case_studies`)
