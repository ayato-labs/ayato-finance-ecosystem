import httpx
import asyncio

async def main():
    async with httpx.AsyncClient() as client:
        res = await client.get("http://127.0.0.1:5009/prices/^GSPC")
        data = res.json()
        print(f"Oldest: {data[0]['Date']}")
        print(f"Newest: {data[-1]['Date']}")
        print(f"Total rows: {len(data)}")

asyncio.run(main())
