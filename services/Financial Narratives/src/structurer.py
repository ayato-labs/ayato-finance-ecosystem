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

    SYSTEM_PROMPT_MAPPING = """
    あなたは高度な金融データエンジニアです。
    提供された EDINET XBRL のタグ名リストから、以下の 6 つのカテゴリのいずれかに関連する可能性
    があるタグを特定してください。

    カテゴリ:
    1. capex: 設備投資、主要な設備の状況、投資計画
    2. rd: 研究開発活動、技術開発、知的財産
    3. governance: コーポレート・ガバナンスの状況、資本配分の方針、株主還元、取締役会
    4. employees: 従業員の状況、平均給与、勤続年数、セグメント別従業員数
    5. compensation: 役員報酬の内容、設計、個別の報酬、インセンティブ
    6. cross_shareholding: 政策保有株式、持ち合い株、投資株式の保有目的

    出力ルール:
    - 以下の構造の JSON 形式のみで回答してください。
    - "thinking" フィールドに、どのタグがなぜ重要かの推論過程を記述してください。
    {
    "thinking": "推論過程...",
    "capex": ["tag_name1", "tag_name2", ...],
    "rd": [...],
    "governance": [...],
    "employees": [...],
    "compensation": [...],
    "cross_shareholding": [...]
    }
    """

    SYSTEM_PROMPT_STRUCTURING = """
    あなたは高度な金融専門アナリストです。提供された開示資料の断片（Markdown）から、特定の項目について「事実」のみを構造化抽出してください。

    抽出項目と目的:
    - capex: 将来の投資計画、具体的な投資金額や時期。
    - rd: 重点研究項目、技術的優位性の根拠。
    - governance: 資本配分方針、還元方針、ガバナンス体制。
    - employees: 給与、勤続年数、人員構成の事実。
    - compensation: 報酬設計のロジック、選任理由、個別報酬額（記載がある場合）。
    - cross_shareholding: 銘柄別の保有目的、削減方針の有無。

    ルール:
    - 主観的な解釈は含めない。
    - 該当する記述がない項目は null とする。
    - 各項目の "raw_evidence" には、抽出の根拠となった原文の該当箇所を短く引用する。
    - 以下の構造の JSON 形式のみで回答してください。
    - "thinking" フィールドに、情報の欠落がないかの注意深い推論過程を記述してください。
    {
    "thinking": "推論過程...",
    "capex": {"facts": "...", "raw_evidence": "..."},
    ...
    }
    """

    def __init__(self, api_key: str, model_name: str | None = None):
        self.client = genai.Client(api_key=api_key)
        self.model_name = model_name
        self.models = GOOGLE_AI_MODELS

    def _parse_json(self, text: str) -> dict:
        """
        LLMの出力からJSONをパースする。JSONモード時は通常そのままパース可能。
        """
        if not text:
            return {}
        
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            # フォールバック: マークダウンブロックや余計なテキストが含まれている場合
            try:
                match = re.search(r"\{.*\}", text, re.DOTALL)
                if match:
                    return json.loads(match.group(0))
            except Exception:
                pass
            
            logger.warning(f"Failed to parse JSON even with JSON mode: {text[:200]}...")
            return {}

    async def _identify_tags(self, tag_names: list[str]) -> dict:
        """
        全タグ名から関連するタグをLLMに特定させる（第1段階）
        """
        if not tag_names:
            return {}

        # SEC documents (US market) typically store the entire MD&A in a single 'full_content' key.
        if len(tag_names) == 1 and tag_names[0] == "full_content":
            return {
                "capex": ["full_content"],
                "rd": ["full_content"],
                "governance": ["full_content"],
                "employees": ["full_content"],
                "compensation": ["full_content"],
                "cross_shareholding": ["full_content"]
            }

        tag_list_str = "\n".join(tag_names)
        prompt = f"""以下のタグ名リストを分析し、各カテゴリに関連するタグ名を選択してください。
        
        タグ名リスト:
        {tag_list_str}
        """

        # スキーマ定義
        schema = {
            "type": "OBJECT",
            "properties": {
                "thinking": {"type": "STRING", "description": "推論過程"},
                "capex": {"type": "ARRAY", "items": {"type": "STRING"}},
                "rd": {"type": "ARRAY", "items": {"type": "STRING"}},
                "governance": {"type": "ARRAY", "items": {"type": "STRING"}},
                "employees": {"type": "ARRAY", "items": {"type": "STRING"}},
                "compensation": {"type": "ARRAY", "items": {"type": "STRING"}},
                "cross_shareholding": {"type": "ARRAY", "items": {"type": "STRING"}}
            },
            "required": ["thinking", "capex", "rd", "governance", "employees", "compensation", "cross_shareholding"]
        }

        models_to_try = [self.model_name] if self.model_name else self.models

        for model_name in models_to_try:
            try:
                logger.info(f"Identifying tags using {model_name}...")
                response = self.client.models.generate_content(
                    model=model_name,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        system_instruction=self.SYSTEM_PROMPT_MAPPING,
                        response_mime_type="application/json",
                        response_schema=schema
                    ),
                )
                if response.text:
                    return self._parse_json(response.text)
            except Exception as e:
                logger.error(f"Tag mapping failed with {model_name}: {e}")
                continue
        return {}

    async def extract_facts(self, sections: dict[str, str]) -> dict:
        """
        2段階のプロセスで事実を構造化抽出する
        """
        try:
            tag_names = list(sections.keys())
            mapping = await self._identify_tags(tag_names)

            if not mapping:
                logger.warning("No tag mapping generated")
                return {}

            logger.info(f"Generated Mapping: {json.dumps(mapping, ensure_ascii=False)}")

            context_per_category = {}
            for category, mapped_tags in mapping.items():
                if category == "thinking":
                    continue
                combined_text = ""
                for tag in mapped_tags:
                    if sections.get(tag):
                        combined_text += f"--- Tag: {tag} ---\n{sections[tag]}\n\n"
                if combined_text.strip():
                    context_per_category[category] = combined_text

            if not context_per_category:
                logger.warning("No relevant content found after mapping")
                return {}

            final_prompt_parts = []
            for cat, text in context_per_category.items():
                final_prompt_parts.append(f"## Category: {cat}\n{text}")

            final_prompt = "以下の情報を分析し、各項目の事実を抽出してください:\n\n" + "\n\n".join(final_prompt_parts)

            # 詳細構造化のスキーマ
            fact_item_schema = {
                "type": "OBJECT",
                "properties": {
                    "facts": {"type": "STRING", "description": "抽出された事実内容。該当なしは空文字"},
                    "raw_evidence": {"type": "STRING", "description": "根拠となった原文の引用。該当なしは空文字"}
                },
                "required": ["facts", "raw_evidence"]
            }
            
            schema = {
                "type": "OBJECT",
                "properties": {
                    "thinking": {"type": "STRING", "description": "情報の欠落がないかの注意深い推論過程"},
                    "capex": fact_item_schema,
                    "rd": fact_item_schema,
                    "governance": fact_item_schema,
                    "employees": fact_item_schema,
                    "compensation": fact_item_schema,
                    "cross_shareholding": fact_item_schema
                },
                "required": ["thinking", "capex", "rd", "governance", "employees", "compensation", "cross_shareholding"]
            }

            models_to_try = [self.model_name] if self.model_name else self.models

            for model_name in models_to_try:
                try:
                    logger.info(f"Structuring facts using {model_name}...")
                    response = self.client.models.generate_content(
                        model=model_name,
                        contents=final_prompt,
                        config=types.GenerateContentConfig(
                            system_instruction=self.SYSTEM_PROMPT_STRUCTURING,
                            response_mime_type="application/json",
                            response_schema=schema
                        ),
                    )
                    if response.text:
                        return self._parse_json(response.text)
                except Exception as e:
                    logger.error(f"Structuring failed with {model_name}: {e}")
                    continue

            return {}
        except Exception as e:
            logger.exception(f"Critical error in extract_facts: {e}")
            return {}
