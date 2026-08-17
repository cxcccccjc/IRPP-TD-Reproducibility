import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from scipy import stats
import warnings
from pathlib import Path

warnings.filterwarnings('ignore')

# 设置中文字体支持
plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei']
plt.rcParams['axes.unicode_minus'] = False


class WaterQualityPreprocessor:
    def __init__(self, input_file_path, output_file_path):
        """初始化水质数据预处理器"""
        self.input_file_path = input_file_path
        self.output_file_path = output_file_path
        self.df_original = None
        self.df_processed = None
        self.removed_rows = []

    def load_data(self):
        """加载原始数据"""
        try:
            # 尝试不同编码方式加载数据
            encodings = ['utf-8', 'gbk', 'latin-1', 'cp1252']
            for encoding in encodings:
                try:
                    self.df_original = pd.read_csv(self.input_file_path, encoding=encoding)
                    print(f"数据加载成功！编码: {encoding}")
                    print(f"原始数据形状: {self.df_original.shape}")
                    break
                except UnicodeDecodeError:
                    continue

            if self.df_original is None:
                raise Exception("无法用常见编码加载数据")

            # 显示列名和前几行数据
            print(f"列名: {list(self.df_original.columns)}")
            print("\n前5行数据:")
            print(self.df_original.head())

            return True

        except Exception as e:
            print(f"数据加载失败: {e}")
            return False

    def data_overview(self):
        """数据概览"""
        print("\n" + "=" * 60)
        print("原始数据概览")
        print("=" * 60)

        print(f"数据集大小: {self.df_original.shape[0]} 行, {self.df_original.shape[1]} 列")
        print(f"数据类型:")
        for col, dtype in self.df_original.dtypes.items():
            print(f"  {col}: {dtype}")

        print(f"\n缺失值统计:")
        missing_count = self.df_original.isnull().sum()
        total_rows = len(self.df_original)
        for col in missing_count.index:
            missing = missing_count[col]
            percentage = (missing / total_rows) * 100
            print(f"  {col}: {missing} ({percentage:.2f}%)")

        # 基础统计信息
        print(f"\n数值列基础统计:")
        numeric_cols = self.df_original.select_dtypes(include=[np.number]).columns
        if len(numeric_cols) > 0:
            print(self.df_original[numeric_cols].describe())

    def remove_potability_column(self):
        """移除Potability列"""
        if 'Potability' in self.df_original.columns:
            self.df_processed = self.df_original.drop('Potability', axis=1).copy()
            print(f"\n 已移除 'Potability' 列")
        else:
            self.df_processed = self.df_original.copy()
            print(f"\n 未找到 'Potability' 列")

        print(f"处理后数据形状: {self.df_processed.shape}")
        print(f"剩余列: {list(self.df_processed.columns)}")

    def detect_anomalies(self, method='iqr', z_threshold=3):
        """检测异常值"""
        print(f"\n" + "=" * 60)
        print(f"异常值检测 (方法: {method.upper()})")
        print("=" * 60)

        numeric_cols = self.df_processed.select_dtypes(include=[np.number]).columns
        anomaly_indices = set()
        anomaly_details = {}

        for col in numeric_cols:
            col_anomalies = set()

            if method == 'iqr':
                # IQR方法检测异常值
                Q1 = self.df_processed[col].quantile(0.25)
                Q3 = self.df_processed[col].quantile(0.75)
                IQR = Q3 - Q1
                lower_bound = Q1 - 1.5 * IQR
                upper_bound = Q3 + 1.5 * IQR

                col_anomalies = set(self.df_processed[
                                        (self.df_processed[col] < lower_bound) |
                                        (self.df_processed[col] > upper_bound)
                                        ].index)

                print(f"\n{col}:")
                print(f"  正常范围: [{lower_bound:.3f}, {upper_bound:.3f}]")
                print(f"  异常值数量: {len(col_anomalies)}")

            elif method == 'zscore':
                # Z-score方法检测异常值
                z_scores = np.abs(stats.zscore(self.df_processed[col].dropna()))
                col_anomalies = set(self.df_processed[col].dropna().index[z_scores > z_threshold])

                print(f"\n{col}:")
                print(f"  Z-score阈值: {z_threshold}")
                print(f"  异常值数量: {len(col_anomalies)}")

            anomaly_details[col] = col_anomalies
            anomaly_indices.update(col_anomalies)

        return anomaly_indices, anomaly_details

    def water_quality_specific_checks(self):
        """水质特定的异常值检查"""
        print(f"\n" + "=" * 60)
        print("水质特定异常值检查")
        print("=" * 60)

        water_quality_anomalies = set()

        # 定义水质参数的合理范围
        water_quality_ranges = {
            'ph': (0, 14),  # pH值范围
            'Hardness': (0, 500),  # 硬度 mg/L
            'Solids': (0, 50000),  # 固体溶解物 ppm
            'Chloramines': (0, 15),  # 氯胺 ppm
            'Sulfate': (0, 1000),  # 硫酸盐 mg/L
            'Conductivity': (0, 2000),  # 电导率 μS/cm
            'Organic_carbon': (0, 50),  # 有机碳 ppm
            'Trihalomethanes': (0, 200),  # 三卤甲烷 μg/L
            'Turbidity': (0, 10)  # 浊度 NTU
        }

        for col, (min_val, max_val) in water_quality_ranges.items():
            if col in self.df_processed.columns:
                # 检查超出合理范围的值
                out_of_range = self.df_processed[
                    (self.df_processed[col] < min_val) |
                    (self.df_processed[col] > max_val)
                    ].index

                water_quality_anomalies.update(out_of_range)

                if len(out_of_range) > 0:
                    print(f"\n{col}:")
                    print(f"  合理范围: [{min_val}, {max_val}]")
                    print(f"  超出范围的数量: {len(out_of_range)}")
                    print(f"  超出范围的值: {self.df_processed.loc[out_of_range, col].tolist()}")

        # 检查逻辑异常
        print(f"\n逻辑一致性检查:")

        # pH值与其他参数的逻辑关系检查
        if 'ph' in self.df_processed.columns:
            # 极端pH值应该对应其他参数的异常
            extreme_ph = self.df_processed[
                (self.df_processed['ph'] < 4) | (self.df_processed['ph'] > 10)
                ].index
            print(f"  极端pH值 (<4 或 >10): {len(extreme_ph)} 个")

        return water_quality_anomalies

    def handle_missing_values(self):
        """处理缺失值"""
        print(f"\n" + "=" * 60)
        print("缺失值处理")
        print("=" * 60)

        missing_before = self.df_processed.isnull().sum().sum()
        print(f"处理前缺失值总数: {missing_before}")

        # 记录有缺失值的行
        rows_with_missing = self.df_processed[self.df_processed.isnull().any(axis=1)].index
        print(f"有缺失值的行数: {len(rows_with_missing)}")

        # 选择处理策略
        numeric_cols = self.df_processed.select_dtypes(include=[np.number]).columns

        for col in numeric_cols:
            missing_count = self.df_processed[col].isnull().sum()
            missing_pct = (missing_count / len(self.df_processed)) * 100

            if missing_count > 0:
                print(f"\n{col}: {missing_count} 个缺失值 ({missing_pct:.2f}%)")

                if missing_pct > 50:
                    # 如果缺失值超过50%，考虑删除该列
                    print(f"  建议: 缺失值过多，建议删除该列")
                elif missing_pct > 10:
                    # 缺失值在10%-50%之间，删除对应行
                    print(f"  策略: 删除含缺失值的行")
                else:
                    # 缺失值小于10%，可以用中位数填充
                    median_val = self.df_processed[col].median()
                    self.df_processed[col].fillna(median_val, inplace=True)
                    print(f"  策略: 用中位数填充 ({median_val:.3f})")

        # 删除仍有缺失值的行
        self.df_processed.dropna(inplace=True)

        missing_after = self.df_processed.isnull().sum().sum()
        print(f"\n处理后缺失值总数: {missing_after}")
        print(f"剩余数据行数: {len(self.df_processed)}")

    def remove_anomalies(self, use_water_quality_checks=True):
        """移除异常值"""
        print(f"\n" + "=" * 60)
        print("异常值移除")
        print("=" * 60)

        initial_count = len(self.df_processed)
        all_anomalies = set()

        # 1. 统计学异常值检测
        iqr_anomalies, iqr_details = self.detect_anomalies(method='iqr')
        zscore_anomalies, zscore_details = self.detect_anomalies(method='zscore', z_threshold=3.5)

        # 2. 水质特定异常值检测
        water_anomalies = set()
        if use_water_quality_checks:
            water_anomalies = self.water_quality_specific_checks()

        # 合并所有异常值（取交集以避免过度删除）
        # 只有在多种方法都认为是异常值时才删除
        conservative_anomalies = iqr_anomalies.intersection(zscore_anomalies)
        all_anomalies = conservative_anomalies.union(water_anomalies)

        print(f"\n异常值汇总:")
        print(f"  IQR方法检测: {len(iqr_anomalies)} 个")
        print(f"  Z-score方法检测: {len(zscore_anomalies)} 个")
        print(f"  水质特定检测: {len(water_anomalies)} 个")
        print(f"  保守策略(IQR∩Z-score): {len(conservative_anomalies)} 个")
        print(f"  最终删除: {len(all_anomalies)} 个")

        # 保存被删除的行信息
        if len(all_anomalies) > 0:
            self.removed_rows = self.df_processed.loc[list(all_anomalies)].copy()
            self.df_processed = self.df_processed.drop(index=all_anomalies)

        final_count = len(self.df_processed)
        removed_count = initial_count - final_count
        removal_rate = (removed_count / initial_count) * 100

        print(f"\n处理结果:")
        print(f"  原始行数: {initial_count}")
        print(f"  删除行数: {removed_count}")
        print(f"  剩余行数: {final_count}")
        print(f"  删除比例: {removal_rate:.2f}%")

    def quality_assessment(self):
        """数据质量评估"""
        print(f"\n" + "=" * 60)
        print("数据质量评估")
        print("=" * 60)

        numeric_cols = self.df_processed.select_dtypes(include=[np.number]).columns

        print("处理后数据统计:")
        print(self.df_processed[numeric_cols].describe())

        print(f"\n数据分布检查:")
        for col in numeric_cols:
            skewness = stats.skew(self.df_processed[col])
            kurtosis = stats.kurtosis(self.df_processed[col])
            print(f"  {col}:")
            print(f"    偏度: {skewness:.3f} ({'正偏' if skewness > 0 else '负偏' if skewness < 0 else '对称'})")
            print(f"    峰度: {kurtosis:.3f} ({'尖峰' if kurtosis > 0 else '平峰' if kurtosis < 0 else '正态'})")

    def create_visualizations(self):
        """创建数据处理前后对比图"""
        print(f"\n生成数据处理对比图...")

        numeric_cols = self.df_processed.select_dtypes(include=[np.number]).columns
        n_cols = len(numeric_cols)

        if n_cols == 0:
            print("没有数值列可以绘图")
            return

        # 计算子图布局
        n_rows = (n_cols + 2) // 3
        fig, axes = plt.subplots(n_rows, 3, figsize=(18, 6 * n_rows))
        axes = axes.flatten() if n_rows > 1 else [axes] if n_rows == 1 else axes

        for i, col in enumerate(numeric_cols):
            if col in self.df_original.columns:
                # 绘制处理前后的箱线图对比
                ax = axes[i]

                # 原始数据（移除Potability列后）
                if 'Potability' in self.df_original.columns:
                    original_data = self.df_original.drop('Potability', axis=1)
                else:
                    original_data = self.df_original

                data_to_plot = [original_data[col].dropna(), self.df_processed[col].dropna()]
                labels = ['处理前', '处理后']

                box_plot = ax.boxplot(data_to_plot, labels=labels, patch_artist=True)
                box_plot['boxes'][0].set_facecolor('lightcoral')
                box_plot['boxes'][1].set_facecolor('lightblue')

                ax.set_title(f'{col} - 异常值处理对比', fontsize=12, fontweight='bold')
                ax.set_ylabel('数值')
                ax.grid(True, alpha=0.3)

        # 隐藏多余的子图
        for i in range(n_cols, len(axes)):
            axes[i].set_visible(False)

        plt.tight_layout()
        plt.show()

    def save_processed_data(self):
        """保存处理后的数据"""
        try:
            self.df_processed.to_csv(self.output_file_path, index=False, encoding='utf-8')
            print(f"\n 处理后的数据已保存到: {self.output_file_path}")
            print(f"处理后数据形状: {self.df_processed.shape}")

            # 保存异常值报告
            if len(self.removed_rows) > 0:
                report_path = self.output_file_path.replace('.csv', '_removed_rows.csv')
                self.removed_rows.to_csv(report_path, index=True, encoding='utf-8')
                print(f" 被删除的异常行已保存到: {report_path}")

            return True
        except Exception as e:
            print(f" 保存失败: {e}")
            return False

    def generate_summary_report(self):
        """生成处理摘要报告"""
        print(f"\n" + "=" * 70)
        print("水质数据预处理摘要报告")
        print("=" * 70)

        original_rows = len(self.df_original) if self.df_original is not None else 0
        processed_rows = len(self.df_processed) if self.df_processed is not None else 0
        removed_rows = original_rows - processed_rows

        print(f"\n 数据处理统计:")
        print(f"  原始数据行数: {original_rows:,}")
        print(f"  处理后行数: {processed_rows:,}")
        print(f"  删除行数: {removed_rows:,}")
        print(f"  数据保留率: {(processed_rows / original_rows * 100):.2f}%" if original_rows > 0 else "N/A")

        print(f"\n 处理步骤:")
        print(f"  ✓ 移除 Potability 列")
        print(f"  ✓ 缺失值处理")
        print(f"  ✓ 异常值检测与移除")
        print(f"  ✓ 数据质量验证")

        if self.df_processed is not None:
            numeric_cols = self.df_processed.select_dtypes(include=[np.number]).columns
            print(f"\n 最终数据概况:")
            print(f"  特征数量: {len(numeric_cols)}")
            print(f"  数据完整性: 100% (无缺失值)")

            for col in numeric_cols:
                col_min = self.df_processed[col].min()
                col_max = self.df_processed[col].max()
                col_mean = self.df_processed[col].mean()
                print(f"  {col}: [{col_min:.3f}, {col_max:.3f}], 均值: {col_mean:.3f}")

        print(f"\n 输出文件:")
        print(f"  清洁数据: {self.output_file_path}")
        if len(self.removed_rows) > 0:
            report_path = self.output_file_path.replace('.csv', '_removed_rows.csv')
            print(f"  异常数据: {report_path}")

        print(f"\n 预处理完成！数据已准备就绪，可用于后续分析。")

    def run_preprocessing(self):
        """运行完整的预处理流程"""
        print(" 开始水质数据预处理...")

        # 1. 加载数据
        if not self.load_data():
            return False

        # 2. 数据概览
        self.data_overview()

        # 3. 移除Potability列
        self.remove_potability_column()

        # 4. 处理缺失值
        self.handle_missing_values()

        # 5. 移除异常值
        self.remove_anomalies(use_water_quality_checks=True)

        # 6. 数据质量评估
        self.quality_assessment()

        # 7. 创建可视化对比图
        self.create_visualizations()

        # 8. 保存处理后的数据
        if self.save_processed_data():
            # 9. 生成摘要报告
            self.generate_summary_report()
            return True

        return False


