// SPDX-License-Identifier: MIT
pragma solidity ^0.8.11;

/// @notice Ledger-side state machine used by the matched RQ5 reproduction.
/// Plain sensing reports and exact reputations remain off chain.  The contract
/// records the rule/input/output commitments, one-time credential transitions,
/// challenges, threshold-audit outcomes, and settlement state described by P1--P7.
contract IRPPWorkflow {
    address public immutable owner;
    uint32 public constant AUDIT_THRESHOLD = 3;

    struct Task {
        bytes32 ruleRoot;
        bytes32 inputRoot;
        bytes32 outputRoot;
        bytes32 aggregateCommitment;
        bytes32 transcriptRoot;
        uint32 expectedWorkers;
        uint32 closedWorkers;
        uint64 finalizeAfterBlock;
        uint8 state; // 1=published, 2=input closed, 3=pending, 4=final
        bool challenged;
        bool corrected;
    }

    mapping(bytes32 => Task) public tasks;
    mapping(bytes32 => bool) public consumedCredential;
    mapping(bytes32 => bytes32) public pendingSuccessor;
    mapping(address => bool) public validAuditor;
    mapping(bytes32 => mapping(uint8 => mapping(address => bool))) public auditVoted;
    mapping(bytes32 => mapping(uint8 => uint32)) public auditFaultVotes;
    mapping(bytes32 => mapping(uint8 => uint32)) public auditCleanVotes;
    mapping(bytes32 => mapping(uint8 => mapping(bytes32 => uint32))) public auditDigestVotes;
    mapping(bytes32 => bool) public auditResolved;
    mapping(bytes32 => bool) public correctionAuthorized;
    mapping(bytes32 => bytes32) public correctedDigest;

    event TaskPublished(bytes32 indexed taskId, bytes32 ruleRoot, uint32 expectedWorkers);
    event CredentialReserved(bytes32 indexed taskId, bytes32 indexed predecessor, bytes32 successor);
    event InputClosed(bytes32 indexed taskId, bytes32 inputRoot, uint32 workerCount);
    event OutputCommitted(bytes32 indexed taskId, bytes32 outputRoot, bytes32 aggregateCommitment, bytes32 transcriptRoot);
    event Challenged(bytes32 indexed taskId, bytes32 indexed leafRef, bytes32 reason);
    event AuditVote(bytes32 indexed taskId, uint8 round, bool drFault, bytes32 correctDigest);
    event Finalized(bytes32 indexed taskId, bool corrected);

    constructor() {
        owner = msg.sender;
    }

    function registerAuditor(address auditor) external {
        require(msg.sender == owner, "only owner");
        require(auditor != address(0), "zero auditor");
        require(!validAuditor[auditor], "auditor exists");
        validAuditor[auditor] = true;
    }

    function publishTask(bytes32 taskId, bytes32 ruleRoot, uint32 expectedWorkers) external {
        require(tasks[taskId].state == 0, "task exists");
        tasks[taskId].ruleRoot = ruleRoot;
        tasks[taskId].expectedWorkers = expectedWorkers;
        tasks[taskId].state = 1;
        emit TaskPublished(taskId, ruleRoot, expectedWorkers);
    }

    function reserveCredential(bytes32 taskId, bytes32 predecessor, bytes32 successor) external {
        require(tasks[taskId].state == 1, "not collecting");
        require(!consumedCredential[predecessor], "predecessor consumed");
        consumedCredential[predecessor] = true;
        pendingSuccessor[predecessor] = successor;
        tasks[taskId].closedWorkers += 1;
        emit CredentialReserved(taskId, predecessor, successor);
    }

    function closeInput(bytes32 taskId, bytes32 inputRoot, uint32 workerCount) external {
        Task storage t = tasks[taskId];
        require(t.state == 1, "wrong state");
        require(workerCount == t.closedWorkers, "count mismatch");
        t.inputRoot = inputRoot;
        t.state = 2;
        emit InputClosed(taskId, inputRoot, workerCount);
    }

    function commitOutput(
        bytes32 taskId,
        bytes32 outputRoot,
        bytes32 aggregateCommitment,
        bytes32 transcriptRoot
    ) external {
        Task storage t = tasks[taskId];
        require(t.state == 2, "wrong state");
        t.outputRoot = outputRoot;
        t.aggregateCommitment = aggregateCommitment;
        t.transcriptRoot = transcriptRoot;
        // The pending output cannot be finalized in its commit block.  On the
        // matched 500-ms local block cadence, the next-block gate implements
        // the declared challenge window without a wall-clock oracle.
        t.finalizeAfterBlock = uint64(block.number + 1);
        t.state = 3;
        emit OutputCommitted(taskId, outputRoot, aggregateCommitment, transcriptRoot);
    }

    function challenge(bytes32 taskId, bytes32 leafRef, bytes32 reason) external {
        require(tasks[taskId].state == 3, "not pending");
        tasks[taskId].challenged = true;
        emit Challenged(taskId, leafRef, reason);
    }

    function auditVote(
        bytes32 taskId,
        uint8 round,
        bool drFault,
        bytes32 correctDigest
    ) external {
        require(tasks[taskId].state == 3, "not pending");
        require(validAuditor[msg.sender], "unregistered auditor");
        require(!auditVoted[taskId][round][msg.sender], "duplicate auditor");
        auditVoted[taskId][round][msg.sender] = true;
        if (drFault) {
            auditFaultVotes[taskId][round] += 1;
            auditDigestVotes[taskId][round][correctDigest] += 1;
            // Authorization requires a threshold on one identical corrected
            // digest, not merely three generic "DR fault" flags.
            if (auditDigestVotes[taskId][round][correctDigest] >= AUDIT_THRESHOLD) {
                auditResolved[taskId] = true;
                correctionAuthorized[taskId] = true;
                correctedDigest[taskId] = correctDigest;
            }
        } else {
            auditCleanVotes[taskId][round] += 1;
            if (auditCleanVotes[taskId][round] >= AUDIT_THRESHOLD) {
                auditResolved[taskId] = true;
            }
        }
        emit AuditVote(taskId, round, drFault, correctDigest);
    }

    function finalize(bytes32 taskId, bool corrected) external {
        Task storage t = tasks[taskId];
        require(t.state == 3, "not pending");
        if (corrected) {
            require(auditResolved[taskId] && correctionAuthorized[taskId], "correction not authorized");
        } else {
            require(block.number >= t.finalizeAfterBlock, "challenge window open");
            require(!correctionAuthorized[taskId], "correction required");
            require(!t.challenged || auditResolved[taskId], "challenge unresolved");
        }
        t.corrected = corrected;
        t.state = 4;
        emit Finalized(taskId, corrected);
    }
}
