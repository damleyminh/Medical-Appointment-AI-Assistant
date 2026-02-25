"""
tools.py — mock appointment data layer and tool functions.

"""
from __future__ import annotations
from datetime import datetime, timedelta

# ─── Mock database 

# ─── Seed appointments — rich medical backgrounds per patient 


_APPOINTMENTS: dict[str, dict] = {

    # ── Jane Smith — ongoing cardiac & imaging follow-up 
    "APT-001": {
        "id": "APT-001", "patient_name": "Jane Smith",
        "type": "MRI Imaging", "datetime": "2026-03-07 09:00",
        "provider": "Dr. Anand Patel (Radiology)",
        "location": "QEII Halifax Infirmary — Radiology, 1799 Robie St",
        "status": "confirmed",
        "notes": "Brain MRI — follow-up for migraine investigation. Contrast required. No metal implants on file.",
    },
    "APT-002": {
        "id": "APT-002", "patient_name": "Jane Smith",
        "type": "Specialist Consultation", "datetime": "2026-03-14 14:00",
        "provider": "Dr. Sarah Chen (Neurology)",
        "location": "QEII Halifax Infirmary — Neurology Clinic, 1799 Robie St",
        "status": "confirmed",
        "notes": "Initial neurology consult. Bring MRI results from APT-001. Referral from Dr. MacLeod.",
    },
    "APT-003": {
        "id": "APT-003", "patient_name": "Jane Smith",
        "type": "Blood Work", "datetime": "2026-02-20 08:30",
        "provider": "Lab Services",
        "location": "Bayers Lake Community Outpatient Centre — 420 Susie Lake Cres",
        "status": "completed",
        "notes": "CBC, thyroid panel, lipid panel. Results available in patient portal within 72 hrs.",
    },

    # ── John Doe — diabetes management & cardiac monitoring 
    "APT-004": {
        "id": "APT-004", "patient_name": "John Doe",
        "type": "Annual Physical", "datetime": "2026-03-10 14:30",
        "provider": "Dr. Linda Chen (Family Medicine)",
        "location": "Bayers Lake Community Outpatient Centre — 420 Susie Lake Cres",
        "status": "confirmed",
        "notes": "Annual checkup. Review diabetes management — HbA1c trends. Fasting blood work ordered.",
    },
    "APT-005": {
        "id": "APT-005", "patient_name": "John Doe",
        "type": "Blood Work", "datetime": "2026-03-10 07:45",
        "provider": "Lab Services",
        "location": "Bayers Lake Community Outpatient Centre — 420 Susie Lake Cres",
        "status": "confirmed",
        "notes": "Fasting labs before annual physical. HbA1c, glucose, kidney function, cholesterol panel.",
    },
    "APT-006": {
        "id": "APT-006", "patient_name": "John Doe",
        "type": "Ultrasound", "datetime": "2026-02-15 11:00",
        "provider": "Dr. Kevin Nguyen (Radiology)",
        "location": "Dartmouth General Hospital — 325 Pleasant St, Dartmouth",
        "status": "completed",
        "notes": "Abdominal ultrasound — liver and kidney screening for diabetic complications.",
    },
    "APT-007": {
        "id": "APT-007", "patient_name": "John Doe",
        "type": "Follow-up Visit", "datetime": "2026-03-28 10:00",
        "provider": "Dr. Linda Chen (Family Medicine)",
        "location": "Bayers Lake Community Outpatient Centre — 420 Susie Lake Cres",
        "status": "pending",
        "notes": "Review annual physical results and adjust diabetes medication if needed.",
    },

    # ── Maria Garcia — post-surgery orthopedic recovery 
    "APT-008": {
        "id": "APT-008", "patient_name": "Maria Garcia",
        "type": "Orthopedic Assessment", "datetime": "2026-03-05 09:30",
        "provider": "Dr. James Williams (Orthopedics)",
        "location": "Bayers Lake Community Outpatient Centre — 420 Susie Lake Cres",
        "status": "confirmed",
        "notes": "6-week post-op follow-up after right knee ACL reconstruction. Bring physio progress notes.",
    },
    "APT-009": {
        "id": "APT-009", "patient_name": "Maria Garcia",
        "type": "X-Ray", "datetime": "2026-03-05 08:45",
        "provider": "Dr. Kevin Nguyen (Radiology)",
        "location": "QEII Halifax Infirmary — Radiology, 1799 Robie St",
        "status": "confirmed",
        "notes": "Right knee X-ray before orthopedic assessment. Wear loose shorts or bring them.",
    },
    "APT-010": {
        "id": "APT-010", "patient_name": "Maria Garcia",
        "type": "CT Scan", "datetime": "2026-02-18 10:00",
        "provider": "Dr. Anand Patel (Radiology)",
        "location": "Dartmouth General Hospital — 325 Pleasant St, Dartmouth",
        "status": "completed",
        "notes": "Pre-op CT scan of right knee. Results reviewed by surgical team.",
    },

    # ── Amir Hassan — renal monitoring & specialist care 
    "APT-011": {
        "id": "APT-011", "patient_name": "Amir Hassan",
        "type": "Ultrasound", "datetime": "2026-03-12 10:30",
        "provider": "Dr. Kevin Nguyen (Radiology)",
        "location": "QEII Victoria General (VG) Site — 1278 Tower Rd",
        "status": "confirmed",
        "notes": "Renal ultrasound — monitoring kidney stones. Drink 4 glasses of water before arrival.",
    },
    "APT-012": {
        "id": "APT-012", "patient_name": "Amir Hassan",
        "type": "Specialist Consultation", "datetime": "2026-03-19 15:00",
        "provider": "Dr. Fatima Malik (Nephrology)",
        "location": "QEII Halifax Infirmary — Nephrology Clinic, 1799 Robie St",
        "status": "confirmed",
        "notes": "Nephrology consultation — chronic kidney disease monitoring. Bring recent blood work.",
    },
    "APT-013": {
        "id": "APT-013", "patient_name": "Amir Hassan",
        "type": "Blood Work", "datetime": "2026-03-19 07:30",
        "provider": "Lab Services",
        "location": "QEII Halifax Infirmary — Lab, 1799 Robie St",
        "status": "confirmed",
        "notes": "Fasting kidney function panel (creatinine, GFR, electrolytes) before nephrology appointment.",
    },
    "APT-014": {
        "id": "APT-014", "patient_name": "Amir Hassan",
        "type": "Blood Work", "datetime": "2026-01-15 08:00",
        "provider": "Lab Services",
        "location": "Bayers Lake Community Outpatient Centre — 420 Susie Lake Cres",
        "status": "completed",
        "notes": "Quarterly kidney function monitoring. Results show eGFR stable at 62 mL/min.",
    },

    # ── Sarah Nguyen — prenatal & women's health
    "APT-015": {
        "id": "APT-015", "patient_name": "Sarah Nguyen",
        "type": "Ultrasound", "datetime": "2026-03-06 13:00",
        "provider": "Dr. Priya Singh (OB/GYN)",
        "location": "IWK Health Centre — Women's Health, 5850 University Ave",
        "status": "confirmed",
        "notes": "20-week anatomy scan. Bring partner/support person. Appointment takes approx. 45 min.",
    },
    "APT-016": {
        "id": "APT-016", "patient_name": "Sarah Nguyen",
        "type": "Specialist Consultation", "datetime": "2026-03-20 11:00",
        "provider": "Dr. Priya Singh (OB/GYN)",
        "location": "IWK Health Centre — Women's Health, 5850 University Ave",
        "status": "confirmed",
        "notes": "OB/GYN consultation — review anatomy scan results and birth plan discussion.",
    },
    "APT-017": {
        "id": "APT-017", "patient_name": "Sarah Nguyen",
        "type": "Blood Work", "datetime": "2026-02-28 09:00",
        "provider": "Lab Services",
        "location": "IWK Health Centre — Lab, 5850 University Ave",
        "status": "completed",
        "notes": "Glucose screening test (GCT) for gestational diabetes. 1-hour draw, non-fasting.",
    },

    # ── Robert MacLeod — elderly — cancer monitoring & cardiac 
    "APT-018": {
        "id": "APT-018", "patient_name": "Robert MacLeod",
        "type": "CT Scan", "datetime": "2026-03-09 08:00",
        "provider": "Dr. Anand Patel (Radiology)",
        "location": "QEII Halifax Infirmary — Radiology, 1799 Robie St",
        "status": "confirmed",
        "notes": "Chest CT with contrast — 6-month surveillance scan for lung nodule follow-up.",
    },
    "APT-019": {
        "id": "APT-019", "patient_name": "Robert MacLeod",
        "type": "Specialist Consultation", "datetime": "2026-03-16 14:00",
        "provider": "Dr. James Porter (Respirology)",
        "location": "QEII Halifax Infirmary — Respirology Clinic, 1799 Robie St",
        "status": "confirmed",
        "notes": "Review CT results with respirologist. Bring previous imaging reports.",
    },
    "APT-020": {
        "id": "APT-020", "patient_name": "Robert MacLeod",
        "type": "Bone Density Scan", "datetime": "2026-03-23 10:00",
        "provider": "Dr. Fatima Malik (Endocrinology)",
        "location": "Bayers Lake Community Outpatient Centre — 420 Susie Lake Cres",
        "status": "confirmed",
        "notes": "DEXA scan for osteoporosis screening. No calcium supplements 24hrs before.",
    },
    "APT-021": {
        "id": "APT-021", "patient_name": "Robert MacLeod",
        "type": "Annual Physical", "datetime": "2026-02-10 09:30",
        "provider": "Dr. Linda Chen (Family Medicine)",
        "location": "Clayton Park Medical Clinic — 278 Lacewood Dr",
        "status": "completed",
        "notes": "Annual physical completed. BP elevated at 148/92 — follow-up ordered. All vaccinations current.",
    },
}

