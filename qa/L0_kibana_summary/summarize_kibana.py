import query_kibana
import pandas
from datetime import datetime, date, timedelta
import matplotlib.pyplot as plt


# convert string timestamp to datatime object
def StringToDateTime(timestamp_str):
    return datetime.strptime(timestamp_str, "%Y-%m-%dT%H:%M:%S.%fZ")


# convert datatime object to string timestamp
def DateTimeToString(dtime):
    return dtime.strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] + 'Z'


# convert string timestamp to Y-M-D string
def TimestampToYDMString(timestamp):
    return datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d")


# timestamp,onnx,libtorch,netdef,custom,savedmodel,graphdef
def create_timestamp_dataframe(df, label, unique_backends):
    x = pandas.DataFrame(columns=['timestamp'] + unique_backends)
    d = dict()
    time_list = []
    for i, row in df.iterrows():
        if row['backend'] in d:
            # average out timestamps
            d['timestamp'] = sum(time_list) / len(time_list)
            x = x.append(d, ignore_index=True)
            d = dict()
            time_list = []
        d[row['backend']] = row[label]
        time_list.append(StringToDateTime(row['timestamp']).timestamp())

    return x


# Smoothen to YYYY-MM-DD
def create_date_dataframe(x, unique_backends):
    df_days = pandas.DataFrame(columns=['date'] + unique_backends)
    old_ymd = None
    curr_i = 0
    same_day = 1
    for i, row in x.iterrows():
        current_ymd = TimestampToYDMString(row['timestamp'])
        if old_ymd is None:
            old_ymd = current_ymd
        elif old_ymd != current_ymd:
            val_list = dict()
            for col_i in range(1, len(unique_backends) + 1):
                val_list[unique_backends[col_i - 1]] = round(
                    x.iloc[i - same_day:i, col_i].mean(), 2)
            val_list['date'] = old_ymd
            df_days = df_days.append(val_list, ignore_index=True)
            curr_i += 1
            old_ymd = current_ymd
            same_day = 1
        else:
            same_day += 1
    return df_days


# Create moving average
def create_moving_average_dataframe(df_days, unique_backends, ma_days=7):
    ma_df = pandas.DataFrame(columns=['date'] + unique_backends)
    for i in range(df_days.shape[0] - ma_days):
        val_list = dict()
        for col in range(1, len(unique_backends) + 1):
            val_list[unique_backends[col - 1]] = round(
                df_days.iloc[i:i + ma_days, col].mean(), 2)
        val_list['date'] = df_days.iloc[i + ma_days]['date']
        ma_df = ma_df.append(val_list, ignore_index=True)
    return ma_df


# Create current moving average
def current_moving_average_dataframe(label,
                                     value_list,
                                     where_dict,
                                     last_date=None,
                                     plot=False,
                                     plot_file="plot.png"):
    if last_date is None:
        today = date.today()
    else:
        today = datetime.strptime(last_date, "%Y-%m-%d").date()

    end_date = today.strftime("%Y-%m-%d")
    start_date = (today - timedelta(days=120)).strftime("%Y-%m-%d")
    qk = query_kibana.QueryKibana()
    rows = qk.fetch_results(value_list,
                            where_dict=where_dict,
                            limit=0,
                            start_date=start_date,
                            end_date=end_date)
    qk.close()
    df = pandas.DataFrame(rows, columns=[label, 'backend', 'timestamp'])
    df = df.sort_values('timestamp')
    unique_backends = list(set(df['backend']))
    timestamp_df = create_timestamp_dataframe(df, label, unique_backends)
    date_df = create_date_dataframe(timestamp_df, unique_backends)

    ma_df = pandas.DataFrame(columns=['days'] + unique_backends)
    for d in (120, 60, 30, 7):
        start_date = (today - timedelta(days=d)).strftime("%Y-%m-%d")
        date_subset = date_df[date_df['date'] > start_date]
        val_list = dict()
        for col in range(1, len(unique_backends) + 1):
            val_list[unique_backends[col - 1]] = round(
                date_subset.iloc[:, col].mean(), 2)
        val_list['days'] = d
        ma_df = ma_df.append(val_list, ignore_index=True)

    if plot:
        plt.switch_backend('agg')
        ma_df.drop(columns=['days']).plot()
        plt.xticks([0, 1, 2, 3], ma_df.days)
        lgd = plt.legend(loc='upper center', bbox_to_anchor=(0.5, 1.2), ncol=4)
        plt.xlabel('Moving average days')
        plt.ylabel('Inferences / Second')
        plt.savefig(plot_file, bbox_extra_artists=(lgd,), bbox_inches='tight')

    return ma_df