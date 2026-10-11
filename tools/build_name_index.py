#!/usr/bin/env python3
"""Build the name index Data/index/names.sqlite read by panoloc.names (TASKS.md T16, PLAN.md 4.4).

The inputs are downloaded files, so they are treated as untrusted. Every row is checked (field
count, identifiers, finite WGS84 coordinates, known countries), and bad rows are skipped and counted
in the build report. SQL is always parameterised.
  Data/wikidata/wikidata_ptesfr.csv.gz              items with coordinates (tools/fetch_wikidata.py)
  Data/geo/geonames/places/{PT,ES,FR}/{CC}.txt      GeoNames gazetteer dumps
  Data/geo/geonames/postcodes/{PT,ES,FR}/{CC}.txt   GeoNames postal codes
  Data/geo/geonames/featureCodes_en.txt, admin1CodesASCII.txt, admin2Codes.txt   names for codes (optional)

The index is written to <out>.tmp-<pid> and renamed over <out> only when complete. A failed run
leaves the previous index in place, and a rerun always rebuilds from scratch. SQLite's sort spills
and the staging database go to the output folder, never to /tmp (a RAM disk on the dev laptop).
  place        one row per Wikidata item or GeoNames entry: point, role, extent, prominence, group, details
  name         one row per (place, normalised name), in descending prominence (rowid order), with the
               squashed and core keys of panoloc.names.keys() indexed for exact and variant matches
  ftok, tokdf  FTS5 word index over name.norm ("contains" matches), and the number of names per word
  fkey, fgram  distinct core keys, and their trigram postings per key length (fuzzy matches)
  link         Wikidata/GeoNames pairs sharing a name within LINK_RADIUS_M (for two large areas, half the
               smaller extent, up to LINK_MAX_M), stored in both directions
  postcode     PT 4-3, ES and FR codes and PT 4-digit prefixes, each aggregated over its rows
  meta         schema, build time, input files (size, mtime, sha256), counts, constants, rule tables

Roles and extents. Settlements, administrative units, natural extents (parks, lakes, mountains,
beaches, forests), streets and squares are `area`. Buildings, monuments, shops, stations, bridges and
other objects are `landmark`. Nothing is `camera`. Neither source gives an extent, so extent_m is an
assumed radius, and details["extent_source"] is "assumed":
  Wikidata  WIKIDATA_RULES, by P31 type label. Each type takes the first rule that matches it; the
            item takes the role of its highest-priority rule and the largest extent among its rules
            with that role. Untyped or unmatched items are landmarks of 100 m. Items whose only types
            are events (battles, festivals, races) are left out: they are not places. When an item's
            own coordinates spread wider than its extent, the spread is used and the source is "source".
  GeoNames  GEONAMES_EXTENTS, by feature code; admin units by country (GEONAMES_ADMIN). Populated
            places with a population use 450 m x (population / 1000)^0.4, between 250 m and 15 km.
            Feature classes A, H, L, P, R, T, U and V are areas and S (spots, buildings) landmarks,
            except the codes in GEONAMES_LANDMARK_CODES and GEONAMES_AREA_CODES.
  Postcode  each row's point gets POSTCODE_EXTENT for its accuracy flag, adjusted by the populated
            place (else admin unit) it names within POSTCODE_PLACE_M: a point shared by several codes
            is that place's centroid and takes its whole extent; a code's own point is only narrowed.
            A code covers all its rows, and a PT prefix all its codes.

Usage (from the repo root; -I because it reads downloaded files):
  python3 -I tools/build_name_index.py              # ~70 s, 1.4 GB file, ~1.1 GB peak RAM (2026-10-10 data)
  python3 -I tools/build_name_index.py --out Data/index/names.sqlite --wikidata FILE --geonames DIR
"""
import argparse
import array
import csv
import gzip
import hashlib
import json
import math
import os
import re
import resource
import sqlite3
import sys
import time
import unicodedata
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from panoloc import names as N  # noqa: E402
from panoloc.scoring import haversine_m  # noqa: E402

DEFAULT_WIKIDATA = ROOT / "Data" / "wikidata" / "wikidata_ptesfr.csv.gz"
DEFAULT_GEONAMES = ROOT / "Data" / "geo" / "geonames"

LINK_RADIUS_M = 1000.0
LINK_MAX_M = 5000.0
LANGS = ("pt", "es", "fr", "en", "ca", "gl", "eu", "mul")
LABEL_LANGUAGE = {"PT": "pt", "ES": "es", "FR": "fr"}
MAX_NAMES = 60  # per place: GeoNames lists hundreds of transliterations for big places
MAX_NAME_CHARS = 200
MAX_LIST = 10  # types, heritage designations and P131 values kept in details
BATCH = 20_000
QID = re.compile(r"^Q[1-9]\d{0,11}$")
POSTCODE_FORMAT = {"PT": re.compile(r"^\d{4}-\d{3}$"), "ES": re.compile(r"^\d{5}$"), "FR": re.compile(r"^\d{5}$")}

