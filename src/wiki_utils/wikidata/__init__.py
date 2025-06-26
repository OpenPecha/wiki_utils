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
            "P1476": "title",
            "P50": "author",
            "P655": "translator",
            "P373": "commons_category_link",
            "P31": "instance_of",
            "P279": "subclass_of",
            "P747": "has_edition",
            "P4969": "derivative_work",
            "P136": "genre",
            "P921": "main_subject",
            "P1343": "described_by_source",
            "P2888": "exact_match",
            "P407": "language_of_work",
            "P18": "image",
            "P10": "video",
            "P2671": "google_knowledge_graph_id",
            "P2477": "sbn_author_id",
            "P989": "spoken_text_audio",
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
        Get Wiki Data qid for a given BDRC work id
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

    def get_entity_metadata_by_qid(self, qid: str) -> Optional[Dict[str, Any]]:
        """
        Get Wiki Data Entity metadata for a given qid
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

    def get_entity_metadata_by_bdrc_work_id(
        self, bdrc_work_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Get Wiki Data Entity metadata for a given BDRC work id.
        """
        qid = self.get_qid_by_bdrc_work_id(bdrc_work_id)
        if qid is None:
            logger.warning(f"No QID found for BDRC work ID: {bdrc_work_id}")
            return None

        entity_metadata = self.get_entity_metadata_by_qid(qid)
        if entity_metadata is None:
            logger.warning(f"No Wikidata entity found for QID: {qid}")
            return None

        return entity_metadata

    def _parse_labels(self, metadata: Dict[str, Any]) -> Dict[str, str]:
        return {
            lang: label["value"] for lang, label in metadata.get("labels", {}).items()
        }

    def _parse_descriptions(self, metadata: Dict[str, Any]) -> Dict[str, str]:
        return {
            lang: desc["value"]
            for lang, desc in metadata.get("descriptions", {}).items()
        }

    def _parse_aliases(self, metadata: Dict[str, Any]) -> Dict[str, List[str]]:
        return {
            lang: [alias["value"] for alias in aliases]
            for lang, aliases in metadata.get("aliases", {}).items()
        }

    def _extract_property_values(
        self, properties_metadata: Dict[str, Any], property_id: str
    ) -> List[Any]:
        """
        Imp Notes:
            'claims' aka 'statements' is a structure in which properties information are stored in Wiki Data.
            The mainsnak is the core part of a statement: it holds the main property and its value for that statement
        """
        prop_values = []
        for property_metadata in properties_metadata.get(property_id, []):
            mainsnak = property_metadata.get("mainsnak", {})
            datavalue = mainsnak.get("datavalue", {})
            value = datavalue.get("value")
            if isinstance(value, dict) and "id" in value:
                prop_values.append(value["id"])
            else:
                prop_values.append(value)
        return prop_values

    def parse_entity_metadata(self, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """
        Parse useful metadata from entity metadata.
        Fields including label, description, aliases, and other properties defined in the constructor.

        Imp Note: 'claims' aka 'statements' is a structure in which properties information are stored in Wiki Data.
        """
        try:
            labels = self._parse_labels(metadata)
            descriptions = self._parse_descriptions(metadata)
            aliases = self._parse_aliases(metadata)

            parsed_metadata = {
                "qid": metadata.get("id", ""),
                "labels": labels,
                "descriptions": descriptions,
                "aliases": aliases,
            }

            properties_metadata = metadata.get("claims", {})
            for property_id, property_name in self.property_id_to_name.items():
                parsed_metadata[property_name] = self._extract_property_values(
                    properties_metadata, property_id
                )

            return parsed_metadata
        except Exception as e:
            logger.error(
                f"Error extracting fields from entity for QID {metadata.get('id', 'unknown')}: {e}"
            )
            return {
                "qid": metadata.get("id", ""),
                "labels": {},
                "descriptions": {},
                "aliases": {},
            }

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

    def walk(self, qid: str, _visited=None, _edges=None):
        """
        Recursively walk through 'has_edition' and 'derivative_work' relationships,
        storing only the QID pairs and their relationship type.
        Returns a list of dicts: { 'from': ..., 'to': ..., 'relationship': ... }
        """
        if _visited is None:
            _visited = set()
        if _edges is None:
            _edges = []
        if qid in _visited:
            return _edges
        _visited.add(qid)

        entity_metadata = self.get_entity_metadata_by_qid(qid)
        if not entity_metadata:
            return _edges
        parsed_metadata = self.parse_entity_metadata(entity_metadata)

        # Process 'has_edition' relationships
        for edition_qid in parsed_metadata.get("has_edition", []):
            if (
                edition_qid
                and isinstance(edition_qid, str)
                and edition_qid.startswith("Q")
            ):
                _edges.append(
                    {"from": qid, "to": edition_qid, "relationship": "has_edition"}
                )
                self.walk(edition_qid, _visited, _edges)

        # Process 'derivative_work' relationships
        for derivative_qid in parsed_metadata.get("derivative_work", []):
            if (
                derivative_qid
                and isinstance(derivative_qid, str)
                and derivative_qid.startswith("Q")
            ):
                _edges.append(
                    {
                        "from": qid,
                        "to": derivative_qid,
                        "relationship": "derivative_work",
                    }
                )
                self.walk(derivative_qid, _visited, _edges)

        return _edges
