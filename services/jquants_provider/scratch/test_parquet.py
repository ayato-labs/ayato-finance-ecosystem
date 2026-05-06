import os
from pathlib import Path
from src.engine import JPEngine

def test_parquet_export():
    engine = JPEngine()
    output_path = Path("scratch/test_export.parquet")
    if output_path.exists():
        os.remove(output_path)
    
    # Export daily_prices (which should have some data from the sync)
    try:
        engine.export_to_parquet("daily_prices", output_path)
        if output_path.exists():
            print(f"Success! Parquet file created at {output_path}")
            print(f"File size: {os.path.getsize(output_path) / 1024:.2f} KB")
        else:
            print("Failed: File was not created.")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_parquet_export()
