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
  const AUTH_Q = /(?:.*(legally )?authori[sz]ed to work|.*eligible to work|.*work authori[sz]ation|.*authori[sz]ation to work|.*(legally )?(permitted|allowed|qualified) to work|.*legally able to work|.*\blegal right to work\b|.*(legally )?eligible for employment|.*authori[sz]ed (or|and\/or) (legally )?(able|eligible|permitted) to work)/i;   // "legally able to work" (iCIMS West Bend 2026-11-03); "legally authorized or able to work in the country in which the position is located" (Newell SF 11-05, type AC)
  const RESTRICTED = !!(P.work_auth && P.work_auth.restricted);   // e.g. F-1 / CPT: authorized, but not unrestricted / permanent
  const R = [
    // ---- identity & contact
    { id: 'name_pronunciation', q: /pronounc(e|ed|ing)\b|pronunciation|phonetic/i },   // JSA-218 (Akuna 11-05): answers.name_pronunciation; none on file → ask, never the phone / name
    { id: 'has_preferred', q: /i have a preferred name|do you have a preferred name/i },   // Workday checkbox (Joey 10-28: use Joey)
    { id: 'preferred_full_name', q: /preferred (first\s*(&|and|\/)\s*last|full) name/i },   // Sierra (Ashby) 11-06: "Preferred First & Last Name" (JSA-230 live check)
    { id: 'preferred_last_name', q: /preferred (last name|surname|family name)/i },   // Dell (Oracle) 11-06: "Preferred Last Name"
    { id: 'preferred_name', q: /preferred (first )?name|nick ?name/i, not: /^(legal )?(first|last|middle) name\b|\blegal (first |last |middle )?name\b/i },   // "Legal Last Name (if different from preferred name)" got "Joey" (a Greenhouse employer 11-05, JSA-218)   // "Nick Name" (Hermeus 10-31, JSA-075)
    { id: 'first_name', q: /^(legal )?first name\b|given name/i },
    { id: 'last_name', q: /^(legal )?last name\b|family name|surname/i },
    { id: 'full_name', q: /^(?!.*(school|company|employer|university|reference|manager|supervisor|emergency|preferred|first|last|middle|refer|recruiter|relative|friend|contact person|team member)).*(\b(full|legal)\s+(legal\s+)?name\b|^name\b|^your name|^name of applicant)/i },
    { id: 'secondary_email', q: /\b(secondary|alternate|alternative|second|backup|additional)\s+(e-?mail|email address)\b/i },   // contact.secondary_email (Joey 2026-11-05); never the main address twice (Goldman Oracle 11-05)
    { id: 'email', q: /^(?!.*(marketing|newsletter|promotional|consent|communications)).*e-?mail/i },
    { id: 'phone_device', q: /phone (number )?(device )?type|device type|type of phone/i },   // Workday ("Phone Type": JSA-185) My Information
    { id: 'phone_code', q: /country phone code|phone (country )?code|country code/i },   // Workday
    { id: 'phone', q: /^(?!.*extension)(?=.*(phone(?!tic)|mobile( number)?$|\bcell\b))/i, not: /phone (interview|screen|call)s?\b|pronounc|phonetic/i },   // "…how your name is pronounced phonetically" got the phone number (Akuna 11-05, JSA-218)   // "…may consist of phone interview, … a drug screen … willing to participate?" is the background question (Oracle 2026-11-03)
    { id: 'permanent_address', q: /permanent( (legal|home|residential|street|mailing))* address|home country address|address in (your )?home country/i },   // F-1: the family home in China (Joey 2026-11-03, Workable an employer)
    { id: 'address', q: /street address|address line ?1|mailing address|^address\*?$/i },   // a bare "Address" (Workable an employer 2026-11-03); never "permanent legal address"
    { id: 'address_type', q: /^address type$/i },   // iCIMS profile: the address block's own Type list (Home …) (JSA-093 Lennox 2026-11-03)
    { id: 'city_state_zip', q: /city,? state,? (and )?zip/i },   // one box for all three (AMAT relocation 2026-10-30)
    { id: 'city_state', q: /\(city,? (and )?state\)|where do you (currently )?(live|reside)\b/i, not: /zip|postal|country|relocat|willing|commute/i },   // "Where do you currently live? (City, State)" (Pattern Lever 2026-11-04, JSA-144)
    { id: 'county', q: /^county\b/i, not: /county\s*\/\s*state|county or state/i },   // "County/State" is the state list (an employer 11-04)   // the county of the profile address (Regeneron 2026-10-30)
    { id: 'zip', q: /zip|postal code/i, not: /\+ ?4\b|plus ?4\b|zip ?4\b|extension/i },   // "Zip Code+4" is the 4-digit add-on, never the 5-digit ZIP (Oracle 2026-11-03)
    { id: 'city', q: /^city\b|(current )?home city\b|city (in which|where) you (currently )?(reside|live)/i },
    { id: 'state', q: /^county\s*\/\s*state\b|^state\b|(current )?home state\b|province|(indicate|which|what) (is )?(the )?state\b|state (in which|where) you (currently )?(reside|live)/i },
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
    { id: 'college_year_current', q: /(what|which) year (of|in) (college|university|school) are you( currently)?( in)?|current year (of|in) (college|university)|what is your current (college|university) year|(current )?class standing|year in school/i },   // "What is your current class standing?" (Bosch 11-04) → Other when no graduate option   // same fact: 5th year
    { id: 'undergrad_year', q: /^are you an? (freshman|sophomore|junior|senior|rising (junior|senior))\b/i },   // he is a master's student (SouthState 2026-11-01)
    { id: 'noncompete_detail', q: /(describe|detail|list|explain) any (non[- ]?compete|restrictive)|currently employed.{0,40}(detail|describe|list).{0,60}non[- ]?compete|non[- ]?compete.{0,80}(if you are currently employed|current employer)/i, not: /\b(yes|no)\b.{0,5}$|^(are|is|do|does|have|has|will|would)\b/i },   // "Are you subject to a non-compete … with a previous or current employer?" is the yes/no question (DeepSeek case, Erie 11-04)   // Joey 2026-10-26 (no non-compete) + not employed (a Workday employer 2026-11-01)
    { id: 'know_employee', q: /do you know (anyone|someone|any (current )?employees?)\b.{0,40}\b(work|employ)/i },   // Joey 2026-11-01: default No unless he says otherwise
    { id: 'debarred', q: /debarred|excluded (or sanctioned )?(from|by)\b|sanctioned by\b/i },   // Joey 2026-11-01 (Excellus)
    { id: 'industry_investor', q: /owner or investor|investor in (an|any) (entity|company)|\b(own|owner|ownership|invest|investor|investment)\b.{0,40}\b(winery|wineries|liquor|alcohol|brewer|brewery|distill\w*|spirits)\b/i },   // Joey 2026-11-01 (a Workday employer, alcohol industry)
    { id: 'industry_side_role', q: /consultant, endorser|influencer, advisor|advisor,? or mentor in|\b(consultant|endorser|influencer|advisor|mentor)\b.{0,40}\b(in|for|to) (an?|any|the) (\w+ ){0,2}(industry|entity|company)\b/i },   // outside-business No (2026-10-26)
    { id: 'other_jobs', q: /additional jobs? (you )?(plan|intend) to (continue|keep)|other (employment|jobs?) you (plan|intend) to (continue|keep)|(continue|keep) (any )?(additional|other) jobs?/i },
    { id: 'conflict_interest', q: /(aware of|have|are there) any (potential |actual )?conflicts? of interest/i },   // follows from the three above (Constellation 2026-11-01)
    { id: 'eligibility_3way', q: /describ\w* your employment eligibility|option describing your (work|employment) (eligibility|authori[sz]ation)|^employment eligibility\b/i },   // Joey 2026-11-01 (Copart): this three-way wording → sponsorship
    { id: 'language_level', q: /\benglish (language )?proficiency|^(verbal|written)( and written)? communication( level)?$/i },   // Workday languages all Fluent (Joey 2026-10-28)
    { id: 'contact_employer', q: /\b(may|can) we contact (your )?(current|present|previous|former)? ?(employer|supervisor|manager)s?\b/i },   // Joey 2026-11-01 (EMC): Yes
    { id: 'interview_travel', q: /\b(require|need)\b.{0,30}\btravel (assistance|reimbursement|support)\b.{0,60}\binterview|\binterview\b.{0,80}\b(require|need)\b.{0,30}\btravel (assistance|reimbursement|support)\b/i },   // Joey 2026-11-01 (a Workday employer): No
    { id: 'employer', q: /(current|most recent) (or (last|most recent) )?employer|current or last employer|current company/i, not: /\b(may|can) we contact\b|non[- ]?compete|non[- ]?solicit|confidentiality|obligations?\b|agreements?\b/i },   // "With respect to any previous or current employer, are you subject to … non-compete …" is the restriction question (Erie SF 11-04)
    { id: 'lives_outside_us', q: /live outside (of )?the (u\.?s\.?|united states)/i },
    // ---- education
    { id: 'education_list', q: /(represent|list|write (in|out)|enter|provide|describe|include)\b[^?]{0,60}\b(completed|in[- ]progress|all)\b[^?]{0,30}\b(university |college )?degrees\b|(list|enter|provide|include)\b[^?]{0,20}\b(all |each )?(the )?(colleges?|universities|colleges? (or|and|\/) universities|post-?secondary (schools|institutions))\b[^?]{0,40}\battended\b|\b(completed and in[- ]progress|in[- ]progress and completed)\b[^?]{0,30}degrees|\beducation(al)? (history|background)\b[^?]{0,40}\b(list|write|describe|below|above)/i },   // HRT 11-05 (JSA-218): DeepSeek wrote "B.S." / "M.S. Data Science" / high school "not provided" — the profile's entries instead
    { id: 'hs_name', q: /(high|secondary) school[^?]{0,25}\bname\b|\bname of (your |the )?(high|secondary) school|(which|what) (high|secondary) school/i },   // the high school's name (profile high_school, JSA-218)
    { id: 'school_level', q: /^(?!.*(highest|completed|attained|finished)).*(level of (schooling|education|study)|year in school|current (academic )?(year|level) of study)/i },
    // ---- education
    { id: 'school', not: /\b(major|minor|concentration)\s*:?\s*$|\bschool (city|state|location|address|country|zip|year|gpa)\b|\bgpa\b|high school/i, q: /^(school|university|college|institution)( name)?\b|which (college|university|school) (did|do) you attend|collegiate institution|(school|university|college|institution) (do |did |are )?you (currently )?attend/i },
    { id: 'degree', not: /mm\s*\/\s*yyyy/i, q: /^degree\b|degree (type|level)|degree level|(what|which) degree are you (currently )?(pursuing|working towards?|seeking|enrolled in)|(current )?degree (that )?(you are|you're) (currently )?(obtaining|pursuing|earning|working (on|towards?))/i },   // Hermeus 10-31 (JSA-075)
    // no data-science option on the tenant -> Computer Science, then Information Systems, before Statistics (Joey 2026-10-28)
    { id: 'discipline', q: /discipline|field of study|major|area of study|(course|program|concentration) of study|^(academic )?concentration\b|what are you (currently )?studying/i, not: /\b(school|university|college|institution) (are|do|did) you\b|graduat|\bdegree and\b|\bgpa\b|grade point/i },   // "…GPA (cumulative, not major specific)" is the GPA, not the major (Brattle 10-31 got "Other", replay JSA-188)   // "What is your area of study?" (a Lever employer 2026-11-02, JSA-075); "graduate from your course of study" = grad date
    // Greenhouse education block dates (labels like "Start date month", "End date year"; helpers prefix bare Month/Year with the Start/End legend)
    { id: 'start_month', q: /start.{0,20}month|month.{0,12}start/i },
    { id: 'start_year', q: /start.{0,20}year|year.{0,12}start/i },
    { id: 'end_month', q: /(end|expected end).{0,20}month|month.{0,12}end/i },
    { id: 'end_year', q: /(end|expected end).{0,20}year|year.{0,12}end/i },
    { id: 'ft_start', q: /earliest[^?]{0,80}\b(begin|start|eligible)[^?]{0,40}full[- ]?time|full[- ]?time[^?]{0,40}\b(start|begin)(ning)? date|when (can|could|would|are) you (be )?(able to |available to )?(begin|start) full[- ]?time/i },   // "…earliest you are eligible to begin full-time employment?" got February 2027 from grad_date (HRT 11-05, JSA-218): answers.ft_start
    { id: 'grad_date', not: /high school|secondary school|mm\s*\/\s*yyyy|sponsor|visa|full[- ]?time/i, q: /when (will|do) you (complete|finish) your (degree|program|studies)|(expected |anticipated )?graduation( date| year| month| term| semester)?\b|when (will|do) you graduate|when (are|will) you (be )?expected to graduate|when do you expect to graduate|(month and year|when) (are|will) you (be )?expected to graduate|are you expected to graduate/i },   // "When do you expect to graduate?" (Hermeus 10-31, JSA-075)   // December 2027: never "Summer 2027" (an Ashby employer 2026-10-31)
    { id: 'highest_ed', q: /highest (completed |attained )?level of (education|schooling)( (completed|attained))?\b|highest (level of )?education (completed|attained)|highest (level of )?(completed|attained) (education|degree)\b|highest (level of )?(degree|education)( of education)?( (you have )?(completed|earned|attained))?\??$/i },   // "What is your highest degree of education?" (Workable Thorlabs 2026-11-03)
    { id: 'degree_progress', q: /(in the process of|pursuing|working toward).{0,60}(or (have )?(recently )?completed)?.{0,40}\b(bachelor|master)'?s?\b.{0,30}\bor\b.{0,10}\b(master|bachelor)'?s?\b/i, not: /in business( administration)? or (a )?related/i },   // "Are you currently in the process of or have recently completed a Bachelor's Degree or Masters Degree?" (an employer 11-04): M.S. in progress + B.A. 05/2026 → Yes
    { id: 'enrolled', not: /in business( administration)? or (a )?related/i, q: /currently enrolled|current(ly)? (a )?student|enrolled in (a|an) .*program/i },
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
    { id: 'immigration_status', q: /(current|present) (u\.?s\.? )?(employment )?(immigration|visa) status|^immigration status|what is your (current )?(u\.?s\.? )?(immigration|visa) status|^(?!\s*(are|do|does|will|would|is|have|has|can|could)\s+you\b)(?!.*\b(sponsor\w*|requir\w*)\b).*\bvisa (type|status|classification)\b/i },   // "provide your visa type / status / classification" = the visa (F-1), not the work authorization (CPT): replay JSA-188 found 6 such boxes answered "CPT" (a Greenhouse employer, a Greenhouse employer, Sysk 10-28…10-31)   // no plain F-1 → F-1 CPT, never F-1 OPT (RBC 2026-11-01)   // plain F-1 over "F-1 CPT" (handoff 10-28b)
    { id: 'auth_kind', not: /file a petition|petition or application|on your behalf|number of (months|years|days)|how (many|long)\b|\bif not,? (please )?type\b|\btype ["“']?n\/?a\b/i,   // "…indicate the number of months you have remaining" asks a number, not the kind (Goldman 11-05); "…if not type N/A": type is the verb (an employer referral-name box 11-05 got "CPT")
      q: /^(?!.*sponsor).*(if (yes|so)\b[^?]{0,60}\b(kind|type|visa|status|category)\b|what (kind|type|category)( of)? .{0,30}(authori[sz]ation|visa|status)|(kind|type) of (work )?(authori[sz]ation|visa|status)|visa (type|status)\b(?!.*(sponsor|require))|immigration status)/i },
    { id: 'spons_now', q: /^(?!.*\b(future|ever)\b)(?!.*(after graduat|at any time|any time after|\blater\b|eventually|going forward|upon graduation))(?:.*sponsorship.*\b(now|currently|at this time)\b|.*\b(now|currently|at this time)\b.{0,40}\bsponsorship|.*require.*sponsorship.*to (begin|start) (the|this) internship)/i },
    { id: 'degree_start_mmyyyy', q: /^(?=.*mm\s*\/\s*yyyy)(?=.*((begin|began|start(ed)?).{0,40}(degree|program)|(degree|program).{0,40}(start|begin))).*/i },   // "When did you begin your current degree program? … MM/YYYY" (a Lever employer 11-04, JSA-150)
    { id: 'degree_end_mmyyyy', q: /^(?=.*mm\s*\/\s*yyyy)(?=.*(complet|finish|graduat|end date)).*/i },
    { id: 'sponsorship_type', q: /(what|which) (type|kind) of (visa |work |immigration )?sponsorship|(?<!\bany )type of (visa )?sponsorship|sponsorship type/i },   // "Will you require ANY type of sponsorship now or in the future?" is the yes/no question (Newell SF 11-05, type AD)   // "If yes, what type of sponsorship?" → the profile's explanation text, never "Yes" (a Lever employer / Belvedere 11-04, JSA-150)
    { id: 'hs_grad_year', not: /^(did|have) you graduated?\b/i, q: /high school.{0,30}graduat|graduat\w*.{0,30}high school|year of high school|high school (diploma|completion).{0,20}(year|date)/i },   // confirmed 2026-10-28 (candidate-profile)
    { id: 'spons_future', not: /(what|which) (type|kind)|(?<!\bany )type of (visa|sponsorship)|sponsorship (type|category)|(which|what) sponsorship category/i, q: /sponsor|file a petition .{0,80}(employment|immigration)|employment[- ]based (status|visa|immigration)/i },   // "…require <Co> to file a petition … for employment-based status" (Workable an employer 2026-11-03)
    { id: 'on_opt', not: /legally (authori[sz]ed|able) to work|(hold|obtain) valid (u\.?s\.? )?work authori[sz]ation|can (you )?(obtain|commence)|e\.g\.,?[^)]{0,80}\bopt\b/i, q: { test: l => /\b(currently|now|presently|current|active)\b.{0,60}\b(opt|optional practical training)\b|\bon (stem )?opt\b|\b(participating in|based on)\b.{0,20}\b(opt|optional practical training)\b/i.test(noExamples(l)) } },   // JSA-175: only a question that asks whether he is ON OPT — OPT inside an example group / "e.g." clause does not count   // OPT named only as an example of authorization is not "are you on OPT" (Goldman 11-05)   // F-1, internship on CPT, not on OPT (a Workday employer 2026-10-30)
    { id: 'any_employer', q: /\b(any|all) employers?\b|without (any )?restriction|unrestricted/i },   // "authorized to work for ALL employers" = any employer → No (an employer 11-05, JSA-218)
    { id: 'work_permit', q: /(valid|current|hold|have|possess)\b.{0,30}\bwork permit/i },   // Joey 2026-10-30 (HPE): Yes; 'any employer' stays No
    { id: 'citizen_pr', q: /^are you an? (u\.?s\.? )?(citizen|national)( or (a )?(lawful )?permanent resident)?\??$|^are you a (u\.?s\.? )?(lawful )?permanent resident\??$|^(?=.*\bcitizen\b)(?=.*\bpermanent resident\b)(?=.*\b(refugee|asylee|asylum)\b)(?!.*\b(sponsor|authori[sz]ed|eligible to work)\b)/i },   // "Are you one of the following: citizen of the United States, lawful permanent resident, refugee, or asylee?" (Erie SF 11-04) = the protected-individual question: F-1 → No   // answer from profile work_auth (2026-11-01)
    { id: 'authorized', q: { test: l => !/\b(opt|optional practical training)\b/i.test(noExamples(l)) && AUTH_Q.test(l) } },   // JSA-175: OPT named only as an example of authorization ("(e.g., U.S. citizen, permanent resident, F-1 OPT)", Goldman 11-05) is still the authorization question → Yes; "authorized to work on OPT?" stays out
    // ---- availability & logistics
    { id: 'disability_cc305', q: /^please check one of the boxes below/i },   // OFCCP CC-305 on Self Identify (a Workday employer 2026-10-30); candidate-profile EEO: no disability
    { id: 'essential_functions', q: /essential functions.{0,80}(with or without|accommodation)/i },   // Joey 2026-10-30 (Hitachi, iMessage yes)
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
    { id: 'enrollment_status', q: /(best describes|what is) your (current )?enrollment status|current(ly)? enrollment status/i },   // config: Master's program (an employer 11-04)
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
    { id: 'business_degree', q: /(pursuing|enrolled in|studying|completed|have) .{0,50}degree( program)? in business( administration)? or (a )?related field|degree( program)? in business or (a )?related/i, yes: false },   // Joey 2026-11-04: Applied Data Science is not business / related (an employer)
    { id: 'recruiter_contact', q: /(were|have) you (been )?(contacted|approached|referred) by (an? |the )?.{0,40}recruiter/i, yes: false },   // every application so far is his own (tracker referral_status Cold); SPX 11-04
    { id: 'signature', q: /typed signature|electronic signature|e-?signature|digital signature|sign(ature)? .{0,20}(full|legal) name|^signature( of (the )?applicant)?$|^applicant'?s? signature$/i, not: /\bdate\b/i },   // "Signature of Applicant" (Erie SF 11-04)   // config signature (full name); SPX / an employer 11-04
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
    { id: 'relocate', q: /^(?!.*(\bwhere\b|scope|how far|which (areas|locations))).*relocat/i },
    { id: 'local_area', q: /\b(are|is) you (currently )?local to\b|\blocal to (the )?[\w .,/&-]{0,40}\b(area|region|office)\b/i },   // "Are you local to NYC … able to commute in for a Hybrid schedule?" asks where he lives, not willingness (NYT 2026-11-04): home city → Yes, else the relocate option / No
    { id: 'onsite', q: /on[- ]?site|in[- ]office|hybrid|return to office|\brto\b|in person|in (the|our) [\w ]{0,30}office|\bcommute\b|office.{0,30}days (a|per) week|days (a|per) week.{0,30}office/i, not: /advisor|adviser|professor|school|university|permission|approv|comfortable|\bbased in\b|\blive in\b|\breside|\bcurrently (located|living)|travel (assistance|reimbursement|support)/i },   // "are you based in the SF Bay Area …" asks where he lives (Chicago), not willingness (an Ashby employer 2026-10-31)   // not: someone else's consent (Hitachi 2026-10-30) → Joey
    { id: 'travel', q: /travel(?!l?ers?\b)/i, not: /travel (assistance|reimbursement|support)\b.{0,60}\binterview|\binterview\b.{0,80}\btravel (assistance|reimbursement|support)\b/i },
    { id: 'housing', q: /housing/i },
    { id: 'reside_us', q: /reside in the (us|united states)|located in the (us|united states)/i },
    { id: 'comp', q: /salary|compensation|pay (range|expectation)|desired pay|hourly rate expectation|(required|expected|desired) (pay )?rate|\bpay rate\b/i, not: /hourly or (annual|yearly|salary)|per hour or per year|\bbonus\b/i },   // "What is your required pay rate?" (Thorlabs 2026-11-03); "hourly or annually?" is pay_period
    { id: 'pay_period', q: /(rate|pay|salary|compensation)\b.{0,30}\b(hourly or (annual|annually|yearly|salary)|per hour or per year)/i },   // internship pay is hourly (25 / hour standard, Joey 2026-11-01)
    { id: 'how_heard', q: /(how|where) did you (\w+ )?(hear|find|learn)|(how|where) you (\w+ )?(heard|found out|learned) (about|of)\b|how were you made aware of\b|^source\b|^referral source\b|^(applicant |candidate )?source of (referral|application)\b/i, not: /root cause|investigat|problem|what changed|\bfix(ed)?\b/i },   // "How did you find the root cause…" is an essay, never the source answer (BFF Workable 11-04)   // "Where did you hear about this opportunity?" (TikTok 2026-11-03)
    // ---- relationships & restrictions
    { id: 'relative_names', q: /family member names|names?(\(s\))? and relationships?(\(s\))?/i },   // "name(s) and relationship(s)" (Thorlabs 2026-11-03)
    { id: 'relatives', q: /relative|family member|related to (an|any) employee/i, not: /^(relative'?s? )?(name|position|relationship|title|department)\b|relative (name|position)/i },   // "Relative Name" / "Position" boxes stay empty (an employer 11-04)
    { id: 'prev_employed', q: /(previously|ever|currently) (been )?(directly )?(employed|worked|work) (as an? [\w -]+ )?(by|for|with|at)|\bhave you (ever )?been (directly )?(employed|working) (at|by|with|for)\b[^?]{0,90}\b(before|previously|in the past)\b|(ever|previously) (previously )?worked in any\b|been (directly )?employed (by|with) [\w&.,' -]+ in the past|(currently|in the past),? (or have you (in the past )?)?been employed by|been an? employee of|(former|previous|prior) employee|provided services to|\bare you,? or have you (ever )?been (directly )?employed (by|with|at|for)\b|\bhave you (ever )?been (directly )?employed (by|with|at|for)\b[^?]{0,140}\b(during|in|within|over) the (last|past|previous) (\d+|one|two|three|four|five|ten) (months|years)\b/i },   // "Are you, or have you been employed by <Co> during the last 5 years … or any of its companies?" (Newell SF 11-05, type AC; resume employers stay Yes by resume_employer)   // "certify whether you are a previous employee" (Allison 2026-11-03)
    { id: 'employee_statement', q: /which (one )?(of the following )?(statements?|options?) (best )?(applies|apply|describes?)( to)? (you|your (current )?(status|situation|relationship))/i, not: new RegExp(EMP_WORDS, 'i') },   // "Which statement best applies to you today?" + "I have never worked for <Co>…" (Oracle 2026-11-03); the answer picks only a never-worked-here option
    { id: 'on_assignment', q: /currently (on (an )?assignment|placed|working) as an? (contractor|consultant|temp)|currently on (an )?assignment\b.{0,80}(contractor|consultant|staffing|statement of work|master service)/i },   // "on assignment … as a contractor … at any affiliated <Co> companies" (GuideWell / Oracle 2026-11-03): No — a student, no contract work
    { id: 'notice_period', q: /^notice period\??$|(what is|how long is) your notice period|notice (period )?(required|needed) (to|before)/i },   // student, no job to leave: Available immediately (Joey 2026-11-03)
    { id: 'startup_fit', q: /(confident|comfortable|thrive|enjoy|willing) (working |to work )?in (a |an )?(fast[- ](moving|paced)|startup|start-up|ambiguous|high[- ]growth)|fast[- ](moving|paced),? startup[- ]like environment/i },   // self-assessment: Yes (Joey 2026-11-03)
    { id: 'publications', q: /(number of|how many) .{0,40}(publications|papers)|(peer[- ]reviewed|first[- ]author(ed)?) (publications|papers)|publications? (on which|where) you are/i },   // none yet (Joey 2026-11-03: 「0 篇」)
    { id: 'bond_declined', q: /bond(ing)? company|fidelity bond|fiduciary bond|declined, denied,? or revoked a bond/i },   // Joey 2026-11-03: No
    { id: 'military_status', q: /(hiring and supporting )?military service members and their spouses|disclose your (military|veteran) status|status as (a )?(military|service member)/i },   // not a service member or spouse (profile EEO)
    { id: 'noncompete', q: /non[- ]?compete|non[- ]?solicit|confidentiality agreement|restrict.*(ability|you) (to )?work/i },
    { id: 'government', q: /^(?!.*government[- ]?(issued|id\b|identification)).*(government|military|public official)/i },
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
    { id: 'certify', q: /^\*?\s*i certify\.?$|certify that (all )?(the )?(information|answers|statements)\b[^.?!]{0,120}\b(true|truthful|accurate|correct|complete)\b|certif(y|ication)\b.{0,60}(true|truthful|accurate|complete)|answers (are|were) (true|truthful|accurate)|information (given|provided|submitted)( by me)?( in this application)? is (true|accurate|correct|complete)/i },   // + "The information given by me in this application is true …" box (Bosch 11-04)
    { id: 'terms', q: /arbitration|terms (and|&) conditions|terms of (use|service)|user agreement|create (an |your )?account/i, consent: true },
    { id: 'marketing', q: /marketing (communication|email|message)s?|recruitment marketing|promotional (email|message)|newsletter/i },
    { id: 'sms', q: /text message|\bsms\b/i },
    { id: 'profile_visibility', q: /make (my|your) (candidate )?profile visible|profile visibility|(who|which recruiters) (can|may) (see|view|search) (my|your) (candidate )?profile/i },   // SuccessFactors register form (Newell 11-05): Joey's pick in config answers.profile_visibility; none set → unknown
    { id: 'future_contact', q: /talent (community|pool|network)|future (career )?(opportunit|contact|roles)|keep (me|my) (informed|on file|information)|job opportunities, career advice/i },
    { id: 'data_consent', q: /do you agree to (these|the) terms\??$|privacy (notice|policy|statement)|\backnowledge\b|\bconsent\b|\bi agree\b|by checking this box|store and process|process(ing)? (of )?my (personal )?(data|information)|(collect|process)\w* (and (process|store|use)\w* )?(your |the )?personal (data|information)/i },
  ];
  const DERIVED = {                                    // JSA-230: answers built from existing facts when the profile has none of its own
    preferred_last_name: () => P.answers.last_name && { text: P.answers.last_name.text },
    preferred_full_name: () => P.answers.preferred_name && P.answers.last_name && { text: `${P.answers.preferred_name.text} ${P.answers.last_name.text}` },
  };
  for (const r of R) {                                  // the profile's answer for each rule (pick entries are "/re/flags" strings)
    const a = P.answers[r.id] || (DERIVED[r.id] && DERIVED[r.id]());
    if (a) Object.assign(r, a, a.pick ? { pick: a.pick.map(RX) } : {});
  }
  // F-1: a "Yes" that claims unrestricted / permanent authorization is never his (Invesco 2026-11-01 picked "Yes, without restrictions")
  const WITHOUT_SPONS = /^(?:(?!\b(?:requir|need)\w*\b)[^?])*?\bwithout\b[^?]{0,40}\bsponsor/i;   // the question itself (before its '?') asks about working WITHOUT sponsorship, and does not first ask whether he requires it
  const SPONS_LATER = /\bfuture\b|after (you )?graduat|upon graduation|at any (point|time)|any time (after|in)|\blater\b|eventually|going forward|long[- ]term|full[- ]time (employment|role|position)/i;   // the question also covers after the internship
  const UNRESTRICTED = /without (any )?restriction|unrestricted|no restriction|permanent(ly)?|any employer|all employers|citizen|green card|permanent resident/i;
  const yesNo = (opts, yes) => {
    const strict = yes ? /^(yes|true)\b/i : /^(no|false)\b/i;
    const hit = (opts || []).find(o => strict.test(String(o).trim()) && !(RESTRICTED && yes && UNRESTRICTED.test(String(o))));
    if (hit || (opts || []).length > 2) return hit;   // a long list of statements ("I am a U.S. citizen…", an Ashby employer 10-31) is not a yes/no pair → unknown
    const re = yes ? /^(i am|i do|i will|i can)\b(?! not)/i : /^(i am not|i do not|i don't|i will not|i can't)\b/i;
    return (opts || []).find(o => re.test(String(o).trim()) && !(RESTRICTED && yes && UNRESTRICTED.test(String(o))));   // never "I am authorized to work permanently" (DeepSeek case 2026-11-01)
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
  const QA = (P.qa || []).filter(e => e && (e.q || e.match)).map((e, n) => Object.assign({}, e, { n: n + 1, nq: qaNorm(e.q),
    rx: e.match ? RX(e.match) : null, pick: (e.pick || []).map(RX) }));
  function qaFind(label) {                              // exact question (normalised), or the entry's own regex; a long
    const nl = qaNorm(label);                           // question may sit inside a label that adds help text after it
    return QA.find(e => (e.rx && e.rx.test(label)) || (e.nq && (nl === e.nq || (e.nq.length >= 40 && nl.startsWith(e.nq)))));
  }
  function qaAnswer(f, label) {
    const e = qaFind(label);
    if (!e) return null;
    const opts = f.o || f.options || [], id = 'qa:' + e.n;
    if (opts.length) {
      let o;
      for (const p of e.pick) { o = opts.find(x => p.test(String(x).trim())); if (o) break; }
      if (!o && e.text) o = opts.find(x => qaNorm(x) === qaNorm(e.text));
      if (!o && e.yes !== undefined) o = yesNo(opts, e.yes);
      if (!o && e.yes === true && f.t === 'checkbox' && opts.length === 1) o = opts[0];
      return o ? { status: 'ok', label, rule: id, value: o } : { status: 'unknown', label, rule: id, why: id + ': no option matches the saved answer', options: opts.slice(0, 8) };
    }
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
  const HIGH_RISK = new Set(['immigration_status', 'visa_details', 'auth_kind', 'sponsorship_type', 'spons_now', 'spons_future', 'on_opt',
    'eligibility_3way', 'authorized', 'gpa_threshold', 'visa_conditions', 'any_employer', 'auth_today', 'work_permit', 'citizen_pr', 'degree', 'degree_major', 'highest_ed', 'gpa', 'gpa_current',
    'misconduct', 'legal_dispute', 'debarred', 'background_drug']);
  const AUX_Q = /^(are|is|am|do|does|did|will|would|can|could|have|has|had|were|was|should|may)\b/i;
  const WH_Q = /^(what|which|when|where|how|list|name|state|specify|describe|explain|provide|please (provide|list|specify|state|describe|explain|indicate|share|enter|note|give))\b/i;
  function formCheck(label, opts, vals, rule) {        // pure (tested): null = the answer fits the question's form
    if (!HIGH_RISK.has(rule)) return null;
    const norm = x => String(x).replace(/\s+/g, ' ').trim().toLowerCase();
    if (opts.length && vals.every(v => opts.some(o => norm(o) === norm(v)))) return null;   // one of the question's own options
    const q = label.replace(/^\s*(\*|\d+[.)]|q\d+[.:])\s*/i, '').replace(/^(if (yes|so|applicable|no)[,:]?\s*)/i, '').trim();
    const isYN = v => /^(yes|no)\b/i.test(v);
    if (AUX_Q.test(q) && !/^if\b/i.test(label.trim()) && vals.some(v => !isYN(v))) return 'yes / no question answered ' + JSON.stringify(vals.join(', ')) + ' (' + rule + ')';
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
    const hits = R.filter(r => r.q.test(label) && !(r.not && r.not.test(label)));
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
  function answerFor(f, ctx) {
    const a = shapeCheck(f, answerByRules(f, ctx));
    const u = uncertainty(f, a); if (u) a.uncertain = u;
    if (a.status === 'ok' && !a.leave && !a.yn_text && textBox(f) && YN(a.value) && !/^qa:/.test(String(a.rule || ''))) {
      const q = qaAnswer(f, a.label);
      if (q && q.status === 'ok' && !YN(q.value)) return Object.assign(q, { over: a.rule });
    }
    if (a.status !== 'unknown' || (a.ask && !a.qa_ok)) return a;   // qa_ok: an "ask" a saved answer may settle (references, JSA-210)
    return qaAnswer(f, a.label) || a;
  }
  answerFor.qaAnswer = qaAnswer;   // for runner/rules_bridge.js: its text-box guard tries the saved answers before giving up (JSA-205)
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
    { t: 'work_auth', rules: ['visa_expiry', 'authorized', 'any_employer', 'auth_today', 'work_permit', 'citizen_pr', 'spons_now', 'spons_future', 'sponsorship_type', 'eligibility_3way', 'on_opt', 'citizenship_country', 'reside_us'],
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
  function answerByRules(f, ctx) {
    const label = (f.l || f.label || '').replace(/\s+/g, ' ').trim();
    const opts = f.o || f.options || [];
    const hits = R.filter(r => r.q.test(label) && !(r.not && r.not.test(label)) && !(f._noThreshold && r.id === 'gpa_threshold'));   // r.not: label words that rule the rule out
    const refs = hits.find(h => h.id === 'references');   // JSA-210: references = other people's contact details — never his own name / e-mail / phone
    if (refs) return refs.text && !opts.length ? { status: 'ok', label, rule: 'references', value: refs.text }
      : { status: 'unknown', label, rule: 'references', ask: true, qa_ok: true, why: 'references: other people\'s contact details — none on file; the user gives them (never his own e-mail / phone / name)' };
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
    if (hits.length > 1 && !agree && hits[1].id !== r.id && !(r.id === 'onsite' && hits.every(h => ['onsite', 'data_consent'].includes(h.id))) && !['auth_today', 'spons_now', 'spons_future', 'any_employer', 'authorized'].includes(r.id) && !/^(sms|future_contact|marketing|terms|data_consent)$/.test(r.id)) {
      // two different rules → ambiguous unless the first is a known-specific rule
      const specific = ['location_rank', 'hs_name', 'name_pronunciation', 'visa_expiry', 'ft_start', 'education_list', 'secondary_email', 'gpa_threshold', 'visa_conditions', 'local_area', 'military_status', 'permanent_address', 'good_standing', 'college_years_completed', 'college_year_current', 'legal_dispute', 'license_state_class', 'citizen_pr', 'visa_details', 'interviewed_before', 'undergrad_year', 'noncompete_detail', 'know_employee', 'debarred', 'industry_investor', 'industry_side_role', 'other_jobs', 'conflict_interest', 'eligibility_3way', 'language_level', 'contact_employer', 'interview_travel', 'background_drug', 'driver_license', 'work_arrangement', 'city_state_zip', 'immigration_status', 'prev_employed', 'prior_employer', 'resume_employer', 'internship_mandatory', 'enrolled_during', 'office_all', 'intern_when', 'has_preferred', 'avail_season', 'middle_initial', 'employer', 'lives_outside_us', 'school_level', 'relative_names', 'relatives', 'certify', 'preferred_full_name', 'preferred_last_name', 'preferred_name', 'full_time_summer', 'python_r', 'hours', 'noncompete', 'first_name', 'last_name', 'email', 'phone_device', 'phone_code', 'phone', 'linkedin', 'hispanic', 'transgender', 'orientation', 'pronouns', 'dob_minor', 'age18', 'start_date', 'grad_date', 'highest_ed', 'gpa', 'zip', 'city', 'state', 'address', 'school', 'degree', 'discipline', 'location', 'full_name', 'auth_kind', 'start_month', 'start_year', 'end_month', 'end_year'];
      if (!specific.includes(r.id)) return { status: 'unknown', label, why: 'ambiguous: ' + hits.map(h => h.id).join('/') };
    }
    // options that say "for ANY employer" / "without restriction" turn a generic authorization question into the any-employer one (F-1: No)
    if (RESTRICTED && r.id === 'authorized' && opts.some(o => /^yes,? (but )?with (some )?restrictions?\b/i.test(String(o).trim())))   // the precise F-1 / CPT answer when offered (Invesco 2026-11-01)
      return { status: 'ok', label, rule: r.id, value: opts.find(o => /^yes,? (but )?with (some )?restrictions?\b/i.test(String(o).trim())) };
    if (RESTRICTED && r.id === 'authorized' && opts.length && opts.filter(o => /^(yes|i am|i have)\b/i.test(String(o).trim())).length && opts.filter(o => /^(yes|i am|i have)\b/i.test(String(o).trim())).every(o => UNRESTRICTED.test(o))) {
      const no = yesNo(opts, false);                      // every "yes" claims unrestricted / permanent / citizen → the honest pick is No
      if (no) return { status: 'ok', label, rule: 'any_employer', value: no };
    }
    if (RESTRICTED && r.id === 'authorized' && opts.some(o => /any employer|without (any )?restriction|unrestricted/i.test(o))) {
      const o = opts.find(x => /^yes,? (but )?with (some )?restrictions?\b/i.test(x.trim())) || opts.find(x => /^no\b/i.test(x.trim()) && /any employer|restriction/i.test(x)) || yesNo(opts, false);   // "Yes, with restrictions" = F-1 on CPT (Invesco 2026-11-01)
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
      const need = (r.id === 'spons_future' && !SPONS_LATER.test(label) && typeof (P.answers.spons_now || {}).yes === 'boolean') ? P.answers.spons_now.yes : r.yes;
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
    if (r.id === 'grad_date' && /\bmm\s*\/\s*yy\b(?!yy)/i.test(label) && r.mmyy) return { status: 'ok', label, rule: 'grad_date_mmyy', value: r.mmyy };   // "(MM/YY)" → 12/27
    const out = { status: 'ok', label, rule: r.id };
    if (r.all && opts.length) {   // multi-select of offices / cities: he goes anywhere in the U.S. → all of them
      const keep = opts.filter(o => !/decline|prefer not|none|other/i.test(o));
      if (keep.length) return Object.assign(out, { value: keep.join(' | ') });
    }
    if (r.note) out.note = r.note;
    if (opts.length) {
      let o;
      const pickable = r.id === 'how_heard' ? opts.filter(x => !REF_OPT.test(String(x)) && !PERSON_OPT.test(String(x))) : opts;   // nor a recruiter / employee / friend (JSA-219)   // "Employee referral" is never his source (JSA-195): he applies on his own
      if (r.pick) for (const p of r.pick) { o = pickable.find(x => p.test(x.trim())) || (r.id === 'discipline' ? pickable.find(x => parts(x).some(y => p.test(y))) : undefined); if (o) break; }   // JSA-198: a combined major option ("Data Science / Analytics") matches by its parts, in the profile's order
      if (!o && r.yes === true && f.t === 'checkbox' && opts.length === 1) o = opts[0];
      if (!o && r.yes !== undefined) o = yesNo(opts, r.yes);
      if (!o && r.id === 'age18') o = yesNo(opts, true);
      if (!o && /^(degree|college_year_current)$/.test(r.id)) o = opts.find(x => /^other\b/i.test(x.trim()));
      if (!o && r.id === 'enrolled' && !opts.some(x => /^(yes|no)\b/i.test(x.trim()))) o = opts.find(x => /master/i.test(x));   // "Are you currently enrolled in school?" with level options → the master's one   // a master's student where only BA / BS / Ph.D (or Freshman…Senior) are offered (Bosch 11-04)
      if (!o && f.t === 'checkbox' && opts.length === 1 && r.yes === false) return { status: 'ok', label, rule: r.id, leave: true };
      if (!o) return { status: 'unknown', label, why: 'no matching option for ' + r.id, options: opts.slice(0, 8) };
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
  if (typeof module !== 'undefined') module.exports = { R, match, answerFor, jdYears, ageBand, poolCheck, coNorm, qtypes, shapeCheck, uncertainty, formCheck, qaAnswer };
})(typeof window !== 'undefined' ? window : globalThis);
