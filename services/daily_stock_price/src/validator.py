import pandas as pd
from loguru import logger


class DataValidator:
    """
    株価データの整合性を検証するバリデーター。
    1. 論理的チェック: OHLCの関係性、正の値、出来高の負値チェック。
    2. 統計的チェック: 急激な価格変化の検知。
    """

    def __init__(self, spike_threshold: float = 0.5):
        """
        Args:
            spike_threshold: 前日比での変化率の閾値（デフォルト50%）。
        """
        self.spike_threshold = spike_threshold

    def validate(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        DataFrameに対してバリデーションを実行し、クリーンなデータを返す。
        """
        if df.empty:
            return df

        # 論理チェック (不正な行を除外)
        valid_df = self.check_logical(df)

        # 統計チェック (警告のみ、データは保持)
        self.check_statistical(valid_df)

        return valid_df

    def check_logical(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        不合理なOHLC関係を持つ行を除外する。
        """
        # 1. High/Low 関係性
        mask = df["High"] >= df["Low"]

        # 2. Open/Close が High/Low の範囲内か
        mask &= df["High"] >= df["Open"]
        mask &= df["High"] >= df["Close"]
        mask &= df["Low"] <= df["Open"]
        mask &= df["Low"] <= df["Close"]

        # 3. 価格が正の値か
        mask &= df["Open"] > 0
        mask &= df["High"] > 0
        mask &= df["Low"] > 0
        mask &= df["Close"] > 0

        # 4. 出来高が負でないか
        mask &= df["Volume"] >= 0

        invalid_rows = df[~mask]
        if not invalid_rows.empty:
            tickers = invalid_rows["Ticker"].unique()
            logger.error(
                f"Logic violation detected in {len(invalid_rows)} rows for tickers: {tickers.tolist()}"
            )
            # 詳細ログ (最初の3行)
            logger.debug(f"Invalid sample rows:\n{invalid_rows.head(3)}")

        return df[mask].copy()

    def check_statistical(self, df: pd.DataFrame):
        """
        急激な価格変動を検知して警告を出す。
        """
        if len(df) < 2:
            return

        # 銘柄ごとにソートして計算
        df_sorted = df.sort_values(["Ticker", "Date"])

        for ticker, group in df_sorted.groupby("Ticker"):
            if len(group) < 2:
                continue

            # 変化率の計算 (Closeベース)
            # Note: Tickerごとに独立して計算するためにgroup内でpct_changeを実行
            pct_change = group["Close"].pct_change().abs()
            spikes = group[pct_change > self.spike_threshold]

            for idx, row in spikes.iterrows():
                # 以前の行のインデックスを取得
                loc = group.index.get_loc(idx)
                prev_row = group.iloc[loc - 1]
                prev_price = prev_row["Close"]
                change = (row["Close"] - prev_price) / prev_price

                # 分割情報があるかチェック (0は分割なし、1.0も実質なし)
                split = row.get("StockSplits", 0)
                if pd.isna(split) or split == 0 or split == 1.0:
                    logger.warning(
                        f"Price spike detected for {ticker} on {row['Date'].date()}: "
                        f"{change:+.2%} (Prev: {prev_price:.2f}, Curr: {row['Close']:.2f}) "
                        f"WITHOUT split info."
                    )
                else:
                    logger.info(
                        f"Price change for {ticker} on {row['Date'].date()}: "
                        f"{change:+.2%} WITH split info ({split})."
                    )
