"""Entry point: `python run.py`  (set FLASK_DEBUG=1 for the debugger/reloader)."""

import os

from app import app

if __name__ == "__main__":
    app.run(debug=os.environ.get("FLASK_DEBUG") == "1")
