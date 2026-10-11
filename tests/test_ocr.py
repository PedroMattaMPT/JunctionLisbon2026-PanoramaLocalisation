"""Tests for panoloc.ocr. Run from the repo root: .venv/bin/python -m unittest discover -s tests

Parsing, deduplication and the reread logic are pure and need no models. EngineTest renders text with
DejaVu Sans into a synthetic panorama and reads it with the real PP-OCRv6 engine; it is skipped when
the font or the RapidOCR models are missing. Every test string is made up or taken from
COUNTRY_CLUES.md; none comes from the warm-up panoramas.
"""
import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from panoloc import ocr
from panoloc.ocr import (Hit, OcrResult, Sign, absorb_fragments, box_inside, box_overlap, clean_reading,
                         combine_reread, dedup, language_hints, log_ocr, looks_like_strokes, name_candidates,
                         needs_reread, panel_context, parse_domains, parse_hunting_zones, parse_municipal_codes,
                         parse_municipalities, parse_organisations, parse_phones, parse_plates, parse_postcodes,
                         parse_roads, parse_sign, parse_text, parse_trails, picks_for, reread_priority,
                         text_similarity)
from panoloc.runlog import Run
from panoloc.views import cut_view, sphere_to_pano_xy

FONT = Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")


def kinds(items, kind):
    return [it for it in items if it["kind"] == kind]


def one(items, kind):
    found = kinds(items, kind)
    if len(found) != 1:
        raise AssertionError(f"expected one {kind}, got {[(it['kind'], it['value']) for it in items]}")
    return found[0]


def hit(text, yaw, pitch, *, w=6.0, h=1.5, view="h000", conf=0.95, at_edge=False, zone=0.0, height=30.0):
    return Hit(text=text, confidence=conf, view=view, quad=[[0, 0], [10, 0], [10, 5], [0, 5]],
               box={"yaw": yaw % 360, "pitch": pitch, "w": w, "h": h}, height_px=height, zone_fraction=zone,
               at_edge=at_edge)


def sign(text, yaw=45.0, pitch=0.0, *, conf=0.95, w=6.0, h=1.5, height=30.0, at_edge=False, sign_id="s1"):
    first = hit(text, yaw, pitch, w=w, h=h, conf=conf, height=height, at_edge=at_edge)
    return Sign(sign_id, text, conf, first.box, [first])


class PostcodeTest(unittest.TestCase):
    def test_portuguese_4_3_codes_and_the_first_digit_region(self):
        item = one(parse_postcodes("Rua das Flores 12, 3000-123 COIMBRA"), "postcode")
        self.assertEqual((item["value"], item["countries"], item["strength"]), ("3000-123", ["PT"], "strong"))
        self.assertEqual(item["regions"][0]["name"], "Aveiro, Coimbra, Viseu, north Leiria")
        self.assertEqual(item["details"]["locality"], "COIMBRA")
        self.assertEqual(item["details"]["fourth_digit"], "municipality seat")
        self.assertEqual(one(parse_postcodes("8200 – 260"), "postcode")["value"], "8200-260")  # en dash and spaces
        self.assertEqual(one(parse_postcodes("9050-021"), "postcode")["regions"][0]["name"], "Madeira")
        self.assertEqual(one(parse_postcodes("9500-150"), "postcode")["regions"][0]["name"], "Azores")

    def test_portuguese_negatives(self):
        for text in ("01310-100", "2019-2020", "1234-567-890", "40501234", "Lote 1234"):
            with self.subTest(text=text):
                self.assertEqual(parse_postcodes(text), [])

    def test_five_digit_codes_need_context(self):
        for text in ("28013", "Tel 28013", "12500 €", "Nº 28013", "28013 km"):
            with self.subTest(text=text):
                self.assertEqual(parse_postcodes(text), [])

    def test_spanish_context_settles_the_country(self):
        for text in ("C.P. 28013", "Código Postal: 28013", "E-28013"):
            with self.subTest(text=text):
                item = one(parse_postcodes(text), "postcode")
                self.assertEqual((item["value"], item["countries"], item["strength"]), ("28013", ["ES"], "strong"))
                self.assertEqual(item["regions"][0]["name"], "Madrid")

    def test_french_context_and_prefixes_above_52(self):
        item = one(parse_postcodes("75011 PARIS"), "postcode")
        self.assertEqual((item["countries"], item["strength"]), (["FR"], "strong"))
        self.assertEqual(item["details"]["fr_arrondissement"], 11)
        self.assertEqual(one(parse_postcodes("F-64100"), "postcode")["countries"], ["FR"])
        cedex = one(parse_postcodes("44701 ORVAULT CEDEX"), "postcode")
        self.assertEqual((cedex["countries"], cedex["regions"][0]["name"]), (["FR"], "Loire-Atlantique"))

    def test_a_name_after_a_code_01_52_leaves_both_countries(self):
        item = one(parse_postcodes("28013 Madrid"), "postcode")
        self.assertEqual((item["countries"], item["strength"]), (["ES", "FR"], "medium"))
        self.assertEqual([r["name"] for r in item["regions"]], ["Madrid", "Eure-et-Loir"])

    def test_the_named_collisions_17_20_31(self):
        for text, note, regions in (("31000 TOULOUSE", "31 is Haute-Garonne or Navarra", ["Navarra", "Haute-Garonne"]),
                                    ("20000 AJACCIO", "20 is Corsica or Gipuzkoa", ["Gipuzkoa", "Corse-du-Sud"]),
                                    ("17001 Girona", "17 is Charente-Maritime or Girona",
                                     ["Girona", "Charente-Maritime"])):
            with self.subTest(text=text):
                item = one(parse_postcodes(text), "postcode")
                self.assertIn(note, item["notes"])
                self.assertEqual([r["name"] for r in item["regions"]], regions)
        self.assertEqual(one(parse_postcodes("20200 BASTIA"), "postcode")["regions"][1]["code"], "2B")

    def test_ocr_separator_variants(self):
        self.assertEqual(one(parse_postcodes("4700·123 BRAGA"), "postcode")["value"], "4700-123")
        spaced = one(parse_postcodes("4700 123 BRAGA"), "postcode")
        self.assertEqual((spaced["value"], spaced["strength"], spaced["details"]["locality"]),
                         ("4700-123", "medium", "BRAGA"))
        for text in ("4700 123", "4700 123 Braga", "2019 100 ANOS"):  # no hyphen and no capitals locality
            with self.subTest(text=text):
                self.assertEqual(parse_postcodes(text), [])
        glued = one(parse_postcodes("C.P.28013"), "postcode")
        self.assertEqual((glued["value"], glued["countries"]), ("28013", ["ES"]))
        self.assertEqual(one(parse_postcodes("28013, Madrid"), "postcode")["details"]["name_after"], "Madrid")
        for text in ("1.28013", "28013,5 m2", "28013.5"):
            with self.subTest(text=text):
                self.assertEqual(parse_postcodes(text), [])

    def test_corsica_cedex_codes(self):
        cedex = one(parse_postcodes("20700 AJACCIO CEDEX 9"), "postcode")  # 2A also uses 203xx, 205xx, 207xx
        self.assertEqual((cedex["countries"], cedex["regions"][0]["code"]), (["FR"], "2A"))

    def test_ocr_look_alikes_are_repaired_one_strength_weaker(self):
        item = one(parse_postcodes("4O5O-253"), "postcode")
        self.assertEqual((item["value"], item["strength"], item["raw"]), ("4050-253", "medium", "4O5O-253"))
        self.assertTrue(item["details"]["repaired"])


