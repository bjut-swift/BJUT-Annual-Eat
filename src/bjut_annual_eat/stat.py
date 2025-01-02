import polars as pl
import matplotlib.pyplot as plt
from matplotlib.font_manager import FontProperties
import calendar
import json
from bjut_annual_eat.query import query_card_trade_list, load_config
import os
import warnings
import pathlib
import time

warnings.filterwarnings("ignore", category=UserWarning)


def get_monthly_data(year):
    config = load_config()
    all_data = []

    test_mode = config["settings"]["test_mode"]

    if test_mode:
        month_range = range(
            config["settings"]["test_month_start"],
            config["settings"]["test_month_end"] + 1,
        )
    else:
        month_range = range(1, 13)

    cache_dir = f"cache/{year}"
    os.makedirs(cache_dir, exist_ok=True)

    for month in month_range:
        cache_file = f"{cache_dir}/{month:02d}.json"

        if os.path.exists(cache_file):
            print(f"从缓存读取 {year}年{month}月 的数据...")
            with open(cache_file, "r", encoding="utf-8") as f:
                response = json.load(f)
        else:
            print(f"正在获取 {year}年{month}月 的数据...")
            start_date = f"{year}-{month:02d}-01"
            _, last_day = calendar.monthrange(year, month)
            end_date = f"{year}-{month:02d}-{last_day:02d}"

            response = query_card_trade_list(start_date, end_date)
            time.sleep(0.5)

            if response and response.get("success"):
                with open(cache_file, "w", encoding="utf-8") as f:
                    json.dump(response, f, ensure_ascii=False, indent=2)

        if (
            response
            and response.get("success")
            and "data" in response
            and "data" in response["data"]
        ):
            all_data.extend(response["data"]["data"])
        else:
            print(f"警告: {year}年{month}月 的数据获取失败")

    print(f"共获取 {len(all_data)} 条记录")
    return all_data


