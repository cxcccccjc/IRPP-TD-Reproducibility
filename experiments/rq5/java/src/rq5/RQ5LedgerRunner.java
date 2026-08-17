package rq5;

import java.io.File;
import java.io.FileWriter;
import java.io.PrintWriter;
import java.math.BigInteger;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.SecureRandom;
import java.util.ArrayList;
import java.util.Collections;
import java.util.List;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicInteger;
import java.util.concurrent.atomic.AtomicLong;
import java.util.function.Supplier;

import org.fisco.bcos.sdk.v3.BcosSDK;
import org.fisco.bcos.sdk.v3.client.Client;
import org.fisco.bcos.sdk.v3.crypto.keypair.CryptoKeyPair;
import org.fisco.bcos.sdk.v3.model.TransactionReceipt;
import org.fisco.bcos.sdk.v3.model.callback.TransactionCallback;

import rq5.contracts.BSIFWorkflow;
import rq5.contracts.IRPPWorkflow;
import rq5.contracts.RPPSWorkflow;

/**
 * FISCO BCOS 3.7.3 matched-workload runner for RQ5.
 *
 * Deployment and registration are measured separately and amortized. Formal
 * task rows contain only the native per-task state transitions. Ledger bytes
 * are the confirmed transaction input plus the SDK-encoded receipt; physical
 * RocksDB compaction and four-node replication are intentionally excluded.
 */
public final class RQ5LedgerRunner {
    private final SecureRandom random = new SecureRandom();
    private final Client client;
    private final CryptoKeyPair keyPair;
    private final IRPPWorkflow irpp;
    private final List<IRPPWorkflow> irppAuditors;
    private final List<CryptoKeyPair> irppAuditorKeys;
    private final BSIFWorkflow bsif;
    private final RPPSWorkflow rpps;
    private final PrintWriter txWriter;
    private final PrintWriter taskWriter;
    private final PrintWriter deploymentWriter;
    private final PrintWriter throughputWriter;
    private final int dimension;
    private final int payloadBytes;
    private final int paillierCipherBytes;
    private final int bsifReportBytes;
    private final int rppsReportBytes;

    private static final class TxAggregate {
        final List<Double> latencyMs = new ArrayList<>();
        long ledgerBytes = 0;
        long gasUsed = 0;
        int txCount = 0;
        boolean valid = true;

        void add(TxObservation obs) {
            latencyMs.add(obs.latencyMs);
            ledgerBytes += obs.ledgerBytes;
            gasUsed += obs.gasUsed;
            txCount += 1;
            valid &= obs.ok;
        }
    }

    private static final class TxObservation {
        final double latencyMs;
        final long ledgerBytes;
        final long gasUsed;
        final boolean ok;
        final TransactionReceipt receipt;

        TxObservation(double latencyMs, long ledgerBytes, long gasUsed, boolean ok, TransactionReceipt receipt) {
            this.latencyMs = latencyMs;
            this.ledgerBytes = ledgerBytes;
            this.gasUsed = gasUsed;
            this.ok = ok;
            this.receipt = receipt;
        }
    }

    private RQ5LedgerRunner(
            Client client,
            CryptoKeyPair keyPair,
            IRPPWorkflow irpp,
            List<IRPPWorkflow> irppAuditors,
            List<CryptoKeyPair> irppAuditorKeys,
            BSIFWorkflow bsif,
            RPPSWorkflow rpps,
            File output,
            int dimension,
            int payloadBytes) throws Exception {
        this.client = client;
        this.keyPair = keyPair;
        this.irpp = irpp;
        this.irppAuditors = irppAuditors;
        this.irppAuditorKeys = irppAuditorKeys;
        this.bsif = bsif;
        this.rpps = rpps;
        this.dimension = dimension;
        this.payloadBytes = payloadBytes;
        this.paillierCipherBytes = 768; // 3072-bit n -> 6144-bit Paillier ciphertext
        this.rppsReportBytes = dimension * paillierCipherBytes;
        this.bsifReportBytes = rppsReportBytes + 384 + 12 + 16; // RSA-3072 wrap + AES-GCM
        output.mkdirs();
        this.txWriter = writer(output, "chain_transactions.csv",
                "protocol,n,run,audit_mode,phase,tx_index,latency_ms,ledger_bytes,gas_used,block_number,status,tx_hash");
        this.taskWriter = writer(output, "chain_tasks.csv",
                "protocol,n,run,audit_mode,chain_active_ms,tx_count,confirm_median_ms,confirm_p95_ms,ledger_bytes_task,gas_used,block_start,block_end,valid,contract_address");
        this.deploymentWriter = writer(output, "chain_setup.csv",
                "protocol,operation,latency_ms,ledger_bytes,gas_used,block_number,contract_address");
        this.throughputWriter = writer(output, "chain_throughput.csv",
                "protocol,burst,transactions,payload_bytes,wall_ms,tps,successes,ledger_bytes");
    }

