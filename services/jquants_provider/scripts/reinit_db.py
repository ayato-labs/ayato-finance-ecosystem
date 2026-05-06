import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))

from src.engine import JPEngine

if __name__ == "__main__":
    print("Initializing database shards...")
    engine = JPEngine()
    print("Database initialized successfully.")