class PhoneTest(unittest.TestCase):
    def test_portuguese_landline_gives_the_area(self):
        item = one(parse_phones("Tel. 239 123 456"), "phone")
        self.assertEqual((item["value"], item["countries"], item["strength"]), ("+351 239123456", ["PT"], "strong"))
        region = item["regions"][0]
        self.assertEqual((region["name"], region["code"], region["district"]), ("Coimbra", "239", "Coimbra"))
        lisbon = one(parse_phones("(+351) 21 123 4567"), "phone")
        self.assertEqual((lisbon["regions"][0]["code"], lisbon["details"]["international_prefix"]), ("21", True))

    def test_91x_is_a_portuguese_mobile_or_a_madrid_landline(self):
        item = one(parse_phones("Tlm. 912 345 678"), "phone")
        self.assertEqual((item["countries"], item["strength"]), (["PT", "ES"], "medium"))
        self.assertEqual([r["name"] for r in item["regions"]], ["Madrid"])  # a PT mobile has no region
        self.assertTrue(any("Portuguese mobile or a Spanish landline" in n for n in item["notes"]))
        self.assertIn("written 3-3-3, as Portuguese numbers are", item["notes"])
        spanish_style = one(parse_phones("Tel 91 234 56 78"), "phone")
        self.assertIn("written 2-3-2-2, as Spanish landlines often are", spanish_style["notes"])

    def test_country_codes_settle_the_country(self):
        item = one(parse_phones("+34 943 123 456"), "phone")
        self.assertEqual((item["countries"], item["regions"][0]["name"]), (["ES"], "Gipuzkoa"))
        self.assertEqual(one(parse_phones("+351 912 345 678"), "phone")["countries"], ["PT"])
        self.assertEqual(one(parse_phones("+33 6 12 34 56 78"), "phone")["countries"], ["FR"])  # not an ES mobile

    def test_spanish_and_french_numbers(self):
        mobile = one(parse_phones("Móvil 612 345 678"), "phone")
        self.assertEqual((mobile["countries"], mobile["regions"], mobile["strength"]), (["ES"], [], "strong"))
        zone = one(parse_phones("Tél. 05 59 12 34 56"), "phone")
        self.assertEqual((zone["countries"], zone["value"]), (["FR"], "+33 559123456"))
        self.assertTrue(zone["regions"][0]["name"].startswith("south-west"))
        self.assertTrue(any("strong prior, not proof" in n for n in zone["notes"]))
        self.assertEqual(one(parse_phones("+33 1 23 45 67 89"), "phone")["regions"][0]["name"], "Île-de-France")
        self.assertEqual(one(parse_phones("06 12 34 56 78"), "phone")["regions"], [])

    def test_no_phone_word_is_one_strength_weaker_unless_the_panel_has_one(self):
        self.assertEqual(one(parse_phones("239 123 456"), "phone")["strength"], "medium")
        self.assertEqual(one(parse_phones("961 222 333"), "phone")["strength"], "weak")
        panel = one(parse_phones("961 222 333", context="ALUGA-SE"), "phone")
        self.assertEqual((panel["strength"], panel["details"]["phone_word"]), ("medium", "same panel"))

    def test_placeholders_odd_groupings_and_separators(self):
        for text in ("Tel. 666 666 666", "Tel. 999 999 999", "Tél. 06 66 66 66 66"):
            with self.subTest(text=text):
                self.assertEqual(parse_phones(text), [])
        merged = one(parse_phones("Tel. 97525 1441"), "phone")  # 976 25 14 41 misread
        self.assertEqual(merged["strength"], "medium")
        self.assertTrue(any("probably a misread" in n for n in merged["notes"]))
        self.assertEqual(one(parse_phones("Tel. 975 25 14 41"), "phone")["strength"], "strong")
        self.assertEqual(one(parse_phones("Tel. 239·123·456"), "phone")["value"], "+351 239123456")
        self.assertEqual(one(parse_phones("Tfno. 976 25 14 41"), "phone")["details"]["phone_word"], "same line")

    def test_negatives(self):
        for text in ("NIF 234 567 890", "12345678", "1234567890123", "Ref. 912345678"):
            with self.subTest(text=text):
                self.assertEqual(parse_phones(text), [])