    private static PrintWriter writer(File dir, String name, String header) throws Exception {
        PrintWriter out = new PrintWriter(new FileWriter(new File(dir, name), false));
        out.println(header);
        out.flush();
        return out;
    }

    private byte[] randomBytes(int length) {
        byte[] out = new byte[length];
        random.nextBytes(out);
        return out;
    }

    private byte[] digest(String value) {
        try {
            return MessageDigest.getInstance("SHA-256").digest(value.getBytes(StandardCharsets.UTF_8));
        } catch (Exception e) {
            throw new RuntimeException(e);
        }
    }

    private static long hexBytes(String value) {
        if (value == null || value.isEmpty()) return 0;
        int chars = value.startsWith("0x") ? value.length() - 2 : value.length();
        return (chars + 1L) / 2L;
    }

    private static long parseQuantity(String value) {
        if (value == null || value.isEmpty()) return 0;
        try {
            return value.startsWith("0x") ? new BigInteger(value.substring(2), 16).longValue() : new BigInteger(value).longValue();
        } catch (Exception ignored) {
            return 0;
        }
    }

    private static long ledgerBytes(TransactionReceipt receipt) {
        try {
            return hexBytes(receipt.getInput()) + receipt.encodeTransactionReceipt().length;
        } catch (Exception e) {
            return hexBytes(receipt.getInput()) + hexBytes(receipt.getOutput());
        }
    }

    private TxObservation observe(
            String protocol, int n, int run, String auditMode, String phase, int txIndex,
            Supplier<TransactionReceipt> action) {
        long start = System.nanoTime();
        TransactionReceipt receipt = action.get();
        double latency = (System.nanoTime() - start) / 1_000_000.0;
        boolean ok = receipt != null && receipt.isStatusOK();
        long bytes = receipt == null ? 0 : ledgerBytes(receipt);
        long gas = receipt == null ? 0 : parseQuantity(receipt.getGasUsed());
        String block = receipt == null || receipt.getBlockNumber() == null ? "-1" : receipt.getBlockNumber().toString();
        String hash = receipt == null ? "" : receipt.getTransactionHash();
        int status = receipt == null ? -1 : receipt.getStatus();
        txWriter.printf("%s,%d,%d,%s,%s,%d,%.6f,%d,%d,%s,%d,%s%n",
                protocol, n, run, auditMode, phase, txIndex, latency, bytes, gas, block, status, hash);
        txWriter.flush();
        if (!ok) {
            throw new IllegalStateException("transaction failed: " + protocol + " " + phase + " status=" + status
                    + " message=" + (receipt == null ? "null receipt" : receipt.getMessage()));
        }
        return new TxObservation(latency, bytes, gas, ok, receipt);
    }

    private static double percentile(List<Double> values, double p) {
        if (values.isEmpty()) return Double.NaN;
        List<Double> sorted = new ArrayList<>(values);
        Collections.sort(sorted);
        double index = p * (sorted.size() - 1);
        int lo = (int)Math.floor(index), hi = (int)Math.ceil(index);
        if (lo == hi) return sorted.get(lo);
        return sorted.get(lo) * (hi - index) + sorted.get(hi) * (index - lo);
    }

