import sys
from pathlib import Path

# Add current dir to path
sys.path.append(str(Path.cwd()))

print("--- IMPORT DEBUG START ---")

print("Importing datetime...")
import datetime
print("Importing time...")
import time
print("Importing typing...")
from typing import List
print("Importing duckdb...")
import duckdb
print("Importing loguru...")
from loguru import logger

print("Importing settings...")
from src.infra.config import settings
print("Importing setup_logging...")
from src.infra.logging_config import setup_logging

print("Importing DataRepository...")
from src.queries.repository import DataRepository
print("Importing JPEDINETEngine...")
from src.engine import JPEDINETEngine

print("--- IMPORT DEBUG END ---")
