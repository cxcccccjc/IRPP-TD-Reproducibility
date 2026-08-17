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


class TrafficAnalyzer:
    def __init__(self, file_path):
        """初始化交通流量分析器"""
        self.file_path = file_path
        self.df = None
        self.load_data()

    def load_data(self):
        """加载数据"""
        try:
            self.df = pd.read_csv(self.file_path, encoding='utf-8')
            print(f"数据加载成功！数据形状: {self.df.shape}")
            print(f"列名: {list(self.df.columns)}")
        except UnicodeDecodeError:
            # 尝试其他编码
            try:
                self.df = pd.read_csv(self.file_path, encoding='gbk')
                print(f"数据加载成功（GBK编码）！数据形状: {self.df.shape}")
            except:
                print("数据加载失败，请检查文件路径和编码")
                return None
        except Exception as e:
            print(f"数据加载失败: {e}")
            return None

    def basic_info(self):
        """基础数据信息"""
        print("\n" + "=" * 50)
        print("基础数据信息")
        print("=" * 50)

        print(f"数据集大小: {self.df.shape[0]} 行, {self.df.shape[1]} 列")
        print(f"数据类型:")
        print(self.df.dtypes)

        print(f"\n缺失值统计:")
        missing_data = self.df.isnull().sum()
        print(missing_data[missing_data > 0] if missing_data.sum() > 0 else "无缺失值")

        print(f"\n前5行数据:")
        print(self.df.head())

        print(f"\n后5行数据:")
        print(self.df.tail())

    def descriptive_statistics(self):
        """描述性统计分析"""
        print("\n" + "=" * 50)
        print("描述性统计分析")
        print("=" * 50)

        # 基础统计信息
        print("基础统计信息:")
        print(self.df.describe())

        # 各车型流量统计
        print(f"\n各车型总流量排名:")
        total_traffic = self.df.sum().sort_values(ascending=False)
        for i, (vehicle_type, total) in enumerate(total_traffic.items(), 1):
            percentage = (total / total_traffic.sum()) * 100
            print(f"{i}. {vehicle_type}: {total:,} 辆 ({percentage:.2f}%)")

        # 平均流量统计
        print(f"\n各车型平均流量:")
        avg_traffic = self.df.mean().sort_values(ascending=False)
        for vehicle_type, avg in avg_traffic.items():
            print(f"{vehicle_type}: {avg:.0f} 辆")

    def time_series_analysis(self):
        """时间序列分析"""
        print("\n" + "=" * 50)
        print("时间序列分析")
        print("=" * 50)

        # 添加时间索引（假设数据按时间顺序排列）
        self.df['时间点'] = range(1, len(self.df) + 1)

        # 总流量变化
        if '车流量' in self.df.columns:
            total_col = '车流量'
        else:
            # 如果没有总流量列，计算总和
            numeric_cols = self.df.select_dtypes(include=[np.number]).columns
            if '时间点' in numeric_cols:
                numeric_cols = numeric_cols.drop('时间点')
            self.df['总流量'] = self.df[numeric_cols].sum(axis=1)
            total_col = '总流量'

        print(f"总流量统计:")
        print(f"最高流量: {self.df[total_col].max():,} 辆 (第{self.df[total_col].idxmax() + 1}个时间点)")
        print(f"最低流量: {self.df[total_col].min():,} 辆 (第{self.df[total_col].idxmin() + 1}个时间点)")
        print(f"流量变化幅度: {self.df[total_col].max() - self.df[total_col].min():,} 辆")

        # 计算变化率
        self.df['流量变化率'] = self.df[total_col].pct_change() * 100
        print(f"\n最大增长率: {self.df['流量变化率'].max():.2f}%")
        print(f"最大下降率: {self.df['流量变化率'].min():.2f}%")

    def correlation_analysis(self):
        """相关性分析"""
        print("\n" + "=" * 50)
        print("车型间相关性分析")
        print("=" * 50)

        # 选择数值列进行相关性分析
        numeric_cols = self.df.select_dtypes(include=[np.number]).columns
        if '时间点' in numeric_cols:
            numeric_cols = numeric_cols.drop('时间点')
        if '流量变化率' in numeric_cols:
            numeric_cols = numeric_cols.drop('流量变化率')

        correlation_matrix = self.df[numeric_cols].corr()
        print("相关系数矩阵:")
        print(correlation_matrix.round(3))

        # 找出高相关性的车型对
        print(f"\n高相关性车型对 (|r| > 0.8):")
        for i in range(len(correlation_matrix.columns)):
            for j in range(i + 1, len(correlation_matrix.columns)):
                corr_val = correlation_matrix.iloc[i, j]
                if abs(corr_val) > 0.8:
                    print(f"{correlation_matrix.columns[i]} - {correlation_matrix.columns[j]}: {corr_val:.3f}")

    def anomaly_detection(self):
        """异常值检测"""
        print("\n" + "=" * 50)
        print("异常值检测")
        print("=" * 50)

        numeric_cols = self.df.select_dtypes(include=[np.number]).columns
        if '时间点' in numeric_cols:
            numeric_cols = numeric_cols.drop('时间点')
        if '流量变化率' in numeric_cols:
            numeric_cols = numeric_cols.drop('流量变化率')

        for col in numeric_cols:
            Q1 = self.df[col].quantile(0.25)
            Q3 = self.df[col].quantile(0.75)
            IQR = Q3 - Q1
            lower_bound = Q1 - 1.5 * IQR
            upper_bound = Q3 + 1.5 * IQR

            outliers = self.df[(self.df[col] < lower_bound) | (self.df[col] > upper_bound)]
            if not outliers.empty:
                print(f"\n{col} 异常值:")
                for idx, row in outliers.iterrows():
                    print(f"  时间点 {idx + 1}: {row[col]:,} 辆")
            else:
                print(f"\n{col}: 无异常值")

    def create_visualizations(self):
        """创建可视化图表"""
        print("\n" + "=" * 50)
        print("生成可视化图表...")
        print("=" * 50)

        # 设置图表样式
        plt.style.use('seaborn-v0_8')
        fig = plt.figure(figsize=(20, 15))

        # 获取数值列
        numeric_cols = self.df.select_dtypes(include=[np.number]).columns
        if '时间点' in numeric_cols:
            numeric_cols = numeric_cols.drop('时间点')
        if '流量变化率' in numeric_cols:
            plot_cols = numeric_cols.drop('流量变化率')
        else:
            plot_cols = numeric_cols

        # 1. 时间序列图
        plt.subplot(3, 3, 1)
        for col in plot_cols:
            plt.plot(self.df['时间点'], self.df[col], marker='o', label=col, linewidth=2)
        plt.title('各车型流量时间序列', fontsize=14, fontweight='bold')
        plt.xlabel('时间点')
        plt.ylabel('流量 (辆)')
        plt.legend(bbox_to_anchor=(1.05, 1), loc='upper left')
        plt.grid(True, alpha=0.3)

        # 2. 总流量饼图
        plt.subplot(3, 3, 2)
        total_by_type = self.df[plot_cols].sum()
        colors = plt.cm.Set3(np.linspace(0, 1, len(total_by_type)))
        wedges, texts, autotexts = plt.pie(total_by_type.values, labels=total_by_type.index,
                                           autopct='%1.1f%%', colors=colors, startangle=90)
        plt.title('各车型总流量分布', fontsize=14, fontweight='bold')

        # 3. 箱线图
        plt.subplot(3, 3, 3)
        self.df[plot_cols].boxplot(ax=plt.gca())
        plt.title('各车型流量分布箱线图', fontsize=14, fontweight='bold')
        plt.xticks(rotation=45)
        plt.ylabel('流量 (辆)')

        # 4. 相关性热力图
        plt.subplot(3, 3, 4)
        correlation_matrix = self.df[plot_cols].corr()
        sns.heatmap(correlation_matrix, annot=True, cmap='coolwarm', center=0,
                    square=True, cbar_kws={'shrink': 0.8})
        plt.title('车型间相关性热力图', fontsize=14, fontweight='bold')

        # 5. 柱状图 - 平均流量
        plt.subplot(3, 3, 5)
        avg_traffic = self.df[plot_cols].mean().sort_values(ascending=False)
        bars = plt.bar(range(len(avg_traffic)), avg_traffic.values,
                       color=plt.cm.viridis(np.linspace(0, 1, len(avg_traffic))))
        plt.title('各车型平均流量', fontsize=14, fontweight='bold')
        plt.xticks(range(len(avg_traffic)), avg_traffic.index, rotation=45)
        plt.ylabel('平均流量 (辆)')

        # 在柱状图上添加数值标签
        for bar in bars:
            height = bar.get_height()
            plt.text(bar.get_x() + bar.get_width() / 2., height,
                     f'{int(height)}', ha='center', va='bottom')

        # 6. 流量变化趋势
        if '流量变化率' in self.df.columns:
            plt.subplot(3, 3, 6)
            plt.plot(self.df['时间点'][1:], self.df['流量变化率'][1:],
                     marker='o', color='red', linewidth=2)
            plt.title('总流量变化率趋势', fontsize=14, fontweight='bold')
            plt.xlabel('时间点')
            plt.ylabel('变化率 (%)')
            plt.axhline(y=0, color='black', linestyle='--', alpha=0.5)
            plt.grid(True, alpha=0.3)

        # 7. 累积流量图
        plt.subplot(3, 3, 7)
        cumulative = self.df[plot_cols].cumsum()
        for col in plot_cols:
            plt.plot(self.df['时间点'], cumulative[col], marker='o', label=col, linewidth=2)
        plt.title('各车型累积流量', fontsize=14, fontweight='bold')
        plt.xlabel('时间点')
        plt.ylabel('累积流量 (辆)')
        plt.legend(bbox_to_anchor=(1.05, 1), loc='upper left')
        plt.grid(True, alpha=0.3)

        # 8. 流量分布直方图（选择流量最大的车型）
        plt.subplot(3, 3, 8)
        max_traffic_col = self.df[plot_cols].sum().idxmax()
        plt.hist(self.df[max_traffic_col], bins=min(10, len(self.df)),
                 alpha=0.7, color='skyblue', edgecolor='black')
        plt.title(f'{max_traffic_col}流量分布', fontsize=14, fontweight='bold')
        plt.xlabel('流量 (辆)')
        plt.ylabel('频次')
        plt.grid(True, alpha=0.3)

        # 9. 流量占比堆积图
        plt.subplot(3, 3, 9)
        percentages = self.df[plot_cols].div(self.df[plot_cols].sum(axis=1), axis=0) * 100
        bottom = np.zeros(len(self.df))
        colors = plt.cm.Set3(np.linspace(0, 1, len(plot_cols)))

        for i, col in enumerate(plot_cols):
            plt.bar(self.df['时间点'], percentages[col], bottom=bottom,
                    label=col, color=colors[i])
            bottom += percentages[col]

        plt.title('各时间点车型流量占比', fontsize=14, fontweight='bold')
        plt.xlabel('时间点')
        plt.ylabel('占比 (%)')
        plt.legend(bbox_to_anchor=(1.05, 1), loc='upper left')

        plt.tight_layout()
        plt.show()

    def generate_report(self):
        """生成分析报告"""
        print("\n" + "=" * 60)
        print("交通流量数据分析报告")
        print("=" * 60)

        numeric_cols = self.df.select_dtypes(include=[np.number]).columns
        if '时间点' in numeric_cols:
            numeric_cols = numeric_cols.drop('时间点')
        if '流量变化率' in numeric_cols:
            plot_cols = numeric_cols.drop('流量变化率')
        else:
            plot_cols = numeric_cols

        # 数据概述
        print(f"\n📊 数据概述:")
        print(f"• 观测时间点: {len(self.df)} 个")
        print(f"• 车型种类: {len(plot_cols)} 种")
        print(f"• 总观测流量: {self.df[plot_cols].sum().sum():,} 辆")

        # 主要发现
        print(f"\n🔍 主要发现:")

        # 最高流量车型
        total_by_type = self.df[plot_cols].sum().sort_values(ascending=False)
        top_vehicle = total_by_type.index[0]
        print(
            f"• 流量最大车型: {top_vehicle} ({total_by_type.iloc[0]:,} 辆, 占比 {total_by_type.iloc[0] / total_by_type.sum() * 100:.1f}%)")

        # 最低流量车型
        bottom_vehicle = total_by_type.index[-1]
        print(
            f"• 流量最小车型: {bottom_vehicle} ({total_by_type.iloc[-1]:,} 辆, 占比 {total_by_type.iloc[-1] / total_by_type.sum() * 100:.1f}%)")

        # 流量波动
        if '车流量' in self.df.columns:
            total_col = '车流量'
        else:
            total_col = '总流量'

        if total_col in self.df.columns:
            max_traffic_time = self.df[total_col].idxmax() + 1
            min_traffic_time = self.df[total_col].idxmin() + 1
            print(f"• 流量高峰: 第{max_traffic_time}个时间点 ({self.df[total_col].max():,} 辆)")
            print(f"• 流量低谷: 第{min_traffic_time}个时间点 ({self.df[total_col].min():,} 辆)")

        # 相关性分析结果
        correlation_matrix = self.df[plot_cols].corr()
        high_corr_pairs = []
        for i in range(len(correlation_matrix.columns)):
            for j in range(i + 1, len(correlation_matrix.columns)):
                corr_val = correlation_matrix.iloc[i, j]
                if abs(corr_val) > 0.8:
                    high_corr_pairs.append((correlation_matrix.columns[i],
                                            correlation_matrix.columns[j], corr_val))

        if high_corr_pairs:
            print(f"• 高相关性车型: {len(high_corr_pairs)} 对车型流量高度相关")
        else:
            print(f"• 车型间相关性: 各车型流量相对独立")

        print(f"\n💡 建议:")
        print(f"• 重点关注 {top_vehicle}，其流量占总流量的 {total_by_type.iloc[0] / total_by_type.sum() * 100:.1f}%")
        print(f"• 分析流量高峰和低谷的时间规律，优化交通管理")
        print(f"• 根据车型特点制定差异化的交通策略")

        # 保存分析结果到文件
        output_path = self.file_path.replace('.csv', '_analysis_report.txt')
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write("交通流量数据分析报告\n")
            f.write("=" * 50 + "\n\n")
            f.write(f"分析时间: {pd.Timestamp.now()}\n")
            f.write(f"数据文件: {self.file_path}\n\n")
            f.write("描述性统计:\n")
            f.write(str(self.df[plot_cols].describe()))
            f.write("\n\n相关系数矩阵:\n")
            f.write(str(correlation_matrix.round(3)))

        print(f"\n📄 详细分析报告已保存至: {output_path}")

    def run_complete_analysis(self):
        """运行完整分析"""
        if self.df is None:
            print("数据未正确加载，无法进行分析")
            return

        print("开始交通流量数据分析...")

        # 执行各种分析
        self.basic_info()
        self.descriptive_statistics()
        self.time_series_analysis()
        self.correlation_analysis()
        self.anomaly_detection()
        self.create_visualizations()
        self.generate_report()

        print("\n✅ 分析完成！")


# 使用示例
if __name__ == "__main__":
    repository_root = Path(__file__).resolve().parents[2]
    file_path = repository_root / "data" / "processed" / "Traffic_processed.csv"

    # 创建分析器实例并运行分析
    analyzer = TrafficAnalyzer(file_path)
    analyzer.run_complete_analysis()
