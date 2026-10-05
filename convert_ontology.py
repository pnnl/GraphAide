#!/usr/bin/env python3
"""Convert N-Triples ontology to Turtle format for better compatibility."""

import sys
from pathlib import Path

def convert_ntriples_to_turtle(input_file, output_file):
    """Convert N-Triples to Turtle using rdflib."""
    try:
        import rdflib
    except ImportError:
        print("Installing rdflib...")
        import subprocess
        subprocess.check_call([sys.executable, "-m", "pip", "install", "rdflib"])
        import rdflib

    # Parse N-Triples
    g = rdflib.Graph()
    g.parse(input_file, format="nt")

    # Serialize to Turtle
    g.serialize(destination=output_file, format="turtle")

    print(f"✓ Converted {input_file} → {output_file}")
    print(f"  Triples: {len(g)}")
    return True

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python convert_ontology.py <input.nt or .ttl> [output.ttl]")
        sys.exit(1)

    input_path = sys.argv[1]
    output_path = sys.argv[2] if len(sys.argv) > 2 else input_path.replace(".nt", "_converted.ttl").replace(".ttl", "_converted.ttl")

    if not Path(input_path).exists():
        print(f"Error: File not found: {input_path}")
        sys.exit(1)

    try:
        convert_ntriples_to_turtle(input_path, output_path)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)
