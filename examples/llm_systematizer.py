"""
CFA LLM Systematizer — example usage
=====================================
Demonstrates NL → BehaviorSpec → Taxonomy + Rules via LLM.

Requires: pip install openai
"""

from pathlib import Path
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from cfa.behavior.llm import OpenAISystematizerBackend
from cfa.behavior import Systematizer


def main():
    description = """
    # Sales Data Pipeline Governance

    The sales ETL pipeline must:
    - Anonymize all PII (customer names, emails, phone numbers) before writing to silver
    - Enforce merge keys on all silver writes to prevent duplicates
    - Declare partition columns for datasets larger than 1GB
    - Stay within a cost budget of 100 DBU per execution
    - Validate schema contracts before writing to gold
    - Never allow raw PII in the gold layer under any circumstances
    """

    context = """
    Target is a PySpark ETL running on Databricks with Delta Lake.
    Source: bronze
    Target: silver (refined) and gold (curated)
    """

    # Create LLM backend
    backend = OpenAISystematizerBackend(
        model="gpt-4o-mini",
        temperature=0.0,
    )

    # NL → BehaviorSpec → Taxonomy + Rules
    print("Systematizing NL description...")
    taxonomy, rules = Systematizer().systematize_from_nl(
        description,
        backend=backend,
        context=context,
        target_layer="silver",
    )

    print(f"\nTaxonomy: {taxonomy.name}")
    print(f"  Allowed behaviors:    {len(taxonomy.allowed)}")
    print(f"  Not-allowed behaviors: {len(taxonomy.not_allowed)}")
    print(f"  Generated rules:       {len(rules)}")

    print("\nFailure modes:")
    for cat in taxonomy.not_allowed:
        print(f"  [{cat.severity.upper()}] {cat.code}: {cat.label}")
        print(f"    Condition: {cat.condition_type.value}")
        print(f"    Remediation: {'; '.join(cat.remediation[:2])}")

    # Generate test intents
    print("\nGenerated test intents:")
    for intent in taxonomy.generate_test_intents(3):
        print(f"  → {intent[:80]}")

    # Export taxonomy
    taxonomy_path = ROOT / "examples" / "llm_generated_taxonomy.json"
    taxonomy_path.write_text(json.dumps(taxonomy.to_dict(), indent=2))
    print(f"\nTaxonomy saved to: {taxonomy_path}")


if __name__ == "__main__":
    main()