class PlateTest(unittest.TestCase):
    def test_formats(self):
        for text, value, country in (("12-AB-34", "12-AB-34", "PT"), ("12·AB·34", "12-AB-34", "PT"),
                                     ("AB 12 CD", "AB-12-CD", "PT"), ("12-34-AB", "12-34-AB", "PT"),
                                     ("1234 BCD", "1234 BCD", "ES"), ("AB-123-CD", "AB-123-CD", "FR")):
            with self.subTest(text=text):
                item = one(parse_plates(text), "plate")
                self.assertEqual((item["value"], item["countries"], item["strength"]), (value, [country], "weak"))
        self.assertIn("Italian plates share this pattern", one(parse_plates("AB-123-CD"), "plate")["notes"][0])

    def test_negatives(self):
        for text in ("1234 BCA", "AB-123-CI", "AB-123-OU", "Fundada em 1985 SRL"):
            with self.subTest(text=text):
                self.assertEqual(parse_plates(text), [])
        self.assertEqual(kinds(parse_text("AB-12-CD"), "road"), [])  # a plate, not the Albacete road AB-12


class RoadTest(unittest.TestCase):
    def test_portuguese_prefixes(self):
        for text, value in (("IP3", "IP3"), ("IC19", "IC19"), ("EN 125", "EN125"), ("EM 536", "EM536")):
            with self.subTest(text=text):
                item = one(parse_roads(text), "road")
                self.assertEqual((item["value"], item["countries"], item["strength"]), (value, ["PT"], "strong"))
        self.assertEqual(parse_roads("IC40"), [])  # IC runs 1-37

    def test_bare_a_and_n_fit_portugal_and_france(self):
        item = one(parse_roads("N125"), "road")
        self.assertEqual((item["countries"], item["strength"]), (["PT", "FR"], "medium"))
        self.assertEqual(one(parse_roads("Saída N 10-7"), "road")["value"], "N10-7")
        self.assertEqual(one(parse_roads("A 63"), "road")["countries"], ["FR"])  # PT motorways stop at A44

    def test_french_prefixes(self):
        self.assertEqual(one(parse_roads("D 914"), "road")["countries"], ["FR"])
        self.assertEqual(one(parse_roads("RD914"), "road")["strength"], "strong")
        self.assertEqual(one(parse_roads("T20"), "road")["details"]["meaning"], "Corsican route territoriale")
        self.assertEqual(parse_roads("T2"), [])  # a flat typology, not a Corsican road

    def test_spanish_hyphenated_prefixes(self):
        item = one(parse_roads("AP-7"), "road")
        self.assertEqual((item["countries"], item["regions"][0]["name"]), (["ES"], "national toll motorway"))
        self.assertEqual(one(parse_roads("CL-517"), "road")["regions"][0]["name"], "Castilla y León")
        self.assertEqual(one(parse_roads("EX-A1"), "road")["value"], "EX-A1")
        ambiguous = one(parse_roads("CA-33"), "road")
        self.assertIn("CA is ambiguous: Cantabria or Cádiz", ambiguous["notes"])
        self.assertEqual(ambiguous["details"]["city_road"], "Cádiz bay")
        self.assertEqual(one(parse_roads("SC-20"), "road")["details"]["city_road"], "Santiago de Compostela")
        self.assertEqual(parse_roads("XQ-12"), [])  # not a Spanish prefix

    def test_m_roads_are_ambiguous(self):
        item = one(parse_roads("M 506"), "road")
        self.assertEqual((item["countries"], item["strength"]), (["PT", "FR", "ES"], "weak"))

    def test_a_bare_letter_needs_a_sure_lone_reading(self):
        self.assertEqual(parse_roads("D3 LA"), [])                  # DE LA, with the E read as 3
        self.assertEqual(parse_roads("A46", confidence=0.6), [])    # an unsure reading
        self.assertEqual(kinds(parse_text("A46", confidence=0.6), "road"), [])
        self.assertEqual(one(parse_roads("A46"), "road")["countries"], ["FR"])
        self.assertEqual(one(parse_roads("Sortie 3, D 914", confidence=0.6), "road")["value"], "D914")  # road word
        self.assertEqual(one(parse_roads("EN 125", confidence=0.6), "road")["strength"], "strong")  # two letters

    def test_a_letter_and_digits_inside_other_text_is_not_a_road(self):
        for text in ("Bloco D3 Lote 4", "A4 paper", "Apartamento T2"):
            with self.subTest(text=text):
                self.assertEqual(parse_roads(text), [])
        self.assertEqual(one(parse_roads("Sortie 3, D 914"), "road")["strength"], "strong")  # a road word