    private void writeTask(
            String protocol, int n, int run, String auditMode, long startNs,
            BigInteger blockStart, BigInteger blockEnd, TxAggregate agg, String address) {
        double activeMs = (System.nanoTime() - startNs) / 1_000_000.0;
        taskWriter.printf("%s,%d,%d,%s,%.6f,%d,%.6f,%.6f,%d,%d,%s,%s,%s,%s%n",
                protocol, n, run, auditMode, activeMs, agg.txCount,
                percentile(agg.latencyMs, 0.5), percentile(agg.latencyMs, 0.95),
                agg.ledgerBytes, agg.gasUsed, blockStart.toString(), blockEnd.toString(),
                Boolean.toString(agg.valid), address);
        taskWriter.flush();
    }

    private void runIRPP(int n, int run, String auditMode) {
        byte[] taskId = digest("IRPP:" + n + ":" + run + ":" + auditMode + ":" + System.nanoTime());
        TxAggregate agg = new TxAggregate();
        BigInteger blockStart = client.getBlockNumber().getBlockNumber();
        long start = System.nanoTime();
        int index = 0;
        agg.add(observe("IRPP-TD", n, run, auditMode, "publish", index++,
                () -> irpp.publishTask(taskId, randomBytes(32), BigInteger.valueOf(n))));
        for (int i = 0; i < n; i++) {
            final int worker = i;
            agg.add(observe("IRPP-TD", n, run, auditMode, "credential_refresh", index++,
                    () -> irpp.reserveCredential(taskId,
                            digest("pred:" + run + ":" + auditMode + ":" + worker + ":" + System.nanoTime()),
                            randomBytes(32))));
        }
        agg.add(observe("IRPP-TD", n, run, auditMode, "input_close", index++,
                () -> irpp.closeInput(taskId, randomBytes(32), BigInteger.valueOf(n))));
        agg.add(observe("IRPP-TD", n, run, auditMode, "output_commit", index++,
                () -> irpp.commitOutput(taskId, randomBytes(32), randomBytes(32), randomBytes(32))));
        if (!"normal".equals(auditMode)) {
            if ("challenged".equals(auditMode) || "delayed".equals(auditMode)) {
                agg.add(observe("IRPP-TD", n, run, auditMode, "challenge", index++,
                        () -> irpp.challenge(taskId, randomBytes(32), randomBytes(32))));
            }
            final byte[] correctDigest = randomBytes(32);
            for (int j = 0; j < 5; j++) {
                final int auditor = j;
                agg.add(observe("IRPP-TD", n, run, auditMode, "audit_vote", index++,
                        () -> irppAuditors.get(auditor).auditVote(
                                taskId, BigInteger.ONE, true, correctDigest)));
            }
        }
        // Every non-normal path is a malicious-DR fault-injection path.  A
        // proactive audit therefore finalizes the corrected digest just as a
        // worker-triggered audit does; only the trigger message differs.
        final boolean corrected = !"normal".equals(auditMode);
        agg.add(observe("IRPP-TD", n, run, auditMode, "settle", index++,
                () -> irpp.finalize(taskId, corrected)));
        writeTask("IRPP-TD", n, run, auditMode, start, blockStart,
                client.getBlockNumber().getBlockNumber(), agg, irpp.getContractAddress());
    }

    private void runBSIF(int n, int run) {
        byte[] taskId = digest("BSIF:" + n + ":" + run + ":" + System.nanoTime());
        TxAggregate agg = new TxAggregate();
        BigInteger blockStart = client.getBlockNumber().getBlockNumber();
        long start = System.nanoTime();
        int index = 0;
        agg.add(observe("BSIF", n, run, "normal", "publish", index++,
                () -> bsif.publishTask(taskId, randomBytes(payloadBytes + 28), randomBytes(32), BigInteger.valueOf(n))));
        for (int i = 0; i < n; i++) {
            final int worker = i;
            agg.add(observe("BSIF", n, run, "normal", "encrypted_upload", index++,
                    () -> bsif.uploadReport(taskId, digest("bsif-worker:" + worker), randomBytes(bsifReportBytes))));
        }
        agg.add(observe("BSIF", n, run, "normal", "quality_report", index++,
                () -> bsif.submitQuality(taskId, randomBytes(32))));
        for (int i = 0; i < n; i++) {
            final int worker = i;
            agg.add(observe("BSIF", n, run, "normal", "reputation_update", index++,
                    () -> bsif.updateReputation(digest("bsif-worker:" + worker), BigInteger.valueOf(700_000))));
        }
        agg.add(observe("BSIF", n, run, "normal", "settle", index++,
                () -> bsif.settle(taskId, randomBytes(32))));
        writeTask("BSIF", n, run, "normal", start, blockStart,
                client.getBlockNumber().getBlockNumber(), agg, bsif.getContractAddress());
    }

