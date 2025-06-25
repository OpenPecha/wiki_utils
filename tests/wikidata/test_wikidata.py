from unittest import TestCase

import pytest

from wiki_utils.wikidata import WikidataClient


class TestWikidataclient(TestCase):
    def setUp(self):
        self.client = WikidataClient()

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
