import sys
from app import create_app

try:
    print("Initializing Flask app...")
    app = create_app()
    client = app.test_client()
    print("Flask app initialized successfully. Testing routes...")
    
    for path in ['/', '/admin/login', '/admin/projects', '/en/', '/fr/']:
        try:
            res = client.get(path)
            print(f"GET {path:20} -> {res.status_code}")
            if res.status_code == 404:
                print(f"  Response body: {res.data[:200]}")
        except Exception as e_route:
            print(f"GET {path:20} -> CRASHED: {e_route}")
            
except Exception as e:
    print(f"CRITICAL: Failed to create app: {e}")
    import traceback
    traceback.print_exc()