def analyze_consumption(year=2024):
    data = get_monthly_data(year)

    df = pl.DataFrame(data)

    font_path = pathlib.Path(__file__).parent / "fonts" / "SimHei.ttf"
    font = FontProperties(fname=str(font_path))

    # 定义商户分类
    dining_merchants = [
        "北区新餐厅",
        "天天风味",
        "天天餐厅",
        "天天餐厅吧台",
        "奥运餐厅一层",
        "奥运餐厅二层",
        "清真餐厅基本伙",
        "清真餐厅水吧",
        "清真餐厅风味组",
        "美食园",
        "风味餐厅",
    ]

    market_merchants = ["京客隆超市", "京客隆", "超市"]

    df = df.with_columns(
        [
            pl.col("txdate").str.strptime(pl.Datetime, format="%Y-%m-%d %H:%M:%S"),
            pl.col("txamt").cast(pl.Float64),
        ]
    )

    df = df.with_columns(
        [
            pl.col("txdate").dt.month().alias("month"),
            pl.when(pl.col("mername").is_in(dining_merchants))
            .then(pl.lit("饮食"))
            .when(pl.col("mername").is_in(market_merchants))
            .then(pl.lit("超市"))
            .otherwise(pl.lit("其他"))
            .alias("category"),
            # 保留原始商户名称用于食堂详情统计
            pl.when(pl.col("mername").is_in(dining_merchants))
            .then(pl.col("mername"))
            .otherwise(pl.lit("其他"))
            .alias("dining_place"),
        ]
    )

    df = df.with_columns(
        [
            pl.col("txdate").dt.hour().alias("hour"),
            pl.col("txdate").dt.weekday().alias("weekday"),
        ]
    )

    # 1. 总消费量
    total_consumption = df.select(pl.col("txamt").abs().sum()).item()

    # 2. 月度消费统计
    monthly_consumption = (
        df.group_by("month")
        .agg(pl.col("txamt").abs().sum().alias("txamt"))
        .sort("month")
    )

    # 3. 消费构成（食堂 vs 其他）
    category_consumption = (
        df.group_by("category")
        .agg(pl.col("txamt").abs().sum().alias("txamt"))
        .sort("txamt", descending=True)
    )

    # 4. 食堂消费明细 - 修改筛选条件
    canteen_consumption = (
        df.filter(pl.col("dining_place") != "其他")
        .group_by("dining_place")
        .agg(pl.col("txamt").abs().sum().alias("txamt"))
        .sort("txamt", descending=True)
    )

    # 创建热力图数据
    heatmap_data = (
        df.filter(pl.col("category") == "饮食")  # 只看餐饮消费
        .group_by(["weekday", "hour"])
        .agg(pl.len().alias("count"))
        .pivot(values="count", index="weekday", on="hour", aggregate_function="sum")
        .fill_null(0)
        .sort("weekday")
    )

    if os.path.exists("/.dockerenv"):
        base_output_dir = "/app/output"
    else:
        base_output_dir = "output"

    output_dir = os.path.join(base_output_dir, str(year))
    os.makedirs(output_dir, exist_ok=True)

    plt.style.use("seaborn-v0_8")
    fig = plt.figure(figsize=(16, 12))
    fig.suptitle(
        f"{year}年消费统计报告\n总消费: {total_consumption:.2f}元",
        fontproperties=font,
        fontsize=14,
        y=0.98,
    )

    gs = fig.add_gridspec(
        2, 2, hspace=0.25, wspace=0.2, top=0.9, bottom=0.1, left=0.1, right=0.9
    )

    # 1. 月度消费趋势 (左上)
    ax1 = fig.add_subplot(gs[0, 0])
    bars = ax1.bar(
        monthly_consumption["month"].to_list(),
        monthly_consumption["txamt"].to_list(),
        color="#2ecc71",
    )
    ax1.set_title(f"{year}年月度消费趋势", fontproperties=font, pad=10)
    ax1.set_xlabel("月份", fontproperties=font)
    ax1.set_ylabel("消费金额（元）", fontproperties=font)
    for bar in bars:
        height = bar.get_height()
        ax1.text(
            bar.get_x() + bar.get_width() / 2.0,
            height,
            f"{height:.0f}",
            ha="center",
            va="bottom",
            fontproperties=font,
            fontsize=8,
        )

    # 2. 消费构成饼图 (右上)
    ax2 = fig.add_subplot(gs[0, 1])
    colors = ["#3498db", "#e74c3c", "#f1c40f"]
    wedges, texts, autotexts = ax2.pie(
        category_consumption["txamt"].to_list(),
        labels=category_consumption["category"].to_list(),
        colors=colors,
        autopct="%1.1f%%",
        textprops={"fontproperties": font},
    )
    ax2.set_title("消费构成分析", fontproperties=font, pad=10)

    # 3. 各食堂消费对比 (左下)
    ax3 = fig.add_subplot(gs[1, 0])
    bars = ax3.bar(
        canteen_consumption["dining_place"].to_list(),
        canteen_consumption["txamt"].to_list(),
        color="#9b59b6",
    )
    ax3.set_title("各食堂消费对比", fontproperties=font, pad=10)
    ax3.set_xlabel("食堂", fontproperties=font)
    ax3.set_ylabel("消费金额（元）", fontproperties=font)
    plt.setp(ax3.xaxis.get_majorticklabels(), rotation=45, ha="right", fontsize=8)
    ax3.set_xticklabels(
        canteen_consumption["dining_place"].to_list(), fontproperties=font
    )

    # 添加数值标签
    for bar in bars:
        height = bar.get_height()
        ax3.text(
            bar.get_x() + bar.get_width() / 2.0,
            height,
            f"{height:.0f}",
            ha="center",
            va="bottom",
            fontproperties=font,
            fontsize=8,
        )

    # 4. 消费时段热力图 (右下)
    ax4 = fig.add_subplot(gs[1, 1])
    weekdays = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
    hour_columns = [str(i) for i in range(24)]
    existing_columns = set(heatmap_data.columns) - {"weekday"}

    for hour in hour_columns:
        if hour not in existing_columns:
            heatmap_data = heatmap_data.with_columns(pl.lit(0).alias(hour))

    heatmap_matrix = (
        heatmap_data.select(["weekday"] + hour_columns).select(hour_columns).to_numpy()
    )

    im = ax4.imshow(heatmap_matrix, cmap="YlOrRd", aspect="auto")

    ax4.set_xticks(range(24))
    ax4.set_yticks(range(7))
    ax4.set_xticklabels(range(24), fontproperties=font, fontsize=8)
    ax4.set_yticklabels(weekdays, fontproperties=font, fontsize=8)
    ax4.set_title("三餐时间检测", fontproperties=font, pad=10)
    ax4.set_xlabel("小时", fontproperties=font)
    ax4.set_ylabel("星期", fontproperties=font)

    cbar = plt.colorbar(im, ax=ax4)
    cbar.set_label("消费次数", fontproperties=font)
    cbar.ax.tick_params(labelsize=8)
    for l in cbar.ax.yaxis.get_ticklabels():  # noqa: E741
        l.set_font_properties(font)

    plt.savefig(
        os.path.join(output_dir, "consumption_analysis.jpg"),
        dpi=300,
        bbox_inches="tight",
    )
    plt.close()

    monthly_consumption.write_csv(os.path.join(output_dir, "monthly_consumption.csv"))
    category_consumption.write_csv(os.path.join(output_dir, "category_consumption.csv"))
    canteen_consumption.write_csv(os.path.join(output_dir, "canteen_consumption.csv"))

    print(f"\n{year}年消费统计:")
    print(f"总消费: {total_consumption:.2f}元")
    print("\n月度消费:")
    print(monthly_consumption)
    print("\n消费构成:")
    print(category_consumption)
    print("\n食堂消费明细:")
    print(canteen_consumption)


if __name__ == "__main__":
    # 直接运行，不需要传入 test_mode 参数
    analyze_consumption(2024)
