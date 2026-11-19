"""Generate a fictional broker document set: Word guide, PDF policy wordings, an Excel rate sheet, saved emails.

Every firm, insurer, client and figure here is invented for the demo.

    uv run scripts/make_demo_docs.py [out_dir]     (default: data/demo)
"""
import pathlib
import sys
from email.message import EmailMessage

import docx
from fpdf import FPDF
from openpyxl import Workbook

OUT = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else "data/demo")

# --------------------------------------------------------------- Word: placement guide

GUIDE = [
    ("Wensum Risk Partners: Placement and Underwriting Guide", None),
    ("Purpose", "This guide sets out how account handlers at Wensum Risk Partners place commercial risks. "
                "It applies to all new business and renewals from 1 September 2026. Where this guide and an insurer's "
                "wording disagree, the insurer's wording governs the cover; this guide governs what we are willing to place."),
    ("Authority levels", "Account handlers may bind renewals with a premium change of up to 15% without approval. "
                         "Renewals with a premium increase above 15%, and all new business with a premium above £25,000, "
                         "must be approved by an account director before binding. "
                         "Any risk that needs an insurer referral must be referred before quotation, never after."),
    ("Trades we place", "We actively place: logistics and haulage, light manufacturing, professional offices, "
                        "retail shops, property owners (commercial lets), and hospitality without deep-fat frying. "
                        "Restaurants and takeaways with deep-fat frying are placed only with Harbourline Insurance, and only where "
                        "the fryers have an automatic fire suppression system serviced every six months. "
                        "Without suppression, deep-fat frying risks must be declined."),
    ("Trades we decline", "We do not place: waste and recycling, scrap metal, fireworks, nightclubs, "
                          "demolition, or any business with a prior arson claim in the last five years."),
    ("Property risk requirements", "For buildings with a sum insured above £2,000,000 we require a risk survey before inception. "
                                   "Unoccupied buildings must be inspected weekly and the insurer told within 7 days of the building "
                                   "becoming unoccupied. Thatched roofs, timber-frame construction and EPS panels must be referred "
                                   "to the insurer before quotation."),
    ("Fleet and motor", "Fleet policies are placed with Ashby & Vale Underwriting. Drivers under 25 are a referral: "
                        "the handler sends the driver's licence check and claims history to Ashby & Vale and waits for written approval. "
                        "Telematics is required for any fleet of more than 10 HGVs."),
    ("Claims notification", "Clients must report any incident to us within 48 hours. We then notify the insurer the same working day. "
                            "Handlers must check the policy's claims condition, because some insurers make prompt notice a "
                            "condition precedent to liability: late notice can mean the claim is declined."),
    ("Renewals", "Start the renewal process 60 days before expiry. Send the client a renewal summary at least 21 days before expiry. "
                 "If an insurer proposes a rate increase above 10%, obtain at least one alternative quotation."),
    ("Complaints", "Any expression of dissatisfaction is a complaint. Log it in the complaints register the same day and "
                   "acknowledge it to the client within 5 working days. Final responses are due within 8 weeks."),
]


def make_guide(path):
    d = docx.Document()
    d.add_heading(GUIDE[0][0], level=0)
    for heading, body in GUIDE[1:]:
        d.add_heading(heading, level=1)
        d.add_paragraph(body)
    d.add_heading("Commission targets", level=1)
    t = d.add_table(rows=1, cols=3)
    t.rows[0].cells[0].text, t.rows[0].cells[1].text, t.rows[0].cells[2].text = "Product", "Target commission", "Minimum"
    for row in [("Commercial property", "20%", "15%"), ("Employers' and public liability", "17.5%", "12.5%"), ("Fleet motor", "12.5%", "10%")]:
        cells = t.add_row().cells
        for c, v in zip(cells, row):
            c.text = v
    d.save(path)


# --------------------------------------------------------------- PDF: policy wordings