class CodeTest(unittest.TestCase):
    def test_trail_codes_name_the_municipality(self):
        item = one(parse_trails("PR18 LLE"), "trail")
        self.assertEqual((item["countries"], item["strength"], item["regions"][0]["name"]), (["PT"], "strong", "Loulé"))
        unknown = one(parse_trails("GR 10 XYZ"), "trail")
        self.assertEqual((unknown["countries"], unknown["strength"]), ([], "weak"))

    def test_hunting_zones(self):
        zone, kind = parse_hunting_zones("ZONA DE CAÇA MUNICIPAL processo nº 3475-ICNF")
        self.assertEqual((zone["value"], zone["countries"], zone["strength"], zone["details"]["process_number"]),
                         ("3475-ICNF", ["PT"], "strong", 3475))
        self.assertEqual((kind["value"], kind["strength"]), ("ZCM", "medium"))
        self.assertEqual(one(parse_hunting_zones("3605-DGF"), "hunting_zone")["details"]["agency"], "DGF")
        self.assertEqual(one(parse_hunting_zones("ZONA DE CAÇA ASSOCIATIVA"), "hunting_zone")["value"], "ZCA")
        coto = one(parse_hunting_zones("COTO PRIVADO DE CAZA M-10.001"), "hunting_zone")
        self.assertEqual((coto["countries"], coto["regions"][0]["name"], coto["strength"]), (["ES"], "Madrid", "strong"))

    def test_municipal_codes(self):
        eredes = one(parse_municipal_codes("PNI-D-0011"), "municipal_code")
        self.assertEqual((eredes["value"], eredes["regions"][0]["name"]), ("PNI", "Peniche"))
        ctt = one(parse_text("4765-123 LORDELO GMR"), "municipal_code")
        self.assertEqual((ctt["regions"][0]["name"], ctt["strength"]), ("Guimarães", "strong"))
        self.assertEqual(parse_municipal_codes("ABC-D-0011"), [])

    def test_locality_and_municipal_code_without_postcode(self):
        items = parse_text("SERZEDELO GMR")
        code = one(items, "municipal_code")
        self.assertEqual((code["regions"][0]["name"], code["strength"]), ("Guimarães", "medium"))
        self.assertEqual([it["value"].upper() for it in kinds(items, "name")], ["SERZEDELO"])  # the code is not in it
        for text in ("PARQUE AND", "Serzedelo gmr", "RUA DO CARMO 12 GMR"):  # a word code, no capitals, digits
            with self.subTest(text=text):
                self.assertEqual(kinds(parse_text(text), "municipal_code"), [])


class MunicipalityTest(unittest.TestCase):
    def test_portuguese_phrases(self):
        for text, value, unit in (("CÂMARA MUNICIPAL DE VISEU", "VISEU", "municipality"),
                                  ("Câmara Municipal de Vila Nova de Gaia informa", "Vila Nova de Gaia", "municipality"),
                                  ("Junta de Freguesia de São Pedro, Rua 5", "São Pedro", "parish"),
                                  ("Município de Sintra", "Sintra", "municipality")):
            with self.subTest(text=text):
                item = one(parse_municipalities(text), "municipality")
                self.assertEqual((item["value"], item["countries"], item["details"]["unit"]), (value, ["PT"], unit))
        union = one(parse_municipalities("União das Freguesias de Lomba e Santo Isidoro"), "municipality")
        self.assertEqual(union["details"]["parts"], ["Lomba", "Santo Isidoro"])

    def test_spanish_and_french_phrases(self):
        for text, value, country in (("Ayuntamiento de Segovia", "Segovia", "ES"),
                                     ("Ajuntament d'Igualada", "Igualada", "ES"),
                                     ("Concello da Coruña", "A Coruña", "ES"),
                                     ("Bilboko Udala", "Bilbo", "ES"),
                                     ("Mairie de Bayonne", "Bayonne", "FR"),
                                     ("Mairie du Mans", "Le Mans", "FR")):
            with self.subTest(text=text):
                item = one(parse_municipalities(text), "municipality")
                self.assertEqual((item["value"], item["countries"], item["strength"]), (value, [country], "strong"))
        self.assertEqual(one(parse_municipalities("Concello de Lugo"), "municipality")["regions"][0]["name"], "Galicia")
        self.assertEqual(parse_municipalities("Câmara Municipal"), [])


class DomainOrganisationTest(unittest.TestCase):
    def test_country_and_regional_domains(self):
        for text, value, countries, strength in (("www.exemplo.pt", "exemplo.pt", ["PT"], "strong"),
                                                 ("info@exemplo.es", "exemplo.es", ["ES"], "strong"),
                                                 ("WWW.EXEMPLE.FR", "exemple.fr", ["FR"], "strong"),
                                                 ("exemple.cat", "exemple.cat", ["ES"], "medium"),
                                                 ("example.com", "example.com", [], "weak")):
            with self.subTest(text=text):
                item = one(parse_domains(text), "domain")
                self.assertEqual((item["value"], item["countries"], item["strength"]), (value, countries, strength))
        self.assertEqual(one(parse_domains("www.xunta.gal"), "domain")["regions"][0]["name"], "Galicia")
        self.assertEqual(one(parse_domains("sede.gva.es"), "domain")["regions"][0]["name"], "C. Valenciana")
        self.assertEqual(parse_domains("Sr. Silva e Av. Central"), [])

    def test_municipal_web_domains(self):
        item = one(parse_domains("geral@cm-vila-nova-de-gaia.pt"), "municipality")
        self.assertEqual((item["value"], item["countries"]), ("Vila Nova de Gaia", ["PT"]))
        self.assertEqual(kinds(parse_text("WWW.A22.PT"), "road"), [])  # inside a domain

    def test_organisations(self):
        for text, value, region in (("BreizhGo", "BreizhGo", "Bretagne"), ("Vamus Algarve", "Vamus Algarve", "Algarve"),
                                    ("XUNTA DE GALICIA", "Xunta de Galicia", "Galicia")):
            with self.subTest(text=text):
                item = one(parse_organisations(text), "organisation")
                self.assertEqual((item["value"], item["regions"][0]["name"]), (value, region))
        self.assertEqual(one(parse_organisations("Hôtel de Ville"), "organisation")["countries"], ["FR"])
        self.assertEqual(parse_organisations("Carrisso"), [])  # whole words only