    private void runRPPS(int n, int run) {
        byte[] taskId = digest("RPPS:" + n + ":" + run + ":" + System.nanoTime());
        TxAggregate agg = new TxAggregate();
        BigInteger blockStart = client.getBlockNumber().getBlockNumber();
        long start = System.nanoTime();
        int index = 0;
        agg.add(observe("RPPS-TDC", n, run, "normal", "publish", index++,
                () -> rpps.publishTask(taskId, randomBytes(payloadBytes + 28), randomBytes(32), BigInteger.valueOf(n))));
        for (int i = 0; i < n; i++) {
            final int worker = i;
            agg.add(observe("RPPS-TDC", n, run, "normal", "encrypted_upload", index++,
                    () -> rpps.uploadReport(taskId, digest("rpps-worker:" + worker), randomBytes(rppsReportBytes))));
        }
        agg.add(observe("RPPS-TDC", n, run, "normal", "trust_update", index++,
                () -> rpps.commitTrust(taskId, randomBytes(32))));
        agg.add(observe("RPPS-TDC", n, run, "normal", "selection", index++,
                () -> rpps.commitSelection(taskId, randomBytes(32))));
        agg.add(observe("RPPS-TDC", n, run, "normal", "result", index++,
                () -> rpps.commitResult(taskId, randomBytes(32))));
        for (int i = 0; i < n; i++) {
            final int worker = i;
            agg.add(observe("RPPS-TDC", n, run, "normal", "reputation_update", index++,
                    () -> rpps.updateReputation(digest("rpps-worker:" + worker), BigInteger.valueOf(700_000))));
        }
        agg.add(observe("RPPS-TDC", n, run, "normal", "settle", index++,
                () -> rpps.settle(taskId, randomBytes(32))));
        writeTask("RPPS-TDC", n, run, "normal", start, blockStart,
                client.getBlockNumber().getBlockNumber(), agg, rpps.getContractAddress());
    }

    private void registerWorkers(int maxWorkers) {
        for (int i = 0; i < maxWorkers; i++) {
            final int worker = i;
            TxObservation b = observe("BSIF", 0, 0, "setup", "register_worker", i,
                    () -> bsif.registerWorker(digest("bsif-worker:" + worker), BigInteger.valueOf(700_000)));
            deploymentWriter.printf("BSIF,worker_registration,%.6f,%d,%d,%s,%s%n",
                    b.latencyMs, b.ledgerBytes, b.gasUsed, b.receipt.getBlockNumber(), bsif.getContractAddress());
            TxObservation r = observe("RPPS-TDC", 0, 0, "setup", "register_worker", i,
                    () -> rpps.registerWorker(digest("rpps-worker:" + worker), BigInteger.valueOf(700_000)));
            deploymentWriter.printf("RPPS-TDC,worker_registration,%.6f,%d,%d,%s,%s%n",
                    r.latencyMs, r.ledgerBytes, r.gasUsed, r.receipt.getBlockNumber(), rpps.getContractAddress());
        }
        deploymentWriter.flush();
    }

    private void registerAuditors(int count) {
        for (int i = 0; i < count; i++) {
            final int auditor = i;
            TxObservation a = observe("IRPP-TD", 0, 0, "setup", "register_auditor", i,
                    () -> irpp.registerAuditor(irppAuditorKeys.get(auditor).getAddress()));
            deploymentWriter.printf("IRPP-TD,auditor_registration,%.6f,%d,%d,%s,%s%n",
                    a.latencyMs, a.ledgerBytes, a.gasUsed, a.receipt.getBlockNumber(), irpp.getContractAddress());
        }
        deploymentWriter.flush();
    }

