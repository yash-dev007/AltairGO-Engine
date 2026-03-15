"""
test_auth.py — Tests for /auth/* endpoints.
Covers: register, login, /me, token validation, edge cases.
"""

import pytest


class TestRegister:
    """POST /auth/register"""

    def test_register_success(self, client):
        res = client.post("/auth/register", json={
            "name": "Yash Dev",
            "email": "yash@altairgo.com",
            "password": "StrongPass123!"
        })
        assert res.status_code == 201
        data = res.get_json()
        assert "token" in data
        assert data["user"]["email"] == "yash@altairgo.com"
        assert "password" not in data["user"]
        assert "password_hash" not in data["user"]

    def test_register_duplicate_email(self, client, registered_user):
        res = client.post("/auth/register", json={
            "name": "Another User",
            "email": registered_user["payload"]["email"],
            "password": "AnotherPass123!"
        })
        assert res.status_code == 409
        assert "already" in res.get_json().get("error", "").lower()

    def test_register_missing_email(self, client):
        res = client.post("/auth/register", json={
            "name": "No Email",
            "password": "Pass123!"
        })
        assert res.status_code == 400

    def test_register_missing_password(self, client):
        res = client.post("/auth/register", json={
            "name": "No Pass",
            "email": "nopass@altairgo.com"
        })
        assert res.status_code == 400

    def test_register_invalid_email_format(self, client):
        res = client.post("/auth/register", json={
            "name": "Bad Email",
            "email": "not-an-email",
            "password": "Pass123!"
        })
        assert res.status_code == 400

    def test_register_empty_body(self, client):
        res = client.post("/auth/register", json={})
        assert res.status_code == 400

    def test_register_password_not_returned(self, client):
        res = client.post("/auth/register", json={
            "name": "Safe User",
            "email": "safe@altairgo.com",
            "password": "SecretPass999!"
        })
        body = res.get_data(as_text=True)
        assert "SecretPass999!" not in body
        assert "password_hash" not in body


class TestLogin:
    """POST /auth/login"""

    def test_login_success(self, client, registered_user):
        res = client.post("/auth/login", json={
            "email": registered_user["payload"]["email"],
            "password": registered_user["payload"]["password"]
        })
        assert res.status_code == 200
        data = res.get_json()
        assert "token" in data
        assert len(data["token"]) > 20

    def test_login_wrong_password(self, client, registered_user):
        res = client.post("/auth/login", json={
            "email": registered_user["payload"]["email"],
            "password": "WrongPassword!"
        })
        assert res.status_code == 401

    def test_login_nonexistent_user(self, client):
        res = client.post("/auth/login", json={
            "email": "ghost@altairgo.com",
            "password": "NoSuchUser123!"
        })
        assert res.status_code == 401

    def test_login_missing_fields(self, client):
        res = client.post("/auth/login", json={"email": "only@email.com"})
        assert res.status_code == 400

    def test_login_case_insensitive_email(self, client, registered_user):
        """Email should be case-insensitive."""
        email = registered_user["payload"]["email"].upper()
        res = client.post("/auth/login", json={
            "email": email,
            "password": registered_user["payload"]["password"]
        })
        assert res.status_code == 200


class TestMe:
    """GET /auth/me"""

    def test_me_with_valid_token(self, client, registered_user, auth_headers):
        res = client.get("/auth/me", headers=auth_headers)
        assert res.status_code == 200
        data = res.get_json()
        assert data["email"] == registered_user["payload"]["email"]
        assert "password" not in data
        assert "password_hash" not in data

    def test_me_without_token(self, client):
        res = client.get("/auth/me")
        assert res.status_code == 401

    def test_me_with_invalid_token(self, client):
        res = client.get("/auth/me", headers={
            "Authorization": "Bearer totally.invalid.token"
        })
        assert res.status_code == 422

    def test_me_with_malformed_header(self, client):
        res = client.get("/auth/me", headers={
            "Authorization": "NotBearer sometoken"
        })
        assert res.status_code in [401, 422]
