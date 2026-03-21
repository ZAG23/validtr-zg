import pytest
import subprocess
import time
import httpx
import jwt
import json
from datetime import datetime, timedelta
import os
import signal
import sys
from pathlib import Path

@pytest.fixture(scope="session")
def fastapi_server():
    """Start FastAPI server for testing"""
    # Find the main FastAPI application file
    workspace_path = Path("/workspace/output")
    
    # Common FastAPI entry point names
    possible_files = ["main.py", "app.py", "server.py", "api.py"]
    app_file = None
    
    for filename in possible_files:
        if (workspace_path / filename).exists():
            app_file = workspace_path / filename
            break
    
    if not app_file:
        pytest.fail("No FastAPI application file found in /workspace/output/")
    
    # Start the server
    port = 8000
    process = subprocess.Popen([
        sys.executable, "-m", "uvicorn", 
        f"{app_file.stem}:app", 
        "--host", "0.0.0.0", 
        "--port", str(port)
    ], cwd=workspace_path)
    
    # Wait for server to start
    max_retries = 30
    for _ in range(max_retries):
        try:
            response = httpx.get(f"http://localhost:{port}/docs")
            if response.status_code == 200:
                break
        except:
            pass
        time.sleep(1)
    else:
        process.terminate()
        pytest.fail("FastAPI server failed to start")
    
    yield f"http://localhost:{port}"
    
    # Cleanup
    process.terminate()
    process.wait()

@pytest.fixture
def client(fastapi_server):
    """HTTP client for testing"""
    return httpx.Client(base_url=fastapi_server)

def test_fastapi_server_starts(fastapi_server):
    """Test that FastAPI server starts and is accessible"""
    response = httpx.get(f"{fastapi_server}/docs")
    assert response.status_code == 200

def test_openapi_docs_accessible(client):
    """Test that OpenAPI documentation is accessible at /docs"""
    response = client.get("/docs")
    assert response.status_code == 200
    assert "swagger" in response.text.lower() or "openapi" in response.text.lower()

def test_login_endpoint_exists(client):
    """Test that login endpoint exists"""
    response = client.post("/login", json={"username": "test", "password": "test"})
    # Should not return 404 (endpoint exists)
    assert response.status_code != 404

def test_login_with_valid_credentials(client):
    """Test login with valid credentials returns 200"""
    # Try common test credentials
    test_credentials = [
        {"username": "admin", "password": "admin"},
        {"username": "test", "password": "test"},
        {"username": "user", "password": "password"},
        {"email": "test@example.com", "password": "test"},
        {"email": "admin@example.com", "password": "admin"}
    ]
    
    success = False
    for creds in test_credentials:
        response = client.post("/login", json=creds)
        if response.status_code == 200:
            success = True
            break
    
    # If no hardcoded credentials work, check if registration is available
    if not success:
        # Try to register a user first
        register_response = client.post("/register", json={
            "username": "testuser", 
            "password": "testpass",
            "email": "test@example.com"
        })
        
        if register_response.status_code in [200, 201]:
            # Now try to login with registered credentials
            login_response = client.post("/login", json={
                "username": "testuser", 
                "password": "testpass"
            })
            assert login_response.status_code == 200
            success = True
    
    assert success, "Could not authenticate with any test credentials"

def test_login_with_invalid_credentials(client):
    """Test login with invalid credentials returns 401"""
    response = client.post("/login", json={
        "username": "invalid_user", 
        "password": "wrong_password"
    })
    assert response.status_code == 401

