import pytest

from wiki_utils.wikidata import WikidataClient

# These are real BDRC IDs and their expected QIDs as of May 2025.
# If Wikidata changes, these tests may need updating.


@pytest.mark.parametrize(
    "work_id,expected_qid",
    [
        ("WA0RK0529", "Q622868"),  # Heart Sutra
        ("P1215", "Q106795280"),  # Pendrub Zangpo Tashi (author)
        ("PR0EAP570", None),  # Likely no QID for this collection
        ("NONEXISTENTID", None),  # Definitely does not exist
    ],
)
def test_get_qid(work_id, expected_qid):
    result = WikidataClient().get_qid_by_bdrc_work_id(work_id)
    assert result == expected_qid
