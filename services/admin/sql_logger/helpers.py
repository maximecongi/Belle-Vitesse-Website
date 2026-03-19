import re
import ast
from flask import request, session, has_request_context

SENSITIVE_KEYS = {"password", "token", "secret", "authorization", "cookie"}


def escape_sql(value):
    return str(value).replace("'", "''")


def sanitize_params(params):
    if isinstance(params, dict):
        return {
            k: "***" if k.lower() in SENSITIVE_KEYS else v
            for k, v in params.items()
        }
    return params


def render_query(query: str, parameters) -> str:
    if not parameters:
        return query

    params = parameters

    if isinstance(params, str):
        try:
            params = ast.literal_eval(params)
        except Exception:
            return query

    if isinstance(params, dict):
        def replace(match):
            key = match.group(1)
            val = params.get(key)

            if val is None:
                return "NULL"
            if isinstance(val, str):
                return f"'{escape_sql(val)}'"
            return str(val)

        return re.sub(r'%\((\w+)\)s', replace, query)

    if isinstance(params, (list, tuple)):
        it = iter(params)

        def replace(_):
            val = next(it, None)

            if val is None:
                return "NULL"
            if isinstance(val, str):
                return f"'{escape_sql(val)}'"
            return str(val)

        return re.sub(r'%s', replace, query)

    return query


def get_request_context():
    if not has_request_context():
        return {
            "user": "system",
            "endpoint": None,
            "method": None,
            "ip_address": None
        }

    try:
        ip_address = request.headers.get("X-Forwarded-For")
        if ip_address:
            ip_address = ip_address.split(",")[0].strip()
        else:
            ip_address = request.remote_addr

        session_firstname = session.get("admin_user_firstname")
        session_lastname = session.get("admin_user_lastname")

        if session_firstname and session_lastname:
            user = f"{session_firstname} {session_lastname}"
        elif session_firstname:
            user = session_firstname
        else:
            user = session.get("user", "anonymous")

        if isinstance(user, dict):
            user = user.get("email") or str(user.get("id", "anonymous"))

        return {
            "user": str(user),
            "endpoint": request.endpoint,
            "method": request.method,
            "ip_address": ip_address
        }

    except Exception:
        return {
            "user": "unknown",
            "endpoint": None,
            "method": None,
            "ip_address": None
        }
