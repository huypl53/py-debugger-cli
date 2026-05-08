"""Parse Python tracebacks to extract crash location."""

import re
from pathlib import Path


def parse_traceback(content: str) -> list[dict]:
    """Parse a Python traceback string and extract frame information.

    Returns a list of frames, last frame is the crash location.
    """
    frames = []

    # Match lines like:  File "/path/to/file.py", line 42, in function_name
    file_line_pattern = re.compile(
        r'^\s*File "([^"]+)", line (\d+)(?:, in (.+))?$'
    )

    lines = content.strip().split('\n')
    i = 0
    while i < len(lines):
        line = lines[i]
        match = file_line_pattern.match(line)
        if match:
            file_path = match.group(1)
            line_num = int(match.group(2))
            func_name = match.group(3) or "<module>"

            # Get the code line if available (next line)
            code = ""
            if i + 1 < len(lines):
                next_line = lines[i + 1]
                if not file_line_pattern.match(next_line) and next_line.strip():
                    code = next_line.strip()
                    i += 1

            frames.append({
                "file": file_path,
                "line": line_num,
                "function": func_name,
                "code": code,
            })
        i += 1

    return frames


def get_crash_location(content: str) -> dict | None:
    """Get the crash location from a traceback.

    Returns the last frame (where the error occurred).
    """
    frames = parse_traceback(content)
    if frames:
        return frames[-1]
    return None


def parse_traceback_file(file_path: str) -> list[dict]:
    """Parse a traceback from a file.

    If file_path is '-', reads from stdin.
    """
    import sys

    if file_path == "-":
        content = sys.stdin.read()
    else:
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"Traceback file not found: {file_path}")
        content = path.read_text()

    return parse_traceback(content)