# -- Wikidata roles: (rule, role, extent_m, pattern on the lowercased English P31 label) -------------
# Order is priority. "ignore" types say nothing about the object's form; "skip" types are events.
WIKIDATA_RULES = [
    ("generic", "ignore", 0, r"^(cultural heritage|cultural property|cultural asset|architectural heritage monument|"
     r"heritage site|world heritage site|tourist attraction|tourist destination|historic monument|"
     r"monument historique.*|listed building|protected building|national monument|bien de interés cultural|"
     r"architectural landmark|landmark|point of interest|geographic location|geographical (feature|object)|"
     r"geographic (entity|feature)|location|physical object|artificial geographic entity|"
     r"artificial physical structure|structure|built structure|construction|infrastructure|object|entity|site|"
     r"space|area|zone|territory|destroyed building or structure|demolished building|former building|"
     r"architectural structure|monument \(spain\)|immovable cultural heritage|property|real property|item|"
     r"fixed construction|human-geographic territorial entity|historic grouping|group|water depth|set)$"),
    # labels ending in an event word, caught before "railway", "football" or "festival hall" style rules
    ("event", "skip", 0, r"\b(accident|battle|siege|edition|season|ceremony|tournament|championship|festival|"
     r"competition|race|election|massacre|attack|bombing|earthquake|flood|wildfire|shipwreck|crash|disaster|"
     r"expedition|treaty|strike|protest|uprising|revolt|rebellion|war|invasion|event|incident|concert|marathon|"
     r"combat)$"),
    # settlements and administrative units
    ("country", "area", 300_000, r"^(country|sovereign state|nation state|realm|unitary state)$"),
    ("first-level region", "area", 120_000, r"^(autonomous community( of spain)?|region of france|"
     r"overseas (region|collectivity|department)( of france)?|administrative region|"
     r"autonomous region( of portugal)?|nationality|historic nationality)$"),
    ("province", "area", 45_000, r"^(province( of spain)?|department of france|metropolitan department|"
     r"district of portugal|historical province( of france)?|former province.*)$"),
    ("region", "area", 30_000, r"^(region|historical region|natural region( of .+)?|geographic(al)? region|"
     r"cultural region|wine region|traditional region|historical territory|comarca( of .+)?|pays|landscape)$"),
    ("arrondissement", "area", 25_000, r"^(arrondissement( of france)?|county|district|historical district)$"),
    ("metropolitan area", "area", 15_000, r"(metropolitan area|urban area|functional area|agglomeration|"
     r"intercommunality|"
     r"metropolis of france|intermunicipal|community of (communes|municipalities|agglomeration)|urban community|"
     r"mancomunidad|public institution of intermunicipal cooperation)"),
    ("canton", "area", 10_000, r"^(canton( of france)?|electoral (unit|district|constituency)|constituency|"
     r"judicial district|legislative constituency|parliamentary constituency)$"),
    ("municipality of portugal", "area", 10_000, r"^(municipality of portugal|concelho)$"),
    ("big city", "area", 8_000, r"^(big city|large city|metropolis|million city|global city|megacity|megalopolis|"
     r"largest city|national capital|capital city|capital|primate city|regional capital|cultural capital|"
     r"financial cent(er|re)|commercial capital city|fashion capital)$"),
    ("urban unit", "area", 5_000, r"^urban unit$"),
    ("city", "area", 4_000, r"^(city|city of (portugal|spain|france)|border city|port city|university city|"
     r"college town|provincial capital|capital of .+|cathedral city|imperial city|royal city|urban municipality)$"),
    ("municipality", "area", 5_000, r"^(municipality|municipality of .+|former municipality( of .+)?|"
     r"council of asturies)$"),
    ("parish", "area", 3_000, r"^(freguesia( of portugal)?|former freguesia of portugal|union of freguesias|"
     r"civil parish( of .+)?|parish|parish of (asturias|galicia|cantabria)|parroquia|"
     r"collective population entity of spain)$"),
    ("admin unit", "area", 3_000, r"^administrative territorial entity\b.*$"),
    ("commune", "area", 2_500, r"^(commune( of france)?|former commune( of france)?|delegated commune|"
     r"associated commune|commune nouvelle|municipal arrondissement|arrondissement of (paris|lyon|marseille)|"
     r"municipal district)$"),
    ("town", "area", 1_500, r"^(town|town of portugal|market town|fortified town|spa town|county seat|"
     r"municipality capital|municipality seat|vila|villa \(spain\)|bastide|new town|ville|chef-lieu|"
     r"medieval town|historic town|resort town|seaside resort|company town)$"),
    ("minor entity", "area", 1_200, r"^(minor local entity of spain|concejo( of .+)?|council of navarre|pedanía|"
     r"entidad local menor|parçan of occitania|partida|section of commune)$"),
    ("village", "area", 600, r"^(village|village of .+|rural village|abandoned village|deserted village|"
     r"ghost town|aldeia|aldea|historic village|perched village|fishing village|mountain village|schist village)$"),
    ("settlement", "area", 800, r"^(human settlement|settlement|single entity of population|"
     r"nucleus of singular population entity|populated place nucleus|populated place|locality|"
     r"catalan historical locality|urban settlement|rural settlement|dispersed settlement|colony|"
     r"unincorporated community|census-designated place|former settlement)$"),
    ("hamlet", "area", 300, r"^(hamlet|lugar|lugar of .+|settlement in galicia|lieu-dit( \(france\))?|caserío|"
     r"alquer[ií]a|casal|cortijada|quintana)$"),
    ("neighbourhood", "area", 700, r"^(neighbou?rhood|quarter|city district|district of .+|urban district|barrio|"
     r"bairro|barri|suburb|residential (area|district|neighbou?rhood)|housing estate|cité|"
     r"priority neighbou?rhood|old town|historic (centre|center|district|quarter|urban area)|urban ensemble|"
     r"subdivision|ward|administrative quarter.*|quartier|neighbou?rhood of .+)$"),
    ("industrial zone", "area", 500, r"^(industrial (zone|area|estate|park|district|site)|business (park|district)|"
     r"technology (park|cent(er|re))|science park|commercial zone|economic zone|logistics (park|platform)|"
     r"development|zone d'aménagement concerté|activity zone)$"),
    # buildings and other objects
    ("heliport", "landmark", 50, r"^heliport$"),
    ("cathedral", "landmark", 60, r"\b(cathedral|basilica|co-cathedral|collegiate church)\b"),
    ("monastery", "landmark", 80, r"\b(monastery|convent|abbey|priory|charterhouse|friary|commandery|commandry|"
     r"cloister|seminary|beguinage|nunnery)\b"),
    ("sanctuary", "landmark", 100, r"^(sanctuary|marian shrine|pilgrimage site|shrine complex)$"),
    ("chapel", "landmark", 12, r"\b(chapel|oratory|hermitage|ermita|shrine|niche)\b"),
    ("church", "landmark", 25, r"\b(church|temple|synagogue|mosque|place of worship|religious building|kirk)\b"),
    ("city walls", "landmark", 300, r"\b(city walls?|town walls?|defensive walls?|ramparts?|fortified enclosure|"
     r"wall)\b"),
    ("hillfort", "landmark", 150, r"\b(hillfort|castro|oppidum|citania)\b"),
    ("castle", "landmark", 80, r"\b(castle|château|chateau|fortress|citadel|alcazaba|alcázar|alcazar|kasbah|"
     r"fortification|fort|bastion|redoubt|fortified (house|tower|church|farm|gate|manor|building)|keep|donjon|"
     r"motte|star fort|stronghold)\b"),
    ("palace", "landmark", 80, r"\b(palace|palacio|palácio|pazo|royal residence|official residence)\b"),
    ("viewpoint", "landmark", 30, r"\b(scenic viewpoint|viewpoint|lookout|observation deck|belvedere|miradouro|"
     r"mirador)\b"),
    ("estate", "area", 300, r"^(manor estate|country estate|estate|quinta|finca|hacienda|landed estate|"
     r"fighting bull breeding)$"),
    ("ancient city", "landmark", 400, r"^(ancient city|roman city|lost city|ancient settlement|roman town)$"),
    ("archaeological site", "landmark", 100, r"\b(archaeological site|roman villa|villa rustica|"
     r"(?<!national )necropolis|ancient roman structure|roman archaeological site|archaeological remains|"
     r"excavation|ruins?|remains|prehistoric site|iberian settlement|samian ware discovery site|thermae|"
     r"roman baths)\b"),
    ("megalith", "landmark", 10, r"\b(dolmen|menhir|cromlech|megalith|megalithic .+|tumulus|gallery grave|"
     r"standing stone|stone circle|cairn|petroglyph|rock art|rock engraving|cave painting|stele|stela|cist|"
     r"barrow|burial mound|talaiot|anta|stone row|hypogeum|naveta|taula)\b"),
    ("tower", "landmark", 20, r"\b(towers?|watchtower|belfry|bell tower|campanile|minaret|lighthouse|skyscraper|"
     r"chimney|flue-gas stack|water tower|obelisk|column|spire|mast|antenna|transmitter|clock tower)\b"),
    ("viaduct", "landmark", 300, r"\b(viaduct|aqueduct)\b"),
    ("bridge", "landmark", 100, r"\b(bridge|footbridge|overpass)\b"),
    ("tunnel", "landmark", 300, r"\btunnel\b"),
    ("dam", "landmark", 150, r"\b(dam|weir|barrage)\b"),
    ("pier", "landmark", 100, r"\b(pier|jetty|breakwater|mole|groyne|landing stage|wharf|slipway)\b"),
    ("lock", "landmark", 20, r"^(lock|canal lock|lock keeper's house)$"),
    ("parking", "landmark", 50, r"\b(car park|parking( lot| garage| space)?|multi-storey car park|park and ride)\b"),
    ("station", "landmark", 100, r"\b(railway station|train station|railway stop|railway halt|halt|"
     r"station located on surface|goods station|former railway station|terminus|dead-end railway station|"
     r"passenger station|interchange station|high-speed railway station|bus station|ferry terminal|"
     r"port terminal|funicular station|cable car station|transport hub|railway terminal)\b"),
    ("metro station", "landmark", 50, r"\b(metro station|underground station|subway station|s-bahn station|"
     r"rapid transit station|light rail station|tram station|rer station)\b"),
    ("stop", "landmark", 15, r"\b(tram stop|bus stop|public transport stop|stop|bicycle-sharing station|taxi stand|"
     r"bus shelter)\b"),
    ("toll plaza", "landmark", 100, r"\b(toll (plaza|station|gate)|border (crossing|checkpoint)|checkpoint|"
     r"customs post|service area|rest area)\b"),
    ("stadium", "landmark", 120, r"\b(stadium|arena|bullring|plaza de toros|velodrome|racecourse|race ?track|"
     r"horse racing venue|hippodrome|motor racing circuit|motorsport racing track)\b"),
    ("sports venue", "landmark", 50, r"\b(sports venue|sports (hall|cent(er|re)|facility|ground|complex|field)|"
     r"gymnasium|swimming pool|pitch|association football (pitch|venue)|football (pitch|field|ground)|"
     r"rugby (union |league )?venue|tennis court|skate ?park|ice rink|ski jump|shooting range|boulodrome|"
     r"pétanque|fronton|pelota court|bowling|climbing (wall|area|site)|multi-purpose hall|multisport|"
     r"basketball court|handball court|golf club|athletics (track|stadium)|gym|free flight site|"
     r"paragliding (site|takeoff))\b"),
    ("hospital", "landmark", 100, r"\b(hospital|sanatorium|asylum|leprosarium|hospital complex)\b"),
    ("clinic", "landmark", 25, r"\b(clinic|health (cent(er|re)|facility|post)|medical (cent(er|re)|organization)|"
     r"nursing home|retirement home|accommodation facility for dependent elderly people|hospice|care home|"
     r"doctor's office|dispensary|pharmacy|medical practice)\b"),
    ("university", "landmark", 200, r"\b(university|faculty|polytechnic|higher education institution)\b"),
    ("school", "landmark", 50, r"\b(school|lycée|lycee|collège|college|educational (facility|institution)|"
     r"kindergarten|nursery|institute|institut|ies|academy|conservatory|cité scolaire|grande école|"
     r"center for early childhood and primary education|training (centre|center)|"
     r"(public|private) educational institution.*)\b"),
    ("library", "landmark", 25, r"\b(library|archives?|archival .+|documentation cent(er|re)|records office)\b"),
    ("museum", "landmark", 50, r"\b(museum|art gallery|gallery|exhibition (hall|cent(er|re))|"
     r"interpretation cent(er|re)|planetarium|science cent(er|re)|visitor cent(er|re)|ecomuseum)\b"),
    ("theatre", "landmark", 40, r"\b(theatre|theater|opera( house)?|cinema|movie theater|auditorium|concert hall|"
     r"music venue|cultural (cent(er|re)|house|space)|arts? cent(er|re)|casino|event venue|nightclub|ballroom|circus|"
     r"amphitheat(re|er)|congress (centre|center)|convention cent(er|re)|bandstand|kiosk)\b"),
    ("military", "landmark", 100, r"\b(prison|jail|penitentiary|barracks|military (barracks|installation|building)|"
     r"arsenal|armou?ry|bunker|blockhouse|pillbox|casemate|battery|coastal battery|air-raid shelter|"
     r"military trench|trench)\b"),
    ("bank", "landmark", 15, r"^(bank|bank building|bank branch|savings bank|central bank)$"),
    ("civic building", "landmark", 30, r"\b(city hall|town hall|casa consistorial|ayuntamiento|"
     r"mairie( déléguée( of france)?)?|hôtel de ville|courthouse|court|tribunal|tribunal d'instance|post office|"
     r"police station|fire station|volunteer fire department|gendarmerie|embassy|consulate|parliament( building)?|"
     r"government building|administrative building|public building|office building|customs house|"
     r"stock exchange|exchange|city council|former town hall|palace of justice|registry office|social centre|"
     r"community cent(er|re)|youth cent(er|re)|senior cent(er|re))\b"),
    ("hotel", "landmark", 30, r"\b(hotel|hostel|guest house|inn|motel|parador|pousada|albergue|youth hostel|"
     r"(?<!wildlife )refuge|mountain hut|alpine hut|accommodation|hotel building|bed and breakfast|"
     r"holiday (home|village)|gîte)\b"),
    ("market", "landmark", 100, r"\b(market( hall)?|covered market|shopping (cent(er|re)|mall|arcade)|mall|"
     r"department store|galleria|souk|hypermarket)\b"),
    ("shop", "landmark", 15, r"\b(shop|store|restaurant|café|cafe|coffeehouse|bar|pub|tavern|bakery|patisserie|"
     r"confectionery|brewery|winery|wine cellar|bodega|distillery|cider house|supermarket|boutique|"
     r"petrol station|filling station|gas station|service station|car dealership|repair shop|bookshop|"
     r"bookstore|newsagent|butcher|business|enterprise|company|firm|office|commercial establishment)\b"),
    ("mill", "landmark", 15, r"\b(mill|watermill|windmill|tide mill|sawmill|lime kiln|kiln|oven|bread oven|granary|"
     r"hórreo|horreo|espigueiro|dovecote|pigeonnier|columbarium|ice house|nevera|lavoir|wash ?house|cistern|"
     r"aljibe|well|water well|noria|qanat|water mine|water trough|drinking trough|threshing floor|wine press|"
     r"olive press|oil mill|silo|press|winepress)\b"),
    ("industrial", "landmark", 150, r"\b(factory|plant|power station|power plant|hydroelectric|nuclear power|"
     r"thermal power|wind farm|wind park|solar (farm|park|power)|wastewater|sewage|water treatment|"
     r"treatment plant|refinery|ironworks|steelworks|works|foundry|industrial building|industrial heritage site|"
     r"brickworks|tannery|glassworks|cannery|substation|incinerator|landfill|gasometer|depot|hangar|workshop|"
     r"shipyard|dockyard|warehouse|pumping station|manufactory|slaughterhouse|mint)\b"),
    ("mine", "landmark", 300, r"\b(mine|quarry|mining|gravel pit|sand pit|salt mine|clay pit|slag heap|spoil tip|"
     r"open-pit)\b"),
    ("farmhouse", "landmark", 40, r"\b(farmhouse|masia|masía|casería|caseria|cortijo|baserri|caserío|borda|cabana|"
     r"cabin|hut|shepherd's hut|dry stone hut|barn|stable|cowshed|byre|posessió|possessió|grange|farmstead|"
     r"rural house|country house|cottage|chalet|mas|pen|enclosure|sheepfold|corral)\b"),
    ("mansion", "landmark", 40, r"\b(mansion|manor( house)?|villa|stately home|seigniorial home|private mansion|"
     r"hôtel particulier|palazzo|solar|casa solariega)\b"),
    ("house", "landmark", 20, r"\b(house|home|residence|residential building|apartment building|"
     r"multifamily residential|multi-story urban building|building|tenement|townhouse|row house|"
     r"single-family detached home|casa|dwelling|historic building|clergy house|rectory|presbytery|pavilion|"
     r"apartment|bathhouse|hammam|public bath)\b"),
    ("compound monument", "landmark", 8,
     r"^(?!monuments?$|natural monument|group of monuments|monument complex).*\bmonuments?\b"),
    ("small object", "landmark", 8, r"\b(memorial|statues?|sculptures?|bust|relief|work of art|"
     r"public art|installation|mural|fresco|fountain|cross|calvary|crucifix|pillory|whipping post|plaque|"
     r"stolperstein|milestone|boundary (marker|stone)|border stone|sundial|triangulation station|survey point|"
     r"geodetic (point|vertex|station)|benchmark|bench|signpost|sign|panel( histoire de paris)?|"
     r"street furniture|totem|tomb|grave|mausoleum|cenotaph|ossuary|sarcophagus|tree|weather station|clock|"
     r"pulpit|organ|altar(piece)?|door|portal|window|leadlight|stained glass|painting|drawing|"
     r"architectural (element|plan|drawing)|religious ceramic panel|azulejo|tile panel|"
     r"zamenhof-esperanto object|gate|arch|archway|portico|pergola|gazebo|monolith|bollard|street lamp|"
     r"lamppost|telephone box|letter box|baptismal font|font|reredos|mosaic|lintel|pantheon|gnss|gps)\b"),
    ("cave", "landmark", 40, r"\b(cave|cavern|grotto|rock shelter|pit cave|sinkhole|shelter cave|abri|cave system)\b"),
    ("spring", "landmark", 15, r"\b(spring|river source|water source|seepage|fountainhead|resurgence|geyser)\b"),
    ("waterfall", "landmark", 40, r"\b(waterfall|cascade|cataract|rapids)\b"),
    ("observatory", "landmark", 50, r"\b(observatory|radio telescope|meteorological station|research station|"
     r"telescope)\b"),
    ("roundabout", "landmark", 40, r"\b(roundabout|traffic circle|interchange|junction|crossroads|intersection|"
     r"level crossing)\b"),
    # natural and urban extents
    ("mountain range", "area", 15_000, r"\b(mountain range|mountain chain|massif|sierra|cordillera|mountain system|"
     r"mountains|range of hills|hills)\b"),
    ("mountain", "area", 1_500, r"^(mountain|mount|volcano|stratovolcano|extinct volcano|inselberg|monadnock|"
     r"table mountain|mesa|butte)$"),
    ("ridge", "area", 2_000, r"^(ridge|mountain ridge|arête|spur|crest|escarpment|scarp)$"),
    ("summit", "area", 300, r"^(summit|peak|mountain peak|hilltop|subsidiary summit|pic|knoll|tor|crag|pinnacle|"
     r"rock pinnacle|needle|rocky outcrop|outcrop|rock formation|rock|boulder|erratic boulder|natural arch|"
     r"natural monument( of .+)?|rock arch|sea stack|stack|cliff|sea cliff|highest point)$"),
    ("hill", "area", 600, r"^(hill|hillock|mound|slope|ubac, north-facing slope|adret|hillside|mountainside)$"),
    ("pass", "area", 300, r"\b(mountain pass|col|saddle|mountain saddle|gap|notch|pass)\b"),
    ("plain", "area", 5_000, r"\b(plain|coastal plain|alluvial plain|plateau|high plateau|upland|steppe|desert|"
     r"karst( landscape)?|moor(land)?|heath(land)?|lande|garrigue|scrubland|badlands|depression|basin)\b"),
    ("valley", "area", 3_000, r"\b(valley|canyon|gorge|ravine|gully|cirque|combe)\b"),
    ("river", "area", 20_000, r"^(river|main stem|gold river|tributary|distributary|river branch|torrent)$"),
    ("canal", "area", 5_000, r"\b(canal|navigation canal|waterway|irrigation canal)\b"),
    ("stream", "area", 3_000, r"^(stream|brook|creek|rivulet|watercourse|wadi|arroyo|rambla|intermittent river|"
     r"ephemeral river|beck|burn|rill|drainage channel|channel|acequia|ditch|millrace|leat|seasonal river|"
     r"barranco)$"),
    ("sea", "area", 50_000, r"^(sea|ocean|gulf|marginal sea|inland sea)$"),
    ("bay", "area", 3_000, r"\b(bay|bight|inlet|fjord|ria|estuary|delta|river mouth|strait|sound)\b"),
    ("cove", "area", 300, r"\b(cove|calanque)\b"),
    ("reservoir", "area", 2_000, r"\b(reservoir|artificial lake|storage lake)\b"),
    ("lake", "area", 800, r"\b(lake|glacial lake|mountain lake|crater lake|lagoon|laguna|coastal lagoon|tarn|"
     r"oxbow lake|salt lake|salt pan|saltern|salt evaporation pond|water body|body of water)\b"),
    ("pond", "area", 100, r"\b(pond|artificial pond|fish pond|mill pond|pool|natural pool|waterhole|"
     r"swimming hole|upwelling|tank|puddle|alberca)\b"),
    ("wetland", "area", 1_500, r"\b(wetland|marsh|swamp|bog|fen|mire|peat bog|reed bed|floodplain|marshland|"
     r"riparian zone|salt marsh)\b"),
    ("port", "area", 400, r"\b(port|harbou?r|seaport|marina|fishing port|yacht harbou?r|dock|dry dock|anchorage|"
     r"roadstead|quayside)\b"),
    ("beach", "area", 400, r"\b(beach|lido|bathing (area|site))\b"),
    ("archipelago", "area", 30_000, r"^(archipelago|island group|group of islands)$"),
    ("islet", "area", 100, r"\b(islet|skerry|rock island|sea rock)\b"),
    ("island", "area", 2_000, r"\b(island|river island|tidal island|lake island|isle|cay|atoll)\b"),
    ("peninsula", "area", 3_000, r"\b(peninsula|isthmus|tombolo)\b"),
    ("cape", "area", 400, r"\b(cape|headland|promontory|point|coastal point|foreland|ness|punta|pointe|spit|"
     r"sandbank|sandbar|shoal|reef|bank|coastal feature)\b"),
    ("dune", "area", 500, r"\b(dunes?|sand dune|dune system|erg)\b"),
    ("glacier", "area", 1_500, r"\b(glacier|ice field|snowfield)\b"),
    ("national park", "area", 20_000, r"\b(national park|parque nacional)\b"),
    ("natural park", "area", 15_000, r"\b(natural park|regional (natural )?park|nature park|parc naturel|"
     r"parque natural|biosphere reserve|geopark)\b"),
    ("protected area", "area", 5_000, r"\b(protected (area|site|zone|landscape)|natura 2000 site|"
     r"site of community importance|special protection area|special area of conservation|ramsar site|"
     r"wildlife (reserve|refuge|sanctuary)|game reserve|hunting (reserve|ground)|marine (reserve|protected area)|"
     r"nature reserve|natural reserve|national nature reserve|regional nature reserve|ecological reserve|"
     r"conservation area|important bird area|znieff|site classé|site inscrit|natural (site|area|space)|"
     r"espacio natural|biological reserve|forest managed biological reserve|integral reserve|"
     r"pla d'espais d'interès natural)\b"),
    ("cultural landscape", "area", 5_000, r"^cultural landscape$"),
    ("battlefield", "area", 2_000, r"^battlefield$"),
    ("forest", "area", 3_000, r"\b(forest|woodland|wood|woods|grove|national forest|state forest|communal forest|"
     r"domanial forest|forest reserve|pine forest|oak forest|chestnut grove|palm grove|forest massif)\b"),
    ("ski resort", "area", 2_000, r"\bski (resort|area|station|domain)\b"),
    ("golf course", "area", 600, r"\b(golf course|golf links)\b"),
    ("park", "area", 300, r"\b(park|urban park|city park|public park|country park|forest park|zoo|"
     r"zoological (garden|park)|safari park|theme park|amusement park|water park|leisure (park|cent(er|re)|area)|"
     r"fairground|recreation (area|ground)|picnic (site|area)|pleasure garden|arboretum)\b"),
    ("garden", "area", 150, r"\b(garden|botanical garden|public garden|formal garden|jardin|garden square|"
     r"allotment|community garden)\b"),
    ("campsite", "area", 150, r"\b(campsite|camping|campground|caravan (site|park)|playground)\b"),
    ("cemetery", "area", 100, r"\b(cemetery|graveyard|burial ground|churchyard|national necropolis|crematorium|"
     r"père lachaise division)\b"),
    ("square", "area", 60, r"\b(square|town square|plaza|piazza|esplanade|forecourt|parvis|courtyard|cours|"
     r"market square|main square)\b"),
    ("promenade", "area", 400, r"^(promenade|seafront|riverfront|waterfront|embankment|quay|towpath|boardwalk|"
     r"corniche)$"),
    ("alley", "area", 80, r"^(alley|lane|dead end street|cul-de-sac|passage|passageway|stairway|stairs|steps|ramp|"
     r"arcade street|close|pedestrian passage)$"),
    ("street", "area", 250, r"^(street|pedestrian street|shopping street|rambla|calle|rue|rua|via|way|thoroughfare|"
     r"private road|service road|urban road|street \(.*\))$"),
    ("avenue", "area", 500, r"^(avenue|boulevard|ring road|parkway|grand boulevard)$"),
    ("road", "area", 1_500, r"^(road|country road|forest road|forest track|track|rural road|farm road|communal road)$"),
    ("path", "area", 2_000, r"\b(footpath|path|trail|hiking trail|footway|walkway|greenway|cycle (path|track|route)|"
     r"cycleway|bridle (path|way)|drove road|cattle trail|cañada|transhumance route|pilgrimage route|camino|"
     r"via verde|rail trail|long-distance (path|trail)|hiking route)\b"),
    ("highway", "area", 10_000, r"\b(highway|motorway|expressway|freeway|national road|regional road|"
     r"departmental road|route départementale|route nationale|trunk road|european route|autovía|autopista|"
     r"itinerário (principal|complementar)|estrada nacional|road route|railway line|railway|rail line|"
     r"high-speed rail line|tramway line|tram line|metro line|cable car( line)?|aerial tramway|rack railway|"
     r"funicular|chairlift|gondola lift)\b"),
    ("airport", "area", 1_500, r"\b(airport|aerodrome|airfield|airbase|air base|"
     r"military (base|airfield|camp|zone|area)|"
     r"naval base|training area|firing range)\b"),
    ("campus", "area", 300, r"\b(campus|research campus|school complex)\b"),
    ("farm", "area", 200, r"\b(farm|estate|manor estate|quinta|finca|hacienda|plantation|vineyard|orchard|field|"
     r"meadow|pasture|grassland|cultivated field|agricultural (land|area)|dehesa|montado|olive grove|stud farm)\b"),
    ("natural place", "area", 500, r"^(place|natural (place|area|feature)|toponym|landform|terrain|cultivated area|"
     r"area of land|geographic area)$"),
    # weak: generic forms that more specific types override
    ("ensemble", "landmark", 250, r"^(architectural ensemble|group of monuments|monument complex|building complex|"
     r"ensemble|historic site|archaeological park|historic complex|religious complex|industrial complex|"
     r"group of (buildings|structures or buildings)|concentration camp|internment camp|prison camp)$"),
    ("monument", "landmark", 8, r"^monuments?$"),
    ("facility", "landmark", 50, r"(facility|installation|equipment)$"),
    ("organisation", "landmark", 50, r"\b(organi[sz]ation|association|club|society|foundation|federation|union|"
     r"political party|agency|council|committee|commission|authority|administration|institution|corporation|"
     r"cooperative|nonprofit|research (institute|unit|cent(er|re)|laboratory)|laboratory|umr|comissió fallera|"
     r"team|brotherhood|confraternity|religious (order|community)|order|congregation|chapter|police|"
     r"fire brigade|ngo|charity|trust|unit|publisher|public body( in .+)?|radio station|television station|"
     r"broadcaster)\b"),
    # events are not places
    ("event", "skip", 0, r"\b(battle|siege|festival|edition|season|ceremony|tournament|championship|competition|race|"
     r"rally|election|conference|congress|exhibition|trade fair|riot|massacre|attack|bombing|earthquake|flood|"
     r"wildfire|forest fire|shipwreck|accident|crash|disaster|expedition|treaty|strike|protest|demonstration|"
     r"uprising|revolt|rebellion|war|military (operation|campaign)|invasion|event|occurrence|incident|meeting|"
     r"concert|pilgrimage|procession|fiesta|feria|carnival|parade|recurring|film shoot|happening|programme|"
     r"program|project|proposal|marathon|stage)\b"),
]
WIKIDATA_DEFAULT = ("unclassified", "landmark", 100)
# Frequent P31 types without an English label: QID -> rule name
WIKIDATA_TYPE_RULES = {"Q104717505": "street", "Q17383262": "alley", "Q917730": "estate", "Q134452349": "school",
                       "Q66108461": "farmhouse"}

