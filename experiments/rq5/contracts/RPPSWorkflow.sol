// SPDX-License-Identifier: MIT
pragma solidity ^0.8.11;

/// @notice Standard, non-specialized FISCO/EVM implementation of the native
/// RPPS-TDC lifecycle: task release, Paillier report upload, RC trust update,
/// selected-set commitment, result commitment, and trust-weighted settlement.
contract RPPSWorkflow {
    struct Task {
        bytes encryptedTask;
        bytes32 geohashTag;
        uint32 expectedWorkers;
        uint32 reports;
        bytes32 trustRoot;
        bytes32 selectionRoot;
        bytes32 resultRoot;
        uint8 state; // 1=collecting, 2=selected, 3=result, 4=paid
    }

    mapping(bytes32 => Task) public tasks;
    mapping(bytes32 => mapping(bytes32 => bytes)) private encryptedReports;
    mapping(bytes32 => uint64) public reputation;

    event TaskPublished(bytes32 indexed taskId, uint32 expectedWorkers);
    event ReportUploaded(bytes32 indexed taskId, bytes32 indexed workerTag, uint32 bytesLength);
    event TrustCommitted(bytes32 indexed taskId, bytes32 trustRoot);
    event SelectionCommitted(bytes32 indexed taskId, bytes32 selectionRoot);
    event ResultCommitted(bytes32 indexed taskId, bytes32 resultRoot);
    event Settled(bytes32 indexed taskId, bytes32 paymentRoot);

    function registerWorker(bytes32 workerTag, uint64 initialReputation) external {
        reputation[workerTag] = initialReputation;
    }

    function publishTask(
        bytes32 taskId,
        bytes calldata encryptedTask,
        bytes32 geohashTag,
        uint32 expectedWorkers
    ) external {
        require(tasks[taskId].state == 0, "task exists");
        Task storage t = tasks[taskId];
        t.encryptedTask = encryptedTask;
        t.geohashTag = geohashTag;
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

    function commitTrust(bytes32 taskId, bytes32 trustRoot) external {
        Task storage t = tasks[taskId];
        require(t.state == 1, "wrong state");
        require(t.reports == t.expectedWorkers, "missing reports");
        t.trustRoot = trustRoot;
        emit TrustCommitted(taskId, trustRoot);
    }

    function commitSelection(bytes32 taskId, bytes32 selectionRoot) external {
        Task storage t = tasks[taskId];
        require(t.state == 1, "wrong state");
        t.selectionRoot = selectionRoot;
        t.state = 2;
        emit SelectionCommitted(taskId, selectionRoot);
    }

    function commitResult(bytes32 taskId, bytes32 resultRoot) external {
        Task storage t = tasks[taskId];
        require(t.state == 2, "not selected");
        t.resultRoot = resultRoot;
        t.state = 3;
        emit ResultCommitted(taskId, resultRoot);
    }

    function updateReputation(bytes32 workerTag, uint64 nextReputation) external {
        reputation[workerTag] = nextReputation;
    }

    function settle(bytes32 taskId, bytes32 paymentRoot) external {
        Task storage t = tasks[taskId];
        require(t.state == 3, "no result");
        t.state = 4;
        emit Settled(taskId, paymentRoot);
    }

    function reportLength(bytes32 taskId, bytes32 workerTag) external view returns (uint256) {
        return encryptedReports[taskId][workerTag].length;
    }
}
