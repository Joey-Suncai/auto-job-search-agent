#!/usr/bin/env python3
"""Is a posting's location clearly outside the U.S.? (JSA-084, 2026-11-02) — shared by wd_search / board_search keep_posting.

The old per-script lists missed places (Auckland / New Zealand on a Lever board, 11-02). This one follows the gate's
locationVerdict (eligibility_rules.js): split a multi-location string into parts; a part is foreign when it names a
foreign country / city / region, U.S. when it names a state, a U.S. city or "United States"; the posting is non-U.S. only
when some part is foreign and no part is U.S. City names that also exist in the U.S. (Dublin, CA · Paris, TX · London, KY ·
Vancouver, WA · Melbourne, FL …) count as U.S. when the part also carries a U.S. state. Unambiguous foreign cities win over a
two-letter code that is also a state abbreviation ("Bangalore, IN", "Berlin, DE", "Toronto, CA").
Tests (rule 13): scripts/test_board_search.py, scripts/test_wd_search.py (DeepSeek cases).
"""
import re

_COUNTRIES = (
    'afghanistan|albania|algeria|andorra|angola|argentina|armenia|australia|austria|azerbaijan|bahamas|bahrain|bangladesh|'
    'barbados|belarus|belgium|belize|benin|bhutan|bolivia|bosnia|botswana|brazil|brunei|bulgaria|burkina faso|burundi|'
    'cambodia|cameroon|canada|cape verde|chile|china|colombia|congo|costa rica|croatia|cuba|cyprus|czech republic|czechia|'
    'czech|denmark|dominican republic|ecuador|egypt|el salvador|estonia|eswatini|ethiopia|fiji|finland|france|gabon|gambia|'
    'germany|ghana|greece|guatemala|guinea|guyana|haiti|honduras|hong kong|hungary|iceland|india|indonesia|iran|iraq|ireland|'
    'israel|italy|ivory coast|japan|kazakhstan|kenya|kosovo|kuwait|kyrgyzstan|laos|latvia|liberia|libya|'
    'liechtenstein|lithuania|luxembourg|macau|madagascar|malawi|malaysia|maldives|mali|malta|mauritius|moldova|monaco|'
    'mongolia|montenegro|morocco|mozambique|myanmar|namibia|nepal|netherlands|the netherlands|new zealand|nicaragua|niger|'
    'nigeria|north macedonia|norway|oman|pakistan|palestine|paraguay|philippines|poland|portugal|qatar|romania|russia|'
    'rwanda|saudi arabia|saudi|scotland|senegal|serbia|sierra leone|singapore|slovakia|slovenia|somalia|south africa|'
    'south korea|korea|spain|sri lanka|sudan|suriname|sweden|switzerland|syria|taiwan|tajikistan|tanzania|thailand|togo|'
    'trinidad|tunisia|turkey|t[üu]rkiye|turkmenistan|uganda|ukraine|united arab emirates|uae|united kingdom|uk|u\\.k\\.|'
    'great britain|england(?<!new england)|wales|northern ireland|uruguay|uzbekistan|venezuela|vietnam|viet nam|yemen|zambia|zimbabwe|'
    'mexico(?<!new mexico)|m[ée]xico')
