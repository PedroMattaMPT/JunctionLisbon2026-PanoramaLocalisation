# Country clues: Portugal, Spain, France

**Compiled:** 2026-10-10.
**Detail and sources:** `research_notes/Country clues/` (local only):
- `portugal.md`, `spain.md`, `france.md`: full tables, tested regexes and a source link on every clue
- `geomastr.md`, `rainbolt.md` (+ transcripts) and `img/`

**Related:** `PLAN.md` 3.1 (perception), 3.4 (questions), 4.3 (feature table) and 4.4 (rare-feature rules). `MODEL_DECISIONS.md` 4 (OCR parsing), which this extends.

Built only from external sources:
- the GeoGuessr guides Plonk It (Portugal updated 2026-06-20, Spain 2026-05-03, France 2026-08-25), GeoHints, LearnableMeta and community regionguessing docs
- Geomastr and Rainbolt's videos
- Wikipedia and official references: CTT, ANACOM, ICNF, the Portuguese road-sign regulation (RST), Correos, DGT, La Poste

No warm-up panorama and no `Data/warmup_locations.*` was used, so all of it may go into the agent's knowledge base (`RULES.md`).

## 0. Read this first

- **The guides are written for the Google car on a road.** Our camera is handheld, so road furniture (bollards, km markers, guardrails, chevrons) only shows up in road scenes. In squares, piers, cafés and on trails, the useful clues are:
  - text
  - street-name plaques
  - post boxes, paving and shop fronts
  - walls, roofs and vegetation

  Google-car meta (camera generation, antenna, blur, coverage) was dropped. Each note lists what it dropped in its §7.
- **Text beats everything.** A postcode, landline number, road number, municipality code or "Câmara Municipal de X" often names the municipality outright (§2). That is the main route to urban precision.
- **Every clue is soft evidence.** Cars travel, brands cross borders, and the Basque and Catalan languages and flags exist on both sides of the Pyrenees.
  - Strength: **strong** = usually settles it on its own; **medium** = shifts the odds a lot but has look-alikes; **weak** = only a prior.
  - Treat unseen features as missing, not absent (PLAN 4.3).
- **Hard** marks details that need a close, full-resolution crop, such as sign rims and stripe counts.

## 1. Portugal, Spain or France: the fast separators

| Clue | Portugal | Spain | France | Strength |
|---|---|---|---|---|
| **Letters and words** | ã õ ç â ê ô; lh, nh; -ção/-ções; da/do/não/uma | ñ, ¿ ¡; -ción; y, del, los. Catalan: l·l, à è ò, "i". Galician: x, "unha", no ç/ã. Basque: tx, tz, k | é è ê à ù, **œ**; -eux/-aux; du/des. Breton: c'h, zh | strong |
| **Street word** | Rua, Travessa, Largo, Praceta, Beco | Calle (C/), Avda.; Carrer; **Rúa** (accent); Kalea | Rue, Impasse, Allée, Chemin, Place, Quai | strong |
| **Local government** | Câmara Municipal, Município de X, Junta de Freguesia | Ayuntamiento; Ajuntament; Concello; Udala | Mairie, Hôtel de Ville | strong |
| **Number plates** | "P" band; **yellow right band** with year over month (1998–2020); `AA 00 AA` since 2020 (no band); `00-AA-00`, `00-00-AA`; black plates before 1992 | "E" band only; `0000 BBB` (consonants only); old provincial `M-1234-AB` | "F" band **and a blue right band** with region logo and department number; `AA-123-AA`; old `123 ABC 75`; yellow rear plates (1993–2007) | strong |
| **Post boxes** | **red** CTT; blue = Correio Azul | **yellow** Correos, crown-and-horn logo | **yellow** La Poste, rectangular, blue label; brown in heritage areas | strong |
| **Phone format** | 9 digits; landline **2**…; mobile 91/92/93/96 | 9 digits; landline 9…/8…; mobile 6…/7… | **10 digits**, `0X XX XX XX XX` | strong |
| **Postcode** | `NNNN-NNN` | 5 digits, 01–52 | 5 digits, 01–95 (Corsica 20) | strong (ES and FR overlap on 01–52) |
| **Road numbers** | `A2`, `IP3`, `IC1`, `N125`/`EN125`, `ER`, `EM`, `CM` | **hyphen** inside a coloured box: `N-260`, `AP-7`, `CL-517` | **no hyphen**: `D 914` on a **yellow** plate, `N 7`, `A 63`, `M 6`, `T 20` | strong. IP/IC means PT, a hyphen means ES, D means FR. Bare A/N fit PT and FR |
| **Bollards** | Thin white wedge, black band, small white reflector; or a flat post with a wide reflector. Yellow-orange ones only on the left of motorway carriageways | Hollow white post, black band, **yellow-orange rectangle** in front, two white dots behind | **Round white post, pointed top, grey or red band** | ES/FR strong, PT medium |
| **Guardrail reflectors** | red | yellow | none | medium-strong |
| **Curve chevrons** | **black with yellow arrows** | black/white or blue/white | blue/white (1–5 arrows) | strong for PT |
| **Direction signs** | White arrow-shaped plate, black border, black arrowhead that doesn't touch the border; green panels on IP roads | White, with **coloured road-number boxes** | White, black outline set in from the edge, pointed end, small places in *italics*; **yellow "D" plate** on top | strong |
| **Km markers** | Wide white plate with a coloured left part cut diagonally (red IP, black IC, blue A); "tombstone" with a black base (N/ER) or yellow base (EM) | Flat plate, coloured header with the code, "km"; shape and border vary by region (§5) | White with a **yellow (D) or red (N) rounded top**; motorway plate with a decimal | strong |
| **Red-bordered signs** (hard) | thin white rim outside the red | red runs to the edge | thin white rim | strong ES vs the others |
| **Pedestrian-crossing sign** (hard) | 5 stripes, figure wears a belt | **8 stripes** | 5 stripes, head detached | strong for ES |
| **Utility poles** | Concrete "ladder" with **tall** openings, often with a see-through hole | Short-step "waffle" ladder | Short-step ladder; wooden or octagonal metal pole with a **small blue plate** | medium (blue plate: strong) |
| **Rural edge lines** | solid white | solid or dashed, by region | **long, widely spaced dashes**; an "offset-block" centre line is unique | medium |
| **Hunting signs** | **Red and white**: rectangles "ZONA DE CAÇA …" with a process number, diamonds, or small red-white-red plates on fences | White "COTO PRIVADO DE CAZA" with a plate such as `M-10.001`; small black/white diagonal squares | — | strong PT vs ES |
| **Paving** | **Calçada portuguesa**: small white limestone cubes, black patterns; square setts laid diagonally on roads | Barcelona's grey "flower" panot tiles | — | medium-strong |
| **Houses** | Whitewash with **blue or yellow painted bands** (south); azulejo façades; in the north, grey concrete blocks with **white mortar** | Whitewashed towns (Andalucía, Extremadura); Galicia's bare concrete blocks; unpainted timber frames (Basque Country) | Red brick (north; bright orange in Toulouse); **painted** timber frames (French Basque Country); slate roofs in the north-west | medium |
| **Trees** | Eucalyptus everywhere in the north and centre; cork-oak montado; maritime and stone pine | Eucalyptus mainly on the north coast and in Huelva; olives, dehesa, cereal | **Eucalyptus essentially absent**; Landes pine, lavender, hedged bocage | medium (eucalyptus vs FR: strong) |
| **Shops and kiosks** | **Multibanco "MB"**; Super Bock, Sagres, Delta umbrellas; Galp, Prio, Alves Bandeira | ONCE lottery kiosks; "VADO PERMANENTE" plates; Mercadona; Repsol, Cepsa/Moeve; Mahou, Estrella, Cruzcampo | Red **"TABAC" double cone**; FDJ; Super U, Monoprix; TotalEnergies; regional newspapers | medium-strong |
| **Police** | GNR, PSP | Guardia Civil, Policía Local; regional: Mossos (Catalonia), Ertzaintza (Basque Country), Policía Foral (Navarra), Policía Canaria | Gendarmerie, Police municipale | strong |

