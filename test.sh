#!/bin/bash
# Test script for Tunnbox

set -e

echo "========================================"
echo "  Tunnbox - Running Tests"
echo "========================================"

# Backend tests
echo ""
echo "[1/2] Running backend tests..."
cd backend
python3 -m pytest -v --tb=short
cd ..

echo ""
echo "========================================"
echo "  All tests passed!"
echo "========================================"
