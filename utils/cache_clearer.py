import os
import requests
from dotenv import load_dotenv

def clear_cache():
    """
    Clear the cache by sending a POST request to the cache endpoint.
    Uses the ADMIN_CACHE_TOKEN environment variable.
    """
    load_dotenv() 

    admin_token = os.getenv('ADMIN_CACHE_TOKEN')
    if not admin_token:
        raise ValueError("ADMIN_CACHE_TOKEN is not defined.")

    url = "https://www.bellevitesse.com/admin/cache/clear"
    headers = {"X-Admin-Token": admin_token}

    try:
        response = requests.post(url, headers=headers, timeout=10)
        if response.ok:
            print("Cache successfully cleared.")
            return True
        else:
            print(f"Error {response.status_code}: {response.text}")
            return False
    except requests.RequestException as e:
        print(f"Request failed: {e}")
        return False
    
if __name__ == "__main__":
    clear_cache()
