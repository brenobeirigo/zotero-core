from zotero_core.bib.creators import clean, first_creator_match, parse_creators


def test_braced_corporate_author_is_one_single_field_creator():
    # The limitation the skill documented for months: this used to be split
    # into a first and last name.
    creators = parse_creators("{International Maritime Organization}")
    assert creators == [
        {
            "creatorType": "author",
            "firstName": "",
            "lastName": "International Maritime Organization",
            "fieldMode": 1,
        }
    ]


def test_last_comma_first():
    assert parse_creators("Doe, Jane") == [
        {"creatorType": "author", "firstName": "Jane", "lastName": "Doe"}
    ]


def test_first_last():
    assert parse_creators("Jane Van Doe") == [
        {"creatorType": "author", "firstName": "Jane Van", "lastName": "Doe"}
    ]


def test_single_token_is_a_surname():
    assert parse_creators("Aristotle") == [
        {"creatorType": "author", "firstName": "", "lastName": "Aristotle"}
    ]


def test_several_authors_split_on_and():
    assert len(parse_creators("Doe, Jane and Roe, Richard AND Poe, Edgar")) == 3


def test_empty_author_field():
    assert parse_creators("") == [] and parse_creators(None) == []


def test_clean_strips_braces_and_collapses_whitespace():
    assert clean("{Zurich}   Mobility\n Study") == "Zurich Mobility Study"


def test_first_creator_match_prefers_the_surname():
    assert first_creator_match("Doe, Jane and Roe, Richard") == "Doe"
    assert first_creator_match("Jane Van Doe") == "Doe"
    assert first_creator_match("{Transport Lab} and Doe, Jane") == "Transport Lab"
    assert first_creator_match("") == ""
