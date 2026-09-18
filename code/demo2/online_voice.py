"""Isolate network synthesis so the parent can enforce a hard timeout without logging text."""
import asyncio
import json
import sys

from speech import _edge_audio

if __name__ == "__main__":
    try:
        request = json.load(sys.stdin)
        sys.stdout.buffer.write(asyncio.run(_edge_audio(request["text"], request["voice"], request["speed"])))
    except Exception as error:
        print(type(error).__name__, file=sys.stderr)
        sys.exit(1)
