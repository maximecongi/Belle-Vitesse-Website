from app import create_app
import os

app = create_app()

if __name__ == "__main__":
    if os.getenv("FLASK_ENV") == "production":
        app.run()
    else:
        app.config["TEMPLATES_AUTO_RELOAD"] = True
        app.run(debug=True, use_reloader=True)
