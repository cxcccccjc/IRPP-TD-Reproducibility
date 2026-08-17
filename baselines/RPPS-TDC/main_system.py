import json
import numpy as np
import os
import time
from collections import defaultdict
from typing import Dict, List, Tuple
from pathlib import Path
from truth_discovery import truth_discovery
from reputation_update import reputation_update


class WorkerReputationSystem:
    def __init__(self, json_file_path: str):
        """
        初始化工人信誉管理系统

        参数:
        - json_file_path: 任务数据JSON文件路径
        """
        self.json_file_path = json_file_path
        self.task_data = self._load_task_data()

        # 初始化100个工人的信誉和状态
        self.workers = {}
        for worker_id in range(1, 101):
            self.workers[worker_id] = {
                'historical_reputation': 0.7,  # 历史任务信誉值，初始为0.7
                'non_updated_reputation': 0.7,  # 未更新信誉值，初始为0.7
                'cheating_count': 0,  # 犯错次数
                'consecutive_good_tasks': 0,  # 连续无错任务数
                'task_history': []  # 任务历史记录
            }

        # 系统累计统计信息
        self.total_execution_time = 0.0
        self.total_iterations = 0
        self.all_crh_errors = []
        self.all_good_workers_errors = []

        # 每10个任务的统计
        self.batch_stats = []

    def _load_task_data(self) -> dict:
        """加载任务数据"""
        try:
            with open(self.json_file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return data['task_worker_data']
        except FileNotFoundError:
            raise FileNotFoundError(f"找不到文件: {self.json_file_path}")
        except json.JSONDecodeError:
            raise ValueError(f"JSON文件格式错误: {self.json_file_path}")

    def process_single_task(self, task_id: str) -> dict:
        """
        处理单个任务

        参数:
        - task_id: 任务ID

        返回:
        - 任务处理结果字典
        """
        task_info = self.task_data[task_id]
        ground_truth = task_info['task_true_data']
        worker_submissions = task_info['worker_submissions']

        # 准备数据格式
        worker_data = {}
        current_worker_reputations = {}
        participating_workers = []

        for submission in worker_submissions:
            worker_id = submission['worker_id']
            submitted_data = submission['submitted_data']

            worker_data[worker_id] = submitted_data
            current_worker_reputations[worker_id] = self.workers[worker_id]['historical_reputation']
            participating_workers.append(worker_id)

        # 执行真相发现算法
        truth_result = truth_discovery(
            worker_data=worker_data,
            worker_reputations=current_worker_reputations,
            ground_truth=ground_truth,
            p=0.3,
            epsilon=1e-3,
            max_iterations=100
        )

        (aggregated_truth, worker_weights, execution_time,
         iteration_count, error_metrics, data_quality_assessment) = truth_result

        # 更新系统统计信息
        self.total_execution_time += execution_time
        self.total_iterations += iteration_count

        if error_metrics:
            self.all_crh_errors.append([
                error_metrics['CRH_MAE'],
                error_metrics['CRH_MSE'],
                error_metrics['CRH_RMSE']
            ])

            if error_metrics['GOOD_WORKERS_AVG_MAE'] is not None:
                self.all_good_workers_errors.append([
                    error_metrics['GOOD_WORKERS_AVG_MAE'],
                    error_metrics['GOOD_WORKERS_AVG_MSE'],
                    error_metrics['GOOD_WORKERS_AVG_RMSE']
                ])

        # 更新参与任务的工人信誉
        for worker_id in participating_workers:
            is_good_data = data_quality_assessment[worker_id]

            # 更新连续无错计数和犯错计数
            if is_good_data:
                self.workers[worker_id]['consecutive_good_tasks'] += 1
                # 连续三个任务无错可以减少犯错次数
                if self.workers[worker_id]['consecutive_good_tasks'] >= 3:
                    if self.workers[worker_id]['cheating_count'] > 0:
                        self.workers[worker_id]['cheating_count'] -= 1
                    self.workers[worker_id]['consecutive_good_tasks'] = 0
            else:
                self.workers[worker_id]['consecutive_good_tasks'] = 0
                self.workers[worker_id]['cheating_count'] += 1

            # 使用信誉更新算法更新工人信誉
            current_task_reputation, updated_reputation = reputation_update(
                is_good_data=is_good_data,
                historical_reputation=self.workers[worker_id]['historical_reputation'],
                non_updated_reputation=self.workers[worker_id]['non_updated_reputation'],
                cheating_count=self.workers[worker_id]['cheating_count'],
                alpha=0.3,
                k1=1,
                k2=20
            )

            # 更新工人信誉信息
            self.workers[worker_id]['historical_reputation'] = current_task_reputation
            self.workers[worker_id]['non_updated_reputation'] = updated_reputation

            # 记录任务历史
            self.workers[worker_id]['task_history'].append({
                'task_id': int(task_id),
                'is_good_data': is_good_data,
                'weight': worker_weights[worker_id],
                'reputation_after_task': current_task_reputation
            })

        return {
            'task_id': int(task_id),
            'aggregated_truth': aggregated_truth,
            'ground_truth': ground_truth,
            'execution_time': execution_time,
            'iteration_count': iteration_count,
            'error_metrics': error_metrics,
            'participating_workers': len(participating_workers),
            'good_workers_count': sum(1 for is_good in data_quality_assessment.values() if is_good)
        }

    def calculate_batch_statistics(self, batch_errors_crh: List, batch_errors_good: List) -> dict:
        """计算批次统计信息"""
        stats = {}

        if batch_errors_crh:
            crh_errors_array = np.array(batch_errors_crh)
            stats['crh_mae_mean'] = np.mean(crh_errors_array[:, 0])
            stats['crh_mae_std'] = np.std(crh_errors_array[:, 0])
            stats['crh_mse_mean'] = np.mean(crh_errors_array[:, 1])
            stats['crh_mse_std'] = np.std(crh_errors_array[:, 1])
            stats['crh_rmse_mean'] = np.mean(crh_errors_array[:, 2])
            stats['crh_rmse_std'] = np.std(crh_errors_array[:, 2])

        if batch_errors_good:
            good_errors_array = np.array(batch_errors_good)
            stats['good_mae_mean'] = np.mean(good_errors_array[:, 0])
            stats['good_mae_std'] = np.std(good_errors_array[:, 0])
            stats['good_mse_mean'] = np.mean(good_errors_array[:, 1])
            stats['good_mse_std'] = np.std(good_errors_array[:, 1])
            stats['good_rmse_mean'] = np.mean(good_errors_array[:, 2])
            stats['good_rmse_std'] = np.std(good_errors_array[:, 2])
        else:
            stats.update({
                'good_mae_mean': None, 'good_mae_std': None,
                'good_mse_mean': None, 'good_mse_std': None,
                'good_rmse_mean': None, 'good_rmse_std': None
            })

        return stats

    def run_all_tasks(self):
        """运行所有100个任务"""
        print("开始处理100个任务...")
        print("=" * 80)

        batch_crh_errors = []
        batch_good_errors = []
        batch_execution_time = 0.0
        batch_iterations = 0

        for task_id in range(1, 101):
            task_id_str = str(task_id)
            if task_id_str not in self.task_data:
                print(f"警告: 找不到任务 {task_id}")
                continue

            # 处理单个任务
            result = self.process_single_task(task_id_str)

            # 累计批次数据
            batch_execution_time += result['execution_time']
            batch_iterations += result['iteration_count']

            if result['error_metrics']:
                batch_crh_errors.append([
                    result['error_metrics']['CRH_MAE'],
                    result['error_metrics']['CRH_MSE'],
                    result['error_metrics']['CRH_RMSE']
                ])

                if result['error_metrics']['GOOD_WORKERS_AVG_MAE'] is not None:
                    batch_good_errors.append([
                        result['error_metrics']['GOOD_WORKERS_AVG_MAE'],
                        result['error_metrics']['GOOD_WORKERS_AVG_MSE'],
                        result['error_metrics']['GOOD_WORKERS_AVG_RMSE']
                    ])

            # 每10个任务输出统计信息
            if task_id % 10 == 0:
                print(f"\n任务 {task_id - 9} - {task_id} 批次统计:")
                print(f"累计执行时间: {batch_execution_time:.4f} 秒")
                print(f"累计迭代次数: {batch_iterations}")

                # 计算批次误差统计
                batch_stats = self.calculate_batch_statistics(batch_crh_errors, batch_good_errors)

                print(f"\nCRH算法误差统计 (最近10个任务):")
                if batch_crh_errors:
                    print(f"  MAE: 均值={batch_stats['crh_mae_mean']:.6f}, 标准差={batch_stats['crh_mae_std']:.6f}")
                    print(f"  MSE: 均值={batch_stats['crh_mse_mean']:.6f}, 标准差={batch_stats['crh_mse_std']:.6f}")
                    print(f"  RMSE: 均值={batch_stats['crh_rmse_mean']:.6f}, 标准差={batch_stats['crh_rmse_std']:.6f}")

                print(f"\n优秀工人平均值误差统计 (最近10个任务):")
                if batch_good_errors:
                    print(f"  MAE: 均值={batch_stats['good_mae_mean']:.6f}, 标准差={batch_stats['good_mae_std']:.6f}")
                    print(f"  MSE: 均值={batch_stats['good_mse_mean']:.6f}, 标准差={batch_stats['good_mse_std']:.6f}")
                    print(
                        f"  RMSE: 均值={batch_stats['good_rmse_mean']:.6f}, 标准差={batch_stats['good_rmse_std']:.6f}")
                    print(f"  有效任务数: {len(batch_good_errors)}/10")
                else:
                    print("  没有找到优秀工人数据")

                print("=" * 80)

                # 保存批次统计
                self.batch_stats.append({
                    'batch_range': f"{task_id - 9}-{task_id}",
                    'execution_time': batch_execution_time,
                    'iterations': batch_iterations,
                    'crh_errors_count': len(batch_crh_errors),
                    'good_errors_count': len(batch_good_errors),
                    **batch_stats
                })

                # 重置批次计数器
                batch_crh_errors = []
                batch_good_errors = []
                batch_execution_time = 0.0
                batch_iterations = 0

    def print_final_summary(self):
        """打印最终总结"""
        print("\n" + "=" * 80)
        print("最终统计总结")
        print("=" * 80)

        print(f"总执行时间: {self.total_execution_time:.4f} 秒")
        print(f"总迭代次数: {self.total_iterations}")
        print(f"平均每任务执行时间: {self.total_execution_time / 100:.4f} 秒")
        print(f"平均每任务迭代次数: {self.total_iterations / 100:.1f}")

        # 计算所有任务的误差统计
        if self.all_crh_errors:
            all_crh_array = np.array(self.all_crh_errors)
            print(f"\nCRH算法总体误差统计 (100个任务):")
            print(f"  MAE: 均值={np.mean(all_crh_array[:, 0]):.6f}, 标准差={np.std(all_crh_array[:, 0]):.6f}")
            print(f"  MSE: 均值={np.mean(all_crh_array[:, 1]):.6f}, 标准差={np.std(all_crh_array[:, 1]):.6f}")
            print(f"  RMSE: 均值={np.mean(all_crh_array[:, 2]):.6f}, 标准差={np.std(all_crh_array[:, 2]):.6f}")

            # 前50个任务误差统计
            if len(all_crh_array) >= 50:
                first_50_crh = all_crh_array[:50]
                print(f"\nCRH算法前50个任务误差统计:")
                print(f"  MAE: 均值={np.mean(first_50_crh[:, 0]):.6f}, 标准差={np.std(first_50_crh[:, 0]):.6f}")
                print(f"  MSE: 均值={np.mean(first_50_crh[:, 1]):.6f}, 标准差={np.std(first_50_crh[:, 1]):.6f}")
                print(f"  RMSE: 均值={np.mean(first_50_crh[:, 2]):.6f}, 标准差={np.std(first_50_crh[:, 2]):.6f}")

            # 后50个任务误差统计
            if len(all_crh_array) >= 100:
                last_50_crh = all_crh_array[50:]
                print(f"\nCRH算法后50个任务误差统计:")
                print(f"  MAE: 均值={np.mean(last_50_crh[:, 0]):.6f}, 标准差={np.std(last_50_crh[:, 0]):.6f}")
                print(f"  MSE: 均值={np.mean(last_50_crh[:, 1]):.6f}, 标准差={np.std(last_50_crh[:, 1]):.6f}")
                print(f"  RMSE: 均值={np.mean(last_50_crh[:, 2]):.6f}, 标准差={np.std(last_50_crh[:, 2]):.6f}")

        if self.all_good_workers_errors:
            all_good_array = np.array(self.all_good_workers_errors)
            print(f"\n优秀工人平均值总体误差统计:")
            print(f"  MAE: 均值={np.mean(all_good_array[:, 0]):.6f}, 标准差={np.std(all_good_array[:, 0]):.6f}")
            print(f"  MSE: 均值={np.mean(all_good_array[:, 1]):.6f}, 标准差={np.std(all_good_array[:, 1]):.6f}")
            print(f"  RMSE: 均值={np.mean(all_good_array[:, 2]):.6f}, 标准差={np.std(all_good_array[:, 2]):.6f}")
            print(f"  有效任务数: {len(self.all_good_workers_errors)}/100")

            # 前50个任务中有效的优秀工人误差统计
            if len(all_good_array) >= 25:  # 假设前50个任务中至少有25个有优秀工人数据
                # 由于good_workers_errors的索引对应的是有优秀工人的任务，需要根据实际情况分割
                mid_point = len(all_good_array) // 2
                first_half_good = all_good_array[:mid_point]
                print(f"\n优秀工人前半部分任务误差统计:")
                print(f"  MAE: 均值={np.mean(first_half_good[:, 0]):.6f}, 标准差={np.std(first_half_good[:, 0]):.6f}")
                print(f"  MSE: 均值={np.mean(first_half_good[:, 1]):.6f}, 标准差={np.std(first_half_good[:, 1]):.6f}")
                print(f"  RMSE: 均值={np.mean(first_half_good[:, 2]):.6f}, 标准差={np.std(first_half_good[:, 2]):.6f}")
                print(f"  有效任务数: {len(first_half_good)}")

                # 后半部分任务中有效的优秀工人误差统计
                last_half_good = all_good_array[mid_point:]
                print(f"\n优秀工人后半部分任务误差统计:")
                print(f"  MAE: 均值={np.mean(last_half_good[:, 0]):.6f}, 标准差={np.std(last_half_good[:, 0]):.6f}")
                print(f"  MSE: 均值={np.mean(last_half_good[:, 1]):.6f}, 标准差={np.std(last_half_good[:, 1]):.6f}")
                print(f"  RMSE: 均值={np.mean(last_half_good[:, 2]):.6f}, 标准差={np.std(last_half_good[:, 2]):.6f}")
                print(f"  有效任务数: {len(last_half_good)}")

        # 工人信誉分布统计
        reputations = [worker['historical_reputation'] for worker in self.workers.values()]
        cheating_counts = [worker['cheating_count'] for worker in self.workers.values()]

        print(f"\n工人信誉分布:")
        print(f"  平均信誉值: {np.mean(reputations):.4f}")
        print(f"  信誉标准差: {np.std(reputations):.4f}")
        print(f"  最高信誉值: {np.max(reputations):.4f}")
        print(f"  最低信誉值: {np.min(reputations):.4f}")

        print(f"\n工人犯错统计:")
        print(f"  平均犯错次数: {np.mean(cheating_counts):.2f}")
        print(f"  总犯错次数: {np.sum(cheating_counts)}")
        print(f"  无犯错工人数: {sum(1 for count in cheating_counts if count == 0)}")

    def print_worker_reputation_details(self):
        """打印每个工人的详细信誉记录情况"""
        print("\n" + "=" * 80)
        print("工人信誉详细记录")
        print("=" * 80)

        # 按信誉值从高到低排序
        sorted_workers = sorted(self.workers.items(),
                                key=lambda x: x[1]['historical_reputation'],
                                reverse=True)

        print(f"{'工人ID':<8} {'最终信誉':<12} {'未更新信誉':<12} {'犯错次数':<8} {'参与任务数':<10} {'任务记录'}")
        print("-" * 80)

        for worker_id, worker_info in sorted_workers:
            final_reputation = worker_info['historical_reputation']
            non_updated_reputation = worker_info['non_updated_reputation']
            cheating_count = worker_info['cheating_count']
            tasks_count = len(worker_info['task_history'])

            # 构建任务记录简要信息
            if tasks_count > 0:
                good_tasks = sum(1 for task in worker_info['task_history'] if task['is_good_data'])
                task_summary = f"{good_tasks}优/{tasks_count}总"

                # 显示最后5个任务的表现
                recent_tasks = worker_info['task_history'][-5:]
                recent_performance = "".join("✓" if task['is_good_data'] else "✗"
                                             for task in recent_tasks)
                task_record = f"{task_summary} 近期:{recent_performance}"
            else:
                task_record = "未参与任务"

            print(f"{worker_id:<8} {final_reputation:<12.4f} {non_updated_reputation:<12.4f} "
                  f"{cheating_count:<8} {tasks_count:<10} {task_record}")

        # 输出信誉分布统计
        print("\n" + "-" * 80)
        print("信誉分布统计:")

        reputations = [worker['historical_reputation'] for worker in self.workers.values()]

        # 按信誉区间统计
        ranges = [(0.9, 1.0, "优秀"), (0.8, 0.9, "良好"), (0.7, 0.8, "中等"),
                  (0.6, 0.7, "一般"), (0.0, 0.6, "较差")]

        for min_rep, max_rep, label in ranges:
            count = sum(1 for rep in reputations if min_rep <= rep < max_rep)
            percentage = count / len(reputations) * 100
            print(f"{label}工人 ({min_rep}-{max_rep}): {count}人 ({percentage:.1f}%)")

        # 输出参与任务最多和最少的工人
        task_counts = {worker_id: len(info['task_history'])
                       for worker_id, info in self.workers.items()}

        most_active = max(task_counts.items(), key=lambda x: x[1])
        least_active = min(task_counts.items(), key=lambda x: x[1])

        print(f"\n最活跃工人: 工人{most_active[0]} (参与{most_active[1]}个任务)")
        print(f"最不活跃工人: 工人{least_active[0]} (参与{least_active[1]}个任务)")

        # 输出犯错最多和最少的工人
        cheating_counts = {worker_id: info['cheating_count']
                           for worker_id, info in self.workers.items()}

        most_errors = max(cheating_counts.items(), key=lambda x: x[1])
        least_errors = min(cheating_counts.items(), key=lambda x: x[1])

        print(f"犯错最多工人: 工人{most_errors[0]} (犯错{most_errors[1]}次)")
        print(f"犯错最少工人: 工人{least_errors[0]} (犯错{least_errors[1]}次)")

    def print_top_bottom_workers(self, top_n: int = 10):
        """打印信誉最高和最低的工人详细信息"""
        print(f"\n" + "=" * 80)
        print(f"信誉最高和最低的{top_n}个工人详细信息")
        print("=" * 80)

        # 按信誉值排序
        sorted_workers = sorted(self.workers.items(),
                                key=lambda x: x[1]['historical_reputation'],
                                reverse=True)


    def save_results(self, output_file: str = "system_results.json"):
        """保存结果到文件"""
        results = {
            'system_summary': {
                'total_execution_time': self.total_execution_time,
                'total_iterations': self.total_iterations,
                'total_tasks_processed': 100
            },
            'batch_statistics': self.batch_stats,
            'worker_final_states': {
                str(worker_id): {
                    'final_reputation': worker_info['historical_reputation'],
                    'non_updated_reputation': worker_info['non_updated_reputation'],
                    'total_cheating_count': worker_info['cheating_count'],
                    'tasks_participated': len(worker_info['task_history'])
                }
                for worker_id, worker_info in self.workers.items()
            }
        }

        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2, ensure_ascii=False)

        print(f"\n结果已保存到: {output_file}")

    def save_detailed_worker_results(self, output_file: str = "detailed_worker_results.json"):
        """保存详细的工人信誉记录到文件"""
        detailed_results = {
            'generation_info': {
                'total_tasks': 100,
                'total_workers': 100,
                'generation_time': time.strftime("%Y-%m-%d %H:%M:%S")
            },
            'worker_detailed_records': {}
        }

        for worker_id, worker_info in self.workers.items():
            tasks_participated = len(worker_info['task_history'])
            good_tasks = sum(1 for task in worker_info['task_history'] if task['is_good_data'])
            accuracy = (good_tasks / tasks_participated * 100) if tasks_participated > 0 else 0

            # 转换任务历史记录中的数据类型
            task_history_serializable = []
            for task in worker_info['task_history']:
                task_serializable = {
                    'task_id': int(task['task_id']),
                    'is_good_data': bool(task['is_good_data']),  # 确保是Python原生布尔类型
                    'weight': float(task['weight']),  # 确保是Python原生浮点数
                    'reputation_after_task': float(task['reputation_after_task'])
                }
                task_history_serializable.append(task_serializable)

            detailed_results['worker_detailed_records'][str(worker_id)] = {
                'final_reputation': float(worker_info['historical_reputation']),
                'non_updated_reputation': float(worker_info['non_updated_reputation']),
                'cheating_count': int(worker_info['cheating_count']),
                'consecutive_good_tasks': int(worker_info['consecutive_good_tasks']),
                'tasks_participated': int(tasks_participated),
                'good_tasks_count': int(good_tasks),
                'accuracy_percentage': float(accuracy),
                'task_history': task_history_serializable
            }

        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(detailed_results, f, indent=2, ensure_ascii=False)

        print(f"\n详细工人记录已保存到: {output_file}")


def main():
    """主函数"""
    # JSON文件路径
    default_workload = Path(__file__).resolve().parents[2] / "data" / "workloads" / "Scene_2_Number_of_Workers_27.json"
    json_file_path = Path(os.environ.get("IRPP_WORKLOAD", default_workload))

    # 检查文件是否存在
    if not os.path.exists(json_file_path):
        print(f"错误: 找不到文件 {json_file_path}")
        print("请确认文件路径是否正确")
        return

    try:
        # 创建系统实例
        system = WorkerReputationSystem(json_file_path)

        # 运行所有任务
        system.run_all_tasks()

        # 打印最终总结
        system.print_final_summary()

        # 打印每个工人的详细信誉记录
        system.print_worker_reputation_details()

        # 打印信誉最高和最低的工人详细信息
        system.print_top_bottom_workers(top_n=10)

        # 保存结果
        system.save_results("worker_reputation_system_results.json")

        # 保存详细的工人记录
        system.save_detailed_worker_results("detailed_worker_results.json")

    except Exception as e:
        print(f"系统运行出错: {str(e)}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
