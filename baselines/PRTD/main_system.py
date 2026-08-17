import json
import numpy as np
import pandas as pd
import time
from typing import Dict, List, Tuple, Optional
import warnings
import os
from pathlib import Path

warnings.filterwarnings('ignore')


class CrowdSensingTruthDiscoveryAnalysis:
    def __init__(self,
                 tau: float = 0.1,
                 t0: float = 0.5,
                 epsilon: float = 1e-6,
                 xi: float = 1e-6,
                 max_iterations: int = 100,
                 distance_metric: str = 'absolute'):
        """
        群智感知真相发现算法 - 性能分析版本
        使用作者推荐参数：t0=0.5, τ=0.1, ξ=10^-6, 绝对差距离
        """
        self.tau = tau
        self.t0 = t0
        self.epsilon = epsilon
        self.xi = xi
        self.max_iterations = max_iterations
        self.distance_metric = distance_metric
        self.eps_small = 1e-12

        # 性能统计
        self.task_results = []
        self.timing_results = []

    def distance_function(self, a: np.ndarray, b: np.ndarray) -> float:
        """绝对差距离函数"""
        return np.sum(np.abs(a - b))

    def load_data(self, file_path: str) -> Tuple[np.ndarray, Dict[int, float], Dict[int, List]]:
        """加载数据文件"""
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        task_data = data['task_worker_data']

        # 收集所有工人ID和任务ID
        all_workers = set()
        all_tasks = []

        for task_id, task_info in task_data.items():
            all_tasks.append(int(task_id))
            for submission in task_info['worker_submissions']:
                all_workers.add(submission['worker_id'])

        all_workers = sorted(list(all_workers))
        all_tasks = sorted(all_tasks)

        K = len(all_workers)  # 用户数量
        M = len(all_tasks)  # 任务数量
        D = len(task_data[str(all_tasks[0])]['task_true_data'])  # 观测维度

        # 初始化观测矩阵
        X = np.full((K, M, D), np.nan)

        # 创建映射
        worker_to_idx = {worker_id: idx for idx, worker_id in enumerate(all_workers)}
        task_to_idx = {task_id: idx for idx, task_id in enumerate(all_tasks)}

        # 填充观测矩阵
        for task_id, task_info in task_data.items():
            task_idx = task_to_idx[int(task_id)]
            for submission in task_info['worker_submissions']:
                worker_idx = worker_to_idx[submission['worker_id']]
                X[worker_idx, task_idx, :] = np.array(submission['submitted_data'])

        # 初始化工人声誉
        np.random.seed(42)
        worker_reputations = {}
        for worker_id in all_workers:
            base_reputation = 0.6 + 0.3 * np.random.random()
            worker_reputations[worker_id] = base_reputation

        # 收集真实值
        task_true_values = {}
        for task_id, task_info in task_data.items():
            task_true_values[int(task_id)] = np.array(task_info['task_true_data'])

        return X, worker_reputations, task_true_values, all_workers, all_tasks

    def compute_reliability(self, reputations: np.ndarray) -> np.ndarray:
        """计算可靠度"""
        gamma = np.zeros_like(reputations)
        mask = reputations >= self.t0
        gamma[mask] = (reputations[mask] - self.t0) / self.tau
        return gamma

    def iterative_truth_discovery_single_task(self, task_observations: np.ndarray,
                                              gamma: np.ndarray,
                                              true_value: np.ndarray) -> Dict:
        """
        单任务真相发现 - 详细分析版本

        Args:
            task_observations: 单个任务的所有用户观测 (K, D)
            gamma: 可靠度数组 (K,)
            true_value: 真实值 (D,)

        Returns:
            结果字典包含每次迭代的误差和最终结果
        """
        K, D = task_observations.shape

        # 找出参与该任务的用户
        valid_users = ~np.isnan(task_observations).any(axis=1)
        valid_observations = task_observations[valid_users]
        valid_gamma = gamma[valid_users]
        K_valid = len(valid_observations)

        if K_valid == 0:
            return {
                'final_truth': true_value,  # 如果无观测，返回真实值
                'iterations': 0,
                'converged': False,
                'iteration_errors': [],
                'iteration_truths': []
            }

        # 初始化真值（使用中位数）
        x_current = np.median(valid_observations, axis=0)

        iteration_errors = []
        iteration_truths = []

        for iteration in range(self.max_iterations):
            x_previous = x_current.copy()

            # 记录当前迭代的误差
            mae_current = np.mean(np.abs(x_current - true_value))
            mse_current = np.mean((x_current - true_value) ** 2)
            rmse_current = np.sqrt(mse_current)

            iteration_errors.append({
                'iteration': iteration,
                'mae': mae_current,
                'mse': mse_current,
                'rmse': rmse_current
            })
            iteration_truths.append(x_current.copy())

            # 计算用户距离
            d_k = np.zeros(K_valid)
            for k in range(K_valid):
                d_k[k] = self.distance_function(valid_observations[k], x_current)

            d_k = np.maximum(d_k, self.eps_small)

            # 计算S和权重
            S = np.sum(valid_gamma * d_k)
            S = max(S, self.eps_small)

            omega = np.zeros(K_valid)
            for k in range(K_valid):
                if valid_gamma[k] > 0:
                    gamma_d = valid_gamma[k] * d_k[k]
                    gamma_d = max(gamma_d, self.eps_small)
                    omega[k] = np.log(S) - np.log(gamma_d)

            # 归一化权重
            if np.sum(valid_gamma) > 0:
                min_omega = np.min(omega[valid_gamma > 0]) if np.any(valid_gamma > 0) else 0
                omega = omega - min_omega

            # 更新真值
            numerator = np.zeros(D)
            denominator = 0

            for k in range(K_valid):
                if valid_gamma[k] > 0:
                    weight = valid_gamma[k] * omega[k]
                    numerator += weight * valid_observations[k]
                    denominator += weight

            if denominator > self.eps_small:
                x_current = numerator / denominator

            # 检查收敛
            diff = np.linalg.norm(x_current - x_previous)
            if diff < self.epsilon:
                # 记录最终误差
                mae_final = np.mean(np.abs(x_current - true_value))
                mse_final = np.mean((x_current - true_value) ** 2)
                rmse_final = np.sqrt(mse_final)

                iteration_errors.append({
                    'iteration': iteration + 1,
                    'mae': mae_final,
                    'mse': mse_final,
                    'rmse': rmse_final
                })
                iteration_truths.append(x_current.copy())

                return {
                    'final_truth': x_current,
                    'iterations': iteration + 1,
                    'converged': True,
                    'iteration_errors': iteration_errors,
                    'iteration_truths': iteration_truths,
                    'final_mae': mae_final,
                    'final_mse': mse_final,
                    'final_rmse': rmse_final
                }

        # 未收敛的情况
        mae_final = np.mean(np.abs(x_current - true_value))
        mse_final = np.mean((x_current - true_value) ** 2)
        rmse_final = np.sqrt(mse_final)

        return {
            'final_truth': x_current,
            'iterations': self.max_iterations,
            'converged': False,
            'iteration_errors': iteration_errors,
            'iteration_truths': iteration_truths,
            'final_mae': mae_final,
            'final_mse': mse_final,
            'final_rmse': rmse_final
        }

    def analyze_all_tasks(self, file_path: str) -> Dict:
        """分析所有任务的性能"""
        print("正在加载数据...")
        X, worker_reputations, task_true_values, all_workers, all_tasks = self.load_data(file_path)

        K, M, D = X.shape
        print(f"数据加载完成：{K}个用户，{M}个任务，每个观测{D}维")

        # 计算可靠度
        reputation_array = np.array([worker_reputations[worker_id] for worker_id in all_workers])
        gamma = self.compute_reliability(reputation_array)

        reliable_users = np.sum(gamma > 0)
        print(f"可靠用户数量：{reliable_users}/{K}")

        # 分析每个任务
        task_results = []
        cumulative_times = []

        print("\n开始任务分析...")
        start_total = time.time()

        for i, task_id in enumerate(all_tasks):
            start_time = time.time()

            # 获取任务数据
            task_observations = X[:, i, :]
            true_value = task_true_values[task_id]

            # 执行真相发现
            result = self.iterative_truth_discovery_single_task(
                task_observations, gamma, true_value
            )

            end_time = time.time()
            execution_time = end_time - start_time

            # 记录结果
            task_result = {
                'task_id': task_id,
                'task_index': i,
                'true_value': true_value,
                'predicted_value': result['final_truth'],
                'iterations': result['iterations'],
                'converged': result['converged'],
                'execution_time': execution_time,
                'final_mae': result['final_mae'],
                'final_mse': result['final_mse'],
                'final_rmse': result['final_rmse'],
                'iteration_errors': result['iteration_errors']
            }

            task_results.append(task_result)

            # 记录累计时间（每10个任务）
            if (i + 1) % 10 == 0:
                cumulative_time = time.time() - start_total
                cumulative_times.append({
                    'tasks_completed': i + 1,
                    'cumulative_time': cumulative_time
                })
                print(f"完成前{i + 1}个任务，累计时间：{cumulative_time:.4f}秒")

        total_time = time.time() - start_total
        print(f"\n所有任务完成，总时间：{total_time:.4f}秒")

        return {
            'task_results': task_results,
            'cumulative_times': cumulative_times,
            'total_execution_time': total_time,
            'algorithm_params': {
                'tau': self.tau,
                't0': self.t0,
                'epsilon': self.epsilon,
                'xi': self.xi
            }
        }

    def generate_detailed_report(self, results: Dict):
        """生成详细的分析报告"""
        task_results = results['task_results']
        cumulative_times = results['cumulative_times']

        print("\n" + "=" * 80)
        print("群智感知真相发现算法 - 详细性能分析报告")
        print("=" * 80)

        # 1. 算法参数
        params = results['algorithm_params']
        print(f"\n算法参数：")
        print(f"  声誉门槛 t₀ = {params['t0']}")
        print(f"  控制因子 τ = {params['tau']}")
        print(f"  收敛阈值 ε = {params['epsilon']}")
        print(f"  平滑常数 ξ = {params['xi']}")
        print(f"  距离函数：绝对差")

        # 2. 每代聚合真值误差统计
        print(f"\n每代聚合真值误差统计：")
        print("-" * 50)

        all_iterations = []
        all_maes = []
        all_mses = []
        all_rmses = []
        all_execution_times = []

        for i, result in enumerate(task_results):
            all_iterations.append(result['iterations'])
            all_maes.append(result['final_mae'])
            all_mses.append(result['final_mse'])
            all_rmses.append(result['final_rmse'])
            all_execution_times.append(result['execution_time'])

            print(f"任务{result['task_id']:3d}: MAE={result['final_mae']:8.4f}, "
                  f"MSE={result['final_mse']:8.4f}, RMSE={result['final_rmse']:8.4f}, "
                  f"迭代={result['iterations']:2d}次, 时间={result['execution_time']:6.4f}s")

        # 3. 迭代次数统计
        print(f"\n迭代次数统计：")
        print("-" * 30)
        print(f"  平均迭代次数：{np.mean(all_iterations):.2f}")
        print(f"  最少迭代次数：{np.min(all_iterations)}")
        print(f"  最多迭代次数：{np.max(all_iterations)}")
        print(f"  迭代次数标准差：{np.std(all_iterations):.2f}")

        converged_count = sum(1 for result in task_results if result['converged'])
        print(f"  收敛任务数：{converged_count}/{len(task_results)}")

        # 4. 执行时间统计
        print(f"\n执行时间统计：")
        print("-" * 30)
        print(f"  总执行时间：{results['total_execution_time']:.4f}秒")
        print(f"  平均单任务时间：{np.mean(all_execution_times):.4f}秒")
        print(f"  时间标准差：{np.std(all_execution_times):.4f}秒")

        # 5. 累计10个任务执行时间
        print(f"\n累计任务执行时间：")
        print("-" * 30)
        for timing in cumulative_times:
            print(f"  前{timing['tasks_completed']}个任务：{timing['cumulative_time']:.4f}秒")

        # 6. 前50次和后50次任务对比
        print(f"\n前50次 vs 后50次任务对比：")
        print("-" * 40)

        first_50_mae = all_maes[:50]
        first_50_mse = all_mses[:50]
        first_50_rmse = all_rmses[:50]

        last_50_mae = all_maes[50:] if len(all_maes) >= 100 else all_maes[50:]
        last_50_mse = all_mses[50:] if len(all_mses) >= 100 else all_mses[50:]
        last_50_rmse = all_rmses[50:] if len(all_rmses) >= 100 else all_rmses[50:]

        print("前50次任务：")
        print(f"  平均MAE：{np.mean(first_50_mae):.4f} ± {np.std(first_50_mae):.4f}")
        print(f"  平均MSE：{np.mean(first_50_mse):.4f} ± {np.std(first_50_mse):.4f}")
        print(f"  平均RMSE：{np.mean(first_50_rmse):.4f} ± {np.std(first_50_rmse):.4f}")

        if len(last_50_mae) > 0:
            print("后50次任务：")
            print(f"  平均MAE：{np.mean(last_50_mae):.4f} ± {np.std(last_50_mae):.4f}")
            print(f"  平均MSE：{np.mean(last_50_mse):.4f} ± {np.std(last_50_mse):.4f}")
            print(f"  平均RMSE：{np.mean(last_50_rmse):.4f} ± {np.std(last_50_rmse):.4f}")

        # 7. 总体误差统计
        print(f"\n总体误差统计（100次任务）：")
        print("-" * 40)
        print(f"  总体平均MAE：{np.mean(all_maes):.4f} ± {np.std(all_maes):.4f}")
        print(f"  总体平均MSE：{np.mean(all_mses):.4f} ± {np.std(all_mses):.4f}")
        print(f"  总体平均RMSE：{np.mean(all_rmses):.4f} ± {np.std(all_rmses):.4f}")
        print(f"  最佳MAE：{np.min(all_maes):.4f}")
        print(f"  最差MAE：{np.max(all_maes):.4f}")

        # 8. 收敛性分析
        print(f"\n收敛性分析：")
        print("-" * 20)
        quick_converged = sum(1 for iter_count in all_iterations if iter_count <= 5)
        medium_converged = sum(1 for iter_count in all_iterations if 6 <= iter_count <= 15)
        slow_converged = sum(1 for iter_count in all_iterations if iter_count > 15)

        print(f"  快速收敛（≤5次）：{quick_converged}个任务")
        print(f"  中等收敛（6-15次）：{medium_converged}个任务")
        print(f"  缓慢收敛（>15次）：{slow_converged}个任务")

        return {
            'overall_stats': {
                'mean_mae': np.mean(all_maes),
                'std_mae': np.std(all_maes),
                'mean_mse': np.mean(all_mses),
                'std_mse': np.std(all_mses),
                'mean_rmse': np.mean(all_rmses),
                'std_rmse': np.std(all_rmses),
                'mean_iterations': np.mean(all_iterations),
                'std_iterations': np.std(all_iterations)
            },
            'first_50_stats': {
                'mean_mae': np.mean(first_50_mae),
                'std_mae': np.std(first_50_mae),
                'mean_mse': np.mean(first_50_mse),
                'std_mse': np.std(first_50_mse),
                'mean_rmse': np.mean(first_50_rmse),
                'std_rmse': np.std(first_50_rmse)
            },
            'last_50_stats': {
                'mean_mae': np.mean(last_50_mae) if len(last_50_mae) > 0 else 0,
                'std_mae': np.std(last_50_mae) if len(last_50_mae) > 0 else 0,
                'mean_mse': np.mean(last_50_mse) if len(last_50_mse) > 0 else 0,
                'std_mse': np.std(last_50_mse) if len(last_50_mse) > 0 else 0,
                'mean_rmse': np.mean(last_50_rmse) if len(last_50_rmse) > 0 else 0,
                'std_rmse': np.std(last_50_rmse) if len(last_50_rmse) > 0 else 0
            }
        }


