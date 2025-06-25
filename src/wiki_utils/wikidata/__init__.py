from typing import Any, Dict, List, Optional

import pywikibot
import requests

from wiki_utils.utils.logger import get_logger

logger = get_logger(__name__)


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

        self.property_id_to_name = {
            "P373": "commons_category_link",
            "P646": "freebase_id",
            "P31": "instance_of",
            "P435": "musicbrainz_work_id",
            "P3417": "quora_topic_id",
            "P1476": "title",
            "P1417": "encyclopaedia_britannica_online_id",
            "P747": "has_edition",
            "P2581": "babelnet_id",
            "P18": "image",
            "P8885": "un_locode",
            "P10": "video",
            "P10565": "encyclopedia_of_life_id",
            "P2671": "google_knowledge_graph_id",
            "P349": "ndl_authority_id",
            "P214": "viaf_id",
            "P11196": "euvat_id",
            "P9475": "whos_who_in_france_id",
            "P6900": "alexa_skill_id",
            "P11408": "swiss_parliament_id",
            "P279": "subclass_of",
            "P921": "main_subject",
            "P2477": "sbn_author_id",
            "P4969": "derivative_work",
            "P989": "spoken_text_audio",
            "P6262": "fandom_article_id",
        }

    @staticmethod
    def login_to_wikidata() -> pywikibot.Site:
        """
        Log in to Wikidata using Pywikibot and return the site object.
        """
        site = pywikibot.Site("wikidata", "wikidata")
        site.login()
        logger.info(f"Logged in to Wikidata as {site.username()}")
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
                logger.warning(
                    f"No Wikidata QID found for BDRC work_id: {bdrc_work_id}"
                )
        except Exception as e:
            logger.error(f"Error fetching QID for {bdrc_work_id}: {e}")
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
            data = response.json()
            entity = data["entities"][qid]
            return entity
        except Exception as e:
            logger.error(f"Error fetching Wikidata entity for QID {qid}: {e}")
            return None

    def fetch_entity_by_bdrc_work_id(
        self, bdrc_work_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Retrieve useful metadata for a BDRC work ID, including label, description, aliases, and specified properties.
        Returns None if not found or on error.
        """
        qid = self.get_qid_by_bdrc_work_id(bdrc_work_id)
        if not qid:
            logger.warning(f"No QID found for work_id: {bdrc_work_id}")
            return None
        entity = self.fetch_entity_by_qid(qid)
        if not entity:
            logger.warning(f"No Wikidata entity found for QID: {qid}")
            return None
        return entity

    def extract_entity_metadata(
        self,
        entity: Dict,
        language: str = "en",
    ) -> Dict[str, Any]:
        """
        Extract label, description, aliases, and specified property values from Wikidata entity JSON.
        Handles missing fields gracefully.
        """
        try:
            label = entity.get("labels", {}).get(language, {}).get("value", "")
            description = (
                entity.get("descriptions", {}).get(language, {}).get("value", "")
            )
            aliases = [a["value"] for a in entity.get("aliases", {}).get(language, [])]
            result = {
                "label": label,
                "description": description,
                "aliases": aliases,
            }

            result["properties"] = {}
            claims = entity.get("claims", {})
            for property_id in self.property_id_to_name.keys():
                prop_values = []
                if property_id in claims:
                    for claim in claims[property_id]:
                        mainsnak = claim.get("mainsnak", {})
                        datavalue = mainsnak.get("datavalue", {})
                        value = datavalue.get("value")
                        if isinstance(value, dict) and "id" in value:
                            prop_values.append(value["id"])
                        else:
                            prop_values.append(value)
                property_name = self.property_id_to_name[property_id]
                result["properties"][property_name] = prop_values

            return result
        except Exception as e:
            logger.error(
                f"Error extracting fields from entity for QID {entity['id']}: {e}"
            )
            return {"qid": entity["id"], "label": "", "description": "", "aliases": []}

    def search_entities(
        self, search_text: str, language: str = "en", limit: int = 50
    ) -> List[Dict[str, Any]]:
        """
        Search for entities in Wikidata matching the given search_text.

        :param search_text: The text to search for.
        :param language: Language to search in (e.g., 'en', 'bo').
        :param limit: Maximum number of results (max 50).
        :return: A list of matching entities with basic metadata.
        """
        search_url = "https://www.wikidata.org/w/api.php"
        search_params = {
            "action": "wbsearchentities",
            "format": "json",
            "language": language,
            "search": search_text,
            "limit": str(limit),
        }
        try:
            response = requests.get(
                search_url, params=search_params, headers=self.headers, timeout=10
            )
            response.raise_for_status()
            data = response.json()
            return data.get("search", [])
        except Exception as e:
            logger.error(f"Error searching Wikidata for '{search_text}': {e}")
            return []
