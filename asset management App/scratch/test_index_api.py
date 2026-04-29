import asyncio
import httpx

async def test():
    url = "http://127.0.0.1:5009/prices/^GSPC"
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(url)
            print(f"Status: {resp.status_code}")
            data = resp.json()
            print(f"Count: {len(data)}")
            if data:
                print(f"Last entry: {data[-1]}")
        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(test())
