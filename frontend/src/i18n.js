import i18n from 'i18next'
import { initReactI18next } from 'react-i18next'

// UI chrome translations. Data values (district / trade names) stay in their official English form.
const en = {
  app: 'SkillSight', tagline: 'Labour Market Intelligence System', ministry: 'Ministry of Skill Development & Entrepreneurship',
  nav: { overview: 'National command centre', map: 'Geo drill-down', trades: 'Trade explorer', alerts: 'Early warnings', planner: 'Target planner', whatif: 'What-if simulator', mobility: 'Migration & mobility', skills: 'Skills & curriculum', data: 'Data hub', reports: 'Reports & API', method: 'Methodology' },
  group: { intel: 'Intelligence', decide: 'Decide', platform: 'Platform' },
  f: { state: 'State', sector: 'Sector', all_states: 'All pilot states', all_sectors: 'All sectors', trade: 'Trade', district: 'District', all_trades: 'All trades' },
  synthetic: 'Synthetic demonstration data — not official government statistics',
  kpi: { demand: 'Forecast demand (12 m)', supply: 'Expected certified supply', unmet: 'Unmet demand', excess: 'Excess supply', seats: 'Training seats', growth: 'vs last 12 months', invest: 'from announced projects', cells: 'district-trade cells', alerts: 'Active early warnings' },
  status: { 'Acute shortage': 'Acute shortage', Shortage: 'Shortage', Balanced: 'Balanced', Saturating: 'Saturating', Oversupplied: 'Oversupplied' },
  kind: { acute_shortage: 'Acute shortage', saturation: 'Saturation', emerging_shortage: 'Emerging shortage', emerging_saturation: 'Emerging saturation' },
  t: {
    trend: 'Demand trend and forecast', trend_sub: 'Unified Labour Demand Index (openings per month); shaded band = 80% prediction interval',
    top_short: 'Most under-served trades', top_surplus: 'Most saturated trades', map_title: 'Demand–supply gap by district', map_sub: 'Next 12 months · red = shortage, blue = oversupply · click a district to drill down',
    ticker: 'Early-warning feed', view_all: 'View all', gap_ratio: 'Gap ratio', severity: 'Severity', trust: 'Data trust', probability: 'Probability', lead: 'Expected by',
    demand: 'Demand', supply: 'Supply', gap: 'Gap', seats: 'Seats', status: 'Status', trade: 'Trade', district: 'District', state: 'State', sector: 'Sector',
    drivers: 'What is driving this', history: 'History', forecast: 'Forecast', actual: 'Actual', table_view: 'Table view', chart_view: 'Chart view',
    run: 'Run', running: 'Running…', export: 'Export', download: 'Download', save: 'Save', loading: 'Loading…', none: 'Nothing to show for this selection.',
    ask: 'Ask Disha', ask_ph: 'Ask about shortages, forecasts, reskilling…', copilot: 'Disha · planning copilot', read_aloud: 'Read aloud', language: 'Language', theme: 'Theme', text_size: 'Text size',
    light: 'Light', dark: 'Dark', contrast: 'High contrast', back: 'Back', national: 'All pilot states', quarters: 'Quarterly outlook', ledger: 'Forecast accountability', backtest: 'Model backtest',
    pathways: 'Pivot pathways (re-skilling bridges)', curriculum: 'Curriculum drift radar', freshness: 'QP freshness', missing: 'Missing skills', stale: 'Rarely demanded', dsdp: 'District Skill Development Plan',
    acknowledge: 'Acknowledge', assign: 'Assign', dismiss: 'Dismiss', generate: 'Generate', optimise: 'Optimise targets', what_if: 'Simulate project',
  },
}

