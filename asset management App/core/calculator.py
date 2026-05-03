import math

from loguru import logger

from .models import Transaction, TransactionType


class PortfolioCalculator:
    @staticmethod
    def calculate_risk_metrics(
        daily_values: list[float], risk_free_rate: float = 0.0
    ) -> tuple[float | None, float | None, float | None, list[float] | None]:
        """
        日次のポートフォリオ価値のリストからリスク指標を計算する。
        returns: (volatility, sharpe, max_drawdown, returns_list)
        """
        try:
            if not daily_values or len(daily_values) < 2:
                return None, None, None, None

            # 1. 日次収益率の計算
            returns = []
            for i in range(1, len(daily_values)):
                prev = daily_values[i - 1]
                if prev > 0:
                    ret = (daily_values[i] - prev) / prev
                    returns.append(ret)

            if not returns:
                return None, None, None, None

            # 2. ボラティリティ (年率換算: 252日)
            mean_ret = sum(returns) / len(returns)
            variance = sum((r - mean_ret) ** 2 for r in returns) / len(returns)
            stdev = math.sqrt(variance)
            ann_vol = stdev * math.sqrt(252) * 100

            # 3. シャープレシオ
            rf_decimal = risk_free_rate / 100
            ann_return = mean_ret * 252
            ann_stdev = stdev * math.sqrt(252)
            sharpe = (ann_return - rf_decimal) / ann_stdev if ann_stdev > 0 else 0

            # 4. 最大ドローダウン
            max_dd = 0.0
            peak = daily_values[0]
            for v in daily_values:
                if v > peak:
                    peak = v
                dd = (v - peak) / peak if peak > 0 else 0
                if dd < max_dd:
                    max_dd = dd

            max_dd_pct = max_dd * 100

            return ann_vol, sharpe, max_dd_pct, returns

        except Exception as e:
            logger.exception(f"Unexpected error during risk metrics calculation: {e}")
            return None, None, None, None

    @staticmethod
    def calculate_advanced_metrics(
        portfolio_returns: list[float],
        benchmark_returns: list[float],
        risk_free_rate: float = 0.0,
    ) -> tuple[float | None, float | None, float | None]:
        """
        Sortino Ratio, Beta, Correlationを計算する。
        """
        try:
            if (
                not portfolio_returns
                or not benchmark_returns
                or len(portfolio_returns) != len(benchmark_returns)
            ):
                return None, None, None

            # 1. Sortino Ratio (下方偏差のみを使用)
            negative_returns = [r for r in portfolio_returns if r < 0]
            if len(negative_returns) > 0:
                downside_dev = math.sqrt(
                    sum(r**2 for r in negative_returns) / len(portfolio_returns)
                )
                ann_downside_dev = downside_dev * math.sqrt(252)
                rf_decimal = risk_free_rate / 100
                ann_return = (sum(portfolio_returns) / len(portfolio_returns)) * 252
                sortino = (
                    (ann_return - rf_decimal) / ann_downside_dev if ann_downside_dev > 0 else 0
                )
            else:
                # 下落が一度もない場合は非常に優秀な数値とするか、シャープレシオと同様にする
                sortino = 9.99

            # 2. Beta (Covariance / Benchmark Variance)
            p_mean = sum(portfolio_returns) / len(portfolio_returns)
            b_mean = sum(benchmark_returns) / len(benchmark_returns)

            covariance = (
                sum(
                    (p - p_mean) * (b - b_mean)
                    for p, b in zip(portfolio_returns, benchmark_returns, strict=False)
                )
                / len(portfolio_returns)
            )
            b_variance = sum((b - b_mean) ** 2 for b in benchmark_returns) / len(benchmark_returns)

            beta = covariance / b_variance if b_variance > 0 else 1.0

            # 3. Correlation (R)
            p_variance = sum((p - p_mean) ** 2 for p in portfolio_returns) / len(portfolio_returns)
            correlation = (
                covariance / math.sqrt(p_variance * b_variance)
                if (p_variance > 0 and b_variance > 0)
                else 0.0
            )

            return sortino, beta, correlation

        except Exception as e:
            logger.exception(f"Unexpected error calculating advanced metrics: {e}")
            return None, None, None


