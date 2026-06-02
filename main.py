import sys
import os

sys.path.append(
    os.path.join(
        os.path.dirname(__file__),
        "flask-app"
    )
)

from app import app

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
