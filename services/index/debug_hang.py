print("Imports starting...")


print("Loguru imported")

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