Separators that work in a pedestrian scene with no road: language, street plaques, post boxes, paving, house style, shop brands and parked-car plates.

## 2. Text → place (OCR + regex)

Run on all OCR text, then pass the hits to the name index (PLAN 4.4, T16). Never accept digits that only the VLM saw.

| Read by OCR | Portugal | Spain | France |
|---|---|---|---|
| **Postcode** | The 1st digit gives the region (table below). The **4-digit prefix gives the municipality** (760 prefixes, `portugal.md` 4.1) | First 2 digits = **province** (01–52). A 3rd digit of 0 = the provincial capital | First 2 digits = **department** (20 → 2A/2B). `xx000` = the prefecture. Arrondissements: Paris 75001–75020, Lyon 69001–69009, Marseille 13001–13016 |
| **Landline** | 21 Lisbon, 22 Porto, `2xx` = area (table below) | `9xx`/`8xx` → province (91 Madrid, 93 Barcelona; `spain.md` 4.2) | `0Z AB …`: Z = zone 1–5, AB = old department code (`france.md` 4.2). Weaker since nationwide number portability (2023/24) |
| **Mobile** | 91/92/93/96: no region | 6…/7…: no region | 06/07: no region |
| **Plates** | Country and era only. Trailers carry a district-office code | Current plates: none. **Old provincial** codes → province | SIV right band: the **owner chooses** the department (weak). Old FNI suffix = the registration department (medium) |
| **Road numbers** | IP/IC/A route lists. N1xx–N3xx are numbered north → south. EM/CM numbers repeat in every district | The prefix gives the community or province (CL, EX, AG, CV…), plus about 45 city ring-road codes (SC-20 Santiago, GJ-10 Gijón…) | D numbers repeat in every department. M = a métropole, T = Corsica |
| **Municipality** | "Câmara Municipal de X", "Junta de Freguesia de X", "União das Freguesias de X e Y" | "Ayuntamiento / Ajuntament / Concello de X", also on vado plates | "Mairie de X"; the commune on town entry signs |
| **Special codes** | **3-letter municipality code** on trail signs (`PR18 LLE` = Loulé), postal names (`SERZEDELO GMR`) and E-REDES plates (`PNI-D-0011`). **Hunting-zone process number** (`3475-ICNF`) → the zone polygon from the public ICNF map service (`portugal.md` 4.7; **prefetch it before Sunday**) | Hunting-reserve plate (`M-10.001`) → province. Regional-government names and web domains (xunta.gal, gva.es, euskadi.eus, juntadeandalucia.es…) → community. `.cat`/`.gal`/`.eus` | Regional newspapers (Ouest-France, Sud Ouest, La Dépêche…) → departments. Regional transport brands (BreizhGo, Aléop, Rémi, Nomad, Fluo, Mobigo, liO, Zou!) → region |
| **Transport** | Carris Metropolitana (Lisbon area), UNIR (Porto area), Vamus Algarve, STCP, Carris | CTA (Asturias), EMT and green interurban buses (Madrid) | see above |

**Collisions to resolve with the language or other cues:**
- `91x xxx xxx`: a Portuguese mobile or a Madrid landline. The digit grouping helps: PT writes 3-3-3, ES often 2-3-2-2.
- 5-digit postcodes 01–52: 31 is Haute-Garonne or Navarra, 20 is Corsica or Gipuzkoa, 17 is Charente-Maritime or Girona.
- `M` + number: a PT municipal road, a French métropole road, or a Madrid km marker.
- Spanish prefixes with two meanings: A, CA (Cantabria or Cádiz), GI (Girona or Gipuzkoa), HU (Huesca or Huelva). See `spain.md` 4.4.