    private static void requireSuccess(String label, TransactionReceipt receipt) {
        if (receipt == null || !receipt.isStatusOK()) {
            throw new IllegalStateException("preflight unexpectedly failed: " + label);
        }
    }

    private static void requireFailure(String label, Supplier<TransactionReceipt> action) {
        try {
            TransactionReceipt receipt = action.get();
            if (receipt != null && receipt.isStatusOK()) {
                throw new IllegalStateException("preflight unexpectedly succeeded: " + label);
            }
        } catch (RuntimeException expected) {
            // Generated wrappers may throw for a reverted receipt.  An
            // explicit unexpectedly-succeeded exception must still escape.
            if (expected.getMessage() != null && expected.getMessage().startsWith("preflight unexpectedly succeeded")) {
                throw expected;
            }
        }
    }

    private void auditGuardSelfTest() {
        byte[] taskId = digest("IRPP-PREFLIGHT-GUARD:" + System.nanoTime());
        requireSuccess("publish guard task", irpp.publishTask(taskId, randomBytes(32), BigInteger.ZERO));
        requireSuccess("close guard task", irpp.closeInput(taskId, randomBytes(32), BigInteger.ZERO));
        requireSuccess("commit guard task", irpp.commitOutput(taskId, randomBytes(32), randomBytes(32), randomBytes(32)));
        requireSuccess("challenge guard task", irpp.challenge(taskId, randomBytes(32), randomBytes(32)));
        // Advance at least one block so failure cannot be attributed only to
        // the next-block challenge-window gate.
        requireSuccess("advance guard block", irpp.publishTask(
                digest("IRPP-PREFLIGHT-ADVANCE:" + System.nanoTime()), randomBytes(32), BigInteger.ZERO));
        requireFailure("unresolved challenge finalized false", () -> irpp.finalize(taskId, false));

        byte[] agreedDigest = randomBytes(32);
        for (int i = 0; i < 3; i++) {
            requireSuccess("agreed audit vote " + i,
                    irppAuditors.get(i).auditVote(taskId, BigInteger.ONE, true, agreedDigest));
        }
        requireFailure("authorized correction bypassed by finalize(false)", () -> irpp.finalize(taskId, false));
        requireSuccess("authorized correction finalized true", irpp.finalize(taskId, true));

        byte[] mismatchId = digest("IRPP-PREFLIGHT-MISMATCH:" + System.nanoTime());
        requireSuccess("publish mismatch task", irpp.publishTask(mismatchId, randomBytes(32), BigInteger.ZERO));
        requireSuccess("close mismatch task", irpp.closeInput(mismatchId, randomBytes(32), BigInteger.ZERO));
        requireSuccess("commit mismatch task", irpp.commitOutput(mismatchId, randomBytes(32), randomBytes(32), randomBytes(32)));
        for (int i = 0; i < 3; i++) {
            requireSuccess("mismatched audit vote " + i,
                    irppAuditors.get(i).auditVote(mismatchId, BigInteger.ONE, true, randomBytes(32)));
        }
        requireFailure("three disagreeing digests authorized correction", () -> irpp.finalize(mismatchId, true));
        System.out.println("PREFLIGHT IRPP audit identity/digest/finalization guards PASS");
    }

    private void throughputIRPP(int burst, int transactions) throws Exception {
        byte[] taskId = digest("IRPP-TP:" + burst + ":" + System.nanoTime());
        irpp.publishTask(taskId, randomBytes(32), BigInteger.valueOf(transactions));
        runAsyncBurst("IRPP-TD", burst, transactions, 96,
                callbackIndex -> irpp.reserveCredential(taskId,
                        digest("tp-pred:" + burst + ":" + callbackIndex + ":" + System.nanoTime()),
                        randomBytes(32), callbackIndex.callback));
    }

    private void throughputBSIF(int burst, int transactions) throws Exception {
        byte[] taskId = digest("BSIF-TP:" + burst + ":" + System.nanoTime());
        bsif.publishTask(taskId, randomBytes(payloadBytes + 28), randomBytes(32), BigInteger.valueOf(transactions));
        runAsyncBurst("BSIF", burst, transactions, bsifReportBytes,
                callbackIndex -> bsif.uploadReport(taskId,
                        digest("bsif-tp-worker:" + burst + ":" + callbackIndex.index),
                        randomBytes(bsifReportBytes), callbackIndex.callback));
    }

