# Country clues for panorama inference

Use readable identifiers first, distinctive physical features second, and broad landscape tendencies last. A municipal name, postcode, trail code or road marker can lead to a mapped area. Architecture and vegetation help compare candidates. The final camera position still requires map geometry or a reference-image match.

[country_clues.json](country_clues.json) contains **87 selected rules and 10 lookup tables** for Portugal, Spain and France. Each rule includes its observation, supported geography, qualitative strength, next action, exceptions and source references. The extraction uses the external country notes; challenge panoramas, answers and evaluation locations are excluded.

## Readable identifiers

| Observation | Geographic value | Next action |
|---|---|---|
| Full street, locality, landmark or business name | Can identify a specific place; common names remain ambiguous | Look up the full name and aliases with `panoloc.names`; use the surrounding sign text |
| `Câmara Municipal de X`, `Município de X`, `Junta de Freguesia de X` | Portuguese municipality or parish | Read and resolve X |
| `Ayuntamiento`, `Ajuntament`, `Concello` or `Udala` plus a name | Spanish local government and locality | Resolve the locality, including names on vado permits |
| `Mairie de X`, `Hôtel de Ville` or a department name | French commune or department | Resolve the full place name |
| Portuguese `NNNN-NNN` postcode | Postal area; first digit supplies a coarse region | Call `Names.postcode()` with the full code |
| Five-digit postcode, prefix 01–52 | Spain or France | Keep both countries until language/locality resolves it |
| French postcode, prefix 53–95 | Metropolitan French postal space within the challenge scope | Resolve the complete code; preserve special-recipient exceptions |
| `+351` / `+34` / `+33` | PT / ES / FR phone registration | Parse the entire number; explicit prefixes override national-format guesses |
| Portuguese nine-digit landline starting 2 | Numbering area: 21 Lisboa, 22 Porto, otherwise a listed three-digit prefix | Use the longest match in `pt_phone_areas` |
| Spanish geographic 8/9 telephone prefix | Province or numbering area, once Spain is established | Use `es_phone_areas`; exclude mobile/service ranges |
| `PR18 LLE`, `SERZEDELO GMR` | Loulé / Guimarães municipality | Validate the three-letter code, then look up the municipality or trail |
| Hunting-zone process number such as `3475-ICNF` | Portuguese hunting-zone polygon | Query ICNF by `num_def`, requesting WGS84 geometry; intersect the area with candidates |
| PT `IP` / `IC` road identifier | Portuguese route | Resolve the entire route and any kilometre marker |
| ES `CL`, `EX`, `AS`, `AG`, `RM`, `NA`, `LR` road designation | Regional road network | Use the road tables, then verify the full identifier in maps |
| FR yellow `D/RD`, cyan `M`, or contextual `T` identifier | Departmental network / metropolitan network / Corsica | Resolve the route with commune or department context |
| Road identifier plus km, hectometre or PR | A segment of a disambiguated road | Locate the marker and estimate the camera offset from visible geometry |
| Regional transport or newspaper name | Service/distribution area | Use the brand tables and corroborate with fixed local signage |

Direction arrows and advertisements may name distant places. An advertised phone number may belong to a head office. A postcode centroid, municipality polygon or landmark point describes its source object; it is not camera GPS.

## Country separators

| Feature | Portugal | Spain | France |
|---|---|---|---|
| Coherent text | Rua, Travessa, Câmara, Freguesia; ã/õ, lh/nh, -ção | Calle, Ayuntamiento; ñ, -ción | Rue, Impasse, Allée, Mairie; œ, du/des |
| Readable car plate | Two-character groups, including `AA 00 AA`; P band; older yellow right band | Four digits plus three consonants; E band | `AA-123-AA`; F band and blue department/logo band |
| Post box with identifiable logo | Red CTT; blue Correio Azul | Yellow Correos crown/horn | Yellow or heritage-brown La Poste |
| Paving | White limestone cubes and black/white calçada patterns provide medium support | Barcelona flower panot tiles provide a useful city hypothesis | Generic paving supplies little country separation |
| Curve chevrons | Yellow arrows on black | White arrows on black or blue | White arrows on blue |
| Road delineators | Thin wedge/small white reflector or flat/wide white reflector | Hollow post, black band, yellow/orange reflector | Round white post, pointed top, encircling reflective band |
| Guardrail reflectors | Red tendency | Yellow tendency; AP-15 Navarra is an exception | An unreadable or unseen reflector supplies no evidence |

