import numpy as np
import json
import math
import time
import psutil
import os
from typing import Dict, List, Tuple
import tracemalloc
from datetime import datetime
from pathlib import Path


class BatchPerformanceMonitor:
    """批量性能监控类，用于监控多任务的累计性能"""

    def __init__(self):
        self.start_time = None
        self.cumulative_stats = {
            'total_execution_time': 0.0,
            'total_memory_increase': 0.0,
            'peak_memory_overall': 0.0,
            'total_iterations': 0,
            'total_tasks_processed': 0,
            'convergence_rate': 0.0,
            'average_accuracy': 0.0,
            'cumulative_mae': 0.0,
            'cumulative_mse': 0.0,
            'cumulative_rmse': 0.0
        }
        self.milestone_records = []
        self.task_results = []
        self.mae_per_task = []
        self.mse_per_task = []
        self.rmse_per_task = []
        self.process = psutil.Process(os.getpid())

    def start_batch_monitoring(self):
        """开始批量监控"""
        tracemalloc.start()
        self.start_time = time.perf_counter()
        initial_memory = self.process.memory_info().rss / 1024 / 1024
        self.cumulative_stats['initial_memory'] = initial_memory
        print(f"开始批量性能监控 - 初始内存: {initial_memory:.2f} MB")

    def calculate_metrics(self, true_values, estimated_values):
        """计算MAE、MSE和RMSE指标"""
        true_array = np.array(true_values)
        estimated_array = np.array(estimated_values)

        # MAE (Mean Absolute Error)
        mae = np.mean(np.abs(true_array - estimated_array))

        # MSE (Mean Squared Error)
        mse = np.mean((true_array - estimated_array) ** 2)

        # RMSE (Root Mean Square Error)
        rmse = np.sqrt(mse)

        return mae, mse, rmse

    def record_task_result(self, task_result, performance_metrics):
        """记录单个任务的结果"""
        # 计算当前任务的MAE、MSE、RMSE
        task_mae, task_mse, task_rmse = self.calculate_metrics(
            task_result['true_data'], task_result['estimated_truth'])

        self.mae_per_task.append(task_mae)
        self.mse_per_task.append(task_mse)
        self.rmse_per_task.append(task_rmse)

        accuracy_metrics = {
            'mae': task_mae,
            'mse': task_mse,
            'rmse': task_rmse
        }

        self.task_results.append({
            'task_id': task_result['task_id'],
            'performance': performance_metrics,
            'accuracy_metrics': accuracy_metrics,
            'converged': task_result['converged'],
            'iterations': task_result['iteration_count'],
            'mae': task_mae,
            'mse': task_mse,
            'rmse': task_rmse
        })

        # 打印每个任务的指标
        print(f"任务 {task_result['task_id']} - MAE: {task_mae:.6f}, MSE: {task_mse:.6f}, RMSE: {task_rmse:.6f}")

        # 更新累计统计
        self.cumulative_stats['total_execution_time'] += performance_metrics['execution_time_seconds']
        self.cumulative_stats['total_memory_increase'] += performance_metrics['memory_increase_mb']
        self.cumulative_stats['peak_memory_overall'] = max(
            self.cumulative_stats['peak_memory_overall'],
            performance_metrics['peak_memory_mb']
        )
        self.cumulative_stats['total_iterations'] += task_result['iteration_count']
        self.cumulative_stats['total_tasks_processed'] += 1

        # 更新累计指标
        self.cumulative_stats['cumulative_mae'] = np.mean(self.mae_per_task)
        self.cumulative_stats['cumulative_mse'] = np.mean(self.mse_per_task)
        self.cumulative_stats['cumulative_rmse'] = np.mean(self.rmse_per_task)

        # 检查是否需要记录里程碑（每10代记录一次）
        if self.cumulative_stats['total_tasks_processed'] % 10 == 0:
            self.record_milestone()

    def record_milestone(self):
        """记录里程碑性能数据（每10代）"""
        current_time = time.perf_counter()
        elapsed_time = current_time - self.start_time
        current_memory = self.process.memory_info().rss / 1024 / 1024

        completed_tasks = self.cumulative_stats['total_tasks_processed']
        converged_tasks = sum(1 for result in self.task_results if result['converged'])
        convergence_rate = (converged_tasks / completed_tasks) * 100 if completed_tasks > 0 else 0

        # 计算截至目前的指标统计
        current_metrics_stats = {
            'mean_mae': np.mean(self.mae_per_task),
            'mean_mse': np.mean(self.mse_per_task),
            'mean_rmse': np.mean(self.rmse_per_task),
            'std_mae': np.std(self.mae_per_task),
            'std_mse': np.std(self.mse_per_task),
            'std_rmse': np.std(self.rmse_per_task),
            'min_mae': np.min(self.mae_per_task),
            'min_mse': np.min(self.mse_per_task),
            'min_rmse': np.min(self.rmse_per_task),
            'max_mae': np.max(self.mae_per_task),
            'max_mse': np.max(self.mse_per_task),
            'max_rmse': np.max(self.rmse_per_task)
        }

        average_iterations = self.cumulative_stats['total_iterations'] / completed_tasks if completed_tasks > 0 else 0
        average_task_time = self.cumulative_stats[
                                'total_execution_time'] / completed_tasks if completed_tasks > 0 else 0

        milestone_record = {
            'milestone': completed_tasks,
            'timestamp': datetime.now().isoformat(),
            'elapsed_time_seconds': elapsed_time,
            'current_memory_mb': current_memory,
            'metrics_statistics': current_metrics_stats,
            'cumulative_stats': {
                'total_execution_time': self.cumulative_stats['total_execution_time'],
                'average_task_time_ms': average_task_time * 1000,
                'peak_memory_mb': self.cumulative_stats['peak_memory_overall'],
                'total_iterations': self.cumulative_stats['total_iterations'],
                'average_iterations_per_task': average_iterations,
                'convergence_rate_percent': convergence_rate,
                'cumulative_mean_mae': current_metrics_stats['mean_mae'],
                'cumulative_mean_mse': current_metrics_stats['mean_mse'],
                'cumulative_mean_rmse': current_metrics_stats['mean_rmse']
            },
            'performance_trends': self.analyze_recent_performance()
        }

        self.milestone_records.append(milestone_record)
        self.print_milestone_report(milestone_record)

    def analyze_recent_performance(self):
        """分析最近的性能趋势"""
        if len(self.task_results) < 10:
            return None

        recent_results = self.task_results[-10:]
        recent_times = [r['performance']['execution_time_seconds'] for r in recent_results]
        recent_memory = [r['performance']['memory_increase_mb'] for r in recent_results]
        recent_iterations = [r['iterations'] for r in recent_results]
        recent_mae = [r['mae'] for r in recent_results]
        recent_mse = [r['mse'] for r in recent_results]
        recent_rmse = [r['rmse'] for r in recent_results]

        return {
            'recent_avg_time_ms': np.mean(recent_times) * 1000,
            'recent_avg_memory_mb': np.mean(recent_memory),
            'recent_avg_iterations': np.mean(recent_iterations),
            'recent_avg_mae': np.mean(recent_mae),
            'recent_avg_mse': np.mean(recent_mse),
            'recent_avg_rmse': np.mean(recent_rmse),
            'mae_trend': 'improving' if np.mean(recent_mae[:5]) > np.mean(recent_mae[-5:]) else 'stable/degrading',
            'mse_trend': 'improving' if np.mean(recent_mse[:5]) > np.mean(recent_mse[-5:]) else 'stable/degrading',
            'rmse_trend': 'improving' if np.mean(recent_rmse[:5]) > np.mean(recent_rmse[-5:]) else 'stable/degrading'
        }

    def print_milestone_report(self, milestone_record):
        """打印里程碑报告"""
        print(f"\n{'=' * 60}")
        print(f"里程碑报告 - 已完成 {milestone_record['milestone']} 个任务")
        print(f"{'=' * 60}")

        cumulative = milestone_record['cumulative_stats']
        metrics_stats = milestone_record['metrics_statistics']

        print(f"累计执行时间: {cumulative['total_execution_time']:.2f} 秒")
        print(f"平均每任务时间: {cumulative['average_task_time_ms']:.2f} 毫秒")
        print(f"峰值内存使用: {cumulative['peak_memory_mb']:.2f} MB")
        print(f"平均迭代次数: {cumulative['average_iterations_per_task']:.1f}")
        print(f"收敛率: {cumulative['convergence_rate_percent']:.1f}%")

        print(f"\n评估指标统计:")
        print(f"  平均MAE: {metrics_stats['mean_mae']:.6f}")
        print(f"  平均MSE: {metrics_stats['mean_mse']:.6f}")
        print(f"  平均RMSE: {metrics_stats['mean_rmse']:.6f}")
        print(f"  MAE标准差: {metrics_stats['std_mae']:.6f}")
        print(f"  MSE标准差: {metrics_stats['std_mse']:.6f}")
        print(f"  RMSE标准差: {metrics_stats['std_rmse']:.6f}")

        if milestone_record['performance_trends']:
            trends = milestone_record['performance_trends']
            print(f"\n最近10个任务趋势:")
            print(f"  平均时间: {trends['recent_avg_time_ms']:.2f}ms")
            print(f"  平均MAE: {trends['recent_avg_mae']:.6f} ({trends['mae_trend']})")
            print(f"  平均MSE: {trends['recent_avg_mse']:.6f} ({trends['mse_trend']})")
            print(f"  平均RMSE: {trends['recent_avg_rmse']:.6f} ({trends['rmse_trend']})")