    private void throughputRPPS(int burst, int transactions) throws Exception {
        byte[] taskId = digest("RPPS-TP:" + burst + ":" + System.nanoTime());
        rpps.publishTask(taskId, randomBytes(payloadBytes + 28), randomBytes(32), BigInteger.valueOf(transactions));
        runAsyncBurst("RPPS-TDC", burst, transactions, rppsReportBytes,
                callbackIndex -> rpps.uploadReport(taskId,
                        digest("rpps-tp-worker:" + burst + ":" + callbackIndex.index),
                        randomBytes(rppsReportBytes), callbackIndex.callback));
    }

    private interface AsyncSender {
        String send(CallbackIndex value);
    }

    private static final class CallbackIndex {
        final int index;
        final TransactionCallback callback;
        CallbackIndex(int index, TransactionCallback callback) { this.index = index; this.callback = callback; }
    }

    private void runAsyncBurst(String protocol, int burst, int transactions, int payload, AsyncSender sender) throws Exception {
        CountDownLatch latch = new CountDownLatch(transactions);
        AtomicInteger successes = new AtomicInteger();
        AtomicLong bytes = new AtomicLong();
        long start = System.nanoTime();
        for (int i = 0; i < transactions; i++) {
            final long submitted = System.nanoTime();
            TransactionCallback callback = new TransactionCallback() {
                @Override public void onResponse(TransactionReceipt receipt) {
                    if (receipt != null && receipt.isStatusOK()) successes.incrementAndGet();
                    if (receipt != null) bytes.addAndGet(ledgerBytes(receipt));
                    latch.countDown();
                }
                @Override public void onError(int error, String message) { latch.countDown(); }
                @Override public void onTimeout() { latch.countDown(); }
            };
            callback.setTimeout(120_000);
            sender.send(new CallbackIndex(i, callback));
        }
        if (!latch.await(180, TimeUnit.SECONDS)) {
            throw new IllegalStateException("throughput burst timeout: " + protocol);
        }
        double wallMs = (System.nanoTime() - start) / 1_000_000.0;
        double tps = successes.get() / (wallMs / 1000.0);
        throughputWriter.printf("%s,%d,%d,%d,%.6f,%.6f,%d,%d%n",
                protocol, burst, transactions, payload, wallMs, tps, successes.get(), bytes.get());
        throughputWriter.flush();
    }

    private void close() {
        txWriter.close();
        taskWriter.close();
        deploymentWriter.close();
        throughputWriter.close();
    }

