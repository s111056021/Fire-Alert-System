import firebase_admin
from firebase_admin import credentials, db
from datetime import datetime
import pytz
from dotenv import load_dotenv
import os
import requests

load_dotenv() # load .env

# === Firebase 初始化 ===
cred_path = os.getenv("FIREBASE_DATABASE_CERTIFICATE_PATH") # 從環境變數讀取JSON 憑證檔路徑與 URL
db_url = os.getenv("FIREBASE_DATABASE_URL")
cred = credentials.Certificate(cred_path)
if not firebase_admin._apps:
    firebase_admin.initialize_app(cred, {
        'databaseURL': db_url
    })

# === 參數設定區 ===
THRESHOLD_TEMP = 45
THRESHOLD_MQ2 = 2500 # 可調整
THRESHOLD_MQ7 = 150 # 可調整
TIME_WINDOW_MINUTES = 5
FIRE_ALERT_COUNT_THRESHOLD = 3  # 至少 N 筆資料超標才判定為火災

# === 時區設定 ===
taiwan_tz = pytz.timezone('Asia/Taipei') # 台灣時區（UTC+8）

# === 測試模式設定 ===
TEST_MODE = True  # 若為 False，則使用現在時間
TEST_TIME = '2025-05-11 01:30:00'  # 測試時間（格式：YYYY-MM-DD HH:MM:SS）
UNIX_TIME = 1747057201 # 測試時間 unix 格式
# d1_normal:1746919281, d2_normal:1747059327, d1_alart:1747057201

#=== Telegram bot 設定 ===
bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
chat_id = os.getenv("TELEGRAM_CHAT_ID")

# === 函式：發送警報 ===
def send_telegram_alert(message):
    url = f'https://api.telegram.org/bot{bot_token}/sendMessage'
    params = {'chat_id': chat_id, 'text': message}
    try:
        response = requests.post(url, data=params)
        print("訊息發送狀態碼：", response.status_code)
        if response.status_code != 200:
            print("發送訊息失敗！", response.text)
    except Exception as e:
        print("Telegram 發送失敗：", e)
        
# === 函式：根據裝置 ID 抓取時間範圍內的感測資料 ===
def filter_device_data(device_id):
    if TEST_MODE:
        target_time = datetime.fromtimestamp(UNIX_TIME) # 使用 Unix 時間戳
        # 或使用TEST_TIME
        # target_time = datetime.strptime(TEST_TIME, '%Y-%m-%d %H:%M:%S')
    else:
        target_time = datetime.now(taiwan_tz)

    # 測試用，印出裝置ID與時間區間
    # print(f"[{device_id}] Target Time:", target_time.strftime('%Y-%m-%d %H:%M:%S'))

    end_ts = int(target_time.timestamp())
    start_ts = end_ts - (TIME_WINDOW_MINUTES * 60)

    # 抓取五(window)分鐘內資料
    ref = db.reference(f'/sensor_data/{device_id}')
    query = ref.order_by_key().start_at(str(start_ts)).end_at(str(end_ts))
    filtered_data = query.get()
    
    if not filtered_data:
        print(f"[{device_id}] 沒有符合時間範圍內的資料。")
        return [], start_ts, end_ts
    
    # selected = [(int(ts), val) for ts, val in filtered_data.items()]
    
    selected = []
    for ts, val in filtered_data.items():
        try:
            ts_int = int(ts) # 確認 key 是否可轉為int
            if start_ts <= ts_int <= end_ts:
                selected.append((ts_int, val))
        except ValueError:
            print(f"[{device_id}] 忽略無效時間戳：{ts}")
    
    selected.sort(key=lambda x: x[0])
    return selected, start_ts, end_ts

# === 函式：抓取資料庫中所有裝置ID ===
def fetch_all_devices_data():
    root_ref = db.reference('/sensor_data')
    device_ids = root_ref.get(shallow=True)  # 只抓裝置 ID 清單，不含資料

    if not device_ids:
        print("資料庫中沒有任何裝置資料。")
        return []

    results = []

    for device_id in device_ids.keys():
        selected_data, start_ts, end_ts = filter_device_data(device_id)
        if selected_data:
            results.append((device_id, selected_data, start_ts, end_ts))

    return results

# === 函式：分析資料與警報邏輯 ===
def analyze_data(data, device_id):
    if not data:
        print(f"[{device_id}] 沒有符合時間範圍內的資料。")
        return

    anomaly_count = 0
    anomaly_details = []  # 記錄異常描述
    print(f"[{device_id}] 分析筆數：{len(data)}")

    # 每筆資料個別判斷異常狀況
    for ts, val in data:
        temp = val.get('temperature', 0)
        mq2 = val.get('mq2', 0)
        mq7 = val.get('mq7', 0)
        time_str = datetime.fromtimestamp(ts, taiwan_tz).strftime('%H:%M:%S')
        
        temp_alert = temp > THRESHOLD_TEMP
        mq2_alert = mq2 > THRESHOLD_MQ2
        mq7_alert = mq7 > THRESHOLD_MQ7
        
        # 三種異常類型
        alerts = []
        if temp_alert:
            alerts.append("高溫")
        if mq2_alert:
            alerts.append("煙霧過多")
        if mq7_alert:
            alerts.append("高一氧化碳")

        status = "、".join(alerts) if alerts else "正常"
        print(f"[{device_id}] [{time_str}] Temp: {temp}°C | MQ2: {mq2} | MQ7: {mq7} → {status}")

        if alerts:
            anomaly_count += 1
            anomaly_details.append(f"[{time_str}] {status}")

    # 綜合判斷
    if anomaly_count >= FIRE_ALERT_COUNT_THRESHOLD:
        detail_str = "\n".join(anomaly_details)
        alert_msg = f"警告：裝置 {device_id} 偵測到多筆異常（共 {anomaly_count} 筆），異常項目如下：\n{detail_str}"
        print(alert_msg)
        send_telegram_alert(alert_msg)
    else:
        normal_msg = f"裝置[{device_id}] 狀態正常。"
        print(normal_msg)
        if TEST_MODE:
            send_telegram_alert(normal_msg) # 測試時即使正常也送出通知

        
# === 主程式 ===
if __name__ == "__main__":
    device_data_list = fetch_all_devices_data()

    for device_id, data, start_ts, end_ts in device_data_list:
        print(f"\n=== 裝置 {device_id} 分析區間：{datetime.fromtimestamp(start_ts, taiwan_tz)} ~ {datetime.fromtimestamp(end_ts, taiwan_tz)}")
        analyze_data(data, device_id)

