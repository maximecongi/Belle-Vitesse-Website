from app import create_app
app = create_app()
for rule in sorted(app.url_map.iter_rules(), key=lambda r: r.rule):
    print(f"{rule.endpoint:35} -> {rule.rule}")
