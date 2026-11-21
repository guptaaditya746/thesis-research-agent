"""paperfactory: a field-general benchmark builder. An invented world (field pack) is written up as papers (genre
pack, PaperOrchestra), planted facts are located, and question answering is scored against SPARQL gold."""

# Raise whenever tagging, matching or scoring rules change; written into gold.json, tagged.json and report.json so
# numbers made under different rules are never compared by mistake.
SCORING_VERSION = 2

