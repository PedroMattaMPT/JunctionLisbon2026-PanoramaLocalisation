"""Tests for panoloc.names, tools/build_name_index.py and tools/build_osm_index.py. Run from the repo root:
.venv/bin/python -m unittest discover -s tests (the OSM tests are skipped without pyosmium)

A tiny index is built from synthetic files in the real formats (Wikidata CSV, GeoNames places and
postcodes, and a hand-written .osm file for the OSM index), so the tests never read the downloaded
data. Names and coordinates are invented or generic, chosen without looking at the warm-up panoramas
or their locations.
"""
import csv
import gzip
import importlib.util
import json
import os
import tempfile
import unittest
from pathlib import Path

from panoloc.names import (NameIndex, edit_distance, expand_abbreviations, keys, normalise, osm_postcode_share,
                           parse_postcode)
from panoloc.scoring import haversine_m

TOOLS = Path(__file__).resolve().parent.parent / "tools"
spec = importlib.util.spec_from_file_location("build_name_index", TOOLS / "build_name_index.py")
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)

LANGS = ("pt", "es", "fr", "en", "ca", "gl", "eu", "mul")
COLUMNS = (["qid", "country", "lat", "lon", "n_coords", "other_coords", "types", "type_labels_en"]
           + [f"label_{lang}" for lang in LANGS] + [f"aliases_{lang}" for lang in LANGS]
           + ["image", "sitelinks", "heritage", "heritage_labels_en", "located_in"])
WIKIDATA = [
    dict(qid="Q1", country="PT", lat="38.691600", lon="-9.215900", types="Q81917|Q1785071",
         type_labels_en="fortified tower|fort", label_pt="Torre de Belém", label_en="Belém Tower",
         aliases_en="Tower of Belém", sitelinks="57", heritage="Q908411",
         heritage_labels_en="National Monument of Portugal", image="Torre.jpg"),
    dict(qid="Q2", country="PT", lat="39.400000", lon="-9.100000", types="Q1131296",
         type_labels_en="freguesia of Portugal", label_pt="Santa Maria", sitelinks="3"),
    dict(qid="Q3", country="ES", lat="42.000000", lon="-3.000000", types="Q2074737",
         type_labels_en="municipality of Spain", label_es="Santa María", sitelinks="10"),
    dict(qid="Q4", country="FR", lat="48.636100", lon="-1.511500", types="Q484170",
         type_labels_en="commune of France", label_fr="Le Mont-Saint-Michel", aliases_fr="Mont-Saint-Michel",
         sitelinks="80"),
    dict(qid="Q5", country="PT", lat="40.000000", lon="-8.000000", types="Q16970", type_labels_en="church building",
         label_pt="Igreja Matriz", sitelinks="0"),
    dict(qid="Q6", country="ES", lat="41.403600", lon="2.174400", types="Q120560", type_labels_en="minor basilica",
         label_es="Sagrada Familia", label_ca="Sagrada Família",
         aliases_es="Templo Expiatorio de la Sagrada Familia", sitelinks="109"),
    dict(qid="Q7", country="ES|FR", lat="42.800000", lon="0.500000", types="Q8502", type_labels_en="mountain",
         label_es="Pico Fronterizo", label_fr="Pic Frontalier", sitelinks="2"),
    dict(qid="Q8", country="PT", lat="39.361900", lon="-9.157100", types="Q13217644",
         type_labels_en="municipality of Portugal", label_pt="Óbidos", sitelinks="49"),
    dict(qid="Q9", country="PT", lat="41.170000", lon="-8.680000", types="Q22698", type_labels_en="park",
         label_pt="Parque da Cidade", sitelinks="5"),
    dict(qid="Q10", country="PT", lat="39.600000", lon="-8.800000", types="Q178561", type_labels_en="battle",
         label_pt="Batalha de Teste", sitelinks="9"),
    dict(qid="Q11", country="PT", lat="abc", lon="-8.000000", label_pt="Sem Coordenadas"),
    dict(qid="X12", country="PT", lat="40.000000", lon="-8.000000", label_pt="Identificador Errado"),
    dict(qid="Q13", country="PT", lat="38.697900", lon="-9.206800", types="Q44613", type_labels_en="monastery",
         label_pt="Mosteiro dos Jerónimos", sitelinks="53"),
    dict(qid="Q14", country="PT", lat="40.200000", lon="-8.400000", n_coords="2", other_coords="40.218000 -8.400000",
         types="Q12280", type_labels_en="bridge", label_pt="Ponte Velha do Teste", sitelinks="1"),
    dict(qid="Q15", country="PT", lat="38.707700", lon="-9.136400", types="Q1131296",
         type_labels_en="freguesia of Portugal", label_pt="Santa Maria Maior", sitelinks="4"),
]
GEONAMES = {
    "PT": [
        ["2264508", "Óbidos", "Obidos", "", "39.3606", "-9.1571", "P", "PPL", "PT", "", "11", "1006", "", "", "3100"],
        ["2264509", "Santa Maria", "Santa Maria", "", "37.0", "-8.0", "P", "PPL", "PT", "", "08", "", "", "", "500"],
        ["2267057", "Lisboa", "Lisboa", "Lisbon,Lisbonne,Lissabon,Лиссабон", "38.72509", "-9.1498", "P", "PPLC", "PT",
         "", "14", "1106", "", "", "517802"],
        ["2264510", "Igreja Matriz", "Igreja Matriz", "", "41.0", "-8.5", "S", "CH", "PT", "", "13", "", "", "", "0"],
        ["2264511", "Lisboa", "Lisboa", "", "38.7168", "-9.1334", "S", "HTL", "PT", "", "14", "", "", "", "0"],
    ],
    "ES": [["3100001", "Santa María", "Santa Maria", "", "40.5", "-4.0", "P", "PPL", "ES", "", "51", "", "", "",
            "200"]],
    "FR": [["3000001", "Le Mont-Saint-Michel", "Le Mont-Saint-Michel", "Mont-Saint-Michel", "48.6359", "-1.5114", "A",
            "ADM4", "FR", "", "28", "50", "", "", "30"],
           ["3000002", "Too", "Few", "fields"]],
}
POSTCODES = {
    "PT": [["PT", "3750-011", "Alcafaz", "Aveiro", "02", "Águeda", "0101", "Agadão", "010101", "40.5755", "-8.3247",
            "4"],
           ["PT", "3750-012", "Caselho", "Aveiro", "02", "Águeda", "0101", "Agadão", "010101", "40.5619", "-8.3228",
            "4"],
           *(["PT", f"1100-00{i}", "Lisboa", "Lisboa", "14", "Lisboa", "1106", "Lisboa", "", "38.7167", "-9.1333", "4"]
             for i in (1, 2, 3))],
    "ES": [["ES", "28001", "Madrid", "Comunidad de Madrid", "MD", "Madrid", "M", "Madrid", "28079", "40.4251",
            "-3.6906", "4"],
           ["ES", "28001", "Madrid Centro", "Comunidad de Madrid", "MD", "Madrid", "M", "Madrid", "28079", "40.43",
            "-3.69", "3"]],
    "FR": [["FR", "75001", "Paris 01", "Île-de-France", "11", "Paris", "75", "Paris", "751", "48.8592", "2.3417", "5"],
           ["FR", "28001", "Chartres", "Centre-Val de Loire", "24", "Eure-et-Loir", "28", "Chartres", "281", "48.4469",
            "1.4892", "5"],
           ["FR", "75021 CEDEX 01", "Paris 01", "Île-de-France", "11", "Paris", "75", "Paris", "751", "48.8592",
            "2.3417", "5"]],
}