class LanguageNameTest(unittest.TestCase):
    def test_spelling_cues(self):
        for text, lang in (("INFORMAÇÃO", "pt"), ("Señal", "es"), ("Col·legi", "ca"), ("Etxea", "eu"),
                           ("Œuvre", "fr")):
            with self.subTest(text=text):
                self.assertEqual([it["value"] for it in language_hints(text)], [lang])
        self.assertEqual(language_hints("PASTELARIA"), [])

    def test_name_candidates(self):
        self.assertEqual([it["value"] for it in name_candidates("Pastelaria Alfa")], ["Pastelaria Alfa"])
        for text in ("ENTRADA", "PAZ", "IlIl1", "Aluga-se", "TBC", "Hotel"):
            with self.subTest(text=text):
                self.assertEqual(name_candidates(text), [])
        self.assertEqual(name_candidates("Pastelaria Alfa", confidence=0.5), [])

    def test_names_come_from_the_text_between_other_items(self):
        items = parse_text("Rua das Flores, 12 1100-148 Ribeira Velha")
        self.assertEqual([it["value"] for it in kinds(items, "name")], ["Rua das Flores, 12", "Ribeira Velha"])
        self.assertEqual([it["value"] for it in kinds(parse_text("75011 PARIS"), "name")], ["PARIS"])


class ParseTest(unittest.TestCase):
    def test_parse_text_combines_kinds_without_overlaps(self):
        items = parse_text("Câmara Municipal de Viseu | www.cm-viseu.pt | Tel. 232 123 456")
        self.assertEqual(sorted({it["kind"] for it in items}), ["domain", "municipality", "phone"])
        self.assertEqual(sorted(it["value"] for it in kinds(items, "municipality")), ["Viseu", "Viseu"])
        self.assertEqual(one(items, "phone")["regions"][0]["name"], "Viseu")
        for a in items:
            for b in items:
                if a is not b and a["span"] != b["span"]:
                    self.assertFalse(a["span"][0] < b["span"][1] and b["span"][0] < a["span"][1], (a, b))

    def test_items_are_json_ready(self):
        json.dumps(parse_text("C.P. 28013 Madrid · Tel. 91 234 56 78 · www.exemplo.es · AP-7"))

    def test_parse_sign_adds_what_only_an_alternative_shows(self):
        s = sign("Tel. 239 123 456", conf=0.9)
        s.hits.append(hit("Tel. 239 123 466", 45.1, 0.0, view="h090", conf=0.8))
        items = parse_sign(s)
        phones = kinds(items, "phone")
        self.assertEqual([(p["value"], p["source"]) for p in phones],
                         [("+351 239123456", "reading"), ("+351 239123466", "alternative")])
        self.assertTrue(all(p["sign_id"] == "s1" for p in phones))

    def test_agreeing_readings_are_counted(self):
        s = sign("Tel. 239 123 456")
        s.hits.append(hit("TEL 239 123 456", 45.1, 0.0, view="h090", conf=0.9))
        self.assertEqual(one(parse_sign(s), "phone")["readings"], 2)
        s.reread = {"text": "Tel 239 123 456", "confidence": 0.99}
        self.assertEqual(one(parse_sign(s), "phone")["readings"], 3)
        s.hits.append(hit("Tel 239 123 466", 45.2, 0.0, view="h045", conf=0.7))
        self.assertEqual([(p["value"], p["readings"]) for p in kinds(parse_sign(s), "phone")],
                         [("+351 239123456", 3), ("+351 239123466", 1)])

    def test_panel_context(self):
        top, number = sign("ALUGA-SE", pitch=1.0, sign_id="s1"), sign("961 222 333", pitch=-0.5, sign_id="s2")
        far = sign("Tel.", yaw=120.0, sign_id="s3")
        self.assertEqual(panel_context(number, [top, number, far]), "ALUGA-SE")
        self.assertEqual(one(parse_sign(number, "ALUGA-SE"), "phone")["strength"], "medium")

    def test_cleaning(self):
        self.assertEqual(clean_reading("961 222 333 口"), "961 222 333")
        self.assertEqual(clean_reading("目日"), "")
        self.assertEqual(clean_reading("ＴＥＬ１２"), "TEL12")
        self.assertTrue(looks_like_strokes("IIIIl") and looks_like_strokes("I1|l"))
        self.assertFalse(looks_like_strokes("Ill1a") or looks_like_strokes("l"))


