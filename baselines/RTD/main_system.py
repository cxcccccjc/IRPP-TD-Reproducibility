import json
import numpy as np
from typing import Dict, List, Tuple, Any
import logging
from scipy.optimize import minimize
import matplotlib.pyplot as plt
import time
import os
from collections import defaultdict
from pathlib import Path


class ReputationBasedTruthDiscovery:
    def __init__(self, gamma: float = 0.9, epsilon: float = 1e-6, max_iterations: int = 100):
        """
        初始化基于声誉的真相发现算法

        Args:
            gamma: 衰减因子，用于调整声誉的时间衰减
            epsilon: 收敛准则，当两轮真相的差异小于该值时停止迭代
            max_iterations: 最大迭代次数
        """
        self.gamma = gamma
        self.epsilon = epsilon
        self.max_iterations = max_iterations
        self.logger = self._setup_logger()

        # 性能监控变量
        self.execution_times = []  # 每个任务的总执行时间
        self.iteration_times = []  # 每个任务的纯迭代时间
        self.iteration_counts = []  # 每个任务的迭代次数
        self.task_errors = []  # 每个任务的误差
        self.cumulative_time = 0  # 累积执行时间
        self.generation_times = []  # 每10代的累积时间

    def _setup_logger(self):
        """设置日志记录器"""
        logging.basicConfig(level=logging.INFO)
        return logging.getLogger(__name__)

    def load_data(self, file_path: str) -> Dict:
        """加载数据集"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            self.logger.info(f"成功加载数据集，包含 {data['reorganization_info']['total_tasks']} 个任务")
            return data
        except Exception as e:
            self.logger.error(f"加载数据集失败: {e}")
            raise

    def g_function(self, w: float) -> float:
        """
        正则化函数 g(w)
        这里使用简单的线性函数，也可以根据需要调整
        """
        return w

    def compute_distance(self, v_true: np.ndarray, v_observed: np.ndarray,
                         data_type: str = 'continuous') -> float:
        """
        计算观测值和真相之间的损失函数

        Args:
            v_true: 真相值
            v_observed: 观测值
            data_type: 数据类型 ('continuous' 或 'categorical')
        """
        if data_type == 'continuous':
            # 对于连续数据，使用归一化的平方差损失
            diff = v_true - v_observed
            # 添加小的常数避免除零
            std_dev = np.std(v_observed) + 1e-8
            return np.sum((diff ** 2) / std_dev)
        elif data_type == 'categorical':
            # 对于分类数据，使用简单的二值损失
            return float(not np.array_equal(v_true, v_observed))
        else:
            raise ValueError(f"不支持的数据类型: {data_type}")

    def compute_metrics(self, estimated_truth: np.ndarray, true_data: np.ndarray) -> Dict[str, float]:
        """
        计算MAE, MSE, RMSE等指标

        Args:
            estimated_truth: 估计的真相
            true_data: 真实数据

        Returns:
            包含各种误差指标的字典
        """
        diff = estimated_truth - true_data
        mae = np.mean(np.abs(diff))
        mse = np.mean(diff ** 2)
        rmse = np.sqrt(mse)
        error_std = np.std(diff)

        return {
            'mae': mae,
            'mse': mse,
            'rmse': rmse,
            'error_std': error_std
        }

    def update_truth(self, observations: List[np.ndarray], weights: np.ndarray) -> np.ndarray:
        """
        真相更新阶段：基于当前权重计算最优真相

        Args:
            observations: 所有源设备的观测数据
            weights: 当前权重

        Returns:
            更新后的真相值
        """

        def objective(v_truth):
            total_loss = 0
            for i, obs in enumerate(observations):
                g_w = self.g_function(weights[i])
                distance = self.compute_distance(v_truth, obs)
                total_loss += g_w * distance
            return total_loss

        # 初始猜测：使用加权平均
        initial_guess = np.average(observations, weights=weights, axis=0)

        # 使用优化方法找到最优真相
        result = minimize(objective, initial_guess, method='BFGS')

        if result.success:
            return result.x
        else:
            self.logger.warning("真相优化失败，使用加权平均作为备选")
            return initial_guess

    def update_weights(self, observations: List[np.ndarray],
                       current_truth: np.ndarray,
                       current_weights: np.ndarray) -> np.ndarray:
        """
        权重更新阶段：基于当前真相优化权重

        Args:
            observations: 所有源设备的观测数据
            current_truth: 当前真相
            current_weights: 当前权重

        Returns:
            更新后的权重
        """
        n_sources = len(observations)

        def objective(weights):
            # 确保权重和为1的约束
            weights = weights / np.sum(weights)
            total_loss = 0
            for i, obs in enumerate(observations):
                g_w = self.g_function(weights[i])
                distance = self.compute_distance(current_truth, obs)
                total_loss += g_w * distance
            return total_loss

        # 约束条件：权重和为1，权重非负
        constraints = {'type': 'eq', 'fun': lambda w: np.sum(w) - 1}
        bounds = [(0.001, 1.0) for _ in range(n_sources)]  # 避免权重为0

        result = minimize(objective, current_weights,
                          method='SLSQP',
                          constraints=constraints,
                          bounds=bounds)

        if result.success:
            return result.x
        else:
            self.logger.warning("权重优化失败，保持当前权重")
            return current_weights

    def compute_loss_contribution(self, observations: List[np.ndarray],
                                  current_truth: np.ndarray,
                                  weights: np.ndarray) -> np.ndarray:
        """
        计算每个源设备的损失贡献

        Args:
            observations: 所有源设备的观测数据
            current_truth: 当前真相
            weights: 当前权重

        Returns:
            每个源设备的损失贡献
        """
        n_sources = len(observations)
        individual_losses = np.zeros(n_sources)

        # 计算每个源设备的个体损失
        for i, obs in enumerate(observations):
            g_w = self.g_function(weights[i])
            distance = self.compute_distance(current_truth, obs)
            individual_losses[i] = g_w * distance

        # 计算损失贡献（归一化）
        total_loss = np.sum(individual_losses)
        if total_loss > 0:
            loss_contributions = individual_losses / total_loss
        else:
            # 如果总损失为0，平均分配贡献
            loss_contributions = np.ones(n_sources) / n_sources

        return loss_contributions

    def update_reputation_with_decay(self, reputation_history: Dict[int, List[float]],
                                     current_round: int) -> Dict[int, float]:
        """
        使用衰减因子更新声誉

        Args:
            reputation_history: 声誉历史记录
            current_round: 当前轮次

        Returns:
            更新后的声誉字典
        """
        updated_reputation = {}

        for worker_id, rep_history in reputation_history.items():
            decayed_reputation = 0
            for j, rep in enumerate(rep_history):
                decay_factor = self.gamma ** (current_round - j - 1)
                decayed_reputation += decay_factor * rep
            updated_reputation[worker_id] = decayed_reputation

        return updated_reputation

    def process_single_task(self, task_data: Dict, task_index: int) -> Tuple[np.ndarray, Dict[int, float], List[Dict]]:
        """
        处理单个任务的真相发现过程

        Args:
            task_data: 单个任务的数据
            task_index: 任务索引（用于性能监控）

        Returns:
            估计的真相、最终声誉、迭代历史
        """
        task_start_time = time.time()

        task_id = task_data['task_id']
        true_data = np.array(task_data['task_true_data'])
        worker_submissions = task_data['worker_submissions']

        # 提取观测数据和工人ID
        observations = []
        worker_ids = []
        for submission in worker_submissions:
            observations.append(np.array(submission['submitted_data']))
            worker_ids.append(submission['worker_id'])

        n_sources = len(observations)
        self.logger.info(f"处理任务 {task_id}，包含 {n_sources} 个源设备")

        # 初始化权重（第一轮均等权重）
        weights = np.ones(n_sources) / n_sources

        # 初始化声誉
        reputation_history = {worker_id: [] for worker_id in worker_ids}

        # 迭代历史记录
        iteration_history = []

        # 初始真相估计（简单平均）
        current_truth = np.mean(observations, axis=0)
        previous_truth = current_truth.copy()

        # 迭代过程 - 精确记录迭代时间
        iteration_start_time = time.time()

        for iteration in range(self.max_iterations):
            iteration_step_start = time.time()

            self.logger.debug(f"任务 {task_id} - 迭代 {iteration + 1}")

            # 1. 真相更新阶段
            current_truth = self.update_truth(observations, weights)

            # 2. 权重更新阶段
            weights = self.update_weights(observations, current_truth, weights)

            # 3. 损失贡献计算
            loss_contributions = self.compute_loss_contribution(observations, current_truth, weights)

            # 4. 声誉更新
            for i, worker_id in enumerate(worker_ids):
                # 将损失贡献转换为声誉贡献（损失越小，声誉贡献越大）
                reputation_contribution = 1.0 - loss_contributions[i]
                reputation_history[worker_id].append(reputation_contribution)

            iteration_step_end = time.time()
            step_time = iteration_step_end - iteration_step_start

            # 记录迭代历史
            iteration_info = {
                'iteration': iteration + 1,
                'truth': current_truth.copy(),
                'weights': weights.copy(),
                'loss_contributions': loss_contributions.copy(),
                'truth_change': np.linalg.norm(current_truth - previous_truth),
                'iteration_time': step_time  # 单次迭代时间
            }
            iteration_history.append(iteration_info)

            # 收敛检查
            truth_change = np.linalg.norm(current_truth - previous_truth)
            if truth_change < self.epsilon:
                self.logger.info(f"任务 {task_id} 在第 {iteration + 1} 轮收敛")
                break

            previous_truth = current_truth.copy()

        iteration_end_time = time.time()
        total_iteration_time = iteration_end_time - iteration_start_time

        # 使用衰减因子更新最终声誉
        final_reputation = self.update_reputation_with_decay(reputation_history, len(iteration_history))

        # 计算误差指标
        metrics = self.compute_metrics(current_truth, true_data)

        # 记录性能数据
        task_end_time = time.time()
        task_execution_time = task_end_time - task_start_time

        self.execution_times.append(task_execution_time)
        self.iteration_times.append(total_iteration_time)  # 纯迭代时间
        self.iteration_counts.append(len(iteration_history))
        self.task_errors.append(metrics)
        self.cumulative_time += task_execution_time

        # 每10个任务记录累积时间
        if (task_index + 1) % 10 == 0:
            self.generation_times.append({
                'generation': (task_index + 1) // 10,
                'cumulative_time': self.cumulative_time,
                'average_time_per_task': self.cumulative_time / (task_index + 1),
                'cumulative_iteration_time': sum(self.iteration_times),
                'average_iteration_time_per_task': sum(self.iteration_times) / (task_index + 1)
            })
            self.logger.info(f"第 {(task_index + 1) // 10} 代完成，累积时间: {self.cumulative_time:.4f}s, "
                             f"累积迭代时间: {sum(self.iteration_times):.4f}s")

        self.logger.info(f"任务 {task_id} 完成，总执行时间: {task_execution_time:.4f}s, "
                         f"纯迭代时间: {total_iteration_time:.4f}s, "
                         f"迭代次数: {len(iteration_history)}, "
                         f"MAE: {metrics['mae']:.4f}")

        return current_truth, final_reputation, iteration_history

    def run_algorithm(self, data: Dict) -> Dict:
        """
        运行完整的基于声誉的真相发现算法

        Args:
            data: 完整的数据集

        Returns:
            所有任务的结果
        """
        task_worker_data = data['task_worker_data']
        all_results = {}

        # 重置性能监控变量
        self.execution_times = []
        self.iteration_times = []
        self.iteration_counts = []
        self.task_errors = []
        self.cumulative_time = 0
        self.generation_times = []

        # 全局声誉追踪
        global_reputation = {}

        # 按任务ID排序确保处理顺序
        sorted_tasks = sorted(task_worker_data.items(), key=lambda x: int(x[0]))

        for task_index, (task_id_str, task_data) in enumerate(sorted_tasks):
            task_id = int(task_id_str)

            # 处理单个任务
            estimated_truth, task_reputation, iteration_history = self.process_single_task(task_data, task_index)

            # 更新全局声誉
            for worker_id, rep in task_reputation.items():
                if worker_id not in global_reputation:
                    global_reputation[worker_id] = []
                global_reputation[worker_id].append(rep)

            # 保存结果
            all_results[task_id] = {
                'estimated_truth': estimated_truth.tolist(),
                'true_data': task_data['task_true_data'],
                'task_reputation': task_reputation,
                'iteration_history': iteration_history,
                'metrics': self.task_errors[task_index],
                'execution_time': self.execution_times[task_index],
                'iteration_time': self.iteration_times[task_index],  # 纯迭代时间
                'iteration_count': self.iteration_counts[task_index]
            }

        # 计算最终全局声誉（所有任务的平均）
        final_global_reputation = {}
        for worker_id, rep_list in global_reputation.items():
            final_global_reputation[worker_id] = np.mean(rep_list)

        return {
            'task_results': all_results,
            'global_reputation': final_global_reputation,
            'performance_metrics': self.get_performance_metrics(),
            'algorithm_parameters': {
                'gamma': self.gamma,
                'epsilon': self.epsilon,
                'max_iterations': self.max_iterations
            }
        }

    def get_performance_metrics(self) -> Dict:
        """
        获取性能指标

        Returns:
            包含各种性能指标的字典
        """
        total_tasks = len(self.task_errors)
        if total_tasks == 0:
            return {}

        # 计算总体指标
        all_mae = [error['mae'] for error in self.task_errors]
        all_mse = [error['mse'] for error in self.task_errors]
        all_rmse = [error['rmse'] for error in self.task_errors]
        all_error_std = [error['error_std'] for error in self.task_errors]

        # 前50次任务和后50次任务的指标
        first_50_metrics = {}
        last_50_metrics = {}

        if total_tasks >= 50:
            # 前50次任务
            first_50_mae = all_mae[:50]
            first_50_mse = all_mse[:50]
            first_50_rmse = all_rmse[:50]
            first_50_error_std = all_error_std[:50]

            first_50_metrics = {
                'mae_mean': np.mean(first_50_mae),
                'mae_std': np.std(first_50_mae),
                'mse_mean': np.mean(first_50_mse),
                'mse_std': np.std(first_50_mse),
                'rmse_mean': np.mean(first_50_rmse),
                'rmse_std': np.std(first_50_rmse),
                'error_std_mean': np.mean(first_50_error_std),
                'error_std_std': np.std(first_50_error_std)
            }

            # 后50次任务
            if total_tasks >= 100:
                last_50_mae = all_mae[-50:]
                last_50_mse = all_mse[-50:]
                last_50_rmse = all_rmse[-50:]
                last_50_error_std = all_error_std[-50:]

                last_50_metrics = {
                    'mae_mean': np.mean(last_50_mae),
                    'mae_std': np.std(last_50_mae),
                    'mse_mean': np.mean(last_50_mse),
                    'mse_std': np.std(last_50_mse),
                    'rmse_mean': np.mean(last_50_rmse),
                    'rmse_std': np.std(last_50_rmse),
                    'error_std_mean': np.mean(last_50_error_std),
                    'error_std_std': np.std(last_50_error_std)
                }

        # 精确的迭代时间计算
        total_iteration_time = sum(self.iteration_times)  # 所有任务的纯迭代时间总和
        total_iterations = sum(self.iteration_counts)
        avg_iteration_time = total_iteration_time / total_iterations if total_iterations > 0 else 0

        return {
            'total_tasks': total_tasks,
            'total_execution_time': sum(self.execution_times),
            'total_iteration_time': total_iteration_time,  # 纯迭代时间总和
            'average_task_time': np.mean(self.execution_times),
            'average_iteration_time_per_task': np.mean(self.iteration_times),  # 每个任务的平均迭代时间
            'generation_times': self.generation_times,
            'overall_metrics': {
                'mae_mean': np.mean(all_mae),
                'mae_std': np.std(all_mae),
                'mse_mean': np.mean(all_mse),
                'mse_std': np.std(all_mse),
                'rmse_mean': np.mean(all_rmse),
                'rmse_std': np.std(all_rmse),
                'error_std_mean': np.mean(all_error_std),
                'error_std_std': np.std(all_error_std)
            },
            'first_50_metrics': first_50_metrics,
            'last_50_metrics': last_50_metrics,
            'iteration_metrics': {
                'total_iterations': total_iterations,
                'average_iterations_per_task': np.mean(self.iteration_counts),
                'average_iteration_time': avg_iteration_time,  # 平均单次迭代时间
                'total_iteration_time': total_iteration_time,  # 所有迭代的总时间
                'iteration_time_per_task': self.iteration_times  # 每个任务的迭代时间列表
            }
        }

    def analyze_results(self, results: Dict):
        """分析和可视化结果"""
        task_results = results['task_results']
        global_reputation = results['global_reputation']
        performance_metrics = results['performance_metrics']

        # 基本统计信息
        errors = [result['metrics']['mae'] for result in task_results.values()]
        mean_error = np.mean(errors)
        std_error = np.std(errors)

        print(f"\n=== 算法性能分析 ===")
        print(f"处理任务数量: {len(task_results)}")
        print(f"总执行时间: {performance_metrics['total_execution_time']:.4f}s")
        print(f"总迭代时间: {performance_metrics['total_iteration_time']:.4f}s")
        print(f"平均任务执行时间: {performance_metrics['average_task_time']:.4f}s")
        print(f"平均任务迭代时间: {performance_metrics['average_iteration_time_per_task']:.4f}s")

        # 每10代累积时间
        print(f"\n=== 每10代累积时间分析 ===")
        for gen_info in performance_metrics['generation_times']:
            print(f"第 {gen_info['generation']} 代:")
            print(f"  累积总时间: {gen_info['cumulative_time']:.4f}s")
            print(f"  累积迭代时间: {gen_info['cumulative_iteration_time']:.4f}s")
            print(f"  平均任务时间: {gen_info['average_time_per_task']:.4f}s")
            print(f"  平均迭代时间: {gen_info['average_iteration_time_per_task']:.4f}s")

        # 整体误差指标
        overall_metrics = performance_metrics['overall_metrics']
        print(f"\n=== 整体误差指标 ===")
        print(f"MAE: {overall_metrics['mae_mean']:.6f} ± {overall_metrics['mae_std']:.6f}")
        print(f"MSE: {overall_metrics['mse_mean']:.6f} ± {overall_metrics['mse_std']:.6f}")
        print(f"RMSE: {overall_metrics['rmse_mean']:.6f} ± {overall_metrics['rmse_std']:.6f}")
        print(f"误差标准差: {overall_metrics['error_std_mean']:.6f} ± {overall_metrics['error_std_std']:.6f}")

        # 前50次和后50次任务对比
        if performance_metrics['first_50_metrics'] and performance_metrics['last_50_metrics']:
            first_50 = performance_metrics['first_50_metrics']
            last_50 = performance_metrics['last_50_metrics']

            print(f"\n=== 前50次任务 vs 后50次任务对比 ===")
            print("前50次任务:")
            print(f"  MAE: {first_50['mae_mean']:.6f} ± {first_50['mae_std']:.6f}")
            print(f"  MSE: {first_50['mse_mean']:.6f} ± {first_50['mse_std']:.6f}")
            print(f"  RMSE: {first_50['rmse_mean']:.6f} ± {first_50['rmse_std']:.6f}")
            print(f"  误差标准差: {first_50['error_std_mean']:.6f} ± {first_50['error_std_std']:.6f}")

            print("后50次任务:")
            print(f"  MAE: {last_50['mae_mean']:.6f} ± {last_50['mae_std']:.6f}")
            print(f"  MSE: {last_50['mse_mean']:.6f} ± {last_50['mse_std']:.6f}")
            print(f"  RMSE: {last_50['rmse_mean']:.6f} ± {last_50['rmse_std']:.6f}")
            print(f"  误差标准差: {last_50['error_std_mean']:.6f} ± {last_50['error_std_std']:.6f}")

            # 改进程度
            mae_improvement = (first_50['mae_mean'] - last_50['mae_mean']) / first_50['mae_mean'] * 100
            mse_improvement = (first_50['mse_mean'] - last_50['mse_mean']) / first_50['mse_mean'] * 100
            rmse_improvement = (first_50['rmse_mean'] - last_50['rmse_mean']) / first_50['rmse_mean'] * 100

            print(f"\n改进程度:")
            print(f"  MAE改进: {mae_improvement:.2f}%")
            print(f"  MSE改进: {mse_improvement:.2f}%")
            print(f"  RMSE改进: {rmse_improvement:.2f}%")

        # 迭代相关指标
        iteration_metrics = performance_metrics['iteration_metrics']
        print(f"\n=== 迭代相关指标 ===")
        print(f"总迭代次数: {iteration_metrics['total_iterations']}")
        print(f"平均每任务迭代次数: {iteration_metrics['average_iterations_per_task']:.2f}")
        print(f"平均单次迭代时间: {iteration_metrics['average_iteration_time']:.6f}s")
        print(f"总迭代时间: {iteration_metrics['total_iteration_time']:.4f}s")

        # 100次任务的平均迭代时间
        if len(iteration_metrics['iteration_time_per_task']) >= 100:
            avg_100_iteration_time = np.mean(iteration_metrics['iteration_time_per_task'][:100])
            print(f"前100次任务的平均迭代时间: {avg_100_iteration_time:.6f}s")
        else:
            avg_all_iteration_time = np.mean(iteration_metrics['iteration_time_per_task'])
            print(
                f"所有 {len(iteration_metrics['iteration_time_per_task'])} 次任务的平均迭代时间: {avg_all_iteration_time:.6f}s")

        # 声誉分析
        reputation_values = list(global_reputation.values())
        print(f"\n=== 声誉分析 ===")
        print(f"参与工人数量: {len(global_reputation)}")
        print(f"平均声誉: {np.mean(reputation_values):.4f}")
        print(f"声誉标准差: {np.std(reputation_values):.4f}")
        print(f"最高声誉: {max(reputation_values):.4f}")
        print(f"最低声誉: {min(reputation_values):.4f}")

        # 找出声誉最高和最低的工人
        sorted_reputation = sorted(global_reputation.items(), key=lambda x: x[1], reverse=True)
        print(f"\n声誉最高的5个工人:")
        for i, (worker_id, rep) in enumerate(sorted_reputation[:5]):
            print(f"  {i + 1}. 工人 {worker_id}: {rep:.4f}")

        print(f"\n声誉最低的5个工人:")
        for i, (worker_id, rep) in enumerate(sorted_reputation[-5:]):
            print(f"  {i + 1}. 工人 {worker_id}: {rep:.4f}")

        return {
            'mean_error': mean_error,
            'std_error': std_error,
            'reputation_stats': {
                'mean': np.mean(reputation_values),
                'std': np.std(reputation_values),
                'min': min(reputation_values),
                'max': max(reputation_values)
            },
            'performance_metrics': performance_metrics
        }

def main():
    """主函数"""
    # 初始化算法
    algorithm = ReputationBasedTruthDiscovery(
        gamma=0.99,  # 衰减因子
        epsilon=1e-12,  # 收敛准则
        max_iterations=100  # 最大迭代次数
    )

    # 加载数据
    default_workload = Path(__file__).resolve().parents[2] / "data" / "workloads" / "Scene_3_Number_of_Workers_39.json"
    data_path = Path(os.environ.get("IRPP_WORKLOAD", default_workload))
    try:
        data = algorithm.load_data(data_path)
    except Exception as e:
        print(f"无法加载数据文件: {e}")
        return

    # 运行算法
    print("开始运行基于声誉的真相发现算法...")
    start_time = time.time()
    results = algorithm.run_algorithm(data)
    end_time = time.time()

    print(f"算法总运行时间: {end_time - start_time:.4f}s")

    # 分析结果
    stats = algorithm.analyze_results(results)

    # 保存结果
    output_path = "truth_discovery_results_enhanced.json"
    try:
        with open(output_path, 'w', encoding='utf-8') as f:
            # 将numpy数组转换为列表以便JSON序列化
            serializable_results = results.copy()
            json.dump(serializable_results, f, ensure_ascii=False, indent=2)
        print(f"\n结果已保存到: {output_path}")
    except Exception as e:
        print(f"保存结果失败: {e}")


if __name__ == "__main__":
    main()