def geonames_line(fields):
    return "\t".join(fields + [""] * (19 - len(fields)) if len(fields) >= 15 else fields) + "\n"


def write_fixtures(root):
    root = Path(root)
    with gzip.open(root / "wikidata.csv.gz", "wt", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNS)
        writer.writeheader()
        for item in WIKIDATA:
            writer.writerow({"n_coords": "1", **item})
    for country, rows in GEONAMES.items():
        (root / "geonames" / "places" / country).mkdir(parents=True)
        (root / "geonames" / "postcodes" / country).mkdir(parents=True)
        with open(root / "geonames" / "places" / country / f"{country}.txt", "w", encoding="utf-8") as f:
            f.writelines(geonames_line(r) for r in rows)
        with open(root / "geonames" / "postcodes" / country / f"{country}.txt", "w", encoding="utf-8") as f:
            f.writelines("\t".join(r) + "\n" for r in POSTCODES[country])
    (root / "geonames" / "featureCodes_en.txt").write_text(
        "P.PPL\tpopulated place\ta city\nP.PPLC\tcapital of a political entity\t\nS.CH\tchurch\t\n", encoding="utf-8")
    (root / "geonames" / "admin1CodesASCII.txt").write_text("PT.14\tLisbon\tLisbon\t2267056\n", encoding="utf-8")
    (root / "geonames" / "admin2Codes.txt").write_text("PT.14.1106\tLisboa\tLisboa\t8012524\n", encoding="utf-8")
    return root / "wikidata.csv.gz", root / "geonames"


class NameIndexTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.wikidata, cls.geonames = write_fixtures(cls.tmp.name)
        cls.path = Path(cls.tmp.name) / "index" / "names.sqlite"
        cls.report = builder.build(cls.path, cls.wikidata, cls.geonames, log=lambda message: None)
        cls.index = NameIndex.open(cls.path)

    @classmethod
    def tearDownClass(cls):
        cls.index.close()
        cls.tmp.cleanup()

    def sources(self, candidates):
        return [c.source for c in candidates]

    def test_exact_match_ignores_accents_case_and_punctuation(self):
        for text in ("Torre de Belém", "TORRE DE BELEM", "torre-de-belem"):
            first = self.index.lookup(text)[0]
            self.assertEqual(first.source, "wikidata:Q1")
            self.assertEqual((first.details["match_type"], first.details["match_score"]), ("exact", 1.0))
            self.assertEqual(first.details["matched_name"], "Torre de Belém")
            self.assertEqual(first.details["language"], ["pt"])

    def test_alias_carries_its_language(self):
        first = self.index.lookup("Tower of Belem")[0]
        self.assertEqual(first.source, "wikidata:Q1")
        self.assertEqual((first.details["name_kind"], first.details["language"]), ("alias", ["en"]))

    def test_fuzzy_match_survives_one_wrong_or_missing_letter(self):
        first = self.index.lookup("TORRE DE BELEN")[0]
        self.assertEqual(first.source, "wikidata:Q1")
        self.assertEqual((first.details["match_type"], first.details["edit_distance"]), ("fuzzy", 1.0))
        self.assertLess(first.details["match_score"], 1.0)
        self.assertEqual(self.index.lookup("Sagrada Famlia")[0].source, "wikidata:Q6")
        self.assertEqual(self.index.lookup("T0RRE DE BELEM")[0].details["edit_distance"], 0.5)  # 0 for O
        self.assertEqual(self.index.lookup("Torre de Belen", fuzzy=False), [])
        misread = self.index.lookup("TORRE DC BELEM")[0]  # "dc" for "de": c and e look alike, half an edit
        self.assertEqual((misread.source, misread.details["misread_words"]), ("wikidata:Q1", ["dc"]))
        self.assertEqual(misread.details["edit_distance"], 0.5)

    def test_glued_split_abbreviated_and_stopword_variants(self):
        cases = {"SANTAMARIA": ("wikidata:Q3", "spacing"), "Mont St Michel": ("wikidata:Q4", "abbreviation"),
                 "Torre Belem": ("wikidata:Q1", "stopwords")}
        for text, expected in cases.items():
            first = self.index.lookup(text)[0]
            self.assertEqual((first.source, first.details["match_type"]), expected, text)
        # the label without its article ("Le") outweighs the alias with other spacing
        first = self.index.lookup("MONTSAINT MICHEL")[0]
        self.assertEqual((first.source, first.details["match_type"]), ("wikidata:Q4", "stopwords"))

    def test_partial_matches_come_last(self):
        first = self.index.lookup("Jeronimos")[0]
        self.assertEqual((first.source, first.details["match_type"]), ("wikidata:Q13", "contains"))
        found = {c.source: c for c in self.index.lookup("Torre de Belém, Lisboa")}
        self.assertEqual(found["wikidata:Q1"].details["match_type"], "within")
        self.assertIn("geonames:2267057", found)
        self.assertGreater(found["wikidata:Q1"].details["coverage"], found["geonames:2267057"].details["coverage"])
        # the longest run that is a name wins over the shorter names inside it
        found = self.index.lookup("JUNTA DE FREGUESIA DE SANTA MARIA MAIOR")
        self.assertEqual(found[0].source, "wikidata:Q15")
        inner = [c for c in found if c.source == "wikidata:Q2"][0]
        self.assertLess(inner.details["coverage"], found[0].details["coverage"] / 2)

    def test_ambiguous_names_keep_every_place(self):
        exact = [c for c in self.index.lookup("Santa Maria") if c.details["match_type"] == "exact"]
        self.assertEqual(set(self.sources(exact)),
                         {"wikidata:Q2", "wikidata:Q3", "geonames:2264509", "geonames:3100001"})
        self.assertTrue(all(c.details["ambiguity"] == 4 for c in exact))
        self.assertEqual(set(self.sources(self.index.lookup("Igreja Matriz"))), {"wikidata:Q5", "geonames:2264510"})
        self.assertEqual(len(self.index.lookup("Santa Maria", limit=2)), 2)

    def test_country_filter(self):
        for countries, expected in (("ES", {"ES"}), (["PT"], {"PT"}), ("PT,ES", {"PT", "ES"})):
            self.assertEqual({c.country for c in self.index.lookup("Santa Maria", countries=countries)}, expected)
        border = self.index.lookup("Pic Frontalier", countries=["FR"])[0]
        self.assertEqual((border.country, border.details["countries"]), ("FR", ["ES", "FR"]))
        self.assertEqual(self.index.lookup("Pic Frontalier", countries="ES")[0].country, "ES")
        self.assertEqual(self.index.lookup("Torre de Belém", countries="FR"), [])
        with self.assertRaises(ValueError):
            self.index.lookup("Santa Maria", countries=["IT"])

    def test_roles_and_extents(self):
        def first(text):
            return self.index.lookup(text)[0]

        expected = {"Igreja Matriz": ("landmark", 25), "Parque da Cidade": ("area", 300),
                    "Sagrada Família": ("landmark", 60), "Le Mont-Saint-Michel": ("area", 2500)}
        for text, (role, extent) in expected.items():
            c = first(text)
            self.assertEqual((c.role, c.extent_m, c.details["extent_source"]), (role, extent, "assumed"), text)
            self.assertIsNone(c.accuracy_m)
        obidos = {c.source: c for c in self.index.lookup("Obidos")}
        self.assertEqual((obidos["wikidata:Q8"].role, obidos["wikidata:Q8"].extent_m), ("area", 10_000))
        self.assertEqual(obidos["geonames:2264508"].role, "area")
        self.assertEqual(obidos["geonames:2264508"].details["extent_rule"], "geonames population")
        church = [c for c in self.index.lookup("Igreja Matriz") if c.source == "geonames:2264510"][0]
        self.assertEqual((church.role, church.extent_m), ("landmark", 25))
        bridge = first("Ponte Velha do Teste")
        self.assertEqual(bridge.details["extent_source"], "source")
        self.assertGreater(bridge.extent_m, 1900)
        everything = [c for q in ("Santa Maria", "Lisboa", "Torre de Belém", "Obidos") for c in self.index.lookup(q)]
        self.assertTrue(all(c.role in ("landmark", "area") for c in everything))
        self.assertTrue(all(c.extent_m > 0 and c.country in ("PT", "ES", "FR") for c in everything))

    def test_same_place_in_both_sources_is_linked(self):
        obidos = {c.source: c for c in self.index.lookup("Obidos")}
        wd, gn = obidos["wikidata:Q8"], obidos["geonames:2264508"]
        self.assertIsNotNone(wd.group)
        self.assertEqual(wd.group, gn.group)
        self.assertEqual(wd.details["same_place_as"][0]["source"], "geonames:2264508")
        self.assertLess(wd.details["same_place_as"][0]["distance_m"], 1000)
        far = [c for c in self.index.lookup("Santa Maria") if c.source == "geonames:2264509"][0]
        self.assertIsNone(far.group)  # same name as wikidata:Q2, but 270 km away

    def test_weights_rank_prominence_and_match_quality(self):
        found = self.index.lookup("Santa Maria")
        self.assertEqual(found[0].source, "wikidata:Q3")  # 10 sitelinks beat 3, and a population of 500
        self.assertTrue(all(found[i].weight >= found[i + 1].weight for i in range(3)))  # the 4 exact matches
        self.assertEqual(found[4].details["match_type"], "contains")  # Santa Maria Maior, after every exact match
        exact, fuzzy = self.index.lookup("Torre de Belém")[0], self.index.lookup("Torre de Belen")[0]
        self.assertGreater(exact.weight, fuzzy.weight)
        self.assertGreater(fuzzy.weight, 0)

    def test_skipped_rows_and_events(self):
        stats = self.report["stats"]
        self.assertEqual(self.index.lookup("Batalha de Teste"), [])
        self.assertEqual(self.index.lookup("Sem Coordenadas"), [])
        self.assertEqual((stats["wikidata_bad_rows"], stats["wikidata_events_skipped"]), (2, 1))
        self.assertEqual((stats["geonames_bad_rows"], stats["postcode_cedex_skipped"]), (1, 1))
        self.assertEqual(self.index.lookup("Лиссабон"), [])  # non-Latin names are not indexed
        self.assertEqual(self.index.lookup("Lisbon")[0].source, "geonames:2267057")

    def test_postcode_pt_full_code(self):
        for text in ("3750-011", "3750 011", "3750011", "P-3750-011"):
            (c,) = self.index.postcode(text)
            self.assertEqual((c.source, c.role, c.country), ("postcode:PT:3750-011", "area", "PT"))
            self.assertEqual(c.details["geonames_accuracy"], 4)
            self.assertEqual(c.details["extent_source"], "assumed")
            self.assertIsNone(c.accuracy_m)
        self.assertAlmostEqual(c.lat, 40.5755)

    def test_postcode_extent_depends_on_whether_the_point_is_shared(self):
        # 1100-001..003 share one point: it is Lisbon's centroid, so the code may lie anywhere in Lisbon.
        # The hotel named "Lisboa" next to that point is not a place a postcode names.
        (shared,) = self.index.postcode("1100-002")
        self.assertEqual(shared.details["places"][0]["geonames"], "geonames:2267057")
        self.assertGreater(shared.extent_m, 5000)
        (own,) = self.index.postcode("3750-011")  # its own point, and no GeoNames place named Alcafaz
        self.assertEqual(own.extent_m, 1500)

    def test_postcode_pt_prefix_is_one_aggregate_area(self):
        (c,) = self.index.postcode("3750")
        self.assertEqual((c.source, c.details["kind"], c.details["n_codes"]), ("postcode:PT:3750", "prefix", 2))
        self.assertTrue(40.5619 < c.lat < 40.5755)
        for lat, lng in ((40.5755, -8.3247), (40.5619, -8.3228)):
            self.assertGreater(c.extent_m, haversine_m(c.point, (lat, lng)))

    def test_postcode_es_fr_and_ambiguity(self):
        (es,) = self.index.postcode("28001", country="ES")
        self.assertEqual((es.source, es.details["n_rows"], es.details["geonames_accuracy"]),
                         ("postcode:ES:28001", 2, [3, 4]))
        self.assertEqual(sorted(c.country for c in self.index.postcode("28001")), ["ES", "FR"])
        self.assertEqual([c.country for c in self.index.postcode("E-28001")], ["ES"])
        self.assertEqual(self.index.postcode("75001")[0].source, "postcode:FR:75001")
        self.assertEqual(self.index.postcode("9999-999"), [])
        self.assertEqual(self.index.postcode("not a code"), [])

    def test_candidates_are_json_ready(self):
        for c in self.index.lookup("Obidos") + self.index.postcode("3750"):
            json.dumps(c.to_dict())

    def test_rebuild_replaces_the_index(self):
        path = Path(self.tmp.name) / "rebuild" / "names.sqlite"
        first = builder.build(path, self.wikidata, self.geonames, log=lambda message: None)
        second = builder.build(path, self.wikidata, self.geonames, log=lambda message: None)
        self.assertEqual(first["stats"], second["stats"])
        self.assertEqual([p.name for p in path.parent.iterdir()], ["names.sqlite"])
        with NameIndex.open(path) as again:
            self.assertEqual(again.lookup("Torre de Belém")[0].source, "wikidata:Q1")


