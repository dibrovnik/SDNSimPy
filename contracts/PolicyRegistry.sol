// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/**
 * @title PolicyRegistry
 * @dev Смарт-контракт для безопасного хранения и публикации версий политик безопасности и QoS шлюзам и агентам.
 * Рассчитан на работу в ненадежных средах: агенты стягивают свежую версию каждый раз при появлении сети.
 */
contract PolicyRegistry {
    address public owner;
    uint256 public latestVersionId;

    event PolicyUpdated(uint256 indexed versionId, string payload);

    constructor() {
        owner = msg.sender;
        latestVersionId = 0;
    }

    modifier onlyOwner() {
        require(msg.sender == owner, "Only the owner can update the policy");
        _;
    }

    // Сохраняет новую версию JSON-манифеста политики (или CID IPFS)
    // В рамках симуляционной статьи публикуем как строку.
    mapping(uint256 => string) private policyVersions;

    function publishPolicy(string memory _payload) external onlyOwner {
        latestVersionId++;
        policyVersions[latestVersionId] = _payload;
        emit PolicyUpdated(latestVersionId, _payload);
    }

    function getLatestVersionId() external view returns (uint256) {
        return latestVersionId;
    }

    function getPolicyPayload(uint256 _versionId) external view returns (string memory) {
        require(_versionId > 0 && _versionId <= latestVersionId, "Invalid policy version ID");
        return policyVersions[_versionId];
    }
}
