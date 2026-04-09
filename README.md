# dataset-workbench

![License: MIT](https://img.shields.io/badge/license-MIT-green)
![Python](https://img.shields.io/badge/python-3.x-blue)
![Docker](https://img.shields.io/badge/Docker-ready-2496ED)


Practical data preparation before analysis — without Excel freezing.
在分析之前，先把資料整理到「能用」的狀態，不再被 Excel 卡住。

A lightweight, web-based workbench for previewing, filtering, reducing, and analyzing large CSV/XLS datasets before further processing.

一個輕量級的 Web 資料工作台，用來在進一步分析或處理之前，快速預覽、篩選、縮小與初步分析大型 CSV / XLS 資料集。

---

## Why dataset-workbench?

When working with large CSV or Excel files, common tools like Excel often freeze or become unusable.
Before running any serious analysis, data usually needs to be **previewed, filtered, and reduced** first.

`dataset-workbench` is built to solve this exact problem.
It is especially suited for **transactional datasets** (such as orders, events, or record-based data),
where row-level inspection, filtering, and reduction are required before analysis.

當資料量一大，Excel 很容易卡死。
實務上，在進行任何分析之前，資料通常需要先**查看、篩選與縮小**。

`dataset-workbench` 正是為了這個真實痛點而生。
本專案特別適合用於**交易型資料集**（例如訂單、事件或各類紀錄型資料），
重點放在分析前的列級（row-level）預覽、篩選與資料縮減。

---

## Key Features / 主要功能

### 🔍 Dataset Preview
- Preview large CSV / XLS files without loading everything into Excel
- Display schema, row count, and sample rows
- Scrollable preview table with safe layout (no page overflow)

### 🔍 資料預覽
- 不需用 Excel 即可快速預覽大型 CSV / XLS
- 顯示欄位結構、總筆數與前幾筆資料
- 預覽表格具備安全捲動，不會撐爆畫面

---

### 🎯 Interactive Filtering (AND / OR)
- Build filter conditions visually
- Support **global AND / OR** logic
- Clear UI indicators showing current filter logic
- Preview query results before export

### 🎯 互動式篩選（AND / OR）
- 以 UI 建立篩選條件，不需寫 SQL
- 支援全域 AND / OR 條件邏輯
- 畫面清楚顯示目前條件邏輯
- 匯出前可先預覽符合條件的資料筆數

---

### 📉 Dataset Reduction & Export
- Reduce dataset size by filtering rows
- Export results as CSV or XLSX
- Export progress indicator to avoid “is it frozen?” confusion

### 📉 資料縮小與匯出
- 透過篩選條件縮小資料集
- 支援 CSV / XLSX 匯出
- 匯出時提供進度提示，不再誤以為系統當機

---

### 📊 Lightweight Analysis
- Basic exploratory analysis and summaries
- Designed for practical data preparation, not heavy BI workloads

### 📊 輕量分析
- 提供基礎探索式分析與摘要
- 著重資料前處理，而非取代完整 BI 平台

---

## Tech Stack / 技術架構

- **Backend**
  - Python
  - FastAPI
  - DuckDB

- **Frontend**
  - Vanilla HTML / CSS / JavaScript
  - No heavy frontend framework

- **Storage**
  - Local filesystem
  - Input: `data/input/`
  - Output: `data/output/`

---

## Project Structure / 專案結構

```text
dataset-workbench/
├── src/
│   ├── api/            # FastAPI routes
│   ├── pipelines/      # Data processing & filtering logic
│   └── frontend/       # UI (HTML / CSS / JS)
├── data/
│   ├── input/          # Place input datasets here
│   └── output/         # Exported results
├── README.md
└── .gitignore
```

---

## Getting Started / 快速開始

### Requirements / 環境需求
- Python 3.9+
- pip

### 1. Install dependencies / 安裝相依套件
```bash
pip install -r requirements.txt
```

### 2. Run the server / 啟動服務
```bash
uvicorn src.api.main:app --reload
```

### 3. Open in browser / 開啟介面
- Analysis UI（分析工具）: http://localhost:8000/ui
- Dataset Reducer（CSV / XLS 縮小器）: http://localhost:8000/reduce

---

## How It Works / 運作方式

1. Upload a CSV / XLS file to the UI.
2. Preview schema and sample rows without loading everything into Excel.
3. Build filter conditions using AND / OR logic.
4. Preview how many rows will be matched.
5. Export a reduced dataset for downstream analysis.

流程說明：
1. 上傳 CSV / XLS 檔案
2. 快速預覽欄位與資料樣本
3. 使用 AND / OR 條件建立篩選邏輯
4. 匯出前先確認符合條件的資料筆數
5. 匯出縮小後的資料集供後續分析使用

---

## Data Directories / 資料目錄說明

- `data/input/`
  - Place source CSV / XLS files here.
  - 原始資料請放置於此目錄。

- `data/output/`
  - Exported datasets will be written here.
  - 匯出後的結果檔案會產生於此目錄。

> Note:
> - The directory structure is tracked by Git.
> - Actual data files are intentionally ignored to avoid committing sensitive data.
>
> 注意：
> - Git 只追蹤目錄結構
> - 實際資料檔案不會被提交到版本庫

---

## Limitations / 限制說明

- This project is not a full BI or visualization platform.
- Filter logic currently supports global AND / OR only (no nested groups).
- Designed for interactive use and data preparation, not long-running batch jobs.

限制說明：
- 本專案並非完整 BI 或視覺化平台
- 目前僅支援全域 AND / OR 條件，尚未支援巢狀群組
- 著重互動式資料整理，不適合長時間批次處理

---

## Status / 專案狀態

This project is under active development.
Features are added based on real-world usage rather than theoretical completeness.

本專案持續開發中，功能演進以實際使用情境為優先考量。