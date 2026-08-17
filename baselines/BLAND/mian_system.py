import json
import numpy as np
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler
import time
import warnings
import os
from pathlib import Path

warnings.filterwarnings('ignore')


def load_data(file_path):
    """加载数据文件"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return data
    except FileNotFoundError:
        print(f"文件 {file_path} 未找到")
        return None
    except json.JSONDecodeError:
        print("JSON文件格式错误")
        return None


def cluster_worker_data(worker_submissions, n_clusters=2, max_iter=300):
    """
    使用K-means聚类识别正常和异常数据
    返回正常数据的索引、聚类迭代次数
    """
    if len(worker_submissions) < n_clusters:
        # 如果工人数量少于聚类数量，全部视为正常数据
        return list(range(len(worker_submissions))), 1

    # 提取所有工人的提交数据
    data_matrix = np.array([worker['submitted_data'] for worker in worker_submissions])

    # 标准化数据
    scaler = StandardScaler()
    data_scaled = scaler.fit_transform(data_matrix)

    # K-means聚类
    kmeans = KMeans(n_clusters=n_clusters, random_state=42, max_iter=max_iter, n_init=10)
    cluster_labels = kmeans.fit_predict(data_scaled)

    # 计算每个聚类的大小
    unique_labels, counts = np.unique(cluster_labels, return_counts=True)

    # 假设正常数据聚类是数量较多的那个
    normal_cluster = unique_labels[np.argmax(counts)]
    normal_indices = np.where(cluster_labels == normal_cluster)[0].tolist()

    return normal_indices, kmeans.n_iter_


def calculate_aggregated_data(worker_submissions, normal_indices):
    """计算正常数据的平均值作为聚合数据"""
    normal_data = [worker_submissions[i]['submitted_data'] for i in normal_indices]
    if not normal_data:
        return None
    return np.mean(normal_data, axis=0)


def calculate_errors(true_data, aggregated_data):
    """计算MAE, MSE, RMSE误差"""
    true_data = np.array(true_data)
    aggregated_data = np.array(aggregated_data)

    # MAE (Mean Absolute Error)
    mae = np.mean(np.abs(true_data - aggregated_data))

    # MSE (Mean Squared Error)
    mse = np.mean((true_data - aggregated_data) ** 2)

    # RMSE (Root Mean Squared Error)
    rmse = np.sqrt(mse)

    return mae, mse, rmse


def main():
    # 数据文件路径
    default_workload = Path(__file__).resolve().parents[2] / "data" / "workloads" / "Scene_1_Number_of_Workers_27.json"
    file_path = Path(os.environ.get("IRPP_WORKLOAD", default_workload))

    # 加载数据
    data = load_data(file_path)
    if data is None:
        return

    task_data = data['task_worker_data']

    # 存储结果
    all_errors = []
    all_iterations = []
    clustering_times = []

    print("开始处理100个任务的数据...")
    print("=" * 60)

    # 处理每个任务
    for task_idx in range(1, 101):
        task_info = task_data[str(task_idx)]
        true_data = task_info['task_true_data']
        worker_submissions = task_info['worker_submissions']

        # 记录聚类开始时间
        start_time = time.time()

        # 聚类识别正常数据
        normal_indices, iterations = cluster_worker_data(worker_submissions)

        # 记录聚类结束时间
        end_time = time.time()
        clustering_time = end_time - start_time
        clustering_times.append(clustering_time)
        all_iterations.append(iterations)

        # 计算聚合数据
        aggregated_data = calculate_aggregated_data(worker_submissions, normal_indices)

        if aggregated_data is not None:
            # 计算误差
            mae, mse, rmse = calculate_errors(true_data, aggregated_data)
            all_errors.append((mae, mse, rmse))

            # 每10次输出累计聚类时间
            if task_idx % 10 == 0:
                cumulative_time = sum(clustering_times[:task_idx])
                print(f"前{task_idx}次任务累计聚类时间: {cumulative_time:.4f}秒")
        else:
            print(f"任务{task_idx}: 无正常数据")

    print("=" * 60)

    # 计算前50次和后50次的平均误差
    if len(all_errors) >= 100:
        first_50_errors = all_errors[:50]
        last_50_errors = all_errors[50:100]

        # 前50次平均误差
        first_50_mae = np.mean([error[0] for error in first_50_errors])
        first_50_mse = np.mean([error[1] for error in first_50_errors])
        first_50_rmse = np.mean([error[2] for error in first_50_errors])

        # 后50次平均误差
        last_50_mae = np.mean([error[0] for error in last_50_errors])
        last_50_mse = np.mean([error[1] for error in last_50_errors])
        last_50_rmse = np.mean([error[2] for error in last_50_errors])

        print("前50次任务平均误差:")
        print(f"  MAE: {first_50_mae:.4f}")
        print(f"  MSE: {first_50_mse:.4f}")
        print(f"  RMSE: {first_50_rmse:.4f}")
        print()
        print("后50次任务平均误差:")
        print(f"  MAE: {last_50_mae:.4f}")
        print(f"  MSE: {last_50_mse:.4f}")
        print(f"  RMSE: {last_50_rmse:.4f}")
        print()

    # 计算平均迭代次数
    if all_iterations:
        avg_iterations = np.mean(all_iterations)
        print(f"100次任务的平均聚类迭代次数: {avg_iterations:.2f}")
        print(f"聚类迭代次数统计:")
        print(f"  最小迭代次数: {min(all_iterations)}")
        print(f"  最大迭代次数: {max(all_iterations)}")
        print(f"  标准差: {np.std(all_iterations):.2f}")

    # 总体聚类时间统计
    total_clustering_time = sum(clustering_times)
    avg_clustering_time = np.mean(clustering_times)
    print(f"\n聚类时间统计:")
    print(f"  总聚类时间: {total_clustering_time:.4f}秒")
    print(f"  平均单次聚类时间: {avg_clustering_time:.4f}秒")

    # 输出部分详细信息（前5次任务）
    print("\n前5次任务详细信息:")
    print("-" * 60)
    for i in range(min(5, len(all_errors))):
        mae, mse, rmse = all_errors[i]
        iterations = all_iterations[i]
        clustering_time = clustering_times[i]
        print(f"任务{i + 1}: MAE={mae:.4f}, MSE={mse:.4f}, RMSE={rmse:.4f}, "
              f"迭代次数={iterations}, 聚类时间={clustering_time:.4f}s")


if __name__ == "__main__":
    main()