    public static void main(String[] args) throws Exception {
        if (args.length != 9) {
            System.err.println("Usage: RQ5LedgerRunner CONFIG OUT RUNS NCSV DIM PAYLOAD WARMUPS BURSTS BURST_TX");
            System.exit(2);
        }
        String config = args[0];
        File output = new File(args[1]);
        int runs = Integer.parseInt(args[2]);
        String[] nParts = args[3].split(",");
        int dimension = Integer.parseInt(args[4]);
        int payload = Integer.parseInt(args[5]);
        int warmups = Integer.parseInt(args[6]);
        int bursts = Integer.parseInt(args[7]);
        int burstTx = Integer.parseInt(args[8]);
        int maxWorkers = 0;
        for (String value : nParts) maxWorkers = Math.max(maxWorkers, Integer.parseInt(value));

        BcosSDK sdk = BcosSDK.build(config);
        try {
            Client client = sdk.getClient("group0");
            CryptoKeyPair credential = client.getCryptoSuite().getCryptoKeyPair();

            long t0 = System.nanoTime();
            IRPPWorkflow irpp = IRPPWorkflow.deploy(client, credential);
            double irppDeployMs = (System.nanoTime() - t0) / 1_000_000.0;
            List<CryptoKeyPair> irppAuditorKeys = new ArrayList<>();
            List<IRPPWorkflow> irppAuditors = new ArrayList<>();
            for (int i = 0; i < 5; i++) {
                CryptoKeyPair auditorKey = client.getCryptoSuite().generateRandomKeyPair();
                irppAuditorKeys.add(auditorKey);
                irppAuditors.add(IRPPWorkflow.load(irpp.getContractAddress(), client, auditorKey));
            }
            t0 = System.nanoTime();
            BSIFWorkflow bsif = BSIFWorkflow.deploy(client, credential);
            double bsifDeployMs = (System.nanoTime() - t0) / 1_000_000.0;
            t0 = System.nanoTime();
            RPPSWorkflow rpps = RPPSWorkflow.deploy(client, credential);
            double rppsDeployMs = (System.nanoTime() - t0) / 1_000_000.0;

            RQ5LedgerRunner runner = new RQ5LedgerRunner(
                    client, credential, irpp, irppAuditors, irppAuditorKeys,
                    bsif, rpps, output, dimension, payload);
            runner.deploymentWriter.printf("IRPP-TD,contract_deployment,%.6f,%d,%d,%s,%s%n",
                    irppDeployMs, ledgerBytes(irpp.getDeployReceipt()), parseQuantity(irpp.getDeployReceipt().getGasUsed()),
                    irpp.getDeployReceipt().getBlockNumber(), irpp.getContractAddress());
            runner.deploymentWriter.printf("BSIF,contract_deployment,%.6f,%d,%d,%s,%s%n",
                    bsifDeployMs, ledgerBytes(bsif.getDeployReceipt()), parseQuantity(bsif.getDeployReceipt().getGasUsed()),
                    bsif.getDeployReceipt().getBlockNumber(), bsif.getContractAddress());
            runner.deploymentWriter.printf("RPPS-TDC,contract_deployment,%.6f,%d,%d,%s,%s%n",
                    rppsDeployMs, ledgerBytes(rpps.getDeployReceipt()), parseQuantity(rpps.getDeployReceipt().getGasUsed()),
                    rpps.getDeployReceipt().getBlockNumber(), rpps.getContractAddress());
            runner.deploymentWriter.flush();
            runner.registerAuditors(5);
            runner.auditGuardSelfTest();
            runner.registerWorkers(maxWorkers);

            for (int warm = 0; warm < warmups; warm++) {
                runner.runIRPP(3, -1 - warm, "normal");
                runner.runBSIF(3, -1 - warm);
                runner.runRPPS(3, -1 - warm);
            }
            for (String value : nParts) {
                int n = Integer.parseInt(value);
                for (int run = 0; run < runs; run++) {
                    int rotation = run % 3;
                    if (rotation == 0) { runner.runIRPP(n, run, "normal"); runner.runBSIF(n, run); runner.runRPPS(n, run); }
                    if (rotation == 1) { runner.runBSIF(n, run); runner.runRPPS(n, run); runner.runIRPP(n, run, "normal"); }
                    if (rotation == 2) { runner.runRPPS(n, run); runner.runIRPP(n, run, "normal"); runner.runBSIF(n, run); }
                    System.out.printf("CHAIN n=%d run=%d/%d%n", n, run + 1, runs);
                }
            }
            boolean has27 = false;
            for (String value : nParts) if (Integer.parseInt(value) == 27) has27 = true;
            if (has27) {
                for (int run = 0; run < runs; run++) {
                    runner.runIRPP(27, run, "proactive");
                    runner.runIRPP(27, run, "challenged");
                    runner.runIRPP(27, run, "delayed");
                }
            }
            for (int burst = 0; burst < bursts; burst++) {
                int rotation = burst % 3;
                if (rotation == 0) { runner.throughputIRPP(burst, burstTx); runner.throughputBSIF(burst, burstTx); runner.throughputRPPS(burst, burstTx); }
                if (rotation == 1) { runner.throughputBSIF(burst, burstTx); runner.throughputRPPS(burst, burstTx); runner.throughputIRPP(burst, burstTx); }
                if (rotation == 2) { runner.throughputRPPS(burst, burstTx); runner.throughputIRPP(burst, burstTx); runner.throughputBSIF(burst, burstTx); }
                System.out.printf("THROUGHPUT burst=%d/%d%n", burst + 1, bursts);
            }
            runner.close();
        } finally {
            sdk.stopAll();
        }
    }
}
