# 附录 Dirichlet-TV 数值算法正式修改方案

## 修改目标

审稿意见的核心不是式子的定义，而是式 (6)/Algorithm 1 无法据此复现：目前没有
样本数、数值路径、容差、误差控制、缓存范围和成本说明。建议只修改补充材料
Appendix C，在现有 `U_i` 与 `psi_i` 定义之后、`Dirichlet-state validity`
Lemma 之前加入一个紧凑小节；正文公式和 Algorithm 1 均不改，以控制篇幅。

建议标题：

```latex
\paragraph{Numerical evaluation of Dirichlet-TV uncertainty.}
```

## 应加入的技术内容

### 快速估计与可复现性

令 `p_A` 为 `Dir(A)` 密度，均匀参考密度为 `u(x)=2`，并令
`q_A=(p_A+u)/2`。使用恒等式

```latex
\chi(A)=\TV(\Dir(A),\Dir(1,1,1))
=\mathbb E_{X\sim q_A}
\!\left[\frac{|p_A(X)-2|}{p_A(X)+2}\right].
```

对每个新浓度状态，固定由三元组 `A` 导出的随机种子，分别从 `Dir(A)` 和
`Dir(1,1,1)` 抽取 `M/2=512` 个样本，得到 `M=1024` 的分层估计。
密度比用对数域
`abs(tanh((log p_A(x)-log 2)/2))` 计算，避免溢出。

### family-wise 误差控制与阈值保护

在最多 `T=100` 次更新时，正整数浓度状态数不超过
`K_max=binom(T+3,3)=176851`。取总体失败概率 `delta=0.05`，Hoeffding 给出

```latex
r_U=\sqrt{\frac{\log(2K_{\max}/\delta)}{2M}}
=0.0877562,
```

从而所有访问状态的 `U=1-chi` 同时落在
`[U_hat-r_U,U_hat+r_U] cap [0,1]` 内的概率至少为 0.95。
将该区间通过式 (score) 关于 `U` 的二次函数精确映射：检查两个端点与区间内
可能的驻点。若得到的信誉分数区间不跨越 `theta=0.35`，直接采用快速估计；
否则进入确定性求积。因此 MC 误差不会在认证事件上改变阈值分支。

### 阈值附近的确定性 sliced 求积

定义超水平集 `D_A={x in Delta_2:p_A(x)>=2}`，则

```latex
\chi(A)=\Pr_{\Dir(A)}(D_A)-\Pr_{\Dir(1,1,1)}(D_A).
```

令 `x_h=s, x_u=(1-s)t, x_l=(1-s)(1-t)`。对每个 Gauss--Legendre
节点 `s`，用 64 次二分求解至多两个 `p_A=2` 的 `t` 边界；`t` 方向的
Dirichlet 条件质量由正则化不完全 Beta 函数解析计算，只对剩余的一维 `s`
积分进行 Gauss--Legendre 求积。阶数依次为
`128,256,...,8192`；连续两次相邻阶结果差不超过 `tau=10^{-6}` 时停止。
若最高阶仍未满足该准则，实现会显式报错而不会静默接受数值结果。
这里 `tau` 是明确的后验数值收敛准则；MC 部分的概率误差则由上面的
family-wise Hoeffding 界控制。

### 缓存与复杂度

缓存键应为浓度三元组以及 `M,delta,T,tau,theta,zeta` 和求积阶数表。
先验 `(1,1,1)` 精确返回 `chi=0`。平均缓存查询为 `O(1)`；每个未见状态的
快速阶段时间/空间为 `O(M)`；触发求积时，总时间为 `O(Q_max I)`，其中
`I=64` 为二分次数，几何递增阶数之和为 `O(Q_max)`。若运行中访问 `K`
个不同状态，缓存空间为 `O(K)`。同一状态在不同工人和任务间复用。

## 可直接插入的英文压缩稿

```latex
\paragraph{Numerical evaluation of Dirichlet-TV uncertainty.}
Let $p_A$ denote the $\Dir(A)$ density and let $u(x)=2$ on
$\Delta_2$. With $q_A=(p_A+u)/2$,
\[
\chi(A)=\mathbb E_{X\sim q_A}
\left[|p_A(X)-2|/(p_A(X)+2)\right].
\]
For each unseen integer state $A$, we use a state-seeded stratified estimate
with $M/2$ draws from each component ($M=1024$), evaluated in the log domain.
For horizon $T=100$, at most $K_{\max}=\binom{T+3}{3}=176851$ states are
reachable. With family-wise $\delta=0.05$, Hoeffding's inequality gives the
simultaneous radius
$r_U=\sqrt{\log(2K_{\max}/\delta)/(2M)}=0.0877562$ for
$\mathcal U=1-\chi$. We map the clipped interval
$[\widehat{\mathcal U}-r_U,\widehat{\mathcal U}+r_U]$ exactly through the
quadratic score in~\eqref{eq:score}, evaluating both endpoints and any interior
stationary point. The estimate is accepted when this score interval excludes
$\theta$.

Otherwise, we compute $\chi(A)=P_A(D_A)-P_0(D_A)$ for
$D_A=\{x:p_A(x)\ge2\}$. Under
$x_h=s,x_u=(1-s)t,x_l=(1-s)(1-t)$, the at-most-two $t$ boundaries are found
by 64 bisection steps; conditional masses are evaluated by the regularized
incomplete Beta function, leaving a one-dimensional Gauss--Legendre rule in
$s$. Orders $128,256,\ldots,8192$ are doubled until two consecutive changes
are at most $\tau=10^{-6}$; failure at the maximum order raises an error.
Results are cached by $A$ and all numerical
parameters; $(1,1,1)$ is exact. A cache hit is $O(1)$, a new certified state
costs $O(M)$, a fallback costs $O(Q_{\max}\cdot64)$, and $K$ visited states
use $O(K)$ cache space.
```

## 建议追加的一句验证说明

紧接上述段落增加一句即可，不另设表格：

```latex
Across the six retained workloads, 241 of 7,005 non-prior states (3.44\%)
required quadrature; all met $\tau$, no threshold decision differed from the
high-order reference, and the median cold-cache overhead was 1.66\% per task.
```

完整验证还得到：599,940 次 TV 调用、14,400 个 held-out 任务/种子评估中
结构不匹配为 0、NRMSE 不匹配为 0；241 个求积状态最高使用 4096 阶。
这些扩展数字放在代码包 `TV_VALIDATION_REPORT.md`，论文只保留上面一句即可。

## 一致性与篇幅控制

1. 正文式 (6) 与 Algorithm 1 保持不动；其 `Compute U_i` 由本段定义具体实现。
2. Appendix C 的现有范围、极限和有界性证明保持不动；新增算法不改变理论定义。
3. 参数 `M,T,delta,tau,theta` 必须与代码和验证报告一致。
4. 不把 `1e-6` 写成严格解析积分误差上界；它是连续阶求积的后验停止容差。
5. 建议新增内容控制在约半个双栏页面；若页数紧张，删除扩展验证数字，只保留
   压缩稿与一句验证结果。
