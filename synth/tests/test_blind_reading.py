"""A lower-is-better metric still uses literal signed source arithmetic."""
import pytest
from pydantic import ValidationError
from agent import anchor

from synth.blind_reading import DirectReading, ReadingReply, RelativeReading, resolve


@pytest.mark.parametrize("direction,expected", [("higher", 0.402), ("lower", 0.268)])
def test_literal_percentage_point_arithmetic(direction, expected):
    base = "On HistoryQuest, closed-book model has 33.5% unsupported-answer rate."
    relative = (f"On HistoryQuest, RAG pipeline scores 6.7 percentage points {direction} "
                "than closed-book model in unsupported-answer rate.")
    reply = ReadingReply(direct=[DirectReading(condition="closed-book model", metric="unsupported-answer rate",
                         dataset="HistoryQuest", number="33.5", unit="percent", quote=base)],
                         relative=[RelativeReading(condition="RAG pipeline", metric="unsupported-answer rate",
                                   dataset="HistoryQuest", reference_condition="closed-book model",
                                   points="6.7", direction=direction, quote=relative)])
    assert resolve(base + "\n" + relative, reply).measurements[-1].value == expected
    reply.relative[0].direction = "lower" if direction == "higher" else "higher"
    with pytest.raises(ValueError, match="direction"):
        resolve(base + "\n" + relative, reply)


def test_invented_number_rejected():
    quote = "System A scores 16.7%."
    row = DirectReading(condition="A", metric="accuracy", dataset="D", number="6.7", unit="percent", quote=quote)
    with pytest.raises(ValueError, match="does not contain"):
        resolve(quote, ReadingReply(direct=[row]))


def test_count_normalization_and_quote_anchoring():
    quote = "System A has 624 out of 1,000 correct answers."
    row = DirectReading(condition="A", metric="accuracy", dataset="D", number="624", unit="count",
                        denominator="1,000", quote=quote)
    assert resolve(quote, ReadingReply(direct=[row])).measurements[0].value == 0.624
    row.quote = "Invented source text has 624 out of 1,000 answers."
    with pytest.raises(anchor.AnchorError):
        resolve(quote, ReadingReply(direct=[row]))


def test_see_text_is_not_a_numeric_measurement():
    with pytest.raises(ValidationError):
        DirectReading(condition="A", metric="accuracy", dataset="D", number="see text",
                      unit="percent", quote="| A | see text |")
