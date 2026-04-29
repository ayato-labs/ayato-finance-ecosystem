import logging

from src.mappers.ai_mapper import AIMapper

logging.basicConfig(level=logging.INFO)


def test_growth_mapping():
    # Proposed new labels (just for display in results, AI prompt is dynamic)
    # Note: In production, we would add these to settings.TARGET_LABELS

    mapper = AIMapper()

    # map_tags_batch(self, market, tags: List[tuple], model_name, session_id)
    # tags: List of (tag_name, label/description)

    us_test_tags = [
        ("ResearchAndDevelopmentExpense", "Research and Development Expense"),
        ("PropertyPlantAndEquipmentAdditions", "Property, Plant and Equipment, Additions"),
        (
            "PaymentsToAcquirePropertyPlantAndEquipment",
            "Payments to Acquire Property, Plant and Equipment",
        ),
        ("SellingGeneralAndAdministrativeExpense", "Selling, General and Administrative Expense"),
    ]

    # The current mapper uses the production config labels.
    # For this experiment, I'll temporarily patch the mapper's target labels to include growth items.
    # This is safe because it's in memory.
    from src.core.config import settings

    growth_labels = settings.TARGET_LABELS + ["ResearchAndDevelopment", "CapitalExpenditure"]

    print("\n>>> Testing AI Mapping for GROWTH INVESTMENTS (US)...")
    # map_tags_batch expects (market, tags, model_name, session_id)
    model = settings.LIGHT_GOOGLE_AI_MODELS[0]

    # We need to hack the mapper to use growth_labels for this test
    original_get_instruction = mapper._get_system_instruction
    mapper._get_system_instruction = lambda: (
        f"Target Labels: {growth_labels}\n" + original_get_instruction()
    )

    results_us = mapper.map_tags_batch("US", us_test_tags, model, session_id="test-growth")

    for i, mapping in enumerate(results_us):
        tag_name = us_test_tags[i][0]
        print(f"Tag: {tag_name} -> Label: {mapping['mapped_label']}")
        print(f"Reason: {mapping['reasoning']}\n")

    jp_test_tags = [
        ("ResearchAndDevelopmentExpenses", "研究開発費"),
        ("CFI", "Investing Cash Flow"),
    ]

    print("\n>>> Testing AI Mapping for GROWTH INVESTMENTS (JP)...")
    results_jp = mapper.map_tags_batch("JP", jp_test_tags, model, session_id="test-growth-jp")
    for i, mapping in enumerate(results_jp):
        tag_name = jp_test_tags[i][0]
        print(f"Tag: {tag_name} -> Label: {mapping['mapped_label']}")
        print(f"Reason: {mapping['reasoning']}\n")


if __name__ == "__main__":
    test_growth_mapping()
