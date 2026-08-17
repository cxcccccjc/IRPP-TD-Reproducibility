import pandas as pd
import numpy as np
import os
from pathlib import Path


def preprocess_traffic_data(input_file_path, output_file_path):
    """
    预处理交通流量数据：
    1. 读取CSV文件
    2. 清理缺失数据和异常数据（包括0值异常）
    3. 提取指定的6列车流量数据
    4. 保存预处理后的数据
    """

    try:
        # 读取CSV文件
        print("正在读取交通流量数据文件...")
        df = pd.read_csv(input_file_path, encoding='utf-8')

        print(f"原始数据形状: {df.shape}")
        print(f"列名: {list(df.columns)}")
        print(f"原始数据前5行:\n{df.head()}")

        # 1. 检查和处理缺失值
        print("\n检查缺失值...")
        missing_counts = df.isnull().sum()
        print(f"各列缺失值数量:\n{missing_counts}")

        # 2. 提取需要的车流量列
        target_columns = ['中型车流量', '大车流量', '微型车流量', '长车流量', '车流量', '轻型车流量']

        # 检查目标列是否存在
        missing_columns = [col for col in target_columns if col not in df.columns]
        if missing_columns:
            print(f"警告: 以下列在数据文件中不存在: {missing_columns}")
            print(f"可用的列名: {list(df.columns)}")
            return None

        df_selected = df[target_columns].copy()
        print(f"提取目标列后数据形状: {df_selected.shape}")

        # 3. 数据类型转换和清理
        print("\n数据类型转换和清理...")

        # 转换为数值类型，处理科学计数法和非数值数据
        for col in target_columns:
            # 先转换为字符串，去除可能的空格和制表符
            df_selected[col] = df_selected[col].astype(str).str.strip()

            # 转换为数值类型
            df_selected[col] = pd.to_numeric(df_selected[col], errors='coerce')

        print(f"数值转换后数据形状: {df_selected.shape}")
        print("转换后数据类型:")
        print(df_selected.dtypes)

        # 删除包含缺失值的行
        initial_count = len(df_selected)
        df_clean = df_selected.dropna()
        print(f"删除缺失值: 删除 {initial_count - len(df_clean)} 行，剩余 {len(df_clean)} 行")

        # 4. 车流量数据异常值清理
        print("\n车流量数据异常值清理...")

        # 规则1: 删除负数车流量
        before_count = len(df_clean)
        condition_positive = (df_clean >= 1).all(axis=1)
        df_clean = df_clean[condition_positive]
        print(f"删除负数车流量: 删除 {before_count - len(df_clean)} 行，剩余 {len(df_clean)} 行")

        # 规则2: 删除全零或接近全零的异常行
        # 对于交通监测点，如果所有车流量都为0或大部分为0，通常表示设备故障
        before_count = len(df_clean)

        # 2.1 删除所有车流量都为0的行
        all_zero_condition = (df_clean == 0).all(axis=1)
        df_clean = df_clean[~all_zero_condition]
        removed_all_zero = before_count - len(df_clean)
        print(f"删除全零流量行: 删除 {removed_all_zero} 行，剩余 {len(df_clean)} 行")

        # 2.2 删除大部分车流量为0的异常行（超过80%的列为0）
        before_count = len(df_clean)
        zero_ratio = (df_clean == 0).sum(axis=1) / len(target_columns)
        mostly_zero_condition = zero_ratio <= 0.8  # 保留零值比例不超过80%的行
        df_clean = df_clean[mostly_zero_condition]
        removed_mostly_zero = before_count - len(df_clean)
        print(f"删除大部分为零的异常行: 删除 {removed_mostly_zero} 行，剩余 {len(df_clean)} 行")

        # 2.3 删除总车流量为0但分类车流量不为0的逻辑错误行
        before_count = len(df_clean)
        vehicle_types = ['中型车流量', '大车流量', '微型车流量', '长车流量', '轻型车流量']

        # 总车流量为0但其他车流量不为0的情况
        total_zero = df_clean['车流量'] == 0
        others_nonzero = (df_clean[vehicle_types] > 0).any(axis=1)
        logical_error_condition = ~(total_zero & others_nonzero)

        df_clean = df_clean[logical_error_condition]
        removed_logical_error = before_count - len(df_clean)
        print(f"删除逻辑错误行（总流量为0但分类流量不为0）: 删除 {removed_logical_error} 行，剩余 {len(df_clean)} 行")

        # 规则3: 删除单个车流量类型异常为0的情况
        # 在正常交通中，如果总车流量较大，但某类车辆完全为0，可能是统计异常
        print("\n检查单类车流量异常为0的情况...")
        before_count = len(df_clean)

        # 当总车流量>1000时，各类车辆流量不应该都为0
        high_total_flow = df_clean['车流量'] > 100

        for vehicle_type in vehicle_types:
            # 如果总流量很高但某类车辆为0，且这种情况较少见，则可能是异常
            zero_single_type = df_clean[vehicle_type] == 0
            suspicious_condition = high_total_flow & zero_single_type

            # 计算这种情况的比例，如果比例很小（<5%），则认为是异常
            if suspicious_condition.sum() > 0:
                suspicious_ratio = suspicious_condition.sum() / len(df_clean)
                if suspicious_ratio < 0.05:  # 少于5%的情况认为异常
                    df_clean = df_clean[~suspicious_condition]
                    removed = before_count - len(df_clean)
                    if removed > 0:
                        print(f"删除{vehicle_type}异常为0的行: 删除 {removed} 行，剩余 {len(df_clean)} 行")
                        before_count = len(df_clean)

        # 规则4: 总车流量与分类车流量一致性检查
        print("\n总车流量一致性检查...")
        before_count = len(df_clean)

        # 计算各类型车流量之和
        df_clean['计算总流量'] = df_clean[vehicle_types].sum(axis=1)

        # 允许15%的误差范围（考虑到统计误差）
        tolerance = 0.15
        relative_error = np.abs(df_clean['车流量'] - df_clean['计算总流量']) / np.maximum(df_clean['车流量'], 1)
        consistency_condition = relative_error <= tolerance

        df_clean = df_clean[consistency_condition]
        removed_inconsistent = before_count - len(df_clean)
        print(f"删除总流量不一致的行: 删除 {removed_inconsistent} 行，剩余 {len(df_clean)} 行")

        # 删除临时计算列
        df_clean = df_clean.drop('计算总流量', axis=1)

        # 规则5: 删除极端异常值（使用IQR方法）
        print("\n删除极端异常值...")
        for col in target_columns:
            Q1 = df_clean[col].quantile(0.25)
            Q3 = df_clean[col].quantile(0.75)
            IQR = Q3 - Q1

            # 使用3倍IQR作为异常值界限
            lower_bound = Q1 - 3 * IQR
            upper_bound = Q3 + 3 * IQR

            # 但确保下界不小于0（车流量不能为负）
            lower_bound = max(0, lower_bound)

            before_count = len(df_clean)
            outlier_condition = (df_clean[col] >= lower_bound) & (df_clean[col] <= upper_bound)
            df_clean = df_clean[outlier_condition]
            removed = before_count - len(df_clean)
            if removed > 0:
                print(f"  {col}: 删除 {removed} 行极端异常值，剩余 {len(df_clean)} 行")

        # 6. 最终数据质量检查
        print("\n最终数据质量检查...")
        print("清理后数据统计:")
        print(df_clean.describe())

        # 检查零值分布情况
        print("\n零值分布检查:")
        for col in target_columns:
            zero_count = (df_clean[col] == 0).sum()
            zero_ratio = zero_count / len(df_clean) * 100
            print(f"{col}: {zero_count} 个零值 ({zero_ratio:.2f}%)")

        # 检查数据合理性
        print("\n数据合理性检查:")
        for col in target_columns:
            min_val = df_clean[col].min()
            max_val = df_clean[col].max()
            mean_val = df_clean[col].mean()
            median_val = df_clean[col].median()
            print(f"{col}: 最小值={min_val:.0f}, 最大值={max_val:.0f}, 平均值={mean_val:.0f}, 中位数={median_val:.0f}")

        # 7. 保存预处理后的数据
        print(f"\n保存预处理后的数据到: {output_file_path}")

        # 确保输出目录存在
        output_dir = os.path.dirname(output_file_path)
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
            print(f"创建目录: {output_dir}")

        # 保存数据
        df_clean.to_csv(output_file_path, index=False, encoding='utf-8')
        print(f"预处理完成！最终数据形状: {df_clean.shape}")

        # 8. 数据清理总结
        print(f"\n数据清理总结:")
        print(f"原始数据行数: {initial_count}")
        print(f"最终数据行数: {len(df_clean)}")
        print(f"删除行数: {initial_count - len(df_clean)}")
        print(f"保留比例: {len(df_clean) / initial_count * 100:.2f}%")

        print(f"\n异常数据清理类型统计:")
        print(f"- 全零流量行: {removed_all_zero} 行")
        print(f"- 大部分为零的异常行: {removed_mostly_zero} 行")
        print(f"- 逻辑错误行: {removed_logical_error} 行")
        print(f"- 总流量不一致行: {removed_inconsistent} 行")

        # 显示清理后的前几行数据
        print(f"\n预处理后数据前5行:\n{df_clean.head()}")

        return df_clean

    except FileNotFoundError:
        print(f"错误: 找不到文件 {input_file_path}")
        print("请检查文件路径是否正确")
        return None
    except Exception as e:
        print(f"处理过程中发生错误: {str(e)}")
        return None


