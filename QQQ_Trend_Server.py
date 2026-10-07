# ============================================================
# QQQ Trend Following System V2.1 - SERVER EDITION
# ============================================================
# Based directly on the uploaded QQQ_Trend.py V2.0 strategy.
# RUN_MODE=report : full backtest/report, no orders
# RUN_MODE=paper  : daily decision + Alpaca PAPER rebalance
# RUN_MODE=live   : REAL orders only when ALLOW_LIVE_TRADING=1
# Daily paper/live mode skips Walk Forward + Monte Carlo.
# ============================================================

# ============================================================
# QQQ Trend Following System V2.0
#
# Features:
# - Multi ETF Rotation
# - QQQ + SPY Market Filter
# - Volatility Targeting
# - Sharpe Walk Forward Optimization
# - Monte Carlo Stress Test
# - Alpaca Execution
#
# Part 1/4
# Data Layer
# ============================================================


import os
import sys
import time
import warnings
import logging
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import yfinance as yf
from dotenv import load_dotenv


warnings.filterwarnings("ignore")

# ============================================================
# SERVER RUNTIME CONFIG
# ============================================================

BASE_DIR = Path(__file__).resolve().parent
DATA_FOLDER = str(BASE_DIR / "market_data")
LOG_FOLDER = BASE_DIR / "logs"
LOG_FOLDER.mkdir(parents=True, exist_ok=True)
load_dotenv(BASE_DIR / ".env")

# 引入 1% 的过滤带，减少假突破
BUFFER_PCT = 0.01 

RUN_MODE = os.getenv("RUN_MODE", "report").lower()
# report = backtest/report only
# paper  = daily allocation + Alpaca paper execution
# live   = REAL trading (requires explicit opt-in below)

