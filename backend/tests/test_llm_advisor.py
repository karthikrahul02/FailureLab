from app.services.llm_advisor import parse_advisory_json


def test_parse_plain_advisory_json():
    result = parse_advisory_json(
        '{"summary":"Database pressure observed","findings":["Latency increased"],'
        '"recommendations":["Use bounded connection pools"]}'
    )
    assert result == {
        "summary": "Database pressure observed",
        "findings": ["Latency increased"],
        "recommendations": ["Use bounded connection pools"],
    }


def test_parse_advisory_json_with_fence_and_surrounding_text():
    result = parse_advisory_json(
        'Analysis:\n```json\n{"summary":"Observed","findings":["One"],'
        '"recommendations":["Two"]}\n```'
    )
    assert result is not None
    assert result["summary"] == "Observed"


def test_reject_invalid_or_incomplete_advisory():
    assert parse_advisory_json("not JSON") is None
    assert parse_advisory_json('{"summary":"x","findings":[],"recommendations":["y"]}') is None
    assert parse_advisory_json('{"summary":3,"findings":["x"],"recommendations":["y"]}') is None


def test_advisory_output_is_bounded_and_non_string_items_are_ignored():
    result = parse_advisory_json(
        '{"summary":"s" * 1000,"findings":["valid",4,"also valid"],'
        '"recommendations":["recommend"]}'
    )
    # The intentionally invalid expression-like string above must be rejected.
    assert result is None

    payload = '{"summary":"' + ('s' * 1000) + '","findings":["' + ('f' * 400) + '",4],' \
        '"recommendations":["' + ('r' * 400) + '"]}'
    bounded = parse_advisory_json(payload)
    assert bounded is not None
    assert len(bounded["summary"]) == 900
    assert len(bounded["findings"][0]) == 320
    assert len(bounded["recommendations"][0]) == 320