# 使用示例
if __name__ == "__main__":
    # 使用作者推荐参数
    algorithm = CrowdSensingTruthDiscoveryAnalysis(
        tau=0.1,  # 作者推荐值
        t0=0.5,  # 作者推荐值
        epsilon=1e-12,
        xi=1e-6,  # 作者推荐值
        max_iterations=100,
        distance_metric='absolute'  # 作者推荐绝对差
    )

    default_workload = Path(__file__).resolve().parents[2] / "data" / "workloads" / "Scene_2_Number_of_Workers_27.json"
    file_path = Path(os.environ.get("IRPP_WORKLOAD", default_workload))

    try:
        # 运行完整分析
        results = algorithm.analyze_all_tasks(file_path)

        # 生成详细报告
        report_stats = algorithm.generate_detailed_report(results)

        # 可选：保存结果到文件
        import json

        with open('detailed_analysis_results.json', 'w', encoding='utf-8') as f:
            # 转换numpy数组为list以便JSON序列化
            results_serializable = {}
            for key, value in results.items():
                if key == 'task_results':
                    results_serializable[key] = []
                    for task_result in value:
                        task_dict = task_result.copy()
                        task_dict['true_value'] = task_result['true_value'].tolist()
                        task_dict['predicted_value'] = task_result['predicted_value'].tolist()
                        results_serializable[key].append(task_dict)
                else:
                    results_serializable[key] = value

            json.dump(results_serializable, f, indent=2, ensure_ascii=False)

        print("\n详细结果已保存到 'detailed_analysis_results.json'")

    except FileNotFoundError:
        print(f"文件未找到：{file_path}")
        print("请确保文件路径正确")
    except Exception as e:
        print(f"运行出错：{e}")
        import traceback

        traceback.print_exc()
