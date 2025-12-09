from typing import Any, List, Dict
from pathlib import Path
from mcp.server.fastmcp import FastMCP  # type: ignore

# create a new fastmcp server instance that models can connect to
mcp = FastMCP("study-docs-server")

# absolute path to the folder where study documents are stored
# this folder is the only allowed access point for all tools
DOCS_ROOT = Path("/Users/deepikaparthasarathy/Desktop/MCP/classDocs").expanduser().resolve()


def _all_files() -> List[Path]:
    """
    recursively return all valid files inside docs_root.
    this ignores hidden files and non-files, ensuring the model does not see system metadata.
    """
    if not DOCS_ROOT.exists():
        return []

    return [
        p for p in DOCS_ROOT.rglob("*")
        if p.is_file() and not any(part.startswith(".") for part in p.parts)
    ]


def _safe_join(path: str) -> Path:
    """
    safely join a user-provided file path with docs_root.
    prevents path traversal attacks like '../../../private.txt'
    by checking that the resolved path is still inside docs_root.
    """
    full = (DOCS_ROOT / path).resolve()
    if DOCS_ROOT not in full.parents and full != DOCS_ROOT:
        raise ValueError("invalid file path - access denied")
    return full


@mcp.tool()
def list_documents() -> List[str]:
    """
    list all available study documents that the model can access.
    returned paths are relative so they can be passed safely into other tools.
    """
    return [str(f.relative_to(DOCS_ROOT)) for f in _all_files()]


@mcp.tool()
def read_document(path: str, max_chars: int = 8000) -> str:
    """
    read a document's content as plain text.
    limits output to avoid overwhelming the model or exceeding context size.
    returns a warning if the file is unreadable or doesn't exist.
    """
    file_path = _safe_join(path)

    if not file_path.exists():
        return f"file not found: {path}"

    try:
        text = file_path.read_text(errors="ignore")
    except Exception:
        return "this file is not readable as text."

    # truncate long files so model does not receive too much content
    if len(text) > max_chars:
        return text[:max_chars] + "\n\n...[truncated]..."
    return text


@mcp.tool()
def search_documents(query: str, max_results: int = 10) -> List[Dict[str, Any]]:
    """
    search all study documents for a given keyword.
    returns small snippets showing where the match occurs so the model has context.
    stops once max_results is reached to keep responses efficient.
    """
    q = query.lower()
    results = []

    for f in _all_files():
        # ignore files that cannot be read as text
        try:
            text = f.read_text(errors="ignore")
        except Exception:
            continue

        idx = text.lower().find(q)
        if idx == -1:
            continue

        # extract a short preview around the match
        snippet = text[max(0, idx - 80):idx + 80].replace("\n", " ")
        results.append({
            "path": str(f.relative_to(DOCS_ROOT)),
            "snippet": snippet
        })

        if len(results) >= max_results:
            break

    return results


def main():
    """
    launch the server using stdio transport.
    this allows models like claude to communicate with the server securely.
    """
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()