# -- GeoNames roles and extents --------------------------------------------------------------------
GEONAMES_AREA_CLASSES = set("AHLPRTUV")
GEONAMES_LANDMARK_CODES = {"H.SPNG", "H.SPNS", "H.SPNT", "H.WLL", "H.WTRH", "H.FLLS", "V.TREE", "T.RK", "T.BLDR",
                           "R.TNL", "R.TNLRR", "R.TNLN", "R.RDJCT", "R.RJCT", "R.STKR"}
GEONAMES_AREA_CODES = {"S.AIRP", "S.AIRF", "S.AIRB", "S.MAR", "S.RECG", "S.ZOO", "S.GDN", "S.SQR", "S.CMTY", "S.EST",
                       "S.ESTO", "S.RSRT", "S.FRMS", "S.RNCH", "S.ITTR"}
GEONAMES_CLASS_EXTENT = {"A": 10_000, "H": 1_000, "L": 1_000, "P": 600, "R": 1_000, "S": 50, "T": 1_000,
                         "U": 2_000, "V": 1_000}
GEONAMES_ADMIN = {"ADM1": {"PT": 40_000, "ES": 120_000, "FR": 150_000},
                  "ADM2": {"PT": 10_000, "ES": 50_000, "FR": 45_000},
                  "ADM3": {"PT": 3_000, "ES": 5_000, "FR": 25_000},
                  "ADM4": {"PT": 1_500, "ES": 2_000, "FR": 2_500}}