_CLINIC_INFO = {

    # ══════════════════════════════════════════════
    # MAJOR HOSPITALS
    # ══════════════════════════════════════════════

    "qeii_infirmary": {
        "name":     "QEII Health Sciences Centre — Halifax Infirmary",
        "type":     "Major Hospital & Imaging Centre",
        "address":  "1799 Robie Street (main), Halifax, NS B3H 3A7\nED entrance: 1840 Bell Road (as of Dec 2024)",
        "phone":    "(902) 473-2700",
        "hours":    "Radiology/Imaging: Mon–Fri 7:30 AM – 5:00 PM\nED: Open 24/7\nOutpatient Clinics: Mon–Fri 8:00 AM – 4:30 PM\nVirtual Urgent Care: Daily 8:00 AM – 7:00 PM",
        "services": "MRI, CT Scan, X-Ray, Ultrasound, Specialist Consultations, Surgery, Emergency",
        "parking":  "FREE with validation ticket from info desk or registration kiosk. Accessible spaces at all entrances.",
        "transit":  "Halifax Transit routes along Robie Street. Taxi: Yellow Cab (902) 420-0000.",
        "website":  "https://www.nshealth.ca/locations-and-facilities/qeii-health-sciences-centre",
    },

    "qeii_vg": {
        "name":     "QEII Health Sciences Centre — Victoria General (VG) Site",
        "type":     "Major Hospital",
        "address":  "1278 Tower Road, Halifax, NS B3H 2Y9",
        "phone":    "(902) 473-2700",
        "hours":    "Outpatient Clinics: Mon–Fri 8:00 AM – 4:30 PM\nED: 24/7 (via Halifax Infirmary site)",
        "services": "Surgery, Specialist Clinics, Cancer Care, Blood Collection, Neurosciences",
        "parking":  "FREE with validation ticket. Lot between Tower Road and South Park Street.",
        "transit":  "Halifax Transit routes along Tower Road and South Park Street.",
        "note":     "Free shuttle runs between VG and Halifax Infirmary every 20 min during the day.",
        "website":  "https://www.nshealth.ca",
    },

    "dartmouth_general": {
        "name":     "Dartmouth General Hospital",
        "type":     "Acute Care Hospital",
        "address":  "325 Pleasant Street, Dartmouth, NS B2Y 4G8",
        "phone":    "(902) 465-8300",
        "hours":    "Emergency: Open 24/7\nBlood Collection: Book online or call (902) 473-2074 or 1-833-942-2298, Mon–Fri 7AM–6PM",
        "services": "Emergency, Surgery, Diagnostic Imaging, Blood Collection, Renal Dialysis, Urology, Orthopedics",
        "parking":  "Paid parking on site.",
        "transit":  "Halifax Transit serves Pleasant Street.",
        "website":  "https://www.nshealth.ca/locations-and-facilities/dartmouth-general-hospital",
    },

    "iwk": {
        "name":     "IWK Health Centre",
        "type":     "Women's & Children's Hospital",
        "address":  "5850/5980 University Avenue, Halifax, NS B3K 6R8\nED entrance: South Street",
        "phone":    "(902) 470-8888",
        "toll_free": "1-888-470-5888",
        "hours":    "Open 24/7 (select programs)\nBlood Collection & X-Ray: Online booking available",
        "services": "Pediatric Care, Women's Health, Maternity, Diagnostic Imaging, Blood Collection, Mental Health",
        "parking":  "Paid parking on site.",
        "transit":  "Halifax Transit on University Avenue.",
        "crisis":   "Mobile Crisis Team: 1-888-429-8167 | Kids Help Phone: 1-800-668-6868",
        "website":  "https://www.iwkhealth.ca",
    },

    # ══════════════════════════════════════════════
    # COMMUNITY OUTPATIENT CENTRES
    # ══════════════════════════════════════════════

    "bayers_lake": {
        "name":     "Bayers Lake Community Outpatient Centre",
        "type":     "Community Outpatient Centre (opened Nov 2023)",
        "address":  "420 Susie Lake Crescent, Halifax, NS (near Hwys 102 & 103)",
        "phone":    "Book via Nova Scotia Health: 1-844-473-2665",
        "hours":    "Mon–Fri: Appointment-based services\nCall for specific clinic hours",
        "services": "Blood Collection, X-Ray, Ultrasound, Bone Density, Eye Care, Orthopedic Assessment, Renal Dialysis, Rehabilitation, Endocrinology, Plastic Surgery",
        "parking":  "Ample free and paid parking. EV charging stations on site. Underground patient drop-off.",
        "transit":  "Halifax Transit Route #28 stops at centre 7 days a week.",
        "note":     "Appointment-based only — no walk-ins. Reduces need to travel downtown.",
        "website":  "https://www.nshealth.ca/locations-and-facilities/bayers-lake-community-outpatient-centre",
    },

    # ══════════════════════════════════════════════
    # WALK-IN CLINICS
    # ══════════════════════════════════════════════

    "clayton_park": {
        "name":     "Clayton Park Medical Clinic",
        "type":     "Walk-In Clinic",
        "address":  "278 Lacewood Drive, Clayton Park, Halifax (next to Shoppers Drug Mart)",
        "hours":    "7 days a week (call ahead for current hours)",
        "services": "Walk-In, Blood Collection, Ear Syringing, Rapid Strep Test, Suturing, Travel Vaccines, Women's Health",
        "parking":  "Free parking available.",
        "note":     "First-come, first-served. Blood collection on-site.",
    },

    "family_focus": {
        "name":     "The Family Focus Medical Clinics",
        "type":     "Walk-In & Family Practice",
        "address":  "Multiple Halifax locations.\nLower Sackville: 207-667 Sackville Drive (above Lawtons), NS B4C 2S4",
        "phone":    "(902) 420-6060 ext 1",
        "hours":    "Walk-in: first-come, first-served\nVirtual care available",
        "services": "Walk-In, Family Practice, Virtual Care",
        "note":     "Will fax visit notes to your family doctor if requested.",
        "website":  "https://www.thefamilyfocus.ca",
    },

    "scotiamed": {
        "name":     "ScotiaMed Walk-In Clinic",
        "type":     "Walk-In Clinic",
        "address":  "955 Bedford Highway, Bedford, NS B4A 1A9",
        "hours":    "Mon–Fri: 1:00 PM – 8:00 PM (Registration opens at 12:00 noon)",
        "services": "Walk-In, Family Practice, Urgent Care",
        "parking":  "Free parking. Wheelchair accessible.",
        "website":  "https://www.scotiamed.ca",
    },

    # ══════════════════════════════════════════════
    # GENERAL INFO
    # ══════════════════════════════════════════════
    "general": {
        "wait_times":  "Check live wait times at https://www.medimap.ca",
        "health_line": "Health811: Call 8-1-1 for non-emergency health advice, 24/7",
        "crisis":      "Mental Health Crisis: (902) 429-8167 or 1-888-429-8167 (24/7)",
        "emergency":   "Life-threatening emergency: Call 9-1-1",
        "no_doctor":   "Need a family doctor? Call 811 Mon–Fri 11AM–7PM or visit https://www.nshealth.ca",
    },
}