**Core regexes.** Tested on sample strings; the full sets with region mappings are in the notes.

```python
PT_POSTCODE  = r'(?<!\d)([1-9]\d{3})\s?[-–]\s?(\d{3})(?!\d)'
ES_POSTCODE  = r'(?<![\d.,/])((?:0[1-9]|[1-4]\d|5[0-2])\d{3})(?![\d.,/])'          # needs context: "C.P.", a town name
FR_POSTCODE  = r"(?<!\d)((?:0[1-9]|[1-8]\d|9[0-5])\d{3})\s+([A-ZÉÈÀÂÊÎÔÛÇ' \-]{2,})"  # postcode + COMMUNE in capitals

PT_PHONE     = r'(?<![\d+])(?:(?:\+|00)\s?351[\s.\-]?)?((?:2\d|9[01236])(?:[\s.\-]?\d){7})(?!\d)'
ES_PHONE     = r'(?<![\d+])(?:(?:\+|00)\s?34[\s.\-]?)?([6789](?:[\s.\-]?\d){8})(?!\d)'
FR_PHONE     = r'(?<![\d+])0[1-9](?:[\s.\-]?\d{2}){4}(?!\d)|\+33\s?(?:\(0\)\s?)?[1-9](?:[\s.\-]?\d{2}){4}(?!\d)'

PT_PLATE     = r'(?<![A-Z0-9])(?:\d{2}-\d{2}-[A-Z]{2}|\d{2}-[A-Z]{2}-\d{2}|[A-Z]{2}[\s-]?\d{2}[\s-]?[A-Z]{2}|[A-Z]{2}-\d{2}-\d{2})(?![A-Z0-9])'
ES_PLATE     = r'(?<![A-Z0-9])\d{4}[\s\-·]?[BCDFGHJKLMNPRSTVWXYZ]{3}(?![A-Z0-9])'   # since 2000; no vowels
FR_PLATE_SIV = r'(?<![A-Z0-9])[A-HJ-NP-TV-Z]{2}[\s-]?\d{3}[\s-]?[A-HJ-NP-TV-Z]{2}(?![A-Z0-9])'  # Italy's plates match too

PT_ROAD      = r'\b(?:A\s?\d{1,2}|IP\s?[1-9]|IC\s?(?:[1-9]|[12]\d|3[0-7])|(?:EN|ER|N|R)\s?\d{1,3}(?:\s?-\s?\d{1,2})?|(?:EM|M)\s?[5-9]\d\d|CM\s?1\d{3,})\b'
ES_ROAD      = r'(?<![A-Za-z0-9])(?:EX-A\d{1,2}|(?:AP|[A-Z][A-Za-z]{0,2}(?:-[PV])?)-(?:\d{1,4}(?:\.\d{1,2})?|[IVX]{1,4}))(?!\d)'  # then whitelist the prefix
FR_ROAD      = r'\b(?:RD|RN|D|T)\s?\d{1,4}\b'                                  # France-only prefixes

PT_TRAIL     = r'\b(PR|GR)\s?(\d{1,3})\s?([A-Z]{3})\b'                         # group 3 = municipality code
PT_HUNT      = r'\b(\d{1,4})\s?[-–]\s?(ICNF|DGF)\b'                              # ICNF zone process number
```

**Portuguese postcode, first digit** (shares from the CTT data):

| 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 |
|---|---|---|---|---|---|---|---|---|
| Lisbon city | Lisbon region, Setúbal peninsula, Santarém, Oeste | Aveiro, Coimbra, Viseu, N Leiria | Porto, Braga, Viana do Castelo | Vila Real, Bragança, Douro | Castelo Branco, Guarda | Alentejo (Beja, Évora, Portalegre, S Setúbal) | Algarve | 90–94 Madeira, 95–99 Azores |

**Portuguese landline codes** (ANACOM area names):
- **Norte:** 22 Porto · 251 Valença · 252 V. N. de Famalicão · 253/257 Braga · 254 Peso da Régua · 255 Penafiel · 256 S. João da Madeira · 258 Viana do Castelo · 259 Vila Real · 273 Bragança · 276 Chaves · 278 Mirandela · 279 Moncorvo
- **Centro:** 231 Mealhada · 232 Viseu · 233 Figueira da Foz · 234 Aveiro · 235 Arganil · 236 Pombal · 238 Seia · 239 Coimbra · 244 Leiria · 271 Guarda · 272 Castelo Branco · 274 Proença-a-Nova · 275 Covilhã · 277 Idanha-a-Nova
- **Lisbon and Tejo:** 21 Lisboa · 241 Abrantes · 243 Santarém · 249 Torres Novas · 261 Torres Vedras · 262 Caldas da Rainha · 263 V. Franca de Xira · 265 Setúbal
- **Alentejo:** 242 Ponte de Sor · 245 Portalegre · 266 Évora · 268 Estremoz · 269 Santiago do Cacém · 283 Odemira · 284 Beja · 285 Moura · 286 Castro Verde
- **Algarve:** 281 Tavira · 282 Portimão · 289 Faro
- **Islands:** 291 Funchal · 292 Horta · 295 Angra do Heroísmo · 296 Ponta Delgada

**Spanish province codes.** The postcode prefix and the landline prefix give the same province:

