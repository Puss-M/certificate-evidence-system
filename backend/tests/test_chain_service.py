"""
测试链接入服务测试（P2加分项）。

分两部分：
1. 没配置/配置不全时，chain_service的所有函数都应该安全跳过（返回None，
   不抛异常）——这是降级策略要求的核心行为，必须测到。
2. 配置齐全、链能连上时，真的能写入、读取——这部分用web3.py自带的
   EthereumTesterProvider（纯Python内存里模拟一条链，不需要真的起
   Ganache/Hardhat进程），通过monkeypatch替换掉chain_service里
   Web3.HTTPProvider的连接方式，来验证真实的合约调用逻辑没写错。
"""
import asyncio
import json
from pathlib import Path

import httpx
import pytest

from app.core.config import settings
from app.main import app
from app.models.credential_root import CredentialRoot
from app.models.student import Student
from app.services import chain_service


ARTIFACT_PATH = (
    Path(__file__).resolve().parents[2] / "chain" / "artifacts" / "CredentialRootRegistry.json"
)


def test_is_chain_configured_false_by_default(monkeypatch):
    # 显式清空三项配置，而不是依赖“测试环境本来就没配置”——如果开发者本机
    # backend/.env 里已经填了真实的CHAIN_*（比如刚跑通本地链联调），pydantic-settings
    # 会自动读到这些值，不加monkeypatch这里就会假失败，跟chain_service本身的
    # 逻辑对不对无关，纯粹是测试隔离没做好。
    monkeypatch.setattr(settings, "chain_rpc_url", None)
    monkeypatch.setattr(settings, "chain_backend_private_key", None)
    monkeypatch.setattr(settings, "chain_contract_address", None)
    assert chain_service.is_chain_configured() is False


def test_record_root_on_chain_skips_when_not_configured(monkeypatch):
    monkeypatch.setattr(settings, "chain_rpc_url", None)
    monkeypatch.setattr(settings, "chain_backend_private_key", None)
    monkeypatch.setattr(settings, "chain_contract_address", None)

    result = chain_service.record_root_on_chain(
        root_no="ROOT-20260715-0001",
        batch_id=1,
        merkle_root="a" * 64,
        previous_root_hash="0" * 64,
        current_root_hash="b" * 64,
    )
    assert result is None


def test_get_root_from_chain_skips_when_not_configured(monkeypatch):
    monkeypatch.setattr(settings, "chain_rpc_url", None)
    monkeypatch.setattr(settings, "chain_backend_private_key", None)
    monkeypatch.setattr(settings, "chain_contract_address", None)

    assert chain_service.get_root_from_chain("ROOT-20260715-0001") is None


@pytest.fixture()
def deployed_contract_settings(monkeypatch):
    """在内存里（EthereumTesterProvider）部署一份真实合约，把settings指向它，
    同时把chain_service里用来连接的Web3.HTTPProvider替换成EthereumTesterProvider
    ——这样record_root_on_chain/get_root_from_chain走的是和生产环境完全一样的
    代码路径，只是最终连接的是内存链，不是真的Ganache/Hardhat进程。
    """
    pytest.importorskip("eth_tester")
    web3 = pytest.importorskip("web3")
    EthereumTesterProvider = web3.EthereumTesterProvider
    Web3 = web3.Web3

    if not ARTIFACT_PATH.exists():
        pytest.skip(f"合约编译产物不存在：{ARTIFACT_PATH}，跳过链上集成测试")

    artifact = json.loads(ARTIFACT_PATH.read_text())
    provider = EthereumTesterProvider()
    w3 = Web3(provider)
    owner = w3.eth.accounts[0]

    # eth-tester的测试账户没有真实私钥字符串可以直接拿到，这里另外生成一个
    # 全新账户当"后端钱包"，先转一点测试币给它付手续费，然后专门用这个账户
    # （而不是eth-tester自带的account[0]）来部署合约——这样部署出来的合约
    # owner就是这个backend_account，跟chain_service.py实际签名交易用的账户
    # 是同一个，才能真的调用得动recordRoot（合约有onlyOwner限制）。
    from eth_account import Account

    backend_account = Account.create()
    w3.eth.send_transaction(
        {"from": owner, "to": backend_account.address, "value": w3.to_wei(10, "ether")}
    )

    Contract = w3.eth.contract(abi=artifact["abi"], bytecode=artifact["bytecode"])
    deploy_tx = Contract.constructor().build_transaction(
        {
            "from": backend_account.address,
            "nonce": w3.eth.get_transaction_count(backend_account.address),
        }
    )
    signed_deploy = backend_account.sign_transaction(deploy_tx)
    deploy_tx_hash = w3.eth.send_raw_transaction(signed_deploy.raw_transaction)
    receipt = w3.eth.wait_for_transaction_receipt(deploy_tx_hash)
    contract_address = receipt.contractAddress

    monkeypatch.setattr(settings, "chain_rpc_url", "http://127.0.0.1:8545")
    monkeypatch.setattr(settings, "chain_backend_private_key", backend_account.key.hex())
    monkeypatch.setattr(settings, "chain_contract_address", contract_address)
    monkeypatch.setattr(settings, "chain_expected_chain_ids", str(w3.eth.chain_id))

    # 关键一步：chain_service内部是 from web3 import Web3 之后调用
    # Web3.HTTPProvider(...)，这里直接把HTTPProvider换成一个"不管传什么参数
    # 都返回同一个EthereumTesterProvider"的假函数，request_kwargs等其它调用点
    # 不受影响。
    import web3 as web3_module

    monkeypatch.setattr(web3_module.Web3, "HTTPProvider", lambda *args, **kwargs: provider)

    return {"w3": w3, "contract_address": contract_address}