# Convenience alias — used by existing get_clinic_info for general queries
_PRIMARY_CLINIC = _CLINIC_INFO["qeii_infirmary"]

# ─── Mock patient accounts (username → profile) ───────────────────────────────
# In production these would come from your EHR/auth system
PATIENT_ACCOUNTS: dict[str, dict] = {
    "jane.smith": {
        "name":       "Jane Smith",
        "dob":        "1985-04-12",
        "health_card":"NS-1234-5678",
        "phone":      "(902) 555-0101",
        "password":   "pass123",   # demo only — never store plaintext in production
    },
    "john.doe": {
        "name":       "John Doe",
        "dob":        "1979-08-30",
        "health_card":"NS-9876-5432",
        "phone":      "(902) 555-0202",
        "password":   "pass123",
    },
    "maria.garcia": {
        "name":       "Maria Garcia",
        "dob":        "1992-02-15",
        "health_card":"NS-5555-1111",
        "phone":      "(902) 555-0303",
        "password":   "pass123",
    },
    "amir.hassan": {
        "name":       "Amir Hassan",
        "dob":        "1988-11-22",
        "health_card":"NS-7777-2222",
        "phone":      "(902) 555-0404",
        "password":   "pass123",
    },
}

def authenticate_patient(username: str, password: str) -> dict | None:
    """Returns patient profile dict if credentials match, else None."""
    account = PATIENT_ACCOUNTS.get(username.lower().strip())
    if account and account["password"] == password:
        return {k: v for k, v in account.items() if k != "password"}
    return None

