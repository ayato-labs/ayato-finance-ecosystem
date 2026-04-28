import json
from loguru import logger
from typing import Dict, Optional, Any
from google import genai
from pydantic import BaseModel, Field
from src.ai_utils import retry_on_ai_quota, AIRateLimiter

class NarrativeAnalysis(BaseModel):
    capex_summary: str = Field(description="Summary of Capex and future investment plans")
    rd_summary: str = Field(description="Summary of R&D and technological advantages")
    governance_summary: str = Field(description="Summary of capital allocation policy and governance discipline")
    key_quotes: list[str] = Field(description="Direct quotes from the filing that support the summaries")
    sentiment_score: float = Field(description="Qualitative sentiment score from 0.0 to 1.0 (optimistic vs disciplined)")

class EdgarAnalyzer:
    """
    抽出されたセクションから、経営の質（Gate 1）に関する洞察を LLM で抽出するクラス
    """
    def __init__(self, api_key: str, model_id: str = "gemini-2.0-flash"):
        self.client = genai.Client(api_key=api_key)
        self.model_id = model_id

    def _generate_prompt(self, sections: Dict[str, str]) -> str:
        # 必要なセクションを結合
        mda = sections.get("mda", "")
        business = sections.get("business", "")
        risk = sections.get("risk_factors", "")
        
        prompt = f"""
以下の SEC Filing (10-K/10-Q) の抜粋を分析し、投資判断に重要な定性情報を抽出してください。

### 分析対象テキスト
[Item 1. Business]
{business[:15000]}

[Item 7. Management's Discussion and Analysis]
{mda[:20000]}

### 抽出・分析のガイドライン
1. **Capex (設備投資)**: 将来の成長のための投資計画、工場の新設・更新、具体的な投資額や時期に言及があれば抽出。
2. **R&D (研究開発)**: 技術的優位性、開発パイプライン、競合他社に対するエッジについて抽出。
3. **Governance & Discipline**: 資本配分の方針（株主還元 vs 再投資）、経営陣の規律、ガバナンス上の特徴。

出力は必ず指定された JSON 形式に従ってください。
"""
        return prompt

    @retry_on_ai_quota(max_retries=10)
    async def analyze_narratives(self, sections: Dict[str, str]) -> Optional[NarrativeAnalysis]:
        """
        セクション情報を分析し、構造化された洞察を返す
        """
        if not sections:
            return None

        # レート制限を考慮
        await AIRateLimiter.throttle()

        prompt = self._generate_prompt(sections)
        
        logger.info(f"Starting narrative analysis using {self.model_id}...")
        response = await self.client.aio.models.generate_content(
            model=self.model_id,
            contents=prompt,
            config={
                "response_mime_type": "application/json",
                "response_schema": NarrativeAnalysis,
            }
        )
        
        if response and response.parsed:
            logger.success("Narrative analysis completed successfully.")
            return response.parsed
        else:
            logger.error("Failed to parse analysis results from Gemini.")
            return None

if __name__ == "__main__":
    # 簡易テスト
    import asyncio
    import os
    
    async def test():
        api_key = os.environ.get("GOOGLE_API_KEY")
        if not api_key:
            print("GOOGLE_API_KEY not found")
            return
            
        analyzer = EdgarAnalyzer(api_key=api_key)
        # ダミーデータ
        sections = {"mda": "We plan to invest $10B in new AI data centers over the next 3 years.", "business": "Our R&D focus is on next-gen chips."}
        result = await analyzer.analyze_narratives(sections)
        print(result)

    asyncio.run(test())
