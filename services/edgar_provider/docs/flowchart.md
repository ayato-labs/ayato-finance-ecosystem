# フローチャート図 - EDGAR Sync & Repair Logic

データの「完全性（Completeness）」を担保するための論理パスを示します。

```mermaid
graph TD
    Start([同期開始]) --> GetIndex[SEC Indexの取得]
    GetIndex --> EachFiling{各書類について}
    
    EachFiling --> CheckExists{書類(定性)は<br/>DBにあるか?}

    CheckExists -- No --> FullSync[ダウンロード & <br/>定性・定量データの全取得]
    
    CheckExists -- Yes --> CheckFacts{財務数値(定量)は<br/>DBにあるか?}

    CheckFacts -- No --> RepairFacts[定量データのみ<br/>抽出 & 補完]
    CheckFacts -- Yes --> Skip[スキップ<br/>完全なデータ]

    FullSync --> SaveDB[DuckDBへの保存]
    RepairFacts --> SaveDB

    SaveDB --> End([同期完了])

    subgraph RepairCommand [repair-facts コマンド]
        FindGaps[数値が欠けている全IDを抽出] --> LoopRepair[一つずつ補完実行]
    end

    style RepairFacts fill:#e1f5fe,stroke:#01579b
    style FullSync fill:#fff9c4,stroke:#fbc02d
```
