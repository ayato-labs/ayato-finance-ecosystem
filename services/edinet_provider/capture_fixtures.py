import edinet_tools
import json
import os


def capture_data():
    entity = edinet_tools.entity("7203")
    docs = entity.documents(days=365)[:5]
    data = [doc._data for doc in docs]
    os.makedirs("tests/fixtures", exist_ok=True)
    with open("tests/fixtures/edinet_replay.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)


if __name__ == "__main__":
    capture_data()
