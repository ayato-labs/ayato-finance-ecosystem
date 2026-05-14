import time

import psutil
from loguru import logger

from src.shared.infra.config import settings


class GovernanceService:
    @staticmethod
    def get_system_metrics():
        process = psutil.Process()
        return {
            "cpu_percent": process.cpu_percent(),
            "memory_mb": process.memory_info().rss / (1024 * 1024),
            "disk_usage": psutil.disk_usage(str(settings.DATA_DIR)).percent,
            "timestamp": time.time(),
        }

    @staticmethod
    def check_health():
        metrics = GovernanceService.get_system_metrics()
        logger.debug(f"Health Check: {metrics}")
        # Add logic for auto-throttling if disk is full
        if metrics["disk_usage"] > 95:
            logger.error("CRITICAL: Disk usage > 95%. Suggesting pause.")
            return False
        return True
