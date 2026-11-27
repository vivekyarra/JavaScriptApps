"""Compatibility shim: the server now lives in pharos.server."""
from .server import main, mcp  # noqa: F401

if __name__ == "__main__":
    main()
