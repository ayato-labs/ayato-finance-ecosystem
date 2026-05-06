from src.logging_utils import setup_logging
import os

def test_error_isolation():
    logger = setup_logging(unit_name="test_error")
    logger.info("This is an INFO message - should not be in error.log")
    logger.error("This is an ERROR message - MUST be in error.log")
    
    log_dir = "logs"
    error_log = os.path.join(log_dir, "error.log")
    
    if os.path.exists(error_log):
        print(f"SUCCESS: {error_log} created.")
        with open(error_log, "r") as f:
            content = f.read()
            if "ERROR" in content and "INFO" not in content:
                print("SUCCESS: Only ERROR level messages are in error.log")
            else:
                print("FAILURE: Content mismatch in error.log")
    else:
        print("FAILURE: error.log not created.")

if __name__ == "__main__":
    test_error_isolation()
