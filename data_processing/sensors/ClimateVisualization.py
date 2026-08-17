import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from scipy import stats
import warnings
from pathlib import Path

warnings.filterwarnings('ignore')

# 设置中文字体显示
plt.rcParams['font.sans-serif'] = ['SimHei']  # 用于显示中文
plt.rcParams['axes.unicode_minus'] = False  # 用于显示负号


def analyze_climate_data(file_path):
    """
    对气候数据进行全面分析
    """
    try:
        # 读取预处理后的数据
        print("=== 读取预处理后的气候数据 ===")
        df = pd.read_csv(file_path)
        print(f"数据形状: {df.shape}")
        print(f"数据列: {list(df.columns)}")
        print(f"\n数据预览:\n{df.head()}")

        # 1. 基础统计分析
        print("\n" + "=" * 60)
        print("1. 基础统计分析")
        print("=" * 60)

        # 描述性统计
        stats_summary = df.describe()
        print("\n描述性统计:")
        print(stats_summary)

        # 数据类型和基本信息
        print(f"\n数据信息:")
        print(f"总行数: {len(df)}")
        print(f"总列数: {len(df.columns)}")
        print(f"缺失值: {df.isnull().sum().sum()}")

        # 2. 分布分析
        print("\n" + "=" * 60)
        print("2. 数据分布分析")
        print("=" * 60)

        # 创建分布图
        fig, axes = plt.subplots(2, 3, figsize=(18, 12))
        fig.suptitle('气候数据分布分析', fontsize=16, fontweight='bold')

        columns = df.columns
        for i, col in enumerate(columns):
            row = i // 3
            col_idx = i % 3
            if i < 5:  # 只画前5列
                # 直方图
                axes[row, col_idx].hist(df[col], bins=30, alpha=0.7, color='skyblue', edgecolor='black')
                axes[row, col_idx].set_title(f'{col}分布')
                axes[row, col_idx].set_xlabel(col)
                axes[row, col_idx].set_ylabel('频数')

                # 添加统计信息
                mean_val = df[col].mean()
                std_val = df[col].std()
                axes[row, col_idx].axvline(mean_val, color='red', linestyle='--', label=f'均值: {mean_val:.2f}')
                axes[row, col_idx].legend()

        # 删除空的子图
        if len(columns) == 5:
            fig.delaxes(axes[1, 2])

        plt.tight_layout()
        plt.savefig('climate_distributions.png', dpi=300, bbox_inches='tight')
        plt.show()

        # 正态性检验
        print("\n正态性检验 (Shapiro-Wilk Test):")
        for col in df.columns:
            if len(df) <= 5000:  # Shapiro-Wilk test限制
                stat, p_value = stats.shapiro(df[col].sample(min(1000, len(df))))
                is_normal = "是" if p_value > 0.05 else "否"
                print(f"{col}: p值 = {p_value:.6f}, 正态分布: {is_normal}")
            else:
                # 使用Kolmogorov-Smirnov test对大数据集
                stat, p_value = stats.kstest(df[col], 'norm')
                is_normal = "是" if p_value > 0.05 else "否"
                print(f"{col}: p值 = {p_value:.6f}, 正态分布: {is_normal}")

        # 3. 相关性分析
        print("\n" + "=" * 60)
        print("3. 相关性分析")
        print("=" * 60)

        # 计算相关系数矩阵
        correlation_matrix = df.corr()
        print("\n相关系数矩阵:")
        print(correlation_matrix.round(4))

        # 绘制相关性热力图
        plt.figure(figsize=(10, 8))
        mask = np.triu(np.ones_like(correlation_matrix, dtype=bool))
        sns.heatmap(correlation_matrix, mask=mask, annot=True, cmap='coolwarm', center=0,
                    square=True, fmt='.3f', cbar_kws={'label': '相关系数'})
        plt.title('气候变量相关性热力图', fontsize=14, fontweight='bold')
        plt.tight_layout()
        plt.savefig('correlation_heatmap.png', dpi=300, bbox_inches='tight')
        plt.show()

        # 强相关关系分析
        print("\n强相关关系 (|r| > 0.5):")
        for i in range(len(correlation_matrix.columns)):
            for j in range(i + 1, len(correlation_matrix.columns)):
                corr_val = correlation_matrix.iloc[i, j]
                if abs(corr_val) > 0.5:
                    col1 = correlation_matrix.columns[i]
                    col2 = correlation_matrix.columns[j]
                    relationship = "正相关" if corr_val > 0 else "负相关"
                    print(f"{col1} vs {col2}: {corr_val:.4f} ({relationship})")

        # 4. 箱线图分析（异常值检测）
        print("\n" + "=" * 60)
        print("4. 异常值分析")
        print("=" * 60)

        fig, axes = plt.subplots(1, 5, figsize=(20, 4))
        fig.suptitle('箱线图分析 - 异常值检测', fontsize=16, fontweight='bold')

        for i, col in enumerate(df.columns):
            box_plot = axes[i].boxplot(df[col], patch_artist=True)
            axes[i].set_title(col)
            axes[i].set_ylabel('数值')
            box_plot['boxes'][0].set_facecolor('lightblue')

            # 计算异常值
            Q1 = df[col].quantile(0.25)
            Q3 = df[col].quantile(0.75)
            IQR = Q3 - Q1
            lower_bound = Q1 - 1.5 * IQR
            upper_bound = Q3 + 1.5 * IQR
            outliers = df[(df[col] < lower_bound) | (df[col] > upper_bound)][col]

            print(f"{col}:")
            print(f"  异常值数量: {len(outliers)}")
            print(f"  异常值比例: {len(outliers) / len(df) * 100:.2f}%")
            if len(outliers) > 0:
                print(f"  异常值范围: [{outliers.min():.2f}, {outliers.max():.2f}]")

        plt.tight_layout()
        plt.savefig('boxplots_outliers.png', dpi=300, bbox_inches='tight')
        plt.show()

        # 5. 时间序列分析（如果有时间信息）
        print("\n" + "=" * 60)
        print("5. 变量关系散点图分析")
        print("=" * 60)

        # 创建散点图矩阵
        fig, axes = plt.subplots(5, 5, figsize=(20, 20))
        fig.suptitle('变量间关系散点图矩阵', fontsize=16, fontweight='bold')

        for i, col1 in enumerate(df.columns):
            for j, col2 in enumerate(df.columns):
                if i == j:
                    # 对角线显示直方图
                    axes[i, j].hist(df[col1], bins=20, alpha=0.7, color='lightblue')
                    axes[i, j].set_title(f'{col1}分布')
                else:
                    # 非对角线显示散点图
                    axes[i, j].scatter(df[col2], df[col1], alpha=0.5, s=1)
                    axes[i, j].set_xlabel(col2)
                    axes[i, j].set_ylabel(col1)

        plt.tight_layout()
        plt.savefig('scatter_matrix.png', dpi=300, bbox_inches='tight')
        plt.show()

        # 6. 统计推断分析
        print("\n" + "=" * 60)
        print("6. 变量间显著性检验")
        print("=" * 60)

        # 对高相关性的变量进行显著性检验
        print("\n显著性检验结果:")
        for i in range(len(correlation_matrix.columns)):
            for j in range(i + 1, len(correlation_matrix.columns)):
                col1 = correlation_matrix.columns[i]
                col2 = correlation_matrix.columns[j]
                corr_coef, p_value = stats.pearsonr(df[col1], df[col2])
                significance = "显著" if p_value < 0.05 else "不显著"
                print(f"{col1} vs {col2}: r={corr_coef:.4f}, p={p_value:.6f} ({significance})")

        # 7. 数据质量评估
        print("\n" + "=" * 60)
        print("7. 数据质量评估")
        print("=" * 60)

        quality_report = {}
        for col in df.columns:
            quality_report[col] = {
                '完整性': f"{(1 - df[col].isnull().sum() / len(df)) * 100:.2f}%",
                '唯一值数量': df[col].nunique(),
                '重复值数量': df[col].duplicated().sum(),
                '标准差': f"{df[col].std():.4f}",
                '变异系数': f"{df[col].std() / df[col].mean() * 100:.2f}%" if df[col].mean() != 0 else "N/A"
            }

        quality_df = pd.DataFrame(quality_report).T
        print("\n数据质量报告:")
        print(quality_df)

        # 8. 总结报告
        print("\n" + "=" * 60)
        print("8. 分析总结报告")
        print("=" * 60)

        print(f"""
数据概况:
- 总样本数: {len(df)}
- 变量数: {len(df.columns)}
        """)

        return df, correlation_matrix, quality_df

    except FileNotFoundError:
        print(f"错误: 找不到文件 {file_path}")
        return None, None, None
    except Exception as e:
        print(f"分析过程中发生错误: {str(e)}")
        return None, None, None


# 主程序
if __name__ == "__main__":
    # 文件路径
    repository_root = Path(__file__).resolve().parents[2]
    file_path = repository_root / "data" / "processed" / "Climate_processed.csv"

    print("=== 气候数据分析程序 ===\n")

    # 执行数据分析
    data, correlation_matrix, quality_report = analyze_climate_data(file_path)

    if data is not None:
        print("\n=== 分析完成 ===")
        print("生成的图表文件:")
        print("- climate_distributions.png (数据分布图)")
        print("- correlation_heatmap.png (相关性热力图)")
        print("- boxplots_outliers.png (箱线图异常值检测)")
        print("- scatter_matrix.png (散点图矩阵)")
    else:
        print("数据分析失败，请检查文件路径和数据格式")
