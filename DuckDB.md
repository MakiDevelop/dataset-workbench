# DuckDB 本地大型 CSV 檢視指南

## 為什麼不用 Excel

Excel 雖然方便，但在處理超過百萬行的大型 CSV 時，容易卡頓甚至崩潰。DuckDB 是一個輕量且高效的內嵌分析資料庫，專為處理大型資料設計，能快速載入並查詢本地 CSV 檔案，免除複雜的資料匯入流程。

## Installation (Python pip 安裝)

使用 Python 環境，透過 pip 安裝 DuckDB：

```bash
pip install duckdb
```

## Basic Usage (Python REPL 連線與 read_csv_auto)

啟動 Python REPL，建立 DuckDB 連線，並使用 `read_csv_auto` 直接讀取 CSV：

```python
import duckdb

conn = duckdb.connect()

# 讀取 CSV，路徑為本地檔案
df = conn.execute("""
    SELECT * FROM read_csv_auto('data/output/orders_items_1m.csv')
""").df()

print(df.head())
```

`read_csv_auto` 會自動偵測欄位類型，方便快速載入。

## Common Inspection Queries (count, limit, describe)

常用的資料檢視查詢範例：

```python
# 總筆數
total_rows = conn.execute("""
    SELECT COUNT(*) FROM read_csv_auto('data/output/orders_items_1m.csv')
""").fetchone()[0]
print(f"總筆數: {total_rows}")

# 取前10筆資料
sample_rows = conn.execute("""
    SELECT * FROM read_csv_auto('data/output/orders_items_1m.csv') LIMIT 10
""").df()
print(sample_rows)

# 描述性統計（數值欄位）
desc_stats = conn.execute("""
    DESCRIBE SELECT * FROM read_csv_auto('data/output/orders_items_1m.csv')
""").df()
print(desc_stats)
```

## Sampling Strategies (USING SAMPLE, member slice)

為避免處理全部資料造成效能瓶頸，可使用隨機抽樣或切片：

```python
# 隨機抽樣 1%
sample_1pct = conn.execute("""
    SELECT * FROM read_csv_auto('data/output/orders_items_1m.csv') TABLESAMPLE BERNOULLI (1)
""").df()
print(sample_1pct.head())

# 依 rowid 切片（例如取第 10000 到 10099 筆）
slice_sample = conn.execute("""
    SELECT * FROM (
        SELECT ROW_NUMBER() OVER () AS rowid, * FROM read_csv_auto('data/output/orders_items_1m.csv')
    ) WHERE rowid BETWEEN 10000 AND 10099
""").df()
print(slice_sample)
```

## Export Small Sample for Excel

將抽樣結果匯出為小型 CSV，方便 Excel 使用：

```python
sample_1pct.to_csv('data/output/sample_orders_items.csv', index=False)
print("已匯出 sample_orders_items.csv，可用 Excel 開啟。")
```

## Convert CSV to Parquet (COPY TO PARQUET)

將大型 CSV 轉換為 Parquet 格式，提升後續查詢效能：

```python
conn.execute("""
    COPY (SELECT * FROM read_csv_auto('data/output/orders_items_1m.csv')) 
    TO 'data/output/orders_items_1m.parquet' (FORMAT PARQUET)
""")
print("CSV 已轉換為 Parquet 格式。")
```

## Recommended Next Steps (LTV, 回購分析, 視覺化工具)

完成資料初步檢視後，可進一步：

- 使用 DuckDB 進行 LTV（客戶終身價值）與回購行為分析。
- 將 Parquet 檔案載入視覺化工具（如 Tableau、Power BI、或 Python 的 matplotlib、seaborn）進行深度分析與報表製作。
- 建立定期資料處理流程，利用 DuckDB 快速處理與抽樣，提升分析效率。