def test_login_response_contains_jwt_token(client):
    """Test that login response contains a JWT token"""
    # First try to get a successful login
    test_credentials = [
        {"username": "admin", "password": "admin"},
        {"username": "test", "password": "test"},
        {"username": "user", "password": "password"}
    ]
    
    token = None
    for creds in test_credentials:
        response = client.post("/login", json=creds)
        if response.status_code == 200:
            data = response.json()
            # Common token field names
            token_fields = ["access_token", "token", "jwt", "auth_token"]
            for field in token_fields:
                if field in data:
                    token = data[field]
                    break
            if token:
                break
    
    # If no hardcoded credentials work, try registration
    if not token:
        register_response = client.post("/register", json={
            "username": "testuser2", 
            "password": "testpass",
            "email": "test2@example.com"
        })
        
        if register_response.status_code in [200, 201]:
            login_response = client.post("/login", json={
                "username": "testuser2", 
                "password": "testpass"
            })
            if login_response.status_code == 200:
                data = login_response.json()
                token_fields = ["access_token", "token", "jwt", "auth_token"]
                for field in token_fields:
                    if field in data:
                        token = data[field]
                        break
    
    assert token is not None, "No JWT token found in login response"
    
    # Verify it's a valid JWT structure (3 parts separated by dots)
    parts = token.split('.')
    assert len(parts) == 3, "Token is not a valid JWT format"

def test_jwt_token_contains_required_claims(client):
    """Test that JWT token contains required claims (user_id, exp)"""
    # Get a valid token first
    token = get_valid_token(client)
    
    # Decode without verification to check claims
    try:
        # Try common secret keys for testing
        secrets = ["secret", "your-secret-key", "jwt-secret", "test-secret"]
        decoded = None
        
        for secret in secrets:
            try:
                decoded = jwt.decode(token, secret, algorithms=["HS256"])
                break
            except:
                continue
        
        if not decoded:
            # If we can't decode with common secrets, decode without verification
            decoded = jwt.decode(token, options={"verify_signature": False})
        
        # Check for required claims
        assert "exp" in decoded, "JWT token missing 'exp' claim"
        
        # Check for user identifier (various possible field names)
        user_fields = ["user_id", "sub", "id", "username", "email"]
        has_user_field = any(field in decoded for field in user_fields)
        assert has_user_field, "JWT token missing user identifier claim"
        
    except Exception as e:
        pytest.fail(f"Could not decode JWT token: {e}")

def test_protected_endpoint_without_auth_returns_401(client):
    """Test that protected endpoints return 401 without authentication"""
    # Common protected endpoint patterns
    protected_endpoints = [
        "/protected",
        "/user/profile", 
        "/users/me",
        "/dashboard",
        "/admin",
        "/api/protected"
    ]
    
    found_protected = False
    for endpoint in protected_endpoints:
        response = client.get(endpoint)
        if response.status_code == 401:
            found_protected = True
            break
        elif response.status_code != 404:
            # Endpoint exists but might not be protected, check if it requires auth
            if "unauthorized" in response.text.lower() or "authentication" in response.text.lower():
                found_protected = True
                break
    
    # If no common endpoints found, check OpenAPI spec for protected endpoints
    if not found_protected:
        docs_response = client.get("/openapi.json")
        if docs_response.status_code == 200:
            openapi_spec = docs_response.json()
            paths = openapi_spec.get("paths", {})
            
            for path, methods in paths.items():
                for method, spec in methods.items():
                    if "security" in spec or "Authorization" in str(spec):
                        test_response = client.request(method.upper(), path)
                        if test_response.status_code == 401:
                            found_protected = True
                            break
                if found_protected:
                    break
    
    assert found_protected, "No protected endpoints found that return 401 without auth"

def test_protected_endpoint_with_valid_token_returns_200(client):
    """Test that protected endpoints return 200 with valid JWT token"""
    token = get_valid_token(client)
    headers = {"Authorization": f"Bearer {token}"}
    
    # Try common protected endpoints
    protected_endpoints = [
        "/protected",
        "/user/profile", 
        "/users/me",
        "/dashboard"
    ]
    
    success = False
    for endpoint in protected_endpoints:
        response = client.get(endpoint, headers=headers)
        if response.status_code == 200:
            success = True
            break
        elif response.status_code != 404:
            # Endpoint exists, might be protected
            if response.status_code != 401:
                success = True
                break
    
    assert success, "No protected endpoint accessible with valid token"