_GEONAMES_EXTENTS = """
A PCLI:300000 PCLD:300000 PCLS:300000 ADMD:10000 ADM5:1500 PRSH:3000 ZN:5000 ZNB:5000
P PPLC:7000 PPLA:4000 PPLA2:2500 PPLA3:1500 PPLA4:1000 PPLA5:800 PPLG:3000 PPL:600 PPLX:600 PPLL:400 PPLF:250
  PPLQ:300 PPLW:300 PPLH:600 PPLR:300 PPLS:1500 PPLCH:3000 PPLCD:3000 STLMT:300
H STM:5000 STMI:3000 STMX:3000 STMA:3000 STMC:3000 STMD:3000 STMH:3000 STMQ:3000 STMS:5000 STMSB:3000 STMM:2000
  CNL:5000 CNLA:3000 CNLI:3000 CNLN:3000 CNLX:3000 CNLQ:3000 LK:800 LKS:2000 LKI:500 LKX:500 LKN:500 LKC:500
  RSV:2000 RSVT:300 PND:100 PNDS:300 PNDI:100 PNDN:100 LGN:1000 LGNS:2000 MRSH:1000 MRSHN:1000 SWMP:1000
  WTLD:1000 BOG:1000 BAY:3000 BGHT:3000 COVE:300 GULF:20000 SEA:50000 ESTY:5000 INLT:1000 HBR:500 ANCH:300
  RDST:500 SHOL:500 RF:500 BNK:500 BNKR:500 CHN:2000 CHNM:2000 CHNN:2000 STRT:3000 SD:3000 GLCR:1500 DCK:100
  DCKB:100 POOL:50 FLTT:1000 FLTM:1000 CRNT:1000 WTRC:3000 RPDS:100 WHRL:100 LBED:500 DTCH:1000 DTCHD:1000
  MFGN:300 AIRS:500 FISH:300 CNFL:200 WAD:2000 SPNG:20 SPNS:20 SPNT:20 WLL:20 WTRH:30 FLLS:40
L PRK:400 PRT:400 LCTY:500 RGN:30000 RGNH:30000 RGNE:20000 AREA:1000 RESN:3000 RES:3000 RESF:3000 RESW:3000
  RESP:3000 RESV:3000 RESH:3000 RESA:3000 INDS:500 AMUS:300 CST:3000 GRAZ:500 FLD:300 FLDI:300 CMN:300
  MILB:1000 CTRB:500 DEVH:500 SNOW:1000 BTL:1000 COLF:1000 CLG:300 NVB:1000 OAS:1000 TRB:10000 AGRC:2000
  MVA:3000 MNA:300 RNGA:3000 SALT:500
T MT:1500 MTS:15000 PK:300 PKS:1000 HLL:600 HLLS:2000 RDGE:2000 PASS:200 GAP:300 SDL:300 VAL:3000 VALG:3000
  VALS:3000 CNYN:2000 GRGE:1000 RVN:500 PLN:5000 PLAT:5000 UPLD:3000 ISL:2000 ISLS:20000 ISLET:100 ISLT:100
  ISLX:300 ISLM:300 PEN:3000 CAPE:300 PT:300 PTS:500 HDLD:300 PROM:300 BCH:300 BCHS:1000 RK:30 RKS:100
  RKFL:300 CLF:300 CRQ:500 CRQS:500 DUNE:300 DUNS:1000 SLP:500 SHOR:500 SPIT:500 VLC:2000 CONE:500 CRTR:500
  LAVA:1000 DPR:500 MESA:1000 BUTE:500 ATOL:3000 DSRT:20000 KRST:5000 SINK:100 BLDR:10 TAL:300 TRR:300
  SCRP:1000 REG:5000 PAN:1000 HMDA:3000 ASPH:300 BAR:500 BDLD:3000 CUET:300 FSR:500 ISTH:1000 MND:100 MRN:500
  PLDR:1000 RDGB:1000 SPUR:1000
V FRST:3000 FRSTF:3000 VIN:300 CULT:500 GRSLD:500 HTH:1000 MDW:300 SCRB:500 TREE:10 BUSH:100 GRVP:300 GRVPN:300
  GRVO:300 MOOR:1000
R ST:250 RD:2000 RDA:2000 TRL:2000 RR:10000 RRQ:10000 RYD:500 PRMN:400 CSWY:500 RDB:100 RDCR:50 TNL:300
  TNLRR:500 TNLN:300 RDJCT:30 RJCT:50 STKR:5
S CH:25 CTRR:50 MSTY:80 CVNT:60 HERM:15 SHRN:15 TMPL:25 MSQE:25 SYG:25 RLG:25 RLGR:50 CSTL:80 FT:100 PAL:80
  CSTM:25 MUS:50 THTR:40 OPRA:50 AMTH:60 LIBR:25 ARCHV:25 SCH:50 SCHC:50 SCHL:50 SCHM:50 SCHA:50 SCHT:50
  SCHN:50 UNIV:200 UNIP:200 HSP:100 HSPC:25 HSPD:25 HSPL:100 HTL:30 RSRT:300 REST:15 CSNO:50 MALL:150 MKT:50
  BANK:15 PO:15 PS:20 GOVL:25 ADMF:30 CTHSE:30 PRN:100 PRNJ:100 BLDG:25 BLDO:25 BLDA:25 HSE:20 HSEC:40
  HSTS:100 MNMT:10 RUIN:50 ANS:150 TOWR:15 LTHSE:15 BDG:100 BDGQ:100 DAM:150 DAMQ:150 LOCK:20 RSTN:100
  RSTNQ:100 RSTP:20 RSTPQ:20 MTRO:50 BUSTN:50 BUSTP:10 TRANT:50 AIRP:1500 AIRF:600 AIRB:1000 AIRH:50
  AIRQ:300 MAR:300 QUAY:200 PIER:100 JTY:100 WHRF:100 LDNG:50 DCKY:200 STDM:120 ATHF:100 RECG:600 RECR:200
  ZOO:300 GDN:150 SQR:60 CMTY:100 FRM:200 FRMS:500 FRMQ:200 EST:500 ESTO:300 CMP:200 CMPQ:200 MFG:150
  MFGB:100 MFGC:100 MFGN:150 MFGQ:100 MN:300 MNQ:300 MNQR:300 ML:15 MLWND:15 MLWTR:15 MLO:15 MLSW:15
  OBPT:20 OBS:50 OBSR:50 GATE:10 ARCH:10 WALL:100 WALLA:300 TMB:10 GRVE:5 CAVE:50 SPA:50 PP:20 HUT:10
  HUTS:10 ITTR:300 TRIG:5 STNM:10 STNB:100 STNE:100 STNR:50 FCL:50 CTRCM:50 CTRF:50 CTRM:50 CTRS:50 CTRA:50
  RHSE:20 BCN:10 DIKE:500 BRKW:200 MOLE:200 INSM:50 BRKS:100 FY:50 FYT:50 PSH:50 WTRW:50 SWT:50 PMPW:20
  PMPO:20 NSY:100 DARY:100 AGRF:100 RNCH:500 STBL:30 GHSE:20 SHSE:20 RET:20 COMC:50 ASTR:20 CARN:5 BTYD:100
  SNTR:100 TOLL:100 VETF:30 TWO:50 SPLY:50 SLCE:20 NOV:50 LEPC:50 HLT:50 FNDY:50 DIP:30 SECP:30 OILT:100
  PSN:50 PPQ:50 PGDA:20 PSTB:30 BP:5 ASYL:50 PYR:20 HMSD:200 PKLT:30 PRKGT:20
"""
GEONAMES_EXTENTS = {}
for _line in re.findall(r"^([A-Z]) (.+(?:\n  .+)*)", _GEONAMES_EXTENTS, re.M):
    for _code, _extent in (item.split(":") for item in _line[1].split()):
        GEONAMES_EXTENTS[f"{_line[0]}.{_code}"] = int(_extent)
