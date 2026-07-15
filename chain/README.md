# 本地测试链接入（P2加分项）

对应 `docs/协作管理/FISCO_BCOS与存证降级策略.md` 第8节 / `docs/协作管理/数据库设计.md` 第9.5节。

## 这一层做什么

批次算完 Merkle Root 之后（`merkle_service.compute_batch_root()`），额外把这一批的
Root 信息写一笔交易上本地测试链，作为本地哈希链之外的"链上回执"。**只上批次
Root，不逐张证书上链**——一个批次一笔交易，单张证书哈希始终只存在本地
`evidence_receipts` 表。

这一层是纯粹的可选叠加，不是主线闭环的一部分。链没配置、连不上、写入失败，
`chain_service.py` 的函数都只返回 `None`，不抛异常，不影响本地 Root 已经算好、
已经能验证的事实——符合降级策略"遇阻立即降级回本地哈希链"的要求。

## 目录结构

- `contracts/CredentialRootRegistry.sol` — 合约源码。存储结构按批次 Root
  设计（不是 1 号自己那份按单证书设计的 `CertificateRegistry.sol`），`onlyOwner`
  写权限，每个 `rootNo` 只能写一次（Root 一旦生成就是历史事实，不允许覆盖，
  对应 9.4 节"Root 不会因撤销而重新计算"）。
- `artifacts/CredentialRootRegistry.abi.json` / `.json` — 编译产物（ABI +
  bytecode），用 `solc@0.8.20` 编译好的，直接用，不需要在每台机器上重新编译。
- `scripts/deploy.py` — 部署脚本，读 `backend/.env` 里的私钥和 RPC 地址，
  部署合约，把地址写进 `chain/deployment-info.json`（本地生成，不提交进 git，
  每个人部署出来的合约地址不一样）。
- `scripts/generate_wallet.py` — 生成一个全新的后端专属钱包（地址+私钥），
  用于本地测试链部署与写入交易的签名账户。

## 怎么跑起来

1. **起一条本地测试链**（Ganache 或 Hardhat 均可，只要是本地监听、兼容以太坊
   JSON-RPC 的节点）：

   ```bash
   npx ganache --wallet.deterministic
   ```

   `--wallet.deterministic` 让每次生成的测试账户地址固定，方便反复调试；不加
   这个参数也能用，只是账户地址每次都不一样。

2. **拿一个私钥当后端钱包**。两种方式都行：
   - 直接用 Ganache 启动时打印出来的某个测试账户私钥（自带测试币，最省事）；
   - 或者跑 `python chain/scripts/generate_wallet.py` 自己生成一个新钱包，
     然后手动给它转一点本地测试币（同样是假币，不需要真的领）。

   **这个私钥只用于后端服务自动签名交易，不是任何人的个人 MetaMask 钱包**——
   演示/自动化场景下不能依赖某个人的浏览器插件，必须是服务端能直接读取的
   账户，见 `backend/app/core/config.py` 里 `chain_backend_private_key` 的注释。

3. **配置 `backend/.env`**（照抄 `.env.example` 里的三项）：

   ```
   CHAIN_RPC_URL=http://127.0.0.1:8545
   CHAIN_BACKEND_PRIVATE_KEY=<第2步拿到的私钥>
   CHAIN_CONTRACT_ADDRESS=
   ```

   `CHAIN_CONTRACT_ADDRESS` 先留空，等第4步部署完再填。

4. **部署合约**：

   ```bash
   python chain/scripts/deploy.py
   ```

   成功后会打印合约地址，同时写入 `chain/deployment-info.json`。把打印出来的
   合约地址填回 `backend/.env` 的 `CHAIN_CONTRACT_ADDRESS`。

5. 重启后端。之后每次调用批次生成 Merkle Root 的接口
   （`POST /api/admin/batches/{batch_id}/merkle-root`），只要三项配置都齐全、
   链连得上，返回结果和数据库里 `credential_roots.tx_hash` 字段就会带上链上
   交易哈希；任意一步失败，`tx_hash` 保持 `null`，本地 Root 计算结果不受影响。

## 三项配置任意一项没填会怎样

`chain_service.is_chain_configured()` 要求 `CHAIN_RPC_URL` /
`CHAIN_BACKEND_PRIVATE_KEY` / `CHAIN_CONTRACT_ADDRESS` 三项都非空，缺一项就
直接跳过上链（记一条日志，不报错）。也就是说：只做 Merkle Root 这一层、完全
不碰链的同学，什么都不用配，主线功能不受任何影响。

## 测试

`backend/tests/test_chain_service.py` 用 `web3.py` 自带的
`EthereumTesterProvider`（纯 Python 内存里模拟一条链）验证真实的合约调用逻辑，
不需要真的起 Ganache 进程就能跑：

```bash
cd backend && python -m pytest -q tests/test_chain_service.py
```
