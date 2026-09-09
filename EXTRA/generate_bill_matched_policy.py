from pathlib import Path
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak
from reportlab.lib import colors

OUT = Path('fixtures/phase4/policy_bill_matched_usd.pdf')
OUT.parent.mkdir(parents=True, exist_ok=True)
styles = getSampleStyleSheet()
styles.add(ParagraphStyle(name='TitleCenter', parent=styles['Title'], alignment=TA_CENTER, textColor=colors.HexColor('#123B63'), fontSize=16, leading=20))
styles.add(ParagraphStyle(name='LabelLine', parent=styles['BodyText'], fontSize=10, leading=15, spaceAfter=3))
styles.add(ParagraphStyle(name='Small', parent=styles['BodyText'], fontSize=8, leading=10, textColor=colors.HexColor('#555555')))

doc = SimpleDocTemplate(str(OUT), pagesize=letter, rightMargin=0.7*72, leftMargin=0.7*72, topMargin=0.55*72, bottomMargin=0.55*72)
story = [Paragraph('SYNTHETIC TEST POLICY — NOT A REAL INSURANCE CONTRACT', styles['TitleCenter']), Spacer(1, 8)]
def line(label, value):
    story.append(Paragraph(f'<b>{label}:</b> {value}', styles['LabelLine']))

story.append(Paragraph('<b>HDFC ERGO General Insurance — Example Test Plan</b>', styles['Heading2']))
story.append(Paragraph('This document is synthetic test data created only for Medi Gaurd AI testing. It is not a real insurance contract and must not be used to determine actual coverage.', styles['Small']))
story.append(Spacer(1, 8))
line('Policy number', 'POL-HDFC-ERGO-SYN-2026-001')
line('Member reference', 'MRN-1039485')
line('Member name', 'Amit Singh')
line('Insurer', 'HDFC ERGO General Insurance')
line('Currency', 'USD')
line('Effective date', '2026-01-01')
line('Expiry date', '2026-12-31')
story.append(Spacer(1, 8))
story.append(PageBreak())
story.append(Paragraph('1. Coverage and financial terms', styles['Heading2']))
line('Annual limit', 'USD 50,000 per policy year')
line('Deductible', 'USD 100 per claim')
line('Copayment', '10 percent after deductible')
line('Room limit', 'USD 500 per day')
line('Emergency room coverage', 'Covered when medically necessary and documented')
line('Diagnostic tests coverage', 'Covered when ordered for a covered condition')
line('Pharmacy and medicines coverage', 'Covered when prescribed for a covered condition')
story.append(Spacer(1, 8))
story.append(Paragraph('2. Waiting period and authorization controls', styles['Heading2']))
line('Waiting period', '12 months for pre-existing conditions')
line('Pre-authorization', 'Required for planned admissions and procedures above USD 1,000')
line('Emergency authorization', 'Emergency room treatment may proceed without prior authorization when emergency documentation is present')
story.append(Spacer(1, 8))
story.append(PageBreak())
story.append(Paragraph('3. Network and exclusions', styles['Heading2']))
line('Network restriction', 'In-network providers receive the stated benefits; confirmed out-of-network services are not covered')
line('Exclusions', 'Cosmetic treatment, experimental treatment, and services unrelated to the documented diagnosis are excluded')
story.append(Spacer(1, 8))
story.append(Paragraph('4. Evidence and adjudication rules', styles['Heading2']))
story.append(Paragraph('The patient amount due on a provider statement is not automatically the insurance-covered amount. The verifier must use billed line items, policy terms, deductible, copayment, limits, adjustments, and authoritative evidence. Suspected duplicate charges are not automatically removed. Multiple bills require explicit reviewer confirmation before aggregation.', styles['BodyText']))
story.append(Spacer(1, 8))
story.append(Paragraph('Synthetic fixture note: This policy is intentionally matched to the uploaded Lilavati Hospital-style bill. The bill shows total billed charges of USD 1,508.00, an insurance adjustment of USD 1,309.00, and patient amount due of USD 199.00.', styles['Small']))
doc.build(story)
print(OUT)
