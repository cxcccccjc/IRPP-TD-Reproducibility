import numpy as np
import math
import time
from typing import Dict, List, Tuple, Union, Optional


def truth_discovery(worker_data: Dict[Union[str, int], List[float]],
                    worker_reputations: Dict[Union[str, int], float],
                    ground_truth: Optional[List[float]] = None,
                    p: float = 0.2,
                    epsilon: float = 1e-3,
                    max_iterations: int = 100) -> Tuple[
    List[float], Dict[Union[str, int], float], float, int, Optional[Dict[str, float]], Dict[Union[str, int], bool]]:
    """
    CRH真相发现算法模块（改进版本）

    参数:
    - worker_data: Dict, 工人数据字典，格式为 {worker_id: [data_vector]}
    - worker_reputations: Dict, 工人信誉字典，格式为 {worker_id: reputation_value}，信誉值在0-1之间
    - ground_truth: Optional[List[float]], 任务的真实值，可选参数
    - p: float, 数据质量判断阈值，默认0.2
    - epsilon: float, 收敛阈值，默认1e-6
    - max_iterations: int, 最大迭代次数，默认100

    返回:
    - aggregated_truth: List[float], 聚合后的真值
    - worker_weights: Dict, 每个工人的数据权重，格式为 {worker_id: weight}
    - execution_time: float, 真相发现的持续时间（秒）
    - iteration_count: int, 实际迭代次数
    - error_metrics: Optional[Dict[str, float]], 误差指标（如果提供了ground_truth），包含MAE、MSE、RMSE
    - data_quality_assessment: Dict, 每个工人数据质量评估，格式为 {worker_id: is_good_data}
    """

    start_time = time.perf_counter()

    # 提取工人ID和数据向量
    worker_ids = list(worker_data.keys())
    data_vectors = list(worker_data.values())

    # 验证信誉数据完整性
    if not all(worker_id in worker_reputations for worker_id in worker_ids):
        raise ValueError("所有工人都必须提供信誉值")

    # 转换为numpy数组
    data_matrix = np.array(data_vectors)
    m, d = data_matrix.shape

    # 初始化
    t = 0
    weights = np.ones(m)  # 初始权重为1
    # truth_estimate初始化为所有工人数据的平均值
    truth_estimate = np.mean(data_matrix, axis=0)

    # CRH算法迭代（使用修正后的聚合方法）
    while t < max_iterations:
        t += 1
        previous_truth = truth_estimate.copy()

        # 步骤1：计算距离平方
        distances_squared = np.sum((data_matrix - previous_truth) ** 2, axis=1)
        distances_squared = np.maximum(distances_squared, 1e-10)  # 避免数值问题

        # 步骤2：计算总距离平方和
        total_distance_squared = np.sum(distances_squared)
        total_distance_squared = max(total_distance_squared, 1e-10)  # 避免数值问题

        # 步骤3：更新权重
        log_total = math.log(total_distance_squared)
        new_weights = log_total - np.log(distances_squared)
        weights = new_weights

        # 步骤4：更新真值估计
        weighted_sum = np.sum(weights[:, np.newaxis] * data_matrix, axis=0)
        weight_sum = np.sum(weights)
        truth_estimate = weighted_sum / weight_sum

        # 步骤5：收敛性检查
        convergence_measure = np.linalg.norm(truth_estimate - previous_truth)
        print("1", truth_estimate)
        print("2", previous_truth)
        if convergence_measure < epsilon:
            print(convergence_measure)
            break

    # 计算执行时间
    end_time = time.perf_counter()
    execution_time = end_time - start_time

    # 构建基本结果
    aggregated_truth = truth_estimate.tolist()
    worker_weights = {worker_ids[i]: float(weights[i]) for i in range(len(worker_ids))}

    # 数据质量评估
    # 找到信誉最高的所有工人
    max_reputation = max(worker_reputations.values())
    highest_reputation_workers = [worker_id for worker_id, rep in worker_reputations.items() if rep == max_reputation]

    # 计算信誉最高工人的权重平均值
    highest_weights = [worker_weights[worker_id] for worker_id in highest_reputation_workers]
    w_highest_avg = np.mean(highest_weights)

    # 评估每个工人的数据质量
    data_quality_assessment = {}
    for worker_id in worker_ids:
        if worker_id in highest_reputation_workers:
            # 信誉最高的工人也需要与平均权重比较
            w_i = worker_weights[worker_id]
            relative_diff = abs(w_highest_avg - w_i) / abs(w_highest_avg) if w_highest_avg != 0 else 0
            data_quality_assessment[worker_id] = relative_diff < p
        else:
            w_i = worker_weights[worker_id]
            # 计算相对差异：|w_highest_avg - w_i| / |w_highest_avg|
            relative_diff = abs(w_highest_avg - w_i) / abs(w_highest_avg) if w_highest_avg != 0 else float('inf')
            # 小于阈值p则认为是优秀数据
            data_quality_assessment[worker_id] = relative_diff < p

    # 计算误差指标（如果提供了ground_truth）
    error_metrics = None
    if ground_truth is not None:
        gt_array = np.array(ground_truth)
        if gt_array.shape[0] == d:
            # 方法1：使用CRH算法得出的估计真值与地面真值比较
            errors_crh = truth_estimate - gt_array
            mae_crh = np.mean(np.abs(errors_crh))
            mse_crh = np.mean(errors_crh ** 2)
            rmse_crh = np.sqrt(mse_crh)

            # 方法2：使用优秀工人数据的平均值作为估计真值与地面真值比较
            good_quality_workers = [worker_id for worker_id, is_good in data_quality_assessment.items() if is_good]

            if good_quality_workers:  # 如果有优秀工人
                # 获取优秀工人的数据
                good_quality_data = [worker_data[worker_id] for worker_id in good_quality_workers]
                good_quality_matrix = np.array(good_quality_data)

                # 计算优秀工人数据的平均值
                good_workers_average = np.mean(good_quality_matrix, axis=0)

                # 计算优秀工人平均值与地面真值的误差
                errors_good = good_workers_average - gt_array
                mae_good = np.mean(np.abs(errors_good))
                mse_good = np.mean(errors_good ** 2)
                rmse_good = np.sqrt(mse_good)

                error_metrics = {
                    'CRH_MAE': float(mae_crh),
                    'CRH_MSE': float(mse_crh),
                    'CRH_RMSE': float(rmse_crh),
                    'GOOD_WORKERS_AVG_MAE': float(mae_good),
                    'GOOD_WORKERS_AVG_MSE': float(mse_good),
                    'GOOD_WORKERS_AVG_RMSE': float(rmse_good),
                    'good_workers_count': len(good_quality_workers),
                    'good_workers_average': good_workers_average.tolist()
                }
            else:
                # 如果没有优秀工人，只返回CRH算法的误差指标
                error_metrics = {
                    'CRH_MAE': float(mae_crh),
                    'CRH_MSE': float(mse_crh),
                    'CRH_RMSE': float(rmse_crh),
                    'GOOD_WORKERS_AVG_MAE': None,
                    'GOOD_WORKERS_AVG_MSE': None,
                    'GOOD_WORKERS_AVG_RMSE': None,
                    'good_workers_count': 0,
                    'good_workers_average': None
                }
        else:
            print(f"警告：真实值维度({gt_array.shape[0]})与数据维度({d})不匹配")

    return aggregated_truth, worker_weights, execution_time, t, error_metrics, data_quality_assessment