01 Álava 945 · 02 Albacete 967 · 03 Alicante 965/966 · 04 Almería 950 · 05 Ávila 920 · 06 Badajoz 924 · 07 Baleares 971 · 08 Barcelona 93 · 09 Burgos 947 · 10 Cáceres 927 · 11 Cádiz 956 · 12 Castellón 964 · 13 Ciudad Real 926 · 14 Córdoba 957 · 15 A Coruña 981 · 16 Cuenca 969 · 17 Girona 972 · 18 Granada 958 · 19 Guadalajara 949 · 20 Gipuzkoa 943 · 21 Huelva 959 · 22 Huesca 974 · 23 Jaén 953 · 24 León 987 · 25 Lleida 973 · 26 La Rioja 941 · 27 Lugo 982 · 28 Madrid 91 · 29 Málaga 951/952 · 30 Murcia 968 · 31 Navarra 948 · 32 Ourense 988 · 33 Asturias 984/985 · 34 Palencia 979 · 35 Las Palmas 928 · 36 Pontevedra 986 · 37 Salamanca 923 · 38 S. C. de Tenerife 922 · 39 Cantabria 942 · 40 Segovia 921 · 41 Sevilla 954/955 · 42 Soria 975 · 43 Tarragona 977 · 44 Teruel 978 · 45 Toledo 925 · 46 Valencia 960–963 · 47 Valladolid 983 · 48 Bizkaia 944/946 · 49 Zamora 980 · 50 Zaragoza 976 · 51 Ceuta (956) · 52 Melilla (952). The 8XX range mirrors 9XX.

**French phone zones:**
- **01:** Île-de-France
- **02:** north-west (Bretagne, Normandie, Pays de la Loire, Centre-Val de Loire)
- **03:** north-east (Hauts-de-France, Grand Est, Bourgogne-Franche-Comté)
- **04:** south-east (Auvergne-Rhône-Alpes, PACA, Corsica, and Languedoc-Roussillon: 11, 30, 34, 48, 66)
- **05:** south-west (Nouvelle-Aquitaine, and Midi-Pyrénées: 09, 12, 31, 32, 46, 65, 81, 82)

## 3. Border areas where the countries look alike

| Pair | Same on both sides: don't over-weight | Separators |
|---|---|---|
| **Galicia ↔ Minho / Trás-os-Montes** | Granite, eucalyptus, maritime pine, maize, granaries (hórreos ↔ espigueiros) | Galician ñ/x, "unha", "Rúa", "Concello", place names starting A / O / As / Os, versus PT ç/ã/õ, "Rua", "Junta de Freguesia". Then: yellow vs red guardrail reflectors; black/white vs **black/yellow** chevrons; 8 vs 5 pedestrian stripes; no rim vs white rim; yellow vs red post boxes; concrete blocks without vs **with white mortar** |
| **Castilla y León ↔ Trás-os-Montes / Beiras** | Plateaus, cereal, stone villages | Dashed edge lines (common in CyL, almost absent in PT); hunting signs (black/white vs red/white). Mirandese bilingual signs exist on the PT side (Miranda do Douro) |
| **Extremadura ↔ Alentejo / Beira Baixa** | Dehesa = montado; whitewashed towns | PT houses have **blue or yellow bands**. ES only: EX codes, **green-topped bollards**, dashed edge lines, "coto … caza" signs (a code starting "EX" = Extremadura) |
| **Huelva / Sevilla ↔ Algarve / Baixo Alentejo** | White towns, citrus, eucalyptus | **Algarve chimneys**, especially the round ones (strong); "Junta de Andalucía" signs with a green left stripe on the ES side |
| **Spanish ↔ French Basque Country** | Basque language, ikurriña, big white farmhouses | "**kalea**" vs "**karrika**"; Basque on top of a black-bordered sub-plate (ES) vs Basque in a **thinner font** (FR); **unpainted** vs **red or green painted** timber frames; one plate band vs two; yellow-orange bollards vs round white ones |
| **Aragón / Navarra ↔ French Pyrenees** | Stone villages, dark roofs, pines | Spanish square, black-bordered km markers vs French bornes; plates; bollards; sign rims; hyphenated codes vs a yellow "D" plate |
| **Catalonia ↔ Roussillon (66) ↔ Andorra** | Catalan language, Senyera | Roussillon: Catalan **with French** (Mairie, Rue), French plates and furniture. Catalonia: Catalan with Spanish, "Gual permanent", estelada flags. Andorra: an orange dot on plates, CG/CS road codes. Llívia is a Spanish exclave inside France; the Val d'Aran (Spain) uses Aranese ("carrèr", eth/era) |

## 4. Portugal by region

Most panoramas are Portuguese, so this level matters most. The full clue tables are in `portugal.md` §3.