const hi = {
  app: 'स्किलसाइट', tagline: 'श्रम बाज़ार आसूचना प्रणाली', ministry: 'कौशल विकास एवं उद्यमशीलता मंत्रालय',
  nav: { overview: 'राष्ट्रीय कमान केंद्र', map: 'भौगोलिक विश्लेषण', trades: 'ट्रेड एक्सप्लोरर', alerts: 'प्रारंभिक चेतावनियाँ', planner: 'लक्ष्य योजनाकार', whatif: 'क्या-अगर सिम्युलेटर', mobility: 'प्रवासन एवं गतिशीलता', skills: 'कौशल एवं पाठ्यक्रम', data: 'डेटा हब', reports: 'रिपोर्ट एवं API', method: 'कार्यप्रणाली' },
  group: { intel: 'आसूचना', decide: 'निर्णय', platform: 'प्लेटफ़ॉर्म' },
  f: { state: 'राज्य', sector: 'क्षेत्र', all_states: 'सभी पायलट राज्य', all_sectors: 'सभी क्षेत्र', trade: 'ट्रेड', district: 'जिला', all_trades: 'सभी ट्रेड' },
  synthetic: 'सिंथेटिक प्रदर्शन डेटा — आधिकारिक सरकारी आँकड़े नहीं',
  kpi: { demand: 'अनुमानित मांग (12 माह)', supply: 'अपेक्षित प्रमाणित आपूर्ति', unmet: 'अपूर्ण मांग', excess: 'अतिरिक्त आपूर्ति', seats: 'प्रशिक्षण सीटें', growth: 'पिछले 12 माह की तुलना में', invest: 'घोषित परियोजनाओं से', cells: 'जिला-ट्रेड इकाइयाँ', alerts: 'सक्रिय चेतावनियाँ' },
  status: { 'Acute shortage': 'गंभीर कमी', Shortage: 'कमी', Balanced: 'संतुलित', Saturating: 'संतृप्ति की ओर', Oversupplied: 'अधिक आपूर्ति' },
  kind: { acute_shortage: 'गंभीर कमी', saturation: 'संतृप्ति', emerging_shortage: 'उभरती कमी', emerging_saturation: 'उभरती संतृप्ति' },
  t: {
    trend: 'मांग प्रवृत्ति एवं पूर्वानुमान', trend_sub: 'एकीकृत श्रम मांग सूचकांक (मासिक रिक्तियाँ); छायांकित पट्टी = 80% पूर्वानुमान अंतराल',
    top_short: 'सबसे कम सेवित ट्रेड', top_surplus: 'सबसे संतृप्त ट्रेड', map_title: 'जिलेवार मांग–आपूर्ति अंतर', map_sub: 'अगले 12 माह · लाल = कमी, नीला = अधिक आपूर्ति · जिले पर क्लिक करें',
    ticker: 'प्रारंभिक चेतावनी फ़ीड', view_all: 'सभी देखें', gap_ratio: 'अंतर अनुपात', severity: 'गंभीरता', trust: 'डेटा विश्वसनीयता', probability: 'संभावना', lead: 'अपेक्षित समय',
    demand: 'मांग', supply: 'आपूर्ति', gap: 'अंतर', seats: 'सीटें', status: 'स्थिति', trade: 'ट्रेड', district: 'जिला', state: 'राज्य', sector: 'क्षेत्र',
    drivers: 'इसके कारण', history: 'इतिहास', forecast: 'पूर्वानुमान', actual: 'वास्तविक', table_view: 'तालिका दृश्य', chart_view: 'चार्ट दृश्य',
    run: 'चलाएँ', running: 'चल रहा है…', export: 'निर्यात', download: 'डाउनलोड', save: 'सहेजें', loading: 'लोड हो रहा है…', none: 'इस चयन के लिए कुछ नहीं।',
    ask: 'दिशा से पूछें', ask_ph: 'कमी, पूर्वानुमान, पुनः कौशल के बारे में पूछें…', copilot: 'दिशा · योजना सहायक', read_aloud: 'पढ़कर सुनाएँ', language: 'भाषा', theme: 'थीम', text_size: 'अक्षर आकार',
    light: 'हल्का', dark: 'गहरा', contrast: 'उच्च कंट्रास्ट', back: 'वापस', national: 'सभी पायलट राज्य', quarters: 'तिमाही परिदृश्य', ledger: 'पूर्वानुमान जवाबदेही', backtest: 'मॉडल बैकटेस्ट',
    pathways: 'पुनः कौशल मार्ग', curriculum: 'पाठ्यक्रम विचलन रडार', freshness: 'QP ताज़गी', missing: 'अनुपलब्ध कौशल', stale: 'कम मांग वाले', dsdp: 'जिला कौशल विकास योजना',
    acknowledge: 'स्वीकारें', assign: 'सौंपें', dismiss: 'ख़ारिज करें', generate: 'तैयार करें', optimise: 'लक्ष्य अनुकूलित करें', what_if: 'परियोजना सिम्युलेट करें',
  },
}

