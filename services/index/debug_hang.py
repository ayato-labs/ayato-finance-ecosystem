import sys
print("Imports starting...")
import argparse
import uvicorn
from loguru import logger
print("Loguru imported")
from src.api.app import app, engine, fetcher
print("App imported")
from src.logging_utils import setup_logging, trace
print("Logging utils imported")
setup_logging("test")
print("Logging setup done")
@trace("test_trace")
def test_func():
    print("Inside test_func")
    return True
print("Calling test_func")
test_func()
print("Done")
