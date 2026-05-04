import asyncio
import statistics
import time
from http import HTTPStatus

import httpx

API_URL = "http://127.0.0.1:5005"
TICKERS = ["AAPL", "MSFT", "GOOGL", "AMZN", "7203.T", "8035.T"]
HTTP_OK = HTTPStatus.OK


async def fetch_price(client, ticker):
    start = time.time()
    try:
        resp = await client.get(f"{API_URL}/prices/{ticker}", timeout=10)
        elapsed = time.time() - start
        return elapsed, resp.status_code
    except Exception as e:
        return time.time() - start, str(e)


async def stress_test(concurrency):
    print(f"\n[Stress Test] Simulating {concurrency} concurrent requests...")

    async with httpx.AsyncClient() as client:
        tasks = []
        for i in range(concurrency):
            ticker = TICKERS[i % len(TICKERS)]
            tasks.append(fetch_price(client, ticker))

        start_time = time.time()
        results = await asyncio.gather(*tasks)
        total_time = time.time() - start_time

        latencies = [r[0] for r in results if isinstance(r[1], int) and r[1] == HTTP_OK]
        errors = [r for r in results if not (isinstance(r[1], int) and r[1] == HTTP_OK)]

        if latencies:
            success_rate = len(latencies) / concurrency * 100
            print(f"  - Success Rate: {len(latencies)}/{concurrency} ({success_rate:.1f}%)")
            print(f"  - Avg Latency: {statistics.mean(latencies):.4f}s")
            print(f"  - P95 Latency: {statistics.quantiles(latencies, n=20)[18]:.4f}s")
            print(f"  - Total Test Time: {total_time:.4f}s")
        else:
            print("  - CRITICAL: No successful requests.")

        if errors:
            print(f"  - Errors encountered: {len(errors)} (First: {errors[0][1]})")


async def run_all():
    # Warm up
    async with httpx.AsyncClient() as client:
        await client.get(f"{API_URL}/status")

    for c in [5, 20, 50]:
        await stress_test(c)


if __name__ == "__main__":
    asyncio.run(run_all())
