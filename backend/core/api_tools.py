import requests
from typing import Dict, Any, Optional

def http_request(method: str, url: str, headers: Optional[Dict] = None, json_body: Optional[Dict] = None):
    """
    Execute HTTP request safely and return a simplified response for AI.
    """
    try:
        response = requests.request(
            method=method.upper(),
            url=url,
            headers=headers or {"Content-Type": "application/json"},
            json=json_body,
            timeout=10
        )
        
        # Calculate elapsed time in seconds (float)
        elapsed = response.elapsed.total_seconds()
        
        # Try to parse JSON response for better readability by AI
        content = response.text[:2000]
        try:
            content = response.json()
        except ValueError:
            pass

        return {
            "status_code": response.status_code,
            "content": content,
            "elapsed": elapsed,
            "headers": dict(response.headers)
        }
    except Exception as e:
        return {"error": str(e), "status_code": -1}
