#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${APP_DIR:-$HOME/quant}"
cd "$APP_DIR"

python3 -m venv venv
source venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

mkdir -p market_data logs

if [ ! -f .env ]; then
  cp .env.example .env
  echo "Created $APP_DIR/.env. Edit it before running Paper Trading."
fi

python -m py_compile QQQ_Trend.py

echo "Installation check passed."
echo "Next: edit $APP_DIR/.env, then run:"
echo "  source $APP_DIR/venv/bin/activate"
echo "  RUN_MODE=report RUN_BACKTEST=1 python $APP_DIR/QQQ_Trend.py"
