import sys
import time
from pathlib import Path

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent))

from dotenv import load_dotenv

from src.mappers.ai_mapper import AIMapper

load_dotenv()

MODEL_NAME = "gemma-4-26b-a4b-it"


def run_benchmark_v2():
    mapper = AIMapper()

    # Sample tags
    tags = [
        (
            "us-gaap:NetIncomeLoss",
            "Net income including portion attributable to noncontrolling interest.",
        ),
        ("us-gaap:Revenues", "Amount of revenue from goods and services."),
        (
            "us-gaap:OperatingIncomeLoss",
            "The net result for the period of operating profit and loss.",
        ),
        (
            "us-gaap:Assets",
            "Sum of the carrying amounts as of the balance sheet date of all assets.",
        ),
        (
            "us-gaap:Liabilities",
            "Sum of the carrying amounts as of the balance sheet date of all liabilities.",
        ),
        ("jppfs_cor:NetSales", "Net sales of the company."),
        ("jppfs_cor:OperatingIncome", "Operating income from main business."),
        ("jppfs_cor:OrdinaryIncome", "Ordinary income including non-operating items."),
        ("jppfs_cor:NetAssets", "Total net assets."),
        ("jppfs_cor:TotalAssets", "Total assets."),
    ] * 10  # 100 tags total

    # We will test "Single Call Batching" for various sizes
    batch_sizes = [1, 5, 10, 15, 20, 30]

    results_log = []

    print(f"=== TRUE BATCHING BENCHMARK START (Model: {MODEL_NAME}) ===")

    for size in batch_sizes:
        print(f"\n[STEP] Batch Size: {size} - Requesting...")
        sample = tags[:size]

        start_time = time.time()
        # Call the new batch method directly
        res = mapper.map_tags_batch("Global", sample, MODEL_NAME, f"bench-v2-batch-{size}")
        duration = time.time() - start_time

        success_count = len(res)
        throughput = duration / size if size > 0 else 0

        status = "SUCCESS" if success_count == size else "PARTIAL/FAILED"
        print(
            f"       >>> {status}: {duration:.2f}s (Throughput: {throughput:.3f}s/tag) | Items: {success_count}/{size}"
        )

        results_log.append(
            {
                "batch_size": size,
                "duration": duration,
                "throughput": throughput,
                "success_rate": (success_count / size) * 100,
            }
        )

        # Cooldown to avoid 429 PerMinute
        if size < 30:
            print("[WAIT] 10s cooldown...")
            time.sleep(10)

    # Save Report
    report_path = "docs/Batch_Benchmark_Report_V2.md"
    with open(report_path, "w", encoding="utf-8") as f:
        f.write("# True Batching Benchmark Report (V2)\n\n")
        f.write(f"**Model**: {MODEL_NAME}\n")
        f.write(f"**Date**: {time.ctime()}\n\n")
        f.write("| Batch Size | Total Duration (s) | Throughput (s/tag) | Success Rate |\n")
        f.write("|------------|--------------------|--------------------|--------------|\n")
        for log in results_log:
            f.write(
                f"| {log['batch_size']} | {log['duration']:.2f} | {log['throughput']:.3f} | {log['success_rate']:.1f}% |\n"
            )

        f.write("\n## Conclusion\n")
        best = min(results_log, key=lambda x: x["throughput"])
        f.write(
            f"Optimal batch size for throughput is **{best['batch_size']}** with **{best['throughput']:.3f}s/tag**.\n"
        )

    print(f"\n=== BENCHMARK V2 COMPLETE. Report saved to {report_path} ===")


if __name__ == "__main__":
    run_benchmark_v2()
