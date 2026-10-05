#!/usr/bin/env python
"""Test script to verify .env loading."""

from pathlib import Path
import os
import sys

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from dotenv import load_dotenv

print("=" * 60)
print("Testing .env Loading")
print("=" * 60)

# Test the path calculation
core_file = Path(__file__).parent / 'src' / 'graphgen' / 'core.py'
print(f"\n✅ core.py path: {core_file}")
print(f"   Exists: {core_file.exists()}")

repo_root = core_file.parent.parent.parent
print(f"\n✅ Calculated repo root: {repo_root}")

env_file = repo_root / '.env'
print(f"\n✅ Expected .env location: {env_file}")
print(f"   Exists: {env_file.exists()}")

# Show all potential .env locations
print(f"\n📍 .env file search order:")
print(f"   1. Repo root: {repo_root / '.env'} → {(repo_root / '.env').exists()}")
print(f"   2. Current dir: {Path.cwd() / '.env'} → {(Path.cwd() / '.env').exists()}")
print(f"   3. Home/.graphaide: {Path.home() / '.graphaide' / '.env'} → {(Path.home() / '.graphaide' / '.env').exists()}")
print(f"   4. Home: {Path.home() / '.env'} → {(Path.home() / '.env').exists()}")

# Try loading it
if env_file.exists():
    print(f"\n🔄 Loading .env from: {env_file}")
    load_dotenv(str(env_file))

    # Check key variables
    variables_to_check = [
        'OPENAI_API_KEY',
        'OPENAI_MODEL_NAME',
        'NEO4J_URI',
        'LANGFUSE_PUBLIC_KEY',
        'LANGFUSE_SECRET_KEY',
    ]

    print(f"\n📋 Environment variables loaded:")
    for var in variables_to_check:
        value = os.getenv(var)
        if value:
            # Mask sensitive values
            if 'KEY' in var or 'PASSWORD' in var:
                display = value[:10] + '...' if len(value) > 10 else value
            else:
                display = value
            print(f"   ✅ {var}: {display}")
        else:
            print(f"   ❌ {var}: NOT SET")
else:
    print(f"\n❌ .env file NOT found at: {env_file}")

print("\n" + "=" * 60)