class BenchmarkCalculator:
    @staticmethod
    def create_shadow_performance(
        transactions: list[Transaction],
        benchmark_price_map: dict[str, float],
        current_benchmark_price: float,
        ticker_filter: str | None = None,
        forex_rates: dict[str, float] | None = None,
    ) -> tuple[float, float, float]:
        """
        与えられたトランザクションと同じタイミング・同じ金額(USDベース)で
        ベンチマークを購入したと仮定した場合のパフォーマンスを計算する。
        returns: (total_bench_cost_usd, total_bench_market_value_usd, total_bench_units)
        """
        from datetime import timedelta

        total_units = 0.0
        total_cost_usd = 0.0

        # フィルタリング(特定銘柄のみの比較用)
        filtered_txs = [
            tx
            for tx in transactions
            if tx.transaction_type == TransactionType.BUY
            and (ticker_filter is None or tx.ticker == ticker_filter)
        ]

        for tx in filtered_txs:
            tx_date = tx.timestamp.strftime("%Y-%m-%d")
            bench_price = benchmark_price_map.get(tx_date)

            if not bench_price:
                # 週末や祝日の場合は直近5日まで遡る
                for i in range(1, 6):
                    prev_date = (tx.timestamp - timedelta(days=i)).strftime("%Y-%m-%d")
                    bench_price = benchmark_price_map.get(prev_date)
                    if bench_price:
                        break

            if bench_price and bench_price > 0:
                # 当時の投資額(USDベースに変換)
                rate = forex_rates.get(tx.currency, 1.0) if forex_rates else 1.0
                inv_usd = tx.quantity * tx.price * rate
                total_units += inv_usd / bench_price
                total_cost_usd += inv_usd

        market_value_usd = total_units * current_benchmark_price
        msg = (
            f"Shadow performance for {ticker_filter or 'portfolio'}: "
            f"Cost={total_cost_usd:.2f}, Value={market_value_usd:.2f}, Units={total_units:.4f}"
        )
        logger.info(msg)
        return total_cost_usd, market_value_usd, total_units

    @staticmethod
    def calculate_alpha_metrics(
        portfolio_market_value_usd: float,
        portfolio_cost_usd: float,
        benchmark_market_value_usd: float,
        benchmark_cost_usd: float,
    ) -> dict[str, float]:
        """
        ポートフォリオとベンチマークの比較指標を計算する。
        Geometric Alpha(幾何学的な乖離)を主眼に置く。
        """
        # Arithmetic Returns (単純利益率)
        p_return = (
            (portfolio_market_value_usd - portfolio_cost_usd) / portfolio_cost_usd
            if portfolio_cost_usd > 0
            else 0
        )
        b_return = (
            (benchmark_market_value_usd - benchmark_cost_usd) / benchmark_cost_usd
            if benchmark_cost_usd > 0
            else 0
        )

        # Alpha Percent: (1 + Portfolio Return) / (1 + Benchmark Return) - 1
        # これは「ベンチマークを100とした時に、自分がどれだけ価値を上乗せしたか」を示す
        if benchmark_market_value_usd > 0:
            alpha_percent = portfolio_market_value_usd / benchmark_market_value_usd - 1
        else:
            alpha_percent = p_return - b_return

        alpha_value_usd = portfolio_market_value_usd - benchmark_market_value_usd

        return {
            "alpha_percent": alpha_percent * 100,
            "alpha_value_usd": alpha_value_usd,
            "portfolio_return": p_return * 100,
            "benchmark_return": b_return * 100,
            "shadow_market_value_usd": benchmark_market_value_usd,
            "shadow_cost_usd": benchmark_cost_usd,
        }
