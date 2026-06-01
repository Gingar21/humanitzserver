#!/usr/bin/env bash
set -e
cd "$(dirname "$0")"

if [ ! -d ".venv-build" ]; then
  python3 -m venv .venv-build
fi

source .venv-build/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m pip install pyinstaller
pyinstaller --noconfirm --clean --distpath dist-linux --workpath build-linux server-manager-linux.spec

echo
echo "Build termine."
echo "Binaire: $(pwd)/dist-linux/server-manager"
