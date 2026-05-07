import uvicorn
from fastapi import FastAPI
import duckdb
from pathlib import Path

app = FastAPI(title="FRED Provider API")

@app.get("/series/{series_id}")
def get_series(series_id: str):
    db_path = Path("data/fred.duckdb")
    if not db_path.exists():
        return {"error": "Database not found"}
    
    conn = duckdb.connect(str(db_path), read_only=True)
    df = conn.execute("SELECT * FROM observations WHERE series_id = ?", [series_id]).fetchdf()
    conn.close()
    
    return df.to_dict(orient="records")

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=5011)