WORDINGS = {
    "Harbourline Commercial Property Policy Wording.pdf": ("Harbourline Insurance plc", "Commercial Property Policy Wording (HL-CP 2026)", [
        ("Section 1: Definitions", [
            "Buildings: the structure at the premises, including landlord's fixtures and fittings, walls, gates and fences.",
            "Unoccupied: not used by you for your business for more than 30 consecutive days.",
            "Excess: the amount you must pay towards each claim, as shown in the schedule or this wording.",
        ]),
        ("Section 2: What is covered", [
            "We cover physical loss of or damage to the buildings and contents at the premises caused by fire, lightning, explosion, "
            "storm, flood, escape of water, theft involving forcible entry, impact and malicious damage.",
            "Business interruption is covered only if shown in the schedule, for an indemnity period of up to 24 months.",
        ]),
        ("Section 3: Excesses", [
            "Standard excess: £500 for each and every claim.",
            "Escape of water: £1,000 for each and every claim.",
            "Subsidence, heave and landslip: £2,500 for each and every claim.",
            "Unoccupied buildings: the excess for any claim is doubled while the building is unoccupied.",
        ]),
        ("Section 4: Exclusions", [
            "We do not cover damage caused by wear and tear, gradual deterioration, rot or rust.",
            "We do not cover theft from unoccupied buildings, or malicious damage while the building is unoccupied.",
            "We do not cover loss caused by cyber events, including ransomware, unless the cyber extension is shown in the schedule.",
        ]),
        ("Section 5: Conditions", [
            "Fire suppression: where deep-fat frying takes place, an automatic fire suppression system must be fitted and serviced "
            "at least every six months. This is a condition precedent to our liability for fire claims.",
            "Unoccupancy: you must tell us within 7 days if any building becomes unoccupied, and inspect it at least weekly.",
            "Claims: you must notify us of any claim within 14 days. Prompt notification is a condition precedent to our liability.",
            "Claims are notified to claims@harbourline.example or by phone on 0300 555 0142.",
        ]),
    ]),
    "Northgate Mutual Liability Policy Wording.pdf": ("Northgate Mutual Insurance", "Employers' and Public Liability Wording (NM-EPL 2026)", [
        ("Part A: Employers' liability", [
            "Limit of indemnity: £10,000,000 for any one occurrence, including costs. "
            "This limit is reduced to £5,000,000 for claims arising out of terrorism.",
            "Territorial limits: Great Britain, Northern Ireland, the Isle of Man and the Channel Islands, and employees "
            "temporarily working abroad for up to 90 days.",
        ]),
        ("Part B: Public and products liability", [
            "Limit of indemnity: £5,000,000 any one occurrence for public liability, and £5,000,000 in the aggregate for products liability. "
            "Higher limits of £10,000,000 are available by endorsement.",
            "Excess: £250 for third-party property damage claims. There is no excess for bodily injury claims.",
        ]),
        ("Part C: Exclusions", [
            "We do not cover liability arising from work at heights above 15 metres, unless agreed in writing.",
            "We do not cover liability arising from asbestos.",
            "We do not cover professional advice or design, which needs a professional indemnity policy.",
        ]),
        ("Part D: Conditions", [
            "Heat work: when using any flame or heat-producing equipment away from your premises, you must keep a suitable fire "
            "extinguisher at hand, remove combustible materials within 10 metres, and inspect the area for 60 minutes after work ends. "
            "This is a condition precedent to our liability.",
            "Claims: you must tell us of any incident that may lead to a claim as soon as reasonably possible, and in any case within 30 days.",
            "Subcontractors: you must check that subcontractors hold public liability insurance with a limit of at least £2,000,000.",
        ]),
    ]),
    "Ashby & Vale Fleet Motor Policy Wording.pdf": ("Ashby & Vale Underwriting", "Fleet Motor Policy Wording (AV-FM 2026)", [
        ("Section 1: Who may drive", [
            "Any driver aged 25 to 75 who holds a full UK licence held for at least 2 years, and who is employed by you.",
            "Drivers aged under 25 are covered only if approved by us in writing before they drive.",
            "Drivers with more than 6 penalty points, or any drink-driving conviction in the last 10 years, are not covered unless agreed by us.",
        ]),
        ("Section 2: Excesses", [
            "Accidental damage: £350 for each claim.",
            "Additional excess for drivers aged under 25: £750, added to the accidental damage excess.",
            "Windscreen: £75 if repaired by our approved supplier; £250 otherwise.",
        ]),
        ("Section 3: Cover", [
            "Comprehensive cover for vehicles listed in the schedule, including fire and theft.",
            "Territorial limits: Great Britain, Northern Ireland, and any EU country for up to 30 days per trip.",
            "Goods in transit is not covered by this policy.",
        ]),
        ("Section 4: Conditions", [
            "Telematics: fleets of more than 10 HGVs must have our approved telematics fitted within 30 days of inception.",
            "Accidents must be reported to us within 48 hours using our 24-hour line, 0300 555 0177.",
            "Vehicles must be kept in a roadworthy condition and have a valid MOT where required.",
        ]),
    ]),
}


