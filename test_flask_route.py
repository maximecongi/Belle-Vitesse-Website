from flask import Flask
from functools import wraps

app = Flask(__name__)

def init_users_routes(app):
    def require_admin(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            return f(*args, **kwargs)
        return decorated_function

    @app.route("/admin/users")
    @require_admin
    def admin_users_list():
        pass

init_users_routes(app)
for rule in app.url_map.iter_rules():
    print(rule, rule.endpoint)
