import json
from typing import Any, Dict, List, Optional

import pywikibot
import requests


class WikiDataSearch:
    def __init__(self):
        self.user_agent = (
            "OpenPecha/1.0 "
            "(https://github.com/OpenPecha/wikidata_pipeline; "
            "openpecha.dev@gmail.com) "
            "python-requests/2.32.3"
        )
        self.headers = {"Accept": "application/json", "User-Agent": self.user_agent}

    @staticmethod
    def login():
        """
        Logs in to Wikidata using Pywikibot.

        Returns:
        - site: Pywikibot Site object for Wikidata.
        """
        site = pywikibot.Site("wikidata", "wikidata")
        site.login()  # Log into Wikidata
        print(f"Logged in to Wikidata as {site.username()}")
        return site

    def get_qid(self, work_id: str) -> Optional[str]:
        """
        Returns the Wikidata QID for a given BDRC work_id.
        If not found, returns None.
        """
        query = f"""
        SELECT ?item WHERE {{
        ?item wdt:P2477 \"{work_id}\" .   #noqa
        }}     #noqa
        """
        url = "https://query.wikidata.org/sparql"

        try:
            response = requests.get(
                url, params={"query": query}, headers=self.headers, timeout=10
            )
            response.raise_for_status()
            data = response.json()
            results = data.get("results", {}).get("bindings", [])
            if results:
                return results[0]["item"]["value"].split("/")[-1]
            else:
                print(f"No Wikidata QID found for BDRC work_id: {work_id}")
        except Exception as e:
            print(f"Error fetching QID for {work_id}: {e}")
        return None

    def get_wikidata_entity(self, qid: str) -> Optional[Dict[str, Any]]:
        """
        Returns the Wikidata entity data for a given QID.
        If not found, returns None.
        """
        url = f"https://www.wikidata.org/wiki/Special:EntityData/{qid}.json"  # noqa

        try:
            response = requests.get(url, headers=self.headers, timeout=10)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"Error fetching Wikidata entity for QID {qid}: {e}")
            return None

    def get_wikidata_metadata(
        self, work_id: str, language: str = "en", properties: Optional[List[str]] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Combines the above functions to return useful metadata for a BDRC work_id.
        Returns None if not found or on error.
        """
        qid = self.get_qid(work_id)
        if not qid:
            print(f"No QID found for work_id: {work_id}")
            return None
        entity = self.get_wikidata_entity(qid)
        if not entity:
            print(f"No Wikidata entity found for QID: {qid}")
            return None
        return self.extract_useful_fields_from_entity(entity, qid, language, properties)

    def extract_useful_fields_from_entity(
        self,
        entity_json: Dict[str, Any],
        qid: str,
        language: str = "en",
        properties: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Extracts label, description, aliases, and specified property values from Wikidata entity JSON.
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
            # Extract specified properties if provided
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
                            # For entity references, extract the QID
                            if isinstance(value, dict) and "id" in value:
                                prop_values.append(value["id"])
                            else:
                                prop_values.append(value)
                    result["properties"][prop] = prop_values
            return result
        except Exception as e:
            print(f"Error extracting fields from entity for QID {qid}: {e}")
            return {"qid": qid, "label": "", "description": "", "aliases": []}


if __name__ == "__main__":
    wiki_data = WikiDataSearch()

    work_id = "WA0RK0529"
    metadata = wiki_data.get_wikidata_metadata(
        work_id, language="en", properties=["P31", "P4969", "P1476"]
    )
    print(json.dumps(metadata, indent=2, ensure_ascii=False))
    author_id = "P1215"
    author_metadata = wiki_data.get_wikidata_metadata(
        author_id, language="en", properties=["P31", "P4969", "P1476"]
    )
    print(json.dumps(author_metadata, indent=2, ensure_ascii=False))