try:  # the OSM builder needs the venv (pyosmium, numpy, shapely)
    import osmium  # noqa: F401
    osm_spec = importlib.util.spec_from_file_location("build_osm_index", TOOLS / "build_osm_index.py")
    osm_builder = importlib.util.module_from_spec(osm_spec)
    osm_spec.loader.exec_module(osm_builder)
except ImportError:
    osm_builder = None


def osm_node(nid, lat, lng, **tags):
    body = "".join(f'<tag k="{k.replace("__", ":")}" v="{v}"/>' for k, v in tags.items())
    return f'  <node id="{nid}" lat="{lat}" lon="{lng}" version="1">{body}</node>\n'


def osm_way(wid, refs, **tags):
    body = "".join(f'<nd ref="{r}"/>' for r in refs) + "".join(
        f'<tag k="{k.replace("__", ":")}" v="{v}"/>' for k, v in tags.items())
    return f'  <way id="{wid}" version="1">{body}</way>\n'


# Invented objects; the landmarks reuse the WIKIDATA fixture's coordinates above
OSM_NODES = [
    osm_node(1, 40.2, -8.4, amenity="cafe", name="Pastelaria Aurora"),
    *(osm_node(11 + i, lat, lng) for i, (lat, lng) in enumerate(
        [(40.2049, -8.4051), (40.2051, -8.4051), (40.2051, -8.4049), (40.2049, -8.4049)])),
    osm_node(15, 40.205, -8.405, shop="bakery", name="Padaria Estrela"),
    *(osm_node(101 + i, 40.21 + 0.0005 * i, -8.41) for i in range(4)),  # one street, three connected ways
    osm_node(105, 40.2128, -8.41), osm_node(106, 40.2133, -8.41),       # ... and a piece 145 m on
    osm_node(201, 40.4, -8.41), osm_node(202, 40.4005, -8.41),           # another street of that name, 20 km away
    *(osm_node(301 + i, 37.0 + 0.4 * i, -8.0, shop="supermarket", name="Mercado Exemplo", brand="Mercado Exemplo")
      for i in range(10)),
    osm_node(311, 41.9, -8.0, shop="supermarket", name="Mercado Exemplo Norte", brand="Mercado Exemplo"),
    osm_node(312, 41.95, -8.0, amenity="cafe", name="Café do Mercado Exemplo"),  # not the chain, but named after it
    osm_node(401, 38.69165, -9.21585, historic="tower", name="Torre de Belém", wikidata="Q1"),
    osm_node(402, 39.36065, -9.15705, place="town", name="Óbidos", wikidata="Q8"),
    osm_node(403, 38.698, -9.2067, historic="monastery", name="Mosteiro dos Jerónimos"),
    osm_node(404, 38.7, -9.2, amenity="bench", name="Banco do Jardim"),
    osm_node(601, 39.5, -8.5, shop="gift", name="Bazar"),  # a one-word shop name that other names share ...
    *(osm_node(602 + i, 39.5 + 0.1 * (i + 1), -8.5, shop="gift", name=name)
      for i, name in enumerate(["Bazar Central", "Bazar Lindo", "Café Bazar"])),
    osm_node(606, 39.6, -8.6, shop="gift", name="Lenuquinha"),  # ... and one no other name holds
    osm_node(701, 39.8, -8.8, place="locality", name="Lameira"), osm_node(702, 39.9, -8.9, place="hamlet", name="Lameira"),
    osm_node(703, 39.91, -8.9, amenity="cafe", name="Café Lameira"),
    osm_node(801, 39.95, -8.95, amenity="restaurant", name="Se Vende"),  # a for-sale sign mapped as a restaurant
    *(osm_node(501 + i, lat, lng, addr__postcode="3750-011") for i, (lat, lng) in enumerate(
        [(40.5801, -8.3301), (40.5802, -8.3302), (40.5803, -8.3301)])),
    osm_node(511, 38.71, -9.135, addr__postcode="1100-148"), osm_node(512, 38.7101, -9.1351, addr__postcode="1100 148"),
    *(osm_node(521 + i, lat, lng, addr__postcode="4000-322") for i, (lat, lng) in enumerate(
        [(41.15, -8.61), (41.1501, -8.61), (41.15, -8.6101), (41.1501, -8.6101), (41.15005, -8.61005)])),
    osm_node(526, 41.42, -8.61, addr__postcode="4000-322"),  # 30 km away: a typo
    *(osm_node(531 + i, lat, lng) for i, (lat, lng) in enumerate(
        [(41.1502, -8.6102), (41.1503, -8.6102), (41.1503, -8.6103), (41.1502, -8.6103)])),
    osm_node(540, 40.0, -8.0, addr__postcode="28013"),  # not a Portuguese code
]
OSM_WAYS = [
    osm_way(10, [11, 12, 13, 14, 11], building="retail", shop="bakery", name="Padaria Estrela"),
    osm_way(101, [101, 102], highway="residential", name="Rua das Flores"),
    osm_way(102, [102, 103], highway="residential", name="Rua das Flores"),
    osm_way(103, [103, 104], highway="tertiary", name="Rua das Flores"),
    osm_way(104, [105, 106], highway="residential", name="Rua das Flores"),
    osm_way(105, [201, 202], highway="residential", name="Rua das Flores"),
    osm_way(520, [531, 532, 533, 534, 531], building="yes", addr__postcode="4000-322"),
]


