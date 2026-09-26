#!/usr/bin/env python3
import sys
from pathlib import Path

# Add workspace virtual environment site-packages if present
VENV_LIB = Path(__file__).resolve().parent / ".venv" / "lib"
if VENV_LIB.exists():
    for site_pkg in VENV_LIB.glob("python*/site-packages"):
        if str(site_pkg) not in sys.path:
            sys.path.insert(0, str(site_pkg))

# Add consentor_be directory to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent))

if __name__ == "__main__":
    import uvicorn
    print("\n=======================================================")
    print("  Starting Consentor Face ID Biometric API Server")
    print("  Docs: http://localhost:8000/docs")
    print("  OpenAPI: http://localhost:8000/api/v1/openapi.json")
    print("=======================================================\n")
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
