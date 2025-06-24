import json
import logging
from typing import Any, Dict, List, Optional

import pywikibot
import requests


class WikidataClient:
    def __init__(
        self,
        sparql_url: str = "https://query.wikidata.org/sparql",
        entity_url: str = "https://www.wikidata.org/wiki/Special:EntityData",
    ):
        self.sparql_url = sparql_url
        self.entity_url = entity_url
        self.user_agent = (
            "OpenPecha/1.0 "
            "(https://github.com/OpenPecha/wikidata_pipeline; "
            "openpecha.dev@gmail.com) "
            "python-requests/2.32.3"
        )
        self.headers = {"Accept": "application/json", "User-Agent": self.user_agent}
        logging.basicConfig(level=logging.INFO)

    @staticmethod
    def login_to_wikidata() -> pywikibot.Site:
        """
        Log in to Wikidata using Pywikibot and return the site object.
        """
        site = pywikibot.Site("wikidata", "wikidata")
        site.login()
        logging.info(f"Logged in to Wikidata as {site.username()}")
        return site

    def get_qid_by_bdrc_work_id(self, bdrc_work_id: str) -> Optional[str]:
        """
        Retrieve the Wikidata QID for a given BDRC work ID.
        Returns None if not found or on error.
        """
        query = f"""
        SELECT ?item WHERE {{
        ?item wdt:P2477 \"{bdrc_work_id}\" .
        }}
        """
        try:
            response = requests.get(
                self.sparql_url,
                params={"query": query},
                headers=self.headers,
                timeout=10,
            )
            response.raise_for_status()
            data = response.json()
            results = data.get("results", {}).get("bindings", [])
            if results:
                return results[0]["item"]["value"].split("/")[-1]
            else:
                logging.warning(
                    f"No Wikidata QID found for BDRC work_id: {bdrc_work_id}"
                )
        except Exception as e:
            logging.error(f"Error fetching QID for {bdrc_work_id}: {e}")
        return None

    def fetch_entity_by_qid(self, qid: str) -> Optional[Dict[str, Any]]:
        """
        Fetch the Wikidata entity data for a given QID.
        Returns None if not found or on error.
        """
        url = f"{self.entity_url}/{qid}.json"
        try:
            response = requests.get(url, headers=self.headers, timeout=10)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logging.error(f"Error fetching Wikidata entity for QID {qid}: {e}")
            return None

    def get_entity_metadata_by_bdrc_work_id(
        self,
        bdrc_work_id: str,
        language: str = "en",
        properties: Optional[List[str]] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Retrieve useful metadata for a BDRC work ID, including label, description, aliases, and specified properties.
        Returns None if not found or on error.
        """
        qid = self.get_qid_by_bdrc_work_id(bdrc_work_id)
        if not qid:
            logging.warning(f"No QID found for work_id: {bdrc_work_id}")
            return None
        entity = self.fetch_entity_by_qid(qid)
        if not entity:
            logging.warning(f"No Wikidata entity found for QID: {qid}")
            return None
        return self.extract_entity_metadata(entity, qid, language, properties)

    def extract_entity_metadata(
        self,
        entity_json: Dict[str, Any],
        qid: str,
        language: str = "en",
        properties: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Extract label, description, aliases, and specified property values from Wikidata entity JSON.
        Handles missing fields gracefully.
        """
        try:
            entity = entity_json["entities"][qid]
            label = entity.get("labels", {}).get(language, {}).get("value", "")
            description = (
                entity.get("descriptions", {}).get(language, {}).get("value", "")
            )
            aliases = [a["value"] for a in entity.get("aliases", {}).get(language, [])]
            result = {
                "qid": qid,
                "label": label,
                "description": description,
                "aliases": aliases,
            }
            if properties:
                result["properties"] = {}
                claims = entity.get("claims", {})
                for prop in properties:
                    prop_values = []
                    if prop in claims:
                        for claim in claims[prop]:
                            mainsnak = claim.get("mainsnak", {})
                            datavalue = mainsnak.get("datavalue", {})
                            value = datavalue.get("value")
                            if isinstance(value, dict) and "id" in value:
                                prop_values.append(value["id"])
                            else:
                                prop_values.append(value)
                    result["properties"][prop] = prop_values
            return result
        except Exception as e:
            logging.error(f"Error extracting fields from entity for QID {qid}: {e}")
            return {"qid": qid, "label": "", "description": "", "aliases": []}


if __name__ == "__main__":
    wikidata_client = WikidataClient()

    work_id = "WA0RK0529"
    metadata = wikidata_client.get_entity_metadata_by_bdrc_work_id(
        work_id, language="en", properties=["P31", "P4969", "P1476"]
    )
    print(json.dumps(metadata, indent=2, ensure_ascii=False))

    author_id = "P1215"
    author_metadata = wikidata_client.get_entity_metadata_by_bdrc_work_id(
        author_id, language="en", properties=["P31", "P4969", "P1476"]
    )
    print(json.dumps(author_metadata, indent=2, ensure_ascii=False))
