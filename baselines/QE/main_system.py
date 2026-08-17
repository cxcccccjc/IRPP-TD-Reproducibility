import json
import numpy as np
import time
from typing import Dict, List, Tuple, Set
import matplotlib.pyplot as plt
from sklearn.metrics import mean_absolute_error, mean_squared_error
import warnings
import os
from pathlib import Path

warnings.filterwarnings('ignore')


class CrowdSensingSystem:
    def __init__(self, distance_threshold=4.0, proportion_threshold=0.31, epsilon=1e-12):
        """
        初始化群智感知系统

        Args:
            distance_threshold: 离群点检测的距离阈值 (默认为4)
            proportion_threshold: 离群点检测的比例阈值 (默认为0.31)
            epsilon: 防止除零的小常数
        """
        self.distance_threshold = distance_threshold
        self.proportion_threshold = proportion_threshold
        self.epsilon = epsilon

        # 广义逻辑函数参数 (根据您提供的参数更新)
        self.A = 0.0  # 信誉下限
        self.B = 1.0  # 信誉上限
        self.D = 1.0
        self.F = 1.0
        self.M = 1.0
        self.h = 1.0

        # 历史记录
        self.worker_quality_history = {}
        self.worker_reputation_history = {}

        # 统计信息
        self.quality_estimation_times = []
        self.iteration_counts = []

    def euclidean_distance(self, x1: List[float], x2: List[float]) -> float:
        """计算欧几里得距离"""
        return np.sqrt(sum((a - b) ** 2 for a, b in zip(x1, x2)))

    def quality_estimation(self, data_points: List[List[float]], max_iterations=100, tolerance=1e-12) -> Tuple[
        List[float], List[float], int]:
        """
        数据质量估计模块

        Returns:
            qualities: 每个数据点的质量
            centroid: 聚类质心
            iterations: 迭代次数
        """
        n = len(data_points)
        if n == 0:
            return [], [], 0

        # 初始化质量
        qualities = [1.0 / n] * n

        # 计算初始质心
        centroid = [sum(point[i] for point in data_points) / n
                    for i in range(len(data_points[0]))]

        iterations = 0
        for iteration in range(max_iterations):
            iterations += 1
            old_qualities = qualities.copy()

            # 更新质心 - 使用加权平均
            weighted_sum = [0] * len(data_points[0])
            total_weight = 0

            for i, point in enumerate(data_points):
                weight = qualities[i]
                total_weight += weight
                for j in range(len(point)):
                    weighted_sum[j] += point[j] * weight

            if total_weight > 0:
                centroid = [ws / total_weight for ws in weighted_sum]

            # 计算距离的平方
            distances = []
            for point in data_points:
                dist_squared = self.euclidean_distance(point, centroid) ** 2
                distances.append(dist_squared + self.epsilon)

            # 更新质量 - 根据公式 qi,k = (1/di,k) / (Σ(1/dj,k) + ε)
            inv_distances = [1.0 / d for d in distances]
            sum_inv_distances = sum(inv_distances) + self.epsilon

            qualities = [inv_d / sum_inv_distances for inv_d in inv_distances]

            # 检查收敛
            quality_change = sum(abs(q - old_q) for q, old_q in zip(qualities, old_qualities))
            if quality_change < tolerance:
                break

        return qualities, centroid, iterations

    def reputation_estimation(self, worker_id: int, quality: float, time_slot: int) -> float:
        """
        信誉度估计模块 - 使用更新后的广义逻辑函数参数

        Args:
            worker_id: 工人ID
            quality: 当前数据质量
            time_slot: 时间槽

        Returns:
            reputation: 更新后的信誉度
        """
        # 初始化历史记录
        if worker_id not in self.worker_quality_history:
            self.worker_quality_history[worker_id] = []
            self.worker_reputation_history[worker_id] = []

        # 添加当前质量到历史记录
        self.worker_quality_history[worker_id].append(quality)

        # 计算历史质量记录 q'i,k = Σ(ωk-t * (qi,t - 1/n))
        n = len(self.worker_quality_history[worker_id])  # 历史记录数量
        historical_quality = 0
        decay_weight = 0.9  # 衰减权重 ω

        for t, hist_quality in enumerate(self.worker_quality_history[worker_id]):
            weight = decay_weight ** (n - 1 - t)  # ωk-t
            historical_quality += weight * (hist_quality - 1.0 / n)

        # 使用广义逻辑函数计算信誉度
        # Ri,k(qi,k) = A + (B-A) / ((1 + D*e^(-F*(qi,k - M)))^(1/h))
        # 参数: A=0, B=1, D=1, F=1, M=1, h=1

        # 将质量调整到合适范围，考虑历史质量影响
        adjusted_quality = quality + 0.1 * historical_quality

        try:
            exp_term = np.exp(-self.F * (adjusted_quality - self.M))
            denominator = (1 + self.D * exp_term) ** (1.0 / self.h)
            reputation = self.A + (self.B - self.A) / denominator
        except (OverflowError, ZeroDivisionError):
            # 处理数值溢出情况
            if adjusted_quality > self.M:
                reputation = self.B
            else:
                reputation = self.A

        # 确保信誉度在合理范围内
        reputation = max(0.01, min(1.0, reputation))

        self.worker_reputation_history[worker_id].append(reputation)
        return reputation

    def outlier_detection(self, data_points: List[List[float]], worker_ids: List[int]) -> Set[int]:
        """
        离群点检测模块 - 使用更新后的阈值参数

        使用距离阈值 r=4 和比例阈值 μ=0.31

        Returns:
            outlier_indices: 离群点的索引集合
        """
        n = len(data_points)
        if n <= 2:
            return set()

        outlier_indices = set()

        for i, point_i in enumerate(data_points):
            # 计算与其他点的距离
            close_points_count = 0

            for j, point_j in enumerate(data_points):
                if i != j:
                    dist = self.euclidean_distance(point_i, point_j)
                    if dist <= self.distance_threshold:  # r = 4
                        close_points_count += 1

            # 计算比例
            proportion = close_points_count / (n - 1)

            # 如果比例小于等于阈值，标记为离群点
            # |{xj,k | dist(xi,k, xj,k) ≤ r}| / n ≤ μ
            if proportion <= self.proportion_threshold:  # μ = 0.31
                outlier_indices.add(i)

        return outlier_indices

    def ground_truth_estimation(self, data_points: List[List[float]],
                                reputations: List[float],
                                normal_indices: List[int]) -> List[float]:
        """
        真值估计模块 - 使用信誉度加权的最小二乘估计

        x̄k = argmin Σ(dist²(x̄k, xi,k) × Ri,k) for i ∈ Nk

        Args:
            data_points: 所有数据点
            reputations: 所有工人的信誉度
            normal_indices: 正常数据点的索引

        Returns:
            ground_truth: 估计的真值
        """
        if not normal_indices:
            return []

        # 使用加权最小二乘方法
        # 对于最小化 Σ(dist²(x̄k, xi,k) × Ri,k)，最优解是加权平均
        weighted_sum = [0] * len(data_points[0])
        total_weight = 0

        for i in normal_indices:
            weight = reputations[i]
            total_weight += weight
            for j in range(len(data_points[i])):
                weighted_sum[j] += data_points[i][j] * weight

        if total_weight > 0:
            ground_truth = [ws / total_weight for ws in weighted_sum]
        else:
            # 如果权重和为0，使用简单平均
            ground_truth = [sum(data_points[i][j] for i in normal_indices) / len(normal_indices)
                            for j in range(len(data_points[0]))]

        return ground_truth

    def process_task(self, task_data: Dict, time_slot: int) -> Tuple[List[float], Dict]:
        """
        处理单个任务

        Returns:
            estimated_truth: 估计的真值
            metrics: 包含各种统计信息的字典
        """
        start_time = time.time()

        # 提取数据
        worker_submissions = task_data['worker_submissions']
        data_points = [submission['submitted_data'] for submission in worker_submissions]
        worker_ids = [submission['worker_id'] for submission in worker_submissions]
        true_data = task_data['task_true_data']

        if not data_points:
            return [], {}

        # 1. 数据质量估计
        qualities, centroid, iterations = self.quality_estimation(data_points)
        quality_time = time.time() - start_time
        self.quality_estimation_times.append(quality_time)
        self.iteration_counts.append(iterations)

        # 2. 信誉度估计
        reputations = []
        for i, worker_id in enumerate(worker_ids):
            reputation = self.reputation_estimation(worker_id, qualities[i], time_slot)
            reputations.append(reputation)

        # 3. 离群点检测
        outlier_indices = self.outlier_detection(data_points, worker_ids)
        normal_indices = [i for i in range(len(data_points)) if i not in outlier_indices]

        # 4. 真值估计
        if normal_indices:
            estimated_truth = self.ground_truth_estimation(data_points, reputations, normal_indices)
        else:
            # 如果所有数据都被标记为离群点，使用质量加权平均
            estimated_truth = self.ground_truth_estimation(data_points, qualities, list(range(len(data_points))))

        # 计算误差
        if estimated_truth and true_data:
            mae = mean_absolute_error([true_data], [estimated_truth])
            mse = mean_squared_error([true_data], [estimated_truth])
            rmse = np.sqrt(mse)
        else:
            mae = mse = rmse = float('inf')

        metrics = {
            'mae': mae,
            'mse': mse,
            'rmse': rmse,
            'quality_time': quality_time,
            'iterations': iterations,
            'outliers_count': len(outlier_indices),
            'normal_count': len(normal_indices),
            'outlier_indices': list(outlier_indices),
            'avg_reputation': np.mean(reputations) if reputations else 0
        }

        return estimated_truth, metrics