def write_osm(path):
    Path(path).write_text('<?xml version="1.0" encoding="UTF-8"?>\n<osm version="0.6" generator="panoloc tests">\n'
                          + "".join(OSM_NODES + OSM_WAYS) + "</osm>\n", encoding="utf-8")


@unittest.skipIf(osm_builder is None, "pyosmium is not installed: run with .venv/bin/python")
class OsmIndexTest(unittest.TestCase):
    """The OSM index (tools/build_osm_index.py) from a hand-written .osm file, next to the tiny names.sqlite."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        root = Path(cls.tmp.name)
        wikidata, geonames = write_fixtures(root)
        cls.folder = root / "index"
        cls.path = cls.folder / "names.sqlite"
        builder.build(cls.path, wikidata, geonames, log=lambda message: None)
        write_osm(root / "pt.osm")
        cls.report = osm_builder.build("PT", root / "pt.osm", cls.folder / "osm_PT.sqlite", cls.path, outline="none",
                                       work=root / "work", keep_work=True, log=lambda message: None)
        cls.index = NameIndex.open(cls.path)  # attaches osm_PT.sqlite, found next to names.sqlite

    @classmethod
    def tearDownClass(cls):
        cls.index.close()
        cls.tmp.cleanup()

    def osm(self, candidates):
        return [c for c in candidates if c.source.startswith("osm:")]

    def test_the_index_is_attached_and_described(self):
        self.assertEqual([i["country"] for i in self.index.osm], ["PT"])
        stats = self.report["stats"]
        self.assertEqual(stats["streets"], 2)
        self.assertGreaterEqual(stats["postcode_values_rejected"], 1)  # "28013" is not a PT code
        self.assertEqual(self.report["schema"], "panoloc.names.osm/1")

    def test_exact_and_fuzzy_matches(self):
        (c, *_) = self.index.lookup("Pastelaria Aurora")
        self.assertEqual((c.source, c.role, c.extent_m, c.label), ("osm:n1", "landmark", 12, "Pastelaria Aurora"))
        d = c.details
        self.assertEqual((d["source"], d["osm_id"], d["osm_type"], d["match_type"]), ("osm", "n1", "amenity=cafe", "exact"))
        self.assertEqual((d["extent_source"], d["occurrences"], d["tags"]["name"]), ("assumed", 1, "Pastelaria Aurora"))
        self.assertIsNone(c.accuracy_m)
        self.assertAlmostEqual(c.weight, d["prior"], places=4)  # exact label, unique name
        # short texts get no fuzzy OSM match ("Lamera" is one edit from the hamlet Lameira), longer ones do
        self.assertEqual(self.osm(self.index.lookup("Lamera")), [])
        self.assertIn("osm:n702", [c.source for c in self.index.lookup("Lameirra")])
        fuzzy = self.index.lookup("PASTELARIA AUR0RA")[0]
        self.assertEqual((fuzzy.source, fuzzy.details["match_type"], fuzzy.details["edit_distance"]),
                         ("osm:n1", "fuzzy", 0.5))
        self.assertEqual(self.index.lookup("Pastelaria Aurora", countries="ES"), [])
        self.assertEqual(self.osm(self.index.lookup("Banco do Jardim")), [])  # benches are not places
        self.assertEqual(self.osm(self.index.lookup("SE VENDE")), [])  # a sign phrase is never an OSM place

    def test_one_word_shop_names_are_weak_when_other_names_hold_the_word(self):
        (bazar,) = [c for c in self.osm(self.index.lookup("Bazar")) if c.details["match_type"] == "exact"]
        self.assertEqual((bazar.source, bazar.details["occurrences"], bazar.details["word_frequency"]), ("osm:n601", 1, 4))
        self.assertAlmostEqual(bazar.weight, bazar.details["prior"] / 4, places=6)  # any of 4 signs may read "Bazar"
        unique = self.osm(self.index.lookup("Lenuquinha"))[0]
        self.assertNotIn("word_frequency", unique.details)
        self.assertAlmostEqual(unique.weight, unique.details["prior"], places=6)
        obidos = [c for c in self.index.lookup("Obidos") if c.source == "osm:n402"][0]  # a town: its sign is its name
        self.assertNotIn("word_frequency", obidos.details)
        found = {c.source: c for c in self.osm(self.index.lookup("Lameira"))}
        locality, hamlet = found["osm:n701"], found["osm:n702"]  # 2 places of that name, 3 names hold the word
        self.assertEqual((locality.details["word_frequency"], locality.details["occurrences"]), (3, 2))
        self.assertAlmostEqual(locality.weight, locality.details["prior"] / 3, places=6)
        self.assertNotIn("word_frequency", hamlet.details)  # a settlement
        self.assertAlmostEqual(hamlet.weight, hamlet.details["prior"] / 2, places=6)

    def test_same_name_objects_close_together_are_one_entry(self):
        (c,) = self.osm(self.index.lookup("Padaria Estrela"))
        self.assertEqual((c.source, c.details["osm_ids"], c.details["extent_source"]), ("osm:w10", ["n15", "w10"], "source"))
        self.assertLess(haversine_m(c.point, (40.205, -8.405)), 5)  # inside the building

    def test_street_ways_merge_into_one_area_on_the_street(self):
        found = self.osm(self.index.lookup("Rua das Flores"))
        self.assertEqual(len(found), 2)
        near = next(c for c in found if c.lat < 40.3)
        far = next(c for c in found if c.lat > 40.3)
        self.assertEqual((near.role, near.details["n_objects"]), ("area", 4))
        self.assertEqual(sorted(near.details["osm_ids"]), ["w101", "w102", "w103", "w104"])
        self.assertEqual(near.details["osm_type"], "highway=tertiary")  # the most important class of its ways
        nodes = [(40.21 + 0.0005 * i, -8.41) for i in range(4)] + [(40.2128, -8.41), (40.2133, -8.41)]
        self.assertTrue(any(haversine_m(near.point, n) < 0.5 for n in nodes))  # a node: on the street
        self.assertTrue(all(near.extent_m >= haversine_m(near.point, n) for n in nodes))
        self.assertEqual((far.details["n_objects"], far.details["osm_ids"]), (1, ["w105"]))
        self.assertEqual(near.details["occurrences"], 2)  # two streets share the name: half the weight each
        self.assertAlmostEqual(near.weight, near.details["prior"] / 2, places=6)

    def test_chain_names_stay_one_weak_ambiguous_clue(self):
        found = self.osm(self.index.lookup("Mercado Exemplo", limit=20))
        chain = [c for c in found if c.details["match_type"] == "exact"]
        self.assertEqual(len(chain), 3)  # CHAIN_KEEP of the 11 stores (10 named so, 1 by its brand)
        for c in chain:
            self.assertTrue(c.details["chain"])
            self.assertEqual(c.details["occurrences"], 11)
            self.assertGreaterEqual(c.details["ambiguity"], 11)
            self.assertAlmostEqual(c.weight, c.details["prior"] / 11, places=6)
        self.assertLess(sum(c.weight for c in chain), chain[0].details["prior"] / 3)
        # a store left out does not come back through a weaker tier under its own name
        self.assertNotIn("Mercado Exemplo Norte", [c.label for c in found if c.details["match_type"] != "exact"])
        # the text is itself a generic name: a partial match is taken as one more of its 11 places
        (cafe,) = [c for c in found if c.label == "Café do Mercado Exemplo"]
        self.assertEqual((cafe.details["match_type"], cafe.details["generic_query"]), ("contains", 11))
        coverage = cafe.details["coverage"]
        self.assertAlmostEqual(cafe.weight, 0.2 * coverage ** 2 * cafe.details["prior"] / 11, places=6)
        alone = self.osm(self.index.lookup("Café do Mercado Exemplo"))[0]  # the café's own name: unique
        self.assertEqual((alone.label, alone.details["occurrences"]), ("Café do Mercado Exemplo", 1))
        self.assertNotIn("generic_query", alone.details)

    def test_near_finds_the_chain_store_by_a_hypothesis(self):
        (store,) = self.osm(self.index.lookup("Mercado Exemplo", near=(37.4, -8.0, 1000)))
        self.assertEqual((store.source, store.details["near_distance_m"]), ("osm:n302", 0.0))
        self.assertEqual(store.details["ambiguity"], 1)  # within the box
        self.assertEqual(store.details["occurrences"], 11)  # the country-wide count stays in the weight
        nearby = self.index.lookup("Mercado Exemplo", near=(37.0, -8.0, 50_000))  # 37.0 and 37.4 are 44 km apart
        self.assertEqual(sorted(c.source for c in self.osm(nearby)), ["osm:n301", "osm:n302"])  # no chain cap
        self.assertEqual(self.index.lookup("Torre de Belém", near=(40.0, -8.0, 1000)), [])
        with self.assertRaises(ValueError):
            self.index.lookup("Torre de Belém", near=(40.0, -8.0, 0))

    def test_wikidata_tag_links_to_the_item(self):
        found = {c.source: c for c in self.index.lookup("Torre de Belém")}
        osm, wd = found["osm:n401"], found["wikidata:Q1"]
        self.assertIsNotNone(osm.group)
        self.assertEqual(osm.group, wd.group)
        self.assertIn({"source": "wikidata:Q1", "how": "wikidata tag"},
                      [{k: v for k, v in link.items() if k != "distance_m"} for link in osm.details["same_place_as"]])
        self.assertIn("osm:n401", [link["source"] for link in wd.details["same_place_as"]])
        self.assertEqual(osm.details["prominence"], wd.details["prominence"])  # the item's prominence, not a tower's
        obidos = {c.source: c for c in self.index.lookup("Obidos")}
        self.assertEqual(obidos["osm:n402"].group, obidos["wikidata:Q8"].group)
        self.assertEqual(obidos["osm:n402"].group, "same-place:geonames:2264508")  # the existing group is kept

    def test_same_name_nearby_links_too(self):
        found = {c.source: c for c in self.index.lookup("Mosteiro dos Jerónimos")}
        osm, wd = found["osm:n403"], found["wikidata:Q13"]
        self.assertTrue(osm.details["same_place_as"][0]["how"].startswith("name within"))
        self.assertEqual((osm.group, wd.group), ("same-place:wikidata:Q13", "same-place:wikidata:Q13"))
        with NameIndex.open(self.path, osm=False) as plain:
            self.assertIsNone(plain.lookup("Mosteiro dos Jerónimos")[0].group)

    def test_postcode_prefers_the_osm_aggregate(self):
        osm, geonames = self.index.postcode("3750-011")
        self.assertEqual((osm.source, osm.role, osm.weight), ("osm-postcode:PT:3750-011", "area", 0.8))
        self.assertEqual((osm.details["source"], osm.details["n_addresses"], osm.details["kind"]), ("osm", 3, "code"))
        self.assertEqual((osm.lat, osm.lng), (40.5802, -8.3302))  # the median address
        self.assertEqual(osm.extent_m, 100)  # fewer than 5 addresses: at least 100 m
        self.assertGreater(osm.details["geonames_distance_m"], 500)
        self.assertEqual((geonames.source, geonames.weight, geonames.details["source"]),
                         ("postcode:PT:3750-011", 0.2, "geonames"))
        (only,) = self.index.postcode("1100-148")  # GeoNames lacks it
        self.assertEqual((only.source, only.weight, only.details["n_addresses"]), ("osm-postcode:PT:1100-148", 1.0, 2))
        prefix = self.index.postcode("3750")
        self.assertEqual([c.source for c in prefix], ["osm-postcode:PT:3750", "postcode:PT:3750"])
        self.assertEqual(prefix[0].details["kind"], "prefix")
        # ES and FR codes are commune-level: OSM and GeoNames split the weight evenly
        self.assertEqual([osm_postcode_share(n, c) for n, c in ((1, "PT"), (12, "PT"), (500, "ES"), (2, "FR"))],
                         [0.65, 0.9, 0.5, 0.5])

    def test_postcode_spread_ignores_outliers(self):
        c = self.index.postcode("4000-322")[0]
        d = c.details
        self.assertEqual((d["n_addresses"], d["n_outliers"]), (7, 1))  # 5 nodes, a building, and the typo
        self.assertLess(d["spread_max_m"], 100)
        self.assertEqual(c.extent_m, 50)  # the spread is smaller than the 50 m floor
        self.assertLess(haversine_m(c.point, (41.15005, -8.61005)), 30)

    def test_switching_osm_off_gives_the_results_without_it(self):
        bare = Path(self.tmp.name) / "bare"
        bare.mkdir(exist_ok=True)
        (bare / "names.sqlite").write_bytes(self.path.read_bytes())
        queries = ["Torre de Belém", "Obidos", "Santa Maria", "Rua das Flores", "Mosteiro dos Jerónimos"]
        with NameIndex.open(bare / "names.sqlite") as without, NameIndex.open(self.path, osm=False) as off:
            self.assertEqual((without.osm, off.osm), ([], []))
            for q in queries:
                self.assertEqual([c.to_dict() for c in without.lookup(q)], [c.to_dict() for c in off.lookup(q)], q)
            for code in ("3750-011", "1100-148", "3750"):
                self.assertEqual([c.to_dict() for c in without.postcode(code)],
                                 [c.to_dict() for c in off.postcode(code)])
            self.assertEqual([c.source for c in off.postcode("3750-011")], ["postcode:PT:3750-011"])
            self.assertEqual(off.postcode("3750-011")[0].weight, 1.0)
        previous = os.environ.get("PANOLOC_NAMES_OSM")
        os.environ["PANOLOC_NAMES_OSM"] = "0"
        try:
            with NameIndex.open(self.path) as env_off, NameIndex.open(self.path, osm=True) as forced:
                self.assertEqual((len(env_off.osm), len(forced.osm)), (0, 1))
        finally:
            if previous is None:
                os.environ.pop("PANOLOC_NAMES_OSM")
            else:
                os.environ["PANOLOC_NAMES_OSM"] = previous

    def test_an_unreadable_osm_index_is_skipped_or_refused(self):
        folder = Path(self.tmp.name) / "bad"
        folder.mkdir(exist_ok=True)
        (folder / "names.sqlite").write_bytes(self.path.read_bytes())
        (folder / "osm_PT.sqlite").write_bytes(self.path.read_bytes())  # a names.sqlite, not an OSM index
        with self.assertWarns(RuntimeWarning):
            with NameIndex.open(folder / "names.sqlite") as index:
                self.assertEqual(index.osm, [])
        with self.assertRaises(RuntimeError):
            NameIndex.open(folder / "names.sqlite", osm=[folder / "osm_PT.sqlite"])

    def test_candidates_are_json_ready_and_rebuild_resumes(self):
        for c in self.index.lookup("Rua das Flores") + self.index.postcode("3750-011"):
            json.dumps(c.to_dict())
        root = Path(self.tmp.name)
        again = osm_builder.build("PT", root / "pt.osm", root / "again" / "osm_PT.sqlite", self.path, outline="none",
                                  work=root / "work", log=lambda message: None)
        self.assertEqual(again["resumed"], ["pass1", "pass2"])
        self.assertEqual(again["stats"]["entries"], self.report["stats"]["entries"])
        self.assertFalse((root / "work").exists())  # removed after a successful build without keep_work


class NormalisationTest(unittest.TestCase):
    def test_normalise_and_keys(self):
        self.assertEqual(normalise("Praça do Comércio"), "praca do comercio")
        self.assertEqual(normalise("  L'Haÿ-les-Roses "), "l hay les roses")
        self.assertEqual(normalise("ŒUVRE Nª Srª"), "oeuvre na sra")
        self.assertEqual(keys("torre de belem"), ("torredebelem", "torrebelem"))
        self.assertEqual(keys("de la"), ("dela", "dela"))

    def test_edit_distance(self):
        self.assertEqual(edit_distance("belem", "belen"), 1)
        self.assertEqual(edit_distance("lisboa", "lisoba"), 1)  # adjacent transposition
        self.assertEqual(edit_distance("porto", "p0rto"), 0.5)
        self.assertGreater(edit_distance("porto", "faro", limit=1), 1)

    def test_abbreviations_and_postcode_parsing(self):
        self.assertIn("mont saint michel", expand_abbreviations("mont st michel"))
        self.assertIn("nossa senhora da luz", expand_abbreviations("n sra da luz"))
        self.assertEqual(expand_abbreviations("torre de belem"), [])
        self.assertEqual(parse_postcode("1100"), [("PT", "1100")])
        self.assertEqual(parse_postcode("8001", country="ES"), [("ES", "08001")])
        self.assertEqual(parse_postcode("F-75OO1"), [("FR", "75001")])  # O read for 0


if __name__ == "__main__":
    unittest.main()
