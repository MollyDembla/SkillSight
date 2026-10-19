"""Static reference taxonomy: pilot geography, trades (NCO-2015 / NSQF QP), skills and staffing.

NCO and QP codes are illustrative mappings chosen for the pilot; they must be verified against the
official NCO-2015 and NQR registers before operational use.
"""
from __future__ import annotations
import json
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent / "data"

PILOT_STATES = ["Karnataka", "Maharashtra", "Odisha", "Uttar Pradesh"]

# Urban/industrial hubs: (urbanisation 0-1, population weight multiplier)
HUBS = {
    "Bengaluru Urban": (1.0, 4.2), "Mumbai": (1.0, 4.0), "Pune": (0.9, 3.4), "Thane": (0.9, 3.2),
    "Nagpur": (0.75, 2.0), "Gautam Buddha Nagar": (0.9, 2.4), "Ghaziabad": (0.85, 2.2), "Lucknow": (0.8, 2.4),
    "Kanpur Nagar": (0.7, 2.0), "Khordha": (0.75, 1.9), "Cuttack": (0.6, 1.4), "Mysuru": (0.6, 1.4),
    "Nashik": (0.6, 1.8), "Aurangabad": (0.6, 1.6), "Dharwad": (0.55, 1.2), "Dakshina Kannada": (0.6, 1.3),
    "Agra": (0.55, 1.6), "Varanasi": (0.55, 1.6), "Prayagraj": (0.5, 1.7), "Meerut": (0.55, 1.6),
    "Sundargarh": (0.5, 1.2), "Angul": (0.45, 1.0), "Jharsuguda": (0.5, 0.9), "Belagavi": (0.45, 1.6),
    "Kalaburagi": (0.4, 1.2), "Kolhapur": (0.5, 1.4), "Raigad": (0.55, 1.2), "Palghar": (0.5, 1.2),
    "Ganjam": (0.35, 1.5), "Gorakhpur": (0.45, 1.6), "Bareilly": (0.45, 1.4), "Aligarh": (0.45, 1.3),
}

# NITI Aayog Aspirational Districts within the pilot states.
ASPIRATIONAL = {
    "Raichur", "Yadgir", "Gadchiroli", "Nandurbar", "Washim", "Osmanabad", "Kalahandi", "Koraput",
    "Malkangiri", "Nabarangapur", "Rayagada", "Kandhamal", "Gajapati", "Balangir", "Nuapada", "Dhenkanal",
    "Bahraich", "Shrawasti", "Balrampur", "Siddharthnagar", "Chitrakoot", "Sonbhadra", "Chandauli", "Fatehpur",
}

# Districts whose workers commonly migrate out (origin propensity 0-1).
MIGRANT_ORIGINS = {
    "Ganjam": 0.55, "Balangir": 0.45, "Kalahandi": 0.4, "Nuapada": 0.45, "Kendrapara": 0.35, "Gajapati": 0.35,
    "Azamgarh": 0.5, "Gorakhpur": 0.4, "Ballia": 0.45, "Jaunpur": 0.45, "Ghazipur": 0.4, "Deoria": 0.4,
    "Siddharthnagar": 0.4, "Bahraich": 0.35, "Gonda": 0.35, "Basti": 0.35, "Yadgir": 0.35, "Raichur": 0.3,
    "Kalaburagi": 0.3, "Osmanabad": 0.3, "Beed": 0.35, "Nanded": 0.25,
}
MIGRANT_DESTINATIONS = {"Bengaluru Urban": 0.3, "Mumbai": 0.22, "Pune": 0.16, "Thane": 0.12, "Gautam Buddha Nagar": 0.1, "Ghaziabad": 0.05, "Khordha": 0.05}

SECTORS = {
    "RE": "Renewable energy",
    "EV": "Electronics & e-mobility",
    "HC": "Healthcare",
    "IT": "IT-ITeS & digital",
    "LG": "Logistics",
    "CN": "Construction",
}

