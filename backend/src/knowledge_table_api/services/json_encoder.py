"""JSON Encoder."""

import json
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Dict

import numpy as np
from whyhow import Chunk, ChunkMetadata


class CustomJSONEncoder(json.JSONEncoder):
    """Custom JSON encoder that handles a variety of data types."""

    def default(self, obj: Any) -> Any:
        """Override the default JSON encoding behavior to handle additional data types."""
        if isinstance(obj, bool):
            return str(obj).lower()
        elif isinstance(obj, (datetime, date)):
            return obj.isoformat()
        elif isinstance(obj, Decimal):
            return float(obj)
        elif isinstance(obj, (set, frozenset)):
            return list(obj)
        elif isinstance(obj, Chunk):
            return self.encode_chunk(obj)
        elif isinstance(obj, ChunkMetadata):
            return self.encode_chunk_metadata(obj)
        elif isinstance(obj, np.ndarray):
            return obj.tolist()
        elif isinstance(obj, np.integer):
            return int(obj)
        elif isinstance(obj, np.floating):
            return float(obj)
        elif hasattr(obj, "to_dict"):
            return obj.to_dict()
        elif hasattr(obj, "__dict__"):
            return {
                key: self.default(value) for key, value in obj.__dict__.items()
            }
        try:
            return super().default(obj)
        except TypeError:
            return str(obj)

    def encode_chunk(self, chunk: Chunk) -> Dict[str, Any]:
        """Encode a Chunk object into a JSON-serializable dictionary."""
        return {
            "chunk_id": chunk.chunk_id,
            "created_at": (
                chunk.created_at.isoformat() if chunk.created_at else None
            ),
            "updated_at": (
                chunk.updated_at.isoformat() if chunk.updated_at else None
            ),
            "document_id": chunk.document_id,
            "workspace_ids": chunk.workspace_ids,
            "metadata": (
                self.encode_chunk_metadata(chunk.metadata)
                if chunk.metadata
                else None
            ),
            "content": chunk.content,
            "embedding": self.default(chunk.embedding),
            "tags": chunk.tags,
            "user_metadata": chunk.user_metadata,
        }

    def encode_chunk_metadata(self, metadata: ChunkMetadata) -> Dict[str, Any]:
        """Encode ChunkMetadata object into a JSON-serializable dictionary."""
        return {
            "language": metadata.language,
            "length": metadata.length,
            "size": metadata.size,
            "data_source_type": metadata.data_source_type,
            "index": metadata.index,
            "page": metadata.page,
            "start": metadata.start,
            "end": metadata.end,
        }
