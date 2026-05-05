import sys
import time

from src.db.master_db import JobQueue


def main():
    queue = JobQueue()
    print("\n[Monitor] Waiting for all jobs to complete...")
    print("--------------------------------------------------")

    while True:
        stats = queue.get_stats()
        pending = stats.get("PENDING", 0)
        processing = stats.get("PROCESSING", 0)
        fetching = stats.get("FETCHING", 0)
        llm_waiting = stats.get("LLM_WAITING", 0)
        saving = stats.get("SAVING", 0)
        parsed = stats.get("PARSED", 0)
        completed = stats.get("COMPLETED", 0)
        failed = stats.get("FAILED", 0)

        active = pending + processing + fetching + llm_waiting + saving + parsed

        # 1行で進捗を表示
        sys.stdout.write(
            f"\rActive: {active:4} | P:{pending:3} W:{llm_waiting:3} S:{saving:3} R:{parsed:3} | Done: {completed:5} | Fail: {failed:3} "
        )
        sys.stdout.flush()

        if active == 0:
            print("\n\n[Success] All jobs processed!")
            # ゾンビクリーンアップを最後に1回実行
            queue.cleanup_zombie_jobs()
            return 0

        time.sleep(10)


if __name__ == "__main__":
    sys.exit(main())
