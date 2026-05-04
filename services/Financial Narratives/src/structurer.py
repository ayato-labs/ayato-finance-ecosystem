import json
from google import genai
from google.genai import types
from loguru import logger
from src.config import LLM_MODEL_NAME


class FilingStructurer:
    """
    抽出されたセクション（Markdown）から特定の事実項目を構造化抽出するクラス。
    解釈や分析は行わず、テキストに含まれる事実の特定に特化する。
    """

    SYSTEM_PROMPT = """
あなたは高度な金融データエンジニアです。提供された企業の開示資料（定性情報）から、以下の項目について「事実」のみを構造化抽出してください。
主観的な解釈や感情的な分析は一切含めないでください。

抽出対象項目:
1. capex (設備投資): 将来の投資計画、既存設備の更新予定、具体的な投資金額や時期の記述。
2. rd (研究開発): 重点的な研究開発項目、技術的優位性の根拠となる事実。
3. governance (ガバナンス/資本配分): 資本配分の方針（株主還元・再投資）、役員報酬の設計、キャッシュの使い道。

出力形式:
必ず以下の構造のJSON形式で出力してください。該当する事実がない場合は null を設定してください。
{
  "capex": { "intent": string, "amount_hint": string, "timing": string, "raw_evidence": string },
  "rd": { "priority_items": string[], "technical_advantage": string, "raw_evidence": string },
  "governance": { "capital_allocation_policy": string, "shareholder_return_policy": string, "raw_evidence": string }
}
"""

    def __init__(self, api_key: str):
        self.client = genai.Client(api_key=api_key)
        self.model_name = LLM_MODEL_NAME

    async def extract_facts(self, sections: dict[str, str]) -> dict:
        """
        セクションデータから事実を構造化抽出する
        """
        # 抽出対象のテキストを結合
        combined_text = ""
        for key, text in sections.items():
            if text:
                combined_text += f"### Section: {key}\n{text}\n\n"

        if not combined_text.strip():
            logger.warning("No text content available for structuring.")
            return {}

        prompt = f"以下の開示資料から事実を抽出してください:\n\n{combined_text}"

        try:
            # flashモデルを使用して高速かつ低コストに抽出
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=prompt,
                config=types.GenerateContentConfig(
                    system_instruction=self.SYSTEM_PROMPT,
                    response_mime_type="application/json",
                ),
            )

            if response.text:
                structured_data = json.loads(response.text)
                logger.info("Successfully extracted structured facts using Gemini.")
                return structured_data
            
            return {}

        except Exception as e:
            logger.error(f"Failed to extract facts using Gemini: {e}")
            return {}