RUN_BACKTEST = os.getenv("RUN_BACKTEST", "1") == "1"
ALLOW_LIVE_TRADING = os.getenv("ALLOW_LIVE_TRADING", "0") == "1"
TIMEZONE = ZoneInfo("America/New_York")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    handlers=[
        logging.FileHandler(LOG_FOLDER / "strategy.log"),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger("QQQTrend")



# ============================================================
# 1. CONFIGURATION
# ============================================================


START_DATE = "2010-01-01"

TODAY = datetime.now(TIMEZONE).strftime("%Y-%m-%d")



# ETF universe

ETF_LIST = [

    "QQQ",
    "SPY",
    "IWM",
    "TLT",
    "GLD",
    "BIL"

]



# Benchmark

BENCHMARK = "QQQ"



# Portfolio settings


INITIAL_CAPITAL = 100000


TARGET_VOL = 0.15


TRANSACTION_COST = 0.001



# Walk Forward


TRAIN_WINDOW = 756
# 3 years


TEST_WINDOW = 126
# 6 months



# Cache folder is configured above relative to this script.
Path(DATA_FOLDER).mkdir(parents=True, exist_ok=True)





# ============================================================
# 2. DATA DOWNLOAD ENGINE
# ============================================================



def download_single_ticker(
        ticker
):


    filename = os.path.join(
        DATA_FOLDER,
        f"{ticker}.csv"
    )


    df=None


    # ---------------------------
    # Load cache
    # ---------------------------


    if os.path.exists(filename):

        try:

            local=pd.read_csv(
                filename,
                index_col=0,
                parse_dates=True
            )


            if len(local)>100:


                last_date=local.index[-1]


                diff=(
                    pd.Timestamp(TODAY)
                    -
                    last_date
                ).days


                if diff<=3:


                    print(
                        f"Cache OK {ticker}"
                    )


                    return local



        except Exception:


            pass



    # ---------------------------
    # Download
    # ---------------------------


    print(
        f"Downloading {ticker}..."
    )



    for attempt in range(3):


        try:


            df=yf.download(

                ticker,

                start=START_DATE,

                end=TODAY,

                progress=False,

                auto_adjust=False

            )


            if (
                df is not None
                and
                len(df)>100
            ):

                break



        except Exception as e:


            print(
                "Download error",
                e
            )

            time.sleep(2)



    if df is None or len(df)==0:


        raise Exception(
            f"{ticker} download failed"
        )




    # yfinance multiindex fix


    if isinstance(
        df.columns,
        pd.MultiIndex
    ):


        df.columns=(
            df.columns
            .get_level_values(0)
        )



    df.columns=[
        str(x)
        for x in df.columns
    ]



    df.to_csv(
        filename
    )



    return df






# ============================================================
# 3. DOWNLOAD ALL ETF DATA
# ============================================================



def load_market_data():


    market={}


    for ticker in ETF_LIST:


        market[ticker]=(
            download_single_ticker(
                ticker
            )
        )



    return market





# ============================================================
# 4. INDICATOR ENGINE
# ============================================================



def add_indicators(
        df
):


    df=df.copy()



    # Moving Average

    df["MA100"] = df["Close"].rolling(100).mean()

    df["MA200"]=(
        df["Close"]
        .rolling(200)
        .mean()
    )



    # Momentum


    df["Momentum12M"]=(
        
        df["Close"]
        /
        df["Close"]
        .shift(252)

        -1
    )



    # Volatility


    df["Volatility20"]=(
        df["Close"]
        .pct_change()
        .rolling(20)
        .std()
        * np.sqrt(252)
    )

    df["Return20"] = df["Close"].pct_change(20)

    df["Return63"] = (
    df["Close"]
    .pct_change(63)
)

    df["Return126"] = (
    df["Close"]
    .pct_change(126)
)

    df["Return252"] = (
    df["Close"]
    .pct_change(252)
)



    # ATR


    high_low=(

        df["High"]
        -
        df["Low"]

    )


    high_close=(

        abs(
            df["High"]
            -
            df["Close"]
            .shift(1)
        )

    )


    low_close=(

        abs(
            df["Low"]
            -
            df["Close"]
            .shift(1)
        )

    )


    tr=pd.concat(

        [
            high_low,
            high_close,
            low_close

        ],

        axis=1

    ).max(axis=1)



    df["ATR"]=(
        tr
        .rolling(20)
        .mean()
    )



    return df.dropna()





# ============================================================
# 5. INITIALIZE MARKET DATABASE
# ============================================================



print(
    "\nLoading ETF database..."
)



market=load_market_data()



for ticker in market:


    market[ticker]=add_indicators(
        market[ticker]
    )


    print(
        ticker,
        len(market[ticker]),
        "rows"
    )



print(
    "\nData layer ready."
)


# ============================================================
# END PART 1
# ============================================================

# ============================================================
# QQQ Trend Following System V2.0
#
# Part 2/4
# Signal Engine + Portfolio Construction
# ============================================================



# ============================================================
# 6. MARKET REGIME FILTER
# ============================================================


def spy_market_filter(
        date
):


    spy = market["SPY"]


    if date not in spy.index:

        return False



    row=spy.loc[date]



    return (

        row["Close"]
        >
        row["MA200"] * (1.0 * BUFFER_PCT)

    )





# ============================================================
# 7. QQQ TREND SIGNAL
# ============================================================


def qqq_trend_signal(
        date
):


    qqq=market["QQQ"]



    if date not in qqq.index:

        return False



    row=qqq.loc[date]



    qqq_trend=(

        row["Close"]
        >
        (row["MA200"] * (1.0 + BUFFER_PCT))

    )



    qqq_momentum=(

        row["Momentum12M"]
        >
        0

    )



    spy_filter=(
        spy_market_filter(date)
    )



    return (

        qqq_trend

        and

        qqq_momentum

        and

        spy_filter

    )





# ============================================================
# 8. MULTI ETF MOMENTUM ROTATION
# ============================================================



ROTATION_ETFS=[

    "QQQ",
    "SPY",
    "IWM",
    "TLT",
    "GLD"

]




def select_best_etf(date):

    candidates = [
        "QQQ",
        "SPY",
        "IWM",
        "TLT",
        "GLD"
    ]

    scores = {}

    for ticker in candidates:

        if ticker not in market:
            continue

        df = market[ticker]

        if date not in df.index:
            continue

        row = df.loc[date]

        close = row.get(
            "Close",
            np.nan
        )

        ma200 = row.get(
            "MA200",
            np.nan
        )

        ret63 = row.get(
            "Return63",
            np.nan
        )

        ret126 = row.get(
            "Return126",
            np.nan
        )

        ret252 = row.get(
            "Return252",
            np.nan
        )

        if pd.isna(close) or pd.isna(ma200):
            continue

        # ======================================
        # Momentum Score
        # ======================================

        momentum_score = 0.0

        if not pd.isna(ret63):
            momentum_score += (
                0.20 *
                ret63
            )

        if not pd.isna(ret126):
            momentum_score += (
                0.30 *
                ret126
            )

        if not pd.isna(ret252):
            momentum_score += (
                0.50 *
                ret252
            )

        # ======================================
        # Trend
        # ======================================

        trend_bonus = 0.0

        if close > ma200:
            trend_bonus = 0.20

        else:
            trend_bonus = -0.20

        # ======================================
        # Final score
        # ======================================

        scores[ticker] = (
            momentum_score
            +
            trend_bonus
        )

    # ==========================================
    # 没有符合条件
    # ==========================================

    if not scores:
        return "BIL"

    # ==========================================
    # 最强 ETF
    # ==========================================

    selected = max(
        scores,
        key=scores.get
    )

    # ==========================================
    # 如果所有 ETF 都是负动量
    # → BIL
    # ==========================================

    if scores[selected] <= 0:

        return "BIL"

    return selected





# ============================================================
# 9. VOLATILITY TARGETING
# ============================================================



def calculate_position_size(ticker, date):
    """
    趋势 + 波动率 + SPY/QQQ市场过滤
    返回目标仓位 0~1
    """

    if ticker not in market:
        return 0.0

    df = market[ticker]

    if date not in df.index:
        return 0.0

    row = df.loc[date]

    # ==============================
    # 1. 基础数据
    # ==============================

    close = row.get("Close", np.nan)
    ma200 = row.get("MA200", np.nan)
    ma100 = row.get("MA100", np.nan)
    vol = row.get("Volatility20", np.nan)

    if (
        pd.isna(close)
        or pd.isna(ma200)
        or pd.isna(vol)
        or vol <= 0
    ):
        return 0.0

    # ==============================
    # 2. 波动率目标仓位
    # ==============================

    vol_weight = TARGET_VOL / vol

    vol_weight = np.clip(
        vol_weight,
        0.0,
        1.0
    )

    # ==============================
    # 3. 个股/ETF趋势评分
    # ==============================

    trend_score = 0.0

    # Close > MA200
    if close > ma200:
        trend_score += 0.50

    # Close > MA100
    if not pd.isna(ma100) and close > ma100:
        trend_score += 0.25

    # 20日趋势
    ret20 = row.get("Return20", np.nan)

    if not pd.isna(ret20) and ret20 > 0:
        trend_score += 0.25

    # ==============================
    # 4. SPY + QQQ 双重市场过滤
    # ==============================

    market_score = 1.0

    try:

        spy = market["SPY"]

        qqq = market["QQQ"]

        if date in spy.index and date in qqq.index:

            spy_row = spy.loc[date]

            qqq_row = qqq.loc[date]

            spy_close = spy_row.get(
                "Close",
                np.nan
            )

            spy_ma200 = spy_row.get(
                "MA200",
                np.nan
            )

            qqq_close = qqq_row.get(
                "Close",
                np.nan
            )

            qqq_ma200 = qqq_row.get(
                "MA200",
                np.nan
            )

            spy_bull = (
                not pd.isna(spy_close)
                and
                not pd.isna(spy_ma200)
                and
                spy_close > spy_ma200
            )

            qqq_bull = (
                not pd.isna(qqq_close)
                and
                not pd.isna(qqq_ma200)
                and
                qqq_close > qqq_ma200
            )

            # 双牛
            if spy_bull and qqq_bull:

                market_score = 1.0

            # 一个牛，一个熊
            elif spy_bull or qqq_bull:

                market_score = 0.65

            # 双熊
            else:

                market_score = 0.25

    except Exception:

        market_score = 1.0

    # ==============================
    # 5. 趋势评分转成仓位系数
    # ==============================

    if trend_score >= 0.75:

        trend_multiplier = 1.00

    elif trend_score >= 0.50:

        trend_multiplier = 0.75

    elif trend_score >= 0.25:

        trend_multiplier = 0.40

    else:

        trend_multiplier = 0.0

    # ==============================
    # 6. 最终仓位
    # ==============================

    weight = (
        vol_weight
        *
        trend_multiplier
        *
        market_score
    )

    return float(
        np.clip(
            weight,
            0.0,
            1.0
        )
    )


# ============================================================
# 10. FINAL DAILY ALLOCATION ENGINE
# ============================================================



def generate_allocation(
        date
):


    allocation={

        "QQQ":0,
        "SPY":0,
        "IWM":0,
        "TLT":0,
        "GLD":0,
        "BIL":0

    }



    # --------------------------
    # Risk OFF
    # --------------------------


    if not qqq_trend_signal(date):


        allocation["BIL"]=1


        return allocation





    # --------------------------
    # Risk ON
    # --------------------------


    selected=select_best_etf(
        date
    )



    weight=calculate_position_size(

        selected,

        date

    )



    allocation[selected]=weight



    # remaining cash

    allocation["BIL"]=(
        1-weight
    )



    return allocation





# ============================================================
# 11. BUILD DAILY PORTFOLIO TABLE
# ============================================================



def build_allocation_history():


    dates=market["QQQ"].index



    records=[]



    for date in dates:


        alloc=generate_allocation(
            date
        )


        alloc["Date"]=date


        records.append(
            alloc
        )



    result=pd.DataFrame(
        records
    )


    result=result.set_index(
        "Date"
    )



    return result





allocation_history = None
portfolio_returns = None

if RUN_BACKTEST or RUN_MODE == "report":
    print("\nBuilding portfolio allocation...")
    allocation_history = build_allocation_history()
    print(allocation_history.tail())



# ============================================================
# 12. PORTFOLIO RETURN ENGINE
# ============================================================



def calculate_portfolio_returns(
        allocation
):


    returns=pd.DataFrame(
        index=allocation.index
    )



    for ticker in ETF_LIST:


        returns[ticker]=(
            market[ticker]
            ["Close"]
            .pct_change()

        )



    portfolio=(

        allocation.shift(1)

        *
        returns

    ).sum(axis=1)



    return portfolio.fillna(0)





if RUN_BACKTEST or RUN_MODE == "report":
    portfolio_returns = calculate_portfolio_returns(allocation_history)
    print("\nPortfolio engine ready.")



# ============================================================
# END PART 2
# ============================================================

# ============================================================
# PERFORMANCE / WALK-FORWARD / MONTE CARLO FUNCTIONS
# ============================================================

def calculate_sharpe(
        returns
):


    if returns.std()==0:

        return 0



    return (

        returns.mean()
        /
        returns.std()

        *
        np.sqrt(252)

    )





def calculate_max_drawdown(
        returns
):


    equity=(

        1+returns

    ).cumprod()



    high_water=(
        equity.cummax()
    )


    drawdown=(

        equity
        /
        high_water

        -1

    )


    return drawdown.min()





def calculate_cagr(
        returns
):


    equity=(

        1+returns

    ).cumprod()



    years=(

        len(equity)
        /
        252

    )


    return (

        equity.iloc[-1]
        **
        (1/years)

        -1

    )





def optimization_score(
        returns
):


    sharpe=calculate_sharpe(
        returns
    )


    dd=calculate_max_drawdown(
        returns
    )



    # Sharpe - drawdown penalty


    score=(

        sharpe

        -

        abs(dd)
        *
        0.5

    )


    return score





def walk_forward_backtest(returns):

    print(
        "\nStarting Walk Forward..."
    )

    oos_returns = pd.Series(
        0.0,
        index=returns.index,
        dtype=float
    )

    records = []

    start = TRAIN_WINDOW

    # ==========================================
    # 参数网格
    # ==========================================

    target_vol_grid = [
        0.10,
        0.12,
        0.15,
        0.18,
        0.20
    ]

    cash_buffer_grid = [
        0.00,
        0.05,
        0.10,
        0.15
    ]

    # ==========================================
    # Walk Forward
    # ==========================================

    while start < len(returns):

        train = returns.iloc[
            start - TRAIN_WINDOW:
            start
        ]

        test = returns.iloc[
            start:
            min(
                start + TEST_WINDOW,
                len(returns)
            )
        ]

        if len(test) == 0:
            break

        best_score = -np.inf

        best_parameter = None

        # ======================================
        # Parameter optimization
        # ======================================

        for target_vol in target_vol_grid:

            for cash_buffer in cash_buffer_grid:

                # --------------------------------
                # 训练期波动率
                # --------------------------------

                train_vol = (
                    train
                    .rolling(20)
                    .std()
                    *
                    np.sqrt(252)
                )

                # --------------------------------
                # Volatility targeting
                # --------------------------------

                vol_weight = (
                    target_vol /
                    train_vol
                )

                vol_weight = (
                    vol_weight
                    .clip(
                        lower=0.0,
                        upper=1.0
                    )
                    .fillna(0.0)
                )

                # --------------------------------
                # Cash allocation
                # --------------------------------

                strategy_weight = (
                    vol_weight
                    *
                    (1.0 - cash_buffer)
                )

                strategy_ret = (
                    train
                    *
                    strategy_weight
                )

                # --------------------------------
                # T-Bill return
                # --------------------------------

                try:

                    bil_return = (
                        market["BIL"]
                        ["Close"]
                        .pct_change()
                        .reindex(train.index)
                        .fillna(0.0)
                    )

                except Exception:

                    bil_return = pd.Series(
                        0.0,
                        index=train.index
                    )

                cash_return = (
                    bil_return
                    *
                    cash_buffer
                )

                adjusted = (
                    strategy_ret
                    +
                    cash_return
                )

                # --------------------------------
                # Sharpe / DD optimization
                # --------------------------------

                score = optimization_score(
                    adjusted
                )

                # --------------------------------
                # 防止异常参数
                # --------------------------------

                if pd.isna(score):
                    continue

                if score > best_score:

                    best_score = score

                    best_parameter = (
                        target_vol,
                        cash_buffer
                    )

        # ======================================
        # 如果优化失败
        # ======================================

        if best_parameter is None:

            best_parameter = (
                0.15,
                0.10
            )

            best_score = -np.inf

        # ======================================
        # OOS parameters
        # ======================================

        target_vol = best_parameter[0]

        cash_ratio = best_parameter[1]

        # ======================================
        # OOS volatility targeting
        # ======================================

        test_vol = (
            test
            .rolling(20)
            .std()
            *
            np.sqrt(252)
        )

        vol_weight = (
            target_vol /
            test_vol
        )

        vol_weight = (
            vol_weight
            .clip(
                lower=0.0,
                upper=1.0
            )
            .fillna(0.0)
        )

        # ======================================
        # Strategy return
        # ======================================

        strategy_weight = (
            vol_weight
            *
            (1.0 - cash_ratio)
        )

        oos = (
            test
            *
            strategy_weight
        )

        # ======================================
        # T-Bill
        # ======================================

        try:

            bil_return = (
                market["BIL"]
                ["Close"]
                .pct_change()
                .reindex(test.index)
                .fillna(0.0)
            )

        except Exception:

            bil_return = pd.Series(
                0.0,
                index=test.index
            )

        oos += (
            cash_ratio
            *
            bil_return
        )

        # ======================================
        # 防止 pandas dtype 问题
        # ======================================

        oos = pd.Series(
            np.asarray(oos, dtype=float),
            index=test.index
        )

        oos_returns.loc[
            test.index
        ] = oos

        # ======================================
        # Record
        # ======================================

        records.append(
            {
                "date":
                    test.index[0],

                "target_vol":
                    target_vol,

                "cash_ratio":
                    cash_ratio,

                "train_score":
                    best_score,

                "test_return":
                    float(
                        (1.0 + oos).prod()
                        - 1.0
                    )
            }
        )

        print(
            f"{test.index[0].date()} | "
            f"Vol={target_vol:.2%} | "
            f"Cash={cash_ratio:.2%} | "
            f"Score={best_score:.3f}"
        )

        start += TEST_WINDOW

    return (
        oos_returns,
        pd.DataFrame(records)
    )



def monte_carlo_test(

        returns,

        simulations=5000

):


    results=[]



    returns=returns.dropna()



    for i in range(simulations):


        sample=np.random.choice(

            returns,

            size=len(returns),

            replace=True

        )



        equity=(

            1+
            pd.Series(sample)

        ).cumprod()



        results.append(

            equity.iloc[-1]

        )



    return pd.Series(
        results
    )





# ============================================================
# REPORT MODE
# ============================================================

def run_backtest_report():
    logger.info("Starting Walk Forward...")
    wf_returns, wf_records = walk_forward_backtest(portfolio_returns)
    qqq_returns = (market["QQQ"]["Close"].pct_change().reindex(wf_returns.index).fillna(0.0))
    performance = pd.DataFrame({
        "Strategy": [calculate_cagr(wf_returns), calculate_max_drawdown(wf_returns), calculate_sharpe(wf_returns), (wf_returns == 0).mean()],
        "QQQ Buy Hold": [calculate_cagr(qqq_returns), calculate_max_drawdown(qqq_returns), calculate_sharpe(qqq_returns), 0.0],
    }, index=["CAGR", "Max Drawdown", "Sharpe", "Cash Ratio"])
    print("\n==============================")
    print("PERFORMANCE REPORT")
    print("==============================")
    print(performance)
    logger.info("Running Monte Carlo...")
    mc_results = monte_carlo_test(wf_returns, 5000)
    print("Monte Carlo Result")
    print("5% Worst:", mc_results.quantile(0.05))
    print("Median:", mc_results.quantile(0.50))
    print("95% Best:", mc_results.quantile(0.95))
    try:
        import matplotlib.pyplot as plt
        strategy_equity = (1 + wf_returns).cumprod()
        qqq_equity = (1 + qqq_returns).cumprod()
        plt.figure(figsize=(12, 6))
        plt.plot(strategy_equity, label="QQQ Trend V2.1")
        plt.plot(qqq_equity, label="QQQ Buy Hold")
        plt.title("QQQ Trend Following vs QQQ")
        plt.ylabel("Growth of $1")
        plt.grid()
        plt.legend()
        plt.tight_layout()
        chart = BASE_DIR / "logs" / "equity_curve.png"
        plt.savefig(chart, dpi=150)
        plt.close()
        logger.info("Equity curve saved to %s", chart)
    except Exception as exc:
        logger.warning("Chart generation skipped: %s", exc)


try:
    from alpaca.trading.client import TradingClient
    from alpaca.trading.requests import MarketOrderRequest
    from alpaca.trading.enums import OrderSide, TimeInForce
except ImportError:
    TradingClient = None
    MarketOrderRequest = None
    OrderSide = None
    TimeInForce = None

ALPACA_API_KEY = os.getenv("ALPACA_API_KEY")
ALPACA_SECRET_KEY = os.getenv("ALPACA_SECRET_KEY")

# Paper is the default. Live requires BOTH RUN_MODE=live and ALLOW_LIVE_TRADING=1.
ALPACA_PAPER = RUN_MODE != "live"


def connect_alpaca():
    if not ALPACA_API_KEY or not ALPACA_SECRET_KEY:
        logger.warning("Alpaca credentials not found; execution disabled.")
        return None

    if TradingClient is None:
        logger.error("alpaca-py is not installed. Install requirements.txt.")
        return None

    try:
        client = TradingClient(
            ALPACA_API_KEY,
            ALPACA_SECRET_KEY,
            paper=ALPACA_PAPER,
        )
        account = client.get_account()
        logger.info(
            "Alpaca connected | paper=%s | equity=%s",
            ALPACA_PAPER,
            account.equity,
        )
        return client
    except Exception as exc:
        logger.exception("Alpaca connection failed: %s", exc)
        return None


#api = connect_alpaca()
#1. 引入专门的行情数据客户端
try:
    from alpaca.data.historical import StockHistoricalDataClient
    from alpaca.data.requests import StockLatestTradeRequest
except ImportError:
    StockHistoricalDataClient = None
#2. 实例化行情客户端
    data_client = None
    if ALPACA_API_KEY and ALPACA_SECRET_KEY and StockHistoricalDataClient:
        data_client = StockHistoricalDataClient(ALPACA_API_KEY,ALPACA_SECRET_KEY)
#3. 保持原有的交易客户端连接不变
    api = connect_alpaca()


# ============================================================
# 23. PORTFOLIO REBALANCE ENGINE
# ============================================================



def get_current_positions(api):
    holdings = {}
    if api is None:
        return holdings
    try:
        positions = api.get_all_positions()
        for p in positions:
            holdings[p.symbol] = float(p.qty)
    except Exception as exc:
        logger.exception("Could not read positions: %s", exc)
    return holdings


def submit_market_order(api, symbol, qty, side):
    if api is None or qty <= 0:
        return None

    try:
        order_side = OrderSide.BUY if side.lower() == "buy" else OrderSide.SELL
        request = MarketOrderRequest(
            symbol=symbol,
            qty=qty,
            side=order_side,
            time_in_force=TimeInForce.DAY,
        )
        order = api.submit_order(request)
        logger.info("ORDER | %s | %s | qty=%s", side.upper(), symbol, qty)
        return order
    except Exception as exc:
        logger.exception("Order failed | %s %s: %s", side, symbol, exc)
        return None


def live_rebalance(api, target_symbol, target_weight):
    if api is None:
        logger.warning("Execution skipped: Alpaca unavailable.")
        return

    if RUN_MODE == "live" and not ALLOW_LIVE_TRADING:
        logger.error("LIVE mode requested but ALLOW_LIVE_TRADING != 1. No orders sent.")
        return

    if RUN_MODE not in ("paper", "live"):
        logger.info("RUN_MODE=%s; execution skipped.", RUN_MODE)
        return

    today = datetime.now(TIMEZONE).date()
    marker = BASE_DIR / "logs" / "last_execution_date.txt"
    if marker.exists() and marker.read_text().strip() == str(today):
        logger.warning("Execution already completed for %s; skipping duplicate run.", today)
        return

    account = api.get_account()
    equity = float(account.equity)
    holdings = get_current_positions(api)

    target_value = equity * (target_weight if target_symbol != "BIL" else 0.0)

    prices = {}
    for t in ETF_LIST:
        try:
            if data_client is not None:
            #使用最新标准的新价请求方法
                req = StockLatestTradeRequest(symbol_or_symbols=t)
                res = data_client.get_stock_latest_trade(req)
                prices[t] = float(res[t].price)
            else:
                 # 如果行情客户端不可用，降级使用本地历史数据的最后一个收盘价作为参考估算值
                prices[t] = float(market[t]["Close"].iloc[-1])
        except Exception as exc:
            logger.warning("No Alpaca price for %s, using fallback: %s", t, exc)
            # 降级备用兜底逻辑
            prices[t] = float(market[t]["Close"].iloc[-1])

    # Sell every non-target ETF. This intentionally leaves proceeds as cash
    # when target_symbol == BIL, matching the existing strategy's cash behavior.
    for symbol, qty in holdings.items():
        should_sell = (
            qty > 0
            and symbol in ETF_LIST
            and (symbol != target_symbol or target_symbol == "BIL")
        )
        if should_sell:
            submit_market_order(api, symbol, int(qty), "sell")

    if target_symbol in prices and target_symbol != "BIL":
        current_qty = holdings.get(target_symbol, 0.0)
        current_value = current_qty * prices[target_symbol]
        difference = target_value - current_value

        # Only buy; any excess target position is handled by a sell below.
        if difference > 100:
            buy_qty = int(difference / prices[target_symbol])
            if buy_qty > 0:
                submit_market_order(api, target_symbol, buy_qty, "buy")
        elif difference < -100:
            sell_qty = int(abs(difference) / prices[target_symbol])
            if sell_qty > 0:
                submit_market_order(api, target_symbol, sell_qty, "sell")

    marker.write_text(str(today))
    logger.info(
        "Rebalance complete | target=%s | target_weight=%.2f%% | equity=%.2f",
        target_symbol, target_weight * 100, equity
    )


# ============================================================

# ============================================================
# SERVER RUNTIME
# ============================================================

def get_latest_completed_date():
    idx = market["QQQ"].index
    if len(idx) == 0:
        raise RuntimeError("No QQQ market data available.")
    return idx[-1]

def run_daily():
    now = datetime.now(TIMEZONE)
    if now.weekday() >= 5:
        logger.info("Weekend detected; no trading execution.")
        return

    latest_date = get_latest_completed_date()
    qqq_signal = qqq_trend_signal(latest_date)
    selected = select_best_etf(latest_date)
    if selected == "BIL" or not qqq_signal:
        target = 0.0
        target_symbol = "BIL"
    else:
        target_symbol = selected
        target = calculate_position_size(selected, latest_date)
    logger.info("CURRENT DECISION | date=%s | QQQ=%s | ETF=%s | target=%.2f%% | cash=%.2f%%", latest_date.date(), "ON" if qqq_signal else "OFF", target_symbol, target * 100, (1 - target) * 100)
    if RUN_MODE in ("paper", "live"):
        live_rebalance(api, target_symbol, target)
    else:
        logger.info("No broker orders in RUN_MODE=%s", RUN_MODE)

def main():
    logger.info("QQQ Trend V2.1 server start | mode=%s | backtest=%s | base=%s", RUN_MODE, RUN_BACKTEST, BASE_DIR)
    if RUN_BACKTEST or RUN_MODE == "report":
        run_backtest_report()
    run_daily()
    logger.info("QQQ Trend V2.1 server finished")

if __name__ == "__main__":
    main()
