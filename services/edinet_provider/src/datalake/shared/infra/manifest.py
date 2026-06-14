from src.datalake.shared.infra.db import db_manager

def init_manifest():
    """Initialize the manifest table."""
    with db_manager.connect_master(read_only=False) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS registry_db.document_manifest (
                doc_id VARCHAR PRIMARY KEY,
                status VARCHAR,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

def get_document_status(doc_id: str) -> str | None:
    """Get the status of a document."""
    try:
        with db_manager.connect_master(read_only=True) as conn:
            result = conn.execute(
                "SELECT status FROM registry_db.document_manifest WHERE doc_id = ?", [doc_id]
            ).fetchone()
            return result[0] if result else None
    except Exception:
        # Fallback if table does not exist yet
        return None

def update_document_status(doc_id: str, status: str):
    """Update the status of a document."""
    with db_manager.connect_master(read_only=False) as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO registry_db.document_manifest (doc_id, status, updated_at)
            VALUES (?, ?, CURRENT_TIMESTAMP)
        """,
            [doc_id, status],
        )
