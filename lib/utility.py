from typing import Any

def repr_tool_args(args:dict[str, Any]) -> str:
    return ", ".join([f"{arg}={val}" for arg, val in args.items()])