const kn = {
  app: 'ಸ್ಕಿಲ್‌ಸೈಟ್', tagline: 'ಕಾರ್ಮಿಕ ಮಾರುಕಟ್ಟೆ ಗುಪ್ತಚರ ವ್ಯವಸ್ಥೆ', ministry: 'ಕೌಶಲ್ಯಾಭಿವೃದ್ಧಿ ಮತ್ತು ಉದ್ಯಮಶೀಲತೆ ಸಚಿವಾಲಯ',
  nav: { overview: 'ರಾಷ್ಟ್ರೀಯ ಕಮಾಂಡ್ ಕೇಂದ್ರ', map: 'ಭೌಗೋಳಿಕ ವಿಶ್ಲೇಷಣೆ', trades: 'ವೃತ್ತಿ ಅನ್ವೇಷಕ', alerts: 'ಮುನ್ನೆಚ್ಚರಿಕೆಗಳು', planner: 'ಗುರಿ ಯೋಜಕ', whatif: 'ಏನಾದರೆ ಸಿಮ್ಯುಲೇಟರ್', mobility: 'ವಲಸೆ ಮತ್ತು ಚಲನಶೀಲತೆ', skills: 'ಕೌಶಲ್ಯ ಮತ್ತು ಪಠ್ಯಕ್ರಮ', data: 'ಡೇಟಾ ಹಬ್', reports: 'ವರದಿಗಳು ಮತ್ತು API', method: 'ವಿಧಾನ' },
  group: { intel: 'ಗುಪ್ತಚರ', decide: 'ನಿರ್ಧಾರ', platform: 'ವೇದಿಕೆ' },
  f: { state: 'ರಾಜ್ಯ', sector: 'ವಲಯ', all_states: 'ಎಲ್ಲಾ ಪೈಲಟ್ ರಾಜ್ಯಗಳು', all_sectors: 'ಎಲ್ಲಾ ವಲಯಗಳು', trade: 'ವೃತ್ತಿ', district: 'ಜಿಲ್ಲೆ', all_trades: 'ಎಲ್ಲಾ ವೃತ್ತಿಗಳು' },
  synthetic: 'ಕೃತಕ ಪ್ರದರ್ಶನ ಡೇಟಾ — ಅಧಿಕೃತ ಸರ್ಕಾರಿ ಅಂಕಿಅಂಶಗಳಲ್ಲ',
  kpi: { demand: 'ಮುನ್ಸೂಚಿತ ಬೇಡಿಕೆ (12 ತಿಂ)', supply: 'ನಿರೀಕ್ಷಿತ ಪ್ರಮಾಣೀಕೃತ ಪೂರೈಕೆ', unmet: 'ಪೂರೈಸದ ಬೇಡಿಕೆ', excess: 'ಹೆಚ್ಚುವರಿ ಪೂರೈಕೆ', seats: 'ತರಬೇತಿ ಸೀಟುಗಳು', growth: 'ಕಳೆದ 12 ತಿಂಗಳಿಗೆ ಹೋಲಿಸಿದರೆ', invest: 'ಘೋಷಿತ ಯೋಜನೆಗಳಿಂದ', cells: 'ಜಿಲ್ಲೆ-ವೃತ್ತಿ ಘಟಕಗಳು', alerts: 'ಸಕ್ರಿಯ ಎಚ್ಚರಿಕೆಗಳು' },
  status: { 'Acute shortage': 'ತೀವ್ರ ಕೊರತೆ', Shortage: 'ಕೊರತೆ', Balanced: 'ಸಮತೋಲನ', Saturating: 'ಸಂತೃಪ್ತಿಯತ್ತ', Oversupplied: 'ಅತಿಯಾದ ಪೂರೈಕೆ' },
  kind: { acute_shortage: 'ತೀವ್ರ ಕೊರತೆ', saturation: 'ಸಂತೃಪ್ತಿ', emerging_shortage: 'ಉದಯೋನ್ಮುಖ ಕೊರತೆ', emerging_saturation: 'ಉದಯೋನ್ಮುಖ ಸಂತೃಪ್ತಿ' },
  t: { trend: 'ಬೇಡಿಕೆ ಪ್ರವೃತ್ತಿ ಮತ್ತು ಮುನ್ಸೂಚನೆ', top_short: 'ಕಡಿಮೆ ಸೇವೆ ಪಡೆದ ವೃತ್ತಿಗಳು', top_surplus: 'ಅತಿ ಸಂತೃಪ್ತ ವೃತ್ತಿಗಳು', map_title: 'ಜಿಲ್ಲಾವಾರು ಬೇಡಿಕೆ–ಪೂರೈಕೆ ಅಂತರ', ticker: 'ಮುನ್ನೆಚ್ಚರಿಕೆ ಫೀಡ್', view_all: 'ಎಲ್ಲವನ್ನೂ ನೋಡಿ',
    demand: 'ಬೇಡಿಕೆ', supply: 'ಪೂರೈಕೆ', gap: 'ಅಂತರ', seats: 'ಸೀಟುಗಳು', status: 'ಸ್ಥಿತಿ', trade: 'ವೃತ್ತಿ', district: 'ಜಿಲ್ಲೆ', state: 'ರಾಜ್ಯ', severity: 'ತೀವ್ರತೆ', trust: 'ಡೇಟಾ ವಿಶ್ವಾಸಾರ್ಹತೆ', probability: 'ಸಂಭವನೀಯತೆ',
    ask: 'ದಿಶಾಳನ್ನು ಕೇಳಿ', ask_ph: 'ಕೊರತೆ, ಮುನ್ಸೂಚನೆ, ಮರುಕೌಶಲ್ಯದ ಬಗ್ಗೆ ಕೇಳಿ…', copilot: 'ದಿಶಾ · ಯೋಜನಾ ಸಹಾಯಕ', language: 'ಭಾಷೆ', theme: 'ಥೀಮ್', text_size: 'ಅಕ್ಷರ ಗಾತ್ರ', light: 'ಬೆಳಕು', dark: 'ಗಾಢ', contrast: 'ಹೆಚ್ಚಿನ ಕಾಂಟ್ರಾಸ್ಟ್',
    pathways: 'ಮರುಕೌಶಲ್ಯ ಮಾರ್ಗಗಳು', curriculum: 'ಪಠ್ಯಕ್ರಮ ವ್ಯತ್ಯಾಸ ರಾಡಾರ್', dsdp: 'ಜಿಲ್ಲಾ ಕೌಶಲ್ಯಾಭಿವೃದ್ಧಿ ಯೋಜನೆ', optimise: 'ಗುರಿಗಳನ್ನು ಅತ್ಯುತ್ತಮಗೊಳಿಸಿ', what_if: 'ಯೋಜನೆಯನ್ನು ಅನುಕರಿಸಿ', loading: 'ಲೋಡ್ ಆಗುತ್ತಿದೆ…' },
}