| Region | Codes | Landscape | Buildings and streets | Strongest tells |
|---|---|---|---|---|
| **Minho and Porto** (Viana do Castelo, Braga, Porto) | 4xxx; 22, 251–253, 255–258 | Green, wet hills; eucalyptus, maritime pine; small maize fields; vines high on pergolas | Granite; concrete blocks with white mortar; granite paving in Porto | **Espigueiros** (Soajo, Lindoso); **Porto plaques**: pale lime-green, white serif capitals, notched top; UNIR / STCP; "Quelha" (53% are in Viana do Castelo); names ending -ães, -elo, -ufe, -mil, or starting Souto, Bouça, Paço |
| **Trás-os-Montes and Douro** (Vila Real, Bragança, N Viseu and Guarda) | 5xxx; 259, 254, 273, 276, 278, 279 | High plateaus; olives in the north-east | Granite, schist | **Douro schist vineyard terraces**; **Mirandese** bilingual signs (lh-, "l"/"ls" articles: "Miranda de l Douro") |
| **Centro** (Aveiro, Coimbra, Viseu, N Leiria, Guarda, Castelo Branco) | 3xxx, 6xxx; 23x, 244, 271, 272, 274, 275, 277 | Eucalyptus and pine hills; Mondego rice | **Schist villages** (Lousã, Açor ranges) | **Serra da Estrela**: granite boulders and **yellow-black snow poles**; "Aldeia …" (Guarda, Castelo Branco); "Póvoa …" (Aveiro, Viseu) |
| **Lisbon, Oeste, Tejo, Setúbal** | 1xxx (Lisbon city), 2xxx; 21, 24x, 26x | Oeste farmland; Tejo/Sorraia rice; **pines on white sand** (Setúbal–Sines) | Azulejo façades; calçada with black patterns; trams | **Lisbon plaques**: white limestone, black serif capitals, **four corner bolts**; black plaques with white capitals; azulejo plaques. Carris / Carris Metropolitana. "Casal", "Praceta", "Azinhaga", "Escadinhas"; "Pinhal …" and "Courela …" (Setúbal) |
| **Alentejo** (Portalegre, Évora, Beja, S Setúbal) | 7xxx; 242, 245, 266, 268, 269, 283–286 | **Montado** (scattered cork and holm oaks); cereal; dense olive hedgerows around Alqueva | Whitewash with **blue or yellow bands**; big chimneys; whitewashed farmsteads (montes) | Place names "Monte …" and "Herdade …"; addresses on "Estrada / Caminho Municipal" |
| **Algarve** (Faro) | 8xxx; 281, 282, 289 | Citrus on the south coast; dry scrub in the south-west | Whitewash; decorated parapets (platibandas) | **Ornate chimneys**, especially the round ones; N125 / A22; "Cerro …" (78% Faro); "Urbanização"; Vamus Algarve |
| **Azores** | 95xx–99xx; 292, 295, 296 | **Black basalt walls**, hydrangeas, Japanese cedar, black-and-white cows | Pastel walls with **grey trims**, green shutters; azulejo plaques; Impérios (small Holy Spirit chapels) | "Canada" street word (99% Azores); roads like "R1-1ª"; EDA; Especial beer; Azores flag |
| **Madeira** | 90xx–94xx; 291 | Very steep terraces, bananas, agapanthus | White, grey or pastel houses; A-frame thatched houses at Santana | **Stone bollards with a red reflector**; yellow-black guardrails; "Vereda", "Entrada"; VR1 / ER 101; EEM; Coral beer |

Clues that hold across Portugal:
- calçada and azulejos
- red CTT boxes and Multibanco
- Super Bock leans north and Sagres south (weak)
- GNR covers rural areas and most towns; PSP covers the big cities on the mainland

## 5. Spain by community (short)

`spain.md` §3 has full profiles, km-marker and edge-line maps, flags and city ring-road codes.

| Community | Strongest tells |
|---|---|
| **Galicia** | Galician language; **A / O / As / Os** place names; "Concello" signs with a green or blue top strip; hórreos; bare concrete-block houses; km markers whose border colour doesn't match the header; AG / VG / AC / LU / OU / PO / DP / EP codes; `.gal`; Camino scallop shells |
| **Asturias** | **Square hórreos on 4 pillars**, slate in the west; red-post CTA bus stops; COGERSA bins; yellow snow poles; AS codes; Xixón / Uviéu |
| **Cantabria** | Green meadows; big white farmhouses with unpainted timber; CA codes; S-10…S-30 (Santander) |
| **Basque Country** | Basque **on top** of bilingual sub-plates; "kalea"; **round-topped km markers** (Bizkaia); yellow-capped stone markers (Araba); grey markers (Gipuzkoa); **oval gilded plaques** (Bilbao); Ertzaintza; BI / GI / A codes; `.eus` |
| **Navarra** | Spanish **on top** of Basque; green Pyrenees in the north, Ebro semi-desert in the south; NA codes; red reflectors on the AP-15; Policía Foral |
| **La Rioja** | Vineyards on a plain with mountain ranges to the north and south; LR codes |
| **Aragón** | **Square, black-bordered km markers**; flat white stick bollards with grey reflectors; Ebro badlands, red soil in Teruel; "COMUNIDAD DE ARAGÓN" boundary signs; A-xxxx codes |
| **Catalonia** | Catalan ("carrer", "i", l·l); round ribbed signposts; Senyera / estelada; **square orange-reflector bollards** (Lleida, Tarragona); Barcelona panot tiles, marble plaques, black-and-yellow taxis; Mossos; C- codes; Aranese in the Val d'Aran |
| **Castilla y León** | Meseta cereal flats; dashed edge lines; CL codes; tall white posts with the Junta arms and an orange lower half; magenta, purple or grey-blue provincial markers; stone pines around Valladolid |
| **Madrid** | **Square km markers topped by the Madrid flag** (red, white stars) with a red "M"; green interurban buses; red bus stops; M-30 / M-40 / M-50 |
| **Castilla-La Mancha** | Flat vineyards and olives on red soil; **square, blue-bordered km markers**; CM codes; field-boundary stones painted blue on the left |
| **Extremadura** | Dehesa; whitewashed towns; **green-topped bollards** (unique); square EX markers with a bottom reflector; Fala bilingual signs (Jálama valley) |
| **Andalucía** | "Seas" of olives (Jaén, Córdoba); white villages; **plastic greenhouses** (Almería–Motril); "Junta de Andalucía" signs with a **green left stripe**; **extra-tall km markers**; blue-and-yellow snow poles (Sierra Nevada) |
| **Murcia** | Arid land, hazy bare mountains; **small square chevrons with a red arrow on white** (unique); steel lattice poles; RM / MU codes |
| **Valencian Community** | Orange groves; Valencian and Spanish mixed ("Gual permanent"); "Generalitat Valenciana" strip on km markers; CV codes; Aleppo pine |
| **Balearic Islands** | Dry-stone walls; "Es / Sa / Ses / S'" names; island road codes Ma- / Me- / EI- / PM-; Mallorca's white stone markers with a yellow top |
| **Canary Islands** | Volcanic land; island codes GC / TF / LZ / FV / LP / HI / GM, never N/A/AP; "guagua"; Lanzarote vines in semicircular stone pits |

