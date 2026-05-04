import json
import re

from google import genai
from google.genai import types
from loguru import logger

from src.config import GOOGLE_AI_MODELS


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
3. governance (ガバナンス/資本配分): 資本配分の方針（株主還元・再投資）、役員報酬の設計、
   キャッシュの使い道。

出力形式:
必ず以下の構造のJSON形式で出力してください。該当する事実がない場合は null を設定してください。
{
  "capex": { "intent": string, "amount_hint": string, "timing": string, "raw_evidence": string },
  "rd": { "priority_items": string[], "technical_advantage": string, "raw_evidence": string },
  "governance": { "capital_allocation_policy": string, "shareholder_return_policy": string,
                  "raw_evidence": string }
}
"""

    def __init__(self, api_key: str):
        self.client = genai.Client(api_key=api_key)
        self.models = GOOGLE_AI_MODELS

    def _prepare_prompt(self, sections: dict[str, str]) -> str | None:
        """
        結合されたセクションデータから抽出用のプロンプトを作成する。
        """
        combined_text = ""
        for key, text in sections.items():
            if text:
                combined_text += f"### Section: {key}\n{text}\n\n"

        if not combined_text.strip():
            return None

        return f"以下の開示資料から事実を抽出してください:\n\n{combined_text}"

    def _parse_response(self, response_text: str) -> dict:
        """
        LLMからのレスポンス文字列をJSONとしてパースする。
        """
        try:
            clean_text = response_text.strip()
            # MarkdownのJSONコードブロックを検索
            json_match = re.search(r"```json\s*(.*?)\s*```", clean_text, re.DOTALL)
            if json_match:
                clean_text = json_match.group(1)
            else:
                # ``` ... ``` だけの場合も考慮
                code_match = re.search(r"```\s*(.*?)\s*```", clean_text, re.DOTALL)
                if code_match:
                    clean_text = code_match.group(1)

            return json.loads(clean_text)
        except json.JSONDecodeError:
            logger.exception(f"Failed to parse LLM response | raw_text={response_text[:500]}")
            raise ValueError(f"Invalid JSON response from LLM")
        except Exception:
            logger.exception("Unexpected error during JSON parsing")
            raise

    async def extract_facts(self, sections: dict[str, str]) -> dict:
        """
        セクションデータから事実を構造化抽出する
        """
        try:
            prompt = self._prepare_prompt(sections)
            if not prompt:
                logger.warning("No text content available for structuring")
                return {}

            for model_name in self.models:
                try:
                    logger.info(f"LLM Extraction attempt | model={model_name}")
                    response = self.client.models.generate_content(
                        model=model_name,
                        contents=prompt,
                        config=types.GenerateContentConfig(
                            system_instruction=self.SYSTEM_PROMPT,
                            response_mime_type="application/json",
                        ),
                    )

                    if response.text:
                        structured_data = self._parse_response(response.text)
                        logger.info(f"LLM Extraction successful | model={model_name}")
                        return structured_data
                    else:
                        logger.warning(f"LLM returned empty response | model={model_name}")

                except Exception:
                    logger.exception(f"Model extraction failed | model={model_name}")
                    continue

            logger.error("All models failed for extraction")
            return {}
        except Exception:
            logger.exception("Critical error in extract_facts orchestration")
            return {}