_CITIES = (  # foreign cities with no well-known U.S. namesake
    'toronto|quebec|qu[ée]bec|montreal|montr[ée]al|ottawa|calgary|edmonton|winnipeg|mississauga|burnaby|'
    'british columbia|alberta|nova scotia|'
    'edinburgh|glasgow|leeds|liverpool|belfast|cork|galway|'
    'amsterdam|rotterdam|eindhoven|the hague|utrecht|brussels|antwerp|luxembourg city|'
    'berlin|munich|m[üu]nchen|frankfurt|cologne|k[öo]ln|stuttgart|d[üu]sseldorf|leipzig|dresden|'
    'zurich|z[üu]rich|gen[èe]ve|basel|lausanne|wien|prague|praha|budapest|bratislava|'
    'warszawa|krak[óo]w|krakow|wroc[łl]aw|gda[ńn]sk|pozna[ńn]|bucharest|cluj|sofia|belgrade|zagreb|ljubljana|'
    'kyiv|kiev|lviv|kharkiv|minsk|tallinn|riga|vilnius|helsinki|stockholm|gothenburg|g[öo]teborg|malm[öo]|oslo|copenhagen|'
    'k[øo]benhavn|reykjavik|lisbon|lisboa|porto|madrid|barcelona|seville|sevilla|bilbao|milano|turin|torino|bologna|'
    'marseille|lyon|toulouse|bordeaux|lille|nantes|grenoble|monte carlo|'
    'tel aviv|jerusalem|haifa|herzliya|istanbul|ankara|izmir|dubai|abu dhabi|sharjah|doha|riyadh|jeddah|al khobar|khobar|dammam|dhahran|'
    'neom|muscat|manama|kuwait city|amman|beirut|baghdad|erbil|tehran|casablanca|'
    'lagos|abuja|nairobi|accra|kigali|addis ababa|johannesburg|cape town|durban|'
    'bangalore|bengaluru|hyderabad|pune|chennai|mumbai|new delhi|gurgaon|gurugram|noida|kolkata|ahmedabad|kochi|'
    'karachi|lahore|islamabad|dhaka|colombo|kathmandu|'
    'beijing|shanghai|shenzhen|guangzhou|hangzhou|chengdu|wuhan|nanjing|suzhou|xian|xi\'an|tianjin|'
    'taipei|hsinchu|tokyo|osaka|kyoto|yokohama|fukuoka|seoul|busan|pangyo|'
    'kuala lumpur|penang|jakarta|bandung|manila|makati|cebu|bangkok|ho chi minh|hanoi|da nang|phnom penh|'
    'sydney|adelaide|canberra|auckland|christchurch|'
    'cambridge, uk|cambridge, england|s[ãa]o paulo|rio de janeiro|belo horizonte|curitiba|porto alegre|buenos aires|c[óo]rdoba|bogot[áa]|medell[íi]n|'
    'santiago de chile|ciudad de m[ée]xico|mexico city|guadalajara|monterrey|tijuana|quer[ée]taro|san jos[ée], costa rica|'
    'montevideo|quito|caracas|'
    'saint petersburg|st\\. petersburg, russia|almaty|baku|tbilisi|yerevan')
_REGIONS = 'europe|emea|apac|asia[- ]pacific|asia|latam|latin america|middle east|africa|oceania|nordics|scandinavia|baltics|balkans|dach|benelux|mena|anz|eastern europe|south america|central america'
# names shared with U.S. places: foreign unless the same part carries a U.S. state / "United States"
_AMBIG = ('london|paris|dublin|vancouver|melbourne|perth|oxford|brisbane|bristol|halifax|hamburg|ontario|geneva|vienna|warsaw|bern|milan|moscow|jamaica|birmingham|manchester|athens|rome|'
          'florence|naples|valencia|toledo|lima|victoria|waterloo|kingston|richmond|windsor|hamilton|wellington|'
          'cairo|panama|peru|lebanon|jordan|delhi|santiago|bergen')

FOREIGN = re.compile(r'\b(' + _COUNTRIES + '|' + _CITIES + '|' + _REGIONS + r')\b', re.I)
FOREIGN_CODE = re.compile(r'\b(GBR|CAN|DEU|FRA|NLD|ESP|POL|SGP|JPN|CHN|IND|BRA|MEX|ARG|COL|MYS|AUS|NZL|IRL|ISR|KOR|TWN|'
                          r'PHL|VNM|THA|IDN|PRT|ITA|CHE|SWE|DNK|NOR|FIN|AUT|BEL|CZE|HUN|ROU|UKR|TUR|ARE|SAU|EGY|NGA|KEN|ZAF)\b')