# 示例
def create_sample_traffic_data(file_path):
    """
    如果原文件不存在，创建示例交通流量数据文件
    """
    sample_data = """中型车流量,数据时间,大车流量,平均车速,监测点id,微型车流量,长车流量,车头距,id,车流量,平均占道率,轻型车流量
5047,2024-01-22 00:00:00,10965,67.7,1001,31830,7959,0,24025,52033,22.7,36021
4656,2024-01-23 00:00:00,9605,65.0,1001,29633,6974,0,24026,47914,24.6,33653
0,2024-01-24 00:00:00,0,0,1001,0,0,0,24027,0,0,0
4200,2024-01-25 00:00:00,8053,78.9,1001,26233,5685,0,24028,42047,17.4,29794
3205,2024-01-26 00:00:00,6600,75.6,1001,0,4803,0,24029,33809,15.9,0
2682,2024-01-27 00:00:00,5321,74.2,1001,17192,3825,0,24030,27534,14.6,19531"""

    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(sample_data)
    print(f"创建示例交通流量数据文件: {file_path}")


# 主程序
if __name__ == "__main__":
    # 文件路径
    repository_root = Path(__file__).resolve().parents[2]
    input_file_path = repository_root / "data" / "raw" / "TrafficVolume.csv"
    output_file_path = repository_root / "data" / "processed" / "Traffic_processed.csv"
    output_file_path.parent.mkdir(parents=True, exist_ok=True)

    print("=== 交通流量数据预处理程序 ===\n")

    # 检查输入文件是否存在
    if not os.path.exists(input_file_path):
        print(f"输入文件不存在: {input_file_path}")
        user_input = input("是否创建示例数据文件进行测试? (y/n): ")
        if user_input.lower() == 'y':
            create_sample_traffic_data(input_file_path)
        else:
            print("程序结束")
            exit()

    # 执行数据预处理
    processed_data = preprocess_traffic_data(input_file_path, output_file_path)

    if processed_data is not None:
        print("\n=== 预处理成功完成 ===")
        print(f"输入文件: {input_file_path}")
        print(f"输出文件: {output_file_path}")
        print(f"最终数据维度: {processed_data.shape}")
        print(f"包含列: {list(processed_data.columns)}")
    else:
        print("\n=== 预处理失败 ===")
        print("请检查数据文件格式或列名是否正确")