## 6. France by region (short)

`france.md` §3 also covers roof, brick, place-name suffix and signpost-colour gradients, and the 80/90 km/h speed-limit patchwork.

| Region | Strongest tells |
|---|---|
| **Hauts-de-France** | Rows of dark red brick; wind turbines; -court; Flemish -ghem / -hem names; **Lille plaques with a red fleur-de-lis**; La Voix du Nord |
| **Normandie** | Hedged bocage lanes, cows; slate in the west; **-ville**, -tot, -bec; Ouest-France; Nomad |
| **Bretagne** | Black slate roofs, **chimneys on the gable ends**, granite; **Breton** bilingual signs (c'h, zh, "Straed"); Plou- / Ker- / Tre- names; Gwenn-ha-du flag; dark green signposts; BreizhGo |
| **Pays de la Loire** | Slate north of the Loire; low white houses with red tiles on the Vendée coast; salt pans; names ending -é; Aléop |
| **Centre-Val de Loire** | The flat, hedgeless Beauce cereal plain; Sologne flat tiles; decimal D numbers (D134.10, mostly 28); Rémi |
| **Île-de-France** | **Paris plaques**: dark blue, green frame, arched top, arrondissement; mansard roofs; Haussmann buildings; brown posts (77); zone 01; Le Parisien |
| **Grand Est** | Alsace: half-timbering, fish-scale tiles, "Gass" / "Stross", names in -heim / -ach / -willer. Lorraine: -ange / -ing / -court / -rupt. Champagne vineyards; Marne's combined entry/exit sign; Fluo |
| **Bourgogne-Franche-Comté** | **Imperial-dome bell towers** with glazed tiles (Franche-Comté); reddish asphalt (Yonne); -ey / -ans; Mobigo |
| **Auvergne-Rhône-Alpes** | Alpine chalets, onion-shaped spires, -oz / -az; Massif Central stone-slab or slate roofs, -at; **Lyon plaques** with corner bolts; light-yellow plaques (Saint-Étienne); blue-and-white region logo |
| **Nouvelle-Aquitaine** | **Flat Landes pine monoculture**; claret-red square posts around Bordeaux; Pays Basque **painted timber** and "karrika"; -ac; Sud Ouest |
| **Occitanie** | **Bright orange brick** (Toulouse); red-and-yellow **Occitan cross** logo, liO; **Catalan + Senyera** in the Roussillon (66); -argues; La Dépêche, Midi Libre |
| **PACA** | Riviera palms, **azure-blue posts**; rows of tiles under the eaves (génoises); lavender; Provence flag with **vertical** stripes; Marseille plaques; "Région Sud", Zou!; La Provence, Nice-Matin |
| **Corse** | Corsican (chj, ghj, -u endings; "carrughju"); **T roads**; Moor's head flag; 20xxx; Corse-Matin |

## 7. Proposed VLM checklist

Merged from the three notes' §6. Every item also takes `not_visible` and `other`, which imply nothing. Ask about the object first, then its attributes. Use crops at about 40–75% of image height, outside the photographer mask. Leave plate characters, phone numbers, postcodes, road numbers and codes to OCR.

**A. Any scene**

| # | Key | Options → implication |
|---|---|---|
| 1 | `sign_language` | `portuguese` PT · `spanish` ES · `catalan` Catalonia, Valencia, Balearics, 66 · `galician` Galicia · `basque` Basque areas (ES or FR) · `french` FR · `breton` Brittany · `occitan` Toulouse, Avignon · `corsican` Corsica |
| 2 | `plate_layout` | `blue_left_yellow_right` PT 1998–2020 (strong) · `blue_both_ends` FR (strong) · `blue_left_only` ES or PT 2020+ · `black_plate_white_chars` PT before 1992 or old FR · `yellow_rear_plate` old FR |
| 3 | `post_box` | `red` PT (strong) · `blue_correio_azul` PT · `yellow_crown_horn_logo` ES (strong) · `yellow_la_poste_logo` FR (strong) · `brown_la_poste` FR |
| 4 | `street_plaque` | `white_stone_black_serif_corner_bolts` Lisbon · `blue_on_white_azulejo` PT (Lisbon, Azores) · `black_plate_white_caps` Lisbon · `pale_green_white_serif` Porto · `white_marble_black_caps` Barcelona or generic PT (weak) · `oval_blue_gilded_frame` Bilbao · `dark_blue_coat_of_arms` Madrid · `dark_blue_green_frame_arched` Paris · `red_fleur_de_lis` Lille · `corner_bolts_notched_border` Lyon · `light_yellow` Saint-Étienne |
| 5 | `pavement` | `white_limestone_cubes` PT (medium-strong) · `black_white_mosaic` PT · `dark_basalt_white_patterns` Azores, Madeira · `flower_panot_tiles` Barcelona · `granite_slabs` N PT, Porto (weak) · `diagonal_square_setts` PT · `asphalt` · `dirt` |
| 6 | `wall_finish` | `whitewash_blue_or_yellow_bands` S PT (medium-strong) · `whitewash_plain` S PT, Andalucía, Extremadura · `azulejo_facade` PT · `concrete_blocks_white_mortar` N PT · `concrete_blocks_plain` Galicia · `granite` N PT, Galicia, Brittany · `dark_schist` PT Centro, Douro · `dark_red_brick` N FR, Paris (strong) · `orange_brick` Toulouse (strong) · `white_painted_timber` French Basque (strong) · `white_unpainted_timber` Spanish Basque, Navarra, Cantabria · `half_timbering` Alsace, Normandy · `haussmann_limestone` Paris · `pastel_grey_trims_green_shutters` Azores |
| 7 | `roof` | `orange_canal_tiles` south (weak) · `dark_slate` NW Spain interior, NW France, Massif Central, Pyrenees · `flat_roofs` SE Spain, Canaries · `fish_scale_tiles` Alsace · `stone_slabs` Massif Central · `mansard_dormers` Paris · `thatch` |
| 8 | `chimney` | `ornate_lattice_or_round_spire` **Algarve (strong)** · `large_whitewashed_block` Alentejo · `gable_end_chimneys` Brittany |
| 9 | `granary` | `long_stone_granary_on_pillars` Minho, Galicia (strong for NW Iberia) · `square_wooden_granary_four_pillars` Asturias, León (strong) |
| 10 | `flag` | national flags; `azores` · `madeira` · `galicia` · `senyera` (Catalonia or 66) · `estelada` (ES Catalan areas) · `ikurrina` (Basque, ES or FR) · `andalucia` · `extremadura` · `gwenn_ha_du` · `occitan_cross` · `provence_vertical` · `moor_head` |
| 11 | `logo_seen` | `ctt_horse_rider` PT · `multibanco_mb` PT · `correos_crown` ES · `once` ES · `la_poste_bird` FR · `tabac_double_cone` FR · `fdj` FR |

**B. Road scenes**

| # | Key | Options → implication |
|---|---|---|
| 12 | `bollard` | `thin_wedge_small_white_reflector` PT · `flat_post_wide_reflector` PT (rare FR) · `yellow_orange_rect_reflector` ES (also the left side of PT motorways) · `same_green_top` Extremadura · `square_orange_front` Lleida, Tarragona, Las Palmas · `round_pointed_top_band` FR (strong) · `diagonal_black_band` DE/LU/CH type, weak FR (east) · `stone_block_red_reflector` Madeira |
| 13 | `guardrail_reflectors` | `red` PT · `yellow` ES · `none` FR · `yellow_black_painted_rail` Madeira |
| 14 | `chevron` | `black_yellow` **PT (strong)** · `black_white` ES · `blue_white` ES or FR · `small_square_red_on_white` Murcia · `large_square_single_arrow` Catalonia |
| 15 | `km_marker` | `plate_diagonal_colour_left` PT (red IP, black IC, blue A) · `tombstone_black_base` PT N/ER · `yellow_base` PT EM · `coloured_header_rectangle` ES · `square_no_km_word` Extremadura, CLM, Aragón · `square_madrid_flag` Madrid · `extra_tall_junta_band` Andalucía · `rounded_top_large` Bizkaia · `white_yellow_round_top` FR D-road · `white_red_round_top` FR N-road · `plate_decimal_km` FR motorway |
| 16 | `direction_sign` | `white_arrow_plate_black_arrowhead` PT · `green_panel` PT IP (also FR main routes) · `coloured_number_boxes` ES (strong) · `offset_outline_italics` FR · `yellow_D_plate` **FR (strong)** · `cyan_M_plate` French métropole |
| 17 | `red_sign_rim` (hard) | `white_rim` PT or FR · `red_to_edge` ES |
| 18 | `pedestrian_sign` (hard) | `eight_stripes` ES (strong) · `five_belted_figure` PT · `five_detached_head` FR |
| 19 | `edge_lines` | `solid` PT and some ES regions · `dashed_short` CyL, Extremadura, CLM, Catalonia · `long_widely_spaced` FR · `offset_block_centre` FR (strong) · `yellow` roadworks or kerb rules (weak) |
| 20 | `utility_pole` | `ladder_tall_openings_holes` PT (medium-strong) · `ladder_short_steps` ES or FR · `small_blue_plate` FR (strong) · `octagonal_metal` FR · `steel_lattice_rect_mesh` Murcia, S Alicante |
| 21 | `hunting_sign` | `red_white_sign` PT (strong): a rectangle, a diamond or a red-white-red plate; OCR the process number · `white_coto_privado_de_caza` ES · `black_white_diagonal_square` ES · `area_privada_de_caca` Catalonia, Balearics |

**C. Landscape**

| # | Key | Options → implication |
|---|---|---|
| 22 | `vegetation` | `eucalyptus` PT or N Spain, **not FR** · `maritime_pine` N half of PT, Galicia · `stone_pine` · `cork_holm_oak_scattered` Alentejo, dehesa · `olive_rows` · `douro_schist_terraces` Douro (strong) · `pergola_vines` Minho · `citrus` Algarve, Valencia · `rice_paddies` Tejo, Sado, Mondego, Ebro delta · `plastic_greenhouses` Almería · `lavender` Provence · `flat_pine_monoculture` Landes · `hedged_bocage` Normandy, Brittany · `japanese_cedar` Azores · `banana` Madeira · `palms` |
| 23 | `terrain` | `flat_plain` · `rolling` · `mountains` · `granite_boulders_snow_poles` Serra da Estrela, Gerês · `white_sand_pines` Setúbal–Sines · `volcanic` Azores, Canaries · `sea_cliffs` |
| 24 | `soil` | `red` Teruel, CLM, Alentejo olive land · `white_grey` Aragón, Ebro · `black_volcanic` Lanzarote · `orange_volcanic` Fuerteventura |

## 8. Questions for the team

The checklist doubles as question vocabulary (PLAN 3.4, T19). Good questions ask about features a teammate can check in the panorama in seconds, and they offer at most 4 explicit options:

- **"Look at the right-hand end of the parked cars' number plates. What do you see?"**
  - A) a yellow strip with two small numbers
  - B) a blue strip with a number and a logo
  - C) plain white
  - D) no plate readable
