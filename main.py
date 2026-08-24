"""JeevanLink entry point.

    python main.py

Then open http://127.0.0.1:5000 in a browser.
"""

import os

from jeevanlink.run import create_app


app = create_app()


if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    host = os.getenv("HOST", "127.0.0.1")

    print("=" * 55)
    print("  JeevanLink is running")
    print(f"  Home        : http://{host}:{port}")
    print(f"  Donate      : http://{host}:{port}/donate")
    print(f"  Request     : http://{host}:{port}/request")
    print(f"  Health      : http://{host}:{port}/api/health")
    print("=" * 55)

    app.run(host=host, port=port, debug=True)
