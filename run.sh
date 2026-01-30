#!/bin/bash
# Helper script to run PolyArb-X

# Run in dry-run mode by default
echo "🚀 Starting PolyArb-X (Dry Run)..."
PYTHONPATH=. python3 src/main.py --dry-run
