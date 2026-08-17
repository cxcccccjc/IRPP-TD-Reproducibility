import pandas as pd
import numpy as np
import os
from pathlib import Path


def preprocess_climate_data(input_file_path, output_file_path):
    """
    预处理气候数据：
    1. 读取CSV文件（使用原有列名）
    2. 清理空数据和异常数据
    3. 提取指定列
    4. 保存预处理后的数据
    """

    try:
        # 读取CSV文件，使用第一行作为列名
        print("正在读取数据文件...")
        df = pd.read_csv(input_file_path)

        print(f"原始数据形状: {df.shape}")
        print(f"列名: {list(df.columns)}")
        print(f"原始数据前5行:\n{df.head()}")

        # 1. 检查和处理缺失值
        print("\n检查缺失值...")
        missing_counts = df.isnull().sum()
        print(f"各列缺失值数量:\n{missing_counts}")

        # 删除包含缺失值的行
        df_clean = df.dropna()
        print(f"删除缺失值后数据形状: {df_clean.shape}")

        # 2. 提取需要的列（使用原文件中的列名）
        target_columns = ['p (mbar)', 'Tpot (K)', 'rh (%)', 'rho (g/m**3)', 'wd (deg)']

        # 检查目标列是否存在
        missing_columns = [col for col in target_columns if col not in df_clean.columns]
        if missing_columns:
            print(f"警告: 以下列在数据文件中不存在: {missing_columns}")
            print(f"可用的列名: {list(df_clean.columns)}")
            return None

        df_selected = df_clean[target_columns].copy()
        print(f"提取目标列后数据形状: {df_selected.shape}")

        # 3. 处理异常数据
        print("\n处理异常数据...")

        # 转换为数值类型并处理非数值数据
        for col in target_columns:
            df_selected[col] = pd.to_numeric(df_selected[col], errors='coerce')

        # 再次删除转换后产生的NaN值
        df_selected = df_selected.dropna()
        print(f"数值转换后数据形状: {df_selected.shape}")

        # 定义合理的数据范围
        data_ranges = {
            'p (mbar)': (800, 1200),  # 气压范围
            'Tpot (K)': (200, 350),  # 位温范围
            'rh (%)': (0, 100),  # 相对湿度范围
            'rho (g/m**3)': (1000, 1500),  # 密度范围
            'wd (deg)': (0, 360)  # 风向范围
        }

        # 根据合理范围过滤异常数据
        initial_count = len(df_selected)
        for col, (min_val, max_val) in data_ranges.items():
            before_count = len(df_selected)
            condition = (df_selected[col] >= min_val) & (df_selected[col] <= max_val)
            df_selected = df_selected[condition]
            after_count = len(df_selected)
            print(f"过滤 {col} 异常值: 删除 {before_count - after_count} 行，剩余 {after_count} 行")

        print(f"总共过滤掉 {initial_count - len(df_selected)} 行异常数据")

        # 4. 统计检查
        print("\n预处理后数据统计:")
        print(df_selected.describe())

        # 5. 保存预处理后的数据
        print(f"\n保存预处理后的数据到: {output_file_path}")

        # 确保输出目录存在
        output_dir = os.path.dirname(output_file_path)
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
            print(f"创建目录: {output_dir}")

        # 保存数据
        df_selected.to_csv(output_file_path, index=False)
        print(f"预处理完成！最终数据形状: {df_selected.shape}")

        # 6. 显示预处理后的前几行数据
        print(f"\n预处理后数据前5行:\n{df_selected.head()}")

        return df_selected

    except FileNotFoundError:
        print(f"错误: 找不到文件 {input_file_path}")
        print("请检查文件路径是否正确")
        return None
    except Exception as e:
        print(f"处理过程中发生错误: {str(e)}")
        return None


def create_sample_data(file_path):
    """
    如果原文件不存在，创建示例数据文件（包含表头）
    """
    sample_data = """Date,Time,p (mbar),T (degC),Tpot (K),Tdew (degC),rh (%),VPmax (mbar),VPact (mbar),VPdef (mbar),sh (g/kg),H2OC (mmol/mol),rho (g/m**3),wv (m/s),max. wv (m/s),wd (deg)
01.01.2009,00:10:00,996.52,-8.02,265.4,-8.9,93.3,3.33,3.11,0.22,1.94,3.12,1307.75,1.03,1.75,152.3
01.01.2009,00:20:00,996.57,-8.41,265.01,-9.28,93.4,3.23,3.02,0.21,1.89,3.03,1309.8,0.72,1.5,136.1
01.01.2009,00:30:00,996.53,-8.51,264.91,-9.31,93.9,3.21,3.01,0.2,1.88,3.02,1310.24,0.19,0.63,171.6
01.01.2009,00:40:00,996.51,-8.31,265.12,-9.07,94.2,3.26,3.07,0.19,1.92,3.08,1309.19,0.34,0.5,198
01.01.2009,00:50:00,996.51,-8.27,265.15,-9.04,94.1,3.27,3.08,0.19,1.92,3.09,1309,0.32,0.63,214.3
01.01.2009,01:00:00,996.5,-8.05,265.38,-8.78,94.4,3.33,3.14,0.19,1.96,3.15,1307.86,0.21,0.63,192.7
03.01.2009,05:10:00,1001.52,-7.19,265.85,-8.2,92.4,3.56,3.29,0.27,2.04,3.28,1310.14,0.39,0.88,158.2
03.01.2009,05:20:00,1001.4,-7.35,265.7,-8.36,92.4,3.51,3.24,0.27,2.02,3.24,1310.79,0.55,1,65.2
03.01.2009,05:30:00,1001.29,-7.54,265.52,-8.5,92.8,3.46,3.21,0.25,2,3.21,1311.6,0.45,0.88,58.6"""

    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    with open(file_path, 'w') as f:
        f.write(sample_data)
    print(f"创建示例数据文件: {file_path}")


# 主程序
if __name__ == "__main__":
    # 文件路径
    repository_root = Path(__file__).resolve().parents[2]
    input_file_path = repository_root / "data" / "raw" / "Climate.csv"
    output_file_path = repository_root / "data" / "processed" / "Climate_processed.csv"
    output_file_path.parent.mkdir(parents=True, exist_ok=True)

    print("=== 气候数据预处理程序 ===\n")

    # 检查输入文件是否存在
    if not os.path.exists(input_file_path):
        print(f"输入文件不存在: {input_file_path}")
        user_input = input("是否创建示例数据文件进行测试? (y/n): ")
        if user_input.lower() == 'y':
            create_sample_data(input_file_path)
        else:
            print("程序结束")
            exit()

    # 执行数据预处理
    processed_data = preprocess_climate_data(input_file_path, output_file_path)

    if processed_data is not None:
        print("\n=== 预处理成功完成 ===")
        print(f"输入文件: {input_file_path}")
        print(f"输出文件: {output_file_path}")
        print(f"最终数据维度: {processed_data.shape}")
        print(f"包含列: {list(processed_data.columns)}")
    else:
        print("\n=== 预处理失败 ===")
        print("请检查数据文件格式或列名是否正确")