# Sector clusters: district -> {sector: demand multiplier}
CLUSTERS = {
    "Pune": {"EV": 2.4, "IT": 1.8}, "Bengaluru Urban": {"IT": 2.6, "EV": 1.8, "HC": 1.3},
    "Gautam Buddha Nagar": {"IT": 2.0, "EV": 1.7}, "Mumbai": {"HC": 1.5, "LG": 1.6, "IT": 1.4},
    "Thane": {"LG": 1.8}, "Nagpur": {"LG": 1.7}, "Khordha": {"IT": 1.5, "RE": 1.3},
    "Angul": {"RE": 1.6}, "Jharsuguda": {"RE": 1.4}, "Sundargarh": {"RE": 1.3}, "Chitradurga": {"RE": 1.8},
    "Tumakuru": {"RE": 1.6, "LG": 1.2}, "Ballari": {"RE": 1.5}, "Aurangabad": {"EV": 1.6}, "Nashik": {"EV": 1.3},
    "Lucknow": {"HC": 1.6, "IT": 1.2}, "Kanpur Nagar": {"LG": 1.3}, "Mysuru": {"EV": 1.2, "IT": 1.1},
    "Dharwad": {"EV": 1.3}, "Prayagraj": {"HC": 1.2}, "Jhansi": {"RE": 1.7}, "Mirzapur": {"RE": 1.4},
}

# Each trade: NCO-2015 code (illustrative), title, sector, NSQF QP, level, hours, cost/seat (INR),
# women share, base demand per pop unit, annual growth, supply ratio (certified supply / demand),
# entry wage (INR/month), urban affinity, seasonality profile, emerging flag.
TRADES = [
    # code, title, sector, qp, nsqf, hours, cost, women, base, growth, supply, wage, urban, season, emerging
    ("7411.0101", "Solar PV Installer (Suryamitra)", "RE", "SGJ/Q0101", 4, 400, 18000, 0.08, 9, 0.24, 0.7, 15500, 0.2, "re", 1),
    ("7412.0301", "Wind Turbine Technician", "RE", "SGJ/Q0301", 4, 480, 24000, 0.05, 3, 0.15, 0.6, 18000, 0.1, "re", 1),
    ("3113.0102", "Rooftop Solar Grid Engineer", "RE", "SGJ/Q0102", 5, 520, 26000, 0.12, 4, 0.30, 0.65, 21000, 0.6, "re", 1),
    ("3133.0400", "Green Hydrogen Plant Operator", "RE", "SGJ/Q1001", 5, 560, 32000, 0.10, 1.2, 0.55, 0.38, 24000, 0.3, "flat", 1),
    ("7231.0501", "EV Battery Technician", "EV", "ASC/Q1405", 4, 450, 28000, 0.10, 5, 0.38, 0.5, 19000, 0.7, "flat", 1),
    ("7231.0100", "Automotive Service Technician", "EV", "ASC/Q1411", 4, 420, 22000, 0.06, 11, 0.04, 1.05, 15000, 0.5, "flat", 0),
    ("7231.0400", "Two-Wheeler Service Technician", "EV", "ASC/Q1416", 3, 360, 16000, 0.05, 13, 0.01, 1.35, 12500, 0.3, "flat", 0),
    ("7421.0700", "Drone Service Technician", "EV", "ELE/Q7902", 4, 400, 30000, 0.14, 1.6, 0.42, 0.55, 20000, 0.6, "flat", 1),
    ("5321.0100", "General Duty Assistant", "HC", "HSS/Q5101", 4, 420, 20000, 0.62, 14, 0.07, 1.1, 13500, 0.6, "flat", 0),
    ("5322.0100", "Home Health Aide", "HC", "HSS/Q5102", 4, 360, 17000, 0.78, 8, 0.12, 0.9, 13000, 0.7, "flat", 0),
    ("3212.0100", "Medical Lab Technician", "HC", "HSS/Q0301", 5, 600, 30000, 0.48, 5, 0.09, 0.8, 16500, 0.7, "flat", 0),
    ("3258.0100", "Emergency Medical Technician", "HC", "HSS/Q2301", 4, 700, 34000, 0.30, 3, 0.11, 0.75, 17000, 0.5, "flat", 0),
    ("4132.0100", "Data Entry Operator", "IT", "SSC/Q2212", 3, 300, 12000, 0.55, 10, -0.09, 2.4, 10500, 0.7, "flat", 0),
    ("4222.0100", "Domestic BPO - CRM Voice", "IT", "SSC/Q2210", 4, 330, 14000, 0.50, 12, -0.04, 1.9, 12000, 0.9, "flat", 0),
    ("2512.0100", "Junior Software Developer", "IT", "SSC/Q0508", 5, 600, 35000, 0.38, 6, 0.10, 0.85, 22000, 1.0, "flat", 0),
    ("4132.0301", "AI Data Annotation Analyst", "IT", "SSC/Q8113", 4, 300, 15000, 0.52, 4, 0.48, 0.55, 14500, 0.8, "flat", 1),
    ("9321.0100", "Warehouse Packer", "LG", "LSC/Q2305", 3, 240, 10000, 0.30, 16, 0.08, 1.0, 11500, 0.6, "lg", 0),
    ("8321.0100", "Last-Mile Delivery Associate", "LG", "LSC/Q2304", 3, 200, 9000, 0.08, 20, 0.13, 0.75, 14000, 0.8, "lg", 0),
    ("8344.0100", "Forklift Operator", "LG", "LSC/Q1104", 4, 300, 16000, 0.04, 6, 0.10, 0.8, 15500, 0.5, "lg", 0),
    ("7127.0201", "Cold Chain Technician", "LG", "LSC/Q2601", 4, 380, 22000, 0.06, 2.5, 0.28, 0.6, 17000, 0.5, "flat", 1),
    ("7112.0100", "Mason General", "CN", "CON/Q0102", 3, 300, 11000, 0.06, 18, 0.05, 0.9, 13000, 0.3, "cn", 0),
    ("7411.0200", "Assistant Electrician", "CN", "CON/Q0602", 3, 360, 13000, 0.04, 12, 0.07, 1.2, 13500, 0.4, "cn", 0),
    ("7114.0300", "Bar Bender & Steel Fixer", "CN", "CON/Q0204", 3, 280, 11000, 0.03, 9, 0.06, 0.7, 13000, 0.4, "cn", 0),
    ("7126.0100", "Plumber General", "CN", "PSC/Q0104", 3, 300, 12000, 0.04, 8, 0.06, 0.9, 13500, 0.5, "cn", 0),
]
TRADE_FIELDS = ["code", "title", "sector", "qp_code", "nsqf_level", "hours", "cost_per_seat", "women_share", "base", "growth", "supply_ratio", "entry_wage", "urban_affinity", "season", "emerging"]