# Imaging/procedure types available at specific hospitals
_IMAGING_LOCATIONS = {
    "MRI Imaging": [
        "QEII Halifax Infirmary — 1799 Robie St, Halifax | (902) 473-2700",
        "QEII Victoria General (VG) — 1278 Tower Rd, Halifax | (902) 473-2700",
        "Dartmouth General Hospital — 325 Pleasant St, Dartmouth | (902) 465-8300",
    ],
    "CT Scan": [
        "QEII Halifax Infirmary — 1799 Robie St, Halifax | (902) 473-2700",
        "QEII Victoria General (VG) — 1278 Tower Rd, Halifax | (902) 473-2700",
        "Dartmouth General Hospital — 325 Pleasant St, Dartmouth | (902) 465-8300",
    ],
    "X-Ray": [
        "QEII Halifax Infirmary — 1799 Robie St, Halifax | (902) 473-2700",
        "Bayers Lake Community Outpatient Centre — 420 Susie Lake Cres | 1-844-473-2665",
        "Dartmouth General Hospital — 325 Pleasant St, Dartmouth | (902) 465-8300",
        "IWK Health Centre (children/women) — 5850 University Ave | (902) 470-8888",
    ],
    "Ultrasound": [
        "QEII Halifax Infirmary — 1799 Robie St, Halifax | (902) 473-2700",
        "Bayers Lake Community Outpatient Centre — 420 Susie Lake Cres | 1-844-473-2665",
        "Dartmouth General Hospital — 325 Pleasant St, Dartmouth | (902) 465-8300",
        "IWK Health Centre (children/women) — 5850 University Ave | (902) 470-8888",
    ],
    "Blood Work": [
        "QEII Halifax Infirmary — 1799 Robie St, Halifax | Book: (902) 473-2074",
        "Bayers Lake Community Outpatient Centre — 420 Susie Lake Cres | Book: 1-844-473-2665",
        "Dartmouth General Hospital — 325 Pleasant St, Dartmouth | Book: (902) 473-2074",
        "IWK Health Centre (children/women) — 5850 University Ave | Online booking available",
    ],
    "Bone Density Scan": [
        "Bayers Lake Community Outpatient Centre — 420 Susie Lake Cres | 1-844-473-2665",
        "QEII Halifax Infirmary — 1799 Robie St, Halifax | (902) 473-2700",
    ],
    "Annual Physical":          ["Bayers Lake Community Outpatient Centre", "QEII Halifax Infirmary"],
    "Specialist Consultation":  ["QEII Halifax Infirmary", "QEII Victoria General (VG)", "Dartmouth General Hospital", "Bayers Lake Community Outpatient Centre"],
    "Orthopedic Assessment":    ["Bayers Lake Community Outpatient Centre — 420 Susie Lake Cres | 1-844-473-2665"],
    "Eye Care":                 ["Bayers Lake Community Outpatient Centre — 420 Susie Lake Cres | 1-844-473-2665", "IWK Health Centre — 5850 University Ave | (902) 470-8888"],
    "Follow-up Visit":          ["QEII Halifax Infirmary", "Bayers Lake Community Outpatient Centre", "Dartmouth General Hospital"],
    "Vaccination":              ["Clayton Park Medical Clinic — 278 Lacewood Dr", "Family Focus Medical — 667 Sackville Dr, Lower Sackville"],
}

