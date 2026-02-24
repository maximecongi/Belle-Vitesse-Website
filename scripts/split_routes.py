import os

with open('routes/admin.py', 'r') as f:
    lines = f.readlines()

def get_section(start_str, end_str=None):
    start_idx = -1
    end_idx = len(lines)
    for i, l in enumerate(lines):
        if start_str in l:
            start_idx = i
            break
    if start_idx == -1: return []
    
    if end_str:
        for i in range(start_idx + 1, len(lines)):
            if end_str in lines[i]:
                end_idx = i
                break
    return lines[start_idx:end_idx]

# Map section comments to file names and function names
sections = [
    ("# ── Login / Logout ────────────────────────────────────────────", "auth.py", "init_auth_routes"),
    ("# ── File Serving ──────────────────────────────────────────────", "files.py", "init_files_routes"),
    ("# ── Dashboard ─────────────────────────────────────────────────", "dashboard.py", "init_dashboard_routes"),
    ("# ── Checkouts CRUD ────────────────────────────────────────────", "checkouts.py", "init_checkouts_routes"),
    ("# ── Checkins CRUD ────────────────────────────────────────────", "checkins.py", "init_checkins_routes"),
    ("# ── Projects CRUD ─────────────────────────────────────────────", "projects.py", "init_projects_routes"),
    ("# ── Productions CRUD ──────────────────────────────────────────", "productions.py", "init_productions_routes"),
    ("# ── Newsletter ────────────────────────────────────────────────", "newsletter.py", "init_newsletter_routes"),
    ("# ── Admin API ─────────────────────────────────────────────────", "api.py", "init_api_routes")
]

os.makedirs('routes/admin', exist_ok=True)

imports = """from utils.decorators import require_roles
from datetime import datetime, timezone
from flask import (
    render_template,
    abort,
    jsonify,
    request,
    current_app,
    session,
    redirect,
    url_for,
    flash,
)

from extensions import csrf
from extensions import limiter
from utils.mailer import send_newsletter_campaign

from services.admin import (
    list_checkouts,
    get_checkout_detail,
    get_checkout_form_context,
    create_checkout,
    update_checkout,
    delete_checkout,
    list_checkins,
    get_checkin_detail,
    get_checkin_form_context,
    create_checkin,
    update_checkin,
    delete_checkin,
    list_projects,
    get_project_form_context,
    create_project,
    update_project,
    get_project_for_edit,
    delete_project,
    list_productions,
    create_production,
    update_production,
    get_production_for_edit,
    delete_production,
    get_calendar_events,
    get_checkout_stats,
)
from services.auth import request_magic_link, verify_magic_link
from services.newsletter import (
    list_newsletter_subscribers,
    remove_newsletter_subscriber_by_id,
)
"""

init_file_content = ""

for i, (comment, filename, func_name) in enumerate(sections):
    end_comment = sections[i+1][0] if i+1 < len(sections) else None
    block_lines = get_section(comment, end_comment)
    
    # Write the subfile
    with open(f"routes/admin/{filename}", "w") as f:
        f.write(imports + "\n\n")
        f.write(f"def {func_name}(app):\n")
        f.writelines(block_lines)

    # Append to init_file_content
    init_file_content += f"from .{filename[:-3]} import {func_name}\n"

init_file_content += "\n\ndef init_admin_routes(app):\n"
for _, _, func_name in sections:
    init_file_content += f"    {func_name}(app)\n"

with open("routes/admin/__init__.py", "w") as f:
    f.write(init_file_content)

print("routes/admin module generated successfully.")
