"""Explicit local Snippy MCP client; server output is data, never instructions."""
import asyncio
import json
import base64
import io
import uuid
from contextlib import AsyncExitStack
from urllib.parse import urlparse
from floter.security.sandbox import SafeFileSystem
from pathlib import Path
from floter.config import config
from floter.workers import CancelledError

ALLOWED_TOOLS = {'snippy_get_monitor_layout', 'snippy_take_snip', 'snippy_ocr_screen',
                 'snippy_extract_table', 'snippy_get_color_palette'}

def validate_server_url(url):
    parsed = urlparse(url)
    if parsed.scheme != 'http' or parsed.hostname not in {'127.0.0.1', 'localhost', '::1'} or parsed.username or parsed.password or parsed.fragment:
        raise ValueError('Snippy SSE must use a local loopback HTTP URL without credentials')
    return url

async def _session(tool, arguments, cancel):
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
    from mcp.client.sse import sse_client
    async def operation():
        async with AsyncExitStack() as stack:
            if config.SNIPPY_URL:
                read, write = await stack.enter_async_context(sse_client(validate_server_url(config.SNIPPY_URL), timeout=5, sse_read_timeout=20))
            else:
                command = Path(config.SNIPPY_COMMAND)
                if not command.is_absolute() or not command.is_file():
                    raise RuntimeError('Set SNIPPY_URL or the absolute SNIPPY_COMMAND path')
                args = json.loads(config.SNIPPY_ARGS)
                if not isinstance(args, list) or not all(isinstance(arg,str) for arg in args):
                    raise ValueError('SNIPPY_ARGS must be a JSON string array')
                server = StdioServerParameters(command=str(command), args=args, cwd=config.SNIPPY_CWD or str(command.parent))
                read, write = await stack.enter_async_context(stdio_client(server))
            session = await stack.enter_async_context(ClientSession(read, write))
            await session.initialize()
            if tool == 'list_tools':
                response = await session.list_tools()
                return {'tools':[t.name for t in response.tools if t.name in ALLOWED_TOOLS]}
            response = await session.call_tool(tool, arguments)
            if response.isError:
                raise RuntimeError('Snippy reported an MCP tool error')
            data = response.model_dump(mode='json')
            return save_screenshot(data) if tool == 'snippy_take_snip' else data
    task = asyncio.create_task(operation())
    deadline = asyncio.get_running_loop().time() + 20
    try:
        while not task.done():
            if asyncio.get_running_loop().time() >= deadline:
                raise TimeoutError('Snippy exceeded its time budget')
            if cancel is not None and cancel.is_set():
                raise CancelledError('Snippy request cancelled')
            await asyncio.sleep(.05)
        return await task
    finally:
        if not task.done():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass


def call_snippy(tool, arguments=None, cancel=None):
    if tool not in ALLOWED_TOOLS | {'list_tools'}:
        raise ValueError('Unsupported Snippy tool')
    arguments = arguments or {}
    if set(arguments) - {'region'}:
        raise ValueError('Unsupported Snippy arguments')
    if 'region' in arguments:
        region=arguments['region']
        if not isinstance(region,list) or len(region)!=4 or any(type(v) is not int for v in region) or region[2]<=region[0] or region[3]<=region[1]:
            raise ValueError('Invalid screen region')
    return asyncio.run(_session(tool,arguments,cancel))


def save_screenshot(response):
    """Accept actual MCP image bytes; never treat a PIL repr as a screenshot."""
    from PIL import Image
    for item in response.get('content', []):
        if item.get('type') != 'image':
            continue
        encoded = item.get('data', '')
        if not isinstance(encoded, str) or len(encoded) > 40_000_000:
            raise ValueError('Snippy image exceeds its size budget')
        try:
            raw = base64.b64decode(encoded, validate=True)
            with Image.open(io.BytesIO(raw)) as image:
                if image.width * image.height > 40_000_000:
                    raise ValueError('Snippy image dimensions exceed their budget')
                image.verify()
            extension = {'image/png':'.png', 'image/jpeg':'.jpg'}.get(item.get('mimeType'))
            if not extension:
                raise ValueError('Unsupported screenshot image type')
        except Exception as exc:
            raise RuntimeError('Snippy returned invalid image data') from exc
        path = config.SNIPPY_CACHE_DIR / ('snippy_' + uuid.uuid4().hex + extension)
        SafeFileSystem.write_new_bytes(path, raw)
        return {'path':str(path),'source':'Snippy MCP','status':'success'}
    raise RuntimeError('Snippy returned no image bytes. This server version returns a PIL object description; update its snippy_take_snip tool to return an MCP ImageContent result. No screenshot was saved.')