_APPOINTMENT_TYPES = list(_IMAGING_LOCATIONS.keys())

_PREP_INSTRUCTIONS: dict[str, str] = {

    "mri": (
        "MRI Preparation Instructions:\n"
        "• Remove all metal jewellery, piercings, hair clips, and body piercings before your appointment.\n"
        "• Wear comfortable, loose-fitting clothing with no metal fasteners (zippers, underwire bras, belt buckles).\n"
        "• Inform our team of any implants, pacemakers, cochlear implants, or metallic devices — some may prevent an MRI.\n"
        "• Fasting is not usually required unless contrast dye (gadolinium) is ordered; your referral letter will specify.\n"
        "• If contrast is required: fast for 4 hours beforehand. Water and essential medications are fine.\n"
        "• Arrive 15 minutes early to complete the safety screening form.\n"
        "• The scan typically takes 30–60 minutes. Earplugs are available at reception — the machine is loud.\n"
        "• You may bring a family member or support person to wait in the waiting area.\n"
        "• Claustrophobia: let us know in advance — a mild sedative may be arranged with your doctor."
    ),

    "ct": (
        "CT Scan Preparation Instructions:\n"
        "• If contrast dye is required (your referral will say): fast for 4 hours before the scan. Water is fine.\n"
        "• Wear comfortable clothing with no metal. A gown will be provided if needed.\n"
        "• Inform our team of: kidney disease, diabetes (especially if on metformin), allergies to iodine or contrast dye.\n"
        "• If you have had a contrast reaction before, tell us immediately — pre-medication may be required.\n"
        "• Bring your Nova Scotia Health Card and referral letter. Arrive 20 minutes early for registration.\n"
        "• The scan itself takes only 10–15 minutes.\n"
        "• You can drive yourself and resume normal activities right after, unless sedation was given."
    ),

    "xray": (
        "X-Ray Preparation Instructions:\n"
        "• No special preparation is usually required for most X-rays.\n"
        "• Wear clothing without metal zippers, buttons, or underwire if possible — or a gown will be provided.\n"
        "• Remove jewellery from the area being imaged.\n"
        "• Inform the technologist if you are pregnant or may be pregnant — a lead apron will be used for protection.\n"
        "• Bring your health card and requisition form from your doctor.\n"
        "• The procedure takes approximately 10–15 minutes.\n"
        "• Online booking available for X-ray at IWK and Bayers Lake Outpatient Centre."
    ),

    "ultrasound": (
        "Ultrasound Preparation Instructions:\n\n"
        "Preparation depends on the type of ultrasound ordered:\n\n"
        "Abdominal Ultrasound (liver, gallbladder, pancreas, spleen):\n"
        "• Fast for 6 hours before your appointment. Water is permitted.\n"
        "• Avoid gum, mints, and smoking during the fast.\n\n"
        "Pelvic Ultrasound (uterus, ovaries, bladder):\n"
        "• Drink 1 litre of water 1 hour before your appointment.\n"
        "• Do NOT urinate before your appointment — a full bladder is required.\n\n"
        "Renal / Kidney Ultrasound:\n"
        "• Drink 2–4 glasses of water before arriving. Do not empty your bladder.\n\n"
        "Vascular / Thyroid / Musculoskeletal Ultrasound:\n"
        "• No special preparation needed.\n\n"
        "General:\n"
        "• Wear comfortable, two-piece clothing for easy access to the area.\n"
        "• Bring your health card and referral. Arrive 10 minutes early."
    ),

    "blood work": (
        "Blood Work / Lab Collection Preparation Instructions:\n"
        "• Fasting blood work (cholesterol, glucose, triglycerides): fast for 8–12 hours beforehand.\n"
        "  Water and essential medications are permitted during the fast.\n"
        "• Non-fasting tests: no preparation required — eat and drink normally.\n"
        "• Your requisition form from your doctor will indicate if fasting is needed.\n"
        "• Drink plenty of water before your appointment — good hydration makes veins easier to find.\n"
        "• Avoid strenuous exercise 24 hours before some tests (e.g. CK, troponin).\n"
        "• Bring your Nova Scotia Health Card and requisition form.\n"
        "• Appointments required at most locations. Book online or call (902) 473-2074.\n"
        "• Results are typically sent to your referring physician within 24–72 hours."
    ),

    "bone density": (
        "Bone Density Scan (DEXA) Preparation Instructions:\n"
        "• Do NOT take calcium supplements for 24 hours before your scan.\n"
        "• Wear comfortable clothing without metal (no zippers, buttons, or underwire bras).\n"
        "• If you have had a barium study, nuclear medicine scan, or IV contrast in the past 7 days,\n"
        "  inform the clinic as this may affect results.\n"
        "• The scan is painless and takes approximately 10–20 minutes.\n"
        "• You will lie on a padded table — no injection or enclosure is required.\n"
        "• Bring your health card and referral. Available at Bayers Lake Outpatient Centre and QEII."
    ),

    "annual physical": (
        "Annual Physical Exam Preparation:\n"
        "• Fast for 8–12 hours if blood work is part of your physical (water is fine).\n"
        "• Bring a complete list of all current medications, vitamins, and supplements.\n"
        "• Bring any relevant medical records, previous test results, or specialist reports.\n"
        "• Write down any health concerns, symptoms, or questions you want to discuss.\n"
        "• Be ready to discuss your family medical history (heart disease, cancer, diabetes, etc.).\n"
        "• Wear comfortable clothing — you may need to change into a gown.\n"
        "• Bring your Nova Scotia Health Card and photo ID.\n"
        "• Arrive 10–15 minutes early to complete intake forms."
    ),

    "specialist": (
        "Specialist Consultation Preparation:\n"
        "• Bring your referral letter from your family doctor or nurse practitioner.\n"
        "• Bring a complete list of current medications, dosages, and allergies.\n"
        "• Bring any relevant test results, imaging (X-rays, MRI/CT), or previous specialist reports.\n"
        "• Write down all symptoms — when they started, how often they occur, what makes them better or worse.\n"
        "• Bring your Nova Scotia Health Card and photo ID.\n"
        "• You are welcome to bring a family member or advocate.\n"
        "• Arrive 15 minutes early for registration and paperwork.\n"
        "• If your appointment is at QEII, allow extra time for parking and wayfinding."
    ),

    "orthopedic": (
        "Orthopedic Assessment Preparation:\n"
        "• Bring any imaging related to the injury or condition (X-rays, MRI, CT scans) — on disc or printed report.\n"
        "• Bring your referral letter from your doctor.\n"
        "• Wear or bring loose, comfortable clothing that allows access to the affected joint (e.g. shorts for knee/hip).\n"
        "• Be prepared to describe your pain: location, severity (1–10), what worsens or relieves it.\n"
        "• Bring a list of medications including pain relievers and anti-inflammatories.\n"
        "• Note any previous treatments: physiotherapy, injections, or prior surgeries.\n"
        "• Available at Bayers Lake Community Outpatient Centre — appointment required."
    ),

    "eye": (
        "Eye Care Appointment Preparation:\n"
        "• If dilation drops will be used (your referral will say): arrange a driver — your vision will be blurry\n"
        "  for 4–6 hours after. Do not drive yourself home.\n"
        "• Bring your current glasses and/or contact lenses.\n"
        "• Remove contact lenses before the appointment if instructed.\n"
        "• Bring a list of any eye drops or medications you use.\n"
        "• Bring your referral letter and Nova Scotia Health Card.\n"
        "• Inform the clinic of any family history of glaucoma, macular degeneration, or diabetes.\n"
        "• Available at Bayers Lake Community Outpatient Centre and IWK Health Centre."
    ),

    "follow-up": (
        "Follow-up Visit Preparation:\n"
        "• Bring any test results, imaging reports, or specialist letters received since your last visit.\n"
        "• Bring your current medication list — note any changes since your last appointment.\n"
        "• Write down any new symptoms or concerns you want to discuss.\n"
        "• Bring your Nova Scotia Health Card and photo ID.\n"
        "• Arrive 10 minutes early.\n"
        "• If your condition has changed significantly since booking, call ahead to let the clinic know."
    ),

    "vaccination": (
        "Vaccination Appointment Preparation:\n"
        "• No fasting required — eat and drink normally before your appointment.\n"
        "• Wear a short-sleeved shirt or clothing with easy arm access.\n"
        "• Bring your Nova Scotia Health Card and your immunization record if you have one.\n"
        "• Inform the nurse of any allergies, especially to eggs, latex, or previous vaccine reactions.\n"
        "• Mention any current illness, fever, or immune-suppressing medications.\n"
        "• Plan to wait 15 minutes after the vaccine for observation (anaphylaxis precaution).\n"
        "• Available at Clayton Park Medical Clinic and Family Focus Medical Clinics.\n"
        "• Travel vaccines: book at least 6–8 weeks before your departure date."
    ),

    "general": (
        "General Appointment Preparation:\n"
        "• Bring your Nova Scotia Health Card and photo ID.\n"
        "• Bring a complete list of current medications, vitamins, and supplements.\n"
        "• Bring any relevant medical records, test results, or referral letters.\n"
        "• Write down your symptoms and questions before arriving.\n"
        "• Arrive 10–15 minutes early to check in and complete any paperwork.\n"
        "• If you need to cancel or reschedule, please call at least 24 hours in advance."
    ),
}


