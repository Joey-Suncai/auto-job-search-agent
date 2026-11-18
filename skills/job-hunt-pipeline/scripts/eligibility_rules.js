// Eligibility gate — pure rules, no I/O. Runs in Chrome (eligibility_fetch.js) and in Node (tests).
// The candidate's facts come from setCandidate({needs_sponsorship, citizen_or_pr, grad, degree_level}) (JSA-081 / JSA-087:
// eligibility_classify.js reads config/profile.json → "eligibility"). Default = the author's: F-1 (needs sponsorship; CPT for
// a Summer 2027 internship), not a citizen / permanent resident, M.S. student graduating Dec 2027; U.S. roles only.
// degree_level = the degree the candidate is enrolled in: "bachelors" | "masters" (default) | "phd".
// verdict: "Eligible" | "Review" | "Ineligible" | "Closed". reasons: [{code, level:"block"|"review"|"plus", ev:"snippet"}]
(function (root) {
  const CAND = { needs_sponsorship: true, citizen_or_pr: false, grad: 2027 + 11 / 12, degree_level: "masters", intern_summer: 2027 };   // grad: decimal year (Dec 2027)
  const DEGREE = { bachelors: "bachelors", bachelor: "bachelors", undergraduate: "bachelors", masters: "masters", master: "masters",
    phd: "phd", doctoral: "phd" };
  function setCandidate(c) {                 // {needs_sponsorship, citizen_or_pr, grad: decimal year or "YYYY-MM", degree_level}
    for (const k of ["needs_sponsorship", "citizen_or_pr"]) if (c && typeof c[k] === "boolean") CAND[k] = c[k];
    if (c && typeof c.degree_level === "string" && DEGREE[c.degree_level.toLowerCase().replace(/['’]/g, "")]) CAND.degree_level = DEGREE[c.degree_level.toLowerCase().replace(/['’]/g, "")];
    if (c && Number.isInteger(c.intern_summer) && c.intern_summer > 2000) CAND.intern_summer = c.intern_summer;
    if (c && typeof c.grad === "number") CAND.grad = c.grad;
    else if (c && /^\d{4}-\d{2}$/.test(c.grad || "")) CAND.grad = +c.grad.slice(0, 4) + (+c.grad.slice(5) - 1) / 12;
    return Object.assign({}, CAND);
  }
  const MONTHS = { jan: 1, feb: 2, mar: 3, apr: 4, may: 5, jun: 6, jul: 7, aug: 8, sep: 9, oct: 10, nov: 11, dec: 12,
    spring: 5, summer: 8, fall: 12, autumn: 12, winter: 12 };
  const clean = s => (s || "").replace(/<[^>]+>/g, " ").replace(/&nbsp;|&#160;/g, " ").replace(/&amp;/g, "&")
    .replace(/&lt;/g, "<").replace(/&gt;/g, ">").replace(/&#39;|&rsquo;|&lsquo;/g, "'").replace(/&quot;|&ldquo;|&rdquo;/g, '"')
    .replace(/[‘’]/g, "'").replace(/[–—]/g, "-").replace(/\s+/g, " ").trim();
  const snip = (t, i, n = 140) => t.slice(Math.max(0, i - 40), i + n).trim();
  function find(t, re) { const m = re.exec(t); return m ? snip(t, m.index) : null; }

  // ---------- sponsorship / citizenship
  const NO_SPONSOR = [
    /\b(unable|not able|cannot|can ?not|can't|won't|will not|do(?:es)? not|are not|is not|we don't|we do not)\b[^.;]{0,50}\b(sponsor\w*)\b/i,
    /\bwithout (?:the )?(?:need (?:for|of) |requiring |needing |requirement (?:for|of) )?(?:current or future |now or in the future |future |any |the )?(?:employer[- ]|company[- ]|visa |immigration |employment |work )*(?:visa )?sponsorship/i,
    /\bno (?:visa |employment |immigration |work )?sponsorship\b/i,
    // "Must be legally authorized to work in the U.S. and not require sponsorship now or in the future" (Stryker 2026-10-30)
    /\b(?:not|never)\s+(?:to\s+)?(?:currently\s+)?(?:require|need)s?\b[^.;]{0,40}\bsponsor(?:ship)?\b/i,
    /\bsponsorship (?:is |will )?(?:not|un)\s?(?:available|be (?:provided|offered|considered))/i,
    /\bsponsorship\b[^.;]{0,80}\b(?:is|will be) not available\b/i,
    /\bnot eligible for (?:visa |employment |immigration |employer |work )*sponsorship/i,
    // a labelled field: "Sponsorship: Not Available" (Nissan 2026-11-01), "Visa Sponsorship: No", "Sponsorship - None"
    /\b(?:visa |immigration |employment |work )?sponsorship(?: available| offered| provided)?\s*[:\-–]\s*(?:not available|unavailable|no|none|not offered|not provided)\b/i,
    /\b(?:F-?1|OPT(?![- ]?(?:out|in)\b)|CPT|STEM OPT|student visa)\b[^.;]{0,70}\b(?:not eligible|ineligible|not be considered|not considered|unable|cannot|not accept|does not qualify|do not qualify)/i,
    /\b(?:not eligible|ineligible|unable|cannot|can't|will not|won't|do(?:es)? not)\b[^.;]{0,70}\b(?:F-?1|OPT(?![- ]?(?:out|in)\b)|CPT|STEM OPT)\b/i,  // \"opt out\" of AI screening is not OPT (Rippling 2026-11-01)
    /\bauthori[sz]ed to work (?:permanently |indefinitely )?(?:in the (?:U\.?S\.?|United States) )?for any employer\b/i,
    // "authorized to work in the United States on a full-time basis for anyone other than current employer and/or education institution" (ConocoPhillips 2026-11-01)
    /\bauthori[sz]ed to work\b[^.;]{0,80}\bfor anyone other than\b/i,
    /\b(?:permanent|unrestricted) (?:U\.?S\.? )?work authori[sz]ation\b/i,
  ];
  // the patterns above that rule out an F-1 student's internship itself, not only a later sponsorship (JSA-238)
  const NO_SPONSOR_RESTRICTIVE = NO_SPONSOR.filter(re => /F-\?1|any employer|anyone other than|permanent\|unrestricted/.test(re.source)).concat([
    // "unable to sponsor … any type of employment visa, including F-1 (OPT/CPT), H-1B" (Viget): the student visa named in the no
    /\b(?:unable|cannot|can ?not|can't|will not|won't|do(?:es)? not|not)\b[^.;]{0,140}\b(?:F-?1|CPT|STEM OPT|OPT(?![- ]?(?:out|in)\b)|student visas?)\b/i]);
  // the candidate's side of the sentence ("must not require sponsorship", "authorized to work without sponsorship") — the
  // employer's side is "does not sponsor" (JSA-385)
  const MUST_NOT_NEED = /\b(?:not|never)\s+(?:to\s+)?(?:currently\s+)?(?:require|need)s?\b[^.;]{0,40}\bsponsor|\bwithout (?:the )?(?:need (?:for|of) |requiring |needing )?(?:current or future |now or in the future |future |any |the )?(?:employer[- ]|company[- ]|visa |immigration |employment |work )*(?:visa )?sponsorship|\b(?:do(?:es)? not|don't) (?:currently )?(?:require|need) (?:visa |immigration |employment |work )*sponsorship/i;
  const OFFERS_SPONSOR = /\b(will|can|may|able to|happy to|open to|does|do)\s+(?:provide |offer |consider )?(?:visa |H-?1B |immigration )?sponsor(?:ship)?\b(?![^.;]{0,30}\b(?:not|unable)\b)|(?<!\bno (?:visa |H-?1B |immigration |employment |work )?)\bsponsorship (?:is )?(?:available|provided|offered)\b|\bvisa sponsorship: ?yes\b/i;
  const CITIZEN = [
    /\b(?:must|required to|need to) be (?:a )?(?:U\.?S\.?|United States) citizens?\b/i,
    /\b(?:U\.?S\.?|United States) citizenship (?:is |will be )?(?:required|mandatory|needed)\b/i,
    /\brequires? (?:U\.?S\.?|United States) citizenship\b/i,
    /\bmust be a (?:U\.?S\.?|United States) person\b/i,
    /\b(?:U\.?S\.?|United States) persons?\b[^.;]{0,120}\b(?:required|must|only|eligible|ITAR|EAR|export)/i,
    /\bITAR\b/,
    /\bexport[- ]control\w*[^.;]{0,160}\b(?:U\.?S\.? person|citizen|permanent resident|green card|lawful permanent)/i,
    /\b(?:security|secret|top secret|TS\/SCI|DoD|government|federal|public trust) clearance\b/i,
    /\b(?:citizens? or (?:lawful )?permanent residents?|green card holders?)\b[^.;]{0,40}\b(?:only|required|must|eligible)/i,
    /\bwho may apply:?\s*(?:only\s+)?(?:U\.?S\.?|United States) citizens?\b/i,   // USAJOBS "Who may apply: U.S. Citizens, Nationals …" (2026-11-03)
    /\bowe allegiance to the (?:U\.?S\.?|United States)\b/i,
    /(?<!\bnot )\bonly (?:U\.?S\.?|United States) citizens\b(?! but also)|\b(?:U\.?S\.?|United States) citizens only\b/i,   // "only U.S. citizens will be considered" (Kitware 2026-11-04, JSA-142)
  ];

  // ---------- location
  const US_MARK = /\b(United States|U\.S\.A?\.?|USA|US\b|U\.S\.|Remote[^,;]{0,15}\b(US|U\.S\.|United States|USA)|Alabama|Alaska|Arizona|Arkansas|California|Colorado|Connecticut|Delaware|Florida|Georgia, USA|Hawaii|Idaho|Illinois|Indiana|Iowa|Kansas|Kentucky|Louisiana|Maine|Maryland|Massachusetts|Michigan|Minnesota|Mississippi|Missouri|Montana|Nebraska|Nevada|New Hampshire|New Jersey|New Mexico|New York|North Carolina|North Dakota|Ohio|Oklahoma|Oregon|Pennsylvania|Rhode Island|South Carolina|South Dakota|Tennessee|Texas|Utah|Vermont|Virginia|Washington|West Virginia|Wisconsin|Wyoming|District of Columbia|SF|NYC|Bay Area|Silicon Valley|Seattle|Boston|Chicago|Austin|Denver|Atlanta|Los Angeles|San Francisco|San Jose|San Diego|Dallas|Houston|Miami|Philadelphia|Pittsburgh|Phoenix|Detroit|Minneapolis|Portland|Salt Lake|Raleigh|Nashville|Columbus|Cincinnati|Cleveland|St\.? Louis|Kansas City|Baltimore|Arlington|Palo Alto|Mountain View|Sunnyvale|Menlo Park|Redmond|Bellevue|Irvine|Santa Monica|Cambridge, MA|Brooklyn|Jersey City|Hoboken|Princeton|Ann Arbor|Madison|Boulder|Durham|Charlotte|Tampa|Orlando)\b|,\s?(AL|AK|AZ|AR|CA|CO|CT|DE|FL|GA|HI|ID|IL|IN|IA|KS|KY|LA|ME|MD|MA|MI|MN|MS|MO|MT|NE|NV|NH|NJ|NM|NY|NC|ND|OH|OK|OR|PA|RI|SC|SD|TN|TX|UT|VT|VA|WA|WV|WI|WY|DC)\b/;
  const FOREIGN = /\b(Canada|Toronto|Vancouver|Montr[eé]al|Ottawa|Ontario|Quebec|Calgary|Waterloo|United Kingdom|UK\b|U\.K\.|England|London(?!, (?:Ontario|KY|OH))|Manchester|Edinburgh|Scotland|Ireland|Dublin|India|Bangalore|Bengaluru|Hyderabad|Pune|Mumbai|Delhi|Gurgaon|Gurugram|Noida|Chennai|Germany|Berlin|Munich|M[üu]nchen|Hamburg|Frankfurt|France|Paris(?!, (?:TX|TN|KY))|Netherlands|Amsterdam|Spain|Madrid|Barcelona|Italy|Milan|Rome|Poland|Warsaw|Krak[oó]w|Wroc[lł]aw|Portugal|Lisbon|Porto|Israel|Tel Aviv|Haifa|Singapore|Japan|Tokyo|China|Beijing|Shanghai|Shenzhen|Hangzhou|Hong Kong|Taiwan|Taipei|Korea|Seoul|Australia|Sydney|Melbourne|Brazil|S[ãa]o Paulo|Mexico|Ciudad de M[eé]xico|Guadalajara|Argentina|Buenos Aires|Colombia|Bogot[aá]|Medell[ií]n|Peru|Chile|Santiago|Philippines|Manila|Vietnam|Malaysia|Kuala Lumpur|Indonesia|Jakarta|Thailand|Bangkok|Dubai|UAE|United Arab Emirates|Saudi|Riyadh|Egypt|Cairo|Nigeria|Lagos|Kenya|Nairobi|South Africa|Cape Town|Switzerland|Z[üu]rich|Geneva|Sweden|Stockholm|Denmark|Copenhagen|Norway|Oslo|Finland|Helsinki|Czech|Prague|Romania|Bucharest|Hungary|Budapest|Serbia|Belgrade|Ukraine|Kyiv|Turkey|Istanbul|Greece|Athens|Austria|Vienna|Belgium|Brussels|Costa Rica|Guatemala|Uruguay|Montevideo|New Zealand|Auckland|Pakistan|Bangladesh|Sri Lanka|Azerbaijan|Baku|Russia|Moscow|Vladivostok|Kazakhstan|Estonia|Tallinn|Latvia|Lithuania|Vilnius|Luxembourg|Cyprus|Malta|EMEA|APAC|LATAM|MYS|IND|GBR|CAN|DEU|FRA|NLD|ESP|POL|SGP|JPN|CHN|BRA|MEX|ARG|COL)\b/;
  // JSA-084 (2026-11-03): the same place lists as us_location.py (Workday / Lever / Ashby searches) — keep the two in step;
  // scripts/test_gate_location.js runs the shared DeepSeek cases on both. A part naming an unambiguous foreign country / city /
  // region is foreign even with a state-like code ("Bangalore, IN", "Toronto, CA"); only an explicit U.S. word rescues it.
  const FOREIGN_X = /(?<![A-Za-z0-9_\u00C0-\u024F])(afghanistan|albania|algeria|andorra|angola|argentina|armenia|australia|austria|azerbaijan|bahamas|bahrain|bangladesh|barbados|belarus|belgium|belize|benin|bhutan|bolivia|bosnia|botswana|brazil|brunei|bulgaria|burkina faso|burundi|cambodia|cameroon|canada|cape verde|chile|china|colombia|congo|costa rica|croatia|cuba|cyprus|czech republic|czechia|czech|denmark|dominican republic|ecuador|egypt|el salvador|estonia|eswatini|ethiopia|fiji|finland|france|gabon|gambia|germany|ghana|greece|guatemala|guinea|guyana|haiti|honduras|hong kong|hungary|iceland|india|indonesia|iran|iraq|ireland|israel|italy|ivory coast|japan|kazakhstan|kenya|kosovo|kuwait|kyrgyzstan|laos|latvia|liberia|libya|liechtenstein|lithuania|luxembourg|macau|madagascar|malawi|malaysia|maldives|mali|malta|mauritius|moldova|monaco|mongolia|montenegro|morocco|mozambique|myanmar|namibia|nepal|netherlands|the netherlands|new zealand|nicaragua|niger|nigeria|north macedonia|norway|oman|pakistan|palestine|paraguay|philippines|poland|portugal|qatar|romania|russia|rwanda|saudi arabia|saudi|scotland|senegal|serbia|sierra leone|singapore|slovakia|slovenia|somalia|south africa|south korea|korea|spain|sri lanka|sudan|suriname|sweden|switzerland|syria|taiwan|tajikistan|tanzania|thailand|togo|trinidad|tunisia|turkey|t[üu]rkiye|turkmenistan|uganda|ukraine|united arab emirates|uae|united kingdom|uk|u\.k\.|great britain|england(?<!new england)|wales|northern ireland|uruguay|uzbekistan|venezuela|vietnam|viet nam|yemen|zambia|zimbabwe|mexico(?<!new mexico)|m[ée]xico|toronto|quebec|qu[ée]bec|montreal|montr[ée]al|ottawa|calgary|edmonton|winnipeg|mississauga|burnaby|british columbia|alberta|nova scotia|edinburgh|glasgow|leeds|liverpool|belfast|cork|galway|amsterdam|rotterdam|eindhoven|the hague|utrecht|brussels|antwerp|luxembourg city|berlin|munich|m[üu]nchen|frankfurt|cologne|k[öo]ln|stuttgart|d[üu]sseldorf|leipzig|dresden|zurich|z[üu]rich|gen[èe]ve|basel|lausanne|wien|prague|praha|budapest|bratislava|warszawa|krak[óo]w|krakow|wroc[łl]aw|gda[ńn]sk|pozna[ńn]|bucharest|cluj|sofia|belgrade|zagreb|ljubljana|kyiv|kiev|lviv|kharkiv|minsk|tallinn|riga|vilnius|helsinki|stockholm|gothenburg|g[öo]teborg|malm[öo]|oslo|copenhagen|k[øo]benhavn|reykjavik|lisbon|lisboa|porto|madrid|barcelona|seville|sevilla|bilbao|milano|turin|torino|bologna|marseille|lyon|toulouse|bordeaux|lille|nantes|grenoble|monte carlo|tel aviv|jerusalem|haifa|herzliya|istanbul|ankara|izmir|dubai|abu dhabi|sharjah|doha|riyadh|jeddah|al khobar|khobar|dammam|dhahran|neom|muscat|manama|kuwait city|amman|beirut|baghdad|erbil|tehran|casablanca|lagos|abuja|nairobi|accra|kigali|addis ababa|johannesburg|cape town|durban|bangalore|bengaluru|hyderabad|pune|chennai|mumbai|new delhi|gurgaon|gurugram|noida|kolkata|ahmedabad|kochi|karachi|lahore|islamabad|dhaka|colombo|kathmandu|beijing|shanghai|shenzhen|guangzhou|hangzhou|chengdu|wuhan|nanjing|suzhou|xian|xi'an|tianjin|taipei|hsinchu|tokyo|osaka|kyoto|yokohama|fukuoka|seoul|busan|pangyo|kuala lumpur|penang|jakarta|bandung|manila|makati|cebu|bangkok|ho chi minh|hanoi|da nang|phnom penh|sydney|adelaide|canberra|auckland|christchurch|cambridge, uk|cambridge, england|s[ãa]o paulo|rio de janeiro|belo horizonte|curitiba|porto alegre|buenos aires|c[óo]rdoba|bogot[áa]|medell[íi]n|santiago de chile|ciudad de m[ée]xico|mexico city|guadalajara|monterrey|tijuana|quer[ée]taro|san jos[ée], costa rica|montevideo|quito|caracas|saint petersburg|st\. petersburg, russia|almaty|baku|tbilisi|yerevan|europe|emea|apac|asia[- ]pacific|asia|latam|latin america|middle east|africa|oceania|nordics|scandinavia|baltics|balkans|dach|benelux|mena|anz|eastern europe|south america|central america)(?![A-Za-z0-9_\u00C0-\u024F])/i;   // accent-safe word edges (Bogotá)
  const FOREIGN_CODE = /\b(GBR|CAN|DEU|FRA|NLD|ESP|POL|SGP|JPN|CHN|IND|BRA|MEX|ARG|COL|MYS|AUS|NZL|IRL|ISR|KOR|TWN|PHL|VNM|THA|IDN|PRT|ITA|CHE|SWE|DNK|NOR|FIN|AUT|BEL|CZE|HUN|ROU|UKR|TUR|ARE|SAU|EGY|NGA|KEN|ZAF)\b/;
  const AMBIG = /\b(london|paris|dublin|vancouver|melbourne|perth|oxford|brisbane|bristol|halifax|hamburg|ontario|geneva|vienna|warsaw|bern|milan|moscow|jamaica|birmingham|manchester|athens|rome|florence|naples|valencia|toledo|lima|victoria|waterloo|kingston|richmond|windsor|hamilton|wellington|cairo|panama|peru|lebanon|jordan|delhi|santiago|bergen)\b/i;
  const CA_PROVINCE = /,\s?(ON|QC|BC|AB|MB|SK|NS|NB|NL|PE|PEI)\b/;
  const NEW_TOWN = /\bnew (?!delhi|zealand|south wales|taipei|caledonia|guinea)[a-z]+/gi;   // "New Berlin, WI": a U.S. town named after a foreign city
  const US_WORD = /\b(united states|u\.s\.a?\.?|usa|north america|remote[^,;]{0,15}\b(?:us|united states|usa)\b|alabama|alaska|arizona|arkansas|california|colorado|connecticut|delaware|florida|hawaii|idaho|illinois|indiana|iowa|kansas|kentucky|louisiana|maine|maryland|massachusetts|michigan|minnesota|mississippi|missouri|montana|nebraska|nevada|new hampshire|new jersey|new mexico|new york|north carolina|north dakota|ohio|oklahoma|oregon|pennsylvania|rhode island|south carolina|south dakota|tennessee|texas|utah|vermont|virginia|washington|west virginia|wisconsin|wyoming|district of columbia|puerto rico)(?![\w])/i;
  function partKind(p) {
    const q = p.replace(NEW_TOWN, " ");
    if ((FOREIGN_X.test(q) || FOREIGN_CODE.test(q)) && !US_WORD.test(p)) return "foreign";
    if (US_MARK.test(p) || /^remote$/i.test(p) || /^remote\b(?![^,]{0,25}\b(?:canada|uk|europe|india|emea|latam|apac|mexico|brazil))/i.test(p) && !FOREIGN.test(p)) return "us";
    if (FOREIGN.test(q) || AMBIG.test(q) || CA_PROVINCE.test(p)) return "foreign";
    return "";
  }
  function locationVerdict(loc) {
    loc = (loc || "").trim();
    if (!loc) return null;
    const parts = loc.split(/;|\||\/(?! )|\s{2,}| or |\n|•/i).map(s => s.trim()).filter(Boolean);
    const kinds = parts.map(partKind);
    if (kinds.includes("foreign") && !kinds.includes("us")) return { code: "NON_US", level: "block", ev: loc.slice(0, 120) };
    return null;
  }

  // ---------- dates
  // "January - March 2027", "Sep 2026 – Dec 2026", "Jan 5, 2027 to Apr 30, 2027": internship dates that skip the summer
  const MON = { jan: 1, feb: 2, mar: 3, apr: 4, may: 5, jun: 6, jul: 7, aug: 8, sep: 9, oct: 10, nov: 11, dec: 12 };
  function termRange(t) {
    const re = /\b(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?\s*(?:\d{1,2}(?:st|nd|rd|th)?,?\s*)?(?:(?:20)?(2[6-8])\s*)?(?:-|–|—|to|through|until)\s*(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?\s*(?:\d{1,2}(?:st|nd|rd|th)?,?\s*)?(?:20)?(2[6-8])\b/gi;
    let m;
    while ((m = re.exec(t))) {
      if (/graduat|class of|degree|commencement|apply|deadline|posted|application/i.test(t.slice(Math.max(0, m.index - 70), m.index))) continue;
      const a = MON[m[1].toLowerCase()], b = MON[m[3].toLowerCase()];
      const ya = m[2] ? +m[2] : (a <= b ? +m[4] : +m[4] - 1), yb = +m[4];
      const months = []; for (let y = ya, mo = a; (y < yb || (y === yb && mo <= b)) && months.length < 24; mo === 12 ? (mo = 1, y++) : mo++) months.push(mo);
      if (!months.length || months.length > 9) continue;
      if (!months.some(x => x >= 6 && x <= 8)) return snip(t, m.index);
    }
    return null;
  }
  function tokens(s) { // month/season + year -> decimal year; bare year -> [year, year+11/12]
    const out = []; const re = /\b(?:(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec|spring|summer|fall|autumn|winter)\w*\.?,?\s*(?:of\s+)?)?(?:'|20)(2[5-9]|3[0-2])\b/gi;
    let m; while ((m = re.exec(s))) { const y = 2000 + +m[2]; const mo = m[1] ? MONTHS[m[1].toLowerCase().slice(0, 3)] || MONTHS[m[1].toLowerCase()] : null;
      out.push(mo ? { lo: y + (mo - 1) / 12, hi: y + (mo - 1) / 12, i: m.index } : { lo: y, hi: y + 11 / 12, i: m.index, bare: true }); }
    // "May/June 2027": a month right before a slash-month-year
    const re2 = /\b(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\w*\s*\/\s*(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\w*\.?,?\s*(?:20)(2[5-9]|3[0-2])\b/gi;
    while ((m = re2.exec(s))) { const y = 2000 + +m[2]; const mo = MONTHS[m[1].toLowerCase().slice(0, 3)]; out.push({ lo: y + (mo - 1) / 12, hi: y + (mo - 1) / 12, i: m.index }); }
    return out.sort((a, b) => a.i - b.i);
  }
  function gradVerdict(t) {
    // "expected May 2028 graduation date": the date sits between "expected" and "graduation" (an employer, JSA-087)
    const re = /\b(graduat\w*|class of|grad(?:uation)? date|degree completion|completion of (?:your|their) degree|expected (?:to )?(?:graduat|complet)\w*|(?:expected|anticipated) (?=(?:(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec|spring|summer|fall|autumn|winter)\w*\.?,? )?(?:of )?20\d\d (?:graduat|grad\b|degree)))/gi;
    let m, best = null, blocked = null;
    while ((m = re.exec(t))) {
      // the window ends with its sentence: "... June 2028. The internship runs Summer 2027" is two statements (JSA-231)
      let w = t.slice(m.index, m.index + 170); const se = /[.!?]\s+(?=[A-Z])/g; se.lastIndex = 15; const sm = se.exec(w); if (sm) w = w.slice(0, sm.index);
      const tk = tokens(w);
      if (!tk.length) continue;
      if (/\b(we|our|company)\b[^.]{0,20}graduat/i.test(w.slice(0, 40))) continue;
      // "a graduate degree / program / student" is a degree level, not a graduation date (JSA-087)
      if (/^graduates?\s+(?:degree|program|programme|student|school|studies|level|or undergraduate|\/)/i.test(w) || /^graduates?\)/i.test(w)) continue;
      let lo, hi;
      if (/\b(or later|or beyond|and beyond|or after|and after|onward|thereafter|or more recently)\b/i.test(w) && tk.length === 1) { lo = tk[0].lo; hi = 9999; }
      else if (/\b(or earlier|or before|no later than|by)\b/i.test(w) && tk.length === 1) { lo = 0; hi = tk[0].hi; }
      else if (/\b(within the (?:last|past)|in the last|since)\b/i.test(w)) { continue; }
      else { lo = Math.min(...tk.map(x => x.lo)); hi = Math.max(...tk.map(x => x.hi)); }
      const ok = CAND.grad >= lo - 0.01 && CAND.grad <= hi + 0.01;
      // "students graduating in 2029 may also be considered" widens the window, it does not replace it (JSA-231)
      if (!ok && /^[^.;]{0,90}\b(?:may|will|can) also be considered|^[^.;]{0,90}\bare also (?:welcome|eligible|encouraged)/i.test(w)) continue;
      const r = { code: ok ? "GRAD_OK" : "GRAD_WINDOW", level: ok ? "plus" : "block", ev: snip(t, m.index, 170) };
      if (!ok) { blocked = blocked || r; continue; } best = best || r;
    }
    // one window fits and another does not: the JD contradicts itself → a person looks (JSA-231)
    if (blocked && best) return { code: "GRAD_MIXED", level: "review", ev: blocked.ev };
    return blocked || best;
  }

  // ---------- main
  // minimum years of experience asked for; ranges use the low end ("0 to 3 years" -> 0); numbers > 15 are company history ("over 35 years of experience")
  const EXP_RE = /\b(\d{1,2})\+?\s*(?:(?:-|\u2013|\u2014|to)\s*\d{1,2}\+?\s*)?(?:years?|yrs?)(?:'|\u2019)?\s+(?:of\s+)?(?:professional |relevant |industry |full[- ]time |hands-on |work |related |progressive )*(?:work )?experience\b/gi;
  function expFloor(t) {
    const re = new RegExp(EXP_RE.source, "gi"); let m;
    while ((m = re.exec(t))) { const n = +m[1];
      if (/\b(?:up to|no more than|less than|fewer than|under|maximum of|max\.?)\s*$/i.test(t.slice(Math.max(0, m.index - 16), m.index))) continue;   // a ceiling, not a floor (JSA-231)
      if (n <= 15) return { n, i: m.index }; }
    return null;
  }
  // JSA-231: is the experience line a preference? The nearest heading before it decides ("Preferred Qualifications" vs
  // "Minimum / Required / Basic Qualifications"), or the line itself says "preferred" / "a plus" / "nice to have"
  const PREF_HEAD = /\b(?:preferred|desired|bonus|nice[- ]to[- ]have|additional)\s+(?:qualifications?|skills|experience|background|requirements|attributes)\b|\b(?:nice[- ]to[- ]haves?|bonus points|preferred)\s*[:\-]|\bideally,? you(?:'d| would) have\b/gi;
  const REQ_HEAD = /(?<!\b(?:preferred|desired|bonus|additional|nice[- ]to[- ]have)\s)\b(?:minimum|required|basic|must[- ]haves?|requirements|what you(?:'ll)? need|what we(?:'re| are) looking for|what you (?:have|bring)|qualifications|you (?:may|might) be a good fit|you(?:'ll)? thrive)\b/gi;
  function lastIdx(re, s) { let m, i = -1; const r = new RegExp(re.source, "gi"); while ((m = r.exec(s))) i = m.index; return i; }
  function expPreferred(t, i) {
    // "3+ years of experience ... preferred" in the same clause; "NICE TO HAVE:" right after is the next heading, not this line
    if (/^[^.;,\u2022]{0,90}\b(?:preferred|is a plus|are a plus|a plus|nice to have|desired)\b(?!\s*[:\-])/i.test(t.slice(i, i + 120))) return true;
    const before = t.slice(Math.max(0, i - 600), i);
    return lastIdx(PREF_HEAD, before) > lastIdx(REQ_HEAD, before);
  }
  // "Minimum Years of Work Experience: 0" (Home Depot's labelled field) outranks any preferred floor
  const EXP_ZERO = /\bminimum (?:years of )?(?:work |relevant )?experience(?: \(years\))?\s*:\s*(?:0|none|no)\b/i;
  // JSA-416: the internship's own term. Season + year ("Summer 2026") and month ranges with a year ("June – August 2026") are the
  // terms the posting offers; a posted date, a deadline or graduation wording is not. Returns the years found with a snippet.
  function cycleYears(t) {
    const out = [];
    const skip = (i, len) => { const pre = t.slice(Math.max(0, i - 60), i), sent = pre.slice(Math.max(pre.lastIndexOf(". "), pre.lastIndexOf("; ")) + 1);   // this sentence only
      return /graduat|class of|degree|commencement|apply (?:by|before|until)|application|deadline|posted|recruit|copyright|©|opens?\b|closes?\b/i.test(sent)
        || /\b(?:was|were|last|previous|prior|past|successful|success)\b/i.test(sent + " " + t.slice(i, i + len + 80).split(/[.;]\s/)[0])
        || /^\s*(?:applications?|recruit\w*|deadline|posting)/i.test(t.slice(i + len, i + len + 20)); };
    let m, re = /\b(summer|fall|autumn|spring|winter)\s+(?:term\s+|session\s+|cohort\s+|internship\s+)?(?:of\s+)?(?:20)?(2[5-9]|3[0-2])\b/gi;
    while ((m = re.exec(t))) if (!skip(m.index, m[0].length)) out.push({ year: 2000 + +m[2], ev: snip(t, m.index) });
    re = /\b(?:20)(2[5-9]|3[0-2])\s+(?:summer|fall|autumn|spring|winter)\b/gi;
    while ((m = re.exec(t))) if (!skip(m.index, m[0].length)) out.push({ year: 2000 + +m[1], ev: snip(t, m.index) });
    re = /\b(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?\s*(?:\d{1,2}(?:st|nd|rd|th)?,?\s*)?(?:(?:20)?\d\d\s*)?(?:-|–|—|to|through|until)\s*(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?\s*(?:\d{1,2}(?:st|nd|rd|th)?,?\s*)?(?:20)(2[5-9]|3[0-2])\b/gi;
    while ((m = re.exec(t))) if (!skip(m.index, m[0].length)) out.push({ year: 2000 + +m[2], ev: snip(t, m.index) });
    return out;
  }
  // JSA-416: a postdoc, or a posting that needs the doctorate already finished (the candidate is a master's student)
  function doctorateHeld(title, t) {
    if (/\bpost-?doc(?:toral)?\b/i.test(title)) return title;
    { const pm = /\bthis (?:is|role is|position is) an? (?:[\w–-]+ ){0,3}post-?doc(?:toral)? (?:appointment|position|fellowship|role)\b/i.exec(t); if (pm) return snip(t, pm.index); }   // "This is a 12-24 month postdoctoral appointment"
    const DOC = "(?:Ph\\.?\\s?D\\.?|doctorate|doctoral degree)";
    const re = new RegExp("\\b" + DOC + "\\b[^.;]{0,60}\\bmust be (?:completed|conferred|awarded|obtained|earned|received)\\b|\\b(?:must|required to|need to|should) (?:have|hold|possess) (?:a |an )?(?:completed |earned |recent )?" + DOC + "\\b|\\b" + DOC + "\\b(?: degree)? (?:is |are )?required\\b|\\b(?:completed|received|earned) (?:a |an |your |their )?" + DOC + "\\b[^.;]{0,30}\\b(?:prior to|before) (?:the )?start", "gi");
    let m;
    while ((m = re.exec(t))) {
      const a = Math.max(t.lastIndexOf(".", m.index), t.lastIndexOf(";", m.index)) + 1, e = t.indexOf(".", m.index + m[0].length);
      const sent = t.slice(a, e < 0 ? t.length : e);
      if (/\b(?:prefer\w*|plus|bonus|desired|ideal\w*|or equivalent|master'?s|M\.?S\.?\b|bachelor'?s|or higher)\b/i.test(sent)) continue;
      // JSA-416 review: a sentence about the candidate's own PhD studies, or about another role / the mentor, is not this role's requirement
      if (/\b(?:pursuing|enrolled|candidacy|in progress|qualifying)\b/i.test(sent)) continue;
      if (/\b(?:mentor\w*|supervis\w*|manager|senior|staff|principal|other roles?|our (?:scientists|researchers|team)|for the [\w ]{0,40}\brole)\b/i.test(sent) && !/\bthis (?:role|position|internship)\b|\bcandidates?\b|\bapplicants?\b|\byou\b/i.test(sent)) continue;
      return snip(t, m.index);
    }
    return null;
  }
  function classify(job) {
    // job: {title, text (html or plain), loc, level: "Internship"|"New grad"|"Early career", closed}
    const title = clean(job.title), t = clean(job.text), all = title + " . " + t, R = [];
    if (job.closed) return { verdict: "Closed", reasons: [{ code: "CLOSED", level: "block", ev: job.closed }] };
    if (!t || t.length < 200) R.push({ code: "NO_TEXT", level: "review", ev: "job description not readable" });
    let ev;
    for (const re of CITIZEN) if ((ev = find(all, re))) {
      const clearance = /clearance|ITAR|export[- ]control/i.test(ev) || /clearance|ITAR|export/i.test(re.source);
      if (!CAND.citizen_or_pr) { R.push({ code: "CITIZEN_OR_CLEARANCE", level: "block", ev }); break; }
      if (clearance) { R.push({ code: "CITIZEN_OR_CLEARANCE", level: "review", ev }); break; }   // a citizen may still lack the clearance
    }                                                                                             // citizenship alone: a citizen passes (open-source users, 11-03)
    // JSA-231: "does not participate in the STEM OPT extension" says nothing about CPT, OPT or H-1B — a review, not a block;
    // such sentences are taken out before the no-sponsorship patterns run
    let spText = all, stemOpt = null;
    spText = spText.replace(/[^.;]*\bSTEM[- ]?OPT\b[^.;]*[.;]?/gi, sent => {
      if (!/\b(?:not|no|never|unable|cannot|can't|won't|doesn't|don't)\b/i.test(sent)) return sent;
      if (/\bsponsor\w*|\bH-?1B\b|\bF-?1\b|\bCPT\b|(?<!STEM[- ]?)\bOPT\b(?![- ]?(?:out|in)\b)|\bvisas?\b/i.test(sent.replace(/\bSTEM[- ]?OPT\b/gi, ""))) return sent;
      stemOpt = stemOpt || sent.trim().slice(0, 180); return " ";
    });
    let noSp = null; for (const re of NO_SPONSOR) if ((ev = find(spText, re))) { noSp = ev; break; }
    const offers = find(spText, OFFERS_SPONSOR);
    const discretion =
      // "At its sole discretion, X determines whether to offer sponsorship", "may be considered in limited circumstances"
      // (Joey 2026-11-05 Acuity: 「照投」): discretionary sponsorship is not a no
      find(spText, /\bsponsor\w*\b[^.]{0,140}\b(?:sole discretion|case[- ]by[- ]case|limited circumstances|may be considered|evaluated individually)\b|\b(?:sole discretion|case[- ]by[- ]case|limited circumstances)\b[^.]{0,140}\bsponsor\w*/i);
    if (stemOpt && !noSp && CAND.needs_sponsorship) R.push({ code: "NO_STEM_OPT", level: "review", ev: stemOpt });
    // JSA-238 (Joey 2026-11-06: 「如果只是说不提供担保，但是可以实习的话就不拦。如果是实习都不能实习，就拦掉。」):
    // an internship runs on CPT, which needs no sponsorship — a plain "no sponsorship (for this position)" does not block it.
    // Still a block when the posting rules out the internship itself: F-1 / CPT / OPT not accepted, authorized "for any
    // employer", permanent / unrestricted authorization. "now or in the future" (a return offer would need H-1B) → a review.
    const internRole = /intern/i.test(job.level || "") || /\bintern(ship)?s?\b|\bco-?op\b/i.test(title);
    const restrictive = noSp && NO_SPONSOR_RESTRICTIVE.map(re => find(spText, re)).find(Boolean);
    const FUT = "(?:now or (?:at any (?:time|point) )?in the future|(?:currently|presently|today) or in the future|now or later|at any (?:time|point)(?: in the future)?|in the future|future (?:visa |immigration |employment |work )?sponsorship|ever (?:require|need))";
    const futureSp = noSp && find(spText, new RegExp("\\bsponsor\\w*\\b[^.;]{0,90}\\b" + FUT + "\\b|\\b" + FUT + "\\b[^.;]{0,60}\\bsponsor\\w*|\\bfuture (?:visa |immigration |employment |work )?sponsorship\\b", "i"));
    if (noSp && !CAND.needs_sponsorship) { /* "no sponsorship" does not matter to this candidate */ }
    else if (noSp && internRole && !restrictive && !offers && !discretion) {
      // JSA-385 (Joey 2026-11-17: his top goal is an internship; CPT needs no sponsorship): both wordings are Eligible now, as a
      // 'plus' code the scorer reads. (1) the employer only says it does not sponsor → NO_SPONSORSHIP_INTERN (ranked a little
      // lower by the sponsor factor). (2) the candidate must not need sponsorship now or in the future, or a "without /
      // not require sponsorship" sentence with no time word (unsure → treat as 2) → NO_FUTURE_SPONSORSHIP_INTERN (one tier
      // lower, C; the form answers stay truthful).
      const mustNotNeed = futureSp || find(spText, MUST_NOT_NEED);
      // a student / temporary visa named as not accepted, in words the restrictive patterns miss ("temporary visas … not
      // eligible", "CPT, OPT … do not meet the requirements"): unsure → a person reads it, as before JSA-385
      const visaNamed = find(spText, /\b(?:CPT|OPT|F-?1|J-?1|STEM OPT|temporary visas?|student visas?|visa holders?|international students?|foreign nationals?|non-?citizens?)\b[^.;]{0,120}\b(?:not|ineligible|unable|cannot)\b|\b(?:not eligible|ineligible|cannot|unable)\b[^.;]{0,80}\b(?:CPT|OPT|F-?1|temporary visas?|student visas?|international students?|foreign nationals?|non-?citizens?)\b|\bclearance\b[^.;]{0,60}\b(?:eligib\w*|required|requirement)\b|\beligib\w*[^.;]{0,30}\bclearance\b/i);
      if (visaNamed) R.push({ code: "NO_FUTURE_SPONSORSHIP_INTERN", level: "review", ev: visaNamed });
      else if (mustNotNeed) R.push({ code: "NO_FUTURE_SPONSORSHIP_INTERN", level: "plus", ev: mustNotNeed });
      else R.push({ code: "NO_SPONSORSHIP_INTERN", level: "plus", ev: noSp });
    }
    else if (noSp && !offers && !discretion) R.push({ code: "NO_SPONSORSHIP", level: "block", ev: restrictive || noSp });
    else if (noSp && (offers || discretion)) R.push({ code: "SPONSORSHIP_MIXED", level: "review", ev: noSp });
    else if (offers) R.push({ code: "OFFERS_SPONSORSHIP", level: "plus", ev: offers });
    const lv = locationVerdict(job.loc); if (lv) R.push(lv);
    const intern = /intern/i.test(job.level || "") || /\bintern(ship)?\b/i.test(title);
    if (intern) {
      const tl = title.toLowerCase();
      const summerAny = /\bsummer\b/i.test(all);
      if (/\b(winter|spring|fall|autumn)\b/.test(tl) && !/\bsummer\b/.test(tl)) R.push({ code: "OFF_CYCLE", level: "block", ev: title });
      // JSA-238 (Joey 2026-11-06 「改成待核实」): a co-op with no term or dates is a review; a stated off-summer term still blocks
      else if (!summerAny || (/\bco-?op\b/.test(tl) && !/\bsummer\b/.test(tl))) {
        let coop = /\bco-?op\b/.test(tl) && !/\bsummer\b/.test(tl) ? title : null;
        const re = /\b(winter|spring|fall|autumn)\s+(?:20)?2[67]\b|\b(fall|spring|winter) (semester|term|quarter|session)\b|\bco-?op\b/gi; let mm;
        while ((mm = re.exec(t))) { if (/graduat|class of|degree/i.test(t.slice(Math.max(0, mm.index - 60), mm.index))) continue;
          // "prior internship or co-op experience", "Co-op/Interns will be reimbursed" describe the candidate or a benefit, not this role
          if (/co-?op/i.test(mm[0]) && (/(internship|intern)s?\s*(or|and|\/)\s*$/i.test(t.slice(Math.max(0, mm.index - 20), mm.index)) || /^co-?op\s*(\/\s*interns?|s?\s*(or|and)\s*interns?|\s+(experience|students? and interns?))/i.test(t.slice(mm.index, mm.index + 30)))) continue; if (/co-?op/i.test(mm[0])) {
            // "a 4-month co-op starting in January": an off-summer month next to the co-op is a date
            const near = t.slice(Math.max(0, mm.index - 60), mm.index + 60);
            if (/\b(?:jan|feb|mar|apr|sep|oct|nov|dec)(?:uary|ruary|ch|il|tember|ober|ember)?\b/i.test(near) && !/\b(?:may|june?|july?|aug(?:ust)?)\b/i.test(near)) { R.push({ code: "OFF_CYCLE", level: "block", ev: snip(t, mm.index) }); break; }
            coop = coop || snip(t, mm.index); continue; }
          R.push({ code: "OFF_CYCLE", level: "block", ev: snip(t, mm.index) }); break; }
        if (coop && !R.some(r => r.code === "OFF_CYCLE") && !termRange(t)) R.push({ code: "COOP_NO_DATES", level: "review", ev: coop });
      }
      // a dated range that never touches June–August (Hitachi "Duration: 3 Months (January - March 2027)", 2026-10-30)
      if (!R.some(r => r.code === "OFF_CYCLE")) { const off = termRange(t); if (off) R.push({ code: "OFF_CYCLE", level: summerAny ? "review" : "block", ev: off }); }
      // JSA-416: every term / date the posting states is before the candidate's internship summer → a cycle that has passed
      { const cy = cycleYears(all); if (cy.length && Math.max(...cy.map(c => c.year)) < CAND.intern_summer) R.push({ code: "PAST_CYCLE", level: "block", ev: cy[0].ev + " (before Summer " + CAND.intern_summer + ")" }); }
      const tm = title.match(/(?<!\d\s?[-–]\s?)\b(?:5|6|7|8|9|10|11|12|five|six|seven|eight|nine|ten|twelve)[- ]?months?\b/i);
      if (tm) R.push({ code: "TOO_LONG", level: "block", ev: title });
      else if ((ev = find(t, /\b(?:duration|length|period|lasts?|runs? for|internship of|for a period of)\b[^.;:]{0,15}:?\s*(?<!\b[1-4]\s?(?:-|to|or)\s?)(?:5|6|7|8|9|10|11|12|five|six|seven|eight|nine|ten|twelve)[- ]?months?\b/i))) R.push({ code: "TOO_LONG", level: "block", ev });
      else if ((ev = find(t, /\b(?:minimum|at least|min\.?)\b[^.;]{0,25}\b(?<!\b[1-4]\s?(?:-|to|or)\s?)(?:5|6|7|8|9|10|11|12|five|six|seven|eight|nine|ten|twelve)[- ]?months?\b|(?<!\b[1-4]\s?(?:-|to|or)\s?)\b(?:6|six|8|eight|12|twelve)[- ]month (?:internship|co-?op|commitment|program)\b/i))) R.push({ code: "TOO_LONG", level: "block", ev });
      if ((ev = find(t, /\bpart[- ]time\b[^.;]{0,60}\b(semester|school year|academic year|during (?:the )?(?:fall|spring))\b/i))) R.push({ code: "PART_TIME_IN_TERM", level: "review", ev });
      // part-time role with no summer dates (e.g. "10–20 hours per week") = likely during the school year
      else if (!summerAny && (ev = find(t, /(?<!full[- ]time\s*(?:or|\/)\s*)\bpart[- ]time\b(?!\s*(?:or|\/)\s*full)(?![^.]{0,30}benefit)|\b(?:[5-9]|[12]\d|30)\s*(?:[-–]|to)\s*(?:[5-9]|[12]\d|30)\s*(?:hours|hrs)\s*(?:per|a|\/)\s*week\b|\bup to (?:[5-9]|[12]\d|30) (?:hours|hrs) (?:per|a) week\b/i))) R.push({ code: "PART_TIME_IN_TERM", level: "review", ev });
      // degree level — a graduate student (masters / phd): class-year and bachelor's-only wording rules them out or needs a look;
      // a bachelor's student (JSA-087): bachelor's wording is fine, a class-year limit needs a look, graduate-only wording too
      const undergradJunk = /\b(?:open|limited|restricted) to junior[- ]status\b[^.;]{0,30}\bonly\b|\bjunior[- ]status (?:college |undergraduate )?students only\b|\b(?:open|limited|restricted) to (?:college |undergraduate )?juniors\b|\bjuniors only\b|\b(rising (?:junior|senior|sophomore)|juniors?\b[^.;]{0,40}\bbachelor'?s|(?:juniors?|sophomores?) (?:or seniors?|and seniors?)|junior or senior year|sophomore or junior|freshman)\b/i;
      if (CAND.degree_level === "bachelors") {
        if ((ev = find(t, undergradJunk))) R.push({ code: "CLASS_YEAR", level: "review", ev });
        if ((ev = find(t, /\b(?:currently )?(?:pursuing|enrolled in|currently in|candidate for|working towards?) (?:a |an |your )?(?:master'?s|graduate|M\.?S\.?|MSc|Ph\.?D|doctoral)(?: degree| program| studies)?\b|\b(?:graduate|master'?s|Ph\.?D) students? only\b/i)) && !/\b(bachelor'?s?|undergraduate|undergrad|BS|B\.S\.|BA|B\.A\.|all (?:education|degree) levels)\b/i.test(t)) R.push({ code: "GRAD_STUDENT_ONLY", level: "review", ev });
      }
      const mastersOk = /(?:undergraduate|bachelor'?s?)\s*(?:\/|or|and)\s*master\b|\bmaster\s+(?:degree|program|student)|\b(master'?s|masters|graduate (?:student|degree|program|school|studies)|M\.?S\.?\b|MSc|M\.Eng|MBA|advanced degree|Ph\.?D|doctoral|postgraduate|graduate or undergraduate|undergraduate or graduate|undergraduate\/graduate|all (?:education|degree) levels)\b/i.test(t);
      // an explicit "juniors only" limit holds even when the JD also says "bachelor's or master's" (Uline 2026-10-30)
      if (CAND.degree_level === "bachelors") { /* handled above */ }
      else if ((ev = find(t, /\b(?:open|limited|restricted) to junior[- ]status\b[^.;]{0,30}\bonly\b|\bjunior[- ]status (?:college |undergraduate )?students only\b|\b(?:open|limited|restricted) to (?:college |undergraduate )?juniors\b|\bjuniors only\b/i))) R.push({ code: "UNDERGRAD_ONLY", level: "block", ev });
      else if (!mastersOk) {
        const um = /\b(rising (?:junior|senior|sophomore)|juniors?\b[^.;]{0,40}\bbachelor'?s|(?:juniors?|sophomores?) (?:or seniors?|and seniors?)|junior or senior year|sophomore or junior|freshman|undergraduate students? only|bachelor'?s (?:students? )?only)\b/i.exec(t);
        // "Rising Junior or Senior preferred", "junior or senior standing preferred": a preference, not a limit (JSA-231)
        if (um && /^[^.;]{0,40}\b(?:preferred|is a plus|a plus|desired|ideal(?:ly)?)\b/i.test(t.slice(um.index + um[0].length, um.index + um[0].length + 60))) R.push({ code: "UNDERGRAD_PREFERRED", level: "review", ev: snip(t, um.index) });
        else if (um) R.push({ code: "UNDERGRAD_ONLY", level: "block", ev: snip(t, um.index) });
        else if ((ev = find(t, /\b(?:pursuing|enrolled in|working towards?|candidate for) (?:a |an |your )?(?:bachelor'?s|undergraduate|BS|B\.S\.|BA|B\.A\.)\b/i))) R.push({ code: "BACHELORS_WORDING", level: "review", ev });
        // "Students expecting to graduate in December 2027 through June 2028 with a bachelor's degree" (Hartford 2026-11-01): his bachelor's is done
        else if ((ev = find(t, /\bgraduat\w*\b[^.;]{0,80}\bwith (?:a |an |their )?(?:bachelor'?s|undergraduate|BS|B\.S\.|BA|B\.A\.)(?: degree)?\b|\b(?:completing|finishing|earning) (?:a |an |their |your )?(?:bachelor'?s|undergraduate) degree\b|\bexpected graduation:? (?:a |an )?(?:bachelor'?s|undergraduate)\b/i))) R.push({ code: "BACHELORS_WORDING", level: "review", ev });
      }
      if (CAND.degree_level !== "phd" && (ev = find(t, /\b(?:currently )?(?:pursuing|enrolled in) (?:a )?(?:Ph\.?D|doctoral)\b|(?:^|[.:;!?]\s+|\bqualifications:?\s+)(?:current )?(?:Ph\.?D\.?|doctoral) (?:students?|candidates?)\b(?! (?:are|is) (?:also )?(?:welcome|encouraged))/i)) && !/\b(master'?s|M\.?S\.?\b|bachelor'?s)\b/i.test(t) && !/\b(?:Ph\.?D|doctoral)\b[^.;]{0,60}\b(?:are|is) (?:also )?(?:welcome|encouraged)|\bwelcome (?:students|applicants) (?:from|in) (?:other|all|any) (?:degree|academic)/i.test(t)) R.push({ code: "PHD_ONLY", level: "block", ev });
    } else {
      // full-time: experience floor
      // the first required floor counts, as before ("2 years ... OR 14 years" = 2); a floor that is only preferred (or a
      // labelled minimum of 0) is a review (JSA-231)
      const re = new RegExp(EXP_RE.source, "gi"); let mm, req = null, pref = null;
      while ((mm = re.exec(t))) { const n = +mm[1];
        if (n > 15 || /\b(?:up to|no more than|less than|fewer than|under|maximum of|max\.?)\s*$/i.test(t.slice(Math.max(0, mm.index - 16), mm.index))) continue;
        if (expPreferred(t, mm.index) || EXP_ZERO.test(t)) { pref = pref || { n, i: mm.index }; }
        else { req = { n, i: mm.index }; break; } }
      if (req && req.n >= 3) R.push({ code: "EXPERIENCE_3PLUS", level: "block", ev: snip(t, req.i) });
      else if (req && req.n === 2) R.push({ code: "EXPERIENCE_2", level: "review", ev: snip(t, req.i) });
      else if (pref && pref.n >= 3) R.push({ code: "EXPERIENCE_PREFERRED", level: "review", ev: snip(t, pref.i) });
    }
    // JSA-416: postdoc / doctorate already held — a master's student cannot meet it (a PhD student may ask for the doctorate)
    if (CAND.degree_level !== "phd" && (ev = doctorateHeld(title, t))) R.push({ code: "POSTDOC_OR_PHD_DONE", level: "block", ev });
    if (/\bMBA\b/.test(title) && !/\b(?:M\.?S\.?|MSc|Master'?s?|Masters|graduate|Ph\.?D|M\.?Eng)\b/i.test(title.replace(/\bMBA\b/g, ""))) R.push({ code: "MBA_ONLY", level: "block", ev: title });
    else if ((ev = find(t, /\b(?:current|currently enrolled|currently pursuing) MBA students?\b/i))) R.push({ code: "MBA_ONLY", level: "block", ev });
    // "Enrolled in an MBA program …", "looking for an MBA candidate" (Nike/Converse 2026-10-30) — not when the JD offers
    // another degree right after it ("… MBA program for an MBA internship OR a master's program for …", Amgen)
    else if ((ev = (() => { const re = /\b(?:enrolled in|pursuing|currently in) (?:an? |the |your )?MBA(?: program| degree)?\b|\blooking for (?:an? )?MBA (?:candidate|student|intern)s?\b|\bpre-MBA (?:professional |work )?experience\b/gi; let m;
        while ((m = re.exec(t))) { if (/^[^.]{0,160}\bor\b[^.]{0,80}\b(?:master|graduate|bachelor|undergraduate|Ph\.?D|M\.?S\b)/i.test(t.slice(m.index + m[0].length, m.index + m[0].length + 260))) continue; return snip(t, m.index); }
        return null; })())) R.push({ code: "MBA_ONLY", level: "block", ev });
    const g = gradVerdict(t); if (g) R.push(g);
    const blocks = R.filter(r => r.level === "block"), reviews = R.filter(r => r.level === "review");
    return { verdict: blocks.length ? "Ineligible" : reviews.length ? "Review" : "Eligible", reasons: R };
  }
  const api = { classify, clean, gradVerdict, locationVerdict, expFloor, setCandidate };
  if (typeof module !== "undefined") module.exports = api; else root.ELIG = api;
})(typeof window !== "undefined" ? window : globalThis);
