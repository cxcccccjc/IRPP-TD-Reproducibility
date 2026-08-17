import pickle
import pandas as pd
import chardet
import numpy as np

# vne_num是系统中的代号，其数量必须大于原始的车辆编号总数
vne_num = 200000
# real_num是系统中真正的工人数量
real_num = 600
# time是系统迭代的时间最小单位
time = 10

if __name__ == '__main__':

    # trace[id][ip]
    trace = []
    for i in range(vne_num):
        trace.append(["veh" + str(i)])

    # print(trace)

    with open('trace.pkl', 'rb') as f:
        data = pickle.load(f)

    # print(data)

    for time_trace in data:
        for id in time_trace:
            # print(int(id[0][3:]))
            trace[int(id[0][3:])].append(id[1])

    # 格式是编号+轨迹
    print("trace", trace[1][2])

    #将其映射到100个工人的轨迹当中
    #mid_trace = [id] [alltime for all_local] [a_local]
    mid_trace = []
    for i in range(real_num):
        mid_trace.append(["veh" + str(i)])
    for item in trace:
        if len(item) > 1:
            #不带时间的版本
            # print(mid_trace[int(item[0][3:])%100])
            mid_trace[int(item[0][3:])%real_num].append(item[1:])
            #带有时间的版本
            # mid_trace[int(item[0][3:]) % real_num].append(["time:"+str(len(mid_trace[int(item[0][3:]) % real_num])*10)+'h',item[1:]])

    # # print(mid_trace)
    # df = pd.DataFrame(mid_trace)
    # # 保存为CSV文件
    # df.to_csv('original_wehicle_tracks.csv', index=False)

    # 查看每个车辆的轨迹报告总数
    # for i in mid_trace:
    #     print(i[1])

    # 每辆车每个时间段的车辆位置计算为中心元素
    final_trace = []
    for i in range(real_num):
        final_trace.append(["veh" + str(i)])
    time = 0
    for i in mid_trace:
        for j in i[1:]:
            length = len(j)
            sum_of_horizontal_coorfinate = 0
            sum_of_vertical_coorfinate = 0
            for ho,ve in j:
                sum_of_horizontal_coorfinate = sum_of_horizontal_coorfinate + ho
                sum_of_vertical_coorfinate   = sum_of_vertical_coorfinate + ve
            final_trace[time].append(('%.2f' % (sum_of_horizontal_coorfinate/length), '%.2f' % (sum_of_vertical_coorfinate/length)))
        time = time + 1

    # 查看每个车辆的最终轨迹报告总数
    for i in final_trace:
        print(len(i))

    # df = pd.DataFrame(final_trace)
    # # # 保存为CSV文件
    # df.to_csv('experience_of_workers_tracks.csv', index = False)
    # with open('experience_of_workers_tracks.pkl', 'wb') as f:
    #     pickle.dump(final_trace, f)
    final_trace_no_id = []
    for i in final_trace:
        final_trace_no_id.append(i[1:])

    # final_trace_no_id = np.array(final_trace_no_id)
    # print(final_trace_no_id)
    with open('experience_of_workers_tracks.pkl', 'wb') as file:
        pickle.dump(final_trace_no_id, file)
