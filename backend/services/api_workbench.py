"""
API Workbench Service - Lightweight Postman-like API Testing

Provides:
- Collection management (CRUD)
- Request execution with httpx
- Variable/Environment management
- Assertion execution
- Chain request support
"""

import logging
import os
import json
import uuid
import time
import asyncio
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field, asdict
from pathlib import Path

logger = logging.getLogger(__name__)

import httpx

# Data directory for storing collections
DATA_DIR = Path(__file__).parent.parent / "data" / "api_workbench"
DATA_DIR.mkdir(parents=True, exist_ok=True)

COLLECTIONS_FILE = DATA_DIR / "collections.json"
ENVIRONMENTS_FILE = DATA_DIR / "environments.json"


@dataclass
class RequestItem:
    """Single API request definition"""
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    name: str = "New Request"
    method: str = "GET"
    url: str = ""
    headers: Dict[str, str] = field(default_factory=dict)
    params: Dict[str, str] = field(default_factory=dict)
    body: str = ""
    body_type: str = "json"  # json, form, raw
    assertions: List[Dict[str, Any]] = field(default_factory=list)
    # Assertion format: {"type": "status", "operator": "equals", "expected": 200}
    # Types: status, json_path, header, response_time
    extract_variables: List[Dict[str, str]] = field(default_factory=list)
    # Extract format: {"name": "token", "source": "json", "path": "$.data.token"}


@dataclass
class Collection:
    """Collection of API requests"""
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    name: str = "New Collection"
    description: str = ""
    requests: List[RequestItem] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class Environment:
    """Environment with variables"""
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    name: str = "Default"
    variables: Dict[str, str] = field(default_factory=dict)
    is_active: bool = False


@dataclass
class RequestResult:
    """Result of executing a request"""
    request_id: str
    request_name: str
    success: bool = False
    status_code: int = 0
    response_time_ms: float = 0
    response_headers: Dict[str, str] = field(default_factory=dict)
    response_body: str = ""
    assertions_passed: int = 0
    assertions_failed: int = 0
    assertion_details: List[Dict[str, Any]] = field(default_factory=list)
    extracted_variables: Dict[str, str] = field(default_factory=dict)
    error: Optional[str] = None