const mr = {
  app: 'स्किलसाइट', tagline: 'कामगार बाजार माहिती प्रणाली', ministry: 'कौशल्य विकास व उद्योजकता मंत्रालय',
  nav: { overview: 'राष्ट्रीय कमांड केंद्र', map: 'भौगोलिक विश्लेषण', trades: 'व्यवसाय एक्सप्लोरर', alerts: 'पूर्वसूचना', planner: 'लक्ष्य नियोजक', whatif: 'जर-तर सिम्युलेटर', mobility: 'स्थलांतर व गतिशीलता', skills: 'कौशल्य व अभ्यासक्रम', data: 'डेटा हब', reports: 'अहवाल व API', method: 'कार्यपद्धती' },
  group: { intel: 'माहिती', decide: 'निर्णय', platform: 'प्लॅटफॉर्म' },
  f: { state: 'राज्य', sector: 'क्षेत्र', all_states: 'सर्व पायलट राज्ये', all_sectors: 'सर्व क्षेत्रे', trade: 'व्यवसाय', district: 'जिल्हा', all_trades: 'सर्व व्यवसाय' },
  synthetic: 'कृत्रिम प्रात्यक्षिक डेटा — अधिकृत सरकारी आकडेवारी नाही',
  kpi: { demand: 'अंदाजित मागणी (12 म)', supply: 'अपेक्षित प्रमाणित पुरवठा', unmet: 'अपूर्ण मागणी', excess: 'अतिरिक्त पुरवठा', seats: 'प्रशिक्षण जागा', growth: 'मागील 12 महिन्यांच्या तुलनेत', invest: 'घोषित प्रकल्पांमुळे', cells: 'जिल्हा-व्यवसाय घटक', alerts: 'सक्रिय पूर्वसूचना' },
  status: { 'Acute shortage': 'तीव्र टंचाई', Shortage: 'टंचाई', Balanced: 'संतुलित', Saturating: 'संपृक्ततेकडे', Oversupplied: 'अतिपुरवठा' },
  kind: { acute_shortage: 'तीव्र टंचाई', saturation: 'संपृक्तता', emerging_shortage: 'उदयोन्मुख टंचाई', emerging_saturation: 'उदयोन्मुख संपृक्तता' },
  t: { trend: 'मागणी कल व अंदाज', top_short: 'सर्वात कमी सेवा मिळालेले व्यवसाय', top_surplus: 'सर्वाधिक संपृक्त व्यवसाय', map_title: 'जिल्हानिहाय मागणी–पुरवठा तफावत', ticker: 'पूर्वसूचना फीड', view_all: 'सर्व पहा',
    demand: 'मागणी', supply: 'पुरवठा', gap: 'तफावत', seats: 'जागा', status: 'स्थिती', trade: 'व्यवसाय', district: 'जिल्हा', state: 'राज्य', severity: 'तीव्रता', trust: 'डेटा विश्वासार्हता', probability: 'संभाव्यता',
    ask: 'दिशाला विचारा', ask_ph: 'टंचाई, अंदाज, पुनर्कौशल्य याबद्दल विचारा…', copilot: 'दिशा · नियोजन सहाय्यक', language: 'भाषा', theme: 'थीम', text_size: 'अक्षर आकार', light: 'फिकट', dark: 'गडद', contrast: 'उच्च कॉन्ट्रास्ट',
    pathways: 'पुनर्कौशल्य मार्ग', curriculum: 'अभ्यासक्रम विचलन रडार', dsdp: 'जिल्हा कौशल्य विकास आराखडा', optimise: 'लक्ष्ये अनुकूल करा', what_if: 'प्रकल्प सिम्युलेट करा', loading: 'लोड होत आहे…' },
}