- **"What colour are the post boxes?"** Red / blue / yellow / none visible.
- **"What colours are the curve chevron boards?"** Black with yellow arrows / black with white / blue with white / none visible.
- **"Which roadside post looks most like this one?"** The options describe the bollard types in §7.
- **"What is the main language on the signs?"** Offer the 3–4 candidates still alive.

Use zone questions with the units above: PT postcode first digits or NUTS regions, ES communities, FR regions. They must cover the whole scope or include "none of these" (PLAN 3.4). A skip changes nothing (RULES).

## 9. Rainbolt

Captions were read for 26 of his YouTube uploads, 13 collaborations and interviews (WIRED, zi8gzag, NPR, VICE) and 167 TikToks. 69 relevant transcripts are saved. After about 45 downloads, YouTube rate-limited caption requests from this machine (HTTP 429 from 17:41). So most of his long gameplay is unread: 176 flagged videos are listed with resume commands in `rainbolt.md` §5 and A3.

His tips agree with the guides. They add little that is new, but they confirm which clues an expert relies on.

**His fast rules:**
- **Portugal:**
  - white cobblestone sidewalks: "more than likely always" Portugal
  - a plate with a blue strip **and** a yellow strip
  - a small **red-white-red** ("Austrian flag") sign on rural fences, a hunting sign. Together with a ladder pole it is "you have to be in Portugal"
  - blue flowers (hydrangeas) mean the Azores
