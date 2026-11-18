// Standard form answers as matching rules — no model needed for fixed questions (JSA-077, 2026-11-02).
// This file holds only the QUESTION matching (q / not / behaviour); every ANSWER (text, pick, alts, yes …) lives in
// config/profile.json → "answers" (rule id → answer), loaded by config/profile.js. Source of the answers: the user's
// candidate profile (here skills/_shared/candidate-profile.md). A rule with no answer in the profile is skipped (unknown). Questions that match nothing (or match two rules) come back as "unknown".
//
// Browser: load cx_bundle.js (= form_helpers.js + this file) once, then (all return OBJECTS unless noted):
//   __cx.extractObj()  fields  |  __cx.plan(answers?) → {actions, unknown, consent, files, notes}  |  await __cx.run(plan) → dump + results
//   Legacy (return JSON STRINGS): __cx.extract(); __cx.auto() → '{fill, click, unknown, consent}'.  Object variant: __cx.autoObj().
//   Option-less combos (react-select) get value = r.combo / r.text / Yes|No, plus `alts` (ordered alternatives) when a rule has them.
// Node (tests): const {match} = require('./answer_rules.js'); match(fields, {jd, company})   — ctx.jd = the JD text (rules with jd: true need it, JSA-105);
//   ctx.company = the hiring company (referral questions check it against the referrer pool, JSA-195; none given = ask the user)
(function (root) {
  const P = root.__cxProfile || (typeof require === 'function' ? require('../../../config/profile.js') : null);   // browser: set globalThis.__cxProfile first
  if (!P || !P.answers) throw new Error('answer_rules: profile not loaded (config/profile.json; in a page set globalThis.__cxProfile)');
  // the referrer pool (JSA-195): config/connections.json → connections; browser: globalThis.__cxPool (build_bundle.py). Not loaded = every referral question is asked
  const POOL = root.__cxPool || (typeof require === 'function' ? (() => { try { return require('../../../config/connections.js'); } catch (e) { return null; } })() : null);
  // the tracker's applications (JSA-281): config/applied.js (Node, read fresh) or globalThis.__cxApplied (browser, dated)
  const APPLIED = root.__cxApplied !== undefined ? root.__cxApplied : (typeof require === 'function' ? (() => { try { return require('../../../config/applied.js'); } catch (e) { return null; } })() : null);
  const RX = s => { const i = s.lastIndexOf('/'); return new RegExp(s.slice(1, i), s.slice(i + 1)); };   // "/re/flags" → RegExp
  const EMP = P.employers_re || '(?!)', EMP_WORDS = P.employer_words_re || '(?!)';   // the user's own employers (resume_employer / prior_employer)
  // JSA-175: example clauses — "(e.g., …)", "(such as …)", a parenthesised list "(U.S. citizen, F-1 OPT, etc.)", "e.g. …" up to the
  // end of the sentence. Removed before asking whether the question itself (not an example) is about OPT. Nested groups are
  // read inside out: "(e.g., … based on F-1 Optional Practical Training (OPT))" (Goldman Oracle 11-05) — the inner "(OPT)"
  // is kept as text, then the outer example group goes.
  const EG_MARK = /\be\.?\s?g\b|\bi\.?\s?e\b|such as|including|for (?:example|instance)|\blike\b|\bex\.|,|\betc\b/i;
  const EG_TAIL = /\b(?:[eE]\.\s?[gG]\.|[sS]uch as|[fF]or (?:example|instance))[\s,:](?:[^.?;()[\]]|\.(?!\s+[A-Z]))*/g;   // no /i: a '.' ends the clause only before a capital ("U.S. citizen" does not)
  const noExamples = l => {
    let s = String(l || ''), prev;
    do { prev = s; s = s.replace(/\(([^()]*)\)/g, (m, c) => EG_MARK.test(c) ? ' ' : '[' + c + ']'); } while (s !== prev);
    return s.replace(EG_TAIL, ' ');
  };
  const CONVICT_Q = /\b(been|ever been|ever|was|were|are you) (convicted|found guilty|charged)\b|\bconvicted of\b|\bpl(ea|e)d(ed)? (guilty|no contest|nolo)|\bfelon(y|ies)?\b|\bcriminal (record|history|conviction|offen[cs]e|charges?)\b|\bconvictions?\b/i;   // JSA-281
  const APPLIED_Q = /\b(previously|ever|already|before|in the past|prior(ly)?|last \d+(?:\s*(?:-|–|to)\s*\d+)? (months?|years?|days?)|past \d+(?:\s*(?:-|–|to)\s*\d+)? (months?|years?|days?))\b[^?]{0,60}\b(applied|submitted (an )?application)|\b(applied|submitted (an )?application)\b[^?]{0,80}\b(before|previously|in the past|prior|last \d+(?:\s*(?:-|–|to)\s*\d+)? (months?|years?|days?)|past \d+(?:\s*(?:-|–|to)\s*\d+)? (months?|years?|days?)|past year|last year)\b/i;   // JSA-281
  const AUTH_Q = /(?:.*(legally )?authori[sz]ed to work|.*eligible to work|.*work authori[sz]ation|.*authori[sz]ation to work|.*(legally )?(permitted|allowed|qualified) to work|.*legally able to work|.*\blegal right to work\b|.*(legally )?eligible for employment|.*authori[sz]ed (or|and\/or) (legally )?(able|eligible|permitted) to work)/i;   // "legally able to work" (iCIMS West Bend 2026-11-03); "legally authorized or able to work in the country in which the position is located" (Newell SF 11-05, type AC)
  const RESTRICTED = !!(P.work_auth && P.work_auth.restricted);   // e.g. F-1 / CPT: authorized, but not unrestricted / permanent
  // JSA-310 (Joey 2026-11-11): every work-authorization question is answered Yes — "for any employer" / "without restriction"
  // too (ATS knock-out filters reject a No; he holds CPT / OPT authorization when he starts). Sponsorship answers do not change.
  const CLAIM_AUTH = RESTRICTED && !!(P.work_auth && P.work_auth.claim_authorized);
  // JSA-316 (a Lever employer 11-05, Joey 2026-11-11): a question about supporting / contributing to military or defense missions
  // (willing, able, any reason not to) — never his own government or military employment. = fact_gate.DEFENSE_SUPPORT.
  // Not: the service-member / veteran self-identification wordings ("hiring and supporting military service members").
  const DEFENSE_SUPPORT = /^(?![\s\S]*\b(service members?|military spouses?|veterans?|(military|veteran) status|self[- ]identif\w*)\b)[\s\S]*(\b(support(s|ed|ing)?|contribut\w*|assist(s|ing)?|help(s|ing)?)\b[^?!]{0,60}\b(military|defen[cs]e|armed forces|allied forces|national security|warfighters?|department of (defense|war)|dod)\b|\b(military|defen[cs]e)[- ](missions?|applications?|projects?|programs?|customers?|clients?|industry|products?|technolog\w*|contracts?|systems?|sector|work)\b|\b(reasons?|objections?|concerns?|reservations?|hesitat\w*)\b[^?]{0,80}\b(military|defen[cs]e|armed forces)\b|\b(willing(ness)?|comfortable|able|okay|ok|object)\b[^?]{0,60}\b(military|defen[cs]e|armed forces)\b)/i;
  const GOV_NOT = new RegExp(DEFENSE_SUPPORT.source + '|\\bveterans?\\b', 'i');   // a veteran question ("veteran or active member of the Armed Forces") stays the veteran rule's
  // JSA-325 (Dell / Excellus 11-11, Joey 「是非问句不填名称 + major 加词边界」): a rule that fills a NAME or other value
// (employer, school, major, name, address …) never answers a yes/no question about it: "Is your current employer a reseller
// of Dell …?" got "University of Chicago" in a text box. The question decides: when it asks only yes/no questions and asks
// for no value, those rules stand aside — the saved qa answer or Joey. The mirror of JSA-322 (yes/no rules in text boxes).
const NAME_RULES = new Set(['employer', 'recent_employer', 'school', 'hs_name', 'degree', 'discipline',
  'education_list', 'first_name', 'last_name', 'full_name', 'preferred_name', 'preferred_full_name', 'preferred_last_name',
  'middle_initial', 'address', 'address_full', 'permanent_address',
  'city', 'city_state', 'city_state_zip', 'county', 'zip', 'state', 'location', 'location_full', 'linkedin', 'website',
  'citizenship_country']);
const YN_WORD = /^\W*(are|is|am|do|does|did|will|would|can|could|have|has|had|were|was|should|may|must)\b/i;
const ASKS_VALUE = /^\W*(what|which|who|whom|whose|where|when|how|why|name|list|enter|provide|specify|state|indicate|please (list|provide|enter|specify|state|name|indicate|write|type|share|tell))\b/i;
function ynBox(f) {   // a text box or a Yes / No pair: a country / degree list under "Do you hold …?" keeps its rule (Intuitive, Bosch replay)
  const o = (f && (f.o || f.options)) || [];
  return !o.length || o.every(x => /^\W*(yes|no)\b/i.test(String(x)));
}
function ynQuestion(label) {   // pure (tested: scripts/test_yn_question.js)
  const q = String(label || '').replace(/\s+/g, ' ').trim();
  const parts = q.split(/(?<=[.?!])\s+/).map(x => x.trim()).filter(Boolean);
  const asks = parts.filter(x => /\?\W*$/.test(x));
  if (!asks.length) return false;
  if (parts.some(x => ASKS_VALUE.test(x.replace(/^\(?\s*(if (yes|so|applicable),?\s*)?/i, '')))) return false;
  if (/\bplease (confirm|tell us|share|specify|provide|list|enter|indicate|state|name) (the|your|which|what|all)\b/i.test(q)) return false;   // "Can you please confirm the current degree …?" asks the degree (Bosch)
  return asks.some(x => YN_WORD.test(x));
}

// JSA-324 (Dell 11-11, Joey 「只答问你自己的题」): the on-site rule answers only a question about HIM being on site. "Are Dell
// Technologies personnel … on site permanently or on a regular basis at your employer's facilities?" has another subject
// (personnel / employees / staff …) and no "you" doing the work → not the on-site rule (the saved qa answer or Joey).
const ONSITE_OTHER = /\b(personnel|employees?|staff|representatives?|contractors?|consultants?|technicians?|engineers?|team members?|workers?)\b[^?.]{0,100}\b(on[- ]?site|in[- ]office|in person|in (the|our|your|their) [\w' ]{0,30}office|commute|hybrid)/i;
const ONSITE_YOU = /\b(are|will|would|can|could|do|did|have|were|is) you\b|\byou(?:'re|'ll| are| will| would| can| could| must| need| have| be| commit| agree| work)\b|\bwilling\b|\bable to\b|\bavailab|\byour (ability|willingness|availability)\b|\bI (am|can|will|would|agree|understand)\b/i;
function onsiteAboutHim(label) { return !ONSITE_OTHER.test(label) || ONSITE_YOU.test(label); }
// JSA-361 stop-gap (Joey 2026-11-16): a sponsorship question that names NO time is never answered by the rules — his
// answer differs by time (now: CPT, no sponsorship; full-time later: H-1B), so it always goes to him ("Do you require
// immigration sponsorship to work for Affirm?"). A detail / type box or a check-all list keeps its own handling.
const SPONS_TIME = /\b(now|currently|presently|at present|at this time|as of today|immediately|future|ever|at any (time|point)|any time|later|eventually|going forward|upon graduation|after (you |your )?graduat\w*|to (begin|start|commence)|(for|during|in|to participate in) (this|the)( [\w-]+){0,3} internship|duration of (this|the|your) internship|during (this|the|your) (position|role|employment|program)|(within|in) the next \d+|long[- ]term|full[- ]time (employment|role|position|job|work))\b/i;
const SPONS_NOT_YN = /\b(explain|describe|details?|provide|specify|list|check all|select all|what (type|kind)|which (type|kind)|type of (visa|sponsorship))\b/i;
const SPONS_Q = /sponsor|petition|employment[- ]based (status|visa|immigration)/i;
function sponsNoTime(label, ask, f) {   // ask = the question sentence(s) only: a note around it ("we do not currently sponsor", a Workday employer's statement) neither makes it a sponsorship question nor gives it a time (review 2026-11-16)
  if (!SPONS_Q.test(ask) || SPONS_TIME.test(ask)) return false;
  const opts = f.o || f.options || [];
  const ynControl = opts.length ? opts.every(o => /^\s*(yes|no)\b/i.test(String(o))) : !/^(text|textarea)$/.test(f.t || 'text');
  return !(SPONS_NOT_YN.test(label) && !ynControl);     // a detail / type box or a check-all list keeps its handling; a Yes / No control asks
}
// JSA-329 (Joey 2026-11-12, option A): "I agree to receive …" is an opt-in to be sent something, not the data consent —
// its "I agree" once answered Hunt Oil's "I agree to receive recruiting campaign communications." with Yes (marketing → No by
// his 10-27 rule). The shape decides, not a word list: an opt-in about jobs / the talent community → future_contact (Yes),
// about campaigns / marketing / events / news / offers → marketing (No), anything else → optin_other (asked). Messages
// about his own application or the hiring process are not an opt-in (data consent / sms as before). Pure (scripts/test_optin.py).
const OPTIN_SHAPE = /\b(agree|consent|opt[- ]?in|like|wish|want|happy)\b[^.?!]{0,40}\b(to )?(receive|get|be sent|be (contacted|notified|informed|kept (informed|posted|updated|up to date)))\b|^\W*(please |yes,? )?(send|e-?mail|notify|contact|receive|get)( me)?\b|\bsign (me )?up\b|\bsubscribe\b|\bopt[- ]?in to\b|\bkeep me (informed|posted|updated|up to date)\b/i;
// JSA-363: "do you have housing / a place to live / are you housed … in <place>" = does he already live there (answers.local_area.home).
const HOUSING_HAVE = /\b(do|does|did|have|has) (you|he|she|they)\b[^?.]{0,25}\b(have|having|already (have|secured))\b[^?.]{0,30}\b(housing|accommodations?|a place to (live|stay)|somewhere to (live|stay)|(an? )?(apartment|residence|lodging))\b|\bare you (currently )?housed\b/i;
// JSA-363: a Yes answer never picks a negated option — the profile's /^i (would|do)\b/ matched "I do not consent"
const NEG_OPT = /^(i |we )?(do not|don'?t|would not|wouldn'?t|will not|decline|disagree|refuse|prefer not|cannot|can'?t|am not|am unwilling|i'?d rather not|not (now|at this time))\b/i;
// JSA-363: "retain / keep my application … for future roles", "contact you later" = the talent-community consent, unless it is also about marketing / sharing
const RETAIN_FUTURE = { test: l => /\b(retain|keep|hold|store|maintain)\w*\b[^?.]{0,60}\b(application|resume|r[eé]sum[eé]|profile|(personal )?information|data)\b[^?.]{0,120}\b(future|later|other (roles|positions|opportunities|openings))\b|\bcontact (you|me) (later|in the future)\b/i.test(l) && !/marketing|promotion|newsletter|third[- ]part|\bshar(e|ing)\b|\bsell\b|\bsold\b|\bdisclos/i.test(l) };
// JSA-363: a place named in the question — "in the Austin area", "in Chicago", "in New York"
const NAMED_PLACE = /\b(in|near|around|at|to) (the )?[A-Z][\w.'-]+/;
const OPTIN_APP = /\b(my|this|the) (application|candidacy)\b|application (status|process|progress)|hiring process|recruit(ment|ing) process|interview|next steps|regarding (this|the) (role|position|job)\b/i;
const OPTIN_JOB_C = /\bjob(s| (opportunit|alert|opening|posting|update|match|recommendation|news)\w*)|career (opportunit|alert|update)\w*|\b(new|future|other|relevant|similar|matching|open) (jobs?|careers?|roles?|positions?|openings?|opportunit\w*|vacanc\w*)|\bopenings\b|talent (community|pool|network)/i;
const OPTIN_MKT_C = /\bcampaigns?\b|marketing|promotion|promotional|newsletter|\bnews\b|\bevents?\b|\bwebinars?\b|\boffers?\b|\bproducts?\b|\bsurveys?\b|\bpartners?\b|third[- ]part/i;
function optIn(l) { return OPTIN_SHAPE.test(l) && !OPTIN_APP.test(l); }
const OPTIN_MKT = { test: l => optIn(l) && OPTIN_MKT_C.test(l) };   // marketing wins a mixed box ("jobs and events"): the opt-in is optional, No is safe
const OPTIN_JOBS = { test: l => optIn(l) && OPTIN_JOB_C.test(l) && !OPTIN_MKT_C.test(l) };
const OPTIN_ABOUT_APP = { test: l => OPTIN_SHAPE.test(l) && OPTIN_APP.test(l) };
function either2(rx, extra) { const e = either(rx, extra); return { test: l => e.test(l) || RETAIN_FUTURE.test(l), source: e.source }; }
function either(rx, extra) { return { test: l => rx.test(l) || extra.test(l), source: rx.source }; }

const R = [
    // ---- identity & contact
    { id: 'name_pronunciation', q: /pronounc(e|ed|ing|iation)\b|pronunciation|phonetic/i },   // JSA-281: the misspelling "Name pronounciation" (an employer 11-09) fell through to full_name   // JSA-218 (Akuna 11-05): answers.name_pronunciation; none on file → ask, never the phone / name
    { id: 'has_preferred', q: /i have a preferred name|do you have a preferred name/i },   // Workday checkbox (Joey 10-28: use Joey)
    { id: 'preferred_full_name', q: /preferred (first\s*(&|and|\/)\s*last|full) name/i },   // Sierra (Ashby) 11-06: "Preferred First & Last Name" (JSA-230 live check)
    { id: 'preferred_last_name', q: /preferred (last name|surname|family name)/i },   // Dell (Oracle) 11-06: "Preferred Last Name"
    { id: 'preferred_name', q: /preferred (first )?name|nick ?name/i, not: /^(legal )?(first|last|middle) name\b|\blegal (first |last |middle )?name\b/i },   // "Legal Last Name (if different from preferred name)" got "Joey" (a Greenhouse employer 11-05, JSA-218)   // "Nick Name" (Hermeus 10-31, JSA-075)
    { id: 'first_name', q: /^(legal )?first name\b|given name/i },
    { id: 'last_name', q: /^(legal )?last name\b|family name|surname/i },
    { id: 'full_name', q: /^(?!.*(school|company|employer|university|reference|manager|supervisor|emergency|preferred|first|last|middle|refer|recruiter|relative|friend|contact person|team member|sponsor|countr(y|ies)|locations|pronoun|pronunc|phonetic)).*(\b(full|legal)\s+(legal\s+)?name\b|^name\b|^your name|^name of applicant)/i },
    { id: 'secondary_email', q: /\b(secondary|alternate|alternative|second|backup|additional)\s+(e-?mail|email address)\b/i },   // contact.secondary_email (Joey 2026-11-05); never the main address twice (Goldman Oracle 11-05)
    { id: 'email', q: /^(?!.*(marketing|newsletter|promotional|consent|communications)).*e-?mail/i, not: /^\W*(please |yes,? )?(send|e-?mail|notify|contact|keep) me\b|\b(i agree|opt[- ]?in|sign me up|subscribe)\b|\bsafe sender list\b/i },   // JSA-333: "add no-reply@… to your safe sender list" is lever_safe_sender, not the address box // "Send me emails about …" is an opt-in, not the address (JSA-329)
    { id: 'phone_device', q: /phone (number )?(device )?type|device type|type of phone/i },   // Workday ("Phone Type": JSA-185) My Information
    { id: 'phone_code', q: /country phone code|phone (country )?code|country code/i },   // Workday
    { id: 'phone', q: /^(?!.*extension)(?=.*(phone(?!tic)|mobile( number)?$|\bcell\b))/i, not: /phone (interview|screen|call)s?\b|pronounc|phonetic|\b(tele)?phone (lines?|service|access|equipment|systems?|plans?)\b|\baccess to (a |an )?(smart|cell |mobile |reliable )?(tele)?phone\b|^\W*(do|does|did|are|is|can|could|will|would|have|has|had)\b(?![^?]*\b(number|#|no\.)(?![a-z]))/i },   // JSA-315 (Voya WD 11-02, Joey 11-11 「收窄电话规则」): only a question that asks for the number — "capability to Work From Home (internet access, dedicated phone line …)" is a Yes / No about equipment (saved answer / asked)   // "…how your name is pronounced phonetically" got the phone number (Akuna 11-05, JSA-218)   // "…may consist of phone interview, … a drug screen … willing to participate?" is the background question (Oracle 2026-11-03)
    { id: 'permanent_address', q: /permanent( (legal|home|residential|street|mailing))* address|home[- ]country address|address in (your )?home[- ]country/i },   // F-1: the family home in China (Joey 2026-11-03, Workable an employer)
    { id: 'address_full', q: /\b(full|complete|entire|whole)( (home|mailing|residential|current|postal))? address\b|\baddress\b[^?]{0,80}?(\?\s*)?[^?]{0,60}\b(includ\w*|with|plus|and|along with)\b[^?]{0,30}\b(city|zip|postal)\b|\baddress\b\s*\((street,? )?city\b|\baddress\b[^?]{0,40}\bstreet,? city\b|\b(street|mailing|home|residential|current) address,? (city|including)\b/i,
      not: /permanent|home[- ]country|e-?mail|web ?site|\bip address|school|employer|company|reference|line ?2|address type|\b(do not|don't|without|exclud\w*|not includ\w*|omit\w*|separate(ly)?)\b|\b(street|address) only\b/i },   // JSA-311 (Crest Lever 10-31 / 11-02): one box that asks street + city / state / zip → "street, city, state zip" (built from answers.address + city_state_zip); was street only because `address` matched first
    { id: 'address', q: /street address|address( line)? ?1\b|mailing address|^address\*?$|street name and number/i, not: /\breferen|employer|company|school|universit|college/i },   // a bare "Address" (Workable an employer 2026-11-03); never "permanent legal address"
    { id: 'address_type', q: /^address type$/i },   // iCIMS profile: the address block's own Type list (Home …) (JSA-093 Lennox 2026-11-03)
    { id: 'city_state_zip', q: /city\s*[,\/]?\s*state\s*[,\/&]?\s*(and |& ?)?(zip|postal)/i },   // one box for all three (AMAT relocation 2026-10-30)
    { id: 'city_state', q: /\(city,? (and )?state\)|where do you (currently )?(live|reside)\b/i, not: /zip|postal|country|relocat|willing|commute/i },   // "Where do you currently live? (City, State)" (Pattern Lever 2026-11-04, JSA-144)
    { id: 'county', q: /^county\b/i, not: /county\s*\/\s*state|county or state/i },   // "County/State" is the state list (an employer 11-04)   // the county of the profile address (Regeneron 2026-10-30)
    { id: 'zip', q: /zip|postal code/i, not: /\+ ?4\b|plus ?4\b|zip ?4\b|extension/i },   // "Zip Code+4" is the 4-digit add-on, never the 5-digit ZIP (Oracle 2026-11-03)
    { id: 'location_full', q: /\bcity\b.{0,30}\b(state|province)\b.{0,40}\bcountry\b/i },   // "City/State/Province and Country where you are currently located" = the full location, never the state alone (a Workday employer 11-02, audit 11-09)
    { id: 'city', q: /^city\b|(current )?home city\b|city (in which|where) you (currently )?(reside|live)/i },
    { id: 'state', q: /^county\s*\/\s*state\b|^state\b|(current )?home state\b|province|(indicate|which|what) (is )?(the )?state\b|state (in which|where) you (currently )?(reside|live)|(which|what) (u\.?s\.? )?state\b[^?]{0,40}\b(reside|live)\b/i, not: /outside (of )?the (u\.?s\.?|united states)|non-?u\.?s|\bif not\b|other than the (u\.?s|united states)/i },
    { id: 'country', q: /^country\b|country (do|where|in which) you (currently )?(reside|live)|country of (residence|residency)|what country do you (currently )?(reside|live)/i, not: /citizenship|nationality/i },  // never bare /^united states/: it matches 'United States Minor Outlying Islands' first (HPE 2026-10-30)
    { id: 'location', q: /^(current )?location\b|city and state|where are you (currently )?(located|based)/i, not: /\(city,? (and )?state\)/i },   // "Location (City, State)" is city_state (JSA-144)
    { id: 'signature_date', q: /signature date|date signed|today'?s date/i, text: (() => { const d = new Date(); return String(d.getMonth() + 1).padStart(2, '0') + '/' + String(d.getDate()).padStart(2, '0') + '/' + d.getFullYear(); })() },   // CC-305 disability form (an employer 2026-10-31)
    { id: 'linkedin', q: /linkedin/i, not: /how did you|hear about|find (out )?about|learn about|referr/i },
    { id: 'website', q: /github|portfolio|website|personal (site|url)/i, not: /password/i },   // "Portfolio, Video, or Website Password" is not a URL box (NYT 2026-11-04)
    { id: 'middle_initial', q: /middle (initial|name)/i },
    { id: 'visa_details', q: /((provide|give|share) (the )?details? (on|of|about)|describe|explain) (your )?(current )?(visa|immigration)\b/i },   // Joey 2026-11-01 (a Workday employer): no expiry date
    { id: 'legal_dispute', q: /(civil )?legal (proceedings?|disputes?|actions?)|litigation|lawsuits?\b/i, not: /explain|describe|details/i },   // Joey 2026-11-01 (Arch Capital)
    { id: 'interviewed_before', q: /(previously|ever|already) (been )?interview(ed)? (at|with|for)\b/i },   // tracker has no interviews yet (2026-11-01, Arrowstreet) — update when one happens
    { id: 'good_standing', q: /(in|of|hold|have) good (academic )?standing|good academic standing|academic(ally)? (in )?good standing|good standing (with|at) (your|the) (academic )?(institution|school|university|college)/i, not: /probation|suspen|dismiss|disciplin/i },   // Joey 2026-11-03: 「我现在是 good standing。」 (VSP)
    { id: 'college_years_completed', q: /how many (years|semesters) of (college|university|undergraduate( study)?|higher education|school) (have you|did you|you have) (completed|finished)|(years|number of years) of (college|university) (completed|finished)/i },   // Joey 2026-11-03: 「现在是第五年大学，这是我 master 的第一年」 (VSP)
    { id: 'college_year_current', q: /(what|which) year (of|in) (college|university|school) are you( currently)?( in)?|current year (of|in) (college|university)|what is your current (college|university) year|(current )?class standing|year in school|\bwhat year (are you|of study are you) (currently )?(at |in )?(in )?(your )?(studies|study|program|degree)\b/i },   // "What year are you currently at in your studies:" (an employer Oracle 11-10, JSA-296)   // "What is your current class standing?" (Bosch 11-04) → Other when no graduate option   // same fact: 5th year
    { id: 'undergrad_year', q: /^are you an? (freshman|sophomore|junior|senior|rising (junior|senior))\b/i },   // he is a master's student (SouthState 2026-11-01)
    { id: 'noncompete_detail', q: /(describe|detail|list|explain) any (non[- ]?compete|restrictive)|currently employed.{0,40}(detail|describe|list).{0,60}non[- ]?compete|non[- ]?compete.{0,80}(if you are currently employed|current employer)/i, not: /\b(yes|no)\b.{0,5}$|^(are|is|do|does|have|has|will|would)\b/i },   // "Are you subject to a non-compete … with a previous or current employer?" is the yes/no question (DeepSeek case, Erie 11-04)   // Joey 2026-10-26 (no non-compete) + not employed (a Workday employer 2026-11-01)
    { id: 'know_employee', q: /do you know (anyone|someone|any (current )?employees?)\b.{0,40}\b(work|employ)/i },   // Joey 2026-11-01: default No unless he says otherwise
    { id: 'debarred', q: /debarred|excluded (or sanctioned )?(from|by)\b|sanctioned by\b/i },   // Joey 2026-11-01 (Excellus)
    { id: 'industry_investor', q: /owner or investor|investor in (an|any) (entity|company)|\b(own|owner|ownership|invest|investor|investment)\b.{0,40}\b(winery|wineries|liquor|alcohol|brewer|brewery|distill\w*|spirits)\b/i },   // Joey 2026-11-01 (a Workday employer, alcohol industry)
    { id: 'industry_side_role', q: /consultant, endorser|influencer, advisor|advisor,? or mentor in|\b(consultant|endorser|influencer|advisor|mentor)\b.{0,40}\b(in|for|to) (an?|any|the) (\w+ ){0,2}(industry|entity|company)\b/i },   // outside-business No (2026-10-26)
    { id: 'other_jobs', q: /additional jobs? (you )?(plan|intend) to (continue|keep)|other (employment|jobs?) you (plan|intend) to (continue|keep)|(continue|keep) (any )?(additional|other) jobs?/i },
    { id: 'conflict_interest', q: /(aware of|have|are there) any (potential |actual )?conflicts? of interest/i },   // follows from the three above (Constellation 2026-11-01)
    { id: 'eligibility_3way', q: /describ\w* your employment eligibility|option describing your (work|employment) (eligibility|authori[sz]ation)|^employment eligibility\b/i },   // Joey 2026-11-01 (Copart): this three-way wording → sponsorship
    { id: 'language_pref', q: /^\W*(preferred language|language preference)\W*$|^language preference\b|\bpreferred language\b|\blanguage (of|for) (communication|correspondence)\b/i, not: /proficien|fluen|speak|level|other than english/i },   // "Language Preference" (English / French Canadian / Spanish, an employer SF 11-10, JSA-295)
    { id: 'language_level', q: /\benglish (language )?proficiency|^(verbal|written)( and written)? communication( level)?$/i },   // Workday languages all Fluent (Joey 2026-10-28)
    { id: 'contact_employer_cond', q: /\bif (you are |you're )?((currently|presently) )?(employed|working)\b[^?]*\bcontact\b[^?]*\b(employer|supervisor|manager)s?\b|\bare you (currently |presently )?(employed|working)\b[^?]*\?\s*if so\b[^?]*\bcontact\b[^?]*\b(employer|supervisor|manager)s?\b|\b(may|can) we contact (your )?(current|present) (employer|supervisor|manager)s?\b[^?]*\bif (you are |you're )?((currently|presently) )?(employed|working)/i },   // JSA-409 (learn 2ed24953): "If you are currently employed, may we contact your employer?" — he has no current job → N/A (answers.contact_employer_cond: text + pick); an option list without an N/A option asks. The unconditional "May we contact your current employer?" stays contact_employer (Joey 2026-11-01)
    { id: 'contact_employer', q: /\b(may|can) we contact (your )?(current|present|previous|former)? ?(employer|supervisor|manager)s?\b/i },   // Joey 2026-11-01 (EMC): Yes
    { id: 'interview_travel', q: /\b(require|need)\b.{0,30}\btravel (assistance|reimbursement|support)\b.{0,60}\binterview|\binterview\b.{0,80}\b(require|need)\b.{0,30}\btravel (assistance|reimbursement|support)\b/i },   // Joey 2026-11-01 (a Workday employer): No
    { id: 'leave_reason', q: /reasons?( ?\(s\))? for leaving|why (did|do) you (want to )?leave|why are you leaving/i },   // never the employer's name (an employer 11-04 got "University of Chicago"; audit 11-08, JSA-246): answers.leave_reason, none → asked
    { id: 'recent_employer', q: /most recent employer|(current|present) ?(\/|or) ?(most recent|last|previous|former) employer|\blast employer\b/i, not: /reasons?( ?\(s\))? for leaving|\b(may|can) we contact\b|non[- ]?compete|non[- ]?solicit|confidentiality|obligations?\b|agreements?\b|restrict|^\s*(did|does|do|has|have|is|was|were|are|will|would|can|could)\b|please let\b/i },   // Joey 2026-11-10 (JSA-288): "most recent employer" = Hyde Park; the current company alone stays UChicago
    { id: 'employer', q: /current employer|current company/i, not: /reasons?( ?\(s\))? for leaving|\b(may|can) we contact\b|non[- ]?compete|non[- ]?solicit|confidentiality|obligations?\b|agreements?\b|restrict/i },   // "With respect to any previous or current employer, are you subject to … non-compete …" is the restriction question (Erie SF 11-04)
    { id: 'lives_outside_us', q: /live outside (of )?the (u\.?s\.?|united states)/i },
    // ---- education
    { id: 'education_list', q: /(represent|list|write (in|out)|enter|provide|describe|include)\b[^?]{0,60}\b(completed|in[- ]progress|all)\b[^?]{0,30}\b(university |college )?degrees\b|(list|enter|provide|include)\b[^?]{0,20}\b(all |each )?(the )?(colleges?|universities|colleges? (or|and|\/) universities|post-?secondary (schools|institutions))\b[^?]{0,40}\battended\b|\b(completed and in[- ]progress|in[- ]progress and completed)\b[^?]{0,30}degrees|\beducation(al)? (history|background)\b[^?]{0,40}\b(list|write|describe|below|above)/i },   // HRT 11-05 (JSA-218): DeepSeek wrote "B.S." / "M.S. Data Science" / high school "not provided" — the profile's entries instead
    { id: 'hs_name', q: /(high|secondary) school[^?]{0,25}\bname\b|\bname of (your |the )?(high|secondary) school|(which|what) (high|secondary) school|^\W*(high|secondary) school\W*$/i },   // the high school's name (a bare "High School" box, a Greenhouse employer, JSA-410) (profile high_school, JSA-218)
    { id: 'school_level', q: /^(?!.*(highest|completed|attained|finished)).*(level of (schooling|education|study)|year in school|current (academic )?(year|level) of study)/i },
    // ---- education
    { id: 'school', not: /\b(major|minor|concentration)\s*:?\s*$|\bschool (city|state|location|address|country|zip|year|gpa)\b|\bgpa\b|high school/i, q: /^(school|university|college|institution)( name)?\b|which (college|university|school) (did|do) you attend|collegiate institution|(school|university|college|institution) (do |did |are )?you (currently )?attend|^\W*(what|which|name (of )?the) (school|university|college|institution)\b[^?]{0,30}\b(are|do) you (currently )?(enrolled|registered|studying|attending)\b|^\W*(please (enter|provide|list|state) )?(the )?(name of the )?(school|university|college|institution)\b[^?.]{0,20}\b(where |that |which )?you (are|were)? ?(currently )?(enrolled|registered|studying|attending|attend)\b|^\W*current (school|university|college|institution)( or (school|university|college|institution))? (attending|enrolled)\b|^\W*(enter|provide|list) your (college|university|school)(\s*\/\s*(college|university|school))?\W*$|\b(college|university|school)(\s*\/\s*(college|university|school))? (are|do) (you )?(currently )?(enrolled|attend|attending)\b/i },   // "Name of the school you are currently enrolled in", "Please enter the institution where you are currently studying.", "Current university or college attending:" (JSA-296 cases)   // "What university are you currently enrolled with?" (an employer Oracle 11-10, JSA-296)
    { id: 'degree', not: /mm\s*\/\s*yyyy/i, q: /^degree\b|degree (type|level)|degree level|(what|which) degree are you (currently )?(pursuing|working towards?|seeking|enrolled in)|(current )?degree (that )?(you are|you're) (currently )?(obtaining|pursuing|earning|working (on|towards?))|\bdegree program (that )?(you are|you're) (currently )?(obtaining|pursuing|earning|enrolled in|working (on|towards?))/i },   // Hermeus 10-31 (JSA-075)
    // no data-science option on the tenant -> Computer Science, then Information Systems, before Statistics (Joey 2026-10-28)
    { id: 'discipline', q: /discipline|field of study|\bmajors?\b|area of study|(course|program|concentration) of study|^(academic )?concentration\b|what are you (currently )?studying|^\W*minors?(\s*\(s\))?\W*$|\bminors? (field|subject|area|concentration|of study)\b/i, not: /\b(school|university|college|institution) (are|do|did) you\b|(?<!under)graduat|\bdegree and\b|\bgpa\b|grade point/i },   // "…GPA (cumulative, not major specific)" is the GPA, not the major (Brattle 10-31 got "Other", replay JSA-188)   // "What is your area of study?" (a Lever employer 2026-11-02, JSA-075); "graduate from your course of study" = grad date
    // Greenhouse education block dates (labels like "Start date month", "End date year"; helpers prefix bare Month/Year with the Start/End legend)
    { id: 'start_month', q: /start.{0,20}month|month.{0,12}start/i },
    { id: 'start_year', q: /start.{0,20}year|year.{0,12}start/i },
    { id: 'end_month', q: /(end|expected end).{0,20}month|month.{0,12}end/i },
    { id: 'end_year', q: /(end|expected end).{0,20}year|year.{0,12}end/i },
    { id: 'ft_start', q: /earliest[^?]{0,80}\b(begin|start|eligible)[^?]{0,40}full[- ]?time|full[- ]?time[^?]{0,40}\b(start|begin)(ning)? date|when (can|could|would|are) you (be )?(able to |available to )?(begin|start) full[- ]?time/i },   // "…earliest you are eligible to begin full-time employment?" got February 2027 from grad_date (HRT 11-05, JSA-218): answers.ft_start
    { id: 'grad_date', not: /high school|secondary school|mm\s*\/\s*yyyy|sponsor|visa|full[- ]?time/i, q: /when (will|do) you (complete|finish) your (degree|program|studies)|(expected |anticipated )?graduation( date| year| month| term| semester)?\b|when (will|do) you graduate|when (are|will) you (be )?expected to graduate|when do you expect to graduate|(month and year|when) (are|will) you (be )?expected to graduate|are you expected to graduate/i },   // "When do you expect to graduate?" (Hermeus 10-31, JSA-075)   // December 2027: never "Summer 2027" (an Ashby employer 2026-10-31)
    { id: 'education_level_now', q: /^\W*(what is )?your current (education(al)? )?level( of (education|study|schooling))?\W*$/i },   // JSA-410 (C9, a Greenhouse employer): the level he is at now (M.S. student) → "Master's" (answers.education_level_now); highest_ed stays the completed one
    { id: 'highest_ed', q: /highest (completed |attained )?level of (education|schooling)( (completed|attained))?\b|highest (level of )?education (completed|attained)|highest (level of )?(completed|attained) (education|degree)\b|highest (level of )?(degree|education)( of education)?( (you have )?(completed|earned|attained))?\??$/i },   // "What is your highest degree of education?" (Workable Thorlabs 2026-11-03)
    { id: 'degree_progress', q: /(in the process of|pursuing|working toward).{0,60}(or (have )?(recently )?completed)?.{0,40}\b(bachelor|master)'?s?\b.{0,30}\bor\b.{0,10}\b(master|bachelor)'?s?\b/i, not: /in business( administration)? or (a )?related/i },   // "Are you currently in the process of or have recently completed a Bachelor's Degree or Masters Degree?" (an employer 11-04): M.S. in progress + B.A. 05/2026 → Yes
    { id: 'enrolled', not: /in business( administration)? or (a )?related|\bbusiness (administration )?(degree|program|major)\b[^?]{0,30}\bor (a )?related\b|\b(student|enrollment) status\b|^\W*(what|which|where|when|how|name|list|please (list|name|enter|provide|specify))\b/i,   // a wh-question asks WHICH school / program, not yes / no (an employer 11-10, JSA-296)
      q: /currently enrolled|current(ly)? (a )?student|enrolled in (a|an) .*program/i },
    { id: 'returning', q: /returning to school|return to (school|your studies)|remaining (term|semester|quarter)/i },
    // the CURRENT GPA = the M.S. in progress, which has none yet → answers.gpa_current (Joey 2026-11-05 Erie, a Workday employer 10-30); undergrad / bachelor's GPA stays `gpa`
    // inferred from the facts, never asked (Joey 2026-11-05 「这种问题你可以通过我的资料推理出来，就不需要问我」):
    // "Do you have a 3.4 GPA or higher?" → compare with the GPA on file; "subject to any conditions … tied to your visa status?" → Yes (F-1)
    { id: 'gpa_threshold', q: /^(?=.*(\bgpa\b|grade point average))(?=.*\b[0-4]\.\d{1,2}\b)(?=.*(or (higher|above|better|greater|more)|at least|minimum( of)?|\bover\b|\babove\b|\bexceed|\bbelow\b|less than|\bunder\b|\b[0-4]\.\d{1,2}\s*\+))/i },
    { id: 'visa_conditions', q: /\b(subject to|bound by|have) (any )?(conditions?|restrictions?|limitations?)\b[^?]{0,80}\b(visa|immigration|work authori[sz]ation) status\b|\b(visa|immigration) status (impose|place|carry|come with|put)s? (any )?(work |employment )?(conditions?|restrictions?|limitations?)\b|\b(conditions?|restrictions?|limitations?)\b[^?]{0,30}\b(on|apply to|attached to|tied to) (your )?(current )?(authori[sz]ation to work|work authori[sz]ation|(visa|immigration) status)\b|\b(conditions?|restrictions?)\b[^?]{0,80}\brequir\w* you to (depart|leave)\b|\b(subject to|have) (an? |the )?(two[- ]year )?home[- ](country )?(physical )?residen(cy|ce) requirement|\b212 ?\(e\)/i },
    { id: 'gpa_current', q: /^(?!.*(under ?grad|bachelor|high school)).*(\b(current|present)\b[^?]{0,40}(\bgpa\b|grade point average)|(\bgpa\b|grade point average)[^?]{0,40}\b(current|present) (program|degree|course of study|program of study|graduate program)\b)/i },   // + "GPA in your current program of study" (JSA-203 DeepSeek case)
    { id: 'gpa', q: /\bgpa\b|grade point average/i, not: /are you (currently )?enrolled\b|^(?!.*(under ?grad|bachelor|high school)).*(\b(current|present)\b[^?]{0,40}(\bgpa\b|grade point average)|(\bgpa\b|grade point average)[^?]{0,40}\b(current|present) (program|degree|course of study|program of study|graduate program)\b)/i },
    // ---- work authorization (order matters: specific before general)
    { id: 'visa_expiry', q: /^(?=.*\b(visa|status|authori[sz]ation|work permit|ead|i-?20)\b)(?=.*\bexpir(e|es|ed|ation|y)\b)/i, not: /permanent resident|^\s*(is|are|do|does|will|would|has|have|can)\b(?![^?]*\bwhen\b)/i },   // a yes/no "Is your authorization temporary or subject to an expiration?" stays a yes/no; a multi-part PR-country question stays with the user   // "If you have a current work authorization/status, when does it expire?" got "Yes" (Akuna 11-05, JSA-218); "visa status and expiration" got only "F-1" (a Greenhouse employer)
    { id: 'auth_today', q: /authori[sz](ed|ation) to work.{0,120}(as of today|effective (as of|now|today)|as of the date you (complete|submit)|currently in effect)|(as of today|as of the date you (complete|submit)).{0,120}authori[sz](ed|ation) to work/i },
    { id: 'immigration_status', q: /(current|present) (u\.?s\.? )?(employment )?(immigration|visa) status|^immigration status|what is your (current )?(u\.?s\.? )?(immigration|visa) status|^(?!\s*(are|do|does|will|would|is|have|has|can|could)\s+you\b)(?!.*\b(sponsor\w*|requir\w*)\b).*\bvisa (type|status|classification)\b|^(?!\s*(are|do|does|will|would|is|have|has|can|could)\s+you\b)(?!.*\b(sponsor\w*|requir\w*|how (long|many)|number of|petition)\b).*\bimmigration status\b/i },   // any fill-in that asks the immigration status = F-1 ("If no, please provide your immigration status in the U.S.", Vanguard 11-10 got "CPT"; Joey 2026-11-10, JSA-287)   // "provide your visa type / status / classification" = the visa (F-1), not the work authorization (CPT): replay JSA-188 found 6 such boxes answered "CPT" (a Greenhouse employer, a Greenhouse employer, Sysk 10-28…10-31)   // no plain F-1 → F-1 CPT, never F-1 OPT (RBC 2026-11-01)   // plain F-1 over "F-1 CPT" (handoff 10-28b)
    { id: 'auth_kind', not: /file a petition|petition or application|on your behalf|number of (months|years|days)|how (many|long)\b|\bif not,? (please )?type\b|\btype ["“']?n\/?a\b/i,   // "…indicate the number of months you have remaining" asks a number, not the kind (Goldman 11-05); "…if not type N/A": type is the verb (an employer referral-name box 11-05 got "CPT")
      q: /^(?!.*sponsor).*(if (yes|so)\b[^?]{0,60}\b(kind|type|visa|status|category)\b|what (kind|type|category)( of)? .{0,30}(authori[sz]ation|visa|status)|(kind|type) of (work )?(authori[sz]ation|visa|status)|visa (type|status)\b(?!.*(sponsor|require)))/i },   // "immigration status" is never the work-authorization kind (F-1, not CPT: JSA-287)
    { id: 'spons_countries', not: /^\s*(are|is|do|does|did|will|would|can|could|have|has)\s+you\b/i, q: /^(?=.*\b(indicate|list|specify|name|enter|provide|separate|which|what)\b)(?=.*((locations?|countr(y|ies))\b.{0,160}\bsponsor|\bsponsor\w*\b.{0,160}\b(locations|countries|(which|what) (location|country))\b))/i },   // a text box listing the countries that need sponsorship (HPE Workday 11-10, JSA-279): needs it → "United States", else "N/A"; a Yes / No question stays spons_now / spons_future
    { id: 'spons_now', q: /^(?!.*\bsponsor\w* (relocation|housing|travel))(?!.*\b(future|ever)\b)(?!.*(after graduat|at any time|any time after|\blater\b|eventually|going forward|upon graduation))(?:.*sponsorship.*\b(now|currently|presently|at present|at this time|as of today)\b|.*\b(now|currently|presently|at present|at this time|as of today)\b.{0,40}\bsponsorship|.*\bimmediately\b.{0,40}\bsponsor|.*require.*sponsorship.*to (begin|start) (the|this) internship|.*\bsponsor\w*\b.{0,60}\b(for|during) (this|the) internship\b|.*\bsponsor\w*\b.{0,60}\bto (begin|start) (working|work|employment)\b)/i },   // \"sponsor a visa for this internship?\" / \"sponsorship to begin working for a Greenhouse employer?\" = now: CPT → No (audit 11-08, JSA-246) // JSA-407: + presently / at present / as of today
    { id: 'degree_start_mmyyyy', q: /^(?=.*mm\s*\/\s*yyyy)(?=.*((begin|began|start(ed)?).{0,40}(degree|program)|(degree|program).{0,40}(start|begin))).*/i },   // "When did you begin your current degree program? … MM/YYYY" (a Lever employer 11-04, JSA-150)
    { id: 'degree_end_mmyyyy', q: /^(?=.*mm\s*\/\s*yyyy)(?=.*(complet|finish|graduat|end date)).*/i },
    { id: 'sponsorship_type', q: /(what|which) (type|kind) of (visa |work |immigration )?sponsorship|(?<!\bany )type of (visa )?sponsorship|sponsorship type/i },   // "Will you require ANY type of sponsorship now or in the future?" is the yes/no question (Newell SF 11-05, type AD)   // "If yes, what type of sponsorship?" → the profile's explanation text, never "Yes" (a Lever employer / Belvedere 11-04, JSA-150)
    { id: 'hs_grad_year', not: /^(did|have) you graduated?\b/i, q: /high school.{0,30}graduat|graduat\w*.{0,30}high school|year of high school|high school (diploma|completion).{0,20}(year|date)/i },   // confirmed 2026-10-28 (candidate-profile)
    { id: 'spons_future', not: /^(?!\s*(are|is|do|does|did|will|would|can|could|have|has)\s+you\b)(?=.*\b(indicate|list|specify|name|enter|provide|separate|which|what)\b)(?=.*((locations?|countr(y|ies))\b.{0,160}\bsponsor|\bsponsor\w*\b.{0,160}\b(locations|countries|(which|what) (location|country))\b))|\bsponsor\w* (for )?(relocation|housing|travel)|(what|which) (type|kind)|(?<!\bany )type of (visa|sponsorship)|sponsorship (type|category)|(which|what) sponsorship category/i, q: /sponsor|file a petition .{0,80}(employment|immigration)|employment[- ]based (status|visa|immigration)/i },   // "…require <Co> to file a petition … for employment-based status" (Workable an employer 2026-11-03)
    { id: 'on_opt', not: /legally (authori[sz]ed|able) to work|(hold|obtain) valid (u\.?s\.? )?work authori[sz]ation|can (you )?(obtain|commence)|e\.g\.,?[^)]{0,80}\bopt\b/i, q: { test: l => /\b(currently|now|presently|current|active)\b.{0,60}\b(opt|optional practical training)\b|\bon (stem )?opt\b|\b(participating in|based on)\b.{0,20}\b(opt|optional practical training)\b/i.test(noExamples(l)) } },   // JSA-175: only a question that asks whether he is ON OPT — OPT inside an example group / "e.g." clause does not count   // OPT named only as an example of authorization is not "are you on OPT" (Goldman 11-05)   // F-1, internship on CPT, not on OPT (a Workday employer 2026-10-30)
    { id: 'any_employer', q: /\b(any|all) ((u\.?\s?s\.?|united states|american)\s*)?employers?\b|without (any )?restriction|unrestricted|\bpermanently (authori[sz]ed|eligible|allowed|permitted)\b/i },   // JSA-291: "permanently authorized" (DeepSeek case 11-10) = No   // JSA-281: "authorized to work for any U.S Employer?" (a Greenhouse employer 11-09) went to authorized → Yes   // "authorized to work for ALL employers" = any employer → No (an employer 11-05, JSA-218)
    { id: 'work_permit', q: /(valid|current|hold|have|possess)\b.{0,30}\bwork permit/i },   // Joey 2026-10-30 (HPE): Yes; 'any employer' stays No
    { id: 'citizen_pr', q: /^are you an? (u\.?s\.? )?(citizen|national)( or (a )?(lawful )?permanent resident)?\??$|^are you a (u\.?s\.? )?(lawful )?permanent resident\??$|^(?=.*\bcitizen\b)(?=.*\bpermanent resident\b)(?=.*\b(refugee|asylee|asylum)\b)(?!.*\b(sponsor|authori[sz]ed|eligible to work)\b)/i },   // "Are you one of the following: citizen of the United States, lawful permanent resident, refugee, or asylee?" (Erie SF 11-04) = the protected-individual question: F-1 → No   // answer from profile work_auth (2026-11-01)
    { id: 'authorized', q: { test: l => !/\b(opt|optional practical training)\b/i.test(noExamples(l)) && AUTH_Q.test(l) } },   // JSA-175: OPT named only as an example of authorization ("(e.g., U.S. citizen, permanent resident, F-1 OPT)", Goldman 11-05) is still the authorization question → Yes; "authorized to work on OPT?" stays out
    // ---- availability & logistics
    { id: 'disability_cc305', q: /^please check one of the boxes below/i },   // OFCCP CC-305 on Self Identify (a Workday employer 2026-10-30); candidate-profile EEO: no disability
    { id: 'accommodation_need', q: /\b(require|need|request)\w*\b[^?.]{0,60}\b(adjustments?|accommodations?)\b/i, not: /housing|lodging|hotel|temporary (housing|living)|\bvisa\b.{0,40}\bsponsor/i, when: l => /\b(do|will|would|did) you\b[^?]*\b(require|need|request)/i.test(questionPart(l)) },   // JSA-408 (learn d083be64): "Do you require reasonable adjustments / accommodations …?" = a disability / process accommodation: his fact in answers.accommodation_need (no → No); before onsite / relocate, whose words sit in the example list
    { id: 'essential_functions', q: /essential functions.{0,80}(with or without|accommodation)/i },   // Joey 2026-10-30 (Hitachi, iMessage yes)
    { id: 'conviction', q: CONVICT_Q },
    { id: 'applied_before', q: APPLIED_Q, not: /\b(worked|been employed|employed by|interned|interviewed|been (an? )?(employee|intern|contractor))\b|\breferr/i },   // JSA-281 (a Greenhouse employer 11-10): state, from the tracker — never a saved fixed answer   // JSA-281: "Have you ever been convicted of a felony …?" (a Workday employer 11-10, 18 USC 1033) — his fact answers.conviction (Joey 2026-11-10); background_drug had answered Yes from "criminal background check" in the preamble
    { id: 'background_drug', q: /background (check|screen|investigation)|drug (screen|test)/i },   // background Yes (2026-10-28); + drug screen Yes (Joey 2026-11-01, a Workday employer)
    { id: 'license_state_class', q: /state and class.{0,30}licen[cs]e|licen[cs]e.{0,30}state and class/i },   // Joey 2026-11-01 (Central Hudson)
    { id: 'driver_license', q: /driver'?s?'? licen[cs]e|driving licen[cs]e/i },   // Joey 2026-11-01 (a Workday employer): valid U.S. driver license = Yes
    { id: 'work_arrangement', q: /preferred (work|working) (arrangement|model|mode|style|environment)|(work|working) (arrangement|model|mode) (do you|would you) prefer/i },   // single pick: Onsite (Joey 2026-11-01, Zekelman); multi-select stays Onsite + Hybrid
    { id: 'other_name', q: /(employed|worked|attended school|known|gone) (by|under) (any |an? )?(other|another|different|former|previous|maiden) names?|(other|another|former|previous|maiden) names? (you (have|'ve) )?(used|been (known|employed))|\b(used?|go by) (any |an? )?(other|another|different|former|previous|maiden) names?/i, yes: false },   // never worked or studied under another name (Joey 2026-11-01, KBR); "Have you even been employed under any other name?" (Hilb 11-04)
    { id: 'insurance_license', q: /(insurance|producer|real[- ]estate|securities|finra|series \d+) licen[cs]e/i, yes: false },   // no licenses of any kind (candidate-profile; a Workday employer 11-01, Hilb 11-04)
    { id: 'bonus', q: /bonus (expectation|target|range)s?|expected bonus|bonus.{0,20}expect/i },   // the lowest band (Joey 2026-11-04 a Workday employer, like the lowest salary range)
    { id: 'work_period', q: /available to work (during|for|in) the (work|internship|program|co-?op) (period|dates|timeframe)|available (for|during) the (dates|period|timeframe) (specified|listed|stated|in the)/i, yes: true },   // batches hold only roles whose JD period is the target summer (gate + prefilter START flag; Intuitive SmartRecruiters 11-04)
    { id: 'citizenship_country', q: /(hold|have) citizenship or permanent residen.{0,80}(following|these|listed|any of)|countr(y|ies) of citizenship|citizenship.{0,30}(which|what) countr|which countr.{0,40}citizen/i },   // a country list for export control (an employer 11-04); the answer = config citizenship_country
    { id: 'intern_dates_mmyy', q: /start (date )?(and|to|[-–—]) ?end dates?|start date\s*[-–—]\s*end date/i },   // "anticipated start and end dates … (MM/YY)" (Bosch 11-04); answer from config intern_dates_mmyy
    { id: 'areas_of_interest', q: /area\(?s?\)? of interest|(what|which) (areas?|fields?|functions?) (are you|would you be) (interested|seeking|looking)/i },   // target roles (candidate-profile) — Bosch 11-04
    { id: 'id_if_worked_here', not: new RegExp('\\b(' + EMP + ')\\b', 'i'), q: /^if you (currently,? )?(or in the past,? )?(have )?(worked|been employed) (for|at|by)\b.{0,80}(provide|enter|list)/i, text: 'N/A' },   // never worked there (Bosch GID 11-04)
    { id: 'enrollment_status', q: /(best describes|what is) your (current )?enrollment status|current(ly)? enrollment status|^\W*(current )?(enrollment|student) status\W*$|\byour (current )?(enrollment|student) status\b/i },   // "Enrollment Status", "Please select your current student status:" (JSA-296 cases)   // config: Master's program (an employer 11-04)
    { id: 'employed_by_other', not: new RegExp('\\b(' + EMP + ')\\b', 'i'), q: /(have you )?been employed by [\w&.,' -]{2,60} in the (last|past) \d+ (months|years)/i, yes: false },   // only the resume companies (Joey 2026-10-30); "employed by SelectQuote in the last 12 months" (Spring Venture 11-04)
    { id: 'transportation', q: /reliable (means of )?transportation|(own|have) (a )?(reliable )?(car|vehicle|transportation)\b(?!.*licen)/i },   // config transportation (Joey 2026-11-04: No)
    { id: 'grad_pursuit', q: /\bpursu(ing|it of)\b (a |an )?(graduate|master'?s?|post-?graduate) (degree|program|studies)\b|\b(enrolled in|working towards?) (a |an )?(graduate|master'?s?) (degree|program)\b/i, not: /^(what|which|when|where|how|list|name|please (list|describe|provide|enter))\b|\b(plan|planning|intend|intending|considering|future|after (graduation|you graduate|completing))\b|\b(ph\.?d|doctor)|\b(in|of) business\b|or (a )?related field/i, yes: (P.education || []).some(e => e.current && /^(master|graduate)/i.test(e.level || '')) || undefined },   // M.S. in progress (profile education, current) — "Are you in pursuit of a Bachelor's degree … or pursuing a graduate degree?" (Erie SF 11-04)
    { id: 'office_software', q: /\b(working knowledge|knowledge|proficien\w*|experience|familiar\w*|comfortable|skilled)\b.{0,30}\b(word processing|spreadsheets?|presentation software|microsoft (office|word|excel|powerpoint)|ms office|office (suite|software|applications)|google (workspace|docs|sheets)|excel,? (and )?powerpoint)\b/i, not: /how (many|much|long)|\byears?\b|\brate\b|\blevel\b|describe|explain|\blist\b/i, yes: true },   // candidate-profile skills: Excel (Pivot, XLOOKUP), PowerPoint, Word (Erie SF 11-04)
    { id: 'agent_roles', q: /(considered for|interest(ed)? in|like to (be|work|become)).{0,80}\b(independent (\w+ )?agent|insurance agent|sales producer|agency (owner|principal))\b/i, yes: false },   // target roles are data / product / AI engineering (candidate-profile) — never insurance-agency sales roles (Erie SF 11-04)
    { id: 'nda', not: /other restriction|other than (a )?non-?compet/i, q: /agreement that contains a confidentiality|confidentiality (agreement|provision)|non-?disclosure agreement|\bnda\b/i, yes: false },   // no NDA / confidentiality agreement binding him (Joey, an employer note 2026-11-0x; an employer 11-04)
    { id: 'contractor_here', q: /(current or former|ever been an?|previously (been )?an?) (contractor|temporary employee|temp|consultant)\b|\b(have you|did you|do you)( ever| currently| previously)? work(ed)?\b.{0,80}\bas an? (third[- ]party )?(contractor|consultant|temp|temporary employee|vendor)\b/i, not: new RegExp('\\b(' + EMP + ')\\b', 'i'), yes: false },   // never a contractor / temp / consultant for a hiring company (an employer 11-04)
    { id: 'hs_diploma', q: /(have|hold|completed|earned|obtained)\b.{0,40}(high school (diploma|degree)|\bged\b|secondary school (diploma|certificate))|high school diploma or (equivalent|ged)|(did|have) you graduated? from high school/i, not: /\b(year|when|date|name|which|where)\b/i, yes: true },   // diploma 2022 (candidate-profile); an employer 11-04
    { id: 'applied_here_before', q: /have you (ever )?(previously )?applied (for any position )?(with|to|at|for|in) /i, not: new RegExp('\\b(' + EMP + ')\\b', 'i') },   // answered from the tracker by the runner (JSA-160); unknown here
    { id: 'hired_here_before', q: /(have you|were you) ever (been )?hired (at|by) /i, not: new RegExp('\\b(' + EMP + ')\\b', 'i'), yes: false },   // never worked anywhere but his resume employers (Joey 2026-10-30)
    { id: 'proof_of_age', q: /proof of age|show (proof|evidence) (that you are|of being) (at least )?1[68]/i, yes: true },   // passport (candidate-profile identity documents); an employer 11-04
    { id: 'business_degree', q: /(pursuing|enrolled in|studying|completed|have) .{0,50}degree( program)? in business( administration)? or (a )?related field|\b(pursuing|enrolled in|studying|completed|have) (a |an )?business (administration )?(degree|program|major)\b[^?]{0,30}\bor (a )?related\b|degree( program)? in business or (a )?related/i, yes: false },   // Joey 2026-11-04: Applied Data Science is not business / related (an employer)
    { id: 'recruiter_contact', q: /(were|have) you (been )?(contacted|approached|referred) by (an? |the )?.{0,40}recruiter/i, yes: false },   // every application so far is his own (tracker referral_status Cold); SPX 11-04
    { id: 'signature', q: /typed signature|electronic signature|e-?signature|digital signature|sign(ature)? .{0,20}(full|legal) name|^signature( of (the )?applicant)?$|^applicant'?s? signature$/i, not: /\bdate\b|\bagree that my (electronic |e-?)?signature\b|\bsignature (below )?(has|will have|carries) the same\b|\b(signature|response)\b[^.?!]{0,80}\bcertif(y|ies) that\b/i },   // "My response … and my electronic signature below certifies that I have read …" is the certify box, not the signature (an employer SF 11-10, JSA-295)   // "Signature of Applicant" (Erie SF 11-04)   // config signature (full name); SPX / an employer 11-04
    { id: 'license', q: /(healthcare|medical|nursing|pharmac|professional) .{0,40}\b(active )?licen[cs]e|licen[cs]ed (healthcare|medical) professional/i },   // no licenses or certifications (candidate-profile; Regeneron 2026-10-30)
    { id: 'misconduct', q: /(investigation|inquiry).{0,80}(misconduct|harass)|(misconduct|harass).{0,80}(investigation|inquiry)/i },   // Joey 2026-10-30 (FHLB)
    { id: 'ai_review', q: /automated (assessment|employment decision) tool|\baedt\b|reviewed by (a )?recruiter only|\b(ai|artificial intelligence)\b.{0,60}(screen|review|assess)/i },   // Standard answers: AI screening = Opt In (a Workday employer 2026-10-30)
    { id: 'recent_industry', q: /industry.{0,60}(most recent|current|latest|last) (work |job )?experience|(most recent|current|latest) (work |job )?experience.{0,60}industry/i },   // industry of the most recent job in the profile (a Workday employer 2026-10-30)
    { id: 'yoe_meets', q: /years? of (\w+ ){0,3}experience.{0,80}\b(required|requirements?|listed|stated|specified|outlined|posted|needed)\b|\b(required|minimum|requisite|necessary)\b.{0,30}\byears? of (\w+ ){0,3}experience\b|\bexperience requirements?\b.{0,40}\b(position|role|job)\b/i, not: /^how many|how many years|\bwith (python|sql|r|java|tableau|excel)\b|\b(list|enter|state|specify) (the |your )?(number|years)/i, jd: true },   // the JD's own requirement: none → Yes, some → Joey (JSA-105, VSP 2026-11-03)
    { id: 'resume_employer', not: /referr?ed|referral|\bid\b|identification|employee (number|no\.?)|\bgid\b/i, q: new RegExp('^(?=.*\\b(' + EMP + ')\\b)(?=.*\\b(work|worked|employ\\w*|intern\\w*)\\b)', 'i') },   // Joey 2026-10-30: employers on his resume = Yes, every other company = No
    { id: 'prior_employer', q: new RegExp('^(?!.*(government|federal|public|agency|competitor|customer|supplier|' + EMP_WORDS + ')).*(have you|are you|did you).{0,40}(previously|currently|ever|formerly).{0,40}(work|employ|contract|intern)\\w*.{0,40}\\b(for|at|with)\\b', 'i') },   // only the profile's own employers count as Yes (a Workday employer 2026-10-30)
    { id: 'python_r', q: /(experience|proficien).{0,60}\b(python|R)\b|\b(python|R)\b.{0,40}(experience|data analysis)/ },
    { id: 'dob_minor', q: /^(?=.*(date of birth|birth ?date|\bdob\b|\bbirthday\b))(?=.*(\bminors?\b|\bunder (the age of )?(1[6-9]|21)\b|younger than (1[6-9]|21)\b|below (the age of )?(1[6-9]|21)\b))/i },   // "For individuals under 18 … please provide your date of birth. Otherwise, you may skip" → stays empty (an employer 11-05 got "No" from age18)
    { id: 'age18', q: /under (the age of )?(1[6-9]|21)\b|younger than (1[6-9]|21)\b|\b(1[6-9]|21)\+|\b(1[6-9]|21) years|age of (1[6-9]|21)\b|at least (1[6-9]|21)\b/i, yesIf: /at least|over|older|\+|years of age or older|are you (1[6-9]|21)\b/i, under: /\bunder (the age of )?(1[6-9]|21)\b|younger than (1[6-9]|21)\b|below (the age of )?(1[6-9]|21)\b/i },   // 16 / 18 / 19 / 21: Yes (Joey 2026-11-01, BCBS NE: at least 19)
    { id: 'full_time_summer', q: /full[- ]time.*(summer|june|12[- ]week)|12[- ]week|available to work full[- ]time/i },
    { id: 'avail_season', q: /when (are|will) you (be )?available to (start|begin)( an internship)?|available to start an internship|desired start date|what date (are|will) you (be )?available to (start|begin)|available start date/i },
    { id: 'hours', q: /hours per week|hours a week|weekly hours|hours .{0,40}\bper week|hours .{0,40}\beach week/i },   // "How many hours would you be available to work per week?" (Bosch 11-04)
    { id: 'overtime', q: /\bovertime\b|work (beyond|past) (normal|regular|scheduled) hours/i },   // Joey 2026-11-02 (Zurn): 「Just evenings」 — never weekends
    { id: 'start_date', q: /earliest (\w+ ){0,3}start|when can you start|when (would|will|could) you be (available|able) to (start|begin)|date (could|can|would) you (start|begin)|start date availability|available start date|date (you are |you can )?(available to )?(start|begin) (work|employment)|date (you are )?available to (start|begin)|available to begin employment/i },   // "Date available to begin employment?" (Allison 2026-11-03)   // candidate-profile: available 06/14/2027 (was 06/07 here — aligned 2026-10-30)
    { id: 'intern_when', q: /when would you like to intern|which (internship )?(term|season|period) (would you like|do you prefer|are you applying|are you interested in)/i },
    { id: 'internship_mandatory', q: /internship.{0,40}(mandatory|required|compulsory) (part|component) of (your )?(study|degree|academic|university) program|program requires? (an |the )?internship/i },   // Joey 2026-10-30 (a Lever employer)
    { id: 'enrolled_during', q: /(officially |still )?(enrolled|registered)( as a student)? during the internship|be (an? )?(officially )?(enrolled|registered) student during/i },   // Joey 2026-10-30 (a Lever employer)
    { id: 'location_rank', q: /\brank\b[^?]{0,60}\b(location|office|city|cities|site)s?\b|\b(location|office)s?\b[^?]{0,40}\b(in order of|ranked|rank them)\b/i },   // "Please rank your location preference … : Austin, Chicago, …" (a Greenhouse employer 11-05): every U.S. place listed, home first (Joey 11-05 「都可以」)
    { id: 'office_all', q: /which (office|location)s? (are you applying to|would you (like|prefer) to work)|check all that apply.{0,80}(relocat|office|location)|select (all|both).{0,40}(office|location)/i, all: true },   // Nationwide → every office offered (a Lever employer, an Ashby employer 2026-10-30)
    { id: 'relocate_where', q: /relocat\w*.{0,60}\bwhere\b|where.{0,40}relocat|relocat\w*.{0,40}(scope|how far|which (areas|locations))/i },   // a Workday employer 2026-10-30; profile: anywhere in the U.S.
    { id: 'course_done', q: /\b(did|have) you (complete|finish)\w* our (online )?[\w' ]{0,30}\bcourse\b/i },   // JSA-410 (Joey 11-17, Akuna "Did you complete our online Options 101 Course?" → "Not yet!"): answers.course_done.pick
    { id: 'visitor_visa', q: /^\W*(a )?visitor('s)? visa\W*$|\b(do|did|have|has|had) you (ever )?(held|hold|have|had|possess|possessed|obtained)\b[^?]{0,40}\b(b-?1\s*\/?\s*b-?2|b-?[12]|visitor'?s?|tourist) (u\.?s\.? )?visa\b/i },   // JSA-410 (Joey 11-17): never held a visitor visa (only F-1) → No (answers.visitor_visa.yes)
    { id: 'eeo_furnish', q: /\bdo you wish to furnish\b[^?]{0,40}\binformation\b/i },   // JSA-410 (Joey 11-17): EEO "Do you wish to furnish this information?" → Yes, then the EEO answers as usual (answers.eeo_furnish.yes)
    { id: 'enrolled_fall', q: /\b(enrolled|registered|studying|a student|in school)\b[^?]{0,60}\b(fall|autumn)\b[^?]{0,40}\b(following|after)\b[^?]{0,30}\binternship|\b(fall|autumn)\b[^?]{0,30}\b(following|after) (the|this|your) internship\b[^?]{0,60}\b(enrolled|registered|student)\b/i },   // JSA-410 (Joey 11-17): derived from the graduation date (answers.grad_date.mmyy), never a stored Yes — see DERIVED
    { id: 'reloc_other', q: /\b(other than|besides|apart from|in addition to)\b[^?]{0,80}\b(location|city|cities|office)s?\b[^?]{0,80}\brelocat|\bwhich other (locations?|cities|offices)\b[^?]{0,80}\brelocat/i },   // JSA-410 (Joey 11-17): a multi-select of other cities he would relocate to → only U.S. and China cities (answers.reloc_other.countries), never London / Singapore …
    { id: 'video_record', q: /\b(record(ed|ing)?|film|make|create)\b[^?.]{0,60}\b(video|loom|screencast)\b|\b(loom|screencast)\b[^?.]{0,40}\b(link|video|recording)\b|\bvideo (introduction|response|submission|pitch|message)\b/i, not: /^\s*(are|is|do|does|did|can|could|will|would|have|has)\b/i },   // JSA-410 (Joey 11-17): a required recorded video is never filled — Waiting for you, he records it
    { id: 'relocate', q: /^(?!.*(\bwhere\b|scope|how far|which (areas|locations))).*relocat/i },
    { id: 'local_area', q: /\b(are|is) you (currently )?local to\b|\bare you (currently )?local\b(?! (government|law|authorit|regulation))[^?]{0,100}\b(in|to) (our |the )?[A-Z]?[\w .,/&-]{0,40}\b(office|area|region|location)\b|\blocal to (the )?[\w .,/&-]{0,40}\b(area|region|office)\b/i },   // "Are you local to NYC … able to commute in for a Hybrid schedule?" asks where he lives, not willingness (NYT 2026-11-04): home city → Yes, else the relocate option / No
    { id: 'onsite', q: /on[- ]?site|in[- ]office|hybrid|return to office|\brto\b|in person|in (the|our) [\w ]{0,30}office|\bcommute\b|office.{0,30}days (a|per) week|days (a|per) week.{0,30}office/i, not: /advisor|adviser|professor|school|university|permission|approv|comfortable|\bbased in\b|\blive in\b|\breside|\bcurrently (located|living)|travel (assistance|reimbursement|support)/i , when: onsiteAboutHim },   // "are you based in the SF Bay Area …" asks where he lives (Chicago), not willingness (an Ashby employer 2026-10-31)   // not: someone else's consent (Hitachi 2026-10-30) → Joey
    { id: 'travel', q: /travel(?!l?ers?\b)/i, not: /travel (assistance|reimbursement|support)\b.{0,60}\binterview|\binterview\b.{0,80}\btravel (assistance|reimbursement|support)\b/i },
    { id: 'housing_have', q: HOUSING_HAVE },   // JSA-363: "Do you have housing accommodations in the Austin area?" asks where he lives (Chicago), not whether he can arrange his own housing (WhiteWater 2026-10-31, audit JSA-245)
    { id: 'housing', q: /housing/i, not: new RegExp('housing (industry|market|finance|sector)|conflict|' + HOUSING_HAVE.source, 'i') },   // "… an entity in the housing industry?" is a conflict-of-interest question, not housing support (a Workday employer 11-01, audit 11-09)
    { id: 'reside_us', q: /reside in the (us|united states)|located in the (us|united states)/i },
    { id: 'comp', q: /salary|compensation|pay (range|expectation)|desired pay|hourly rate expectation|\b((expected|desired|target) )?hourly (rate|pay|wage)\b|(required|expected|desired) (pay )?rate|\bpay rate\b/i, not: /^(?!.*\b(expect|desired|target|requir))(?=.*\bcurrent\b).*\b(salary|compensation|pay)\b|hourly or (annual|yearly|salary)|per hour or per year|^(?!.*\b(salary|base|compensation)\s*(\(|and|&|\+|including|plus)\s*(salary\s*(and|&)\s*)?bonus).*\bbonus\b|^\W*i (understand|acknowledge|agree)\b|(rate|pay|salary) (for this [\w ]{0,30})?is \$/i },   // "What is your current annual salary?" is not his expectation: Joey's saved answer (qa, 0) or asked (BCBS NE 11-10, JSA-269)   // "I understand that the hourly rate for this internship is $15/hour." is an acknowledgement (a Lever employer, JSA-246)   // "What is your required pay rate?" (Thorlabs 2026-11-03); "hourly or annually?" is pay_period
    { id: 'pay_period', q: /(rate|pay|salary|compensation)\b.{0,30}\b(hourly or (annual|annually|yearly|salary)|per hour or per year)/i },   // internship pay is hourly (25 / hour standard, Joey 2026-11-01)
    { id: 'how_heard', q: /(how|where) did you (\w+ )?(hear|find|learn)|(how|where) you (\w+ )?(heard|found out|learned) (about|of)\b|how were you made aware of\b|^source\b|^referral source\b|^(applicant |candidate )?source of (referral|application)\b/i, not: /root cause|investigat|problem|what changed|\bfix(ed)?\b/i },   // "How did you find the root cause…" is an essay, never the source answer (BFF Workable 11-04)   // "Where did you hear about this opportunity?" (TikTok 2026-11-03)
    // ---- relationships & restrictions
    { id: 'relative_names', q: /family member names|names?(\(s\))? and relationships?(\(s\))?/i },   // "name(s) and relationship(s)" (Thorlabs 2026-11-03)
    { id: 'relatives', q: /relative|family member|related to (an|any) employee|related to (or associated with )?(anyone|someone|any person)\b[^?]{0,40}\b(works?|employed)\b/i, not: /^(relative'?s? )?(name|position|relationship|title|department)\b|relative (name|position)/i },   // "Relative Name" / "Position" boxes stay empty (an employer 11-04)
    { id: 'prev_employed', q: /(previously|ever|currently) (been )?(directly )?(employed|worked|work) (as an? [\w -]+ )?(by|for|with|at)|\bhave you (ever )?been (directly )?(employed|working) (at|by|with|for)\b[^?]{0,90}\b(before|previously|in the past)\b|(ever|previously) (previously )?worked in any\b|been (directly )?employed (by|with) [\w&.,' -]+ in the past|(currently|in the past),? (or have you (in the past )?)?been employed by|been an? employee of|(former|previous|prior) employee|provided services to|\bare you,? or have you (ever )?been (directly )?employed (by|with|at|for)\b|\bhave you (ever )?been (directly )?employed (by|with|at|for)\b[^?]{0,140}\b(during|in|within|over) the (last|past|previous) (\d+|one|two|three|four|five|ten) (months|years)\b/i },   // "Are you, or have you been employed by <Co> during the last 5 years … or any of its companies?" (Newell SF 11-05, type AC; resume employers stay Yes by resume_employer)   // "certify whether you are a previous employee" (Allison 2026-11-03)
    { id: 'employee_statement', q: /which (one )?(of the following )?(statements?|options?) (best )?(applies|apply|describes?)( to)? (you|your (current )?(status|situation|relationship))/i, not: new RegExp(EMP_WORDS, 'i') },   // "Which statement best applies to you today?" + "I have never worked for <Co>…" (Oracle 2026-11-03); the answer picks only a never-worked-here option
    { id: 'on_assignment', q: /currently (on (an )?assignment|placed|working) as an? (contractor|consultant|temp)|currently on (an )?assignment\b.{0,80}(contractor|consultant|staffing|statement of work|master service)/i },   // "on assignment … as a contractor … at any affiliated <Co> companies" (GuideWell / Oracle 2026-11-03): No — a student, no contract work
    { id: 'notice_period', q: /^notice period\??$|(what is|how long is) your notice period|notice (period )?(required|needed) (to|before)/i },   // student, no job to leave: Available immediately (Joey 2026-11-03)
    { id: 'startup_fit', q: /(confident|comfortable|thrive|enjoy|willing) (working |to work )?in (a |an )?(fast[- ](moving|paced)|startup|start-up|ambiguous|high[- ]growth)|fast[- ](moving|paced),? startup[- ]like environment/i },   // self-assessment: Yes (Joey 2026-11-03)
    { id: 'publications', q: /(number of|how many) .{0,40}(publications|papers)|(peer[- ]reviewed|first[- ]author(ed)?) (publications|papers)|publications? (on which|where) you are/i },   // none yet (Joey 2026-11-03: 「0 篇」)
    { id: 'bond_declined', q: /bond(ing)? company|fidelity bond|fiduciary bond|declined, denied,? or revoked a bond/i },   // Joey 2026-11-03: No
    { id: 'military_status', q: /(hiring and supporting )?military service members and their spouses|disclose your (military|veteran) status|status as (a )?(military|service member)/i },   // not a service member or spouse (profile EEO)
    { id: 'noncompete', q: /non[- ]?compete|non[- ]?solicit|confidentiality agreement|restrict.*(ability|you) (to )?work/i },
    { id: 'government', q: /^(?!.*government[- ]?(issued|id\b|identification)).*(government|military|armed forces|civil service|public official)/i, not: GOV_NOT },   // only his / his family's own government, civil-service or military job or office (KBR, a Workday employer, Constellation: No). A question about supporting military / defense missions is not that (a Lever employer 11-05, JSA-316: answered No, Joey: Yes) → saved answer (qa) or ask the user
    { id: 'outside_business', q: /own(,|\s*\/|\s+or|\s+and)\s*operate|outside business|provide services to another business/i },   // "will you own/operate your own business or have other employment …" (Erie SF 11-04)
    // JSA-210 (Crest Lever 10-31 got his own e-mail): a question that asks for references / referees — other people's contact
    // details. Never answered from his own facts (name / e-mail / phone); none on file → the user gives them (answerByRules)
    { id: 'references', q: /\b(list|provide|enter|give|include|name|supply|submit|add|share|attach)\b[^.?!]{0,60}\b(references?|referees?)\b|\b(professional|personal|work|employment|character|academic|business|supervisory|former employer) (references?|referees?)\b|^\W*(references?|referees?)\b|\b(references?|referees?)'?s? ?(\d|#|full )?(name|contact|phone|telephone|e-?mail|company|employer|title|position|relationship)\b|\breferees?\b|\b(two|three|four|2|3|4) references\b/i,
      not: /\breference checks?\b|\breference (number|no\b|code|id\b|#)|\b(job|position|requisition|posting|vacancy|application) reference\b|\b(with|in) reference to\b|cross[- ]reference|frame of reference/i },
    // JSA-195 (Joey 2026-11-05): referral questions — the hiring company (ctx.company) in the referrer pool (config/connections.json) → ask the user; not in it → no referral; no company → ask
    { id: 'referral', not: /by (an? |the )?recruiter|^referral source\b|source of (referral|application)|(how|where) did you (\w+ )?(hear|find|learn)|(how|where) you (\w+ )?(heard|found out|learned) (about|of)\b|how were you made aware of\b/i,
      q: /\b(were you )?referred\b|\breferral\b|\breferr(er|ing employee)\b|\brefer(red)? you\b|\b(someone|anyone|an? (current )?employee|a (friend|colleague)) (from|at|of|in) (our|the|this) (company|organi[sz]ation|firm|team)\b.{0,40}\b(suggest|recommend|encourage)\w* (that )?you (to )?apply|\b(suggest|recommend|encourage)\w* (that )?you (to )?apply\b.{0,60}\b(name|who)\b/i },
    // ---- EEO (his answers)
    { id: 'gender', q: /^gender|gender identity|self[- ]identification of (gender|sex)\b|\byour gender\b|\bthe gender (you|that)\b|^sex\b|select your sex|\bsex:\s*$/i },
    { id: 'hispanic', q: /hispanic|latin[oa]/i },   // anchored: /not hispanic/ once picked "White (Not Hispanic or Latino)" from a race list (DeepSeek case 2026-11-01)
    { id: 'race', q: /\braces?\b|ethnicit/i },   // "Select the races you identify with." (Oracle 2026-11-03)
    { id: 'veteran', q: /veteran/i },   // "Not Applicable" among veteran types (Zurn 2026-11-01)   // anchored: never "I identify as a Veteran, just not a protected Veteran" (Workday a Workday employer 10-28)
    { id: 'disability', q: /disabilit/i },
    { id: 'pronouns', q: /pronoun(?!c)/i, not: /self[- ]?describ|if you selected|if (other|not listed)/i },   // "pronounced" is not a pronoun; the self-describe follow-up box stays empty (Akuna 11-05, JSA-218)
    { id: 'transgender', q: /transgender/i },
    { id: 'orientation', q: /sexual orientation/i },
    { id: 'age_range', q: /\bage (range|group|bracket|band)\b|^(what is |what's )?your (current )?age\??$|^(current )?age\??$|^how old are you\??$/i },   // EEO-style age band from profile age + as_of (Joey 2026-11-03: 23; Lever survey, JSA-075); + "What is your current age?" (Ashby, Dyna 11-05, JSA-213)
    // ---- opt-ins & consents (his standing rule 2026-10-27): marketing No · talent community Yes · required consent boxes Yes
    { id: 'certify', q: /^\*?\s*i certify\.?$|certif(y|ies) that i have read\b[^.?!]{0,160}\b(information|answers|statements)\b[^.?!]{0,120}\b(true|accurate|correct|complete)\b|certify that (all )?(the )?(information|answers|statements)\b[^.?!]{0,120}\b(true|truthful|accurate|correct|complete)\b|certif(y|ication)\b.{0,60}(true|truthful|accurate|complete)|answers (are|were) (true|truthful|accurate)|information (given|provided|submitted)( by me)?( in this application)? is (true|accurate|correct|complete)/i },   // + "The information given by me in this application is true …" box (Bosch 11-04)
    // JSA-382 (Joey 2026-11-17): ONE box that agrees to the terms / privacy policy AND to SMS / text / WhatsApp updates is always Yes — the form
    // cannot be submitted without the terms. An SMS-only box keeps the sms rule; a terms + marketing box is not this rule.
    { id: 'terms_sms', q: { test: l => /\bthe terms\b|\bterms\s*(&|and)\s|\bterms of (use|service)\b|\bterms\s*$|conditions of use|privacy (policy|notice|statement)|user agreement/i.test(l) && /\bsms\b|text[- ]?messag|\btext\/|\bwhatsapp\b/i.test(l) }, not: /marketing|promot|newsletter|\boffers\b|job alerts?|advertis|verification code|\bdo(es)? not\b|\bdon'?t\b|opt[- ]?out of|unsubscribe/i, yes: true },
    // JSA-333 (Veeva 11-12, Joey 2026-11-06 / 11-16): Lever's closing "Stay Connected | … add no-reply@hire.lever.co (and the company domain) to your
    // safe sender list" box has one acknowledgement option; the wording changes with the company domain, so a saved qa line never fit twice.
    // JSA-286 (Joey 2026-11-10, a Lever employer): an optional "Message to the Hiring Manager" box takes the first 2–3 sentences of THIS job's cover
    // letter (ctx.cover = cover.txt), nothing when there is none. A saved qa answer for the same wording (Joey's own text) comes first.
    { id: 'hiring_manager_note', q: /^\W*(personal |add a )?(message|note) (to|for) the (hiring (manager|team)|recruiter)\W*(\(optional\))?\W*$/i },
    { id: 'lever_safe_sender', q: /^\W*stay connected\b[^]*\bsafe sender list\b/i, not: /marketing|promot|newsletter|\boffers?\b|opt[- ]?in|subscribe|\bsell\b/i, yes: true },
    { id: 'terms', q: /arbitration|terms (and|&) conditions|terms of (use|service)|user agreement|create (an |your )?account/i, consent: true },
    { id: 'marketing', q: either(/marketing (communication|email|message)s?|recruitment marketing|promotional (email|message)|newsletter|^\W*consent\W{0,3}marketing\b|\bmarketing\b.{0,30}\b(consent|opt[- ]?in|purposes)\b|\b(consent|opt[- ]?in)\b.{0,30}\bmarketing\b/i, OPTIN_MKT) },   // Lever \"Consent: marketing\" box = the marketing opt-in → No (audit 11-08, JSA-246)
    { id: 'sms', q: /text message|\bsms\b/i },
    { id: 'profile_visibility', q: /make (my|your) (candidate )?profile visible|profile visibility|(who|which recruiters) (can|may) (see|view|search) (my|your) (candidate )?profile/i },   // SuccessFactors register form (Newell 11-05): Joey's pick in config answers.profile_visibility; none set → unknown
    { id: 'future_contact', q: either2(/talent (community|pool|network)|future (career )?(opportunit|contact|roles)|keep (me|my) (on file|information)|job opportunities, career advice/i, OPTIN_JOBS) },   // "keep me informed" alone is no longer talent news: it goes through the opt-in shape (about jobs → Yes, about the company → asked; JSA-329)
    { id: 'optin_other', q: { test: l => optIn(l) }, ask: true },   // JSA-329: an opt-in to receive something neither job news nor marketing → Joey decides (never the data consent's Yes)
    { id: 'data_consent', q: either(/do you agree to (these|the) terms\??$|privacy (notice|policy|statement)|\backnowledge\b|\bconsent\b|\bi agree\b|\bi have read and (agree|accept)\b|by checking this box|store and process|process(ing)? (of )?my (personal )?(data|information)|(collect|process)\w* (and (process|store|use)\w* )?(your |the )?personal (data|information)|personal (data|information) (will|may) be (processed|stored|used)/i, OPTIN_ABOUT_APP) },   // + being sent news of his own application (JSA-329)
  ];
  const DERIVED = {
    location_full: () => P.answers.location && { text: P.answers.location.text },   // the profile's full location (city, state, country)                                    // JSA-230: answers built from existing facts when the profile has none of its own
    address_full: () => P.answers.address && P.answers.city_state_zip && { text: `${P.answers.address.text}, ${P.answers.city_state_zip.text}` },   // JSA-311
    preferred_last_name: () => P.answers.last_name && { text: P.answers.last_name.text },
    spons_countries: () => {                         // JSA-279: from the sponsorship facts — needs it now or later → the U.S. (where he seeks work), else N/A
      const f = P.answers.spons_future || {}, n = P.answers.spons_now || {};
      if (f.yes === true || n.yes === true) return { text: 'United States' };
      if (f.yes === false && n.yes === false) return { text: 'N/A' };
      return null;
    },
    enrolled_fall: () => {                           // JSA-410: enrolled in the fall after the (summer) internship ← the graduation date: M.S. ends 12/27 → fall 2027 still enrolled
      const g = (P.answers.grad_date || {}).mmyy, m = /^(\d{1,2})\s*\/\s*(\d{2,4})$/.exec(String(g || ''));
      if (!m) return null;
      const gy = +m[2] < 100 ? 2000 + +m[2] : +m[2], gm = +m[1], now = process.env.JSA_TODAY ? new Date(process.env.JSA_TODAY + 'T12:00:00') : new Date(), fallYear = now.getFullYear() + (now.getMonth() >= 7 ? 1 : 0);   // after August the next internship is next summer (JSA_TODAY pins the date for tests)
      return { yes: gy * 12 + gm >= fallYear * 12 + 9 };
    },
    preferred_full_name: () => P.answers.preferred_name && P.answers.last_name && { text: `${P.answers.preferred_name.text} ${P.answers.last_name.text}` },
  };
  for (const r of R) {                                  // the profile's answer for each rule (pick entries are "/re/flags" strings)
    const a = P.answers[r.id] || (DERIVED[r.id] && DERIVED[r.id]());
    if (a) Object.assign(r, a, a.pick ? { pick: a.pick.map(RX) } : {});
  }
  // F-1: a "Yes" that claims unrestricted / permanent authorization is never his (a Workday employer 2026-11-01 picked "Yes, without restrictions")
  const WITHOUT_SPONS = /^(?:(?!\b(?:requir|need)\w*\b)[^?])*?\bwithout\b[^?]{0,80}\bsponsor/i;   // {0,80}: \"without (now or in the future) requiring any visa sponsorship\" (a Workday employer 11-01, found 11-09)   // the question itself (before its '?') asks about working WITHOUT sponsorship, and does not first ask whether he requires it
  const SPONS_LATER = /\bfuture\b|after (you )?graduat|upon graduation|at any (point|time)|any time (after|in)|\blater\b|eventually|going forward|long[- ]term|full[- ]time (employment|role|position)/i;   // the question also covers after the internship
  const SPONS_NOW_ONLY = /\b(for|in|during) (the duration of )?(this|the) (internship|position|role|job)\b|\bduration of (this|the|my) internship|\b(now|currently|presently|at present|at this time|today)\b|\b(e\.g\.|such as|including)[^?]{0,40}\b(opt|cpt)\b|\((e\.g\.,? )?[^)]{0,30}\b(opt|cpt)\b[^)]*\)/i;   // = canon NOW_ONLY_RE, + OPT / CPT named as an example of working without sponsorship (JSA-175: the employer counts the CPT internship → Yes): only these make a "without sponsorship" question the NOW one (decisions-log 11-05); "…permitted to work in the country where this job is located?" covers the future → No (Ankura 11-10, submitted No)
  const UNRESTRICTED = /without (any )?restriction|unrestricted|no restriction|permanent(ly)?|any employer|all employers|citizen|green card|permanent resident/i;
  // JSA-310: with claim_authorized a "Yes" may claim any employer / no restriction, never citizenship / permanence / no sponsorship
  const NOT_HIS_YES = CLAIM_AUTH ? /\bcitizen|green card|permanent(ly)?\b|\blawful(ly)? permanent|\bwithout\b[^.]{0,60}\bsponsor|\b(do(es)? not|don'?t|will not|won'?t|never|no longer)\b[^.]{0,30}\b(requir|need)\w*[^.]{0,60}\bsponsor|\bno (visa |immigration )?sponsorship/i : UNRESTRICTED;
  const ANY_EMP_OPT = /any (u\.?\s?s\.?\s*)?employers?|all employers|without (any )?restriction|unrestricted/i;   // JSA-291
  const NOT_AUTH_OPT = /\b(not|un)\s*(currently |presently |yet |legally )*(authori[sz]ed|eligible|permitted)\b/i;
  const CIT_STATUS_Q = /\b(u\.?\s?s\.? )?citizen(ship)?\b|\b(lawful(ly)? )?permanent residen|green card|\bu\.?s\.? national\b/i;   // JSA-310
  const PERM_Q = /\bpermanent(ly)? (authori[sz]ed|eligible|allowed|permitted|entitled|right)\b|\bauthori[sz]ed to work permanently\b/i;   // JSA-310
  const SPONS_OPT = /\b(requir|need)\w*\b[^.]{0,80}\bsponsor/i;
  const NO_SPONS_OPT = /\b(do(es)? not|don'?t|will not|won'?t|never|no longer|not)\s+(now or in the future\s+)?(currently\s+)?(requir|need)/i;
  const NEG_STMT = /^(i have not|i haven't|i have never|i've never|i am not|i'm not|i do not|i don't|i did not|i didn't|i was not|i wasn't|i will not|i can't|i cannot|never)\b/i;
  const yesNo = (opts, yes) => {
    const strict = yes ? /^(yes|true)\b/i : /^(no|false)\b/i;
    const hit = (opts || []).find(o => strict.test(String(o).trim()) && !(RESTRICTED && yes && NOT_HIS_YES.test(String(o))));
    if (!hit && !yes && (opts || []).length > 2) {   // JSA-244: "I have not previously been employed at Affirm" among "I have been employed … as …" (a Greenhouse employer 11-08) — exactly one negative statement
      const negs = opts.filter(o => NEG_STMT.test(String(o).trim()));
      if (negs.length === 1) return negs[0];
    }
    if (hit || (opts || []).length > 2) return hit;   // a long list of statements ("I am a U.S. citizen…", an Ashby employer 10-31) is not a yes/no pair → unknown
    const re = yes ? /^(i am|i do|i will|i can)\b(?! not)/i : NEG_STMT;
    return (opts || []).find(o => re.test(String(o).trim()) && !(RESTRICTED && yes && NOT_HIS_YES.test(String(o))));   // never "I am authorized to work permanently" (DeepSeek case 2026-11-01)
  };
  // JSA-105: the lowest number of years of experience the JD asks for (required or preferred); 0 = none; null = no JD text
  const NUM = { zero: 0, one: 1, two: 2, three: 3, four: 4, five: 5, six: 6, seven: 7, eight: 8, nine: 9, ten: 10 };
  const N = '(\\d+|' + Object.keys(NUM).join('|') + ')';
  const YRS_A = new RegExp('\\b' + N + '\\s*\\+?(?:\\s*(?:-|–|—|to)\\s*' + N + ')?\\s*\\+?\\s*(?:years?|yrs?)\\b([^.;\\n]{0,40}?)\\bexperience\\b', 'gi');
  const YRS_B = new RegExp('\\bexperience\\b[^.;\\n]{0,25}?(?:of|:)\\s*(?:at least |a minimum of |minimum of |over )?' + N + '\\s*\\+?\\s*(?:years?|yrs?)\\b', 'gi');
  const NOT_WORK = /degree|college|universit|school|academic|\bage\b|\bold\b|history|founded|in business|serving|, with|;/i;   // "4-year degree", "18 years old", "20 years in business, with experience …"
  function jdYears(jd) {
    if (!jd || !String(jd).trim()) return null;
    const t = String(jd).replace(/\s+/g, ' '), val = x => (x in NUM ? NUM[x.toLowerCase()] : NUM[x.toLowerCase()] ?? parseInt(x, 10));
    const ys = [];
    for (const m of t.matchAll(YRS_A)) if (!NOT_WORK.test(m[3] || '')) ys.push(val(m[1]));
    for (const m of t.matchAll(YRS_B)) ys.push(val(m[1]));
    const pos = ys.filter(y => y > 0);
    return pos.length ? Math.min(...pos) : 0;   // "0-2 years" / "0+ years" = no minimum
  }
  // the option whose numeric band contains `age`: "21-29", "25 to 34", "65+", "60 or older", "17 or younger", "under 18" ('' if none)
  function ageBand(opts, age) {
    for (const o of opts || []) {
      const t = String(o).replace(/\s+/g, ' ').trim();
      let m, lo = null, hi = null;
      if ((m = t.match(/(\d+)\s*(?:-|–|—|to)\s*(\d+)/i))) { lo = +m[1]; hi = +m[2]; }
      else if ((m = t.match(/(?:under|younger than|below|less than)\s*(\d+)/i))) { lo = 0; hi = +m[1] - 1; }
      else if ((m = t.match(/(\d+)\s*(?:or|and)\s*(?:younger|under|below|less)/i))) { lo = 0; hi = +m[1]; }
      else if ((m = t.match(/(\d+)\s*(?:\+|or (?:older|over|above|more)|and (?:older|over|above|up)|plus)/i))) { lo = +m[1]; hi = Infinity; }
      else if ((m = t.match(/(?:over|older than|above)\s*(\d+)/i))) { lo = +m[1] + 1; hi = Infinity; }
      if (lo !== null && age >= lo && age <= hi) return o;
    }
    return '';
  }
  // JSA-164 (Joey 2026-11-04): the profile's question-and-answer table (config/profile.json → qa). A using session that
  // meets a question no rule knows asks the user once and adds the answer with qa_add.py — no code change, no new test.
  // Only for questions the rules leave unknown (never over a rule, never over an "ask the user" result).
  // Entry: {q: "the question as the form wrote it", match?: "/regex/flags", text?, pick?: ["/re/i"], yes?: bool, source, added}
  const qaNorm = s => String(s || '').toLowerCase().replace(/[\u2018\u2019]/g, "'").replace(/\(?\brequired\b\)?|\*/g, ' ')
    .replace(/[^a-z0-9']+/g, ' ').trim();
  const QA = (P.qa || []).map((e, n) => e && Object.assign({}, e, { n: n + 1, nq: qaNorm(e.q),   // n = the entry's place in the table (qa_add --list), kept when retired entries drop out
    rx: e.match ? RX(e.match) : null, pick: (e.pick || []).map(RX) })).filter(e => e && (e.q || e.match) && !e.retired);   // retired: kept for the record, never answers (JSA-281)
  function qaFindAll(label) {                           // exact question (normalised), or the entry's own regex; a long
    const nl = qaNorm(label);                           // question may sit inside a label that adds help text after it
    return QA.filter(e => (e.rx && e.rx.test(label)) || (e.nq && (nl === e.nq || (e.nq.length >= 40 && nl.startsWith(e.nq))))).reverse();
  }
  // Every saved entry that matches, newest first (JSA-277): the first that gives an answer wins. Before, the oldest match
  // was the only one tried, so an old entry whose pick missed this form's options blocked a newer one (prefetch 11-08, 11-10).
  function qaAnswer(f, label) {
    let miss = null;
    for (const e of qaFindAll(label)) {
      const a = qaOne(e, f, label);
      if (a && a.status === 'ok') return a;
      if (a && !miss) miss = a;
    }
    return miss;
  }
  function qaOne(e, f, label) {
    const opts = f.o || f.options || [], id = 'qa:' + e.n;
    if (opts.length) {
      let o;
      for (const p of e.pick) { o = opts.find(x => p.test(String(x).trim())); if (o) break; }
      if (!o && e.text) o = opts.find(x => qaNorm(x) === qaNorm(e.text));
      if (!o && e.yes !== undefined) o = yesNo(opts, e.yes);
      // JSA-419: a Yes ticks the ONE option of a consent box — a checkbox, or any field type when the option itself reads as consent
      // (Fundwell "Background-Check Acknowledgment" [I authorize …]). Never an option that negates ("I am not authorized", "None of the
      // above", "N/A", "I decline") and never one the restricted-status guard (NOT_HIS_YES) blocks.
      if (!o && e.yes === true && opts.length === 1) {
        const only = String(opts[0]).trim();
        const negated = /\w+n['\u2019]t\b|\b(not|never|cannot|can'?t|none|n\/a|neither|without|decline|disagree|refuse|opt[- ]?out)\b|^\W*no\b/i.test(only);
        const consent = /\b(authori[sz]e|agree|acknowledge|consent|certify|confirm|understand|accept|attest|affirm)\b/i.test(only);
        if (!negated && (f.t === 'checkbox' || consent) && !(RESTRICTED && NOT_HIS_YES.test(only))) o = opts[0];
      }
      return o ? { status: 'ok', label, rule: id, value: o } : { status: 'unknown', label, rule: id, why: id + ': no option matches the saved answer', options: opts.slice(0, 8) };
    }
    if (e.box !== undefined && e.box !== '') return { status: 'ok', label, rule: id, value: e.box };   // JSA-419: the value for a TEXT box, apart from the list picks / pattern in text
    // a list answer saved only as a pattern (pick "/^f1 \/ stem opt$/i" → text "^f1 \/ stem opt$") is never typed into a box
    // with no options (Simon Workday record 11-10: the regex itself would be the answer) — a miss, so an older entry may answer
    if (e.text && e.pick.some(p => p.source === e.text)) return { status: 'unknown', label, rule: id, why: id + ': the saved answer is an option pattern; this field has no options' };
    if (e.text) return { status: 'ok', label, rule: id, value: e.text };
    if (e.yes !== undefined) return { status: 'ok', label, rule: id, value: e.yes ? 'Yes' : 'No' };
    return null;
  }
  // A text box that asks a yes/no question and says what to type ("If NO, please indicate NO.", Erie SF 11-04): the word
  // as the form writes it; a Yes that the form wants explained ("If YES, please explain / include …") → ask the user.
  const NO_INSTR = /\bif (no|not)\b,?\s*(?:then\s+)?(?:please\s+)?(?:indicate|answer|enter|type|write|state|put|respond(?: with)?|reply(?: with)?|mark|say|input)\s*:?\s*["\u201c'\u2018]?(n\/a|none|na|no)\b/i;
  const YES_ONLY = /\bif (yes|so)\b,?\s*(?:then\s+)?(?:please\s+)?(?:indicate|answer|enter|type|write|state|put|mark|say|input)\s*:?\s*["\u201c'\u2018]?(yes|y)\b["\u201d'\u2019]?(?!\s*(and|,|with)\b)/i;
  const YES_DETAIL = /\bif (yes|so)\b,?\s*(?:then\s+)?(?:please\s+)?(?:explain|include|provide|list|describe|specify|give|name|state (the|your|who|which|what)|detail|identify|elaborate|tell|share|indicate\s+["\u201c'\u2018]?yes["\u201d'\u2019]?\s*(and|,|with))/i;
  function ynText(out, label) {
    const no = label.match(NO_INSTR), yesOnly = label.match(YES_ONLY), yesDetail = YES_DETAIL.test(label);
    if (!no && !yesOnly && !yesDetail) return out;
    if (/^no$/i.test(out.value)) return no || yesOnly ? Object.assign(out, { value: no ? no[2] : out.value, yn_text: true }) : out;   // only "If yes, explain": the text-box guard decides as before
    const explain = (P.work_auth || {}).sponsorship_explain;   // a sponsorship Yes the form wants explained → the saved explanation (a Greenhouse employer 11-05, JSA-218)
    if (yesDetail && /^spons_(now|future)$/.test(out.rule) && explain) return Object.assign(out, { value: explain, yn_text: true });
    if (yesDetail) return { status: 'unknown', label, rule: out.rule, ask: true, why: out.rule + ': Yes needs the details the form asks for — the user writes them' };
    return Object.assign(out, { value: yesOnly ? yesOnly[2] : out.value, yn_text: true });
  }
  // ---- JSA-195: the referrer pool. Company names are compared loosely: case, punctuation, ".com", "&" / "and", and legal /
  // generic suffixes (Inc, LLC, Corp, Technology, Group, Services …) dropped — "an employer" → amazon,
  // "an employer LLP" → ernst young, "an employer, Inc." → micron. A pool key matches the whole name, its start
  // ("Amazon Web Services") or, for keys of 5+ letters, a whole-word part of it ("TikTok (ByteDance)" → tiktok + bytedance).
  const REF_IDS = ['referral', 'know_employee'];
  const REF_OPT = /\brefer(r(al|ed|er|ing))?\b/i;
  const PERSON_OPT = /\brecruiters?\b|\bemployees?\b|\bfriends?\b|\bcolleagues?\b|\bco-?workers?\b|\bword of mouth\b|\bfamily\b/i;   // a source that claims a person contacted / told him (JSA-219, Radix 11-05 "Radix Recruiter")
  const CO_SUFFIX = /\b(inc|incorporated|llc|l l c|corp|corporation|co|company|ltd|limited|plc|lp|llp|holdings?|group|the|usa|us|services?|technolog(y|ies)|tech|labs?|global|international|intl|and)\b/g;
  const coNorm = c => String(c || '').toLowerCase().replace(/&/g, ' and ').replace(/\.com\b/g, ' ').replace(/[^a-z0-9]+/g, ' ')
    .replace(CO_SUFFIX, ' ').replace(/\s+/g, ' ').trim();
  const CO_ALIAS = { aws: 'amazon', ey: 'ernst young', uchicago: 'university of chicago', 'u chicago': 'university of chicago' };   // common short names (generic; they matter only when the full name is a pool key)
  function poolCheck(ctx) {
    const company = String(((ctx || {}).company) || '').trim();
    if (!POOL || !POOL.connections) return { state: 'nopool', company };
    const ck = coNorm(company);
    if (!ck) return { state: 'unknown', company };
    const alias = Object.assign({}, CO_ALIAS, ...Object.entries(POOL.aliases || {}).map(([k, v]) => ({ [coNorm(k)]: coNorm(v) })));
    const names = [ck].concat(Object.keys(alias).filter(a => ck === a || ck.startsWith(a + ' ')).map(a => alias[a]));
    const people = [], keys = [];
    for (const [key, list] of Object.entries(POOL.connections)) {
      const kk = coNorm(key);
      if (!kk) continue;
      if (names.some(n => n === kk || n.startsWith(kk + ' ') || (kk.length >= 5 && (' ' + n + ' ').includes(' ' + kk + ' ')))) {
        keys.push(key); for (const p of list || []) people.push(p);
      }
    }
    return people.length ? { state: 'pool', company, keys, people } : { state: 'none', company };
  }
  function refAsk(label, rule, ref) {
    if (ref.state === 'pool') return { status: 'unknown', label, rule, ask: true, referrers: ref.people.map(p => [].concat(p)[0]),
      why: rule + ': ' + ref.company + ' is in the referrer pool (' + ref.people.map(p => [].concat(p).filter(Boolean).join(' — ')).join('; ') + ') — ask the user (never filled automatically)' };
    return { status: 'unknown', label, rule, ask: true, why: rule + (ref.state === 'nopool' ? ': the referrer pool is not loaded' : ': no hiring company given') + ' — cannot check the referrer pool; ask the user' };
  }
  // the word the form asks for when there is no referrer: "if not type N/A" → N/A, "write None if no one referred you" → None
  const REF_NONE = [
    /\b(?:if (?:not|no|none|no one|nobody|not applicable|n\/a)|otherwise|if you (?:were|are) not(?: referred)?|if no(?: ?one| employee)?(?: referred you)?|if there is (?:no|none)|if you do not(?: know| have)(?: one| anyone)?)\b[^.?!;]{0,30}?\b(?:type|write|enter|put|indicate|answer|input|state|say|mark|respond with|reply with|use|leave)\s*:?\s*["\u201c'\u2018]?(n\/a|none|na|no|no one|nobody|not applicable)(?![\w/])/i,
    /["\u201c'\u2018]?\b(n\/a|none|not applicable)(?![\w/])["\u201d'\u2019]?\s*(?:if|when)\s+(?:not|none|no|not applicable|you (?:were|are) not|no one|nobody)\b/i,
  ];
  function referralAnswer(f, label, opts, rule, hits, ctx) {
    const ref = poolCheck(ctx);
    if (ref.state !== 'none') return refAsk(label, rule.id, ref);
    const other = hits.filter(h => !REF_IDS.includes(h.id) && !['data_consent', 'how_heard'].includes(h.id));
    if (other.length) return { status: 'unknown', label, rule: rule.id, ask: true, why: rule.id + ': referral question mixed with ' + other.map(h => h.id).join('/') + ' — ask the user' };
    if (rule.yes !== false) return { status: 'unknown', label, rule: rule.id, why: rule.id + ': no answer in the profile' };   // the profile's "no referral" answer (answers.<id>.yes = false); deleted = left for the user
    const out = { status: 'ok', label, rule: rule.id, no_referral: true };
    if (opts.length) {
      if (f.t === 'checkbox' && opts.length === 1) return Object.assign(out, { value: '', leave: true });   // "I was referred by an employee" box stays unticked
      const o = yesNo(opts, false) || opts.find(x => /^(none|n\/a|na|not applicable|no referral|no one|nobody|i was not referred|i have not been referred|not referred)\b/i.test(String(x).trim()));
      return o ? Object.assign(out, { value: o }) : { status: 'unknown', label, rule: rule.id, ask: true, why: rule.id + ': not in the referrer pool, but no "No / None" option — ask the user', options: opts.slice(0, 8) };
    }
    for (const rx of REF_NONE) { const m = label.match(rx); if (m) return Object.assign(out, { value: m[1], yn_text: true }); }
    if (/^(were|was|are|is|did|do|does|have|has|had)\b/i.test(label)) return Object.assign(out, { value: 'No', yn_text: true });   // a yes/no question in a text box
    return Object.assign(out, { value: 'N/A', yn_text: true });   // "Referral name" / "Referred by" / "Name of the employee who referred you"
  }
  // answer-shape check (JSA-201, Joey 2026-11-05): a rule's answer must look like an answer to that type of question —
  // a GPA is a number, a band, N/A or Other; a visa is a visa name, never a work authorization (CPT / OPT). "Other" stays
  // allowed: Joey picks it when no option holds the fact (decisions-log 10-25 Cadence, 10-30 a Workday employer). Wrong shape →
  // not filled, ask Joey.
  const VISA_NAME = /\b(F-?1|J-?1|H-?1B|H-?4|L-?1|L-?2|O-?1|TN|E-?[123]|M-?1|B-?[12])\b|green card|permanent resident|citizen|no visa|n\/?a|not applicable|none/i;
  const NUMLIKE = /\d/;
  // high-risk rules answer only in the question's own form (JSA-203, Joey 2026-11-05): visa, sponsorship, work
  // authorization, degree, GPA and criminal-record rules. A yes/no question ("Are you …?", "Will you …?") gets Yes / No
  // (or one of its own options); a "what / which / please provide" question never gets a bare Yes / No. Anything else →
  // ask. ("Are you subject to any conditions … tied to your current visa status …?" had been answered "F-1".)
  const HIGH_RISK = new Set(['immigration_status', 'visa_details', 'auth_kind', 'sponsorship_type', 'spons_now', 'spons_future', 'spons_countries', 'on_opt',
    'eligibility_3way', 'authorized', 'gpa_threshold', 'visa_conditions', 'any_employer', 'auth_today', 'work_permit', 'citizen_pr', 'degree', 'degree_major', 'highest_ed', 'gpa', 'gpa_current',
    'misconduct', 'legal_dispute', 'debarred', 'background_drug', 'conviction']);
  const AUX_Q = /^(are|is|am|do|does|did|will|would|can|could|have|has|had|were|was|should|may)\b/i;
  const DEGREE_ASKED = /\b(current(ly)?|pursu(e|ing)|obtain(ing)?|earning|working (on|towards?)|enrolled in|studying for|seeking)\b|\bconfirm\b/i;   // the degree asked as a question, not a bare "Degree" box of an education row
  const WH_Q = /^(what|which|when|where|how|list|name|state|specify|describe|explain|provide|please (provide|list|specify|state|describe|explain|indicate|share|enter|note|give))\b/i;
  const REQ_Q = /^(can|could|would|will) you (please |kindly )?(confirm|tell us|share|provide|list|state|describe|specify|indicate|enter|name|let us know)\b(?! (that|whether|if)\b)/i;   // "Can you please confirm the current degree that you are obtaining?" asks WHAT (Bosch SR 11-10, JSA-296)
  function formCheck(label, opts, vals, rule) {        // pure (tested): null = the answer fits the question's form
    if (!HIGH_RISK.has(rule)) return null;
    const norm = x => String(x).replace(/\s+/g, ' ').trim().toLowerCase();
    if (opts.length && vals.every(v => opts.some(o => norm(o) === norm(v)))) return null;   // one of the question's own options
    const q = label.replace(/^\s*(\*|\d+[.)]|q\d+[.:])\s*/i, '').replace(/^(if (yes|so|applicable|no)[,:]?\s*)/i, '').trim();
    const isYN = v => /^(yes|no)\b/i.test(v);
    if (AUX_Q.test(q) && !REQ_Q.test(q) && !/^if\b/i.test(label.trim()) && vals.some(v => !isYN(v))) return 'yes / no question answered ' + JSON.stringify(vals.join(', ')) + ' (' + rule + ')';
    if (WH_Q.test(q) && !opts.length && vals.some(v => /^(yes|no)$/i.test(v))) return 'what-question answered ' + vals.join(', ') + ' (' + rule + ')';
    const main = q.replace(/^if\b[^,?]{0,120},\s*/i, '');   // "If you have a current work authorization/status, when does it expire?" asks WHEN (Akuna 11-05, JSA-218)
    if (main !== q && WH_Q.test(main) && !opts.length && vals.some(v => /^(yes|no)$/i.test(v))) return 'what-question answered ' + vals.join(', ') + ' (' + rule + ')';
    return null;
  }
  function shapeCheck(f, a) {                           // pure (tested): the answer, or an unknown when its shape is wrong
    if (!a || a.status !== 'ok' || a.leave || a.value === undefined || a.value === null || a.value === '') return a;
    const label = a.label || (f.l || f.label || ''), opts = f.o || f.options || [];
    const qt = qtypes(label, opts).map(t => t.t);
    const vals = (Array.isArray(a.value) ? a.value : [a.value]).map(v => String(v).trim());
    const bad = why => ({ status: 'unknown', label, why: 'answer shape: ' + why, rule: a.rule, rejected: a.value, qtype: qt });
    const strict = a.yn_text ? null : formCheck(label, opts, vals, a.rule); if (strict) return bad(strict);   // yn_text = the box's own "If no, write N/A" word
    if (a.rule === 'gpa_threshold' || a.rule === 'visa_conditions') return a;   // a yes/no inferred from the facts (Joey 2026-11-05): its form was just checked; GPA / visa-name shapes do not apply
    if (!qt.length) return a;
    if (qt.includes('gpa') && vals.some(v => !NUMLIKE.test(v) && !/^(n\/?a|not applicable|none|other)\b/i.test(v))) return bad('GPA answer without a number: ' + vals.join(', '));
    if (qt.includes('visa_type') && vals.some(v => !VISA_NAME.test(v))) return bad('visa question answered with a non-visa: ' + vals.join(', '));
    if (qt.includes('visa_type') && vals.some(v => /\b(cpt|opt|curricular|optional practical)\b/i.test(v) && !/\bF-?1\b/i.test(v))) return bad('visa question answered with a work authorization: ' + vals.join(', '));
    const yn = opts.length && opts.every(o => /^(yes|no)\b/i.test(String(o).trim()));
    if (qt.length === 1 && qt[0] === 'major' && vals.some(v => /\b(bachelor|master|ph\.?\s?d|doctor|associate|degree|b\.?[as]\.?|m\.?[as]\.?)$/i.test(v) || (!yn && /^(yes|no)$/i.test(v)))) return bad('major question answered with a degree level / Yes-No: ' + vals.join(', '));
    if (qt.length === 1 && qt[0] === 'gpa' && !yn && vals.some(v => /^(yes|no)$/i.test(v))) return bad('GPA question answered Yes / No');
    return a;
  }
  // uncertain answers (JSA-202): the rules did answer, but by a choice a person would double-check — the question was
  // inverted ("able to work WITHOUT sponsorship"), or several rules with different answers fitted and one won by order.
  // The runner's bridge sends only these to a second opinion (runner/second_opinion.py); a disagreement → ask Joey.
  function uncertainty(f, a) {
    if (!a || a.status !== 'ok' || a.leave || /^(qa:|degree_major$)/.test(String(a.rule || ''))) return null;   // degree_major answers degree AND major from one entry (JSA-197): the two rules fitting is the point
    if (a.inverted) return 'inverted question (' + a.rule + ')';
    const label = (a.label || f.l || f.label || '').replace(/\s+/g, ' ').trim();
    const hl = dropExclusions(label);
    const hits = R.filter(r => r.q.test(hl) && !(r.not && r.not.test(hl)) && !(r.when && !r.when(hl)) && !(NAME_RULES.has(r.id) && ynQuestion(label) && ynBox(f)));
    if (hits.length < 2) return null;
    const yn = hits.every(h => typeof h.yes === 'boolean' && !h.pick && !h.text);
    if (yn && hits.every(h => h.yes === hits[0].yes)) return null;      // every fitting rule gives the same Yes / No
    const typed = new Set(QTYPES.flatMap(t => t.rules));
    if (hits.filter(h => typed.has(h.id)).length < 2) return null;      // only one high-stakes rule fitted: no real conflict
    return 'several rules fitted: ' + hits.map(h => h.id).join(' / ');
  }
  // JSA-205 (Newell SF 11-05): a generic rule's bare Yes / No on an option-less text box does not fit the box ("…Please rank
  // your preferred work locations…" got relocate = Yes, then the text-box guard threw it away). A saved answer (qa) for
  // this very question with a text answer wins then; the bridge's guard tries qa too when it rejects a rule's answer.
  const YN = v => /^(yes|no)$/i.test(String(v).trim());
  const textBox = f => !(f.o || f.options || []).length && /^(text|textarea)$/.test(f.t || 'text');
  // JSA-244: language questions the saved answers miss — a list of languages, or a level for one language. Facts:
  // profile.languages = [{name, re, level: 'native' | 'professional'}] (Joey 2026-11-08: Chinese native, English
  // professional, every other language No). No profile.languages → never answers. Runs after the rules and the qa table.
  const LANGS = /\b(english|chinese|mandarin|cantonese|spanish|french|german|japanese|korean|portuguese|italian|arabic|hindi|russian|dutch|flemish|vietnamese|tagalog|polish|turkish|hebrew|swedish|norwegian|danish|finnish|greek|thai|indonesian|malay|bengali|urdu|persian|farsi|ukrainian|czech|romanian|hungarian)\b/i;
  const LEVEL = /\b(native|mother tongue|bilingual|fluent|fluency|proficien\w*|professional|advanced|intermediate|beginner|elementary|basic|limited|conversational|expert|none|[abc][12]|l[1-3])\b/i;
  const LEVEL_PICK = { native: [/native|mother tongue/i, /^c2\b/i, /bilingual/i, /fluent/i, /expert/i, /advanced/i],
                       professional: [/full professional|professional working/i, /\bprofessional\b/i, /fluent/i, /^c1\b/i, /advanced|expert/i] };
  const NO_LANG = /^(none|no proficiency|not applicable|n\/a|i do not speak|no knowledge|no experience|not proficient)\b/i;
  function langAnswer(f, label) {                       // pure given P (tested): {status, …} or null (not a language question)
    const L = (P.languages || []).filter(x => x && x.re), opts = (f.o || []).map(String);
    if (!L.length || /programming|coding|\bcode\b|software|scripting|query language|framework/i.test(label)) return null;
    const mine = o => L.find(x => new RegExp(x.re, 'i').test(o));
    // JSA-354 (a Greenhouse employer "Languages Spoken"): a text box asking which languages he speaks gets every language in the
    // facts (not only the first), by name, in fact order; "other than English" leaves that language out.
    if (!opts.length && /^(text|textarea)$/.test(f.t || 'text') && /\blanguages\b|\blanguage\(s\)/i.test(label)    // plural only: a singular "this language" is one language, not the list
        && /\b(spoken|speak|speaks|fluent|know|list)\b/i.test(label)
        && !/prefer|proficien|\blevel|\brate\b|\bnative(ly)?\b|\b(first|primary) language|mother tongue|\bfluency\b/i.test(label)) {
      const m = label.match(/\b(other than|besides|apart from|excluding|except)\b([^?]*)/i), tail = m ? m[2] : '';   // every fact language named after the marker is left out ("other than English and Chinese")
      const names = L.filter(x => !(tail && new RegExp(x.re, 'i').test(tail))).map(x => x.name);
      if (names.length) return { status: 'ok', label, rule: 'languages', value: names.join(', ') };
      return null;
    }
    const lists = opts.filter(o => LANGS.test(o)).length >= 2 && !opts.some(o => /^[abc][12]\b|^l[1-3]\b/i.test(o.trim()));
    if (/\blanguages?\b/i.test(label) && lists) {        // which languages: his own, one option per language (the one that starts with it first)
      const pick = [];
      for (const x of L) {
        const re = new RegExp(x.re, 'i'), start = new RegExp('^\\W*(' + x.re + ')', 'i');
        const o = opts.find(y => start.test(y)) || opts.find(y => re.test(y));
        if (o && !pick.includes(o)) pick.push(o);
      }
      if (!pick.length) return null;
      const nat = L.find(x => x.level === 'native'), first = /\b(native|first|mother|primary)\b/i.test(label);
      if (!first && (/^(multi|checkbox)$/.test(f.t) || /\blanguages\b|all that apply|select all|check all|\bfluency\b/i.test(label)))   // the bridge passes a multi-select as combo: the label says it is a list
        return { status: 'ok', label, rule: 'languages', value: pick.join(' | ') };
      if (first && nat) {
        const o = opts.find(y => new RegExp(nat.re, 'i').test(y));
        if (o) return { status: 'ok', label, rule: 'languages', value: o };
      }
      return null;
    }
    if (opts.filter(o => LEVEL.test(o)).length < 3 || !/\b(language|proficien|fluen|cefr|level|rate|speak)\w*/i.test(label)) return null;
    const named = (label.match(new RegExp(LANGS.source, 'gi')) || []).map(w => w.toLowerCase());
    if (!named.length) return { status: 'unknown', label, rule: 'languages', ask: true, why: 'languages: a level question that names no language — ask the user for this job' };
    const own = named.map(w => mine(w)).find(Boolean);
    if (own) {
      for (const re of LEVEL_PICK[own.level] || []) { const o = opts.find(y => re.test(y) && !/certif/i.test(y)); if (o) return { status: 'ok', label, rule: 'languages', value: o }; }
      return { status: 'unknown', label, rule: 'languages', ask: true, why: 'languages: no option fits level ' + own.level + ' for ' + own.name };
    }
    const none = opts.find(y => NO_LANG.test(y.trim()));
    if (none) return { status: 'ok', label, rule: 'languages', value: none };
    return { status: 'unknown', label, rule: 'languages', ask: true, why: 'languages: the user does not speak ' + named[0] + ' and the form has no "none" option — ask the user for this job' };
  }
  // an option that says he already lives / works in a place: true only for home (answers.local_area.home, Chicago)
  const HERE_CLAIM = /\b(i'?m|i am|i'?m currently|i am currently|currently|already)\s+(located |based |living |residing )?in\b|\b(i )?(currently )?(live|reside)s? in\b|\b(located|based) in\b/i;
  function placeClaim(o) {
    if (!HERE_CLAIM.test(String(o))) return false;
    const h = (P.answers.local_area || {}).home;
    return !(h && RX(h).test(String(o)));
  }
  const DIGITS_ONLY = /numer(ic|ical)(al)? (format|value|only|characters?)|numbers? only|digits? only|only (numbers|digits)|without (special |any )?characters|no (special )?characters|whole numbers?|(numbers|digits) without/i;
  function answerFor(f, ctx) {
    const a = shapeCheck(f, answerByRules(f, ctx));
    const u = uncertainty(f, a); if (u) a.uncertain = u;
    if (a.status === 'ok' && !a.leave && !a.yn_text && textBox(f) && YN(a.value) && !/^qa:/.test(String(a.rule || ''))) {
      const q = qaAnswer(f, a.label);
      if (q && q.status === 'ok' && !YN(q.value)) return Object.assign(q, { over: a.rule });
    }
    if (a.status !== 'unknown' || (a.ask && !a.qa_ok)) return a;   // qa_ok: an "ask" a saved answer may settle (references, JSA-210)
    return qaAnswer(f, a.label) || langAnswer(f, a.label) || a;
  }
  answerFor.qaAnswer = qaAnswer;   // for runner/rules_bridge.js: its text-box guard tries the saved answers before giving up (JSA-205)
  answerFor.langAnswer = langAnswer;
  // question types (JSA-200). rules = the rule ids that may answer that type; spec = a specific type (wins over general).
  const BANDS = o => (o || []).filter(x => /\b[0-4]\.\d{1,2}\b/.test(String(x))).length >= 2;
  const ASKS_NEED = /\bsponsor|\b(require|need)s?\b|petition|on (your|my) behalf/i;   // a Yes / No "do you need …" question names visa / authorization kinds only as examples
  const QTYPES = [
    { t: 'gpa', spec: true, rules: ['gpa_threshold', 'gpa', 'gpa_current'],
      is: (l, o) => /\bgpa\b|grade point average|\bcumulative (grade|average)\b/i.test(l) || (BANDS(o) && !/\b(sat|act|gre|gmat|toefl|ielts|score)\b/i.test(l)) },
    { t: 'visa_type', spec: true, rules: ['visa_expiry', 'visa_conditions', 'immigration_status', 'visa_details'],
      is: l => !ASKS_NEED.test(l) && /\bvisa (type|status|category|class|classification)\b|\b(type|kind|category) of visa\b|\b(current|present) (u\.?s\.? )?(immigration|visa) status\b|^immigration status\b|\bdetails? (on|of|about) (your )?(current )?(visa|immigration)\b/i.test(l) },
    { t: 'auth_kind', spec: true, rules: ['auth_kind'],
      is: l => !ASKS_NEED.test(l) && /\b(kind|type|category) of (work |employment )?authori[sz]ation\b|\b(work|employment) authori[sz]ation (type|category|kind)\b/i.test(l) },
    { t: 'major', rules: ['discipline'],
      is: l => /\b(major|field of study|area of study|discipline|concentration|program of study|course of study)\b/i.test(l) && !/\bnot major\b|major[- ]specific/i.test(l) },
    { t: 'degree', rules: ['degree', 'highest_ed', 'school_level', 'degree_progress', 'business_degree', 'grad_pursuit', 'degree_start_mmyyyy', 'degree_end_mmyyyy', 'grad_date', 'enrolled', 'enrollment_status', 'enrolled_during', 'returning', 'college_years_completed', 'college_year_current', 'undergrad_year', 'hs_diploma', 'hs_grad_year'],
      is: l0 => { const l = l0.replace(/\bdegree (major|field|discipline|concentration|subject|program of study)\b/gi, '$1'); return /\b(degree|level of (education|schooling|study)|highest (level of )?education|year in school|academic (year|standing|level))\b/i.test(l); } },
    { t: 'work_auth', rules: ['visa_expiry', 'authorized', 'any_employer', 'auth_today', 'work_permit', 'citizen_pr', 'spons_now', 'spons_future', 'spons_countries', 'sponsorship_type', 'eligibility_3way', 'on_opt', 'citizenship_country', 'reside_us'],
      is: l => /\bsponsor|\bauthori[sz](ed|ation) to work\b|\bwork authori[sz]ation\b|\beligible to work\b|\b(legally )?(permitted|allowed|able) to work\b|\bwork permit\b|\bcitizen(ship)?\b|\bpermanent resident\b|\bh-?1b\b|\bopt\b|\bcpt\b/i.test(l) },
  ];
  function qtypes(label, opts) {                        // pure (tested): the question types this label (+ options) asks
    const q = label.includes('?') ? label.slice(0, label.indexOf('?') + 1) : label;   // the question itself, not the notes after it ("… If so, upload … to confirm enrollment and GPA")
    const all = QTYPES.filter(t => t.is(q, opts));
    const spec = all.filter(t => t.spec);
    return spec.length ? spec : all;
  }
  // JSA-197: one text box that asks the degree AND the major ("Please include what degree you are currently pursuing in
  // addition to major(s) and any minor(s)") → both from the profile's education entry: "M.S. Applied Data Science". Which
  // entry: the level the question names (bachelor's / undergraduate, master's / graduate), else completed / highest → the
  // highest completed degree, else (current / pursuing / no cue, like the single degree and major rules) the current
  // program. No minor on file → none is written. A list, a date / GPA / school question, or no entry → ask.
  const parts = x => { const p = String(x).split(/\s*(?:\/|&|\+|;|\||,|\band\b)\s*/i).map(y => y.trim()).filter(Boolean); return p.length > 1 ? p : []; };
  function degreeMajor(f, label, opts) {
    const unk = why => ({ status: 'unknown', label, why: 'degree + major in one box: ' + why, qtype: ['degree', 'major'] });
    if (opts.length || !/^(text|textarea)$/.test(f.t || 'text')) return unk('not a text box');
    if (/\b(date|when|graduat\w*|gpa|grade|years?|months?|semesters?|credits?)\b|\b(which|what|name of (the|your)) (school|university|college|institution)\b/i.test(label)) return unk('also asks a date / GPA / school');
    const ed = (P.education || []).filter(e => e && e.degree), lvl = { doctor: 4, master: 3, bachelor: 2, associate: 1 };
    const ym = new Date().toISOString().slice(0, 7);
    const done = ed.filter(e => !e.current && e.end && String(e.end) <= ym).sort((a, b) => (lvl[b.level] || 0) - (lvl[a.level] || 0));
    const l = label.replace(/\bundergraduate\b/gi, 'bachelor');
    const cur = /\b(current(ly)?|pursuing|working (on|towards?)|enrolled|studying|expected|in progress)\b/i.test(l);
    const past = /\b(completed|earned|received|obtained|conferred|awarded|highest|previous|prior)\b/i.test(l);
    let e;
    if (/\bbachelor/i.test(l) && !/\bmaster|\bgraduate\b/i.test(l)) e = ed.find(x => x.level === 'bachelor');
    else if (/\bmaster|\bgraduate (degree|program|studies)\b/i.test(l) && !/\bbachelor/i.test(l)) e = ed.find(x => x.level === 'master');
    else if (cur && past) return unk('asks the current and a completed degree');
    else if (past) e = done[0];
    else e = ed.find(x => x.current);
    if (!e) return unk('no such degree on file');
    const deg = String(e.degree).trim(), major = String(e.major || '').trim();
    const value = !major || deg.toLowerCase().includes(major.toLowerCase()) ? deg : deg + ' ' + major;
    return { status: 'ok', label, rule: 'degree_major', value };
  }
  // ---- JSA-218 helpers (Greenhouse recert 11-05)
  const MON = ['jan', 'feb', 'mar', 'apr', 'may', 'jun', 'jul', 'aug', 'sep', 'oct', 'nov', 'dec'];
  const MON_NAME = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
  const canonLow = x => String(x || '').toLowerCase().replace(/[^a-z0-9]+/g, ' ').trim();
  const ymText = ym => { const m = /^(\d{4})-(\d{2})/.exec(String(ym || '')); return m ? MON_NAME[+m[2] - 1] + ' ' + m[1] : String(ym || ''); };
  // the month-year points named in an option ("February 2028", "Dec 2027", "12/2027") → ['2028-02', …]; a bare year → its month
  // given by `edge` ('start' = January, 'end' = December)
  function ymPoints(o, edge) {
    const SEA = { spring: [1, 5], summer: [6, 8], fall: [9, 12], autumn: [9, 12], winter: [12, 12] }, two = n => String(n).padStart(2, '0');
    const out = [], re = /\b(jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*\.?,?\s+(\d{4})\b|\b(0?[1-9]|1[0-2])\s*\/\s*(\d{4})\b|\b((?:spring|summer|fall|autumn|winter)(?:\s*(?:\/|-|and|or)\s*(?:spring|summer|fall|autumn|winter))*)\s+(\d{4})\b|\b(20\d{2})\b/gi;
    let m; while ((m = re.exec(String(o)))) {
      if (m[5]) { const ss = m[5].toLowerCase().match(/spring|summer|fall|autumn|winter/g); out.push(m[6] + '-' + two(edge === 'end' ? SEA[ss[ss.length - 1]][1] : SEA[ss[0]][0])); continue; }   // "Fall/Winter 2027" → 2027-09 … 2027-12
      if (m[1]) out.push(m[2] + '-' + String(MON.indexOf(m[1].slice(0, 3).toLowerCase()) + 1).padStart(2, '0'));
      else if (m[3]) out.push(m[4] + '-' + String(+m[3]).padStart(2, '0'));
      else out.push(m[7] + (edge === 'end' ? '-12' : '-01'));
    }
    return out;
  }
  // an option as a range of months [lo, hi] (inclusive; null = open): "Before X" → [-, X-1], "After X" → [X+1, -], "X or later" →
  // [X, -], "Between X and Y" / "X - Y" / "X to Y" → [X, Y], one month → [X, X]; none → null
  function ymRange(o) {
    const t = String(o).trim(), p = ymPoints(t, 'start'), pe = ymPoints(t, 'end');
    if (!p.length) return null;
    const step = (ym, d) => { let [y, mo] = ym.split('-').map(Number); mo += d; if (mo < 1) { mo = 12; y--; } if (mo > 12) { mo = 1; y++; } return y + '-' + String(mo).padStart(2, '0'); };
    if (/^(before|prior to|earlier than|until|by)\b/i.test(t)) return [null, step(p[0], -1)];
    if (/^(after|later than)\b/i.test(t)) return [step(pe[0], 1), null];
    if (/\b(or|and) (later|after|beyond)\b|\bonwards?\b|\+$/i.test(t)) return [p[0], null];
    if (/\b(or|and) (earlier|before)\b/i.test(t)) return [null, pe[0]];
    if (p.length >= 2) return [p[0], pe[1]];
    return [p[0], pe[0]];   // one month → [X, X]; a season / bare year → its months
  }
  const inRange = (r, ym) => r && (!r[0] || ym >= r[0]) && (!r[1] || ym <= r[1]);
  const RANGE_OPT = /^(before|prior to|earlier than|after|later than|between)\b|\b(or|and) (later|after|earlier|before)\b|\d{4}\s*(-|–|to)\s*\w/i;
  const gradYm = () => { const e = (P.education || []).find(x => x && x.current && x.end); return e ? String(e.end).slice(0, 7) : null; };
  // the education written out in one text box (JSA-218): every entry of the profile, newest first, + the high school when asked
  function educationList(f, label, opts) {
    if (opts.length || !/^(text|textarea)$/.test(f.t || 'text')) return { status: 'unknown', label, why: 'education_list: not a text box' };
    const ed = (P.education || []).filter(e => e && e.school && e.degree).slice().sort((a, b) => String(b.end || '').localeCompare(String(a.end || '')));
    if (!ed.length) return { status: 'unknown', label, why: 'education_list: no education on file' };
    const ym = new Date().toISOString().slice(0, 7);
    const parts = ed.map(e => e.school + ' — ' + e.degree + ', ' + (e.start ? ymText(e.start) + ' – ' : '') + ymText(e.end)
      + ((e.current || String(e.end) > ym) ? ' (in progress)' : ' (completed)'));
    const hs = P.high_school;
    if (/high school|secondary school/i.test(label)) {
      if (!hs || !hs.name) return { status: 'unknown', label, why: 'education_list: the question asks the high school — none on file (high_school)' };
      parts.push('High school: ' + [hs.name, hs.city, hs.region, hs.country].filter(Boolean).join(', ') + (hs.end ? ' (' + hs.end + ')' : ''));
    }
    return { status: 'ok', label, rule: 'education_list', value: parts.join('. ') + '.' };
  }
  // the places a ranking question lists, in the profile's order (answers.location_rank: open = every U.S. place is fine,
  // first = the home pattern first; JSA-218 follow-up, a Greenhouse employer 11-05). A place outside the U.S. ("Brampton, ON (CAN)") is left out.
  function locationRank(label) {
    const r = R.find(h => h.id === 'location_rank') || {};
    if (!r.open) return { status: 'unknown', label, rule: 'location_rank', why: 'location_rank: no ranking preference on file (answers.location_rank)' };
    const m = label.match(/:\s*([^:]+?)(?:\.\s+(?=[A-Z])|;?\s*(?:please|important|if you)\b|$)/i);
    if (!m) return { status: 'unknown', label, rule: 'location_rank', why: 'location_rank: no list of places in the question' };
    const seg = m[1].replace(/\.$/, '');
    const FOREIGN = /\((?!usa?\b|u\.s\.?a?\b)[A-Z]{2,3}\)|\b(canada|mexico|united kingdom|uk|england|india|china|germany|ireland|singapore|japan|france|netherlands|australia|remote)\b/i;
    const raw = seg.split(seg.includes(';') ? ';' : ',').map(x => x.trim()).filter(Boolean), items = [];
    for (const x of raw) {
      if (FOREIGN.test(x)) { if (/^[A-Za-z .]+$/.test(x) && x.split(/\s+/).length <= 2 && items.length && !seg.includes(';')) items.pop(); continue; }   // "London, UK": the country closes the city before it
      items.push(x);
    }
    if (items.length < 2 && !/^\s*\w/.test(seg)) return { status: 'unknown', label, rule: 'location_rank', why: 'location_rank: no list of places in the question' };
    if (!items.length) return { status: 'unknown', label, rule: 'location_rank', why: 'location_rank: no U.S. place listed' };
    const first = r.first ? RX(r.first) : null;
    const ordered = first ? items.filter(x => first.test(x)).concat(items.filter(x => !first.test(x))) : items;
    return { status: 'ok', label, rule: 'location_rank', value: ordered.join(', ') };
  }
  // JSA-281: the part of a label that asks — its sentences ending in "?" (a long notice before it only explains); no "?" → all
  const BG_Q = /background (check|screen|investigation)|drug (screen|test)/i;
  // JSA-408: an exclusion note ("Do not include VISA or relocation expectations", "(excluding travel)"; NOT "other than …", which can be the subject: "an employee (other than our recruiters)") names words the question is
  // explicitly NOT about — the keyword rules must not match them (the accommodations question hit `relocate` and answered Yes).
  const EXCLUSION_NOTE = /[(\[]\s*(?:please\s+)?(?:do not|don'?t|not|never)\s+(?:include|including|mention|count|consider|list)\b[^)\]]*[)\]]|(?:^|(?<=[.?!)]))\s*(?:please\s+)?(?:do not|don'?t)\s+(?:include|mention|count|consider|list)\b[^.?!]*[.!]?|[(\[]\s*(?:excluding|not including)\b[^)\]]*[)\]]|(?<=\s)(?:do not|don'?t)\s+(?:include|mention|count|consider|list)\b[^).?!]*(?=\)?\s*$)/gi;
  const dropExclusions = l => String(l || '').replace(EXCLUSION_NOTE, ' ').replace(/\s+/g, ' ').trim();
const CITY_COUNTRY = {};   // JSA-410: city → country, for the relocation multi-select (general geography, not his facts; his choice of countries is answers.reloc_other.countries)
  for (const c of ['new york', 'nyc', 'new york city', 'chicago', 'san francisco', 'bay area', 'san jose', 'los angeles', 'seattle', 'boston', 'austin', 'dallas', 'houston', 'atlanta', 'miami', 'washington dc', 'philadelphia', 'denver', 'san diego', 'pittsburgh', 'minneapolis', 'detroit', 'charlotte', 'raleigh', 'nashville', 'salt lake city', 'phoenix', 'baltimore', 'palo alto', 'mountain view', 'menlo park', 'stamford', 'princeton', 'irvine', 'las vegas', 'st. louis', 'kansas city', 'indianapolis', 'cleveland', 'cincinnati', 'tampa', 'orlando', 'boulder', 'ann arbor', 'new haven', 'jersey city', 'brooklyn', 'san mateo', 'redwood city', 'sunnyvale', 'santa clara', 'cupertino', 'oakland', 'sacramento', 'honolulu']) CITY_COUNTRY[c] = 'united states';
  for (const c of ['shanghai', 'beijing', 'shenzhen', 'guangzhou', 'hong kong', 'hangzhou', 'chengdu', 'nanjing', 'wuhan', 'suzhou', 'tianjin', "xi'an", 'chongqing', 'macau']) CITY_COUNTRY[c] = 'china';
  for (const c of ['london', 'bristol', 'amsterdam', 'paris', 'singapore', 'mumbai', 'sydney', 'toronto', 'vancouver', 'montreal', 'dublin', 'berlin', 'frankfurt', 'munich', 'zurich', 'geneva', 'tokyo', 'seoul', 'delhi', 'bangalore', 'bengaluru', 'hyderabad', 'melbourne', 'madrid', 'milan', 'stockholm', 'copenhagen', 'luxembourg', 'dubai', 'tel aviv', 'sao paulo', 'mexico city', 'manchester', 'edinburgh', 'cambridge uk', 'oxford']) CITY_COUNTRY[c] = 'other';
  const US_ST = new Set('al ak az ar ca co ct de dc fl ga hi id il in ia ks ky la me md ma mi mn ms mo mt ne nv nh nj nm ny nc nd oh ok or pa ri sc sd tn tx ut vt va wa wv wi wy alabama alaska arizona arkansas california colorado connecticut delaware florida georgia hawaii idaho illinois indiana iowa kansas kentucky louisiana maine maryland massachusetts michigan minnesota mississippi missouri montana nebraska nevada ohio oklahoma oregon pennsylvania tennessee texas utah vermont virginia washington wisconsin wyoming usa us'.split(' ').concat(['new hampshire', 'new jersey', 'new mexico', 'new york', 'north carolina', 'north dakota', 'rhode island', 'south carolina', 'south dakota', 'west virginia', 'united states', 'district of columbia']));
  // "Cambridge, UK" is not Cambridge, MA: the whole text first, then the suffix after the comma (a U.S. state → the U.S.; China / Hong Kong → China; any other suffix → other); a bare ambiguous name is not in the table, so it is never picked
  const cityCountry = o => {
    const t = String(o).toLowerCase().replace(/\s+/g, ' ').trim();
    if (CITY_COUNTRY[t]) return CITY_COUNTRY[t];
    const m = /^([^,(]+?)\s*(?:,|\()\s*([^,)]+)\)?/.exec(t);
    if (!m) return undefined;
    const suf = m[2].trim();
    if (US_ST.has(suf)) return 'united states';
    if (/^(china|prc|hk|hong kong|macau|macao)( sar)?$/.test(suf)) return 'china';
    return CITY_COUNTRY[m[1].trim()] === 'china' && !suf ? 'china' : 'other';
  };
  function questionPart(label) {
    const qs = String(label || '').split(/(?<=[.?!])\s+/).filter(x => /\?\s*\)?\s*$/.test(x.trim()));
    return qs.length ? qs.join(' ') : String(label || '');
  }
  const SECOND_MAJOR = /\b(second(ary)?|double|additional|2nd|other) (major|discipline|field( of study)?|concentration)\b|\bminor\b|\bmajor\s*(#?\s*2|two)\b/i;
  const UNDERGRAD = /\bunder\s?-?grad(uate)?\b|\bbachelor'?s?\b|\bb\.\s?[as]\.?(?=\s|$)|\bcollege major\b/i;
  function majorWhich(label) {                          // pure given the label (tested): 'second' | 'bachelor' | null (= the default, his current degree)
    if (SECOND_MAJOR.test(label) && !/\bmajor(s|\(s\))?(?!\w)[^?]{0,30}(\band\b|&|\/)\s*(any )?minor|\bin addition to\b/i.test(label)) return 'second';   // "major and minor/concentration?" asks the major (Protective 11-02)
    if (UNDERGRAD.test(label) && !/\b(master|graduate (school|program|degree|studies)|post\s?-?grad|m\.\s?s\.|ph\.?\s?d)\b/i.test(label.replace(/\bunder\s?-?graduate\b/ig, ' '))) return 'bachelor';
    return null;
  }
  function majorAnswer(f, label, opts, which) {
    if (which === 'second') {
      const sm = (P.answers.secondary_major || {}).text;
      if (sm) { const o = opts.length ? opts.find(x => canonLow(x) === canonLow(sm)) : sm; if (o) return { status: 'ok', label, rule: 'second_major', value: o }; }
      return { status: 'ok', label, rule: 'second_major', value: '', leave: true, why: 'second major / minor: none on file — left empty (asked when required)' };
    }
    const ed = (P.education || []).find(e => e.level === 'bachelor');
    if (!ed || !ed.major) return { status: 'unknown', label, rule: 'discipline', why: 'undergrad major: no bachelor entry in the profile' };
    if (!opts.length) return { status: 'ok', label, rule: 'discipline:bachelor', value: ed.major };
    const o = opts.find(x => canonLow(x) === canonLow(ed.major)) || opts.find(x => String(x).split(/\s*[\/,&]\s*|\s+and\s+/).some(y => canonLow(y) === canonLow(ed.major)));
    return o ? { status: 'ok', label, rule: 'discipline:bachelor', value: o }
      : { status: 'unknown', label, rule: 'discipline:bachelor', ask: true, why: 'undergrad major ' + ed.major + ': no such option — ask the user' };
  }
  // JSA-281 (Joey 2026-11-10, a Greenhouse employer): "Have you previously applied to <company>?" — Yes when the tracker holds an
  // application to that company dated before today (within "the last N months / years" when the question says so), else No.
  // The company: ctx.company, else a tracker company named in the question. Unknown company, no tracker, or a browser
  // copy of the tracker that is not from today → ask the user.
  // JSA-286: the first 2–3 sentences of a cover letter body (salutation and sign-off dropped), '' when there is none.
  function coverNote(cover) {
    const lines = String(cover || '').replace(/\r/g, '').split('\n');
    let a = 0; while (a < lines.length && !lines[a].trim()) a++;
    if (a < lines.length && /^\s*(dear|hello|hi|to whom)\b/i.test(lines[a])) {   // only the salutation clause goes; text after its comma stays
      const rest = lines[a].replace(/^\s*(?:dear|hello|hi|to whom)\b[^,\n]*(?:,|$)\s*/i, '').trim();
      if (rest) lines[a] = rest; else a++;
    }
    let b = lines.findIndex((l, i) => i >= a && l.trim().length <= 40 && /^\s*(sincerely|best regards|kind regards|warm regards|regards|best|thank you|thanks|many thanks|respectfully|cordially|yours|with (gratitude|appreciation)|all the best)\b[^.?\n]{0,30}$/i.test(l));
    if (b < 0) b = lines.length;
    const body = lines.slice(a, b).join('\n').replace(/\s*\n+\s*/g, '\n').trim();
    if (!body) return '';
    const ABBR = /\b(?:[A-Za-z]\.){1,}[A-Za-z]?\.?$|\b(?:e\.g|i\.e|etc|vs|Mr|Mrs|Ms|Dr|Inc|Ltd|Corp|St)\.$/;
    const sents = []; let cur = '';
    for (const piece of body.split(/(?<=[.!?])\s+(?=[A-Z0-9"'(])|\n/)) {
      cur = cur ? cur + ' ' + piece.trim() : piece.trim();
      if (ABBR.test(cur) && !/\n/.test(piece)) continue;
      if (/[.!?]["')]?$/.test(cur)) { sents.push(cur); cur = ''; }
    }
    if (cur) sents.push(cur);
    for (const n of [3, 2, 1]) { const t = sents.slice(0, n).join(' '); if (t.length <= 500) return sents.length ? t : ''; }
    return '';   // even the first sentence is over 500 characters: nothing is typed (never cut inside a sentence)
  }
  function appliedBefore(label, opts, ctx) {
    const ask = why => ({ status: 'unknown', label, rule: 'applied_before', ask: true, why: 'applied before: ' + why });
    const d = new Date(), today = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
    if (!APPLIED || !Array.isArray(APPLIED.rows)) return ask('no tracker (data/store/applications.jsonl) — ask the user');
    if (APPLIED.date !== today) return ask('the tracker copy is from ' + APPLIED.date + ' — ask the user (or rebuild the bundle)');
    const nl = ' ' + coNorm(label) + ' ';
    const co = coNorm(ctx.company) || (APPLIED.rows.map(r => coNorm(r.company)).filter(c => c.length >= 3).sort((a, b) => b.length - a.length).find(c => nl.includes(' ' + c + ' ')) || '');
    if (!co) return ask('which company is meant is unknown (no ctx.company) — ask the user');
    const w = label.match(/\b(?:last|past) (?:\d+\s*(?:-|–|to)\s*)?(\d+) (month|year|day)s?\b/i) || (/\b(?:last|past) year\b/i.test(label) ? [null, '1', 'year'] : null);   // JSA-333: a range ("last 12-18 months") = its longer bound
    let since = '';
    if (w) { const t = new Date(d); if (/month/i.test(w[2])) t.setMonth(t.getMonth() - +w[1]); else if (/year/i.test(w[2])) t.setFullYear(t.getFullYear() - +w[1]); else t.setDate(t.getDate() - +w[1]);
      since = `${t.getFullYear()}-${String(t.getMonth() + 1).padStart(2, '0')}-${String(t.getDate()).padStart(2, '0')}`; }
    // JSA-376: the same company = the same FULL name (only legal-form words aside); a matching core alone ("Prior Labs" /
    // "Prior Technologies") is a look-alike — never "applied before: Yes", the user is asked.
    const fullN = c => String(c || '').toLowerCase().replace(/&/g, ' and ').replace(/\.com\b/g, ' ').replace(/[^a-z0-9]+/g, ' ')
      .replace(/\band (co|company)\b/g, ' ').replace(/\b(inc|incorporated|llc|l l c|corp|corporation|co|company|ltd|limited|plc|lp|llp|the)\b/g, ' ').replace(/\s+/g, ' ').trim();
    const labelN = ' ' + fullN(label) + ' ';   // no ctx.company: the tracker company named in the question, by its full name
    const full = fullN(ctx.company) || (APPLIED.rows.map(r => fullN(r.company)).filter(c => c.length >= 3 && coNorm(c) === co && labelN.includes(' ' + c + ' ')).sort((a, b) => b.length - a.length)[0]) || co;
    const sameFull = r => fullN(r.company) === full;
    const sameCore = r => { const c = coNorm(r.company); return c === co || (c.length >= 5 && co.length >= 5 && (c.startsWith(co + ' ') || co.startsWith(c + ' '))); };
    const inRange = r => r.applied_on < today && r.applied_on >= since;
    const hit = APPLIED.rows.find(r => sameFull(r) && inRange(r));
    const alike = !hit && APPLIED.rows.find(r => sameCore(r) && !sameFull(r) && inRange(r));
    if (alike) return ask('the tracker has ' + alike.company + ' ' + alike.applied_on + ', a different name from ' + (ctx.company || full) + ' — ask the user');
    const cut = label.split(/\b(?:as a reminder|reminder:|please note|note:)/i)[0], askPart = /\?/.test(cut) ? cut : label;   // cut only when the question is before the marker (review: a leading "As a reminder, … Have you applied …?")   // JSA-333 (a Greenhouse employer 11-12): a trailing reminder about "this position" / "the current season" is not the question
    if (hit && /\bthis (role|position|job|opening|posting|requisition|internship|program)\b(?![^?]{0,30}\bor (any )?(another|other|any)\b)|recruiting (season|cycle)|\bthis (year|season|cycle)\b/i.test(askPart))
      return ask('the tracker has ' + hit.company + ' ' + hit.applied_on + ', but the question asks about one role / season — ask the user');
    const yes = !!hit;
    if (!opts.length) return { status: 'ok', label, rule: 'applied_before', value: yes ? 'Yes' : 'No', why: hit ? 'tracker: ' + hit.company + ' ' + hit.applied_on : 'tracker: none before today' };
    const o = yesNo(opts, yes);
    return o ? { status: 'ok', label, rule: 'applied_before', value: o, why: hit ? 'tracker: ' + hit.company + ' ' + hit.applied_on : 'tracker: none before today' }
      : ask('no ' + (yes ? 'Yes' : 'No') + ' option among ' + opts.slice(0, 4).join(' / '));
  }
  // JSA-336 (AMAT 11-12): the hiring company's name (ctx.company, or a tracker company) masked as "the company", so a rule
  // word inside a name ("a Workday employer", "Prior Labs") never decides the question. A name of two or more words (the full
  // name, or its core without Inc / Labs …) is masked in any case; a one-word name only when capitalised, and only for the
  // hiring company — a one-word tracker core ("Applied" of "Applied Labs") would mask the plain word (review 2026-11-16).
  let coMaskTracker = null;
  const coMaskRes = (name, own) => {
    const raw = String(name || '').toLowerCase().replace(/&/g, ' and ').replace(/[^a-z0-9]+/g, ' ').trim().split(' ').filter(Boolean);
    const core = coNorm(name).split(' ').filter(Boolean);
    return [raw, core].filter((w, i, a) => w.length && w.join(' ').length >= 3 && (w.length >= 2 || own) && (i === 0 || w.join(' ') !== a[0].join(' ')))
      .map(w => ({ one: w.length === 1, re: new RegExp('\\b' + w.map(x => x.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')).join('[^a-z0-9]+(?:(?:and|the|of)[^a-z0-9]+)?') + '\\b', 'gi') }));
  };
  function coMask(label, ctx) {
    if (!coMaskTracker) coMaskTracker = (APPLIED && Array.isArray(APPLIED.rows) ? [...new Set(APPLIED.rows.map(r => r.company).filter(Boolean))] : [])
      .sort((a, b) => b.length - a.length).flatMap(c => coMaskRes(c, false));
    const own = ctx && ctx.company ? coMaskRes(ctx.company, true) : [];
    let out = label;
    for (const { one, re } of [...own, ...coMaskTracker]) out = out.replace(re, m => !one || /^[A-Z0-9]/.test(m) ? 'the company' : m);
    return out;
  }
  // an e-mail box that asks for an address AT the company / as its employee — he has none; never his personal e-mail
  const EMPLOYER_MAIL = /\bif (yes|so)\b|\bif you (answered|selected|checked|said) .?yes|\b(former|previous|prior|current|existing) (employee|worker|intern|associate|contractor)s?\b|\b(previously|formerly|currently) (employed|worked)\b|\b(employee|work|company|corporate|business|internal|staff|associate)('?s)? e-?mail|\bthe company('?s)? (work |corporate )?e-?mail/i;
  // JSA-381: a question that LISTS countries and asks whether he is a citizen / passport holder / dual citizen / permanent
  // resident / refugee in ANY of them ("For any of the countries listed below: … China(PRC), Cuba, …" — export-control lists).
  // It asks about those countries, not the US protected-individual question citizen_pr answers (F-1 → No: it answered this one
  // from the wrong type). Grounded only in the facts: citizenship on file AND named in the list → Yes; not in the list → ask (a
  // passport / permanent residence / refugee status elsewhere is not on file, so No cannot be said); no citizenship on file → ask.
  const COUNTRY_LIST_CUE = /\b(any|one) of (the|these|those) (following |listed )?countr(y|ies)\b|\bcountr(y|ies) (listed|named) (below|here|following)|\b(the )?following countr(y|ies)\b|\bthe countr(y|ies) (listed )?below\b|\blisted below\b/i;
  const COUNTRY_TIE_Q = /\bcitizen(ship)?\b|\bnational\b|\bpassport\b|\bpermanent residen|\brefugee\b|\basylum\b/i;
  function countryListQuestion(label) {   // pure (tested): the list text after the cue when the label is a country-list question about ties, else ''
    const m = COUNTRY_LIST_CUE.exec(label);
    if (!m || !COUNTRY_TIE_Q.test(label) || /\b(sponsor|authori[sz]ed to work|eligible to work)\b/i.test(label)) return '';
    const rest = label.slice(m.index + m[0].length).replace(/^[^,;:]{0,40}:/, '').replace(/^\s*(listed |named )?(below|here)\b/i, '');   // the cue's own tail ("… listed below:") is not a list item
    return (rest.match(/[,;]/g) || []).length >= 2 ? rest : '';
  }
  function countryListAnswer(label, opts) {
    const list = countryListQuestion(label);
    if (!list) return null;
    if (opts.length && !yesNo(opts, true)) return null;   // a list of countries to pick from, not a yes / no question
    // no options (a text box / a lazily loaded list): only a yes / no-shaped question — "Which of the following countries are you a citizen of?" asks for a country
    if (!opts.length && (!/\b(are you|do you|have you|did you|have been granted|is your)\b/i.test(label) || /^\W*(which|what|select|choose|please (select|choose))\b|\b(select|choose|e\.g\.|which of)\b|country of citizenship/i.test(label))) return null;
    const home = String(((P.answers || {}).citizenship_country || {}).text || (P.work_auth || {}).citizenship || '').trim();
    const ask = why => ({ status: 'unknown', label, rule: 'citizenship_country', ask: true, qa_ok: true, why });
    if (!home) return ask('country-list citizenship question: no country of citizenship on file');
    const norm = x => String(x).toLowerCase().replace(/\([^)]*\)/g, ' ').replace(/[^a-z' -]/g, ' ').replace(/\s+/g, ' ').replace(/^(the|or|and) /, '').trim();
    const items = list.split(/[,;•\n]|\s(?:or|and)\s/i).map(norm).filter(Boolean);   // whole list items, not substrings: "South Sudan" is not "Sudan"
    const h = norm(home);
    const named = items.includes(h) || (h === 'china' && items.includes("people's republic of china"));
    if (!named) return ask('country-list citizenship question: ' + home + ' is not in the list, and a passport / permanent residence / refugee status elsewhere is not on file');
    const v = opts.length ? yesNo(opts, true) : 'Yes';
    return { status: 'ok', label, rule: 'citizenship_country', value: v, why: 'citizen of ' + home + ', named in the list' };
  }
  function answerByRules(f, ctx) {
    const label = (f.l || f.label || '').replace(/\s+/g, ' ').trim();
    const opts = f.o || f.options || [];
    const cl = countryListAnswer(label, opts); if (cl) return cl;   // JSA-381: before the keyword rules (citizen_pr would take it)
    const hl = dropExclusions(label);
    const hits = R.filter(r => r.q.test(hl) && !(r.not && r.not.test(hl)) && !(r.when && !r.when(hl)) && !(NAME_RULES.has(r.id) && ynQuestion(label) && ynBox(f)) && !(f._noThreshold && r.id === 'gpa_threshold'));   // r.not: label words that rule the rule out
    const refs = hits.find(h => h.id === 'references');   // JSA-210: references = other people's contact details — never his own name / e-mail / phone
    if (refs) return refs.text && !opts.length ? { status: 'ok', label, rule: 'references', value: refs.text }
      : { status: 'unknown', label, rule: 'references', ask: true, qa_ok: true, why: 'references: other people\'s contact details — none on file; the user gives them (never his own e-mail / phone / name)' };
    if (hits.some(h => h.id === 'spons_future' || h.id === 'spons_now') && sponsNoTime(label, questionPart(label), f))
      return { status: 'unknown', label, rule: 'spons_future', ask: true, no_auto: true, why: 'sponsorship question with no time word (now / in the future): the user answers each one (Joey 2026-11-16, JSA-361)' };
    const mailQ = hits.some(h => h.id === 'email' || h.id === 'secondary_email');
    const masked = mailQ || APPLIED_Q.test(label) ? coMask(label, ctx) : label;   // JSA-336: a company name is not a rule word
    if (mailQ && EMPLOYER_MAIL.test(masked))
      return { status: 'unknown', label, rule: 'email', ask: true, no_auto: true, why: 'an e-mail at the company / as its employee (or an "if yes" follow-up): none on file — never the personal e-mail; the user answers it (JSA-336)' };
    const appliedQ = APPLIED_Q.test(masked);
    if (!appliedQ && hits.some(h => h.id === 'applied_before')) hits.splice(hits.findIndex(h => h.id === 'applied_before'), 1);
    // JSA-218: questions whose answer is built from the profile's facts, decided before the type routing
    if (hits.some(h => h.id === 'education_list')) return educationList(f, label, opts);
    if (hits.some(h => h.id === 'location_rank') && !opts.length && /^(text|textarea)$/.test(f.t || 'text')) return locationRank(label);
    if (hits.some(h => h.id === 'hs_name')) {
      const hs = P.high_school || {};
      if (!opts.length && /^(text|textarea)$/.test(f.t || 'text')) return hs.name ? { status: 'ok', label, rule: 'hs_name', value: hs.name } : { status: 'unknown', label, rule: 'hs_name', why: 'hs_name: no high school on file (high_school)' };
      const o = hs.name && opts.find(x => canonLow(x) === canonLow(hs.name));
      if (o) return { status: 'ok', label, rule: 'hs_name', value: o };
      hits.splice(hits.findIndex(h => h.id === 'hs_name'), 1);   // a region / type list ("Asia") is not the name: other rules or a saved answer
    }
    if (hits.some(h => h.id === 'name_pronunciation')) {
      const np = R.find(h => h.id === 'name_pronunciation');
      return np.text && !opts.length ? { status: 'ok', label, rule: 'name_pronunciation', value: np.text }
        : { status: 'unknown', label, rule: 'name_pronunciation', ask: true, qa_ok: true, why: 'name pronunciation: none on file (answers.name_pronunciation) — ask the user; never the phone number or the plain name' };
    }
    if (hits.some(h => h.id === 'hiring_manager_note')) {   // JSA-286
      if (opts.length || f.t === 'checkbox' || qaFindAll(label).length) hits.splice(hits.findIndex(h => h.id === 'hiring_manager_note'), 1);
      else if ((ctx || {}).cover === undefined) hits.splice(hits.findIndex(h => h.id === 'hiring_manager_note'), 1);   // a caller that has no cover to give: the box is handled as before
      else { const note = coverNote((ctx || {}).cover);
        return note ? { status: 'ok', label, rule: 'hiring_manager_note', value: note, why: 'the first sentences of this job\'s cover letter (Joey 2026-11-10)' }
                    : { status: 'ok', label, rule: 'hiring_manager_note', value: '', leave: true, why: 'no cover letter text: the optional box stays empty' }; }
    }
    if (hits.some(h => h.id === 'applied_before')) return appliedBefore(label, opts, ctx || {});
    if (appliedQ && hits.some(h => ['prev_employed', 'prior_employer'].includes(h.id))) {   // "employed by OR applied to X?": an application makes it Yes
      const ab = appliedBefore(label, opts, ctx || {});
      if (ab.status !== 'ok' || /^(yes|i have)\b/i.test(String(ab.value).trim())) return ab;
    }
    // JSA-281 (a Workday employer 11-10): a long notice may name a criminal background check AND ask about convictions — what the
    // question sentence (the part ending in "?") asks decides; both or neither there → ask the user, never a guess
    if (hits.some(h => h.id === 'conviction')) {
      const ask = questionPart(label), conv = CONVICT_Q.test(ask), bg = BG_Q.test(ask.replace(CONVICT_Q, ' '));
      const cv = R.find(h => h.id === 'conviction');
      if (conv && !bg) {
        if (cv.yes === undefined) return { status: 'unknown', label, rule: 'conviction', ask: true, why: 'conviction question: no fact on file (answers.conviction) — ask the user' };
        hits.splice(0, hits.length, cv);
      } else if (!conv && bg && hits.some(h => h.id === 'background_drug')) hits.splice(hits.findIndex(h => h.id === 'conviction'), 1);
      else return { status: 'unknown', label, rule: 'conviction', ask: true, why: 'conviction / background wording: the question part is unclear — ask the user' };
    }
    // JSA-281 (a Greenhouse employer, a Greenhouse employer 11-10): which major — an undergrad major is the bachelor's (Economics), a second /
    // secondary / double major or a minor is none on file (left empty when optional, asked when required)
    if (hits.some(h => h.id === 'discipline')) { const which = majorWhich(label); if (which) return majorAnswer(f, label, opts, which); }
    // a race list (options like "White (Not Hispanic or Latino)" …) under a label that also says "Hispanic" is the race question (a Workday employer 2026-11-01)
    const raceR = R.find(r => r.id === 'race'), hispR = R.find(r => r.id === 'hispanic');
    if ((hits.some(r => r.id === 'race') || hits.some(r => r.id === 'hispanic')) && opts.some(o => /\basian\b/i.test(o)))
      hits.splice(0, hits.length, raceR);                 // options are race categories → the race question
    else if (hits.some(r => r.id === 'race') && opts.length && opts.some(o => /^not hispanic/i.test(String(o).trim())) && !opts.some(o => /\basian\b/i.test(o)))
      hits.splice(0, hits.length, hispR);                 // "Race/Ethnicity" with only Hispanic / Not Hispanic → the ethnicity question
    // a long legal paragraph names many topics (an employer VEVRAA text: gender, race, disability, veteran …) — 2026-11-01:
    // 1) its last sentence is the question ("Please indicate your gender."): answer that when it names one topic
    if (hits.length > 1 && label.length > 300 && !f._tail) {
      const sents = label.split(/(?<=[.?!])\s+/).filter(x => x.trim());
      for (const k of [1, 2]) {
        const tail = sents.slice(-k).join(' ');
        if (tail.length < 300) {
          const a = answerFor(Object.assign({}, f, { l: tail, _tail: true }), ctx);
          if (a.status === 'ok') return Object.assign(a, { label });
        }
      }
    }
    // 2) else keep the rules whose topic also appears in the OPTIONS when that leaves exactly one
    if (hits.length > 1 && opts.length && label.length > 300) {
      const ot = opts.join(' | ');
      let byOpts = hits.filter(r => r.q.test(ot));
      if (/\basian\b/i.test(ot) && hits.some(r => r.id === 'race')) byOpts = hits.filter(r => r.id === 'race');   // a list with an Asian option is the race question
      if (byOpts.length >= 1 && new Set(byOpts.map(r => r.id)).size === 1) hits.splice(0, hits.length, ...byOpts);
    }
    // ---- question-type routing (JSA-200, Joey 2026-11-05): decide WHAT the question asks first, then let only that
    // type's rules answer. A specific type (GPA, visa type, kind of authorization) beats a general one (major, work
    // authorization / sponsorship, degree); two specific types, or two general ones with no specific → ask Joey.
    const qt = qtypes(label, opts);
    if (qt.length && !qt[0].spec && qt.some(t => t.t === 'degree') && qt.some(t => t.t === 'major')) return degreeMajor(f, label, opts);   // one box, two facts (a Greenhouse employer 10-28 got only "Master's Degree", JSA-197)
    if (qt.length && hits.length) {
      if (qt[0].spec) {                                 // specific: only that type's rules; none fits → ask
        if (qt.length > 1) return { status: 'unknown', label, why: 'question type unclear: ' + qt.map(t => t.t).join(' / '), qtype: qt.map(t => t.t) };
        const routed = hits.filter(h => qt[0].rules.includes(h.id));
        if (!routed.length) return { status: 'unknown', label, why: 'question type ' + qt[0].t + ': no rule of that type fits', qtype: qt[0].t };
        hits.splice(0, hits.length, ...routed);
      } else {                                          // general: drop rules of OTHER typed families; other rules stay
        const own = new Set(qt.flatMap(t => t.rules));
        const other = new Set(QTYPES.filter(t => !qt.includes(t)).flatMap(t => t.rules));
        const famsHit = qt.filter(t => hits.some(h => t.rules.includes(h.id)));
        if (famsHit.length > 1) return { status: 'unknown', label, why: 'question type unclear: ' + famsHit.map(t => t.t).join(' / '), qtype: famsHit.map(t => t.t) };
        if (hits.some(h => own.has(h.id))) { const keep = hits.filter(h => !other.has(h.id) || own.has(h.id)); hits.splice(0, hits.length, ...keep); }   // a rule in this type AND another (visa_expiry: work_auth + visa_type) stays
      }
    }
    if (!hits.length) return { status: 'unknown', label };
    // "… for any employer" decides the question even when "sponsorship" also appears (a Workday employer 10-28: F-1/CPT → No)
    // a privacy notice whose options are only "I Consent / I Agree / I Acknowledge" is the data consent, whatever else it mentions (Joey 2026-10-30)
    const consentOpts = opts.length && opts.every(o => /^(i )?(consent|agree|accept|acknowledge|understand)\b/i.test(String(o).trim()));
    // "check all that apply (… visa sponsorship …)" with city options is the office pick, not the sponsorship question (a Lever employer 2026-10-30)
    const placeOpts = opts.length && !opts.some(o => /^(yes|no)\b/i.test(String(o).trim()));
    const r = hits.find(h => h.id === 'any_employer') || (consentOpts && hits.find(h => h.id === 'data_consent'))
      || (placeOpts && hits.find(h => h.id === 'office_all'))
      || (/office|on[- ]?site/i.test(label) && hits.find(h => h.id === 'data_consent') && hits.find(h => h.id === 'onsite')) || hits[0];   // "I acknowledge … in-office culture … willing to work in the office" = on-site (Gecko 2026-10-31)
    if (r.consent) return { status: 'consent', label, rule: r.id };
    const refHit = hits.find(h => REF_IDS.includes(h.id));
    if (refHit) return referralAnswer(f, label, opts, refHit, hits, ctx);
    const agree = hits.length > 1 && hits.every(h => typeof h.yes === 'boolean' && h.yes === hits[0].yes && !h.pick && !h.text && !h.jd && !h.all && !h.under);   // every rule that fits gives the same Yes / No → that answer (Erie 11-04: other_name / prior_employer / prev_employed all No)
    if (hits.length > 1 && !agree && hits[1].id !== r.id && !(r.id === 'onsite' && hits.every(h => ['onsite', 'data_consent'].includes(h.id))) && !['auth_today', 'spons_now', 'spons_future', 'spons_countries', 'any_employer', 'authorized'].includes(r.id) && !/^(sms|future_contact|marketing|terms|terms_sms|data_consent)$/.test(r.id)) {
      // two different rules → ambiguous unless the first is a known-specific rule
      const specific = ['accommodation_need', 'course_done', 'visitor_visa', 'eeo_furnish', 'enrolled_fall', 'reloc_other', 'video_record', 'education_level_now', 'location_full', 'location_rank', 'hs_name', 'name_pronunciation', 'visa_expiry', 'ft_start', 'education_list', 'secondary_email', 'gpa_threshold', 'visa_conditions', 'local_area', 'military_status', 'permanent_address', 'address_full', 'good_standing', 'college_years_completed', 'college_year_current', 'legal_dispute', 'license_state_class', 'citizen_pr', 'visa_details', 'interviewed_before', 'undergrad_year', 'noncompete_detail', 'know_employee', 'debarred', 'industry_investor', 'industry_side_role', 'other_jobs', 'conflict_interest', 'eligibility_3way', 'language_level', 'contact_employer_cond', 'contact_employer', 'interview_travel', 'applied_before', 'conviction', 'background_drug', 'driver_license', 'work_arrangement', 'city_state_zip', 'immigration_status', 'prev_employed', 'prior_employer', 'resume_employer', 'internship_mandatory', 'enrolled_during', 'office_all', 'intern_when', 'has_preferred', 'avail_season', 'middle_initial', 'employer', 'lives_outside_us', 'school_level', 'relative_names', 'relatives', 'certify', 'preferred_full_name', 'preferred_last_name', 'preferred_name', 'full_time_summer', 'python_r', 'hours', 'noncompete', 'first_name', 'last_name', 'email', 'phone_device', 'phone_code', 'phone', 'linkedin', 'hispanic', 'transgender', 'orientation', 'pronouns', 'dob_minor', 'age18', 'start_date', 'grad_date', 'highest_ed', 'gpa', 'zip', 'city', 'state', 'address', 'school', 'degree', 'discipline', 'location', 'full_name', 'auth_kind', 'start_month', 'start_year', 'end_month', 'end_year'];
      if (!specific.includes(r.id)) return { status: 'unknown', label, why: 'ambiguous: ' + hits.map(h => h.id).join('/') };
    }
    // JSA-310 (Joey 2026-11-11): authorization → Yes. "…for any employer WITHOUT (current or future) sponsorship?" is the
    // sponsorship question (a Workday employer 10-28) → its flipped answer; "PERMANENTLY authorized?" → answers.any_employer.permanent;
    // otherwise the unrestricted Yes / "authorized for any employer" option wins; "with restrictions" / "require sponsorship"
    // only when no plain Yes is offered (the JSA-291 path below); never "not authorized"
    // JSA-310 (KBR 11-01, audit 11-11): "authorized to work … AS a (i) U.S. citizen or national; or (ii) permanent resident?"
    // asks for citizen / PR status — answered from answers.citizen_pr (No), never the authorization Yes; examples ("e.g.,
    // U.S. citizen, permanent resident, F-1 OPT") only illustrate and do not count
    if (['authorized', 'any_employer'].includes(r.id) && CIT_STATUS_Q.test(noExamples(label)) && typeof (P.answers.citizen_pr || {}).yes === 'boolean') {
      const v = opts.length ? yesNo(opts, P.answers.citizen_pr.yes) : (P.answers.citizen_pr.yes ? 'Yes' : 'No');
      return v ? { status: 'ok', label, rule: 'citizen_pr', value: v } : { status: 'unknown', label, rule: 'citizen_pr', ask: true, why: 'authorization as a citizen / permanent resident: no Yes / No option' };
    }
    if (CLAIM_AUTH && ['authorized', 'any_employer'].includes(r.id)) {
      const ae = P.answers.any_employer || {};
      if (WITHOUT_SPONS.test(label) && typeof (P.answers.spons_future || {}).yes === 'boolean') {
        const need = (!SPONS_LATER.test(label) && SPONS_NOW_ONLY.test(label) && typeof (P.answers.spons_now || {}).yes === 'boolean') ? P.answers.spons_now.yes : P.answers.spons_future.yes;
        const v = opts.length ? yesNo(opts, !need) : (need ? 'No' : 'Yes');
        return v ? { status: 'ok', label, rule: r.id, value: v, inverted: true } : { status: 'unknown', label, rule: r.id, why: r.id + ': without-sponsorship wording, no Yes / No option', options: opts.slice(0, 8) };
      }
      if (PERM_Q.test(label) && typeof ae.permanent === 'boolean') {
        const v = opts.length ? yesNo(opts, ae.permanent) : (ae.permanent ? 'Yes' : 'No');
        return v ? { status: 'ok', label, rule: 'any_employer', value: v } : { status: 'unknown', label, rule: 'any_employer', why: 'permanently authorized: no Yes / No option', options: opts.slice(0, 8) };
      }
      if (opts.length) {
        const s = opts.map(o => String(o).trim());
        const his = x => !NOT_AUTH_OPT.test(x) && !/^(no|false)\b/i.test(x) && !NOT_HIS_YES.test(x) && !/\b(present|current) (u\.?s\.? |united states )?employer only\b|\bonly my (present|current)\b|\bwith (some )?restrictions?\b|\b(requir|need)\w*\b[^.]{0,80}\bsponsor|temporary|unknown|prefer not/i.test(x);
        const o = s.find(x => his(x) && ANY_EMP_OPT.test(x)) || s.find(x => his(x) && /^(yes|true)\b/i.test(x))
          || s.find(x => his(x) && /^(i am|i'm|i have)\b/i.test(x) && /\b(authori[sz]ed|eligible|permitted|entitled)\b/i.test(x));
        if (o) return { status: 'ok', label, rule: r.id, value: opts[s.indexOf(o)], claim: true };
        if (s.some(x => /^(no|false)\b/i.test(x) || NOT_AUTH_OPT.test(x)) && !s.some(x => /\bwith (some )?restrictions?\b/i.test(x) || (SPONS_OPT.test(x) && !NO_SPONS_OPT.test(x))))   // the only Yes claims citizenship / permanence / no sponsorship, no restricted option: a No would say "not authorized" (DeepSeek case 11-11)
          return { status: 'unknown', label, rule: r.id, ask: true, why: 'work authorization: no Yes he can claim and no "with restrictions" / "require sponsorship" option — Joey decides (never "not authorized")' };
      }
    }
    // JSA-291 (Joey 2026-11-10, fix A): a STATUS LIST (3+ statements, e.g. "authorized for any employer / require sponsorship /
    // not authorized") is not the yes/no "for any employer?" question — its negative statement means "no authorization at all",
    // which is false for F-1 / CPT. Pick "Yes, with restrictions", else the "require sponsorship" statement; never "not authorized";
    // neither offered → ask the user (an employer 11-06, a Greenhouse employer 10-31, a Greenhouse employer 10-28)
    if (RESTRICTED && ['authorized', 'any_employer'].includes(r.id) && opts.length > 2 && opts.some(o => ANY_EMP_OPT.test(String(o)) || NOT_AUTH_OPT.test(String(o)))) {
      const s = opts.map(o => String(o).trim());
      const o = s.find(x => /^yes,? (but )?with (some )?restrictions?\b/i.test(x)) || s.find(x => SPONS_OPT.test(x) && !NO_SPONS_OPT.test(x) && !NOT_AUTH_OPT.test(x))
        || s.find(x => SPONS_OPT.test(x) && !NO_SPONS_OPT.test(x) && !/^no\b/i.test(x));   // "…not currently authorized and will require sponsorship" is still the sponsorship statement
      return o ? { status: 'ok', label, rule: 'any_employer', value: opts[s.indexOf(o)] }
        : { status: 'unknown', label, rule: 'any_employer', ask: true, why: 'work-authorization status list with no "require sponsorship" / "with restrictions" statement — Joey decides (never "not authorized")' };
    }
    // options that say "for ANY employer" / "without restriction" turn a generic authorization question into the any-employer one (F-1: No)
    if (RESTRICTED && r.id === 'authorized' && opts.some(o => /^yes,? (but )?with (some )?restrictions?\b/i.test(String(o).trim())))   // the precise F-1 / CPT answer when offered (a Workday employer 2026-11-01)
      return { status: 'ok', label, rule: r.id, value: opts.find(o => /^yes,? (but )?with (some )?restrictions?\b/i.test(String(o).trim())) };
    if (RESTRICTED && r.id === 'authorized' && opts.length && opts.filter(o => /^(yes|i am|i have)\b/i.test(String(o).trim())).length && opts.filter(o => /^(yes|i am|i have)\b/i.test(String(o).trim())).every(o => UNRESTRICTED.test(o))) {
      const no = yesNo(opts, false);                      // every "yes" claims unrestricted / permanent / citizen → the honest pick is No
      if (no) return { status: 'ok', label, rule: 'any_employer', value: no };
    }
    if (RESTRICTED && r.id === 'authorized' && opts.some(o => /any employer|without (any )?restriction|unrestricted/i.test(o))) {
      const o = opts.find(x => /^yes,? (but )?with (some )?restrictions?\b/i.test(x.trim())) || opts.find(x => /^no\b/i.test(x.trim()) && /any employer|restriction/i.test(x)) || yesNo(opts, false);   // "Yes, with restrictions" = F-1 on CPT (a Workday employer 2026-11-01)
      return o ? { status: 'ok', label, rule: 'any_employer', value: o } : { status: 'unknown', label, why: 'any-employer wording' };
    }
    if (r.id === 'bonus') {   // a bonus band dropdown → the lowest band (Joey 2026-11-04, a Workday employer)
      const num = o => parseFloat((String(o).match(/(\d+(\.\d+)?)\s*%/) || [0, 'Infinity'])[1]);
      const o = opts.filter(x => /\d\s*%/.test(x)).sort((a, b) => num(a) - num(b))[0];
      return o ? { status: 'ok', label, rule: 'bonus', value: o } : { status: 'unknown', label, why: 'bonus: no % band' };
    }
    if (r.id === 'comp' && opts.some(o => /\$\s?\d/.test(o))) {   // salary RANGE dropdown → the lowest range (Joey 2026-10-30, a Workday employer)
      const num = o => parseFloat((o.match(/\$\s?([\d,.]+)/) || [0, 'Infinity'])[1].replace(/,/g, ''));
      const o = opts.filter(x => /\$\s?\d/.test(x)).sort((a, b) => num(a) - num(b))[0];
      return { status: 'ok', label, rule: 'comp_range', value: o };
    }
    if (r.jd) {   // answered from the JD's requirement, never from the profile alone; the hand-off says "ask", so no model guesses it either
      const y = jdYears((ctx || {}).jd);
      if (y === null) return { status: 'unknown', label, rule: r.id, ask: true, why: r.id + ': no JD text — Joey decides' };
      if (y > 0) return { status: 'unknown', label, rule: r.id, ask: true, why: r.id + ': the JD asks for ' + y + '+ years of experience — Joey decides' };
    }
    if (r.id === 'age_range') {   // age grows from the profile's as_of date (whole years elapsed added)
      const age = r.age + Math.floor((Date.now() - Date.parse(r.as_of)) / (365.25 * 864e5));
      const o = ageBand(opts, age);
      return o ? { status: 'ok', label, rule: r.id, value: o } : { status: 'unknown', label, why: 'age_range: no option contains ' + age, options: opts.slice(0, 8) };
    }
    if (r.id === 'visa_conditions' && /\b(depart|leave|exit)\b[^?]{0,40}\b(u\.?s\.?|united states|country)\b|home[- ](country )?residen|two[- ]year|212 ?\(e\)/i.test(label)) {
      // "… conditions … that would require you to depart the United States for a certain period?" = a home-residency rule (J-1): F-1 has none → No
      const no = r.depart === false ? (opts.length ? yesNo(opts, false) : 'No') : null;
      if (!no) return { status: 'unknown', label, why: 'visa_conditions: departure requirement not on file' };
      const o = { status: 'ok', label, rule: r.id, value: no };
      return !opts.length ? ynText(o, label) : o;   // "If no, write N/A" → N/A (Bridgewater 10-31)
    }
    if (r.id === 'secondary_email') {
      const v = ((P.contact || {}).secondary_email || '').trim(), main = ((P.contact || {}).email || '').trim().toLowerCase();
      return v && v.toLowerCase() !== main ? { status: 'ok', label, rule: r.id, value: v } : { status: 'unknown', label, why: 'secondary_email: none on file (contact.secondary_email)' };
    }
    if (r.id === 'gpa_threshold') {   // a yes/no GPA-threshold question: the yes/no follows from the GPA on file (answers.gpa_threshold)
      const ynForm = (opts.length && opts.every(o => /^(yes|no)\b/i.test(String(o).trim()))) || AUX_Q.test(label.replace(/^\s*(\*|\d+[.)]|q\d+[.:])\s*/i, '').trim());
      if (!ynForm) return answerByRules(Object.assign({}, f, { _noThreshold: true }), ctx);   // "What is your current cumulative GPA? (minimum 3.0 …)" asks the value: the other GPA rules answer, as before (a Greenhouse employer 10-31 = N/A)
      const m = label.match(/\b([0-4]\.\d{1,2})\b/), x = m ? parseFloat(m[1]) : NaN;
      const kind = /\bmajor\b/i.test(label) ? 'major' : /\b(current|present)\b|graduate (program|school)|master'?s/i.test(label) ? 'current' : 'cumulative';
      const g = Number((r.by || {})[kind]);
      if (!(x <= 4.5) || !(g > 0)) return { status: 'unknown', label, why: 'gpa_threshold: no ' + kind + ' GPA on file to compare with ' + (m ? m[1] : '?') };
      const yes = /\bbelow\b|less than|\bunder\b/i.test(label) ? g < x : g >= x;
      if (!opts.length) return ynText({ status: 'ok', label, rule: r.id, value: yes ? 'Yes' : 'No', basis: kind + ' ' + g + ' vs ' + x }, label);
      const v = yesNo(opts, yes);
      return v ? { status: 'ok', label, rule: r.id, value: v, basis: kind + ' ' + g + ' vs ' + x } : { status: 'unknown', label, why: 'gpa_threshold: options are not Yes / No', options: opts.slice(0, 8) };
    }
    if (r.id === 'dob_minor') {   // the box is for minors only: free text stays empty (he is over 18); a Yes/No list = "are you under 18" → No
      if (!opts.length) return { status: 'ok', label, rule: r.id, value: '', leave: true };
      const no = yesNo(opts, false);
      return no ? { status: 'ok', label, rule: r.id, value: no } : { status: 'unknown', label, why: 'dob_minor: options are not Yes / No', options: opts.slice(0, 8) };
    }
    // "Are you eligible to work … WITHOUT (required) sponsorship now or in the future?" asks the opposite of "do you need
    // sponsorship": the profile's answer flipped (an employer 11-05 answered Yes — he needs sponsorship later, so No)
    if (/^spons_(now|future)$/.test(r.id) && typeof r.yes === 'boolean' && WITHOUT_SPONS.test(label)) {
      // no future in the question ("…for the duration of this internship without sponsorship?", Marshall Wace / Xaira 10-31,
      // answered Yes) = the NOW answer flipped: the internship is on CPT, sponsorship now = No → Yes
      const need = (r.id === 'spons_future' && !SPONS_LATER.test(label) && SPONS_NOW_ONLY.test(label) && typeof (P.answers.spons_now || {}).yes === 'boolean') ? P.answers.spons_now.yes : r.yes;
      const v = opts.length ? yesNo(opts, !need) : (need ? 'No' : 'Yes');
      return v ? { status: 'ok', label, rule: r.id, value: v, inverted: true } : { status: 'unknown', label, why: r.id + ': without-sponsorship wording, no Yes / No option', options: opts.slice(0, 8) };
    }
    if (r.id === 'age18' && r.under.test(label)) return { status: 'ok', label, rule: r.id, value: (yesNo(opts, false) || 'No') };
    if (r.id === 'age18' && f.t === 'checkbox' && opts.length === 1) return { status: 'ok', label, rule: r.id, value: opts[0] };   // "I certify that I am at least 18" box (Bosch 11-04)
    if (r.id === 'ft_start') {   // earliest full-time start (JSA-218, HRT 11-05): the first option on / after answers.ft_start.after, never a graduation-date pick
      const after = String(r.after || '').slice(0, 7);
      if (!/^\d{4}-\d{2}$/.test(after)) return { status: 'unknown', label, why: 'ft_start: no answers.ft_start.after on file' };
      if (!opts.length) return r.text ? { status: 'ok', label, rule: r.id, value: r.text } : { status: 'unknown', label, why: 'ft_start: no text on file' };
      const rng = opts.map(o => [o, ymRange(o)]).filter(x => x[1]);
      const o = (rng.find(([, x]) => x[0] !== x[1] && inRange(x, after)) || [])[0]
        || (rng.filter(([, x]) => x[0] && x[0] === x[1] && x[0] >= after).sort((a, b) => a[1][0].localeCompare(b[1][0]))[0] || [])[0];
      return o ? { status: 'ok', label, rule: r.id, value: o } : { status: 'unknown', label, why: 'ft_start: no option on or after ' + after, options: opts.slice(0, 8) };
    }
    if (r.id === 'grad_date' && opts.some(o => RANGE_OPT.test(String(o).trim()))) {   // "Before December 2027" / "Between December 2027 and September 2028" (an employer 11-05, JSA-218): the range holding the graduation month
      const g = gradYm(), o = g && opts.find(x => inRange(ymRange(x), g));
      return o ? { status: 'ok', label, rule: r.id, value: o } : { status: 'unknown', label, why: 'grad_date: no range option holds ' + (g || 'the graduation month (none on file)'), options: opts.slice(0, 8) };
    }
    if (r.id === 'gpa' && opts.some(o => /\d\.\d/.test(o)) && opts.filter(o => /^\s*0(\.0+)?\s*(-|–|to)\s*(4|5|10|100)(\.0+)?\s*$/.test(String(o))).length >= (/\b(scale|range)\b/i.test(label) ? 1 : 2)) {
      // a GPA SCALE list ("0.0 - 5.0", "0.0 - 4.0", "UK Scale") → the scale the GPA on file is on, never the first band holding the GPA (Radix 11-05, JSA-218)
      const sc = parseFloat(r.scale || ((String(r.note || '') + ' ' + String(r.text || '')).match(/\/\s*(\d+(?:\.\d+)?)/) || [])[1]);
      const nums = o => (String(o).match(/\d+(?:\.\d+)?/g) || []).map(Number);
      const o = sc > 0 && opts.find(x => { const n = nums(x); return n.length === 2 && n[0] === 0 && n[1] === sc; });
      return o ? { status: 'ok', label, rule: 'gpa_scale', value: o } : { status: 'unknown', label, why: 'gpa scale: no option for the ' + (sc || '?') + ' scale', options: opts.slice(0, 8) };
    }
    if (r.id === 'gpa' && opts.some(o => /\d\.\d/.test(o))) {   // a GPA band list → the band holding the GPA (Bosch 11-04)
      const g = parseFloat(r.text), nums = o => (o.match(/\d\.\d+/g) || []).map(Number);
      const o = opts.find(x => { const n = nums(x); if (/above|over|higher|\+|or more|greater/i.test(x)) return n.length && g > n[0] || (n.length && g >= n[0] && /\+|or (more|higher)|and above/i.test(x));
        if (/under|below|less|lower/i.test(x)) return n.length && g < n[0]; return n.length === 2 && g >= n[0] && g <= n[1]; });
      return o ? { status: 'ok', label, rule: 'gpa_band', value: o } : { status: 'unknown', label, why: 'gpa: no band holds ' + r.text };
    }
    if (r.id === 'housing_have') {   // JSA-363: has housing in the named place only when it is home (local_area.home); no home on file → ask
      const h = (P.answers.local_area || {}).home;
      if (!h) return { status: 'unknown', label, rule: r.id, ask: true, why: 'housing_have: no answers.local_area.home on file — ask the user' };
      if (!NAMED_PLACE.test(label)) return { status: 'unknown', label, rule: r.id, ask: true, why: 'housing_have: the question names no place — ask the user' };   // "Do you have your own housing arrangements?" is not about where he lives
      const yes = RX(h).test(label), o = opts.length ? yesNo(opts, yes) : (yes ? 'Yes' : 'No');
      return o ? { status: 'ok', label, rule: r.id, value: o } : { status: 'unknown', label, why: 'housing_have: no yes/no option', options: opts.slice(0, 8) };
    }
    if (r.id === 'local_area') {   // local to the named place only when it is home (profile: local_area.home); elsewhere → "No, but willing to relocate", else No
      const home = r.home && RX(r.home).test(label);
      const o = home ? (opts.find(x => /^yes\b/i.test(x.trim())) || '') : (opts.find(x => /willing to relocate/i.test(x) && !/\bnot (willing|able)\b|unable|unwilling|cannot|can't/i.test(x)) || ((o => o && !/\bnot (willing|able)\b|unable|unwilling|cannot|can't/i.test(o) ? o : '')(yesNo(opts, false))));   // a "No, not willing to relocate" option is false for him → ask (DeepSeek DFW case)
      if (opts.length && !o) return { status: 'unknown', label, why: 'local_area: no matching option' };
      return { status: 'ok', label, rule: r.id, value: opts.length ? o : (home ? 'Yes' : 'No') };
    }
    if (r.id === 'highest_ed' && opts.length && r.pick) {   // "Associate of …, Bachelor of Architecture, Bachelor of Arts …" (Acuity SF 11-05): the completed degree's own name, never the first Bachelor option
      const fits = opts.filter(o => r.pick.some(p => p.test(String(o).trim())));
      if (fits.length > 1) {
        const ym = new Date().toISOString().slice(0, 7), lvl = { doctor: 4, master: 3, bachelor: 2, associate: 1 };
        const done = (P.education || []).filter(e => !e.current && e.end && String(e.end) <= ym).sort((a, b) => (lvl[b.level] || 0) - (lvl[a.level] || 0))[0];
        const full = String((done && done.degree_full) || '').trim().toLowerCase();
        const o = full && (fits.find(x => String(x).trim().toLowerCase() === full) || fits.find(x => String(x).trim().toLowerCase().startsWith(full)));
        return o ? { status: 'ok', label, rule: 'highest_ed', value: o } : { status: 'unknown', label, why: 'highest_ed: several options fit and none is the completed degree (' + (full || 'none on file') + ')', options: fits.slice(0, 8) };
      }
    }
    if (r.id === 'how_heard' && REF_OPT.test(label.replace(/\breferral source\b|\bsource of referral\b/gi, ' '))) {   // "How did you hear about us? If referred, name the employee" — a referral question too (JSA-195)
      const ref = poolCheck(ctx);
      if (ref.state !== 'none') return refAsk(label, r.id, ref);
    }
    if (r.id === 'degree' && !opts.length && /^(text|textarea)$/.test(f.t || '') && DEGREE_ASKED.test(label)) {   // a typed answer to "which degree are you pursuing / confirm your current degree": the full name from the facts (JSA-296, Bosch 11-10)
      const e = (P.education || []).find(x => x.current);
      if (e && e.degree_full && e.major && e.school) return { status: 'ok', label, rule: 'degree_full', value: e.degree_full + ' in ' + e.major + ', ' + e.school };
    }
    if (r.id === 'grad_date' && /\bmm\s*\/\s*yy\b(?!yy)/i.test(label) && r.mmyy) return { status: 'ok', label, rule: 'grad_date_mmyy', value: r.mmyy };   // "(MM/YY)" → 12/27
    const out = { status: 'ok', label, rule: r.id };
    if (r.id === 'video_record') return { status: 'unknown', label, rule: r.id, ask: true, no_auto: true, why: 'a recorded video is required — the user records it (Joey 2026-11-17, JSA-410)' };
    if (r.id === 'reloc_other') {   // a multi-select of cities: only those in the countries he named (U.S. + China); a city not in CITY_COUNTRY is never picked
      const cs = (r.countries || []).map(x => String(x).toLowerCase());
      const keep = opts.filter(o => cs.includes(cityCountry(o)));
      return keep.length ? Object.assign(out, { value: keep.join(' | ') }) : { status: 'unknown', label, rule: r.id, why: 'reloc_other: no city in the list is in answers.reloc_other.countries (or the countries are not on file)', options: opts.slice(0, 8) };
    }
    if (r.all && opts.length) {   // multi-select of offices / cities: he goes anywhere in the U.S. → all of them
      const keep = opts.filter(o => !/decline|prefer not|none|other/i.test(o));
      if (keep.length) return Object.assign(out, { value: keep.join(' | ') });
    }
    if (r.note) out.note = r.note;
    if (r.id === 'comp' && !opts.length && DIGITS_ONLY.test(label)) {   // a digits-only pay box: 25 per hour / 52000 per year (Joey 2026-11-01; a Greenhouse employer 10-31 got text, audit 11-08, JSA-246)
      const d = r.digits || {}, v = /\bhour/i.test(label) ? d.hour : /\b(annual|yearly|per year|a year|annum)\b|\bsalary\b/i.test(label) ? d.year : null;
      return v ? Object.assign(out, { value: String(v), note: 'digits-only pay box' }) : { status: 'unknown', label, rule: r.id, why: 'comp: digits-only box, ' + (d.hour ? 'pay period unclear' : 'no answers.comp.digits on file') };
    }
    if (opts.length) {
      let o;
      const pickable = r.id === 'how_heard' ? opts.filter(x => !REF_OPT.test(String(x)) && !PERSON_OPT.test(String(x))) : opts;   // nor a recruiter / employee / friend (JSA-219)   // "Employee referral" is never his source (JSA-195): he applies on his own
      if (r.pick) for (const p of r.pick) { o = pickable.find(x => p.test(x.trim()) && !(r.yes === true && NEG_OPT.test(x.trim()))) || (r.id === 'discipline' ? pickable.find(x => parts(x).some(y => p.test(y))) : undefined); if (o) break; }   // JSA-198: a combined major option ("Data Science / Analytics") matches by its parts, in the profile's order
      if (!o && r.yes === true && f.t === 'checkbox' && opts.length === 1) o = opts[0];
      if (!o && /^spons_(now|future)$/.test(r.id) && r.yes === true) {   // JSA-407: "Yes, … now / Yes, … in the future / No, …" — the Yes options differ by time word; he needs it LATER (CPT now → H-1B later), so the future option; more than one Yes and no single future one → ask
        const ys = opts.filter(x => /^yes\b/i.test(String(x).trim()));
        const NOWW = /\b(now|currently|immediately|at this time|today)\b/i, FUTW = /\b(in the )?future\b|\blater\b|\beventually\b|\bat some point\b|after (i )?graduat/i;
        if (ys.length === 1 && NOWW.test(ys[0]) && !FUTW.test(ys[0]) && SPONS_LATER.test(label))   // a lone "Yes, … now" under a now-or-future question claims a need he does not have yet → ask
          return { status: 'unknown', label, rule: r.id, why: r.id + ': the only Yes option is the "now" one; he needs sponsorship later, not now', options: opts.slice(0, 8) };
        if (ys.length > 1 && ys.some(x => NOWW.test(x) || FUTW.test(x))) {   // split by time words only ("Yes, with restrictions" is another shape)
          const fut = ys.filter(x => FUTW.test(x) && !NOWW.test(x));
          if (fut.length !== 1) return { status: 'unknown', label, rule: r.id, why: r.id + ': several Yes options split by time, no single "in the future" one', options: opts.slice(0, 8) };
          o = fut[0];
        }
      }
      if (!o && r.yes !== undefined) o = yesNo(opts, r.yes);
      if (!o && r.yes === true) o = opts.find(x => /^(i |we )?(consent|agree|accept)\b/i.test(x.trim()));   // JSA-363: "I consent" / "I agree" as the Yes option
      if (!o && r.id === 'age18') o = yesNo(opts, true);
      if (!o && /^(degree|college_year_current)$/.test(r.id)) o = opts.find(x => /^other\b/i.test(x.trim()));
      if (!o && r.id === 'enrolled' && !opts.some(x => /^(yes|no)\b/i.test(x.trim()))) o = opts.find(x => /master/i.test(x));   // "Are you currently enrolled in school?" with level options → the master's one   // a master's student where only BA / BS / Ph.D (or Freshman…Senior) are offered (Bosch 11-04)
      if (!o && f.t === 'checkbox' && opts.length === 1 && r.yes === false) return { status: 'ok', label, rule: r.id, leave: true };
      if (!o) return { status: 'unknown', label, why: 'no matching option for ' + r.id, options: opts.slice(0, 8) };
      if (/^(relocate|onsite|local_area|commute|travel)$/.test(r.id) && placeClaim(o)) {   // "Yes, I'm in SF / Bay Area" / "Yes, I am located in Idaho": false for him (Chicago) → the relocating option, else asked (Pylon, Clênera 10-31; audit 11-08, JSA-246)
        o = opts.find(x => /relocat/i.test(x) && !/\bnot (willing|able|planning)\b|unable|unwilling|cannot|can't|won't|\bno\b/i.test(x) && !placeClaim(x));
        if (!o) return { status: 'unknown', label, rule: r.id, why: r.id + ': the yes option claims he already lives there; no relocation option', options: opts.slice(0, 8) };
      }
      out.value = o;
    } else if (r.date && f.t === 'date') out.value = r.date;   // a date box takes a date, not "Summer 2027" (Genesis 2026-10-31)
    else if (r.text) out.value = r.text;
    else if (r.yes !== undefined || r.id === 'age18') out.value = (r.yes === false ? 'No' : 'Yes');   // option-less combo/toggle: fillCombo matches 'Yes'/'No' exact or word-start (\"Yes, I am...\")
    else return { status: 'unknown', label, why: 'rule ' + r.id + ' needs options' };
    if (r.combo) out.combo = r.combo;
    if (r.alts && !opts.length) out.alts = r.alts.slice();   // option-less combo: ordered alternatives for fillCombo
    if (agree) out.agreed = hits.map(h => h.id);
    if (!opts.length && /^(text|textarea)$/.test(f.t || '') && /^(yes|no)$/i.test(String(out.value))) return ynText(out, label);
    return out;
  }
  function match(fields, ctx) {
    const res = { fill: {}, click: [], unknown: [], consent: [], notes: [] };
    for (const f of fields) {
      if (['file'].includes(f.t)) continue;
      const a = answerFor(f, ctx);
      if (a.status === 'unknown') { if (f.r || f.required) res.unknown.push({ i: f.i, label: a.label.slice(0, 140), why: a.why, options: a.options, ask: a.ask }); else res.unknown.push({ i: f.i, label: a.label.slice(0, 140), optional: true }); continue; }
      if (a.status === 'consent') { res.consent.push({ i: f.i, label: a.label.slice(0, 140) }); continue; }
      if (a.note) res.notes.push(a.label.slice(0, 60) + ': ' + a.note);
      if (a.leave) continue;
      if (['radio', 'combo', 'toggle'].includes(f.t)) res.click.push({ i: f.i, label: a.label.slice(0, 80), option: a.value, combo: a.combo, alts: a.alts });
      else res.fill[f.i] = a.value;
    }
    return res;
  }
  root.__answerRules = { R, match, answerFor, jdYears, ageBand, poolCheck, coNorm, qtypes, shapeCheck, uncertainty, formCheck, qaAnswer, degreeMajor };
  // auto() → JSON STRING (legacy). autoObj() → plain object. Both use the fields of the last extract()/plan() scan.
  if (typeof window !== 'undefined' && window.__cx) {
    const fieldsNow = () => window.__cxFields || (window.__cx.extract(), window.__cxFields);
    window.__cx.autoObj = () => match(fieldsNow(), { jd: window.__cxJd, company: window.__cxCompany });   // __cxJd: the JD text (JSA-105); __cxCompany: the hiring company (referrer pool, JSA-195)
    window.__cx.auto = () => JSON.stringify(window.__cx.autoObj());
  }
  if (typeof module !== 'undefined') module.exports = { R, match, answerFor, ynQuestion, jdYears, ageBand, poolCheck, coNorm, qtypes, shapeCheck, uncertainty, formCheck, qaAnswer, qaOne, qaFindAll, coverNote, QA };
})(typeof window !== 'undefined' ? window : globalThis);