POPULATED_EXTENT = (450.0, 0.4, 250.0, 15_000.0)  # 450 m x (population / 1000)^0.4, clamped
GEONAMES_BONUS = {"P.PPLC": 0.3, "P.PPLA": 0.2, "P.PPLA2": 0.1, "P.PPLA3": 0.05, "A.PCLI": 0.3, "A.ADM1": 0.2,
                  "A.ADM2": 0.1}

# -- postcodes ---------------------------------------------------------------------------------------
POSTCODE_PLACE_M = 3000.0  # a GeoNames place with the row's name within this distance lends its extent
POSTCODE_SHARED_POINT = 3  # a point carried by this many codes is a place centroid, not a code's own point
POSTCODE_EXTENT = {6: 300, 5: 3000, 4: 1500, 3: 2500, 2: 3000, 1: 4000}  # default extent by accuracy flag
POSTCODE_ROW_WEIGHT = {6: 1.0, 5: 1.0, 4: 1.0, 3: 0.7, 2: 0.5, 1: 0.5}  # in centres of codes and prefixes


def log_line(message):
    rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024
    print(f"{datetime.now():%H:%M:%S} {message} (peak RSS {rss:,.0f} MB)", flush=True)


def compact_json(info):
    """JSON without the keys whose value is None (the reader treats a missing key as None)."""
    return json.dumps({k: v for k, v in info.items() if v is not None}, ensure_ascii=False, separators=(",", ":"))


def finite(value):
    try:
        x = float(value)
    except (TypeError, ValueError):
        return None
    return x if math.isfinite(x) else None


def point(lat, lng):
    lat, lng = finite(lat), finite(lng)
    if lat is None or lng is None or not (-90 <= lat <= 90 and -180 <= lng <= 180):
        return None
    return lat, lng


def overseas(lat, lng):
    """Outside mainland PT/ES/FR, Corsica, the Balearics, the Canaries, Madeira and the Azores."""
    boxes = ((35.0, 51.6, -10.0, 10.0), (27.4, 29.6, -18.4, -13.2), (29.9, 33.3, -17.4, -15.7),
             (36.8, 39.9, -31.5, -24.6))
    return not any(a <= lat <= b and c <= lng <= d for a, b, c, d in boxes)


def prominence_wikidata(sitelinks, heritage):
    return min(1.0, math.log1p(sitelinks) / math.log1p(150) + (0.15 if heritage else 0.0))


def prominence_geonames(population, feature):
    return min(1.0, math.log10(1 + population) / 6.5 + GEONAMES_BONUS.get(feature, 0.0))


def populated_extent(population):
    scale, power, low, high = POPULATED_EXTENT
    return min(high, max(low, scale * (population / 1000) ** power))


class WikidataRoles:
    """Role, extent and rule for an item's P31 types (see WIKIDATA_RULES)."""

    def __init__(self, rules=WIKIDATA_RULES, by_type=WIKIDATA_TYPE_RULES):
        self.rules = [(name, role, extent, re.compile(pattern)) for name, role, extent, pattern in rules]
        index = {name: i for i, (name, *_) in reversed(list(enumerate(self.rules)))}
        self.by_type = {qid: index[name] for qid, name in by_type.items()}
        self._cache = {}
        self.rule_counts = Counter()

    def rule_of(self, label, qid=None):
        if qid in self.by_type:
            return self.by_type[qid]
        label = label.strip().lower()
        if label not in self._cache:
            self._cache[label] = next((i for i, (*_, rx) in enumerate(self.rules) if label and rx.search(label)), None)
        return self._cache[label]

    def classify(self, labels, qids=()):
        """(role, extent_m, rule) or None when the item is an event and nothing else. `qids` are the
        P31 QIDs aligned with `labels`, for WIKIDATA_TYPE_RULES."""
        qids = list(qids) + [None] * (len(labels) - len(qids))
        hits = {i for i in map(self.rule_of, labels, qids) if i is not None and self.rules[i][1] != "ignore"}
        places = sorted(i for i in hits if self.rules[i][1] != "skip")
        if not places:
            if hits:
                self.rule_counts["event"] += 1
                return None
            self.rule_counts[WIKIDATA_DEFAULT[0]] += 1
            return WIKIDATA_DEFAULT[1], WIKIDATA_DEFAULT[2], WIKIDATA_DEFAULT[0]
        name, role = self.rules[places[0]][:2]
        extent = max(self.rules[i][2] for i in places if self.rules[i][1] == role)
        self.rule_counts[name] += 1
        return role, extent, name


