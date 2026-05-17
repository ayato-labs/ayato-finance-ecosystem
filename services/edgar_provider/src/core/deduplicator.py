import hashlib
from typing import List, Tuple, Dict

class Deduplicator:
    @staticmethod
    def chunk_text(text: str) -> List[str]:
        """
        Split text into chunks. 
        Using double newlines as a simple paragraph-based chunking.
        """
        # Split by double newline and remove empty chunks
        chunks = [c.strip() for c in text.split("\n\n") if c.strip()]
        return chunks

    @staticmethod
    def get_hash(text: str) -> str:
        """
        Calculate SHA-256 hash of the text.
        """
        return hashlib.sha256(text.encode("utf-8")).hexdigest()

    def deduplicate(self, text: str) -> Tuple[List[str], Dict[str, str]]:
        """
        Deduplicate text by chunking and hashing.
        Returns:
            - List of chunk hashes in order.
            - Dictionary of hash -> chunk_content for unique chunks.
        """
        chunks = self.chunk_text(text)
        chunk_hashes = []
        unique_chunks = {}
        
        for chunk in chunks:
            h = self.get_hash(chunk)
            chunk_hashes.append(h)
            if h not in unique_chunks:
                unique_chunks[h] = chunk
                
        return chunk_hashes, unique_chunks
