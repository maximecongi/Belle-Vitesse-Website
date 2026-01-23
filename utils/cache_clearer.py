import os
import requests
from dotenv import load_dotenv

def clear_cache():
    """
    Clear the cache by sending POST requests to all cache endpoints.
    Uses the ADMIN_CACHE_TOKEN environment variable.
    """
    load_dotenv()

    admin_token = os.getenv('ADMIN_CACHE_TOKEN')
    if not admin_token:
        raise ValueError("ADMIN_CACHE_TOKEN is not defined.")

    urls = [
        "https://www.bellevitesse.com/admin/cache/clear",
        "http://127.0.0.1:5000/admin/cache/clear",
    ]

    headers = {"X-Admin-Token": admin_token}

    success = True

    for url in urls:
        try:
            response = requests.post(url, headers=headers, timeout=10)
            if response.ok:
                print(f"✅ Cache successfully cleared for {url}")
            else:
                print(f"❌ Error {response.status_code} for {url}: {response.text}")
                success = False
        except requests.RequestException as e:
            print(f"❌ Request failed for {url}: {e}")
            success = False

    return success


if __name__ == "__main__":
    clear_cache()