SEASONS = {
    # Multiplicative month-of-year factors, Jan..Dec
    "flat": [1.0, 1.0, 1.03, 0.98, 0.97, 0.98, 1.0, 1.0, 1.01, 1.02, 1.0, 1.01],
    "re": [1.12, 1.1, 1.08, 0.98, 0.92, 0.85, 0.82, 0.85, 0.95, 1.08, 1.12, 1.13],
    "lg": [0.92, 0.9, 0.95, 0.95, 0.96, 0.97, 1.0, 1.05, 1.14, 1.2, 1.12, 0.98],
    "cn": [1.1, 1.12, 1.1, 1.05, 1.0, 0.82, 0.74, 0.78, 0.9, 1.07, 1.13, 1.12],
}

# Skills listed in the current NSQF QP (curriculum) and skills employers ask for (market).
SKILLS = {
    "7411.0101": (["solar panel installation", "dc wiring", "multimeter usage", "earthing", "electrical safety", "site survey", "inverter installation"],
                  ["solar panel installation", "dc wiring", "inverter installation", "electrical safety", "net metering", "drone-based panel inspection", "string monitoring scada", "earthing"]),
    "7412.0301": (["mechanical maintenance", "electrical safety", "working at height", "hydraulics", "multimeter usage"],
                  ["working at height", "mechanical maintenance", "hydraulics", "condition monitoring", "scada operation", "electrical safety"]),
    "3113.0102": (["solar panel installation", "load calculation", "autocad drafting", "net metering", "electrical safety", "inverter installation"],
                  ["load calculation", "pvsyst design", "net metering", "inverter installation", "battery storage sizing", "autocad drafting", "customer handling"]),
    "3133.0400": (["process safety", "gas handling", "plc basics", "electrical safety"],
                  ["electrolyser operation", "process safety", "gas handling", "plc basics", "hazop awareness", "scada operation"]),
    "7231.0501": (["battery safety", "cell testing", "multimeter usage", "wiring harness", "bms basics", "electrical safety"],
                  ["battery safety", "cell testing", "bms diagnostics", "can bus diagnostics", "high-voltage safety", "thermal management", "wiring harness", "obd scanning"]),
    "7231.0100": (["engine overhaul", "brake service", "obd scanning", "wiring harness", "customer handling"],
                  ["engine overhaul", "obd scanning", "brake service", "ev basics", "adas calibration", "customer handling", "wiring harness"]),
    "7231.0400": (["engine overhaul", "brake service", "carburettor tuning", "customer handling", "wiring harness"],
                  ["engine overhaul", "brake service", "fuel injection service", "customer handling", "ev basics", "wiring harness"]),
    "7421.0700": (["drone assembly", "soldering", "battery safety", "flight controller setup"],
                  ["drone assembly", "flight controller setup", "soldering", "dgca rules", "payload integration", "battery safety", "gis mapping"]),
    "5321.0100": (["patient care", "vital signs", "infection control", "bed making", "first aid", "communication skills"],
                  ["patient care", "vital signs", "infection control", "first aid", "ehr data entry", "geriatric care", "communication skills"]),
    "5322.0100": (["patient care", "vital signs", "first aid", "geriatric care", "communication skills", "nutrition basics"],
                  ["geriatric care", "patient care", "vital signs", "first aid", "dementia care", "telehealth devices", "communication skills"]),
    "3212.0100": (["sample collection", "microscopy", "infection control", "lab safety", "lis software"],
                  ["sample collection", "lab safety", "lis software", "automated analyser operation", "quality control", "microscopy"]),
    "3258.0100": (["first aid", "cpr", "patient transport", "vital signs", "communication skills"],
                  ["cpr", "first aid", "trauma care", "patient transport", "ambulance gps systems", "vital signs"]),
    "4132.0100": (["typing", "ms excel", "data validation", "communication skills"],
                  ["typing", "ms excel", "data validation", "google sheets", "communication skills"]),
    "4222.0100": (["communication skills", "crm software", "customer handling", "typing", "hindi english fluency"],
                  ["communication skills", "crm software", "customer handling", "hindi english fluency", "chat support", "typing"]),
    "2512.0100": (["python", "sql", "html css", "git", "javascript"],
                  ["python", "javascript", "sql", "git", "react", "cloud basics", "api integration", "genai tools"]),
    "4132.0301": (["data labelling", "typing", "ms excel", "quality control"],
                  ["data labelling", "image annotation", "llm output evaluation", "quality control", "python", "typing", "ms excel"]),
    "9321.0100": (["packing", "inventory handling", "warehouse safety", "barcode scanning"],
                  ["packing", "barcode scanning", "inventory handling", "warehouse safety", "wms software"]),
    "8321.0100": (["two-wheeler driving", "customer handling", "route planning", "cash handling"],
                  ["two-wheeler driving", "route planning", "customer handling", "delivery app usage", "upi payments", "ev two-wheeler riding"]),
    "8344.0100": (["forklift operation", "warehouse safety", "load handling", "inventory handling"],
                  ["forklift operation", "load handling", "warehouse safety", "reach truck operation", "wms software", "inventory handling"]),
    "7127.0201": (["refrigeration basics", "electrical safety", "multimeter usage", "temperature logging"],
                  ["refrigeration basics", "temperature logging", "iot sensor monitoring", "electrical safety", "reefer container service"]),
    "7112.0100": (["brick laying", "plastering", "reading drawings", "site safety"],
                  ["brick laying", "plastering", "site safety", "aac block laying", "reading drawings"]),
    "7411.0200": (["electrical wiring", "earthing", "multimeter usage", "electrical safety", "conduit installation"],
                  ["electrical wiring", "earthing", "electrical safety", "multimeter usage", "smart home wiring", "solar panel installation", "conduit installation"]),
    "7114.0300": (["rebar cutting", "rebar tying", "reading drawings", "site safety"],
                  ["rebar tying", "rebar cutting", "reading drawings", "site safety", "bbs calculation"]),
    "7126.0100": (["pipe fitting", "leak testing", "site safety", "reading drawings"],
                  ["pipe fitting", "leak testing", "site safety", "cpvc jointing", "rainwater harvesting systems"]),
}