def geonames_role(fclass, fcode, country, population):
    """(role, extent_m, role rule, extent rule) for a GeoNames feature."""
    feature = f"{fclass}.{fcode}"
    if feature in GEONAMES_LANDMARK_CODES:
        role = "landmark"
    elif feature in GEONAMES_AREA_CODES:
        role = "area"
    else:
        role = "area" if fclass in GEONAMES_AREA_CLASSES else "landmark"
    level = fcode[:-1] if fcode.endswith("H") and fcode[:-1] in GEONAMES_ADMIN else fcode
    if fclass == "A" and level in GEONAMES_ADMIN:
        return role, GEONAMES_ADMIN[level].get(country, 10_000), feature, f"geonames {level} in {country}"
    if fclass == "P" and population > 0:
        return role, round(populated_extent(population)), feature, "geonames population"
    extent = GEONAMES_EXTENTS.get(feature, GEONAMES_CLASS_EXTENT.get(fclass, 50))
    return role, extent, feature, "geonames feature code" if feature in GEONAMES_EXTENTS else "geonames class"


def names_of(entries, label_min=1, alias_min=2):
    """Distinct normalised names from (original, kind, language) entries, in order:
    [(norm, squashed, core, languages, kind, original)]. Labels win over aliases for the kind."""
    out = {}
    for original, kind, language in entries:
        original = (original or "").strip()
        if not original or len(original) > MAX_NAME_CHARS:
            continue
        norm = N.normalise(original)
        if not norm or not norm.isascii() or not any(ch.isalpha() for ch in norm):
            continue
        squashed, core = N.keys(norm)
        if len(squashed) < (alias_min if kind in ("alias", "alternate") else label_min):
            continue
        if norm in out:
            entry = out[norm]
            if language and language not in entry[3]:
                entry[3].append(language)
            if kind in ("label", "name") and entry[4] in ("alias", "alternate"):
                entry[4] = kind
        elif len(out) < MAX_NAMES:
            out[norm] = [norm, squashed, core, [language] if language else [], kind, original]
    return [tuple(v) for v in out.values()]


def read_code_names(geonames_dir):
    """GeoNames feature-code descriptions and admin1/admin2 names; missing files give empty maps."""
    features, admin1, admin2 = {}, {}, {}
    for path, target, key_col, value_col in ((geonames_dir / "featureCodes_en.txt", features, 0, 1),
                                             (geonames_dir / "admin1CodesASCII.txt", admin1, 0, 1),
                                             (geonames_dir / "admin2Codes.txt", admin2, 0, 1)):
        if not path.is_file():
            continue
        with open(path, encoding="utf-8", errors="replace") as f:
            for line in f:
                parts = line.rstrip("\r\n").split("\t")
                if len(parts) > value_col and parts[key_col] and len(parts[value_col]) <= MAX_NAME_CHARS:
                    target[parts[key_col]] = parts[value_col]
    return features, admin1, admin2


def file_record(path):
    path = Path(path)
    digest = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            digest.update(block)
    st = path.stat()
    try:
        shown = str(path.resolve().relative_to(ROOT))
    except ValueError:
        shown = str(path)
    return {"path": shown, "bytes": st.st_size, "mtime_utc": datetime.fromtimestamp(st.st_mtime, timezone.utc)
            .isoformat(timespec="seconds"), "sha256": digest.hexdigest()}


SCHEMA_SQL = """
CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE place (id INTEGER PRIMARY KEY, source TEXT NOT NULL, label TEXT NOT NULL, lat REAL NOT NULL,
                    lng REAL NOT NULL, countries TEXT NOT NULL, role TEXT NOT NULL, extent_m REAL NOT NULL,
                    prominence REAL NOT NULL, grp TEXT, info TEXT NOT NULL);
CREATE TABLE link (place_id INTEGER NOT NULL, other_id INTEGER NOT NULL, distance_m REAL NOT NULL);
CREATE TABLE postcode (country TEXT NOT NULL, code TEXT NOT NULL, kind TEXT NOT NULL, lat REAL NOT NULL,
                       lng REAL NOT NULL, extent_m REAL NOT NULL, label TEXT NOT NULL, info TEXT NOT NULL,
                       PRIMARY KEY (country, code)) WITHOUT ROWID;
CREATE TABLE stage.name_stage (place_id INTEGER NOT NULL, norm TEXT NOT NULL, squash TEXT NOT NULL,
                               core TEXT NOT NULL, langs TEXT NOT NULL, kind TEXT NOT NULL, original TEXT NOT NULL,
                               cmask INTEGER NOT NULL, prominence REAL NOT NULL);
"""


