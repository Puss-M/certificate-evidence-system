"""
测试链接入服务（P2加分项）。

对应 docs/协作管理/FISCO_BCOS与存证降级策略.md 第8.4节 / 数据库设计.md 第9.5节：
只把批次的Merkle Root写上链（一个批次一笔交易），不逐张证书上链；单张证书的哈希
仍然只存在本地 evidence_receipts 表。

这一层是纯粹的"可选叠加"，不是主线闭环的一部分——`app.core.config.settings` 里
CHAIN_RPC_URL / CHAIN_BACKEND_PRIVATE_KEY / CHAIN_CONTRACT_ADDRESS 任意一项没配置，
或者链连不上、写入失败，这个模块的函数都只返回 None、记日志，不抛异常、不影响
merkle_service.compute_batch_root() 已经算好的本地结果——符合降级策略第5节
"遇阻立即降级回本地哈希链"的要求。

合约源码、部署方式见 chain/ 目录（chain/README.md）。
"""

import json
import logging
from pathlib import Path

from app.core.config import settings

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[3]
ARTIFACT_PATH = PROJECT_ROOT / "chain" / "artifacts" / "CredentialRootRegistry.json"

_ABI_CACHE: list | None = None


def _load_abi() -> list | None:
    global _ABI_CACHE
    if _ABI_CACHE is not None:
        return _ABI_CACHE
    if not ARTIFACT_PATH.exists():
        logger.warning("找不到合约编译产物：%s，链上功能将跳过", ARTIFACT_PATH)
        return None
    artifact = json.loads(ARTIFACT_PATH.read_text())
    _ABI_CACHE = artifact["abi"]
    return _ABI_CACHE


def is_chain_configured() -> bool:
    """三项配置（RPC地址、后端钱包私钥、合约地址）缺一不可，少任何一项都视为
    "没打算接链"，直接跳过，不算错误。"""
    return bool(
        settings.chain_rpc_url
        and settings.chain_backend_private_key
        and settings.chain_contract_address
    )


def _get_web3_and_contract():
    """延迟导入web3——这样即使没装web3包，只要没配置链相关的环境变量，
    其它不涉及上链的功能也完全不受影响，不会因为导入失败连带炸掉整个后端。"""
    from web3 import Web3

    abi = _load_abi()
    if abi is None:
        return None, None

    w3 = Web3(Web3.HTTPProvider(settings.chain_rpc_url))
    if not w3.is_connected():
        logger.warning("连不上本地测试链：%s，本次跳过上链", settings.chain_rpc_url)
        return None, None

    contract = w3.eth.contract(address=settings.chain_contract_address, abi=abi)
    return w3, contract


def record_root_on_chain(
    *,
    root_no: str,
    batch_id: int,
    merkle_root: str,
    previous_root_hash: str | None,
    current_root_hash: str,
) -> str | None:
    """把一个批次的Merkle Root写上链，成功返回交易哈希（0x开头的字符串），
    任何一步失败（没配置/连不上/合约调用报错）都返回None，调用方不需要
    也不应该因为这个返回None就报错——上链只是锦上添花，不是必须的。
    """
    if not is_chain_configured():
        logger.info("链相关配置不完整，跳过上链：root_no=%s", root_no)
        return None

    try:
        w3, contract = _get_web3_and_contract()
        if w3 is None or contract is None:
            return None

        account = w3.eth.account.from_key(settings.chain_backend_private_key)
        tx = contract.functions.recordRoot(
            root_no,
            batch_id,
            merkle_root,
            previous_root_hash or "0" * 64,
            current_root_hash,
        ).build_transaction(
            {
                "from": account.address,
                "nonce": w3.eth.get_transaction_count(account.address),
            }
        )
        signed = account.sign_transaction(tx)
        tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
        receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=30)

        if receipt.status != 1:
            logger.warning("上链交易失败（status=0）：root_no=%s", root_no)
            return None

        # HexBytes.hex()在不同web3.py版本里带不带"0x"前缀不一致，这里统一补上，
        # 跟区块链浏览器（Etherscan等）展示交易哈希的惯例保持一致。
        tx_hash_hex = receipt.transactionHash.hex()
        if not tx_hash_hex.startswith("0x"):
            tx_hash_hex = f"0x{tx_hash_hex}"
        return tx_hash_hex
    except Exception:
        # 上链这一步任何异常（网络问题、合约revert、超时……）都不应该往上抛，
        # 抛出去会导致调用方（批次生成Root的路由）整个请求失败，
        # 违反"链失败不影响本地闭环"的降级原则。
        logger.exception("上链写入异常，本次跳过：root_no=%s", root_no)
        return None


def get_root_from_chain(root_no: str) -> dict | None:
    """按root_no查链上记录，主要给验真页做"链上/链下比对"用。查不到、连不上、
    没配置，统一返回None，调用方据此展示"暂无链上数据"而不是报错。"""
    if not is_chain_configured():
        return None

    try:
        _, contract = _get_web3_and_contract()
        if contract is None:
            return None

        batch_id, merkle_root, previous_root_hash, current_root_hash, timestamp, exists = (
            contract.functions.getRoot(root_no).call()
        )
        if not exists:
            return None

        return {
            "batch_id": batch_id,
            "merkle_root": merkle_root,
            "previous_root_hash": previous_root_hash,
            "current_root_hash": current_root_hash,
            "timestamp": timestamp,
        }
    except Exception:
        logger.exception("查询链上记录异常：root_no=%s", root_no)
        return None