# 使用示例
if __name__ == "__main__":
    # 文件路径设置
    repository_root = Path(__file__).resolve().parents[2]
    input_file = repository_root / "data" / "raw" / "WaterPotability.csv"
    output_file = repository_root / "data" / "processed" / "Water_processed.csv"
    output_file.parent.mkdir(parents=True, exist_ok=True)

    # 创建预处理器实例
    preprocessor = WaterQualityPreprocessor(input_file, output_file)

    # 运行预处理
    success = preprocessor.run_preprocessing()

    if success:
        print("\n 水质数据预处理成功完成！")
    else:
        print("\n 预处理过程中出现错误，请检查!")


# 验证处理后的数据
def quick_validation(file_path):
    """快速验证处理后的数据质量"""
    try:
        df = pd.read_csv(file_path)
        print(f"\n 处理后数据验证:")
        print(f"  数据形状: {df.shape}")
        print(f"  缺失值: {df.isnull().sum().sum()}")
        print(f"  数据类型: 全部为数值型" if all(df.dtypes == 'float64') else "包含非数值列")
        print(f"  列名: {list(df.columns)}")
        return True
    except Exception as e:
        print(f"验证失败: {e}")
        return False


# quick_validation(Path(__file__).resolve().parents[2] / "data" / "processed" / "Water_processed.csv")
