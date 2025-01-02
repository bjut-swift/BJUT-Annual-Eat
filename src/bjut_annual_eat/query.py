import os
import requests
import yaml


def load_config():
    current_dir = os.path.dirname(os.path.abspath(__file__))
    config_path = os.path.join(current_dir, "config.yaml")

    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def query_card_trade_list(begin_date, end_date, trade_type=1):
    config = load_config()

    url = "https://ydapp.bjut.edu.cn/selftrade/queryCardSelfTradeList"
    params = {
        "beginDate": begin_date,
        "endDate": end_date,
        "tradeType": trade_type,
        "openid": config["user"]["openid"],
        "orgid": "2",
    }

    headers = {
        "Host": "ydapp.bjut.edu.cn",
        "Connection": "keep-alive",
        "isWechatApp": "true",
        "sec-ch-ua-platform": '"Android"',
        "session-type": "uniapp",
        "sec-ch-ua": '"Android WebView";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
        "sec-ch-ua-mobile": "?1",
        "x-requested-with": "XMLHttpRequest",
        "orgid": "2",
        "User-Agent": "Mozilla/5.0 (Linux; Android 14; PJR110 Build/TP1A.220905.001; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/131.0.6778.135 Mobile Safari/537.36 ZhilinEai ZhilinBjutApp/2.5 OPPO PJR110 Android 14 AgentWeb/5.0.8  UCBrowser/11.6.4.950",
        "content-type": "application/json",
        "Accept": "*/*",
        "Sec-Fetch-Site": "same-origin",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Dest": "empty",
        "Referer": "https://ydapp.bjut.edu.cn/",
        "Accept-Encoding": "gzip, deflate, br, zstd",
        "Accept-Language": "zh-CN,zh;q=0.9,ja-JP;q=0.8,ja;q=0.7,en-US;q=0.6,en;q=0.5",
        "Cookie": config["user"]["cookie"],
    }

    try:
        response = requests.get(
            url, params=params, headers=headers, verify=True, stream=True
        )
        response.raw.decode_content = True
        response.raise_for_status()
        return response.json()

    except requests.exceptions.RequestException as e:
        print(f"请求错误: {e}")
        return None
    except ValueError as e:
        print(f"JSON解析错误: {e}")
        print("响应内容:", response.text)
        return None


if __name__ == "__main__":
    # Test Example
    begin_date = "2024-12-01"
    end_date = "2025-01-01"

    result = query_card_trade_list(begin_date, end_date)

    if result:
        import json

        print(json.dumps(result, ensure_ascii=False, indent=2))
