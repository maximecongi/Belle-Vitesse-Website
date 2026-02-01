from app import create_app
import os
import warnings

# Silence DeprecationWarnings from cryptography (used by paramiko/sshtunnel)
# Specifically for the TripleDES warning which is often a CryptographyDeprecationWarning
warnings.filterwarnings("ignore", category=UserWarning, module='cryptography')
try:
    from cryptography.utils import CryptographyDeprecationWarning
    warnings.filterwarnings("ignore", category=CryptographyDeprecationWarning)
except ImportError:
    pass

app = create_app()

if __name__ == "__main__":
    if os.getenv("FLASK_ENV") == "production":
        app.run(host="0.0.0.0", port=5000, debug=False, use_reloader=False, threaded=True)
    else:
        app.config["TEMPLATES_AUTO_RELOAD"] = True
        app.run(debug=True, use_reloader=True)