# Synonyms / raw job titles used to synthesise postings and to train the NCO auto-coder.
TITLE_VARIANTS = {
    "7411.0101": ["Solar PV Installer", "Solar Technician", "Solar Panel Fitter", "Suryamitra Technician", "Solar mistri", "Solar Installation Helper", "PV Module Installer"],
    "7412.0301": ["Wind Turbine Technician", "WTG Technician", "Wind Farm Maintenance Tech", "Windmill Technician"],
    "3113.0102": ["Rooftop Solar Engineer", "Solar Design Engineer", "Rooftop PV Site Engineer", "Solar Grid Engineer"],
    "3133.0400": ["Green Hydrogen Operator", "Electrolyser Plant Operator", "Hydrogen Plant Technician"],
    "7231.0501": ["EV Battery Technician", "Battery Pack Technician", "EV Technician Battery", "Lithium Battery Assembler", "BMS Technician"],
    "7231.0100": ["Automobile Mechanic", "Car Service Technician", "Four Wheeler Mechanic", "Auto Technician", "Workshop Technician"],
    "7231.0400": ["Two Wheeler Mechanic", "Bike Mechanic", "Scooter Service Technician", "2W Technician"],
    "7421.0700": ["Drone Technician", "UAV Technician", "Drone Service Engineer", "Drone Assembly Tech"],
    "5321.0100": ["General Duty Assistant", "Ward Boy", "GDA Hospital", "Patient Care Assistant", "Nursing Assistant"],
    "5322.0100": ["Home Health Aide", "Elderly Caregiver", "Home Nursing Attendant", "Patient Caretaker Home"],
    "3212.0100": ["Lab Technician", "Medical Lab Technician", "Phlebotomist", "Pathology Lab Assistant"],
    "3258.0100": ["Emergency Medical Technician", "EMT Ambulance", "Ambulance Paramedic", "108 Ambulance EMT"],
    "4132.0100": ["Data Entry Operator", "Computer Operator", "DEO", "Back Office Data Entry", "Typist Data Entry"],
    "4222.0100": ["Customer Care Executive", "Telecaller", "BPO Voice Process", "Call Centre Executive", "CRM Executive"],
    "2512.0100": ["Junior Software Developer", "Trainee Software Engineer", "Python Developer Fresher", "Web Developer Junior"],
    "4132.0301": ["Data Annotation Analyst", "AI Data Labeller", "Image Annotator", "AI Training Data Associate"],
    "9321.0100": ["Warehouse Packer", "Packing Helper", "Warehouse Associate", "Picker Packer"],
    "8321.0100": ["Delivery Executive", "Delivery Boy", "Last Mile Delivery Partner", "Courier Delivery Associate", "Food Delivery Rider"],
    "8344.0100": ["Forklift Operator", "Forklift Driver", "Reach Truck Operator", "Material Handling Operator"],
    "7127.0201": ["Cold Chain Technician", "Refrigeration Technician", "Reefer Technician", "Cold Storage Technician"],
    "7112.0100": ["Mason", "Raj Mistri", "Construction Mason", "Brick Mason"],
    "7411.0200": ["Electrician", "Assistant Electrician", "Building Electrician", "Wireman", "Electrical Helper"],
    "7114.0300": ["Bar Bender", "Steel Fixer", "Rebar Fitter", "Sariya Mistri"],
    "7126.0100": ["Plumber", "Plumbing Technician", "Pipe Fitter Plumber", "Sanitary Plumber"],
}

