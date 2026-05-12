import duckdb
import os
import json

def extract_tickers():
    # スクリプトの場所を基準にパスを設定
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    services_dir = os.path.dirname(base_dir)
    
    # 1. J-Quants Masterから日本株を抽出
    jquants_db = os.path.join(services_dir, "jquants_provider", "data", "jquants_master.duckdb")
    jp_tickers = []
    if os.path.exists(jquants_db):
        conn = duckdb.connect(jquants_db)
        res = conn.execute("SELECT code FROM tickers").df()
        # 数値のみのコードを抽出して .T を付与
        # J-Quantsの5桁コード(末尾0)を4桁に変換する
        jp_tickers = []
        for code in res['code']:
            code_str = str(code).strip()
            if len(code_str) == 5 and code_str.endswith('0'):
                code_str = code_str[:4]
            jp_tickers.append(f"{code_str}.T")
        conn.close()
        print(f"Extracted {len(jp_tickers)} Japan tickers from J-Quants.")
    else:
        print(f"J-Quants Master DB not found at {jquants_db}")

    # 2. 主要米国株
    us_tickers = ["AAPL", "MSFT", "GOOGL", "TSLA", "NVDA", "AMZN", "META"]
    all_tickers = jp_tickers + us_tickers
    
    # 3. 出力
    output_file = os.path.join(base_dir, "data", "tickers_to_sync.json")
    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    with open(output_file, "w") as f:
        json.dump(all_tickers, f)
    
    print(f"Total {len(all_tickers)} tickers saved to {output_file}")

if __name__ == "__main__":
    extract_tickers()
