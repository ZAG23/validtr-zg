"""MCP transport parsing: unsupported transports are skipped, not fatal."""

from models.stack import MCPTransport, build_mcp_servers


def test_try_parse_supported():
    assert MCPTransport.try_parse("stdio") is MCPTransport.STDIO
    assert MCPTransport.try_parse("streamable-http") is MCPTransport.STREAMABLE_HTTP


def test_try_parse_none_defaults_to_stdio():
    assert MCPTransport.try_parse(None) is MCPTransport.STDIO


def test_try_parse_deprecated_sse_is_none():
    assert MCPTransport.try_parse("sse") is None


def test_try_parse_unknown_is_none():
    assert MCPTransport.try_parse("websocket") is None


def test_build_skips_sse_servers():
    raw = [
        {"name": "fs", "transport": "stdio", "install": "x"},
        {"name": "remote", "transport": "sse", "install": "y"},
        {"name": "http", "transport": "streamable-http", "install": "z"},
    ]
    servers = build_mcp_servers(raw)
    names = [s.name for s in servers]
    assert names == ["fs", "http"]  # sse server dropped


def test_build_defaults_missing_transport_to_stdio():
    servers = build_mcp_servers([{"name": "fs"}])
    assert servers[0].transport is MCPTransport.STDIO


def test_build_dedups_by_name():
    seen: set[str] = set()
    first = build_mcp_servers([{"name": "fs", "transport": "stdio"}], seen_names=seen)
    second = build_mcp_servers([{"name": "fs", "transport": "stdio"}], seen_names=seen)
    assert len(first) == 1
    assert second == []


def test_build_skips_nameless_servers():
    servers = build_mcp_servers([{"transport": "stdio"}, {"name": "", "transport": "stdio"}])
    assert servers == []