def make_pdf(path, insurer, title, sections):
    pdf = FPDF()
    pdf.set_auto_page_break(True, margin=20)
    for heading, paras in sections:
        pdf.add_page()  # one section per page, so citations point at a clear page number
        pdf.set_font("Helvetica", "B", 9)
        pdf.cell(0, 6, f"{insurer} - {title}", new_x="LMARGIN", new_y="NEXT")
        pdf.ln(4)
        pdf.set_font("Helvetica", "B", 13)
        pdf.cell(0, 8, heading, new_x="LMARGIN", new_y="NEXT")
        pdf.ln(2)
        pdf.set_font("Helvetica", "", 11)
        for p in paras:
            pdf.multi_cell(0, 6, p)
            pdf.ln(2)
    pdf.output(str(path))


# --------------------------------------------------------------- Excel: rates and appetite

APPETITE = [
    ("Trade", "Harbourline Insurance", "Northgate Mutual", "Ashby & Vale", "Notes"),
    ("Logistics and haulage", "Yes", "Yes", "Yes (fleet)", "Telematics required over 10 HGVs"),
    ("Light manufacturing", "Yes", "Yes", "No", "Northgate excludes heat work without a permit system"),
    ("Professional offices", "Yes", "Yes", "No", "Northgate does not cover professional advice"),
    ("Retail shops", "Yes", "Yes", "No", ""),
    ("Restaurants with deep-fat frying", "Refer", "Yes", "No", "Harbourline only with fire suppression serviced six-monthly"),
    ("Restaurants without frying", "Yes", "Yes", "No", ""),
    ("Property owners (commercial lets)", "Yes", "Yes", "No", "Unoccupied buildings: weekly inspection"),
    ("Construction (no heights above 15m)", "No", "Yes", "Refer", "Northgate excludes work above 15 metres"),
    ("Waste and recycling", "No", "No", "No", "Declined by our placement guide"),
    ("Nightclubs", "No", "No", "No", "Declined by our placement guide"),
]

RATES = [
    ("Insurer", "Product", "Trade", "Base rate", "Minimum premium (£)"),
    ("Harbourline Insurance", "Commercial property", "Retail shops", "0.12% of sum insured", 450),
    ("Harbourline Insurance", "Commercial property", "Property owners", "0.09% of sum insured", 400),
    ("Harbourline Insurance", "Commercial property", "Restaurants with frying", "0.28% of sum insured", 950),
    ("Harbourline Insurance", "Commercial property", "Light manufacturing", "0.18% of sum insured", 750),
    ("Northgate Mutual", "Employers' liability", "Logistics and haulage", "0.65% of wageroll", 600),
    ("Northgate Mutual", "Employers' liability", "Professional offices", "0.08% of wageroll", 250),
    ("Northgate Mutual", "Public liability", "Construction", "1.10% of turnover", 1200),
    ("Northgate Mutual", "Public liability", "Retail shops", "0.15% of turnover", 300),
    ("Ashby & Vale Underwriting", "Fleet motor", "HGV (over 7.5t)", "£2,150 per vehicle", 10000),
    ("Ashby & Vale Underwriting", "Fleet motor", "Vans (up to 3.5t)", "£890 per vehicle", 3500),
    ("Ashby & Vale Underwriting", "Fleet motor", "Cars", "£640 per vehicle", 2500),
]