class Builder:
    def __init__(self, con, log):
        self.con, self.log = con, log
        self.stats = Counter()
        self.next_id = 1
        self.places, self.names = [], []
        self.gn_by_key = defaultdict(list)  # squashed name -> [(place id, lat, lng, extent_m)] of GeoNames entries
        self.gn_extent = {}  # GeoNames place id -> (extent_m, source, feature class)
        self.sources = {}  # place id -> source, for linked places
        self.links = {}  # (wikidata id, geonames id) -> distance_m
        self.wikidata_roles = WikidataRoles()

    def add_place(self, source, label, lat, lng, countries, role, extent_m, prominence, info, names):
        place_id = self.next_id
        self.next_id += 1
        cmask = sum(N.COUNTRY_BITS[c] for c in countries)
        self.places.append((place_id, source, label, lat, lng, "|".join(countries), role, float(extent_m),
                            round(prominence, 6), None, compact_json(info)))
        for norm, squashed, core, languages, kind, original in names:
            self.names.append((place_id, norm, squashed, core, ",".join(languages), kind, original, cmask,
                               round(prominence, 6)))
        if len(self.places) >= BATCH:
            self.flush()
        return place_id

    def flush(self):
        self.con.executemany("INSERT INTO place VALUES (?,?,?,?,?,?,?,?,?,?,?)", self.places)
        self.con.executemany("INSERT INTO stage.name_stage VALUES (?,?,?,?,?,?,?,?,?)", self.names)
        self.stats["places"] += len(self.places)
        self.stats["names"] += len(self.names)
        self.places, self.names = [], []

    # -- GeoNames places -------------------------------------------------------------------------------

    def geonames(self, geonames_dir, countries):
        features, admin1, admin2 = read_code_names(geonames_dir)
        for country in countries:
            path = geonames_dir / "places" / country / f"{country}.txt"
            if not path.is_file():
                self.log(f"GeoNames places: {path} missing, skipped")
                self.stats["geonames_missing_files"] += 1
                continue
            before = self.stats["geonames_places"]
            with open(path, encoding="utf-8", errors="replace", newline="") as f:
                for line in f:
                    self.geonames_row(line.rstrip("\r\n").split("\t"), country, features, admin1, admin2)
            self.log(f"GeoNames {country}: {self.stats['geonames_places'] - before:,} places")
        self.flush()

    def geonames_row(self, parts, country, features, admin1, admin2):
        if len(parts) != 19:
            self.stats["geonames_bad_rows"] += 1
            return
        gid, name, ascii_name, alternates, lat, lng, fclass, fcode, cc = parts[:9]
        a1, a2, population = parts[10], parts[11], parts[14]
        where = point(lat, lng)
        if not gid.isdigit() or where is None or cc != country or not re.fullmatch(r"[A-Z]", fclass) \
                or not re.fullmatch(r"[A-Z0-9]{0,10}", fcode):
            self.stats["geonames_bad_rows"] += 1
            return
        population = int(population) if population.isdigit() else 0
        entries = [(name, "name", None), (ascii_name, "name", None)]
        entries += [(alt, "alternate", None) for alt in alternates.split(",")[:4 * MAX_NAMES] if alt]
        names = names_of(entries)
        if not names:
            self.stats["geonames_no_name"] += 1
            return
        role, extent, rule, extent_rule = geonames_role(fclass, fcode, country, population)
        feature = f"{fclass}.{fcode}"
        info = {"geonameid": int(gid), "feature_code": feature, "feature": features.get(feature),
                "population": population or None, "admin1": admin1.get(f"{cc}.{a1}"),
                "admin2": admin2.get(f"{cc}.{a1}.{a2}"), "role_rule": f"geonames {rule}", "extent_rule": extent_rule,
                "extent_source": "assumed"}
        if overseas(*where):
            info["overseas"] = True
        source = f"geonames:{int(gid)}"
        place_id = self.add_place(source, name.strip() or names[0][5], *where, [country], role, extent,
                                  prominence_geonames(population, feature), info, names)
        self.stats["geonames_places"] += 1
        self.gn_extent[place_id] = (extent, source, fclass)
        for squashed in {n[1] for n in names}:
            self.gn_by_key[squashed].append((place_id, *where, extent))

    # -- Wikidata items --------------------------------------------------------------------------------

    def wikidata(self, path):
        csv.field_size_limit(16 * 1024 * 1024)
        with gzip.open(path, "rt", encoding="utf-8", errors="replace", newline="") as f:
            reader = csv.DictReader(f)
            needed = {"qid", "country", "lat", "lon", "types", "type_labels_en", "sitelinks"}
            missing = needed - set(reader.fieldnames or ())
            if missing:
                raise ValueError(f"{path}: missing columns {sorted(missing)}")
            for row in reader:
                self.wikidata_row(row)
                if self.stats["wikidata_rows"] % 200_000 == 0:
                    self.log(f"Wikidata: {self.stats['wikidata_rows']:,} rows")
        self.flush()

    def wikidata_row(self, row):
        self.stats["wikidata_rows"] += 1
        qid = (row.get("qid") or "").strip()
        countries = [c for c in dict.fromkeys((row.get("country") or "").split("|")) if c in N.COUNTRY_BITS]
        where = point(row.get("lat"), row.get("lon"))
        if not QID.match(qid) or not countries or where is None:
            self.stats["wikidata_bad_rows"] += 1
            return
        type_qids = (row.get("types") or "").split("|")
        type_labels = (row.get("type_labels_en") or "").split("|")
        type_labels += [""] * (len(type_qids) - len(type_labels))
        role_info = self.wikidata_roles.classify(type_labels, type_qids)
        if role_info is None:
            self.stats["wikidata_events_skipped"] += 1
            return
        role, extent, rule = role_info
        first = LABEL_LANGUAGE[countries[0]]
        order = [first] + [lang for lang in LANGS if lang != first]
        entries = [(row.get(f"label_{lang}"), "label", lang) for lang in order]
        entries += [(alias, "alias", lang) for lang in order for alias in (row.get(f"aliases_{lang}") or "").split("|")]
        names = names_of(entries)
        if not names:
            self.stats["wikidata_no_name"] += 1
            return
        label = next((row[f"label_{lang}"].strip() for lang in order if (row.get(f"label_{lang}") or "").strip()),
                     names[0][5])
        sitelinks = int(row["sitelinks"]) if (row.get("sitelinks") or "").isdigit() else 0
        heritage = [h for h in (row.get("heritage_labels_en") or "").split("|") if h][:MAX_LIST]
        types = [t for t in (row.get("types") or "").split("|") if QID.match(t)][:MAX_LIST]
        extent_source, extent_rule = "assumed", f"wikidata type: {rule}"
        spread, n_coords = 0.0, 1
        for pair in (row.get("other_coords") or "").split("|"):
            other = point(*pair.split()) if len(pair.split()) == 2 else None
            if other:
                n_coords += 1
                spread = max(spread, haversine_m(where, other))
        if spread > extent:
            extent, extent_source, extent_rule = round(spread), "source", "spread of the item's coordinates"
        info = {"qid": qid, "sitelinks": sitelinks, "types": types,
                "type_labels": [t for t in type_labels if t][:MAX_LIST], "heritage": heritage or None,
                "image": (row.get("image") or "").split("|")[0] or None,
                "located_in": [q for q in (row.get("located_in") or "").split("|") if QID.match(q)][:5] or None,
                "role_rule": f"wikidata {rule}", "extent_rule": extent_rule, "extent_source": extent_source}
        if n_coords > 1:
            info["n_coords"], info["coord_spread_m"] = n_coords, round(spread)
        if overseas(*where):
            info["overseas"] = True
        source = f"wikidata:{qid}"
        place_id = self.add_place(source, label, *where, countries, role, extent,
                                  prominence_wikidata(sitelinks, heritage), info, names)
        self.stats["wikidata_places"] += 1
        self.link(place_id, source, where, extent, {n[1] for n in names})

    def link(self, place_id, source, where, extent, squashed_names):
        lat, lng = where
        reach = min(LINK_MAX_M, max(LINK_RADIUS_M, extent / 2))
        dlat = reach / 111_000
        dlng = dlat / max(math.cos(math.radians(lat)), 0.1)
        for squashed in squashed_names:
            for gid, glat, glng, gextent in self.gn_by_key.get(squashed, ()):
                if abs(glat - lat) <= dlat and abs(glng - lng) <= dlng:
                    d = haversine_m(where, (glat, glng))
                    radius = min(LINK_MAX_M, max(LINK_RADIUS_M, min(extent, gextent) / 2))
                    if d <= radius and d < self.links.get((place_id, gid), math.inf):
                        self.links[(place_id, gid)] = d
                        self.sources[place_id] = source
                        self.sources[gid] = self.gn_extent[gid][1]

    def groups(self):
        """Links in both directions, and one group per connected set of linked places."""
        parent = {}

        def root(x):
            parent.setdefault(x, x)
            while parent[x] != x:
                parent[x] = parent[parent[x]]
                x = parent[x]
            return x

        rows = []
        for (a, b), d in self.links.items():
            parent[root(a)] = root(b)
            rows += [(a, b, round(d, 1)), (b, a, round(d, 1))]
        self.con.executemany("INSERT INTO link VALUES (?,?,?)", rows)
        members = defaultdict(list)
        for x in list(parent):
            members[root(x)].append(x)
        updates = []
        for ids in members.values():
            group = "same-place:" + min(self.sources[i] for i in ids)
            updates += [(group, i) for i in ids]
        self.con.executemany("UPDATE place SET grp = ? WHERE id = ?", updates)
        self.con.execute("CREATE INDEX link_place ON link(place_id)")
        self.stats.update(links=len(self.links), groups=len(members), grouped_places=len(updates))

    # -- derived tables --------------------------------------------------------------------------------

    def name_table(self):
        self.con.executescript("""
            CREATE TABLE name (place_id INTEGER NOT NULL, norm TEXT NOT NULL, squash TEXT NOT NULL, core TEXT NOT NULL,
                               langs TEXT NOT NULL, kind TEXT NOT NULL, original TEXT NOT NULL, cmask INTEGER NOT NULL);
            INSERT INTO name SELECT place_id, norm, squash, core, langs, kind, original, cmask
                FROM stage.name_stage ORDER BY prominence DESC, place_id, norm;
            DROP TABLE stage.name_stage;
            CREATE INDEX name_squash ON name(squash);
            CREATE INDEX name_core ON name(core);
        """)

    def word_index(self):
        self.con.executescript("""
            CREATE VIRTUAL TABLE ftok USING fts5(norm, content='', detail='none', columnsize=0, tokenize='ascii');
            INSERT INTO ftok(rowid, norm) SELECT rowid, norm FROM name;
            INSERT INTO ftok(ftok) VALUES ('optimize');
            CREATE VIRTUAL TABLE temp.ftok_vocab USING fts5vocab(main, ftok, row);
            CREATE TABLE tokdf (token TEXT PRIMARY KEY, df INTEGER NOT NULL) WITHOUT ROWID;
            INSERT INTO tokdf SELECT term, doc FROM temp.ftok_vocab;
            DROP TABLE temp.ftok_vocab;
        """)

    def trigram_index(self):
        keys = [k for (k,) in self.con.execute("SELECT DISTINCT core FROM name WHERE length(core) BETWEEN 4 AND ?",
                                                (N.FUZZY_MAX_KEY,))]
        self.con.execute("CREATE TABLE fkey (id INTEGER PRIMARY KEY, key TEXT NOT NULL)")
        self.con.execute("CREATE TABLE fgram (gram TEXT NOT NULL, len INTEGER NOT NULL, n INTEGER NOT NULL, "
                         "ids BLOB NOT NULL, PRIMARY KEY (gram, len)) WITHOUT ROWID")
        postings = defaultdict(lambda: array.array("I"))
        for key_id, key in enumerate(keys, 1):
            n = len(key)
            for gram in N.trigrams(key):
                postings[(gram, n)].append(key_id)
        self.con.executemany("INSERT INTO fkey VALUES (?, ?)", enumerate(keys, 1))
        self.con.executemany("INSERT INTO fgram VALUES (?, ?, ?, ?)",
                             ((g, n, len(ids), ids.tobytes()) for (g, n), ids in sorted(postings.items())))
        self.stats["fuzzy_keys"], self.stats["fuzzy_postings"] = len(keys), sum(map(len, postings.values()))

    # -- postcodes -------------------------------------------------------------------------------------

    def postcodes(self, geonames_dir, countries):
        rows = []
        for country in countries:
            path = geonames_dir / "postcodes" / country / f"{country}.txt"
            if not path.is_file():
                self.log(f"GeoNames postcodes: {path} missing, skipped")
                self.stats["postcode_missing_files"] += 1
                continue
            with open(path, encoding="utf-8", errors="replace", newline="") as f:
                for line in f:
                    row = self.postcode_row(line.rstrip("\r\n").split("\t"), country)
                    if row:
                        rows.append(row)
        codes_at = defaultdict(set)
        for row in rows:
            codes_at[(row["country"], row["lat"], row["lng"])].add(row["code"])
        for row in rows:
            self.postcode_extent(row, len(codes_at[(row["country"], row["lat"], row["lng"])]))
        by_code = defaultdict(list)
        for row in rows:
            by_code[(row["country"], row["code"])].append(row)
        records, prefixes = [], defaultdict(list)
        for (country, code), members in by_code.items():
            lat, lng, extent = aggregate([(r["lat"], r["lng"], r["extent_m"], r["weight"]) for r in members])
            flags = sorted({r["accuracy"] for r in members if r["accuracy"] is not None})
            place_names = list(dict.fromkeys(r["place"] for r in members if r["place"]))
            shown = [{k: r[k] for k in ("place", "lat", "lng", "accuracy", "admin1", "admin2", "admin3", "geonames",
                                        "extent_m") if r[k] is not None} for r in members[:20]]
            info = {"geonames_accuracy": flags[0] if len(flags) == 1 else flags or None, "n_rows": len(members),
                    "places": shown, "extent_source": "assumed",
                    "extent_rule": "accuracy default, adjusted by the named place"}
            label = f"{code} {', '.join(place_names[:3])}".strip()
            records.append((country, code, "code", lat, lng, round(extent), label, compact_json(info)))
            if country == "PT":
                weight = sum(r["weight"] for r in members)
                prefixes[code[:4]].append((lat, lng, extent, weight, place_names, members))
        for prefix, codes in prefixes.items():
            lat, lng, extent = aggregate([(c[0], c[1], c[2], c[3]) for c in codes])
            place_counts = Counter(name for c in codes for name in c[4])
            flags = Counter(r["accuracy"] for c in codes for r in c[5] if r["accuracy"] is not None)
            admin = Counter((r["admin1"], r["admin2"]) for c in codes for r in c[5]).most_common(1)[0][0]
            info = {"geonames_accuracy": {str(k): v for k, v in sorted(flags.items())} or None,
                    "n_codes": len(codes), "n_rows": sum(len(c[5]) for c in codes),
                    "places": [{"place": name, "codes": n} for name, n in place_counts.most_common(10)],
                    "admin1": admin[0], "admin2": admin[1], "extent_source": "assumed",
                    "extent_rule": "covers the 4-3 codes' areas"}
            label = f"{prefix} {', '.join(name for name, _ in place_counts.most_common(3))}".strip()
            records.append(("PT", prefix, "prefix", lat, lng, round(extent), label, compact_json(info)))
        self.con.executemany("INSERT INTO postcode VALUES (?,?,?,?,?,?,?,?)", records)
        self.stats["postcode_rows"], self.stats["postcode_codes"] = len(rows), len(by_code)
        self.stats["postcode_prefixes"] = len(prefixes)

    def postcode_row(self, parts, country):
        if len(parts) != 12:
            self.stats["postcode_bad_rows"] += 1
            return None
        cc, code, place, admin1, _, admin2, _, admin3, _, lat, lng, accuracy = parts
        code = code.strip()
        where = point(lat, lng)
        if "CEDEX" in code.upper():  # French business-mail codes, not on street signs
            self.stats["postcode_cedex_skipped"] += 1
            return None
        if cc != country or not POSTCODE_FORMAT[country].match(code) or where is None:
            self.stats["postcode_bad_rows"] += 1
            return None
        accuracy = int(accuracy) if accuracy.strip().isdigit() else None
        return {"country": country, "code": code, "place": place.strip()[:MAX_NAME_CHARS], "lat": where[0],
                "lng": where[1], "accuracy": accuracy, "admin1": admin1.strip() or None,
                "admin2": admin2.strip() or None, "admin3": admin3.strip() or None, "geonames": None,
                "weight": POSTCODE_ROW_WEIGHT.get(accuracy, 0.5)}

    def postcode_extent(self, row, codes_here):
        """Set row["extent_m"] (and row["geonames"]): the accuracy flag's default, adjusted by the
        populated place (or admin unit) the row names. A point that several codes share is that
        place's centroid, so the code may lie anywhere in the place; a code's own point is only
        narrowed by it. Estimated points (flags 1-2) keep at least the default."""
        default = POSTCODE_EXTENT.get(row["accuracy"], 4000)
        match = self.nearest_place(row["place"], (row["lat"], row["lng"])) if row["accuracy"] != 6 else None
        extent = default
        if match:
            distance, place_extent, row["geonames"] = match
            reach = distance + place_extent
            if row["accuracy"] in (1, 2, None):
                extent = max(default, reach)
            else:
                extent = reach if codes_here >= POSTCODE_SHARED_POINT else min(default, reach)
        row["extent_m"] = round(extent)

    def nearest_place(self, place, where):
        """(distance_m, extent_m, source) of the GeoNames populated place, else admin unit, named
        `place` nearest to `where` within POSTCODE_PLACE_M; None when there is none."""
        norm = N.normalise(place)
        best = None
        for gid, glat, glng, _ in self.gn_by_key.get(N.keys(norm)[0], ()) if norm else ():
            fclass = self.gn_extent[gid][2]
            if fclass in "PA":
                d = haversine_m(where, (glat, glng))
                rank = (fclass != "P", d)
                if d <= POSTCODE_PLACE_M and (best is None or rank < best[0]):
                    best = (rank, gid)
        return (best[0][1], *self.gn_extent[best[1]][:2]) if best else None