def main():
    # 加载数据
    default_workload = Path(__file__).resolve().parents[2] / "data" / "workloads" / "Scene_1_Number_of_Workers_27.json"
    data_path = Path(os.environ.get("IRPP_WORKLOAD", default_workload))

    try:
        with open(data_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        print(f"成功加载数据文件: {data_path}")
        print(f"数据包含 {data['reorganization_info']['total_tasks']} 个任务")
    except FileNotFoundError:
        print(f"数据文件未找到: {data_path}")
        print("创建模拟数据进行演示...")
        data = create_simulated_data()

    # 初始化系统 (使用更新后的参数)
    system = CrowdSensingSystem(distance_threshold=4.0, proportion_threshold=0.31)

    print(f"系统参数:")
    print(f"  距离阈值 r = {system.distance_threshold}")
    print(f"  比例阈值 μ = {system.proportion_threshold}")
    print(f"  逻辑函数参数: A={system.A}, B={system.B}, D={system.D}, F={system.F}, M={system.M}, h={system.h}")

    # 处理所有任务
    task_worker_data = data['task_worker_data']
    results = []

    mae_errors = []
    mse_errors = []
    rmse_errors = []

    print("\n开始处理任务...")
    print("=" * 80)

    for task_id_str, task_data in task_worker_data.items():
        task_id = int(task_id_str)

        estimated_truth, metrics = system.process_task(task_data, task_id)
        results.append((task_id, estimated_truth, metrics))

        mae_errors.append(metrics['mae'])
        mse_errors.append(metrics['mse'])
        rmse_errors.append(metrics['rmse'])

        print(f"任务 {task_id:3d}: MAE={metrics['mae']:.4f}, MSE={metrics['mse']:.4f}, "
              f"RMSE={metrics['rmse']:.4f}, 迭代={metrics['iterations']:2d}, "
              f"离群点={metrics['outliers_count']:2d}, 平均信誉={metrics['avg_reputation']:.3f}")

        # 每10次任务输出累计质量估计时间
        if task_id % 10 == 0:
            cumulative_time = sum(system.quality_estimation_times)
            avg_time_per_task = cumulative_time / task_id
            print(
                f"前{task_id}次任务累计数据质量估计用时: {cumulative_time:.4f}秒 (平均每次: {avg_time_per_task:.6f}秒)")
            print("-" * 80)

    # 计算统计信息
    print("\n" + "=" * 80)
    print("最终统计结果:")
    print("=" * 80)

    # 前50次和后50次任务的统计
    mid_point = min(50, len(mae_errors) // 2)
    first_half_mae = mae_errors[:mid_point]
    first_half_mse = mse_errors[:mid_point]
    first_half_rmse = rmse_errors[:mid_point]

    second_half_mae = mae_errors[mid_point:]
    second_half_mse = mse_errors[mid_point:]
    second_half_rmse = rmse_errors[mid_point:]

    print(f"前{mid_point}次任务统计:")
    if first_half_mae:
        print(f"  MAE: 均值={np.mean(first_half_mae):.4f}, 标准差={np.std(first_half_mae):.4f}")
        print(f"  MSE: 均值={np.mean(first_half_mse):.4f}, 标准差={np.std(first_half_mse):.4f}")
        print(f"  RMSE: 均值={np.mean(first_half_rmse):.4f}, 标准差={np.std(first_half_rmse):.4f}")

    print(f"\n后{len(second_half_mae)}次任务统计:")
    if second_half_mae:
        print(f"  MAE: 均值={np.mean(second_half_mae):.4f}, 标准差={np.std(second_half_mae):.4f}")
        print(f"  MSE: 均值={np.mean(second_half_mse):.4f}, 标准差={np.std(second_half_mse):.4f}")
        print(f"  RMSE: 均值={np.mean(second_half_rmse):.4f}, 标准差={np.std(second_half_rmse):.4f}")

    print(f"\n总体统计 (共{len(mae_errors)}次任务):")
    print(f"  平均迭代次数: {np.mean(system.iteration_counts):.2f}")
    print(f"  迭代次数标准差: {np.std(system.iteration_counts):.2f}")
    print(f"  总质量估计用时: {sum(system.quality_estimation_times):.4f}秒")
    print(f"  平均每次任务质量估计用时: {np.mean(system.quality_estimation_times):.6f}秒")
    print(f"  质量估计用时标准差: {np.std(system.quality_estimation_times):.6f}秒")

    # 绘制结果图表
    plot_results(mae_errors, mse_errors, rmse_errors, system.iteration_counts, system.quality_estimation_times)

    return results, system


def plot_results(mae_errors, mse_errors, rmse_errors, iterations, quality_times):
    """绘制结果图表"""
    plt.figure(figsize=(16, 12))

    # 误差变化图
    plt.subplot(2, 3, 1)
    plt.plot(mae_errors, 'b-', alpha=0.7, linewidth=1.5)
    plt.title('MAE随任务变化', fontsize=12)
    plt.xlabel('任务ID')
    plt.ylabel('MAE')
    plt.grid(True, alpha=0.3)

    plt.subplot(2, 3, 2)
    plt.plot(mse_errors, 'r-', alpha=0.7, linewidth=1.5)
    plt.title('MSE随任务变化', fontsize=12)
    plt.xlabel('任务ID')
    plt.ylabel('MSE')
    plt.grid(True, alpha=0.3)

    plt.subplot(2, 3, 3)
    plt.plot(rmse_errors, 'g-', alpha=0.7, linewidth=1.5)
    plt.title('RMSE随任务变化', fontsize=12)
    plt.xlabel('任务ID')
    plt.ylabel('RMSE')
    plt.grid(True, alpha=0.3)

    # 迭代次数和时间
    plt.subplot(2, 3, 4)
    plt.plot(iterations, 'purple', alpha=0.7, linewidth=1.5)
    plt.title('迭代次数随任务变化', fontsize=12)
    plt.xlabel('任务ID')
    plt.ylabel('迭代次数')
    plt.grid(True, alpha=0.3)

    plt.subplot(2, 3, 5)
    plt.plot(quality_times, 'orange', alpha=0.7, linewidth=1.5)
    plt.title('质量估计用时随任务变化', fontsize=12)
    plt.xlabel('任务ID')
    plt.ylabel('用时 (秒)')
    plt.grid(True, alpha=0.3)

    # 误差分布直方图
    plt.subplot(2, 3, 6)
    plt.hist(mae_errors, bins=20, alpha=0.7, color='skyblue', edgecolor='black')
    plt.title('MAE分布直方图', fontsize=12)
    plt.xlabel('MAE')
    plt.ylabel('频次')
    plt.grid(True, alpha=0.3)

    plt.tight_layout()
    plt.show()


def create_simulated_data():
    """创建模拟数据用于演示"""
    import random

    data = {
        "reorganization_info": {
            "total_tasks": 10,
            "description": "模拟数据用于演示"
        },
        "task_worker_data": {}
    }

    for task_id in range(1, 11):
        true_data = [random.uniform(100, 1000) for _ in range(5)]
        workers = []

        for worker_id in range(1, 21):
            # 添加一些噪声，有些工人数据质量较差
            if random.random() < 0.8:  # 80%的工人提供较好数据
                submitted_data = [td + random.gauss(0, 5) for td in true_data]
            else:  # 20%的工人提供较差数据
                submitted_data = [td + random.gauss(0, 50) for td in true_data]

            workers.append({
                "worker_id": worker_id,
                "submitted_data": submitted_data
            })

        data["task_worker_data"][str(task_id)] = {
            "task_id": task_id,
            "task_true_data": true_data,
            "worker_submissions": workers
        }

    return data


if __name__ == "__main__":
    results, system = main()
