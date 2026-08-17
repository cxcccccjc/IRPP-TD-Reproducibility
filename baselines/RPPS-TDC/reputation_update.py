import math


def reputation_update(is_good_data, historical_reputation, non_updated_reputation,
                      cheating_count, alpha=0.6, k1=1, k2=20):
    """
    工人信誉值更新方法

    参数:
    - is_good_data: bool, 此次提交的数据是否良好
    - historical_reputation: float, 历史完成任务的信誉值 P^{t-1}
    - non_updated_reputation: float, 工人目前没有更新的信誉值 P^n
    - cheating_count: int/float, 工人历史的作弊次数 β
    - alpha: float, 权重参数，默认0.6
    - k1: float, 不良数据情况下的参数，默认1
    - k2: float, 良好数据情况下的参数，默认20

    返回:
    - current_task_reputation: float, 当前任务后的信誉值 P^t
    - updated_reputation: float, 更新后的信誉值 P^n
    """

    if is_good_data:
        # 数据良好的情况
        # P^t = α * (1 / (1 + e^{-k2*P^{t-1}})) + (1-α) * P^n
        sigmoid_term = 1 / (1 + math.exp(-k2 * historical_reputation))
        current_task_reputation = alpha * sigmoid_term + (1 - alpha) * non_updated_reputation
    else:
        # 数据不良的情况
        # P^t = α * P^{t-1} * e^{-k1*β} + (1-α) * P^n
        current_task_reputation = (alpha * historical_reputation * math.exp(-k1 * cheating_count) +
                                   (1 - alpha) * non_updated_reputation)

    # 更新后的信誉值: P^n = (P^t + P^{t-1}) / 2
    updated_reputation = (current_task_reputation + historical_reputation) / 2

    return current_task_reputation, updated_reputation


# 示例使用
if __name__ == "__main__":
    # 测试例子1：工人被评价为良好，历史信誉值为0.6，没有更新的信誉值为0.7，作弊次数为2
    historical_rep = 0.6
    non_updated_rep = 0.7
    cheating_count = 2
    is_good = True

    current_rep, updated_rep = reputation_update(
        is_good_data=is_good,
        historical_reputation=historical_rep,
        non_updated_reputation=non_updated_rep,
        cheating_count=cheating_count
    )

    print(f"历史信誉值: {historical_rep}")
    print(f"未更新信誉值: {non_updated_rep}")
    print(f"历史作弊次数: {cheating_count}")
    print(f"数据质量: {'良好' if is_good else '不良'}")
    print(f"当前任务信誉值: {current_rep:.4f}")
    print(f"更新后的信誉值: {updated_rep:.4f}")

    print("\n" + "=" * 50 + "\n")

    # 测试例子2：数据不良的情况
    current_rep2, updated_rep2 = reputation_update(
        is_good_data=False,
        historical_reputation=0.6,
        non_updated_reputation=0.7,
        cheating_count=2
    )

    print(f"数据不良情况下:")
    print(f"当前任务信誉值: {current_rep2:.4f}")
    print(f"更新后的信誉值: {updated_rep2:.4f}")

    print("\n" + "=" * 50 + "\n")

    # 测试例子3：对比不同数据质量的结果
    print("对比不同数据质量的信誉值更新:")
    print("相同条件下（历史信誉0.6，未更新信誉0.7，作弊次数2）:")

    # 良好数据
    good_current, good_updated = reputation_update(
        is_good_data=True,
        historical_reputation=0.6,
        non_updated_reputation=0.7,
        cheating_count=2
    )

    # 不良数据
    bad_current, bad_updated = reputation_update(
        is_good_data=False,
        historical_reputation=0.6,
        non_updated_reputation=0.7,
        cheating_count=2
    )

    print(f"良好数据: 当前任务信誉值 {good_current:.4f}, 更新后信誉值 {good_updated:.4f}")
    print(f"不良数据: 当前任务信誉值 {bad_current:.4f}, 更新后信誉值 {bad_updated:.4f}")
