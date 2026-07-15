"""
把 CredentialRootRegistry 合约部署到本地测试链（Ganache / Hardhat 均可，
只要是一个监听在本地、兼容以太坊 JSON-RPC 的节点）。

用法：
    1. 先在另一个终端起本地链，例如：
       cd chain && npx ganache --wallet.deterministic
       （--wallet.deterministic 让每次生成的测试账户地址固定，方便重复调试；
       正式使用不需要这个参数也可以，只是账户地址每次会不一样）
    2. 确保 backend/.env 里配置了 CHAIN_BACKEND_PRIVATE_KEY（本地链的测试账户私钥即可，
       测试链自带的账户默认都已经预充了测试币，不需要另外领）
    3. 在项目根目录运行：
       python chain/scripts/deploy.py
    4. 部署成功后，脚本会把合约地址等信息写到 chain/deployment-info.json
       （这个文件本地生成、不提交进git，每个人本地部署出来的地址都不一样，
       后端读取合约地址时就读这个文件）
"""
import json
import os
import sys
from pathlib import Path

from web3 import Web3

CHAIN_DIR = Path(__file__).resolve().parents[1]
PROJECT_ROOT = CHAIN_DIR.parent
ARTIFACT_PATH = CHAIN_DIR / "artifacts" / "CredentialRootRegistry.json"
DEPLOYMENT_INFO_PATH = CHAIN_DIR / "deployment-info.json"

DEFAULT_RPC_URL = "http://127.0.0.1:8545"
DEFAULT_EXPECTED_CHAIN_IDS = "1337,31337"


def _load_env_file() -> dict:
    """简单读一下 backend/.env（不引入额外依赖），拿 CHAIN_BACKEND_PRIVATE_KEY /
    CHAIN_RPC_URL 这两个配置项。"""
    env_path = PROJECT_ROOT / "backend" / ".env"
    values: dict[str, str] = {}
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            values[key.strip()] = value.strip()
    return values


def main() -> None:
    env_values = _load_env_file()
    private_key = os.environ.get("CHAIN_BACKEND_PRIVATE_KEY") or env_values.get("CHAIN_BACKEND_PRIVATE_KEY")
    if not private_key:
        print(
            "没有找到 CHAIN_BACKEND_PRIVATE_KEY，请先在 backend/.env 里配置好后端专属钱包私钥\n"
            "（本地测试链账户自带测试币，直接用本地链打印出来的某个账户私钥即可，不需要真的去领币）。",
            file=sys.stderr,
        )
        sys.exit(1)

    rpc_url = os.environ.get("CHAIN_RPC_URL") or env_values.get("CHAIN_RPC_URL") or DEFAULT_RPC_URL
    expected_chain_ids_text = (
        os.environ.get("CHAIN_EXPECTED_CHAIN_IDS")
        or env_values.get("CHAIN_EXPECTED_CHAIN_IDS")
        or DEFAULT_EXPECTED_CHAIN_IDS
    )
    try:
        expected_chain_ids = {
            int(item.strip()) for item in expected_chain_ids_text.split(",") if item.strip()
        }
    except ValueError:
        print("CHAIN_EXPECTED_CHAIN_IDS 格式无效，拒绝部署", file=sys.stderr)
        sys.exit(1)

    if not ARTIFACT_PATH.exists():
        print(f"找不到编译产物：{ARTIFACT_PATH}，请先编译合约", file=sys.stderr)
        sys.exit(1)

    artifact = json.loads(ARTIFACT_PATH.read_text())

    w3 = Web3(Web3.HTTPProvider(rpc_url))
    if not w3.is_connected():
        print(f"连不上本地链 {rpc_url}，请确认本地链（Ganache/Hardhat）已经起起来了", file=sys.stderr)
        sys.exit(1)
    if int(w3.eth.chain_id) not in expected_chain_ids:
        print(
            f"拒绝部署到未授权链：chain_id={w3.eth.chain_id}，允许列表={sorted(expected_chain_ids)}",
            file=sys.stderr,
        )
        sys.exit(1)

    account = w3.eth.account.from_key(private_key)
    print(f"部署账户：{account.address}")
    balance = w3.eth.get_balance(account.address)
    print(f"账户余额：{w3.from_wei(balance, 'ether')} ETH（本地测试链的假币）")

    Contract = w3.eth.contract(abi=artifact["abi"], bytecode=artifact["bytecode"])
    tx = Contract.constructor().build_transaction(
        {
            "from": account.address,
            "nonce": w3.eth.get_transaction_count(account.address),
        }
    )
    signed = account.sign_transaction(tx)
    tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
    receipt = w3.eth.wait_for_transaction_receipt(tx_hash)

    contract_address = receipt.contractAddress
    print(f"部署成功！合约地址：{contract_address}")
    print(f"部署交易哈希：{receipt.transactionHash.hex()}")

    deployment_info = {
        "network": "local",
        "rpc_url": rpc_url,
        "chain_id": w3.eth.chain_id,
        "contract_name": "CredentialRootRegistry",
        "contract_address": contract_address,
        "deploy_tx_hash": receipt.transactionHash.hex(),
        "owner_address": account.address,
    }
    DEPLOYMENT_INFO_PATH.write_text(json.dumps(deployment_info, ensure_ascii=False, indent=2))
    print(f"部署信息已写入 {DEPLOYMENT_INFO_PATH}")


if __name__ == "__main__":
    main()
