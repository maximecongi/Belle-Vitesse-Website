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

    # We only keep the relevant production URLs to avoid connection errors in logs
    urls = [
        "https://bellevitesse.com/admin/cache/clear",
        "http://127.0.0.1:5001/admin/cache/clear",  # Port used by Gunicorn in Docker
    ]

    headers = {"X-Admin-Token": admin_token}

    success = True

    for url in urls:
        try:
            response = requests.post(url, headers=headers, timeout=10)
            if response.ok:
                print(f"✅ Cache successfully cleared for {url}")
            else:
                print(
                    f"❌ Error {response.status_code} for {url}: {response.text}")
                success = False
        except requests.RequestException as e:
            # We don't fail the whole sync if cache clearing fails, but we log it
            print(f"⚠️ Cache clear skipped/failed for {url}: {e}")
            # Do not set success = False here if we want the sync to be considered a success
            # even if one cache URL is unreachable (e.g. local dev vs prod)

    return success


if __name__ == "__main__":
    clear_cache()
