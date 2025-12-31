import sys
import duckdb

from analysis_bootstrap import (
    step_1_overview,
    step_2_schema,
    step_3_sample,
    step_4_grain_detection,
    step_5_available_analyses,
    step_6_data_quality_check,
    step_7_uniqueness_check,
    step_8_null_profile,
    derive_analysis_blacklist,
)


def main(csv_path: str):
    con = duckdb.connect()

    print("\n=== 步驟一：資料總覽 ===")
    print("用途：快速確認資料量與時間範圍")
    overview = step_1_overview(con, csv_path)
    print(overview)

    print("\n=== 步驟二：欄位結構（Schema） ===")
    print("用途：檢視資料欄位與資料型態")
    schema = step_2_schema(con, csv_path)
    print(schema.to_string(index=False))

    print("\n=== 步驟三：資料抽樣 ===")
    print("用途：查看資料樣本，確認資料內容")
    sample = step_3_sample(con, csv_path, limit=5)
    print(sample.to_string(index=False))

    print("\n=== 步驟四：資料粒度判斷 ===")
    print("用途：判斷分析時應該站在哪個資料層級")
    grains = step_4_grain_detection(schema)
    print(grains)

    print("\n=== 步驟五：可進行的分析類型 ===")
    print("用途：列出適合此資料的分析方法")
    analyses = step_5_available_analyses(schema)
    print(analyses)

    print("\n=== 步驟六：資料品質檢查 ===")
    print("用途：檢查資料中可能存在的品質問題")
    data_quality = step_6_data_quality_check(con, csv_path, schema)
    print(data_quality)

    print("\n=== 步驟七：唯一性檢查 ===")
    print("用途：確認關鍵欄位的唯一性")
    uniqueness = step_7_uniqueness_check(con, csv_path, schema)
    print(uniqueness)

    print("\n=== 步驟八：缺值分佈（Null Profile） ===")
    print("用途：分析資料中缺值的分佈情況")
    null_profile = step_8_null_profile(con, csv_path, schema)
    for item in null_profile:
        print(item)

    print("\n=== 分析黑名單（會算錯或高風險的組合） ===")
    blacklist = derive_analysis_blacklist(grains, schema)
    for rule in blacklist:
        icon = "🚫" if rule["severity"] == "block" else "⚠️"
        print(f"{icon} 粒度: {rule['grain']}, 指標: {rule['metric']}, 原因: {rule['reason']}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python run_analysis_bootstrap.py <csv_path>")
        sys.exit(1)

    main(sys.argv[1])