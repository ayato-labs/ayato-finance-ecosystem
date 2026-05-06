# パラケット(Parquet)アーカイブ戦略

## 概要
将来的に `edinet_facts.duckdb` および `edinet_narratives.duckdb` のデータサイズが肥大化し、単一のDuckDBファイルでの管理に限界が来た場合、Apache Parquet フォーマットを用いたコールドデータの外部化（アーカイブ）を実施します。
DuckDBはParquetファイルを直接SQLでクエリできるため、アプリケーションの実装をほとんど変更することなく、ストレージコストを極限まで抑えることが可能です。

## 戦略 (Strategy)

1.  **データのパーティショニング:**
    データを年（YYYY）または月（YYYY-MM）単位で区切ります。
    直近1年分のデータ（ホットデータ）のみをDuckDB内に保持し、それより古いデータ（コールドデータ）をParquetファイルとして出力します。

2.  **アーカイブの実行 (SQL例):**
    ```sql
    -- 古いファクトデータをParquetとして書き出す (ZSTD圧縮を適用)
    COPY (
        SELECT * FROM facts_db.company_facts 
        WHERE filing_date < '2023-01-01'
    ) TO 'data/archive/facts_2022.parquet' (FORMAT PARQUET, CODEC ZSTD);
    
    -- アーカイブしたデータをDuckDBから削除
    DELETE FROM facts_db.company_facts WHERE filing_date < '2023-01-01';
    
    -- 容量を解放
    VACUUM;
    ```

3.  **透過的クエリ (Querying):**
    アプリケーションからは、DuckDBのテーブルとParquetファイルを `UNION ALL` で結合したビュー（View）に対してクエリを投げることで、ストレージの場所を意識せずに全データを検索できます。

    ```sql
    -- アプリケーション向けの透過的ビュー
    CREATE VIEW all_company_facts AS
    SELECT * FROM facts_db.company_facts
    UNION ALL
    SELECT * FROM 'data/archive/facts_*.parquet';
    ```

## メリット
*   **ストレージ効率の最大化:** Parquetは列指向かつ高圧縮であるため、数GBのDuckDBファイルが数百MBに縮小する可能性があります。
*   **パフォーマンスの維持:** Parquetの列指向特性により、特定のカラムのみを集計するクエリ（例：特定科目の過去5年分の推移）が非常に高速に実行できます。
*   **副作用ゼロへの道:** ビューを活用することで、Python側のビジネスロジックは一切変更せずにスケーリングが可能です。