# 示例使用
if __name__ == "__main__":
    # 示例数据
    sample_worker_data = {
        "worker_1": [1.28, 2.345, 3.1],
        "worker_2": [1.112, 2.44564, 3.0],
        "worker_3": [1.312, 2.2456, 3.2],
        "worker_4": [5.051, 8.054, 9.0],  # 异常数据
        "worker_5": [1.065, 2.5456, 2.9]
    }

    # 工人信誉值（示例：worker_1和worker_3都有最高信誉）
    sample_worker_reputations = {
        "worker_1": 0.90,  # 最高信誉
        "worker_2": 0.75,
        "worker_3": 0.90,  # 最高信誉
        "worker_4": 0.60,
        "worker_5": 0.80
    }

    # 假设的真实值
    true_values = [1.15, 2.35, 3.05]

    # 执行真相发现
    truth, weights, duration, iterations, errors, quality = truth_discovery(
        sample_worker_data,
        sample_worker_reputations,
        ground_truth=true_values,
        p=0.2
    )

    print("真相发现结果:")
    print(f"聚合真值: {truth}")
    print(f"真实值: {true_values}")
    print(f"执行时间: {duration:.4f} 秒")
    print(f"迭代次数: {iterations}")

    if errors:
        print(f"\n误差指标:")
        print(f"=== CRH算法估计真值 vs 地面真值 ===")
        print(f"MAE (平均绝对误差): {errors['CRH_MAE']:.6f}")
        print(f"MSE (均方误差): {errors['CRH_MSE']:.6f}")
        print(f"RMSE (均方根误差): {errors['CRH_RMSE']:.6f}")

        if errors['good_workers_count'] > 0:
            print(f"\n=== 优秀工人平均值 vs 地面真值 ===")
            print(f"优秀工人数量: {errors['good_workers_count']}")
            print(f"优秀工人平均值: {errors['good_workers_average']}")
            print(f"MAE (平均绝对误差): {errors['GOOD_WORKERS_AVG_MAE']:.6f}")
            print(f"MSE (均方误差): {errors['GOOD_WORKERS_AVG_MSE']:.6f}")
            print(f"RMSE (均方根误差): {errors['GOOD_WORKERS_AVG_RMSE']:.6f}")
        else:
            print(f"\n=== 优秀工人平均值 vs 地面真值 ===")
            print("没有找到优秀工人数据")

    # 找到信誉最高的工人
    max_rep = max(sample_worker_reputations.values())
    highest_rep_workers = [w for w, r in sample_worker_reputations.items() if r == max_rep]
    highest_weights = [weights[w] for w in highest_rep_workers]
    avg_highest_weight = np.mean(highest_weights)

    print(f"\n信誉最高的工人: {highest_rep_workers} (信誉值: {max_rep})")
    print(f"信誉最高工人的权重: {[f'{w}:{weights[w]:.6f}' for w in highest_rep_workers]}")
    print(f"权重平均值: {avg_highest_weight:.6f}")

    print("\n工人详细信息:")
    for worker_id in sample_worker_data.keys():
        reputation = sample_worker_reputations[worker_id]
        weight = weights[worker_id]
        is_good = quality[worker_id]
        relative_diff = abs(avg_highest_weight - weight) / abs(avg_highest_weight) if avg_highest_weight != 0 else 0
        print(
            f"{worker_id}: 信誉={reputation:.2f}, 权重={weight:.6f}, 相对差异={relative_diff:.4f}, 数据质量={'优秀' if is_good else '不良'}")