PT/ES bollards overlap, especially on the left of Portuguese one-way carriageways. A blue-left-only plate fits modern Portugal as well as Spain. French plate departments are owner-chosen. Cars can travel. A single common accent, yellow box or white house is insufficient.

## Regional clues worth checking

| Candidate area | Useful visible or readable separators |
|---|---|
| Minho versus Galicia | Long stone granaries fit both. Use Portuguese versus Galician text, municipality names and independently visible road furniture |
| Porto | Pale green, notched street plaques with white serif capitals; read the street name; STCP/UNIR infrastructure |
| Douro | Dense vineyard terraces with schist retaining walls along a river valley; verify local names and terrain |
| Miranda do Douro / eastern Vimioso | Coherent Mirandese text, such as `Miranda de l Douro`, corroborated by locality names |
| Lisbon | White stone/tiled street plaques, calçada and Carris infrastructure; plaque style alone is medium support |
| Alentejo versus Extremadura | Montado/dehesa and whitewash fit both. Prefer text, hunting-zone identifiers, EX roads or clearly green-topped Spanish delineators |
| Algarve | Ornate lattice or round-spired white chimneys; full postcode beginning 8; 281/282/289 landline area; Vamus Algarve |
| Azores | Dark volcanic pasture walls; ornate Holy Spirit impérios; contextual `Canada` street names; island postcodes and utility/locality text |
| Madeira | Steep stone-walled terraces with bananas; stone delineators/red reflectors; yellow/black guardrails; Santana A-frame thatched houses; contextual `Vereda`/`Entrada` addresses |
| Asturias and neighbouring north-west Spain | Square wooden granaries on four pillars; AS roads; CTA infrastructure. The granary form is not exclusive |
| Bilbao | Oval blue street plaques in ornate gilded frames; resolve their names |
| Barcelona | Clearly recognisable flower panot paving and Catalan local text |
| Madrid | A square km marker with the red/white-star Madrid flag and a red M; resolve the whole road identifier |
| Andalucía / Almería–Motril | Readable Junta de Andalucía signs; extra-tall regional markers; extensive greenhouse landscapes provide medium support |
| Paris | Dark blue street plaque, green frame, arched top and readable arrondissement/street text |
| Lille | Street plaques with the identifiable red slanted fleur-de-lis; read the street name |
| Brittany | Breton text and local names, plus granite/slate/gable-end chimney architecture |
| Alsace / Moselle | Germanic local names, half-timbering and fish-scale roof tiles; half-timbering also occurs in Normandy |
| Franche-Comté | Imperial-domed bell towers with decorative glazed tiles; identify the actual church |
| Toulouse area | A coherent historic orange-brick streetscape plus southern French local text |
| Landes / Gironde | Extensive straight pine plantations on flat sandy ground, supported by local identifiers |
| Corsica | Coherent Corsican/French text, contextual T roads and a full 20xxx postcode |

Basque language and the ikurriña cross the France–Spain border. Catalan and the Senyera occur in Spain and Pyrénées-Orientales. Painted Basque timber framing tends towards France and unpainted framing towards Spain, with exceptions. Full local names are more useful than these tendencies.

## Corrections and limits

