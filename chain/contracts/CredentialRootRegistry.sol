// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/// @title CredentialRootRegistry
/// @notice 只存"批次Merkle Root"，不逐张证书上链，对应
///         docs/协作管理/FISCO_BCOS与存证降级策略.md 第8.4节 /
///         docs/协作管理/数据库设计.md 第9.5节的要求：一个批次一笔交易，
///         单张证书的哈希始终只保存在本地 evidence_receipts 表，不上链。
///
/// 字段跟后端 backend/app/models/credential_root.py 的 CredentialRoot 一一对应，
/// 方便验真时直接比对链上/链下两份记录是否一致。
contract CredentialRootRegistry {
    address public owner;

    struct RootRecord {
        uint256 batchId;
        string merkleRoot;
        string previousRootHash;
        string currentRootHash;
        uint256 timestamp;
        bool exists;
    }

    // rootNo（对应 credential_roots.root_no 业务编号）=> 记录
    mapping(string => RootRecord) private records;

    event RootRecorded(
        string rootNo,
        uint256 batchId,
        string merkleRoot,
        string currentRootHash,
        uint256 timestamp
    );

    modifier onlyOwner() {
        require(msg.sender == owner, "Only owner can operate");
        _;
    }

    constructor() {
        owner = msg.sender;
    }

    /// @notice 记录一个批次的Merkle Root。每个rootNo只能写一次——Root一旦生成
    ///         就是历史事实，不允许覆盖（对应9.4节"Root不会因撤销而重新计算"的约束）。
    function recordRoot(
        string memory rootNo,
        uint256 batchId,
        string memory merkleRoot,
        string memory previousRootHash,
        string memory currentRootHash
    ) public onlyOwner {
        require(bytes(rootNo).length > 0, "rootNo is required");
        require(bytes(merkleRoot).length > 0, "merkleRoot is required");
        require(!records[rootNo].exists, "root already recorded");

        records[rootNo] = RootRecord({
            batchId: batchId,
            merkleRoot: merkleRoot,
            previousRootHash: previousRootHash,
            currentRootHash: currentRootHash,
            timestamp: block.timestamp,
            exists: true
        });

        emit RootRecorded(rootNo, batchId, merkleRoot, currentRootHash, block.timestamp);
    }

    function getRoot(
        string memory rootNo
    )
        public
        view
        returns (
            uint256 batchId,
            string memory merkleRoot,
            string memory previousRootHash,
            string memory currentRootHash,
            uint256 timestamp,
            bool exists
        )
    {
        RootRecord memory record = records[rootNo];
        return (
            record.batchId,
            record.merkleRoot,
            record.previousRootHash,
            record.currentRootHash,
            record.timestamp,
            record.exists
        );
    }
}
