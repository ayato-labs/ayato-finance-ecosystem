import sys
import os

print("--- IMPORT DEBUG START ---")
print(f"Python Version: {sys.version}")
print(f"Executable: {sys.executable}")
print(f"CWD: {os.getcwd()}")
print("Path:")
for p in sys.path:
    print(f"  {p}")

print("\nImporting datetime...")
import datetime

print("Importing time...")
import time

print("Importing typing...")
import typing

print("Importing duckdb...")
import duckdb

print("Importing loguru...")
import loguru

# Test if we can import edinet_tools without pandas
print("Importing edinet_tools.config...")
import edinet_tools.config

print("Importing edinet_tools.timezone...")
import edinet_tools.timezone

print("\n--- IMPORT DEBUG END ---")
