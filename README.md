# 定時任務（macOS / Linux）
在 macOS 或 Linux 上，可以使用 `cron` 來設定定時任務，使 `main.py` 每四分鐘自動執行一次。
請按照以下步驟進行：
## 1. 打開終端機後輸入命令：
crontab -e
## 2. 在打開的 Cron 編輯器底部新增以下一行：
*/4 * * * * /usr/bin/python3 /path/to/your/main.py

*/4 * * * * 是 Cron 表達式，表示每四分鐘執行一次。
/usr/bin/python3 是 Python 3 的安裝路徑，你可以使用 which python3 命令來查找。
/path/to/your/main.py 是你 main.py 文件的完整路徑，請根據實際情況替換成文件的路徑。
## 3. 保存並退出編輯器
在 vim 中，按 Esc 鍵，然後輸入 :wq 並按 Enter。
在 nano 中，按 Ctrl + X，然後選擇 Y 來保存並退出。

# 停止定時任務
若要停止定時執行任務，請按照以下步驟進行：
## 1. 打開終端機後輸入命令：
crontab -e
## 2. 在 Cron 編輯器中，找到之前設置的定時任務行
刪除這一行來停止該任務。
## 3. 保存並退出編輯器
按照使用的編輯器（vim 或 nano）的步驟來退出
## 4. 確認定時任務是否已刪除
輸入以下命令，如沒有顯示任何內容，則表示已成功刪除所有定時任務。
crontab -l



