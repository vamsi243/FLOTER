"""Compatibility launcher for a locally installed Snippy source checkout.

FastMCP 3 exposes Image under utilities.types; older Snippy versions import it
from the package root. This alias repairs image serialization without modifying
Snippy's checkout. Usage: <Snippy-python> snippy_stdio.py <Snippy-source-dir>
"""
import sys
from pathlib import Path

if __name__ == '__main__':
    directory = Path(sys.argv[1]).resolve()
    if not (directory / 'mcp_server.py').is_file():
        raise SystemExit('Snippy mcp_server.py not found')
    sys.path.insert(0, str(directory))
    import fastmcp
    from fastmcp.utilities.types import Image
    if not hasattr(fastmcp, 'Image'):
        fastmcp.Image = Image
    import mcp_server
    mcp_server.run_mcp_stdio()
