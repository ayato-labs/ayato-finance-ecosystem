import psutil
import time
from loguru import logger

from src.core.config import settings

class MemoryGovernor:
    def __init__(self, limit_ratio=None, critical_threshold=None):
        """
        Args:
            limit_ratio: The ratio of total system RAM allowed for this process.
            critical_threshold: The total system RAM usage ratio at which we stop everything.
        """
        self.total_ram = psutil.virtual_memory().total
        self.limit_ratio = limit_ratio or settings.MEM_LIMIT_RATIO
        self.critical_threshold = critical_threshold or settings.MEM_CRITICAL_THRESHOLD
        
        self.limit_bytes = int(self.total_ram * self.limit_ratio)
        self.process = psutil.Process()
        
        logger.info(f"MemoryGovernor initialized: Process limit {self.limit_bytes / (1024**3):.2f} GB ({self.limit_ratio*100}%), "
                    f"System critical threshold {self.critical_threshold*100}%")

    def is_pressured(self) -> bool:
        # ... (rest of the code stays same)
        sys_mem = psutil.virtual_memory()
        proc_mem = self.process.memory_info().rss
        
        # System-wide pressure
        if sys_mem.percent > (self.critical_threshold * 100):
            logger.warning(f"System memory pressure high: {sys_mem.percent}%")
            return True
            
        # Process-specific pressure
        if proc_mem > self.limit_bytes:
            logger.warning(f"Process memory usage ({proc_mem / (1024**3):.2f} GB) "
                           f"exceeds safety limit ({self.limit_bytes / (1024**3):.2f} GB)")
            return True
            
        return False

    def wait_for_clearance(self, check_interval=None):
        """Blocks until memory pressure is relieved."""
        interval = check_interval or settings.MEM_CHECK_INTERVAL
        while self.is_pressured():
            logger.info(f"Waiting {interval}s for memory clearance...")
            time.sleep(interval)

governor = MemoryGovernor()
