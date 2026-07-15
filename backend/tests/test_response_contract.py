import asyncio

import httpx

from app.main import app


async def _request(method: str, path: str, **kwargs) -> httpx.Response:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        return await client.request(method, path, **kwargs)


def test_http_exception_uses_api_response_contract() -> None:
    response = asyncio.run(
        _request(
            "POST",
            "/api/auth/login",
            json={"username": "invalid", "password": "invalid"},
        )
    )

    assert response.status_code == 401
    assert response.json() == {
        "code": 401,
        "message": "用户名或密码错误",
        "data": None,
    }


def test_request_validation_uses_api_response_contract() -> None:
    response = asyncio.run(_request("POST", "/api/auth/login", json={}))

    assert response.status_code == 422
    assert response.json() == {
        "code": 422,
        "message": "request validation failed",
        "data": None,
    }


def test_openapi_uses_error_response_for_validation_errors() -> None:
    operation = app.openapi()["paths"]["/api/auth/login"]["post"]
    schema = operation["responses"]["422"]["content"]["application/json"]["schema"]

    assert schema == {"$ref": "#/components/schemas/ErrorResponse"}


def test_openapi_describes_batch_evidence_response_fields() -> None:
    schemas = app.openapi()["components"]["schemas"]

    assert set(schemas["EvidenceBatchResult"]["required"]) == {
        "batch_id",
        "success_count",
        "receipt_ids",
        "evidenced",
        "newly_evidenced",
    }


def test_openapi_describes_merkle_contract_and_public_route() -> None:
    openapi = app.openapi()
    schemas = openapi["components"]["schemas"]

    assert {
        "batch_id",
        "root_id",
        "root_no",
        "merkle_root",
        "leaf_order_rule",
        "odd_leaf_rule",
        "current_root_hash",
        "leaf_count",
    } <= set(schemas["MerkleRootResult"]["required"])
    assert {
        "certificate_no",
        "certificate_hash",
        "leaf_index",
        "leaf_order_rule",
        "odd_leaf_rule",
        "root_id",
        "root_no",
        "merkle_root",
        "merkle_proof",
        "proof",
        "proof_valid",
        "verified",
    } <= set(schemas["MerkleProofResult"]["required"])
    assert "/api/public/verify/{certificate_no}/merkle-proof" in openapi["paths"]