- French 01–05 phone prefixes are **weak historical regional hints**. Metropolitan geographic restrictions ended on **1 January 2023**, including for newly assigned numbers. [Arcep](https://www.arcep.fr/mes-demarches-et-services/consommateurs/fiches-pratiques/fin-du-decoupage-geographique-des-numeros-fixes-les-nouvelles-regles-en-vigueur.html)
- Portuguese older registrations can receive replacement plates using the newer design, with spaces and no yellow date band. The band’s absence does not exclude Portugal or establish vehicle age. [IMT](https://www.imt-ip.pt/noticias/comunicado-de-imprensa-novas-matriculas/)
- Preserve Spanish road-prefix collisions: **A**, **CA**, **GI**, **HU**, **LP**, **CV**, **C** and **CM**. Also preserve case distinctions such as **M / MA / Ma**. Resolve the complete route with map and sign context.
- A Portuguese mobile beginning 91/92/93/96 can resemble a Spanish landline. Match the complete number token and explicit country prefix before applying any national pattern.
- Eucalyptus supplies weak broad support. It must never hard-exclude France. Wetness, vegetation, architecture and scene resemblance are correlated.
- Street-type/toponym frequencies come from address records, not visible photographs. Use them only after full-name lookup fails, without converting percentages or lifts into probabilities.
- Small sign rims, reflector colours and crossing-stripe counts need close readable crops. `not_visible`, unreadable details, `other` and skipped questions supply no location evidence.

Google capture-car, antenna, camera-generation, blur and coverage clues are excluded. Raw transcript inventories, fuel/beer distribution guesses, unverified installation/tax-ID rules and changing department speed-limit lists are also excluded from the selected recognition rules.

## Using the JSON

The lookup tables retain complete identifier mappings where practical:

| Table | Entries |
|---|---:|
| `pt_postal_zones` | 9 |
| `pt_phone_areas` | 52 |
| `pt_municipal_codes` | 308 |
| `es_postal_provinces` | 52 |
| `es_phone_areas` | 50 rows of prefixes |
| `es_regional_roads` | 17 descriptive regional rows |
| `es_city_access_roads` | 50 descriptive access/ring-road rows |
| `fr_departments` | 96 |
| `regional_transport_brands` | 17 |
| `fr_regional_newspapers` | 25 |

Keep each retrieved rule’s exceptions, the table’s caveats and its source references together. `strength` is qualitative geographic informativeness, not recognition accuracy or a calibrated probability. `supports` lists compatible hypotheses; it is not a probability distribution or an unconditional geographic filter. Road ranges copied as descriptive notation must not be expanded into invented road identifiers.

```python
import json
from pathlib import Path

kb = json.loads(Path("knowledge_base/country_clues.json").read_text())
municipality = kb["lookup_tables"]["pt_municipal_codes"]["entries"]["LLE"]
rules = [r for r in kb["rules"] if r["feature"] == "chimney"]
```

Observe neutral attributes first, retrieve the relevant cross-country rules second, and geocode the resulting identifiers. Deduplicate the same object across views and limit the combined influence of related clues. LearnableMeta often repeats Plonk It, so their agreement is not independent confirmation. Use maps/reference imagery to place the camera and retain alternative hypotheses.

The existing OCR/VLM modules already contain their own country-clue tables. This JSON is a separate extraction for retrieval or future consolidation; the running pipeline has not been changed to load it.

## Sources

The JSON source catalog resolves upstream URLs and records the original note sections and line ranges. Document SHA-256 values identify the exact inputs. The research notes were compiled on 10 October 2026; only the Arcep and IMT corrections were additionally checked against official pages on 11 October. CTT-derived address associations use April 2020 data, and the Spanish kilometre-marker document ends in 2023. Guide maps describe approximate tendencies rather than verified geographic boundaries.

- [Portugal notes](<../research_notes/Country clues/portugal.md>): identifiers, Portuguese regions and transferable physical clues.
- [Spain notes](<../research_notes/Country clues/spain.md>): provinces, phones, roads, regional markers and language contrasts.
- [France notes](<../research_notes/Country clues/france.md>): departments, postal codes, regional text, brands and architecture.
- [Geomastr notes](<../research_notes/Country clues/geomastr.md>): supporting bollard comparisons and ambiguous examples.
- [Rainbolt notes](<../research_notes/Country clues/rainbolt.md>): the workflow of finding a distinctive object, consulting its public dataset and verifying candidates.

The original notes and optional example images are local research assets. The selected JSON contains the facts, mappings and resolved source URLs needed without loading those archives. Source facts remain distinct from observations made in any panorama.
