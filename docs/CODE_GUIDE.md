# 代码说明

IRPP-TD 先用受限随机 ABOD 对报告进行任务内筛查，再以三状态 Dirichlet
历史更新工人信誉，并仅将通过筛查或满足信誉条件的报告送入有界真值发现；
RQ5 进一步验证隐藏状态转换、链上承诺与阈值审计。各目录保留论文对应的冻结
参数、随机种子和结果分析脚本。

## 1. 共享核心

- `irpp_core/reputation.py`：实现混合 Dirichlet-TV 数值算法、阈值决策认证、
  sliced 一维求积、缓存和最终信誉分数。
- `irpp_core/__init__.py`：导出共享信誉类与数值结果结构。
- `tests/test_hybrid_tv.py`：检查均匀先验、阈值附近的确定性求积、固定种子和跨实例缓存。

## 2. RQ1

- `run_rq1.py`：加载六个 workload，冻结参数，运行 IRPP-TD 与基线并生成逐任务结果。
- `analyze_rq1.py`：生成配对比较、种子稳定性和主要结论统计。
- `plot_rq1.py`：生成 RQ1 主图、诊断图及其多种出版格式。
- `config.json`：实验任务范围、随机种子、基线列表、参数和 TV 数值设置。
- `src/data_utils.py`：解析 workload、稳健归一化、输入摘要与哈希辅助函数。
- `src/irpp_td.py`：RQ1 的顺序 IRPP-TD；已调用共享混合 TV 信誉类。
- `src/legacy_adapters.py`：把各基线统一为同一种任务输入/输出接口。
- `src/metrics.py`：NRMSE/NMAE、阶段汇总和 bootstrap 置信区间。
- `src/tuning.py`：只在校准任务上选择冻结参数，避免测试信息泄漏。
- `results/frozen_parameters.json`：论文使用的冻结参数。
- `metadata/workload_manifest.json`：输入哈希、维度、参与度和归一化常数。

## 3. RQ2

- `run_rq2_reorganized.py`：运行冷启动、恶意比例、早期错误、H-to-L/L-to-H 切换实验。
- `analyze_rq2_reorganized.py`：从正式逐任务结果生成置信区间和事件统计。
- `plot_rq2_reorganized.py`：生成正文及补充材料中的 RQ2 图。
- `final_audit.py`：核对结果文件、配置、汇总表和运行审计的一致性。
- `config.json`：参与度 27/39、30 个种子、攻击比例、切换任务和三种冷启动策略。
- `src/data.py`：保留原 SUMO 参与关系并重放受控报告、工人类型和切换事件。
- `src/core_base.py`：公共参数、RABOD、真值发现和信誉接口；Full 模式已接入共享混合 TV。
- `src/model.py`：最终 reorganized IRPP-TD 闭环及 Adaptive-HQ/No-Extra/Random-Extra 策略。
- `tests/test_reorganized.py`：检查参与关系、活动平衡、报告生成规则和三种策略的最小运行。
- `results/`：运行输出目录；旧 TV 实现产生的历史汇总未纳入本包。

## 4. RQ3

- `run_rq3.py`：运行恶意参与率与攻击强度主实验。
- `run_mode_baselines.py`、`run_calibrated_baselines.py`：运行模式攻击及校准基线。
- `run_mode_leakage_baselines.py`、`run_rpps_calibrated_leakage.py`：运行泄漏敏感性对比。
- `src/rq3_data.py`：从共享 workload 生成可复现的攻击重放。
- `src/rq3_model.py`：IRPP-TD 鲁棒性实验闭环。
- `analyze_rq3.py`、`validate_rq3.py`：汇总统计并检查完整性。
- `plot_rq3.py`、`make_rq3_tables.py`：生成 RQ3 图表。

## 5. RQ4

- `run_rq4.py`：运行角度预算、停止条件、稳定性与可扩展性实验。
- `run_rq4_boundaries.py`：运行输入边界和组件消融。
- `src/rq4_core.py`：RQ4 使用的冻结 IRPP-TD/RABOD/TD 实现及数值保护。
- `analyze_rq4.py`、`plot_rq4.py`：生成统计摘要和论文图件。
- `tests/test_rq4.py`：检查聚合附近、相同报告、秩一回退和有限数值。

## 6. RQ5 与区块链

- `python/protocols.py`、`algorithms.py`：四种协议的离线执行与聚合路径。
- `python/run_offchain.py`：运行匹配负载下的离线计时。
- `contracts/*.sol`：IRPP-TD、BSIF 和 RPPS-TDC 的链上工作流。
- `java/src/rq5/RQ5LedgerRunner.java`：提交交易、确认、存储与 TPS 测量。
- `scripts/*.sh`：编译 NTRU+、合约包装和 Java 客户端并运行链上实验。
- `python/run_fault_injection.py`：检查错误标签、权重、状态、聚合与付款处理。
- `python/analyze_rq5.py`、`plot_rq5.py`、`generate_rq5_tables.py`：完整性检查与图表生成。
- `blockchain/fisco_bcos/`：FISCO BCOS 3.7.3 四节点 PBFT/WSL 安装脚本、版本锁和哈希清单；不包含生成的证书或链数据库。

## 7. 基线

- `baselines/CRH/CRH.py`、`CRH-N.py`：CRH 与归一化 CRH。
- `baselines/QE/main_system.py`：QE 筛查和聚合。
- `baselines/BLAND/mian_system.py`：BLIND 聚类基线；保留原历史文件名。
- `baselines/PRTD/main_system.py`：PRTD 基线。
- `baselines/RTD/main_system.py`：信誉真值发现基线。
- `baselines/RPPS-TDC/main_system.py`：RPPS-TDC 主流程。
- `baselines/RPPS-TDC/reputation_update.py`：其信誉更新。
- `baselines/RPPS-TDC/truth_discovery.py`：其真值聚合。

`Mean` 和 `Median` 直接由 `src/legacy_adapters.py` 计算，因此没有独立源文件。

RDPP-TD 对比按照原作者提供的代码包在独立环境中执行。依据原作者关于代码
隐私与安全的声明，本公开包不包含其实现、专用实验脚本或输入；包内绘图也不
生成 RDPP-TD 数据点。

基线示例默认读取 `data/workloads/`；可用环境变量 `IRPP_WORKLOAD` 指定另一
个兼容 workload。

## 8. 数据与预处理

- `data/workloads/Scene_{1,2,3}_Number_of_Workers_{27,39}.json`：三类数据、两种参与度的实验输入。
- `data_processing/sensors/ClimatePreprocess.py`：Climate 清洗与特征构造。
- `data_processing/sensors/ClimateVisualization.py`：Climate 数据诊断图。
- `data_processing/sensors/TrafficPreprocess.py`：Traffic 清洗与特征构造。
- `data_processing/sensors/TrafficVisualization.py`：Traffic 数据诊断图。
- `data_processing/sensors/WaterQualityPreprocess.py`：Water 清洗与特征构造。
- `data_processing/sumo/RunSUMO.py`：运行 SUMO 场景。
- `data_processing/sumo/ConvertSUMOToGrids.py`：把 SUMO 轨迹转为任务网格/参与关系。

预处理脚本需要原始公开数据或 LuST/SUMO 场景；为避免冗余和超大包，这些外部原始文件未复制。
SUMO 入口通过 `IRPP_SUMO_CONFIG` 接收 `.sumocfg` 路径，传感器脚本默认从
`data/raw/` 读取并写入 `data/processed/`。
