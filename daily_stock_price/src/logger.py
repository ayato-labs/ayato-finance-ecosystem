from loguru import logger
from datetime import datetime
from pathlib import Path

import pandas as pd




class SyncLogger:
    def __init__(self, log_dir: str = "./data/logs"):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.history_file = self.log_dir / "sync_history.parquet"

    def log_event(
        self,
        ticker: str,
        start_date: datetime,
        end_date: datetime,
        count: int,
        status: str,
        fetcher: str,
        message: str = "",
    ):
        """
        Records a sync event into the persistent history log.
        """
        new_event = pd.DataFrame(
            [
                {
                    "Timestamp": datetime.now(),
                    "Ticker": ticker,
                    "PeriodStart": pd.to_datetime(start_date),
                    "PeriodEnd": pd.to_datetime(end_date),
                    "RecordsFetched": int(count),
                    "Status": status,
                    "Message": str(message),
                    "Fetcher": fetcher,
                }
            ]
        )

        try:
            if self.history_file.exists():
                # Append to existing log
                # For high-volume development, reading/writing a single file is fine.
                # If it grows too large, we can partition by month.
                existing_df = pd.read_parquet(self.history_file)
                combined_df = pd.concat([existing_df, new_event], ignore_index=True)
                combined_df.to_parquet(self.history_file, compression="zstd")
            else:
                new_event.to_parquet(self.history_file, compression="zstd")

            logger.debug(f"Logged sync event for {ticker}: {status}")
        except Exception as e:
            logger.error(f"Failed to log sync event to {self.history_file}: {e}")

    def log_events(self, events: list[dict]):
        """
        Bulk log events for efficiency.
        """
        if not events:
            return

        new_df = pd.DataFrame(events)
        new_df["Timestamp"] = datetime.now()

        try:
            if self.history_file.exists():
                existing_df = pd.read_parquet(self.history_file)
                combined_df = pd.concat([existing_df, new_df], ignore_index=True)
                combined_df.to_parquet(self.history_file, compression="zstd")
            else:
                new_df.to_parquet(self.history_file, compression="zstd")
        except Exception as e:
            logger.error(f"Failed to bulk log sync events: {e}")
