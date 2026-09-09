from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak
from reportlab.lib import colors

ROOT = Path('fixtures/phase4'); ROOT.mkdir(parents=True, exist_ok=True)
W, H = 1400, 1900
img = Image.new('RGB', (W, H), '#eef3f7'); d = ImageDraw.Draw(img)
try:
    regular = r'C:\Windows\Fonts\arial.ttf'; bold = r'C:\Windows\Fonts\arialbd.ttf'
    F = lambda size, b=False: ImageFont.truetype(bold if b else regular, size)
except Exception:
    F = lambda size, b=False: ImageFont.load_default()
blue, dark, gray, red = '#145a86', '#17212b', '#52616b', '#a52a2a'
fb, f44, f32, f28, f24, f22 = F(52, True), F(44, True), F(32), F(28), F(24), F(22)
d.rectangle((45, 40, W-45, H-40), fill='white', outline='#bccbd5', width=4)
d.text((105, 85), 'Sunrise Care Hospital', fill=blue, font=fb)
d.text((105, 150), 'MG Road, Pune, Maharashtra 411001', fill=gray, font=f28)
d.text((105, 195), 'Phone: (020) 555-0182', fill=gray, font=f28)
d.line((100, 255, W-100, 255), fill='#bccbd5', width=3)
d.text((105, 295), 'MEDICAL BILL — SYNTHETIC TEST', fill=dark, font=f44)
d.text((105, 355), 'NOT A REAL MEDICAL BILL', fill=red, font=f28)

y = 410
fields = [('Statement Date', '08/23/2026'), ('Claim Number', 'CLM-DEMO-2026-001'), ('Patient Name', 'Riya Sharma'), ('Policy Number', 'POL-DEMO-2026-001'), ('Hospital', 'Sunrise Care Hospital'), ('Diagnosis', 'Acute appendicitis'), ('Admission Date', '08/20/2026'), ('Discharge Date', '08/23/2026'), ('Total Amount', 'INR 145000'), ('Diagnostic tests', 'INR 16000')]
for label, value in fields:
    d.text((115, y), f'{label}: {value}', fill=dark, font=f32); y += 50

y += 10; d.text((115, y), 'ITEMIZED CHARGES', fill=blue, font=f32); y += 48
rows = [('Room charges', 'INR 18000'), ('Doctor consultation', 'INR 12000'), ('Surgery and procedure', 'INR 85000'), ('Medicines', 'INR 14000'), ('Diagnostics', 'INR 16000')]
for label, value in rows:
    d.text((135, y), f'{label}: {value}', fill=dark, font=f28); y += 48

y += 18; d.line((115, y, W-115, y), fill='#8d9aa3', width=3); y += 28
d.text((115, y), 'Total Amount: INR 145000', fill=blue, font=f32); y += 55
d.text((115, y), 'Patient responsibility: INR 145000', fill=dark, font=f28)
d.text((105, H-130), 'Synthetic fixture for Medi Gaurd AI testing only.', fill=gray, font=f22)
img_path = ROOT / 'bill_clean_mobile_demo.png'; img.save(img_path)

pdf_path = ROOT / 'policy_clean_mobile_demo.pdf'
styles = getSampleStyleSheet(); styles.add(ParagraphStyle(name='C', parent=styles['Title'], alignment=TA_CENTER, textColor=colors.HexColor('#123B63'), fontSize=16)); styles.add(ParagraphStyle(name='L', parent=styles['BodyText'], fontSize=10, leading=15, spaceAfter=3)); styles.add(ParagraphStyle(name='S', parent=styles['BodyText'], fontSize=8, leading=10, textColor=colors.HexColor('#555555')))
doc = SimpleDocTemplate(str(pdf_path), pagesize=letter, rightMargin=50, leftMargin=50, topMargin=40, bottomMargin=40); story = [Paragraph('SYNTHETIC TEST POLICY — NOT A REAL INSURANCE CONTRACT', styles['C']), Spacer(1, 8)]
def line(label, value): story.append(Paragraph(f'<b>{label}:</b> {value}', styles['L']))
story += [Paragraph('<b>Sunrise Health Assurance — Example Test Plan</b>', styles['Heading2']), Paragraph('Synthetic test data for Medi Gaurd AI only. This is not a real insurance contract.', styles['S']), Spacer(1, 8)]
for pair in [('Policy number','POL-DEMO-2026-001'),('Member name','Riya Sharma'),('Insurer','Sunrise Health Assurance'),('Currency','INR'),('Effective date','2026-01-01'),('Expiry date','2026-12-31')]: line(*pair)
story += [PageBreak(), Paragraph('1. Coverage and financial terms', styles['Heading2'])]
for pair in [('Annual limit','INR 500,000 per policy year'),('Deductible','INR 10,000 per claim'),('Copayment','10 percent after deductible'),('Room limit','INR 5,000 per day'),('Waiting period','0 months for the covered condition')]: line(*pair)
story += [Spacer(1, 8), Paragraph('2. Required evidence controls', styles['Heading2'])]
for pair in [('Pre-authorization','Required for planned procedures above INR 100,000'),('Network restriction','In-network providers receive stated benefits; unknown network status requires Manual Review'),('Exclusions','Cosmetic, experimental, and unrelated services are excluded; uncertain exclusion evidence requires Manual Review')]: line(*pair)
story += [Spacer(1, 8), Paragraph('3. Evidence rules', styles['Heading2']), Paragraph('Use billed line items and Total Amount, not Patient responsibility, as the claim amount. Suspected duplicates are not automatically removed. Multiple bills require reviewer confirmation before aggregation.', styles['BodyText']), Spacer(1, 12), Paragraph('Synthetic fixture paired with bill_clean_mobile_demo.png for testing only.', styles['S'])]
doc.build(story); print(img_path); print(pdf_path)
