# シーケンス図 - EDGAR Data Pipeline (Completeness-Aware)

この図は、一つの提出書類（Filing）が発見されてから、定性・定量データの「完全性」を考慮して保存・修復されるまでの流れを示します。

## メインフロー

```mermaid
sequenceDiagram
    participant CLI as main.py
    participant P as Pipeline
    participant F as EdgarFetcher
    participant Q as EdgarQuantitative (edgartools)
    participant S as EdgarStorage (DuckDB)
    participant SEC as SEC API (EDGAR)

    CLI->>P: sync_recent_us_filings() / process_us_tickers()
    P->>F: list_daily_filings(date) / get_latest_submissions()
    F->>SEC: GET Daily Index / Submissions
    SEC-->>F: Index Content / Metadata
    F-->>P: Filings (acc_no, ticker)

    loop Each Filing
        P->>S: filing_exists(acc_no)
        S-->>P: exists (Boolean)
        P->>S: facts_exist(acc_no)
        S-->>P: facts_present (Boolean)

        rect rgb(240, 240, 240)
            Note over P, SEC: Smart Repair Logic
            
            alt exists == False
                Note right of P: 書類自体がない（新規）
                P->>F: resolve_filing_metadata(acc_no)
                F->>SEC: GET submissions/CIK{cik}.json
                SEC-->>F: primaryDocument
                F-->>P: metadata
                
                alt metadata == None
                    Note right of P: メタデータ解決失敗 - スキップ
                else metadata != None
                    P->>F: fetch_filing_content(url)
                    F->>SEC: GET HTML Document
                    SEC-->>F: HTML content
                    P->>P: _validate_filing(metadata, sections)
                    
                    alt バリデーション成功
                        P->>S: save_filing() + save_filing_sections()
                        P->>Q: extract_facts(acc_no)
                        Q->>Q: _derive_fiscal_period()
                        Q-->>P: facts DataFrame
                        P->>P: _validate_facts(ticker, acc_no, df)
                        P->>S: save_facts_batch()
                    else バリデーション失敗
                        Note right of P: DataIntegrityError - スキップ
                    end
                end
                
            else exists == True AND facts_present == False
                Note right of P: 書類はあるが数値が欠けている（修復）
                P->>Q: extract_facts(acc_no)
                Q->>Q: _derive_fiscal_period()
                Q-->>P: facts DataFrame
                P->>P: _validate_facts(ticker, acc_no, df)
                P->>S: save_facts_batch()
                
            else
                Note right of P: 既に完全なデータがある
                P->>P: スキップ
            end
        end
        
        Note over P: asyncio.sleep(0.11) - SEC制限遵守
    end
```

## リクエストリトライフロー

SEC APIへのリクエストでエラーが発生した場合のリトライ処理：

```mermaid
sequenceDiagram
    participant F as EdgarFetcher
    participant SEC as SEC API

    F->>SEC: HTTP Request
    
    alt 200 OK
        SEC-->>F: Response Data
    else 429 / 5xx Error
        SEC-->>F: Error Response
        F->>F: wait_time = (2^attempt) + random(0,1)
        F->>F: sleep(wait_time)
        Note over F: max_retries=5（指数バックオフ）
        F->>SEC: Retry Request
    end
```