def aggregate(members):
    """Weighted centre of (lat, lng, extent_m, weight) members, and the radius covering every member's extent."""
    total = sum(w for *_, w in members) or 1.0
    lat = sum(m[0] * m[3] for m in members) / total
    lng = sum(m[1] * m[3] for m in members) / total
    extent = max(haversine_m((lat, lng), (m[0], m[1])) + m[2] for m in members)
    return lat, lng, max(extent, 1.0)


def build(out=N.DEFAULT_PATH, wikidata=DEFAULT_WIKIDATA, geonames=DEFAULT_GEONAMES, countries=N.COUNTRIES,
          log=log_line):
    """Build the index at `out` (replacing it only on success) and return the build report."""
    out, wikidata, geonames = Path(out), Path(wikidata), Path(geonames)
    out.parent.mkdir(parents=True, exist_ok=True)
    for stale in list(out.parent.glob(f"{out.name}.tmp-*")) + list(out.parent.glob(f"{out.name}.stage-*")):
        stale.unlink()
    tmp = out.with_name(f"{out.name}.tmp-{os.getpid()}")
    stage = out.with_name(f"{out.name}.stage-{os.getpid()}")
    started, t0 = datetime.now(timezone.utc), time.monotonic()
    con = sqlite3.connect(tmp)
    try:
        con.execute("PRAGMA temp_store_directory = '{}'".format(str(out.parent.resolve()).replace("'", "''")))
        for pragma in ("journal_mode = OFF", "synchronous = OFF", "cache_size = -262144", "temp_store = FILE",
                       "threads = 4"):
            con.execute(f"PRAGMA {pragma}")
        con.execute("ATTACH DATABASE ? AS stage", (str(stage),))
        con.execute("PRAGMA stage.journal_mode = OFF")
        con.executescript(SCHEMA_SQL)
        builder = Builder(con, log)
        inputs = [file_record(wikidata)]
        builder.geonames(geonames, countries)
        builder.wikidata(wikidata)
        log(f"places: {builder.stats['places']:,}, names: {builder.stats['names']:,}, links: {len(builder.links):,}")
        builder.groups()
        builder.postcodes(geonames, countries)
        del builder.gn_by_key, builder.links
        log(f"postcodes: {builder.stats['postcode_codes']:,} codes, {builder.stats['postcode_prefixes']:,} PT prefixes")
        builder.name_table()
        con.execute("DETACH DATABASE stage")
        stage.unlink(missing_ok=True)
        log("name table sorted and indexed")
        builder.word_index()
        log("word index built")
        builder.trigram_index()
        log(f"trigram index: {builder.stats['fuzzy_keys']:,} keys, {builder.stats['fuzzy_postings']:,} postings")
        for country in countries:
            for kind in ("places", "postcodes"):
                path = geonames / kind / country / f"{country}.txt"
                if path.is_file():
                    inputs.append(file_record(path))
        stats = dict(builder.stats)
        stats["wikidata_rule_counts"] = dict(builder.wikidata_roles.rule_counts.most_common())
        report = {
            "schema": N.SCHEMA, "built_utc": started.isoformat(timespec="seconds"),
            "script": "tools/build_name_index.py", "python": sys.version.split()[0], "sqlite": sqlite3.sqlite_version,
            "unicodedata": unicodedata.unidata_version,
            "byteorder": sys.byteorder, "countries": list(countries), "inputs": inputs, "stats": stats,
            "constants": {"link_radius_m": LINK_RADIUS_M, "link_max_m": LINK_MAX_M, "max_names": MAX_NAMES,
                          "postcode_place_m": POSTCODE_PLACE_M, "postcode_shared_point": POSTCODE_SHARED_POINT,
                          "postcode_extent_m": POSTCODE_EXTENT, "populated_extent": POPULATED_EXTENT,
                          "stopwords": sorted(N.STOPWORDS)},
            "wikidata_rules": [[name, role, extent, pattern] for name, role, extent, pattern in WIKIDATA_RULES],
            "wikidata_default": WIKIDATA_DEFAULT, "geonames_extents": GEONAMES_EXTENTS,
            "geonames_admin": GEONAMES_ADMIN, "geonames_class_extent": GEONAMES_CLASS_EXTENT,
        }
        report["build_seconds"] = round(time.monotonic() - t0, 1)
        con.executemany("INSERT INTO meta VALUES (?, ?)",
                        [(k, json.dumps(v, ensure_ascii=False)) for k, v in report.items()])
        con.execute("ANALYZE")
        con.commit()
        con.execute("PRAGMA journal_mode = DELETE")
        con.close()
        os.replace(tmp, out)
    except BaseException:
        con.close()
        tmp.unlink(missing_ok=True)
        stage.unlink(missing_ok=True)
        raise
    report["build_seconds"] = round(time.monotonic() - t0, 1)
    report["bytes"] = out.stat().st_size
    report["peak_rss_mb"] = round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024)
    return report


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--out", type=Path, default=N.DEFAULT_PATH, help="index file (default: Data/index/names.sqlite)")
    ap.add_argument("--wikidata", type=Path, default=DEFAULT_WIKIDATA, help="wikidata_ptesfr.csv.gz")
    ap.add_argument("--geonames", type=Path, default=DEFAULT_GEONAMES, help="GeoNames folder (places/, postcodes/)")
    args = ap.parse_args()
    report = build(args.out, args.wikidata, args.geonames)
    stats = report["stats"]
    log_line(f"wrote {args.out}: {report['bytes'] / 1e6:,.0f} MB in {report['build_seconds']:,.0f} s; "
             f"{stats['places']:,} places, {stats['names']:,} names, {stats['links']:,} links, "
             f"{stats['postcode_codes']:,} postcodes; skipped: "
             + ", ".join(f"{k} {v:,}" for k, v in stats.items() if k.endswith(("bad_rows", "skipped", "no_name"))))


if __name__ == "__main__":
    main()
