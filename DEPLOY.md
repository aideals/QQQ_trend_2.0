# QQQ Trend V2.1 Server Deployment

## 1. Server

Ubuntu 24.04, 1-2 vCPU, 2 GB RAM is sufficient for this strategy.

## 2. Upload

Copy these files into `/home/quant/quant/`:

- `QQQ_Trend.py`
- `requirements.txt`
- `.env.example`
- `.gitignore`
- `qqq-trend.service`
- `qqq-trend.timer`
- `deploy_server.sh`

Then:

```bash
cd /home/quant/quant
chmod +x deploy_server.sh
./deploy_server.sh
cp .env.example .env
nano .env
```

## 3. Paper Trading first

Set:

```text
RUN_MODE=paper
RUN_BACKTEST=0
ALLOW_LIVE_TRADING=0
```

Run manually once:

```bash
source venv/bin/activate
python QQQ_Trend.py
```

Check:

```bash
tail -f logs/strategy.log
```

## 4. Install systemd timer

The supplied unit uses Linux user `quant` and path `/home/quant/quant`. Change those if your server uses another user/path.

```bash
sudo cp qqq-trend.service /etc/systemd/system/
sudo cp qqq-trend.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now qqq-trend.timer
```

Check:

```bash
systemctl list-timers | grep qqq-trend
systemctl status qqq-trend.timer
journalctl -u qqq-trend.service -n 100 --no-pager
```

The timer is scheduled for weekdays at 18:30 America/New_York with a small randomized delay.

## 5. Backtest/report

To run the full Walk Forward + Monte Carlo report manually:

```bash
RUN_MODE=report RUN_BACKTEST=1 python QQQ_Trend.py
```

The report and equity curve are written to `logs/`.

## 6. Live trading

Do not enable this until Paper Trading has been verified.

Required settings:

```text
RUN_MODE=live
RUN_BACKTEST=0
ALLOW_LIVE_TRADING=1
```

The code intentionally requires both `RUN_MODE=live` and `ALLOW_LIVE_TRADING=1` before sending real orders.