const or = {
  app: 'ସ୍କିଲସାଇଟ୍', tagline: 'ଶ୍ରମ ବଜାର ସୂଚନା ପ୍ରଣାଳୀ', ministry: 'ଦକ୍ଷତା ବିକାଶ ଓ ଉଦ୍ୟମିତା ମନ୍ତ୍ରଣାଳୟ',
  nav: { overview: 'ଜାତୀୟ କମାଣ୍ଡ କେନ୍ଦ୍ର', map: 'ଭୌଗୋଳିକ ବିଶ୍ଳେଷଣ', trades: 'ବୃତ୍ତି ଅନୁସନ୍ଧାନ', alerts: 'ପୂର୍ବ ଚେତାବନୀ', planner: 'ଲକ୍ଷ୍ୟ ଯୋଜନାକାରୀ', whatif: 'ଯଦି-ତେବେ ସିମୁଲେଟର', mobility: 'ପ୍ରବାସନ ଓ ଗତିଶୀଳତା', skills: 'ଦକ୍ଷତା ଓ ପାଠ୍ୟକ୍ରମ', data: 'ଡାଟା ହବ୍', reports: 'ରିପୋର୍ଟ ଓ API', method: 'ପଦ୍ଧତି' },
  group: { intel: 'ସୂଚନା', decide: 'ନିଷ୍ପତ୍ତି', platform: 'ପ୍ଲାଟଫର୍ମ' },
  f: { state: 'ରାଜ୍ୟ', sector: 'କ୍ଷେତ୍ର', all_states: 'ସମସ୍ତ ପାଇଲଟ୍ ରାଜ୍ୟ', all_sectors: 'ସମସ୍ତ କ୍ଷେତ୍ର', trade: 'ବୃତ୍ତି', district: 'ଜିଲ୍ଲା', all_trades: 'ସମସ୍ତ ବୃତ୍ତି' },
  synthetic: 'କୃତ୍ରିମ ପ୍ରଦର୍ଶନ ଡାଟା — ସରକାରୀ ପରିସଂଖ୍ୟାନ ନୁହେଁ',
  kpi: { demand: 'ପୂର୍ବାନୁମାନିତ ଚାହିଦା (12 ମାସ)', supply: 'ଆଶା କରାଯାଉଥିବା ପ୍ରମାଣିତ ଯୋଗାଣ', unmet: 'ଅପୂରଣ ଚାହିଦା', excess: 'ଅତିରିକ୍ତ ଯୋଗାଣ', seats: 'ତାଲିମ ସିଟ୍', growth: 'ଗତ 12 ମାସ ତୁଳନାରେ', invest: 'ଘୋଷିତ ପ୍ରକଳ୍ପରୁ', cells: 'ଜିଲ୍ଲା-ବୃତ୍ତି ଏକକ', alerts: 'ସକ୍ରିୟ ଚେତାବନୀ' },
  status: { 'Acute shortage': 'ଗୁରୁତର ଅଭାବ', Shortage: 'ଅଭାବ', Balanced: 'ସନ୍ତୁଳିତ', Saturating: 'ସନ୍ତୃପ୍ତି ଆଡକୁ', Oversupplied: 'ଅତ୍ୟଧିକ ଯୋଗାଣ' },
  kind: { acute_shortage: 'ଗୁରୁତର ଅଭାବ', saturation: 'ସନ୍ତୃପ୍ତି', emerging_shortage: 'ଉଦୀୟମାନ ଅଭାବ', emerging_saturation: 'ଉଦୀୟମାନ ସନ୍ତୃପ୍ତି' },
  t: { trend: 'ଚାହିଦା ଧାରା ଓ ପୂର୍ବାନୁମାନ', top_short: 'ସବୁଠାରୁ କମ୍ ସେବିତ ବୃତ୍ତି', top_surplus: 'ସବୁଠାରୁ ସନ୍ତୃପ୍ତ ବୃତ୍ତି', map_title: 'ଜିଲ୍ଲାୱାରୀ ଚାହିଦା–ଯୋଗାଣ ବ୍ୟବଧାନ', ticker: 'ପୂର୍ବ ଚେତାବନୀ ଫିଡ୍', view_all: 'ସବୁ ଦେଖନ୍ତୁ',
    demand: 'ଚାହିଦା', supply: 'ଯୋଗାଣ', gap: 'ବ୍ୟବଧାନ', seats: 'ସିଟ୍', status: 'ସ୍ଥିତି', trade: 'ବୃତ୍ତି', district: 'ଜିଲ୍ଲା', state: 'ରାଜ୍ୟ', severity: 'ଗୁରୁତ୍ୱ', trust: 'ଡାଟା ବିଶ୍ୱସନୀୟତା', probability: 'ସମ୍ଭାବନା',
    ask: 'ଦିଶାଙ୍କୁ ପଚାରନ୍ତୁ', ask_ph: 'ଅଭାବ, ପୂର୍ବାନୁମାନ, ପୁନଃଦକ୍ଷତା ବିଷୟରେ ପଚାରନ୍ତୁ…', copilot: 'ଦିଶା · ଯୋଜନା ସହାୟକ', language: 'ଭାଷା', theme: 'ଥିମ୍', text_size: 'ଅକ୍ଷର ଆକାର', light: 'ହାଲୁକା', dark: 'ଗାଢ଼', contrast: 'ଉଚ୍ଚ କଣ୍ଟ୍ରାଷ୍ଟ',
    pathways: 'ପୁନଃଦକ୍ଷତା ମାର୍ଗ', curriculum: 'ପାଠ୍ୟକ୍ରମ ବିଚ୍ୟୁତି ରାଡାର', dsdp: 'ଜିଲ୍ଲା ଦକ୍ଷତା ବିକାଶ ଯୋଜନା', optimise: 'ଲକ୍ଷ୍ୟ ଅନୁକୂଳ କରନ୍ତୁ', what_if: 'ପ୍ରକଳ୍ପ ସିମୁଲେଟ କରନ୍ତୁ', loading: 'ଲୋଡ୍ ହେଉଛି…' },
}

export const LANGS = [['en', 'English'], ['hi', 'हिन्दी'], ['kn', 'ಕನ್ನಡ'], ['mr', 'मराठी'], ['or', 'ଓଡ଼ିଆ']]
const fromUrl = new URLSearchParams(location.search).get('lang')
const stored = fromUrl || (() => { try { return localStorage.getItem('lmis-lang') } catch { return null } })()

i18n.use(initReactI18next).init({
  resources: { en: { translation: en }, hi: { translation: hi }, kn: { translation: kn }, mr: { translation: mr }, or: { translation: or } },
  lng: stored || 'en', fallbackLng: 'en', interpolation: { escapeValue: false },
})
i18n.on('languageChanged', (l) => { document.documentElement.lang = l; try { localStorage.setItem('lmis-lang', l) } catch { /* storage unavailable */ } })
document.documentElement.lang = i18n.language
export default i18n
