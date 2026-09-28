"""04 · document_loader — read documents from the local data directory.

Two readers, nothing else:
    load_documents_from_local()            — the raw .txt HR policies
    load_processed_documents_from_local()  — parsed JSON records, written by
                                                processor.py (05)

Binary formats (.pdf/.docx/.pptx) are parsed in processor.py, not here —
this file only loads text that is already text.
"""

import json
from pathlib import Path

from langchain_core.documents import Document

# langchain document cotains 2 things 

# 1) pagecontent: the text content of the document
# 2) metadata: a dictionary of metadata about the document, such as the source,

from hr_assistant import config

## extract policy 
def extract_policy_category(text: str) -> str:
    """Every policy file starts with a 'Policy Category: X' line (HR docs)
    or a 'Category: X' line (noise docs) — pull whichever is present out.
    Shared with processor.py (05)."""
    for line in text.splitlines()[:5]:
        stripped = line.strip().lower()
        if stripped.startswith("policy category:"):
            return line.split(":", 1)[1].strip()
        if stripped.startswith("category:"):
            return line.split(":", 1)[1].strip()
    return "Unknown"


# Load raw HR policy text files.

def load_documents_from_local(data_dir: Path = config.DATA_DIR) -> list[Document]:
    """Read every top-level .txt HR policy under the local data directory,
    returning one LangChain Document per file with source + category
    metadata."""
    documents = []
    for path in sorted(data_dir.glob("*.txt")):
        text = path.read_text(encoding="utf-8")
        documents.append(Document(
            page_content=text,
            metadata={
                "source": path.name,
                "policy_category": extract_policy_category(text),
                "local_path": str(path),
            },
        ))
    return documents


# Load locally processed records.

def load_processed_documents_from_local(
    processed_dir: Path = config.PROCESSED_DATA_DIR,
) -> list[Document]:
    """Read parsed JSON records written under the local processed directory."""
    documents = []
    for path in sorted(processed_dir.rglob("*.json")):
        record = json.loads(path.read_text(encoding="utf-8"))
        documents.append(Document(
            page_content=record["text"],
            metadata={
                "source": record["source"],
                "policy_category": record["policy_category"],
                "local_path": record["raw_local_path"],
            },
        ))
    return documents



