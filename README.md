# 自動分類 Google Photos 截圖 + 每 2 天 AI 重點摘要

每 2 天自動從 Google Photos 抓您最近的截圖，用 Gemini 2.5 Flash 分類成「車宿 / AI 新知 / 對談 / 記錄資料 / 其他」，再用 Claude Sonnet 4.6 做中文重點摘要，透過 Telegram Bot 推給您。

## 資料流

```
手機截圖 ─每天備份─▶ Google Photos
                         │
            每 2 天 09:00 (台北)
                         ▼
              GitHub Actions (cron)
       ┌────────────┬────────────┐
       ▼            ▼            ▼
  Photos API   Gemini Flash  Claude Sonnet 4.6
  拉新截圖       粗分類         深度摘要
       └────────────┬───────────┘
                    ▼
              Telegram Bot 推播
```

## 成本

每次跑 50 張截圖約 $0.10 USD，每月（15 次）約 $1.5 USD。

---

## 一次性設定步驟

### 1. Google Cloud OAuth（約 10 分鐘）

> ⚠️ 自 2025/3 起 Photos Library API 對新 App 收緊。用「Testing」模式把自己加為測試者即可繞過此限制，完全私有。

1. 去 <https://console.cloud.google.com/> 建一個新專案（例：`photo-categorizer`）
2. 左側選單 → APIs & Services → Library → 搜尋 **Photos Library API** → Enable
3. APIs & Services → OAuth consent screen
   - User Type：**External** → Create
   - App name：隨意；Support email / Developer contact：您的 email
   - Publishing status 保持 **Testing**
   - Test users → Add users → 加入自己的 Gmail
4. APIs & Services → Credentials → Create credentials → **OAuth client ID**
   - Application type：**Desktop app**
   - 建完記下 `Client ID` 與 `Client secret`

### 2. 取得 refresh token（只做一次，在本機）

```bash
git clone <your-fork-of-this-repo>
cd test
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

export GOOGLE_CLIENT_ID='你的 client id'
export GOOGLE_CLIENT_SECRET='你的 client secret'
python scripts/auth_bootstrap.py
```

瀏覽器會跳出 → 登入自己的 Google 帳號 → 同意權限 → 終端機會印出 `GOOGLE_REFRESH_TOKEN=1//0...`，複製起來。

### 3. Telegram Bot（約 3 分鐘）

1. Telegram 找 `@BotFather` → `/newbot` → 照步驟命名 → 拿到 `BOT_TOKEN`
2. 找自己剛建的 bot，隨便傳一句訊息（例：`hi`）
3. 打開 `https://api.telegram.org/bot<BOT_TOKEN>/getUpdates`，找 JSON 裡的 `chat.id`（通常是一串純數字）

### 4. API keys

- Anthropic Console <https://console.anthropic.com/> → API Keys → Create Key
- Google AI Studio <https://aistudio.google.com/apikey> → Get API key

### 5. GitHub Secrets

把這個 repo push 到自己的 GitHub，然後 Settings → Secrets and variables → Actions → New repository secret，加入：

| Secret 名稱 | 值 |
| --- | --- |
| `GOOGLE_CLIENT_ID` | 步驟 1.4 拿到的 |
| `GOOGLE_CLIENT_SECRET` | 步驟 1.4 拿到的 |
| `GOOGLE_REFRESH_TOKEN` | 步驟 2 印出的 |
| `ANTHROPIC_API_KEY` | 步驟 4 的 Claude key |
| `GEMINI_API_KEY` | 步驟 4 的 Gemini key |
| `TELEGRAM_BOT_TOKEN` | 步驟 3.1 |
| `TELEGRAM_CHAT_ID` | 步驟 3.3 |

### 6. 第一次手動觸發

GitHub repo → Actions → `Categorize Screenshots` → **Run workflow**，看 log 是否完整跑完，Telegram 是否收到訊息。之後會每 2 天自動跑。

---

## 本機測試

```bash
cp .env.example .env
# 編輯 .env 填入實際值

python scripts/main.py --dry-run    # 只印 report 到 stdout，不推 Telegram
python scripts/main.py              # 實際推 Telegram
```

---

## 檔案自動改名

分類完成後，下載下來的圖片會依內容改名為 `YYYY-MM-DD-類別-摘要.jpg`，例如：

```
2026-04-24-車宿-露營車水塔保養.jpg
2026-04-24-AI新知-Claude_4_7發表.jpg
2026-04-24-記錄資料-長榮機票電子憑.jpg
```

- 日期取自 Google Photos 的 `creationTime`
- 摘要由 Gemini Flash 產出，最多 10 字
- 類別最多 8 字
- 非法檔名字元（`<>:"/\|?*`）會被濾掉
- 重複檔名會自動加 `-2`、`-3` 後綴

改名後的檔案清單會：
1. 出現在 Telegram 報告每類別的「檔名：」區（附 Google Photos 連結）
2. 寫進 [`state/last_batch.json`](state/last_batch.json) 方便追溯

### 想永久保留改名後的檔案

設定環境變數 `ARCHIVE_DIR=/path/to/folder`（本機跑時），會把改名後的副本複製到該目錄。GitHub Actions 上因為 runner 的檔案系統是拋棄式的，所以沒意義；要雲端歸檔請用 Google Drive 或其他持久化儲存（可自行擴充 `rename_and_archive` 的目的地）。

## 調整分類邏輯

- 分類規則在 [`prompts/classify_prompt.txt`](prompts/classify_prompt.txt)
- 摘要風格在 [`prompts/summarize_prompt.txt`](prompts/summarize_prompt.txt)
- 哪些類別要深度摘要 → 改 [`scripts/main.py`](scripts/main.py) 的 `SUMMARIZE_CATEGORIES`
- 檔名長度上限 → 改 [`scripts/rename.py`](scripts/rename.py) 的 `MAX_CAPTION_CHARS` / `MAX_CATEGORY_CHARS`

---

## 常見問題

**Q: OAuth 每 7 天要重新授權？**
A: Testing 模式的 refresh token 有效期 7 天是舊規則；目前實測通常能撐更久。若哪天 workflow 因 `invalid_grant` 失敗，重跑一次 `auth_bootstrap.py` 更新 `GOOGLE_REFRESH_TOKEN` secret 即可。

**Q: 想改成每天 / 每週跑？**
A: 改 [`.github/workflows/categorize.yml`](.github/workflows/categorize.yml) 的 cron 跟 `LOOKBACK_DAYS` 即可。

**Q: 不信任 Google Photos API 的穩定性？**
A: 把手機截圖資料夾改同步到 Google Drive（Android 用 Autosync for Google Drive；iOS 用捷徑 + Drive App），之後把 `scripts/google_photos.py` 換成 Drive API 版本即可，其他模組不動。