AMBIG = re.compile(r'\b(' + _AMBIG + r')\b', re.I)
CA_PROVINCE = re.compile(r',\s?(ON|QC|BC|AB|MB|SK|NS|NB|NL|PE|PEI)\b')   # "Burlington, ON" — U.S. namesake, Canadian province
_STATES = ('alabama|alaska|arizona|arkansas|california|colorado|connecticut|delaware|florida|hawaii|idaho|illinois|'
           'indiana|iowa|kansas|kentucky|louisiana|maine|maryland|massachusetts|michigan|minnesota|mississippi|missouri|'
           'montana|nebraska|nevada|new hampshire|new jersey|new mexico|new york|north carolina|north dakota|ohio|oklahoma|'
           'oregon|pennsylvania|rhode island|south carolina|south dakota|tennessee|texas|utah|vermont|virginia|washington|'
           'west virginia|wisconsin|wyoming|district of columbia|puerto rico')
US_WORD = re.compile(r'\b(united states|u\.s\.a?\.?|usa|north america|remote[^,;]{0,15}\b(?:us|united states|usa)\b|' + _STATES + r')(?![\w])',
                     re.I)
US_CODE = re.compile(r'(?:,|\s-)\s?(AL|AK|AZ|AR|CA|CO|CT|DE|FL|GA|HI|ID|IL|IN|IA|KS|KY|LA|ME|MD|MA|MI|MN|MS|MO|MT|NE|NV|NH|'
                     r'NJ|NM|NY|NC|ND|OH|OK|OR|PA|RI|SC|SD|TN|TX|UT|VT|VA|WA|WV|WI|WY|DC)\b|\bUS\b')
US_CITY = re.compile(r'\b(nyc|sf|bay area|silicon valley|seattle|boston|chicago|austin|denver|atlanta|los angeles|san francisco|'
                     r'san jose|san diego|dallas|houston|miami|philadelphia|pittsburgh|phoenix|detroit|minneapolis|'
                     r'salt lake city|raleigh|nashville|st\.? louis|kansas city|baltimore|palo alto|mountain view|sunnyvale|'
                     r'menlo park|redmond|bellevue|irvine|santa monica|brooklyn|jersey city|hoboken|ann arbor|boulder|'
                     r'charlotte|tampa|orlando)\b', re.I)
# "New Berlin, WI", "New Madrid, MO", "New Lisbon, WI": a U.S. town named after a foreign city
NEW_TOWN = re.compile(r'\bnew (?!delhi|zealand|south wales|taipei|caledonia|guinea)[a-z]+', re.I)
SPLIT = re.compile(r';|\||\n|•|/(?! )|\s{2,}|\s+or\s+|\s+and\s+', re.I)


def _part(p):
    """'us' | 'foreign' | '' for one location part."""
    word, code, city = US_WORD.search(p), US_CODE.search(p), US_CITY.search(p)
    q = NEW_TOWN.sub(' ', p)
    strong = FOREIGN.search(q) or FOREIGN_CODE.search(q)
    if strong and not word:
        return 'foreign'          # "Toronto, CA", "Bangalore, IN", "Auckland, New Zealand" — a state code does not rescue it
    if word or code or city:
        return 'us'               # "Dublin, CA", "Paris, Texas", "New York, NY"
    if AMBIG.search(q) or CA_PROVINCE.search(p):
        return 'foreign'          # bare "London", "Dublin", "Melbourne"
    return ''


def is_non_us(location):
    """Pure (tested). True when the location is clearly outside the U.S.: some part foreign and none U.S.
    "Remote" / empty / unknown places → False."""
    loc = str(location or '').strip()
    if not loc:
        return False
    if re.search(r'\b(united states|usa|u\.s\.|remote us)\b', loc, re.I):
        return False
    kinds = [_part(p.strip()) for p in SPLIT.split(loc) if p and p.strip()]
    return 'foreign' in kinds and 'us' not in kinds