def test_expired_jwt_token_rejected(client):
    """Test that expired JWT tokens are rejected with 401 status"""
    # This test assumes we can create an expired token or wait for expiration
    # For testing purposes, we'll try to create a token with past expiration
    
    # First get a valid token to understand the structure
    valid_token = get_valid_token(client)
    
    # Try to create an expired token (this might not work if we don't know the secret)
    try:
        # Common test secrets
        secrets = ["secret", "your-secret-key", "jwt-secret", "test-secret"]
        
        for secret in secrets:
            try:
                # Decode the valid token to get its structure
                decoded = jwt.decode(valid_token, secret, algorithms=["HS256"])
                
                # Create an expired token
                expired_payload = decoded.copy()
                expired_payload["exp"] = datetime.utcnow() - timedelta(hours=1)
                
                expired_token = jwt.encode(expired_payload, secret, algorithm="HS256")
                
                # Test with expired token
                headers = {"Authorization": f"Bearer {expired_token}"}
                response = client.get("/protected", headers=headers)
                
                # Should return 401 for expired token
                assert response.status_code == 401
                return
                
            except jwt.InvalidTokenError:
                continue
    
    except Exception:
        # If we can't create expired tokens, skip this test
        pytest.skip("Cannot create expired token for testing")

def test_application_has_protected_endpoint(client):
    """Test that application has at least one protected endpoint"""
    # Check OpenAPI spec for endpoints with security requirements
    docs_response = client.get("/openapi.json")
    
    if docs_response.status_code == 200:
        openapi_spec = docs_response.json()
        paths = openapi_spec.get("paths", {})
        
        has_protected = False
        for path, methods in paths.items():
            for method, spec in methods.items():
                if "security" in spec:
                    has_protected = True
                    break
            if has_protected:
                break
        
        if has_protected:
            return
    
    # Fallback: test common protected endpoints
    protected_endpoints = [
        "/protected", "/user/profile", "/users/me", 
        "/dashboard", "/admin", "/api/protected"
    ]
    
    for endpoint in protected_endpoints:
        response = client.get(endpoint)
        if response.status_code == 401:
            return  # Found a protected endpoint
    
    pytest.fail("No protected endpoints found in the application")

def get_valid_token(client):
    """Helper function to get a valid JWT token"""
    # Try common test credentials
    test_credentials = [
        {"username": "admin", "password": "admin"},
        {"username": "test", "password": "test"},
        {"username": "user", "password": "password"}
    ]
    
    for creds in test_credentials:
        response = client.post("/login", json=creds)
        if response.status_code == 200:
            data = response.json()
            token_fields = ["access_token", "token", "jwt", "auth_token"]
            for field in token_fields:
                if field in data:
                    return data[field]
    
    # Try registration if login fails
    register_response = client.post("/register", json={
        "username": "testuser3", 
        "password": "testpass",
        "email": "test3@example.com"
    })
    
    if register_response.status_code in [200, 201]:
        login_response = client.post("/login", json={
            "username": "testuser3", 
            "password": "testpass"
        })
        if login_response.status_code == 200:
            data = login_response.json()
            token_fields = ["access_token", "token", "jwt", "auth_token"]
            for field in token_fields:
                if field in data:
                    return data[field]
    
    pytest.fail("Could not obtain valid JWT token for testing")

def test_registration_endpoint_works(client):
    """Test user registration functionality"""
    response = client.post("/register", json={
        "username": "newuser",
        "password": "newpass",
        "email": "newuser@example.com"
    })
    
    # Registration should return 200, 201, or redirect to login
    assert response.status_code in [200, 201, 302]

def test_invalid_jwt_token_rejected(client):
    """Test that invalid JWT tokens are rejected"""
    invalid_tokens = [
        "invalid.token.here",
        "Bearer invalid",
        "not-a-jwt-token",
        ""
    ]
    
    for invalid_token in invalid_tokens:
        headers = {"Authorization": f"Bearer {invalid_token}"}
        response = client.get("/protected", headers=headers)
        # Should return 401 for invalid tokens (if endpoint exists)
        if response.status_code != 404:
            assert response.status_code == 401

def test_missing_authorization_header(client):
    """Test endpoints handle missing Authorization header properly"""
    response = client.get("/protected")
    # Should return 401 for missing auth header (if endpoint exists)
    if response.status_code != 404:
        assert response.status_code == 401