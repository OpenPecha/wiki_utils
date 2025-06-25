from pathlib import Path
from unittest import TestCase

from wiki_utils.utils import read_json
from wiki_utils.wikidata import WikidataClient


class TestWikidataclient(TestCase):
    def setUp(self):
        self.client = WikidataClient()

        data_dir = Path(__file__).parent / "data"
        self.entity_metadata = read_json(data_dir / "entity_metadata.json")
        self.expected_parsed_entity_metadata = read_json(
            data_dir / "parsed_entity_metadata.json"
        )

    def test_get_id(self):
        # Heart Sutra
        qid = self.client.get_qid_by_bdrc_work_id("WA0RK0529")
        assert qid == "Q622868"

        # Pendrub Zangpo Tashi (author)
        qid = self.client.get_qid_by_bdrc_work_id("P1215")
        assert qid == "Q106795280"

        # Likely no QID for this collection
        qid = self.client.get_qid_by_bdrc_work_id("PR0EAP570")
        assert qid == None

        # Definitely does not exist
        qid = self.client.get_qid_by_bdrc_work_id("NONEXISTENTID")
        assert qid == None

    def test_parse_entity_metadata(self):
        parsed_entity_metadata = self.client.parse_entity_metadata(self.entity_metadata)
        assert parsed_entity_metadata == self.expected_parsed_entity_metadata