def crh_algorithm_optimized(data_vectors, epsilon=1e-12, max_iterations=100):
    """优化后的CRH算法，用于批量处理"""
    monitor_start = time.perf_counter()
    initial_memory = psutil.Process(os.getpid()).memory_info().rss / 1024 / 1024

    data_matrix = np.array(data_vectors)
    m, d = data_matrix.shape

    t = 0
    weights = np.ones(m) / m
    truth_estimate = np.zeros(d)

    while t < max_iterations:
        t += 1
        previous_truth = truth_estimate.copy()

        # 更新真值估计
        weighted_sum = np.sum(weights[:, np.newaxis] * data_matrix, axis=0)
        weight_sum = np.sum(weights)
        truth_estimate = weighted_sum / weight_sum

        # 更新权重
        distances_squared = np.sum((data_matrix - previous_truth) ** 2, axis=1)
        distances_squared = np.maximum(distances_squared, 1e-10)

        total_distance_squared = np.sum(distances_squared)
        total_distance_squared = max(total_distance_squared, 1e-10)

        log_total = math.log(total_distance_squared)
        new_weights = log_total - np.log(distances_squared)

        weights = new_weights

        # 检查收敛
        convergence_measure = np.linalg.norm(truth_estimate - previous_truth)
        if convergence_measure < epsilon:
            break

    # 计算性能指标
    monitor_end = time.perf_counter()
    final_memory = psutil.Process(os.getpid()).memory_info().rss / 1024 / 1024

    performance_metrics = {
        'execution_time_seconds': monitor_end - monitor_start,
        'execution_time_milliseconds': (monitor_end - monitor_start) * 1000,
        'initial_memory_mb': initial_memory,
        'final_memory_mb': final_memory,
        'memory_increase_mb': final_memory - initial_memory,
        'peak_memory_mb': final_memory
    }

    return truth_estimate, weights, t, convergence_measure < epsilon, performance_metrics


