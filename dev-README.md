## 兩種使用模式（dev / web）

- **dev 模式**：給開發者使用，用於撰寫與反覆測試 Python script、資料分析、圖表實驗。  
- **web 模式**：模擬實際產品，提供 Web 介面讓使用者上傳 CSV 並查看分析結果與圖表。  
- 兩種模式共用同一個 Docker image 與程式碼，只差在啟動指令（command）。

### dev 模式操作範例

```bash
docker compose up dev
docker compose exec dev bash
```

### web 模式操作範例

```bash
docker compose up web
```

瀏覽 http://localhost:8000

---

- dev 模式預設 command 為 bash  
- web 模式預設 command 為 uvicorn  
- 此設計可避免在開發與展示之間反覆修改設定

## 使用 VS Code 進入開發環境（建議）

### 建議方式：Attach to Running Container
此方式適合目前專案結構，無需修改 Dockerfile 或 docker-compose 設定，即可直接連線至正在執行的開發容器，享受完整的開發體驗。

### 一次性準備
請先安裝以下 VS Code 官方擴充套件：
- Docker
- Dev Containers

### 操作步驟
1. 使用 `docker compose up -d dev web` 啟動容器
2. 開啟 VS Code
3. 使用 Command Palette（Cmd + Shift + P）
4. 選擇「Attach to Running Container」
5. 選擇 `python-lab-dev`
6. 在 Container 視窗中開啟 `/workspace`

### 開發體驗說明
- VS Code 實際連線至容器內部環境
- Python、Terminal、Debugger 均在容器中執行
- 原始碼與資料仍存放於本機，透過 volume 共享
- 本機無需安裝 Python 或相關套件

### 補充說明
目前不建議直接導入 `.devcontainer/` 設定，避免增加專案複雜度。未來若專案需交付他人，可再依需求補充相關設定。
