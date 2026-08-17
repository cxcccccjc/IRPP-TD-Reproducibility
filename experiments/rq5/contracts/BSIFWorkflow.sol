// SPDX-License-Identifier: MIT
pragma solidity ^0.8.11;

/// @notice Natural FISCO/EVM port of BSIF's reusable task, encrypted upload,
/// requester quality report, next-round reputation, and payment lifecycle.
contract BSIFWorkflow {
    struct Task {
        bytes encryptedTask;
        bytes32 locationTag;
        uint32 expectedWorkers;
        uint32 reports;
        bytes32 qualityRoot;
        uint8 state; // 1=collecting, 2=evaluated, 3=paid
    }

    mapping(bytes32 => Task) public tasks;
    mapping(bytes32 => mapping(bytes32 => bytes)) private encryptedReports;
    mapping(bytes32 => uint64) public reputation;

    event TaskPublished(bytes32 indexed taskId, uint32 expectedWorkers);
    event ReportUploaded(bytes32 indexed taskId, bytes32 indexed workerTag, uint32 bytesLength);
    event QualitySubmitted(bytes32 indexed taskId, bytes32 qualityRoot);
    event Settled(bytes32 indexed taskId, bytes32 paymentRoot);

    function registerWorker(bytes32 workerTag, uint64 initialReputation) external {
        reputation[workerTag] = initialReputation;
    }

    function publishTask(
        bytes32 taskId,
        bytes calldata encryptedTask,
        bytes32 locationTag,
        uint32 expectedWorkers
    ) external {
        require(tasks[taskId].state == 0, "task exists");
        Task storage t = tasks[taskId];
        t.encryptedTask = encryptedTask;
        t.locationTag = locationTag;
        t.expectedWorkers = expectedWorkers;
        t.state = 1;
        emit TaskPublished(taskId, expectedWorkers);
    }

    function uploadReport(bytes32 taskId, bytes32 workerTag, bytes calldata ciphertext) external {
        Task storage t = tasks[taskId];
        require(t.state == 1, "not collecting");
        require(encryptedReports[taskId][workerTag].length == 0, "duplicate");
        encryptedReports[taskId][workerTag] = ciphertext;
        t.reports += 1;
        emit ReportUploaded(taskId, workerTag, uint32(ciphertext.length));
    }

    function submitQuality(bytes32 taskId, bytes32 qualityRoot) external {
        Task storage t = tasks[taskId];
        require(t.state == 1, "wrong state");
        require(t.reports == t.expectedWorkers, "missing reports");
        t.qualityRoot = qualityRoot;
        t.state = 2;
        emit QualitySubmitted(taskId, qualityRoot);
    }

    function updateReputation(bytes32 workerTag, uint64 nextReputation) external {
        reputation[workerTag] = nextReputation;
    }

    function settle(bytes32 taskId, bytes32 paymentRoot) external {
        Task storage t = tasks[taskId];
        require(t.state == 2, "not evaluated");
        t.state = 3;
        emit Settled(taskId, paymentRoot);
    }

    function reportLength(bytes32 taskId, bytes32 workerTag) external view returns (uint256) {
        return encryptedReports[taskId][workerTag].length;
    }
}