def test_record_and_get_root_on_chain_roundtrip(deployed_contract_settings):
    tx_hash = chain_service.record_root_on_chain(
        root_no="ROOT-20260715-0099",
        batch_id=42,
        merkle_root="c" * 64,
        previous_root_hash="0" * 64,
        current_root_hash="d" * 64,
    )
    assert tx_hash is not None
    assert tx_hash.startswith("0x")

    result = chain_service.get_root_from_chain("ROOT-20260715-0099")
    assert result is not None
    assert result["batch_id"] == 42
    assert result["merkle_root"] == "c" * 64
    assert result["current_root_hash"] == "d" * 64


def test_record_root_on_chain_rejects_unexpected_chain_id(
    deployed_contract_settings, monkeypatch
):
    monkeypatch.setattr(settings, "chain_expected_chain_ids", "1")

    tx_hash = chain_service.record_root_on_chain(
        root_no="ROOT-WRONG-CHAIN",
        batch_id=1,
        merkle_root="a" * 64,
        previous_root_hash="0" * 64,
        current_root_hash="b" * 64,
    )

    assert tx_hash is None


def test_get_root_from_chain_returns_none_for_unknown_root(deployed_contract_settings):
    assert chain_service.get_root_from_chain("ROOT-NOT-EXIST") is None


def test_record_root_on_chain_returns_none_on_duplicate(deployed_contract_settings):
    """合约里recordRoot对同一个rootNo只允许写一次，第二次写应该在链上revert——
    chain_service要把这种异常也吞掉，返回None，不能让上链失败拖垮整个请求。"""
    first = chain_service.record_root_on_chain(
        root_no="ROOT-DUP-0001",
        batch_id=1,
        merkle_root="e" * 64,
        previous_root_hash="0" * 64,
        current_root_hash="f" * 64,
    )
    assert first is not None

    second = chain_service.record_root_on_chain(
        root_no="ROOT-DUP-0001",
        batch_id=1,
        merkle_root="e" * 64,
        previous_root_hash="0" * 64,
        current_root_hash="f" * 64,
    )
    assert second is None


async def _post_json(path: str, payload: dict | None = None) -> httpx.Response:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        return await client.post(path, json=payload)


def test_merkle_root_route_writes_tx_hash_when_chain_configured(
    deployed_contract_settings, db_session
) -> None:
    """走完整的HTTP路由（不是直接调chain_service函数）：链配置齐全时，
    POST /admin/batches/{id}/merkle-root 的响应和数据库记录里都应该带上tx_hash。
    这一步验证的是certificate_batches.py里"算完本地Root之后再顺带上链"这段
    胶水代码接得对，而不是chain_service本身的逻辑（那部分前面几个测试已经覆盖了）。
    """
    student1 = Student(student_no="9300", student_name="链路由测试甲", class_name="1班")
    student2 = Student(student_no="9301", student_name="链路由测试乙", class_name="1班")
    db_session.add_all([student1, student2])
    db_session.commit()

    batch_id = asyncio.run(
        _post_json(
            "/api/admin/batches",
            {
                "batch_name": "上链路由测试批次",
                "student_ids": [student1.student_id, student2.student_id],
            },
        )
    ).json()["data"]["batch_id"]

    generate_resp = asyncio.run(_post_json(f"/api/admin/batches/{batch_id}/generate"))
    assert generate_resp.json()["data"]["generated_count"] == 2

    root_resp = asyncio.run(_post_json(f"/api/admin/batches/{batch_id}/merkle-root"))
    assert root_resp.status_code == 200
    root_data = root_resp.json()["data"]
    assert root_data["tx_hash"] is not None
    assert root_data["tx_hash"].startswith("0x")

    # 数据库里也要真的落了盘，不能只是响应体里临时拼出来的
    db_session.expire_all()
    root_record = db_session.query(CredentialRoot).filter(
        CredentialRoot.batch_id == batch_id
    ).first()
    assert root_record.tx_hash == root_data["tx_hash"]

    chain_record = chain_service.get_root_from_chain(root_data["root_no"])
    assert chain_record is not None
    assert chain_record["merkle_root"] == root_data["merkle_root"]
