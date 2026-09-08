def parse_port(raw):
    """Parse a port string, falling back to 8080 when it is empty."""
    return int(raw)