def process_all_tasks_with_metrics_analysis(json_file_path):
    """处理所有任务并进行MAE、MSE、RMSE分析"""

    # 读取数据
    try:
        with open(json_file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except FileNotFoundError:
        print(f"文件未找到: {json_file_path}")
        return
    except json.JSONDecodeError:
        print("JSON文件格式错误")
        return

    task_worker_data = data.get('task_worker_data', {})
    total_tasks = len(task_worker_data)

    print(f"准备处理 {total_tasks} 个任务，将计算每个任务的MAE、MSE、RMSE指标")

    # 初始化批量监控
    batch_monitor = BatchPerformanceMonitor()
    batch_monitor.start_batch_monitoring()

    all_results = []

    # 处理每个任务
    for i, (task_key, task_data) in enumerate(task_worker_data.items(), 1):
        print(f"\n处理任务 {i}/{total_tasks} (ID: {task_data['task_id']})")

        # 提取数据
        worker_submissions = task_data['worker_submissions']
        data_vectors = [submission['submitted_data'] for submission in worker_submissions]

        print(f"真实值: {task_data['task_true_data']}")

        # 执行CRH算法
        final_truth, weights, iterations, converged, performance_metrics = crh_algorithm_optimized(data_vectors)

        print(f"估计值: {final_truth.tolist()}")

        # 构建结果
        task_result = {
            'task_id': task_data['task_id'],
            'estimated_truth': final_truth.tolist(),
            'true_data': task_data['task_true_data'],
            'iteration_count': iterations,
            'converged': converged,
            'worker_count': len(worker_submissions)
        }

        all_results.append(task_result)

        # 记录到批量监控器（这里会计算并打印MAE、MSE、RMSE）
        batch_monitor.record_task_result(task_result, performance_metrics)

    # 处理剩余任务（如果不是10的倍数）
    if total_tasks % 10 != 0:
        batch_monitor.record_milestone()

    return batch_monitor, all_results


def output_first_vs_second_half_errors(mae_values, mse_values, rmse_values):
    """直接输出前50代和后50代的平均误差"""
    half_point = len(mae_values) // 2

    # 前50代平均误差
    first_half_mae_avg = np.mean(mae_values[:half_point])
    first_half_mse_avg = np.mean(mse_values[:half_point])
    first_half_rmse_avg = np.mean(rmse_values[:half_point])

    # 后50代平均误差
    second_half_mae_avg = np.mean(mae_values[half_point:])
    second_half_mse_avg = np.mean(mse_values[half_point:])
    second_half_rmse_avg = np.mean(rmse_values[half_point:])

    print(f"\n前{half_point}代平均误差:")
    print(f"平均MAE: {first_half_mae_avg:.6f}")
    print(f"平均MSE: {first_half_mse_avg:.6f}")
    print(f"平均RMSE: {first_half_rmse_avg:.6f}")

    print(f"\n后{len(mae_values) - half_point}代平均误差:")
    print(f"平均MAE: {second_half_mae_avg:.6f}")
    print(f"平均MSE: {second_half_mse_avg:.6f}")
    print(f"平均RMSE: {second_half_rmse_avg:.6f}")


def generate_metrics_analysis_report(batch_monitor, all_results, output_file=None):
    """生成包含详细MAE、MSE、RMSE分析的最终报告"""

    total_time = time.perf_counter() - batch_monitor.start_time

    # 详细指标分析
    mae_values = batch_monitor.mae_per_task
    mse_values = batch_monitor.mse_per_task
    rmse_values = batch_monitor.rmse_per_task

    metrics_analysis = {
        'mae_analysis': {
            'mean': np.mean(mae_values),
            'std': np.std(mae_values),
            'min': np.min(mae_values),
            'max': np.max(mae_values),
            'median': np.median(mae_values),
            'percentiles': {
                '25th': np.percentile(mae_values, 25),
                '75th': np.percentile(mae_values, 75),
                '90th': np.percentile(mae_values, 90),
                '95th': np.percentile(mae_values, 95)
            }
        },
        'mse_analysis': {
            'mean': np.mean(mse_values),
            'std': np.std(mse_values),
            'min': np.min(mse_values),
            'max': np.max(mse_values),
            'median': np.median(mse_values),
            'percentiles': {
                '25th': np.percentile(mse_values, 25),
                '75th': np.percentile(mse_values, 75),
                '90th': np.percentile(mse_values, 90),
                '95th': np.percentile(mse_values, 95)
            }
        },
        'rmse_analysis': {
            'mean': np.mean(rmse_values),
            'std': np.std(rmse_values),
            'min': np.min(rmse_values),
            'max': np.max(rmse_values),
            'median': np.median(rmse_values),
            'percentiles': {
                '25th': np.percentile(rmse_values, 25),
                '75th': np.percentile(rmse_values, 75),
                '90th': np.percentile(rmse_values, 90),
                '95th': np.percentile(rmse_values, 95)
            }
        }
    }

    # 计算整体统计
    total_tasks = len(all_results)
    converged_tasks = sum(1 for result in all_results if result['converged'])
    convergence_rate = (converged_tasks / total_tasks) * 100

    total_iterations = sum(result['iteration_count'] for result in all_results)
    avg_iterations = total_iterations / total_tasks

    final_report = {
        'execution_summary': {
            'total_tasks_processed': total_tasks,
            'total_execution_time_seconds': total_time,
            'average_time_per_task_ms': (batch_monitor.cumulative_stats['total_execution_time'] / total_tasks) * 1000,
            'peak_memory_usage_mb': batch_monitor.cumulative_stats['peak_memory_overall'],
            'total_iterations': total_iterations,
            'average_iterations_per_task': avg_iterations,
            'convergence_rate_percent': convergence_rate
        },
        'metrics_analysis': metrics_analysis,
        'milestone_records': batch_monitor.milestone_records,
        'individual_task_metrics': [
            {
                'task_id': result['task_id'],
                'mae': batch_monitor.task_results[i]['mae'],
                'mse': batch_monitor.task_results[i]['mse'],
                'rmse': batch_monitor.task_results[i]['rmse'],
                'iterations': result['iteration_count'],
                'execution_time_ms': batch_monitor.task_results[i]['performance']['execution_time_milliseconds']
            }
            for i, result in enumerate(all_results)
        ]
    }

    # 打印最终报告
    print(f"\n{'=' * 80}")
    print("CRH算法批量处理 - MAE/MSE/RMSE分析报告")
    print(f"{'=' * 80}")

    summary = final_report['execution_summary']
    print(f"总任务数: {summary['total_tasks_processed']}")
    print(f"总执行时间: {summary['total_execution_time_seconds']:.2f} 秒")
    print(f"平均每任务时间: {summary['average_time_per_task_ms']:.2f} 毫秒")
    print(f"收敛成功率: {summary['convergence_rate_percent']:.1f}%")

    print(f"\nMAE详细分析:")
    mae_analysis = metrics_analysis['mae_analysis']
    print(f"整体平均MAE: {mae_analysis['mean']:.6f}")
    print(f"MAE标准差: {mae_analysis['std']:.6f}")
    print(f"最佳MAE: {mae_analysis['min']:.6f}")
    print(f"最差MAE: {mae_analysis['max']:.6f}")
    print(f"MAE中位数: {mae_analysis['median']:.6f}")

    print(f"\nMSE详细分析:")
    mse_analysis = metrics_analysis['mse_analysis']
    print(f"整体平均MSE: {mse_analysis['mean']:.6f}")
    print(f"MSE标准差: {mse_analysis['std']:.6f}")
    print(f"最佳MSE: {mse_analysis['min']:.6f}")
    print(f"最差MSE: {mse_analysis['max']:.6f}")
    print(f"MSE中位数: {mse_analysis['median']:.6f}")

    print(f"\nRMSE详细分析:")
    rmse_analysis = metrics_analysis['rmse_analysis']
    print(f"整体平均RMSE: {rmse_analysis['mean']:.6f}")
    print(f"RMSE标准差: {rmse_analysis['std']:.6f}")
    print(f"最佳RMSE: {rmse_analysis['min']:.6f}")
    print(f"最差RMSE: {rmse_analysis['max']:.6f}")
    print(f"RMSE中位数: {rmse_analysis['median']:.6f}")

    output_first_vs_second_half_errors(mae_values, mse_values, rmse_values)

    # 找出各指标最好和最差的任务
    best_mae_idx = np.argmin(mae_values)
    worst_mae_idx = np.argmax(mae_values)
    best_mse_idx = np.argmin(mse_values)
    worst_mse_idx = np.argmax(mse_values)
    best_rmse_idx = np.argmin(rmse_values)
    worst_rmse_idx = np.argmax(rmse_values)

    print(f"\n最佳表现任务:")
    print(f"MAE最佳: 任务{all_results[best_mae_idx]['task_id']}, MAE = {mae_values[best_mae_idx]:.6f}")
    print(f"MSE最佳: 任务{all_results[best_mse_idx]['task_id']}, MSE = {mse_values[best_mse_idx]:.6f}")
    print(f"RMSE最佳: 任务{all_results[best_rmse_idx]['task_id']}, RMSE = {rmse_values[best_rmse_idx]:.6f}")

    print(f"\n最差表现任务:")
    print(f"MAE最差: 任务{all_results[worst_mae_idx]['task_id']}, MAE = {mae_values[worst_mae_idx]:.6f}")
    print(f"MSE最差: 任务{all_results[worst_mse_idx]['task_id']}, MSE = {mse_values[worst_mse_idx]:.6f}")
    print(f"RMSE最差: 任务{all_results[worst_rmse_idx]['task_id']}, RMSE = {rmse_values[worst_rmse_idx]:.6f}")

    # 保存报告到文件
    if output_file:
        try:
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(final_report, f, ensure_ascii=False, indent=2)
            print(f"\n详细报告已保存到: {output_file}")
        except Exception as e:
            print(f"保存报告时出错: {e}")

    return final_report


# 主程序执行
if __name__ == "__main__":
    default_workload = Path(__file__).resolve().parents[2] / "data" / "workloads" / "Scene_2_Number_of_Workers_27.json"
    input_file = Path(os.environ.get("IRPP_WORKLOAD", default_workload))
    output_report_file = Path(__file__).with_name("crh_metrics_analysis_report.json")

    print("开始CRH算法批量性能测试及MAE/MSE/RMSE分析...")
    print(f"数据文件: {input_file}")

    # 处理所有任务
    batch_monitor, all_results = process_all_tasks_with_metrics_analysis(input_file)

    # 生成最终报告
    final_report = generate_metrics_analysis_report(batch_monitor, all_results, output_report_file)

    print(f"\n批量指标分析完成!")
    print(f"共处理了 {len(all_results)} 个任务")
    print(f"整体平均MAE: {final_report['metrics_analysis']['mae_analysis']['mean']:.6f}")
    print(f"整体平均MSE: {final_report['metrics_analysis']['mse_analysis']['mean']:.6f}")
    print(f"整体平均RMSE: {final_report['metrics_analysis']['rmse_analysis']['mean']:.6f}")