class ApiWorkbenchService:
    """Main service for API Workbench functionality"""

    def __init__(self):
        self.collections: Dict[str, Collection] = {}
        self.environments: Dict[str, Environment] = {}
        self.runtime_variables: Dict[str, str] = {}
        self._load_data()

    def _load_data(self):
        """Load collections and environments from disk"""
        # Load collections
        if COLLECTIONS_FILE.exists():
            try:
                with open(COLLECTIONS_FILE, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    for coll_data in data:
                        requests = [RequestItem(**req) for req in coll_data.pop('requests', [])]
                        coll = Collection(**coll_data, requests=requests)
                        self.collections[coll.id] = coll
            except Exception as e:
                logger.error(f"Error loading collections: {e}")

        # Load environments
        if ENVIRONMENTS_FILE.exists():
            try:
                with open(ENVIRONMENTS_FILE, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    for env_data in data:
                        env = Environment(**env_data)
                        self.environments[env.id] = env
            except Exception as e:
                logger.error(f"Error loading environments: {e}")

        # Create default environment if none exists
        if not self.environments:
            default_env = Environment(name="Default", is_active=True)
            self.environments[default_env.id] = default_env
            self._save_environments()

    def _save_collections(self):
        """Save collections to disk"""
        data = []
        for coll in self.collections.values():
            coll_dict = asdict(coll)
            data.append(coll_dict)
        with open(COLLECTIONS_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def _save_environments(self):
        """Save environments to disk"""
        data = [asdict(env) for env in self.environments.values()]
        with open(ENVIRONMENTS_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    # ==================== Collection Management ====================

    def list_collections(self) -> List[Dict]:
        """List all collections with summary info"""
        return [
            {
                "id": c.id,
                "name": c.name,
                "description": c.description,
                "request_count": len(c.requests),
                "updated_at": c.updated_at
            }
            for c in self.collections.values()
        ]

    def get_collection(self, collection_id: str) -> Optional[Dict]:
        """Get full collection details"""
        coll = self.collections.get(collection_id)
        if coll:
            return asdict(coll)
        return None

    def create_collection(self, name: str, description: str = "") -> Dict:
        """Create a new collection"""
        coll = Collection(name=name, description=description)
        self.collections[coll.id] = coll
        self._save_collections()
        return asdict(coll)

    def update_collection(self, collection_id: str, data: Dict) -> Optional[Dict]:
        """Update collection properties"""
        coll = self.collections.get(collection_id)
        if not coll:
            return None

        if 'name' in data:
            coll.name = data['name']
        if 'description' in data:
            coll.description = data['description']
        coll.updated_at = datetime.now().isoformat()

        self._save_collections()
        return asdict(coll)

    def delete_collection(self, collection_id: str) -> bool:
        """Delete a collection"""
        if collection_id in self.collections:
            del self.collections[collection_id]
            self._save_collections()
            return True
        return False

    # ==================== Request Management ====================

    def add_request(self, collection_id: str, request_data: Dict) -> Optional[Dict]:
        """Add a request to a collection"""
        coll = self.collections.get(collection_id)
        if not coll:
            return None

        req = RequestItem(
            name=request_data.get('name', 'New Request'),
            method=request_data.get('method', 'GET'),
            url=request_data.get('url', ''),
            headers=request_data.get('headers', {}),
            params=request_data.get('params', {}),
            body=request_data.get('body', ''),
            body_type=request_data.get('body_type', 'json'),
            assertions=request_data.get('assertions', []),
            extract_variables=request_data.get('extract_variables', [])
        )
        coll.requests.append(req)
        coll.updated_at = datetime.now().isoformat()
        self._save_collections()
        return asdict(req)

    def update_request(self, collection_id: str, request_id: str, request_data: Dict) -> Optional[Dict]:
        """Update a request in a collection"""
        coll = self.collections.get(collection_id)
        if not coll:
            return None

        for req in coll.requests:
            if req.id == request_id:
                if 'name' in request_data:
                    req.name = request_data['name']
                if 'method' in request_data:
                    req.method = request_data['method']
                if 'url' in request_data:
                    req.url = request_data['url']
                if 'headers' in request_data:
                    req.headers = request_data['headers']
                if 'params' in request_data:
                    req.params = request_data['params']
                if 'body' in request_data:
                    req.body = request_data['body']
                if 'body_type' in request_data:
                    req.body_type = request_data['body_type']
                if 'assertions' in request_data:
                    req.assertions = request_data['assertions']
                if 'extract_variables' in request_data:
                    req.extract_variables = request_data['extract_variables']

                coll.updated_at = datetime.now().isoformat()
                self._save_collections()
                return asdict(req)
        return None

    def delete_request(self, collection_id: str, request_id: str) -> bool:
        """Delete a request from a collection"""
        coll = self.collections.get(collection_id)
        if not coll:
            return False

        original_len = len(coll.requests)
        coll.requests = [r for r in coll.requests if r.id != request_id]
        if len(coll.requests) < original_len:
            coll.updated_at = datetime.now().isoformat()
            self._save_collections()
            return True
        return False

    # ==================== Environment Management ====================

    def list_environments(self) -> List[Dict]:
        """List all environments"""
        return [asdict(env) for env in self.environments.values()]

    def get_active_environment(self) -> Optional[Dict]:
        """Get currently active environment"""
        for env in self.environments.values():
            if env.is_active:
                return asdict(env)
        return None

    def create_environment(self, name: str, variables: Dict[str, str] = None) -> Dict:
        """Create a new environment"""
        env = Environment(name=name, variables=variables or {})
        self.environments[env.id] = env
        self._save_environments()
        return asdict(env)

    def update_environment(self, env_id: str, data: Dict) -> Optional[Dict]:
        """Update environment"""
        env = self.environments.get(env_id)
        if not env:
            return None

        if 'name' in data:
            env.name = data['name']
        if 'variables' in data:
            env.variables = data['variables']

        self._save_environments()
        return asdict(env)

    def set_active_environment(self, env_id: str) -> bool:
        """Set an environment as active"""
        if env_id not in self.environments:
            return False

        for env in self.environments.values():
            env.is_active = (env.id == env_id)
        self._save_environments()
        return True

    def delete_environment(self, env_id: str) -> bool:
        """Delete an environment"""
        if env_id in self.environments:
            del self.environments[env_id]
            self._save_environments()
            return True
        return False

    # ==================== Request Execution ====================

    def _substitute_variables(self, text: str, extra_vars: Dict[str, str] = None) -> str:
        """Replace {{variable}} placeholders with actual values"""
        if not text:
            return text

        # Get active environment variables
        env_vars = {}
        for env in self.environments.values():
            if env.is_active:
                env_vars = env.variables.copy()
                break

        # Merge with runtime variables and extra vars
        all_vars = {**env_vars, **self.runtime_variables, **(extra_vars or {})}

        # Replace {{var}} patterns
        for key, value in all_vars.items():
            text = text.replace(f"{{{{{key}}}}}", str(value))

        return text

    def _extract_json_path(self, data: Any, path: str) -> Any:
        """Simple JSON path extraction (supports $.key.subkey format)"""
        if not path.startswith('$.'):
            return None

        keys = path[2:].split('.')
        current = data
        for key in keys:
            if isinstance(current, dict) and key in current:
                current = current[key]
            elif isinstance(current, list):
                try:
                    idx = int(key)
                    current = current[idx]
                except (ValueError, IndexError):
                    return None
            else:
                return None
        return current

    def _evaluate_assertion(self, assertion: Dict, result: RequestResult, response_data: Any) -> Dict:
        """Evaluate a single assertion and return result"""
        assertion_type = assertion.get('type', 'status')
        operator = assertion.get('operator', 'equals')
        expected = assertion.get('expected')
        path = assertion.get('path', '')

        actual = None
        passed = False
        message = ""

        try:
            if assertion_type == 'status':
                actual = result.status_code
            elif assertion_type == 'response_time':
                actual = result.response_time_ms
            elif assertion_type == 'header':
                actual = result.response_headers.get(path, '')
            elif assertion_type == 'json_path':
                actual = self._extract_json_path(response_data, path)
            elif assertion_type == 'body_contains':
                actual = expected in result.response_body
                expected = True

            # Evaluate based on operator
            if operator == 'equals':
                passed = actual == expected
            elif operator == 'not_equals':
                passed = actual != expected
            elif operator == 'contains':
                passed = str(expected) in str(actual)
            elif operator == 'greater_than':
                passed = float(actual) > float(expected)
            elif operator == 'less_than':
                passed = float(actual) < float(expected)
            elif operator == 'exists':
                passed = actual is not None

            message = f"Expected {expected}, got {actual}" if not passed else "Passed"

        except Exception as e:
            message = f"Assertion error: {str(e)}"
            passed = False

        return {
            "type": assertion_type,
            "path": path,
            "operator": operator,
            "expected": expected,
            "actual": actual,
            "passed": passed,
            "message": message
        }

    async def execute_request(self, request_data: Dict, extra_vars: Dict[str, str] = None) -> Dict:
        """Execute a single API request"""
        # Substitute variables
        url = self._substitute_variables(request_data.get('url', ''), extra_vars)
        method = request_data.get('method', 'GET').upper()

        headers = {}
        for k, v in request_data.get('headers', {}).items():
            headers[self._substitute_variables(k, extra_vars)] = self._substitute_variables(v, extra_vars)

        params = {}
        for k, v in request_data.get('params', {}).items():
            params[self._substitute_variables(k, extra_vars)] = self._substitute_variables(v, extra_vars)

        body = self._substitute_variables(request_data.get('body', ''), extra_vars)
        body_type = request_data.get('body_type', 'json')

        result = RequestResult(
            request_id=request_data.get('id', 'adhoc'),
            request_name=request_data.get('name', 'Ad-hoc Request')
        )

        start_time = time.time()

        try:
            async with httpx.AsyncClient(timeout=30.0, verify=False) as client:
                # Prepare request kwargs
                kwargs = {"headers": headers, "params": params}

                if method in ['POST', 'PUT', 'PATCH'] and body:
                    if body_type == 'json':
                        try:
                            kwargs['json'] = json.loads(body)
                        except json.JSONDecodeError:
                            kwargs['content'] = body
                    elif body_type == 'form':
                        kwargs['data'] = json.loads(body) if body else {}
                    else:
                        kwargs['content'] = body

                response = await client.request(method, url, **kwargs)

                result.status_code = response.status_code
                result.response_time_ms = (time.time() - start_time) * 1000
                result.response_headers = dict(response.headers)
                result.response_body = response.text

                # Try to parse as JSON for assertions
                response_data = None
                try:
                    response_data = response.json()
                except Exception:
                    pass

                # Evaluate assertions
                assertions = request_data.get('assertions', [])
                for assertion in assertions:
                    assertion_result = self._evaluate_assertion(assertion, result, response_data)
                    result.assertion_details.append(assertion_result)
                    if assertion_result['passed']:
                        result.assertions_passed += 1
                    else:
                        result.assertions_failed += 1

                # Extract variables for chaining
                for extract in request_data.get('extract_variables', []):
                    var_name = extract.get('name')
                    source = extract.get('source', 'json')
                    path = extract.get('path', '')

                    if source == 'json' and response_data:
                        value = self._extract_json_path(response_data, path)
                        if value is not None:
                            self.runtime_variables[var_name] = str(value)
                            result.extracted_variables[var_name] = str(value)
                    elif source == 'header':
                        value = result.response_headers.get(path)
                        if value:
                            self.runtime_variables[var_name] = value
                            result.extracted_variables[var_name] = value

                result.success = result.assertions_failed == 0

        except httpx.TimeoutException:
            result.error = "Request timed out"
            result.success = False
        except httpx.RequestError as e:
            result.error = f"Request failed: {str(e)}"
            result.success = False
        except Exception as e:
            result.error = f"Unexpected error: {str(e)}"
            result.success = False

        return asdict(result)

    async def run_collection(self, collection_id: str, stop_on_failure: bool = False) -> Dict:
        """Run all requests in a collection sequentially"""
        coll = self.collections.get(collection_id)
        if not coll:
            return {"error": "Collection not found", "results": []}

        # Clear runtime variables before run
        self.runtime_variables.clear()

        results = []
        total_passed = 0
        total_failed = 0
        start_time = time.time()

        for req in coll.requests:
            req_dict = asdict(req)
            result = await self.execute_request(req_dict)
            results.append(result)

            if result.get('success'):
                total_passed += 1
            else:
                total_failed += 1
                if stop_on_failure:
                    break

        total_time = (time.time() - start_time) * 1000

        return {
            "collection_id": collection_id,
            "collection_name": coll.name,
            "total_requests": len(coll.requests),
            "executed": len(results),
            "passed": total_passed,
            "failed": total_failed,
            "total_time_ms": total_time,
            "results": results
        }


# Singleton instance
_service_instance: Optional[ApiWorkbenchService] = None


def get_api_workbench_service() -> ApiWorkbenchService:
    """Get or create the singleton service instance"""
    global _service_instance
    if _service_instance is None:
        _service_instance = ApiWorkbenchService()
    return _service_instance
