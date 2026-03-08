"""Local entrypoint for the web portal scaffold."""

import os

from app import create_app


app = create_app()


if __name__ == "__main__":
    host = os.getenv("WEB_PORTAL_HOST", "127.0.0.1")
    port = int(os.getenv("WEB_PORTAL_PORT", "5050"))
    app.run(host=host, port=port, debug=False)