class GeometryTest(unittest.TestCase):
    def test_box_overlap(self):
        a = {"yaw": 50.0, "pitch": 0.0, "w": 4.0, "h": 2.0}
        self.assertAlmostEqual(box_overlap(a, a), 1.0)
        self.assertAlmostEqual(box_overlap(a, {**a, "yaw": 52.0}), 0.5)
        self.assertEqual(box_overlap(a, {**a, "yaw": 60.0}), 0.0)
        self.assertEqual(box_overlap(a, {**a, "pitch": 3.0}), 0.0)
        small = {"yaw": 50.5, "pitch": 0.2, "w": 1.0, "h": 1.0}
        self.assertAlmostEqual(box_overlap(a, small), 1.0)  # over the smaller box
        self.assertAlmostEqual(box_inside(small, a), 1.0)
        self.assertAlmostEqual(box_inside(a, small), 0.125)

    def test_the_yaw_seam(self):
        a = {"yaw": 359.0, "pitch": 5.0, "w": 4.0, "h": 2.0}
        b = {"yaw": 1.0, "pitch": 5.0, "w": 4.0, "h": 2.0}
        self.assertGreater(box_overlap(a, b), 0.45)
        self.assertGreater(box_overlap(b, a), 0.45)

    def test_text_similarity(self):
        self.assertEqual(text_similarity("Gestão", "GESTAO"), 1.0)
        self.assertGreater(text_similarity("PASTELARIA AL", "PASTELARIA ALFA"), 0.9)  # a cut-off copy
        self.assertGreater(text_similarity("TEL 239 123 456", "TEL 239 123 466"), 0.9)
        self.assertLess(text_similarity("FARMACIA", "PADARIA SÃO JOSÉ"), 0.6)
        self.assertLess(text_similarity("PAZ", "CENTRO DE ESTUDOS"), 0.6)


class DedupTest(unittest.TestCase):
    def test_two_views_of_one_sign_merge(self):
        signs = dedup([hit("FARMÁCIA CENTRAL", 44.0, 5.0, view="h000", conf=0.91),
                       hit("FARMACIA CENTRAL", 44.3, 5.1, view="h045", conf=0.97)])
        self.assertEqual(len(signs), 1)
        self.assertEqual((signs[0].text, signs[0].views), ("FARMACIA CENTRAL", ["h000", "h045"]))
        self.assertEqual(signs[0].alternatives, [])  # the same text once accents are ignored

    def test_merge_across_the_yaw_seam(self):
        signs = dedup([hit("PADARIA NOVA", 359.6, 2.0, view="h315"), hit("PADARIA NOVA", 0.2, 2.0, view="h000")])
        self.assertEqual(len(signs), 1)
        self.assertEqual(signs[0].views, ["h000", "h315"])

    def test_same_text_elsewhere_and_other_text_nearby_stay_apart(self):
        signs = dedup([hit("PADARIA NOVA", 10.0, 2.0, view="h000"), hit("PADARIA NOVA", 100.0, 2.0, view="h090"),
                       hit("ALUGA-SE", 50.0, 1.2, h=1.9, view="h045"), hit("961 222 333", 50.0, 0.3, h=1.9, view="h045"),
                       hit("ALUGA-SE", 50.1, 1.2, h=1.9, view="h090"), hit("961 222 333", 50.1, 0.3, h=1.9, view="h090")])
        self.assertEqual(sorted((s.text, len(s.hits)) for s in signs),
                         [("961 222 333", 2), ("ALUGA-SE", 2), ("PADARIA NOVA", 1), ("PADARIA NOVA", 1)])

    def test_a_sign_takes_one_hit_per_view(self):
        signs = dedup([hit("RUA DO SOL", 10.0, 0.0, view="h000"), hit("RUA DO SOL", 13.0, 0.0, view="h000"),
                       hit("RUA DO SOL", 13.1, 0.0, view="h045")])
        self.assertEqual(sorted(len(s.hits) for s in signs), [1, 2])
        pair = next(s for s in signs if len(s.hits) == 2)
        self.assertAlmostEqual(pair.box["yaw"], 13.0, delta=0.2)

    def test_a_cut_off_part_loses_even_when_its_box_misses_the_border(self):
        signs = dedup([hit("123 456", 56.0, -5.0, w=23.0, h=7.4, view="h090", conf=0.998),
                       hit("TEL. 239 123 456", 44.9, -5.0, w=47.3, h=6.8, view="h045", conf=0.989),
                       hit("TEL. 239", 34.5, -5.0, w=24.4, h=8.0, view="h000", conf=0.981, at_edge=True)])
        self.assertEqual(len(signs), 1)
        self.assertEqual((signs[0].text, signs[0].hits[0].view), ("TEL. 239 123 456", "h045"))
        self.assertAlmostEqual(signs[0].box["w"], 47.3)
        noisy = dedup([hit("PADARIA NOVA", 30.0, 0.0, view="h000", conf=0.97),
                       hit("PADARIA NOVA 1111111", 30.5, 0.0, w=8.0, view="h045", conf=0.55)])
        self.assertEqual(noisy[0].text, "PADARIA NOVA")  # a much less confident longer copy doesn't win

    def test_a_copy_cut_by_a_view_border_loses_to_a_complete_one(self):
        signs = dedup([hit("PASTELARIA AL", 44.0, 0.0, w=10.0, view="h000", conf=0.99, at_edge=True),
                       hit("PASTELARIA ALFA", 45.0, 0.0, w=12.0, view="h045", conf=0.93)])
        self.assertEqual(len(signs), 1)
        self.assertEqual(signs[0].text, "PASTELARIA ALFA")
        self.assertEqual([a["text"] for a in signs[0].alternatives], ["PASTELARIA AL"])
        self.assertFalse(signs[0].truncated)

    def test_fragments_are_absorbed(self):
        whole = Sign("s1", "PADARIA SÃO JOSÉ", 0.95, {"yaw": 30.0, "pitch": 0.0, "w": 10.0, "h": 2.0},
                     [hit("PADARIA SÃO JOSÉ", 30.0, 0.0, w=10.0, h=2.0)])
        part = Sign("s2", "SÃO JOSÉ", 0.97, {"yaw": 32.5, "pitch": 0.0, "w": 4.0, "h": 2.0},
                    [hit("SÃO JOSÉ", 32.5, 0.0, w=4.0, h=2.0, view="h045")])
        kept = absorb_fragments([whole, part])
        self.assertEqual([s.sign_id for s in kept], ["s1"])
        self.assertEqual(kept[0].views, ["h000", "h045"])

    def test_coincident_boxes_merge_whatever_they_say(self):
        signs = dedup([hit("5", 20.0, -3.0, w=1.0, h=1.4, view="h000"), hit("S", 20.05, -3.0, w=1.0, h=1.4, view="h045")])
        self.assertEqual(len(signs), 1)