- **Spain:**
  - **yellow** reflectors on bollards; a **green top** means Extremadura
  - red sign borders that run to the edge
  - "Spanish bins": his tip has no description, so this is a gap
- **France:**
  - a **blue sticker** on utility poles: "the only country in the world"
  - the big round white-red-white bollard (with right-hand traffic)
  - plates with two blue strips; the right one gives the department
  - yellow rear plates on older cars
  - white dashed edge lines
- **Ladder poles:** Spain, Portugal or France. European ones are skinnier, with more holes.

**His order of checks:**
1. poles and bollards (learned first)
2. plates (EU strip)
3. architecture and vegetation
4. driving side, sun
5. soil colour, trees and the ocean: his "top three"

To pinpoint, he reads the road direction, then town names, street names and road numbers. Without language, "urban Europe" is hard even for him. **Our order:** text first, then plates, poles and bollards, signs, paving, vegetation and soil, architecture.

**His pinpointing method, worth copying for urban precision.** He picks one distinctive public object, downloads the public dataset of every such object, filters it, then checks each candidate. His examples:
- a V'Lille bike-share bike → the station list (Lille)
- a Paris bus-shelter design and one-word stop name → the scraped stop list
- `75010` printed on a parking meter → the arrondissement

Our equivalent (our idea, not his): read a bus-stop or station name, then look it up in the operators' open GTFS stop lists (e.g. Carris Metropolitana, STCP; check which other operators publish one) for a stop coordinate within a few metres. Worth prefetching if runtime downloads stay off (PLAN 3.3).

**Mix-ups he warns about:**
- France vs Belgium: the plate decides; a lot of brick points to Belgium
- France vs Denmark: white houses
- France vs UK: hedgerows
- Portugal vs Brazil: architecture
- southern Portugal vs Spain: a "true 50/50" (zi8gzag)
- keep islands in mind: Canaries, Azores, Madeira, Corsica

Other creators' Iberia and France guides surfaced in the search but were not transcribed: zi8gzag "France Explained" and "European Utility Poles", GeoClement "Regionguessing France", Salvado "Portugal guide", ThreeMangoes "Portuguese vs Spanish", GeoTelloth "European Bollards" (IDs in `rainbolt.md` §5).

## 10. Conflicts and gaps

- **PT vs ES bollards.** Geomastr's Portuguese examples look like Spanish ones. Plonk It and the Portuguese road-sign regulation say Portuguese bollards are thin wedges with a small white reflector, and that yellow/orange ones are only used on the left of one-way carriageways (motorways). An orange-reflector bollard on a motorway is weak evidence.
- **Yellow edge lines.** Geomastr and GeoHints list yellow edge lines for PT and ES. The regulations say yellow means kerb no-parking (PT) or roadworks (ES). Weak evidence.
- **Portuguese plates.** The yellow band ran from 1998 to 2020 according to Wikipedia; Rainbolt says from 2005. The `AA 00 AA` series has no band, so a plate without a right-hand band no longer means Spain. Sources disagree on the exact 2020 start date.
- **Spanish road prefixes disagree between sources:** Lleida L/LL, Zaragoza Z/ZP/CV/CHE, HU for both Huesca and Huelva, and "A" for Alicante. Ceuta: N roads only, or its own CE-A code.
- **French "-ac".** geotips puts it in the south-east; every other source says the south-west quarter and south Brittany. Use the latter.
- **French phone numbers.** Since nationwide landline portability (2023 or 2024; sources disagree), the zone digit is a strong prior, not proof.
- **Not covered by any source:**
  - Portuguese street lamps. The organisers' "Praying for Portugal" PDF singles out old-style Lisbon/Coimbra lamps as typically Portuguese.
  - traffic lights and house-number plates in PT
  - Portuguese supermarket distribution (Continente, Pingo Doce, Minipreço)
  - Spanish estanco ("Tabacos") sign colours
- **Data dates:**
  - CTT postcode data: 2020
  - Spanish km-marker doc: 2023
  - Portuguese NUTS regions revised in 2024; parishes split in 2025 (3,091 → 3,259)
  - Cepsa renamed Moeve in October 2024
- **Not reachable:**
  - Reddit (blocked)
  - Discord-hosted infographics (need a login)
  - YouTube captions after about 45 downloads (HTTP 429). Resume later or from another network (`rainbolt.md` A3).