# ─── Tool functions
def lookup_appointment(appointment_id: str) -> dict | None:
    return _APPOINTMENTS.get(appointment_id.upper())


def get_available_slots(apt_type: str, days_ahead: int = 21, location: str = "",
                        preferred_day: str = "") -> list[str]:
    """Return available weekday slots, optionally filtered to a preferred day name."""
    base = datetime.now()
    day_map = {"monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3, "friday": 4}
    preferred_weekday = day_map.get(preferred_day.lower().strip(), None)

    offset = 0
    loc_lower = location.lower()
    if "dartmouth" in loc_lower:                              offset = 1
    elif "bayers" in loc_lower:                               offset = 2
    elif "vg" in loc_lower or "victoria" in loc_lower:        offset = 1

    all_slots = []
    for i in range(1 + offset, days_ahead + offset):
        dt = base + timedelta(days=i)
        if dt.weekday() < 5:          # Mon-Fri only
            all_slots.append(dt.strftime("%Y-%m-%d 09:00"))
            all_slots.append(dt.strftime("%Y-%m-%d 11:00"))
            all_slots.append(dt.strftime("%Y-%m-%d 14:00"))

    if preferred_weekday is not None:
        filtered = [s for s in all_slots
                    if datetime.strptime(s, "%Y-%m-%d %H:%M").weekday() == preferred_weekday]
        return filtered[:6] if filtered else all_slots[:6]

    return all_slots[:6]


def get_locations_for_type(apt_type: str) -> str:
    """Return hospitals/clinics that offer a given appointment type."""
    key = apt_type.strip()
    # fuzzy match
    for k, locs in _IMAGING_LOCATIONS.items():
        if k.lower() in key.lower() or key.lower() in k.lower():
            lines = [f"  {i+1}. {loc}" for i, loc in enumerate(locs)]
            return f"Locations offering {k}:\n" + "\n".join(lines)
    # fallback
    return f"Please call (902) 473-2700 or visit nshealth.ca to find locations for {apt_type}."


def reschedule_appointment(appointment_id: str, new_slot: str) -> dict:
    apt = _APPOINTMENTS.get(appointment_id.upper())
    if not apt:
        return {"success": False, "error": f"Appointment {appointment_id} not found."}
    apt["datetime"] = new_slot
    apt["status"] = "rescheduled"
    return {"success": True, "appointment": apt}


def cancel_appointment(appointment_id: str, reason: str = "") -> dict:
    apt = _APPOINTMENTS.get(appointment_id.upper())
    if not apt:
        return {"success": False, "error": f"Appointment {appointment_id} not found."}
    apt["status"] = "cancelled"
    return {"success": True, "appointment": apt, "reason": reason}


def get_prep_instructions(exam_type: str) -> str:
    key = exam_type.lower().strip()
    # Direct and partial key matching
    for k in _PREP_INSTRUCTIONS:
        if k in key or key in k:
            return _PREP_INSTRUCTIONS[k]
    # Alias matching
    aliases = {
        "x ray": "xray", "x-ray": "xray",
        "blood": "blood work", "lab": "blood work", "bloodwork": "blood work",
        "bone": "bone density", "dexa": "bone density",
        "physical": "annual physical", "checkup": "annual physical", "check-up": "annual physical",
        "specialist": "specialist", "consult": "specialist", "consultation": "specialist",
        "ortho": "orthopedic", "joint": "orthopedic",
        "eye": "eye", "vision": "eye", "ophthalmology": "eye", "optometry": "eye",
        "follow": "follow-up", "followup": "follow-up",
        "vaccine": "vaccination", "shot": "vaccination", "flu": "vaccination", "immuniz": "vaccination",
    }
    for alias, mapped in aliases.items():
        if alias in key:
            return _PREP_INSTRUCTIONS.get(mapped, _PREP_INSTRUCTIONS["general"])
    return _PREP_INSTRUCTIONS["general"]


def list_appointments() -> list[dict]:
    return list(_APPOINTMENTS.values())


def get_appointments_summary(patient_name: str = "") -> str:
    """Formatted summary of appointments, filtered by patient name if provided."""
    all_apts = list(_APPOINTMENTS.values())
    if patient_name:
        # Exact full-name match only (case-insensitive) — prevents "Jane" matching "Jane Smith"
        name_lower = patient_name.strip().lower()
        apts = [a for a in all_apts if a.get("patient_name", "").strip().lower() == name_lower]
        if not apts:
            return f"No appointments found for '{patient_name}'."
    else:
        apts = all_apts

    if not apts:
        return "No appointments currently on file."

    # Sort: upcoming confirmed first, then pending, then completed
    from datetime import datetime as _dt
    def sort_key(a):
        status_order = {"confirmed": 0, "pending": 1, "completed": 2, "cancelled": 3}
        try:   dt = _dt.strptime(a["datetime"], "%Y-%m-%d %H:%M")
        except: dt = _dt(2099, 1, 1)
        return (status_order.get(a.get("status",""), 9), dt)
    apts = sorted(apts, key=sort_key)

    lines = []
    for a in apts:
        notes_line = f"\n  Notes: {a['notes']}" if a.get("notes") else ""
        lines.append(
            f"• {a['id']} — {a['type']}\n"
            f"  Provider: {a['provider']}\n"
            f"  Date/Time: {a['datetime']} | Status: {a['status'].upper()}\n"
            f"  Location: {a['location']}"
            f"{notes_line}"
        )
    return "\n\n".join(lines)


def book_appointment(patient_name: str, apt_type: str, slot: str,
                     provider: str = "TBD", location: str = "QEII Halifax Infirmary") -> dict:
    """Book a new appointment and save to the in-memory database."""
    # Duplicate guard: if same patient already has this type+slot, return existing record
    name_lower = patient_name.strip().lower()
    for existing in _APPOINTMENTS.values():
        if (existing.get("patient_name","").strip().lower() == name_lower
                and existing.get("type","").lower() == apt_type.lower()
                and existing.get("datetime","") == slot):
            return {"appointment": existing, "duplicate": True}

    new_id = f"APT-{str(len(_APPOINTMENTS) + 1).zfill(3)}"
    new_apt = {
        "id":           new_id,
        "patient_name": patient_name,
        "type":         apt_type,
        "datetime":     slot,
        "provider":     provider,
        "location":     location,
        "status":       "confirmed",
    }
    _APPOINTMENTS[new_id] = new_apt
    return {"success": True, "appointment": new_apt}


def _fmt_clinic(c: dict) -> str:
    """Format a single clinic dict into a readable string."""
    lines = [f"🏥 {c['name']} ({c.get('type','')})"]
    if c.get('address'):  lines.append(f"📍 {c['address']}")
    if c.get('phone'):    lines.append(f"📞 {c['phone']}")
    if c.get('toll_free'):lines.append(f"   Toll-free: {c['toll_free']}")
    if c.get('hours'):    lines.append(f"🕐 {c['hours']}")
    if c.get('services'): lines.append(f"🩺 Services: {c['services']}")
    if c.get('parking'):  lines.append(f"🅿️  Parking: {c['parking']}")
    if c.get('transit'):  lines.append(f"🚌 Transit: {c['transit']}")
    if c.get('note'):     lines.append(f"ℹ️  Note: {c['note']}")
    if c.get('website'):  lines.append(f"🌐 {c['website']}")
    return "\n".join(lines)


def get_clinic_info(topic: str = "general") -> str:
    """Return real Halifax clinic info for a given topic."""
    t = topic.lower()

    # Walk-in specific
    if any(w in t for w in ["walk", "walk-in", "walkin", "no appointment", "without appointment"]):
        clinics = [_CLINIC_INFO["clayton_park"], _CLINIC_INFO["family_focus"], _CLINIC_INFO["scotiamed"]]
        result = "Walk-In Clinics in Halifax / HRM:\n\n"
        result += "\n\n".join(_fmt_clinic(c) for c in clinics)
        result += f"\n\n{_CLINIC_INFO['general']['wait_times']}"
        return result

    # Bayers Lake specific
    if any(w in t for w in ["bayers", "outpatient", "lake"]):
        return _fmt_clinic(_CLINIC_INFO["bayers_lake"])

    # IWK / children / women
    if any(w in t for w in ["iwk", "child", "pediatric", "women", "maternity", "kids"]):
        return _fmt_clinic(_CLINIC_INFO["iwk"])

    # Dartmouth
    if "dartmouth" in t:
        return _fmt_clinic(_CLINIC_INFO["dartmouth_general"])

    # All clinics
    if any(w in t for w in ["all clinic", "all hospital", "list", "options", "locations"]):
        hospitals = ["qeii_infirmary", "qeii_vg", "dartmouth_general", "iwk", "bayers_lake"]
        walkins   = ["clayton_park", "family_focus", "scotiamed"]
        result = "=== HOSPITALS & OUTPATIENT CENTRES ===\n\n"
        result += "\n\n".join(_fmt_clinic(_CLINIC_INFO[k]) for k in hospitals)
        result += "\n\n=== WALK-IN CLINICS ===\n\n"
        result += "\n\n".join(_fmt_clinic(_CLINIC_INFO[k]) for k in walkins)
        result += f"\n\n{_CLINIC_INFO['general']['wait_times']}"
        return result

    # Hours
    if any(w in t for w in ["hour", "open", "close", "time", "schedule"]):
        return f"Hours — {_PRIMARY_CLINIC['name']}:\n{_PRIMARY_CLINIC['hours']}"

    # Parking
    if "park" in t:
        return f"Parking:\n{_PRIMARY_CLINIC['parking']}\n\nDartmouth General: {_CLINIC_INFO['dartmouth_general']['parking']}\nBayers Lake: {_CLINIC_INFO['bayers_lake']['parking']}"

    # Transit
    if any(w in t for w in ["transit", "bus", "transport", "taxi", "get there"]):
        return f"Getting Here:\n{_PRIMARY_CLINIC['transit']}\n\nBayers Lake: {_CLINIC_INFO['bayers_lake']['transit']}"

    # Location / address
    if any(w in t for w in ["location", "address", "where", "direction"]):
        return _fmt_clinic(_PRIMARY_CLINIC)

    # Contact / phone
    if any(w in t for w in ["contact", "phone", "call", "number"]):
        return f"Contact Information:\n{_PRIMARY_CLINIC['name']}: {_PRIMARY_CLINIC['phone']}\nDartmouth General: {_CLINIC_INFO['dartmouth_general']['phone']}\nIWK: {_CLINIC_INFO['iwk']['phone']} / {_CLINIC_INFO['iwk']['toll_free']}\nHealth811 (24/7 health advice): 8-1-1"

    # Default: full overview
    gen = _CLINIC_INFO["general"]
    return (
        _fmt_clinic(_PRIMARY_CLINIC) +
        "\n\n" + _fmt_clinic(_CLINIC_INFO["bayers_lake"]) +
        "\n\n" + _fmt_clinic(_CLINIC_INFO["dartmouth_general"]) +
        "\n\n" + _fmt_clinic(_CLINIC_INFO["iwk"]) +
        "\n\nWalk-In Clinics:\n• Clayton Park Medical: 278 Lacewood Dr — 7 days/week\n• Family Focus Medical: 667 Sackville Dr, Lower Sackville — (902) 420-6060\n• ScotiaMed Bedford: 955 Bedford Hwy — Mon–Fri 1–8PM" +
        f"\n\n{gen['wait_times']}\n{gen['health_line']}"
    )


def get_appointment_types_list() -> str:
    return "Available appointment types:\n" + "\n".join(f"• {t}" for t in _APPOINTMENT_TYPES)