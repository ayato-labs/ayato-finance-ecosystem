import os
import zstandard as zstd
from loguru import logger

# デフォルトの辞書ファイルパス
DEFAULT_DICT_PATH = os.path.abspath(
    os.path.join(
        os.path.dirname(__file__),
        "..", "..", "..", "..", "data", "edgar_zstd.dict"
    )
)

class ZstdCompressor:
    """
    辞書付き Zstd 圧縮・解凍を行うクラス
    """
    def __init__(self, dict_path: str = DEFAULT_DICT_PATH):
        self.dict_path = dict_path
        self.dict_data = None
        self.cctx = None
        self.dctx = None
        self._load_dict()

    def _load_dict(self):
        if os.path.exists(self.dict_path):
            try:
                with open(self.dict_path, "rb") as f:
                    self.dict_data = zstd.ZstdCompressionDict(f.read())
                self.cctx = zstd.ZstdCompressor(dict_data=self.dict_data)
                self.dctx = zstd.ZstdDecompressor(dict_data=self.dict_data)
                logger.info(f"Loaded Zstd dictionary from {self.dict_path}")
            except Exception as e:
                logger.error(f"Failed to load dictionary from {self.dict_path}: {e}")
                self._fallback()
        else:
            logger.warning(f"Dictionary file not found at {self.dict_path}. Falling back to standard Zstd.")
            self._fallback()

    def _fallback(self):
        self.cctx = zstd.ZstdCompressor()
        self.dctx = zstd.ZstdDecompressor()

    def compress(self, data: bytes) -> bytes:
        """データを圧縮する"""
        return self.cctx.compress(data)

    def decompress(self, data: bytes) -> bytes:
        """データを解凍する"""
        return self.dctx.decompress(data)

    def is_using_dict(self) -> bool:
        """辞書を使用しているかどうかを返す"""
        return self.dict_data is not None