class RereadLogicTest(unittest.TestCase):
    def test_which_signs_are_reread(self):
        self.assertTrue(needs_reread(sign("TEL 239", conf=0.8, height=40)))
        self.assertFalse(needs_reread(sign("TEL 239", conf=0.8, height=80)))  # tall: not short of pixels
        self.assertTrue(needs_reread(sign("TEL 239", conf=0.99, height=20)))  # small
        self.assertTrue(needs_reread(sign("TEL 239", conf=0.99, height=40, at_edge=True)))  # cut in every view
        self.assertFalse(needs_reread(sign("TEL 239", conf=0.99, height=40)))
        self.assertFalse(needs_reread(sign("5", conf=0.5, height=10)))
        self.assertFalse(needs_reread(sign("A LONG LINE", conf=0.6, height=20, w=50.0)))  # wider than any crop

    def test_digits_first(self):
        signs = [sign("PADARIA", conf=0.6, sign_id="s1"), sign("239 123", conf=0.85, sign_id="s2"),
                 sign("XX", conf=0.4, sign_id="s3")]
        self.assertEqual([s.sign_id for s in sorted(signs, key=reread_priority)], ["s2", "s1", "s3"])

    def test_crop_hits_on_the_line_are_picked_and_joined(self):
        target = {"yaw": 50.0, "pitch": 10.0, "w": 6.0, "h": 1.5}
        words = [hit("239", 48.4, 10.05, w=2.6, h=1.4), hit("123 456", 51.4, 9.95, w=3.0, h=1.5)]
        above = hit("ALUGA-SE", 50.0, 10.9, w=5.0, h=1.5)   # the next line up: centres 0.9 apart
        banner = hit("CAFE", 50.0, 10.5, w=6.0, h=4.0)      # a much taller sign behind
        self.assertEqual([picks_for(target, h) for h in words + [above, banner]], [True, True, False, False])
        text, conf, coverage = combine_reread(words + [above, banner], target)
        self.assertEqual(text, "239 123 456")
        self.assertGreater(coverage, 0.9)
        self.assertAlmostEqual(conf, 0.95)
        self.assertIsNone(combine_reread([above, banner], target))
        whole_line = hit("TEL 239 123 456", 44.0, 10.0, w=20.0, h=1.5)  # runs well past the target's left end
        self.assertFalse(picks_for(target, whole_line))
        self.assertTrue(picks_for(target, whole_line, extend=True))  # for a sign cut in every view


class LogTest(unittest.TestCase):
    def test_signs_and_items_are_logged_and_linked(self):
        s = sign("Tel. 239 123 456", yaw=45.0, pitch=-5.0)
        items = parse_sign(s)
        for i, item in enumerate(items, 1):
            item["item_id"] = f"i{i}"
        result = OcrResult([s], [], items, list(s.hits), {}, {}, {"model": "PP-OCRv6-medium"}, [])
        with tempfile.TemporaryDirectory() as tmp:
            run = Run("IMG_20260101_120000_00_001.jpg", tmp)
            with run.stage("read", model="PP-OCRv6-medium"):
                ids = log_ocr(run, result)
            evidence = [e for e in run.events if e["type"] == "evidence.added"]
        self.assertEqual([e["payload"]["kind"] for e in evidence], ["ocr_text", "phone"])
        text, phone = (e["payload"] for e in evidence)
        self.assertEqual(ids, {"s1": text["evidence_id"]})
        self.assertEqual((text["text"], text["views"], text["in_photographer_zone"]), (s.text, ["h000"], False))
        self.assertEqual(text["box"], s.box)
        self.assertEqual((phone["ocr_evidence_id"], phone["value"], phone["countries"]),
                         (text["evidence_id"], "+351 239123456", ["PT"]))
        self.assertTrue(all(e["stage"] == "read" and e["model"] == "PP-OCRv6-medium" for e in evidence))


def _models_ready():
    try:
        folder = ocr.models_dir()
    except ImportError:
        return False
    files = [ocr.DET_MODELS[ocr.DEFAULT_MODEL][3], ocr.REC_MODELS[ocr.DEFAULT_MODEL][3], ocr.CLS_MODEL[3]]
    return all((folder / f).is_file() for f in files)