def make_xlsx(path):
    wb = Workbook()
    ws = wb.active
    ws.title = "Appetite"
    for r in APPETITE:
        ws.append(r)
    ws2 = wb.create_sheet("Rates")
    for r in RATES:
        ws2.append(r)
    wb.save(path)


# --------------------------------------------------------------- emails

EMAILS = [
    ("2026-10-02 Northgate - Kestrel Logistics renewal terms.eml", "Priya Shah <priya.shah@northgate.example>",
     "Re: Kestrel Logistics Ltd - EL/PL renewal 1 December 2026", "Fri, 02 Oct 2026 10:14:00 +0100",
     "Hi Tom,\n\nThanks for the claims experience for Kestrel Logistics Ltd.\n\n"
     "Given the two manual handling claims this year, we can offer renewal at a rate increase of 7.5% on the employers' "
     "liability wageroll rate, so 0.70% instead of 0.65%. Public liability terms are as expiring.\n\n"
     "This is subject to a manual handling training record for all warehouse staff by 15 November 2026.\n\n"
     "Terms are valid for 30 days.\n\nKind regards,\nPriya Shah\nSenior Underwriter, Northgate Mutual"),
    ("2026-09-18 Harbourline - escape of water excess change.eml", "Underwriting Updates <updates@harbourline.example>",
     "Change to escape of water excess from 1 January 2027", "Fri, 18 Sep 2026 09:00:00 +0100",
     "Dear broker partner,\n\nFrom 1 January 2027, the escape of water excess on all new and renewing Harbourline commercial "
     "property policies will increase from £1,000 to £2,500, reflecting the cost of recent claims.\n\n"
     "Policies incepting before 1 January 2027 keep the £1,000 excess until their next renewal.\n\n"
     "Harbourline Underwriting"),
    ("2026-10-21 Ashby & Vale - young driver approval Fenwick Builders.eml", "Mark Doyle <mark.doyle@ashbyvale.example>",
     "Re: Fenwick Builders - driver approval request (J. Fenwick, age 22)", "Wed, 21 Oct 2026 15:42:00 +0100",
     "Hi Sarah,\n\nWe've reviewed the licence check and claims history for Jamie Fenwick (age 22).\n\n"
     "Approved to drive the Ford Transit (registration FB21 KLM) only, with the £750 young driver excess applying. "
     "Not approved for the tipper truck.\n\nApproval is effective from 22 October 2026.\n\nMark Doyle\nAshby & Vale Underwriting"),
    ("2026-11-04 Harbourline - Bramble Kitchen suppression decline.eml", "Lucy Grant <lucy.grant@harbourline.example>",
     "Re: Bramble Kitchen - restaurant quotation", "Wed, 04 Nov 2026 11:20:00 +0000",
     "Hi Tom,\n\nUnfortunately we can't quote for Bramble Kitchen at this stage. The survey found the fryer suppression system "
     "was last serviced in March 2026, more than six months ago.\n\n"
     "If the client provides a service certificate dated within the last six months, we'll be happy to quote at our standard "
     "restaurant rate of 0.28% of the sum insured.\n\nBest,\nLucy Grant\nHarbourline Insurance"),
]


def make_eml(path, sender, subject, date, body):
    m = EmailMessage()
    m["From"], m["To"], m["Subject"], m["Date"] = sender, "placements@wensumrisk.example", subject, date
    m.set_content(body)
    path.write_bytes(bytes(m))


def main():
    (OUT / "Policy wordings").mkdir(parents=True, exist_ok=True)
    (OUT / "Insurer emails").mkdir(parents=True, exist_ok=True)
    make_guide(OUT / "Placement and Underwriting Guide.docx")
    for name, (insurer, title, sections) in WORDINGS.items():
        make_pdf(OUT / "Policy wordings" / name, insurer, title, sections)
    make_xlsx(OUT / "Insurer rates and appetite.xlsx")
    for name, sender, subject, date, body in EMAILS:
        make_eml(OUT / "Insurer emails" / name, sender, subject, date, body)
    print(f"wrote demo documents to {OUT}")


if __name__ == "__main__":
    main()
