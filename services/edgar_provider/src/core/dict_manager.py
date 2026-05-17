import os
from loguru import logger
from edgar_core.compression import ZstdCompressor

class DictManager:
    def __init__(self, base_dir: str = "data"):
        self.base_dir = base_dir
        self.dicts_dir = os.path.join(base_dir, "dicts")
        self.default_dict = os.path.join(base_dir, "edgar_zstd.dict")
        self.compressors = {} # Cache of compressors
        
        # Ensure dicts directory exists
        os.makedirs(self.dicts_dir, exist_ok=True)

    def get_dict_path(self, sic: str) -> str:
        """
        Get the path to the dictionary for a given SIC code.
        Falls back to default dictionary if not found.
        """
        if not sic:
            logger.warning("No SIC code provided, using default dictionary.")
            return self.default_dict
            
        sic_dict = os.path.join(self.dicts_dir, f"sic_{sic}.dict")
        if os.path.exists(sic_dict):
            logger.info(f"Using sector dictionary for SIC {sic}: {sic_dict}")
            return sic_dict
            
        logger.debug(f"Sector dictionary for SIC {sic} not found. Using default.")
        return self.default_dict

    def get_compressor(self, sic: str) -> ZstdCompressor:
        """
        Get a cached ZstdCompressor instance for the given SIC code.
        """
        dict_path = self.get_dict_path(sic)
        if dict_path not in self.compressors:
            logger.info(f"Creating new compressor for dict: {dict_path}")
            self.compressors[dict_path] = ZstdCompressor(dict_path=dict_path)
            
        return self.compressors[dict_path]