def rendered_panorama():
    """A 4096 x 2048 panorama with black-on-white text: a shop name above a phone, centred on yaw 45 and too
    wide for a reread crop, and a small mobile number at yaw 135, under REREAD_SMALL_PX in a 768 view."""
    width, height = 4096, 2048
    im = Image.new("RGB", (width, height), (110, 125, 135))
    draw = ImageDraw.Draw(im)
    for text, yaw, pitch, size in (("PASTELARIA ALFA", 45.0, 5.0, 60), ("TEL. 239 123 456", 45.0, -5.0, 60),
                                   ("TLM 961 222 333", 135.0, 0.0, 30)):
        font = ImageFont.truetype(str(FONT), size)
        x, y = sphere_to_pano_xy(yaw, pitch, width, height)
        left, top, right, bottom = draw.textbbox((0, 0), text, font=font)
        w, h = right - left, bottom - top
        pad = size // 3
        draw.rectangle([x - w / 2 - pad, y - h / 2 - pad, x + w / 2 + pad, y + h / 2 + pad], fill=(250, 250, 250))
        draw.text((x - w / 2 - left, y - h / 2 - top), text, fill=(15, 15, 15), font=font)
    return np.array(im)


@unittest.skipUnless(FONT.is_file() and _models_ready(), "needs DejaVu Sans and the RapidOCR models")
class EngineTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.engine = ocr.Engine()
        cls.pano = rendered_panorama()
        cls.views = [cut_view(cls.pano, yaw, 0, 90, 768, name=f"h{yaw:03d}") for yaw in (0, 45, 90, 135)]
        cls.result = ocr.read_panorama(cls.pano, cls.engine, views=cls.views)

    def test_reads_dedups_and_parses_the_rendered_text(self):
        signs = self.result.signs
        shop = [s for s in signs if "pastel" in ocr.text_key(s.text)]
        self.assertEqual(len(shop), 1, [s.text for s in signs])  # the cut-off copies in h000/h090 merged
        self.assertIn("pastelariaalfa", ocr.text_key(shop[0].text))
        self.assertIn("h045", shop[0].views)
        self.assertAlmostEqual(shop[0].box["yaw"], 45.0, delta=3.0)
        self.assertAlmostEqual(shop[0].box["pitch"], 5.0, delta=1.5)
        phone = next(p for p in kinds(self.result.items, "phone") if p["value"] == "+351 239123456")
        self.assertEqual((phone["countries"], phone["strength"], phone["source"]), (["PT"], "strong", "reading"))
        self.assertEqual(phone["regions"][0]["name"], "Coimbra")
        phone_sign = self.result.sign(phone["sign_id"])
        self.assertAlmostEqual(phone_sign.box["pitch"], -5.0, delta=1.5)
        self.assertIn("PASTELARIA ALFA", [it["value"] for it in kinds(self.result.items, "name")])
        for key in ("load_average_1m", "views_s", "read_views_s", "detection_s", "recognition_s", "rereads_s", "total_s"):
            self.assertIn(key, self.result.timing)
        self.assertGreater(self.result.timing["detection_s"], 0)
        self.assertEqual(self.result.engine["model"], "PP-OCRv6-medium")

    def test_the_small_line_is_reread_at_full_resolution(self):
        small = next(s for s in self.result.signs if "961222333" in ocr.text_key(s.text))
        self.assertLess(small.height_px, ocr.REREAD_SMALL_PX)
        self.assertIsNotNone(small.reread)
        self.assertIn("961222333", ocr.text_key(small.reread["text"] or ""))
        self.assertIn(small.reread["outcome"], ("chosen", "not_better"))
        self.assertEqual(small.reread["size_px"], max(small.reread["native_px"], ocr.REREAD_MIN_SIZE))
        self.assertGreaterEqual(self.result.rereads["attempted"], 1)
        mobile = next(p for p in kinds(self.result.items, "phone") if p["value"] == "961222333")
        self.assertEqual((mobile["countries"], mobile["strength"]), (["PT", "ES"], "medium"))  # "TLM" is a phone word
        wide = next(s for s in self.result.signs if "pastel" in ocr.text_key(s.text))
        self.assertFalse(ocr.needs_reread(wide))  # wider than any reread crop

    def test_downloads_are_refused(self):
        from rapidocr.utils.download_file import DownloadFile, DownloadFileInput
        with ocr._no_downloads(), self.assertRaises(RuntimeError):
            DownloadFile.run(DownloadFileInput(file_url="https://example.invalid/x.onnx", save_path="/nonexistent/x",
                                               logger=None))
        self.assertIsInstance(DownloadFile.__dict__["run"], classmethod)  # restored afterwards

    def test_unknown_models_are_refused(self):
        with self.assertRaises(ValueError):
            ocr.Engine(det="PP-OCRv9")

    def test_cli_writes_ocr_json_and_debug_images(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "IMG_20260101_120000_00_001.jpg"
            Image.fromarray(self.pano).resize((2048, 1024)).save(path, quality=85)
            out = Path(tmp) / "out"
            with contextlib.redirect_stdout(io.StringIO()) as stdout:
                code = ocr.main([str(path), "--out", str(out), "--size", "384", "--no-rereads", "--debug"],
                                engine=self.engine)
            self.assertEqual(code, 0)
            doc = json.loads((out / "ocr.json").read_text(encoding="utf-8"))
            self.assertEqual((doc["schema"], doc["panorama"]), (ocr.SCHEMA, path.name))
            self.assertEqual(len(doc["views"]), 10)
            for key in ("signs", "items", "rereads", "hits", "low_confidence", "engine"):
                self.assertIn(key, doc)
            self.assertIn("load_s", doc["timing"])
            for name in ("panorama.jpg", "h045.jpg", "ground.jpg"):
                self.assertTrue((out / "debug" / name).is_file(), name)
            self.assertIn("timing:", stdout.getvalue())


if __name__ == "__main__":
    unittest.main()
