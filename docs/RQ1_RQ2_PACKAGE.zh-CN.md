# IRPP-TD clean reproducibility package

本文件夹汇总论文当前使用的 IRPP-TD、RQ1/RQ2、基线适配与数据预处理代码。整理过程未删除原始工程；旧版、失效或重复文件仅未纳入本包。

## IRPP-TD 简介

IRPP-TD 为每个工人维护正先验三元 Dirichlet 状态
`(alpha_h, alpha_u, alpha_l)`，分别累计高质量、不确定质量和低质量证据。
历史状态先生成含认识不确定性的信誉分数；达到条件的工人作为 RABOD
角度筛查锚点。当前报告被标记后，系统仅保留高质量报告以及信誉合格的
不确定报告，再用有界迭代真值发现得到任务真值。当前标签最后写入状态，
供下一任务使用，因此不存在同一任务内的顺序依赖。

本版把原来分散在 RQ1/RQ2 中的固定样本 TV 估计统一为
`irpp_core/reputation.py` 中的混合算法：先以固定状态种子执行 `M=1024`
分层 Monte Carlo；若信誉阈值决策不能由 family-wise Hoeffding 区间认证，
则转入确定性 sliced Dirichlet-TV 求积。结果按状态和数值参数缓存。

## 目录

- `irpp_core/`：共享 Dirichlet-TV 与信誉评分实现。
- `experiments/rq1/`：准确性、运行时间、阶段统计和 Fig. 4 绘图代码。
- `experiments/rq2/`：冷启动、恶意比例、早期错误与状态切换实验的最终 reorganized 版本。
- `baselines/`：RQ1 适配器实际调用的九个基线源文件。
- `data/workloads/`：六个已处理 workload，覆盖三类数据和目标参与度 27/39。
- `data_processing/`：真实传感数据与 SUMO 轨迹的预处理脚本；大型原始数据不重复打包。
- `tests/`：共享 TV 算法测试。
- `docs/`：逐文件说明、验证摘要和附录正式修改方案。

## 环境与运行

建议使用 Python 3.9：

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

先运行快速检查：

```powershell
python tests/test_hybrid_tv.py
python experiments/rq2/tests/test_reorganized.py
```

RQ1 完整重跑：

```powershell
python experiments/rq1/run_rq1.py --stage all --force
python experiments/rq1/analyze_rq1.py
python experiments/rq1/plot_rq1.py
```

RQ2 最小 smoke run 与正式运行：

```powershell
python experiments/rq2/run_rq2_reorganized.py --seed-count 1 --task-limit 10 --output-tag smoke
python experiments/rq2/run_rq2_reorganized.py --task-limit 100 --output-tag formal
python experiments/rq2/analyze_rq2_reorganized.py
python experiments/rq2/plot_rq2_reorganized.py
python experiments/rq2/final_audit.py
```

完整运行会生成相应结果文件。旧固定样本 TV 实现产生的汇总未混入新实现，
所有 RQ1/RQ2 结果应由正式运行重新生成。

论文中的 RDPP-TD 对比按照原作者提供的代码包在独立环境中完成。为遵守
原作者关于代码隐私与安全的声明，本公开包不包含、转发或改写其实现、专用
实验脚本及输入；因此，包内自动重跑和 Fig. 4(d) 重绘不生成 RDPP-TD 数据点。

## 清理原则

本包只保留当前调用链。被排除的主要内容包括旧 RQ2 实验目录、RQ1 的重复副本、
`__pycache__`/`.pyc`、失效的早期 IRPP 自导入脚本、重复 PDF/PNG/SVG/TIFF、
临时日志以及大型 SUMO 路由和原始数据。基线文件名中的历史拼写
`BLAND/mian_system.py` 被保留，因为适配器按该名称加载；它不是重复副本。

详细文件职责见 `docs/CODE_GUIDE.md`，附录插入方案见
`docs/APPENDIX_TV_MODIFICATION_PLAN.md`。