# Share of a sector's project jobs that land in each trade (operations phase).
def staffing_shares(sector: str) -> dict[str, float]:
    codes = [t[0] for t in TRADES if t[2] == sector]
    weights = {"RE": [0.45, 0.15, 0.25, 0.15], "EV": [0.5, 0.2, 0.1, 0.2], "HC": [0.45, 0.2, 0.2, 0.15],
               "IT": [0.2, 0.3, 0.3, 0.2], "LG": [0.4, 0.3, 0.2, 0.1], "CN": [0.35, 0.3, 0.2, 0.15]}[sector]
    return dict(zip(codes, weights))

# Construction-phase demand for any project (masons, electricians, ...).
CONSTRUCTION_SHARES = {"7112.0100": 0.35, "7411.0200": 0.3, "7114.0300": 0.2, "7126.0100": 0.15}

# Investment pipeline (announced projects). jobs_ops = permanent skilled roles; jobs_build = construction phase.
INVESTMENTS = [
    # name, district, sector, capex (crore), jobs_ops, jobs_build, announced, build_start, ops_start, ramp months
    ("EV cell & pack gigafactory, Chakan", "Pune", "EV", 4200, 5200, 2600, "2024-03", "2024-06", "2025-04", 12),
    ("Integrated solar module plant, Khurda", "Khordha", "RE", 2600, 2400, 2200, "2025-02", "2025-06", "2026-03", 9),
    ("2 GW solar park, Chitradurga", "Chitradurga", "RE", 9000, 1800, 5200, "2025-08", "2026-01", "2026-12", 12),
    ("Green hydrogen hub, Angul", "Angul", "RE", 12000, 1500, 6000, "2025-11", "2026-04", "2027-03", 12),
    ("Semiconductor ATMP & drone cluster, Jewar", "Gautam Buddha Nagar", "EV", 6800, 3600, 3000, "2025-05", "2025-10", "2026-10", 12),
    ("Multi-modal logistics park, Nagpur", "Nagpur", "LG", 1500, 4200, 2800, "2024-09", "2025-01", "2025-10", 9),
    ("AIIMS-style super-speciality hospital, Gorakhpur", "Gorakhpur", "HC", 900, 2100, 1400, "2025-01", "2025-05", "2026-06", 9),
    ("Global capability centre campus, Bengaluru", "Bengaluru Urban", "IT", 3100, 6500, 2400, "2025-04", "2025-07", "2026-05", 12),
    ("Two-wheeler EV plant, Hosur road", "Bengaluru Urban", "EV", 2400, 2600, 1800, "2025-07", "2025-11", "2026-11", 12),
    ("Mumbai trans-harbour logistics hub", "Raigad", "LG", 2100, 3800, 3500, "2024-11", "2025-03", "2026-02", 9),
    ("Wind-solar hybrid park, Jhansi", "Jhansi", "RE", 5200, 900, 3800, "2025-06", "2026-02", "2027-02", 9),
    ("Cold chain & food park, Nashik", "Nashik", "LG", 700, 1600, 900, "2025-09", "2026-01", "2026-11", 9),
    ("Medical college & hospital, Koraput", "Koraput", "HC", 650, 1300, 1100, "2025-10", "2026-03", "2027-06", 9),
    ("AI data centre park, Navi Mumbai", "Thane", "IT", 8000, 2800, 4200, "2025-12", "2026-05", "2027-04", 12),
]


def load_districts() -> list[dict]:
    rows = json.loads((DATA_DIR / "districts.json").read_text(encoding="utf-8"))
    for r in rows:
        urban, weight = HUBS.get(r["district"], (0.25, 1.0))
        r["urban"] = urban
        r["pop_weight"] = weight
        r["aspirational"] = int(r["district"] in ASPIRATIONAL)
    return rows


def trades() -> list[dict]:
    return [dict(zip(TRADE_FIELDS, t)) for t in TRADES]
