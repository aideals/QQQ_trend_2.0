#!/bin/bash
# 美股策略每日自动运行脚本

# 日志文件
LOG_DIR="/root/quant/venv/QQQ_trend_2.0/logs"
mkdir -p "$LOG_DIR"
LOG_FILE="$LOG_DIR/cron_$(date +%Y%m%d).log"

# 激活虚拟环境
source /root/quant/venv/bin/activate

# 切换到项目目录
cd /root/quant/venv/QQQ_trend_2.0

echo "===== $(date '+%Y-%m-%d %H:%M:%S') 开始运行策略 =====" >> "$LOG_FILE"

# 清空代理变量（你之前遇到的代理问题），运行策略
env HTTP_PROXY= HTTPS_PROXY= NO_PROXY= http_proxy= https_proxy= no_proxy= \
    python3 QQQ_Trend_Server.py >> "$LOG_FILE" 2>&1

echo "===== $(date '+%Y-%m-%d %H:%M:%S') 策略运行结束 =====" >> "$LOG_FILE"
echo "" >> "$LOG_FILE"
