from pathlib import Path
from typing import Any
import subprocess
import os
import re

SRC_FOLDER = Path(__file__).resolve().parent.parent

def repr_tool_args(args:dict[str, Any]) -> str:
    return "\n".join([f" - {arg} = {val}" for arg, val in args.items()])

def format_contact_embedding_string(name:str, email:str | None = None, phone_number:str | None = None, notes:str | None = None):
    return f"Name: {name}\nEmail: {email or ''}\nPhone Number: {phone_number or ''}\nNotes:\n{notes or ''}"


def set_permanent_env_var(key:str, value:str):
    system = os.name
    os.environ[key] = value
    
    if system == 'nt':
        # Windows handles overwriting automatically
        subprocess.run(['setx', key, value], check=True, capture_output=True)
        return f"Windows: {key} updated."
    
    else:
        # Linux/macOS: Find and replace the line if it exists
        shell = os.environ.get('SHELL', '')
        profile = os.path.expanduser('~/.zshrc' if 'zsh' in shell else '~/.bashrc')
        new_line = f'export {key}="{value}"'
        
        if os.path.exists(profile):
            with open(profile, 'r') as f:
                lines = f.readlines()
            
            # Use regex to find any existing export for this key
            pattern = re.compile(f'^export {key}=.*')
            new_lines = [new_line + '\n' if pattern.match(line) else line for line in lines]
            
            # If the key wasn't found at all, append it
            if not any(pattern.match(line) for line in lines):
                new_lines.append(f'\n{new_line}\n')
            
            with open(profile, 'w') as f:
                f.writelines(new_lines)
        else:
            with open(profile, 'w') as f:
                f.write(f'# Created by Python script\n{new_line}\n')
        
        return f"Unix: {key} updated in {profile}."


import requests

def test_ollama_connection(url="http://localhost:11434"):
    try:
        # Hitting /api/tags is a reliable way to verify full API functionality
        response = requests.get(f"{url}/api/tags", timeout=5)
        if response.status_code == 200:
            return True
    except Exception:
        pass
    return False