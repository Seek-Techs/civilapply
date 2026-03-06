# civil_engineering/cv_pdf.py
#
# Generates a professional one-page CV as a PDF file.
# Called by apply.py (single job) and batch.py (multiple jobs).
#
# DESIGN DECISIONS:
# - A4 format (Nigerian standard)
# - Two-column header: name/title left, contact right
# - Thin accent line under header (dark navy)
# - Section headers in small caps with rule underneath
# - Bullet points as en-dashes (cleaner than circles on screen)
# - Skills shown as inline tags in a single row
# - Fits on one page for 11 years experience
#
# WHY REPORTLAB NOT WORD?
# reportlab produces pixel-perfect layouts every time.
# Word documents look different on every machine.
# A PDF is what recruiters actually want to receive.

import os
from reportlab.lib.pagesizes    import A4
from reportlab.lib.units        import mm
from reportlab.lib              import colors
from reportlab.lib.styles       import ParagraphStyle
from reportlab.lib.enums        import TA_LEFT, TA_RIGHT, TA_CENTER
from reportlab.platypus         import (
    SimpleDocTemplate, Paragraph, Spacer,
    HRFlowable, Table, TableStyle, KeepTogether
)
from reportlab.pdfbase          import pdfmetrics
from reportlab.pdfbase.ttfonts  import TTFont

# ── Colour palette ────────────────────────────────────────────────────────────
NAVY    = colors.HexColor('#1a2744')   # section headers, name
DARK    = colors.HexColor('#1e1e1e')   # body text
MUTED   = colors.HexColor('#555555')   # dates, locations
ACCENT  = colors.HexColor('#2d6a4f')   # thin rule, skill tags
WHITE   = colors.white
LIGHT   = colors.HexColor('#f4f4f0')   # skill tag background

# ── Page margins ──────────────────────────────────────────────────────────────
LEFT_MARGIN   = 18 * mm
RIGHT_MARGIN  = 18 * mm
TOP_MARGIN    = 16 * mm
BOTTOM_MARGIN = 14 * mm

PAGE_W, PAGE_H = A4
CONTENT_W = PAGE_W - LEFT_MARGIN - RIGHT_MARGIN


# ── Styles ────────────────────────────────────────────────────────────────────

def _make_styles():
    return {
        'name': ParagraphStyle(
            'name',
            fontName='Helvetica-Bold',
            fontSize=20,
            textColor=NAVY,
            leading=24,
            spaceAfter=1,
        ),
        'title': ParagraphStyle(
            'title',
            fontName='Helvetica',
            fontSize=10.5,
            textColor=MUTED,
            leading=14,
            spaceAfter=0,
        ),
        'contact': ParagraphStyle(
            'contact',
            fontName='Helvetica',
            fontSize=8.5,
            textColor=MUTED,
            leading=13,
            alignment=TA_RIGHT,
        ),
        'section': ParagraphStyle(
            'section',
            fontName='Helvetica-Bold',
            fontSize=8.5,
            textColor=NAVY,
            leading=12,
            spaceBefore=7,
            spaceAfter=2,
            letterSpacing=1.2,
        ),
        'summary': ParagraphStyle(
            'summary',
            fontName='Helvetica',
            fontSize=9,
            textColor=DARK,
            leading=14,
            spaceAfter=2,
        ),
        'job_title': ParagraphStyle(
            'job_title',
            fontName='Helvetica-Bold',
            fontSize=9.5,
            textColor=DARK,
            leading=13,
            spaceAfter=0,
        ),
        'job_meta': ParagraphStyle(
            'job_meta',
            fontName='Helvetica-Oblique',
            fontSize=8.5,
            textColor=MUTED,
            leading=12,
            spaceAfter=2,
        ),
        'bullet': ParagraphStyle(
            'bullet',
            fontName='Helvetica',
            fontSize=8.5,
            textColor=DARK,
            leading=13,
            leftIndent=10,
            spaceAfter=1,
            bulletIndent=0,
            bulletFontName='Helvetica',
            bulletFontSize=8.5,
            bulletColor=ACCENT,
        ),
        'edu_degree': ParagraphStyle(
            'edu_degree',
            fontName='Helvetica-Bold',
            fontSize=9,
            textColor=DARK,
            leading=13,
            spaceAfter=0,
        ),
        'edu_meta': ParagraphStyle(
            'edu_meta',
            fontName='Helvetica',
            fontSize=8.5,
            textColor=MUTED,
            leading=12,
            spaceAfter=3,
        ),
        'skill_text': ParagraphStyle(
            'skill_text',
            fontName='Helvetica',
            fontSize=8.5,
            textColor=DARK,
            leading=14,
        ),
        'knowledge_item': ParagraphStyle(
            'knowledge_item',
            fontName='Helvetica',
            fontSize=8.5,
            textColor=DARK,
            leading=13,
            leftIndent=10,
            spaceAfter=1,
        ),
    }


# ── Section rule ──────────────────────────────────────────────────────────────

def _section_block(title: str, styles: dict) -> list:
    """Section header + accent rule."""
    return [
        Paragraph(title.upper(), styles['section']),
        HRFlowable(
            width='100%',
            thickness=1.2,
            color=ACCENT,
            spaceAfter=4,
        ),
    ]


# ── Header (name + contact) ───────────────────────────────────────────────────

def _build_header(profile: dict, styles: dict) -> list:
    name    = profile.get('name', '')
    title   = profile.get('title', '')
    years   = profile.get('experience_years', '')
    email   = profile.get('email', '')
    phone   = profile.get('phone', '')
    loc     = profile.get('location', '')
    linkedin = profile.get('linkedin', '')

    title_line = f"{title}  |  {years} Years Experience" if years else title

    contact_lines = []
    if phone:    contact_lines.append(phone)
    if email:    contact_lines.append(email)
    if loc:      contact_lines.append(loc)
    if linkedin: contact_lines.append(linkedin)

    left_col  = [
        Paragraph(name, styles['name']),
        Paragraph(title_line, styles['title']),
    ]
    right_col = [
        Paragraph('<br/>'.join(contact_lines), styles['contact']),
    ]

    tbl = Table(
        [[left_col, right_col]],
        colWidths=[CONTENT_W * 0.60, CONTENT_W * 0.40],
    )
    tbl.setStyle(TableStyle([
        ('VALIGN',       (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING',  (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        ('TOPPADDING',   (0, 0), (-1, -1), 0),
        ('BOTTOMPADDING',(0, 0), (-1, -1), 0),
    ]))

    return [
        tbl,
        HRFlowable(width='100%', thickness=2, color=NAVY, spaceBefore=5, spaceAfter=6),
    ]


# ── Summary ───────────────────────────────────────────────────────────────────

def _build_summary(summary_text: str, styles: dict) -> list:
    if not summary_text:
        return []
    return [
        *_section_block('Professional Summary', styles),
        Paragraph(summary_text, styles['summary']),
        Spacer(1, 3),
    ]


# ── Experience ────────────────────────────────────────────────────────────────

def _build_experience(experience: list, styles: dict) -> list:
    if not experience:
        return []

    elements = [*_section_block('Professional Experience', styles)]

    for role in experience:
        job_title = role.get('role', '')
        company   = role.get('company', '')
        location  = role.get('location', '')
        period    = role.get('period', '')

        meta_parts = []
        if company:  meta_parts.append(company)
        if location: meta_parts.append(location)
        if period:   meta_parts.append(period)

        block = [
            Paragraph(job_title, styles['job_title']),
            Paragraph('  |  '.join(meta_parts), styles['job_meta']),
        ]

        bullets = role.get('bullets', [])
        for b in bullets:
            text = b.lstrip('- ').strip()
            if text:
                block.append(
                    Paragraph(f'– {text}', styles['bullet'])
                )

        block.append(Spacer(1, 4))
        elements.append(KeepTogether(block))

    return elements


# ── Education ─────────────────────────────────────────────────────────────────

def _build_education(education: list, styles: dict) -> list:
    if not education:
        return []

    elements = [*_section_block('Education', styles)]

    for edu in education:
        degree  = edu.get('degree', '')
        inst    = edu.get('institution', '')
        year    = edu.get('year', '')
        meta    = '  |  '.join(filter(None, [inst, year]))

        block = [
            Paragraph(degree, styles['edu_degree']),
            Paragraph(meta, styles['edu_meta']),
        ]
        elements.append(KeepTogether(block))

    return elements


# ── Skills ────────────────────────────────────────────────────────────────────

def _build_skills(skills: list, styles: dict) -> list:
    if not skills:
        return []

    # Capitalise known tools properly
    CAPS = {
        'autocad': 'AutoCAD', 'protastructure': 'ProtaStructure',
        'ms excel': 'MS Excel', 'ms project': 'MS Project',
        'power bi': 'Power BI', 'hse': 'HSE', 'qa/qc': 'QA/QC',
        'bim': 'BIM', 'coren': 'COREN', 'python': 'Python',
    }
    capped = [CAPS.get(s.lower(), s.title()) for s in skills]
    skill_line = '  ·  '.join(capped)

    return [
        *_section_block('Technical Skills', styles),
        Paragraph(skill_line, styles['skill_text']),
        Spacer(1, 3),
    ]


# ── Structural Knowledge ──────────────────────────────────────────────────────

def _build_knowledge(knowledge: list, styles: dict) -> list:
    if not knowledge:
        return []

    elements = [*_section_block('Structural Engineering Knowledge', styles)]
    for item in knowledge:
        elements.append(Paragraph(f'– {item.strip()}', styles['knowledge_item']))
    elements.append(Spacer(1, 3))
    return elements


# ── Public API ────────────────────────────────────────────────────────────────

def generate_cv_pdf(
    cv:           dict,
    output_path:  str,
    cv_summary:   str = '',
) -> str:
    """
    Generate a professional CV PDF.

    Args:
        cv:          Normalised CV dict (from normalize_cv)
        output_path: Where to save the PDF
        cv_summary:  AI-written tailored summary (optional)

    Returns:
        output_path (so caller can print/open it)

    WHY RETURN THE PATH?
    Callers (apply.py, batch.py, web.py) need to know where the file
    landed so they can display it, link to it, or open it.
    Returning the path instead of True/False gives them flexibility.
    """
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    styles = _make_styles()

    doc = SimpleDocTemplate(
        output_path,
        pagesize=A4,
        leftMargin=LEFT_MARGIN,
        rightMargin=RIGHT_MARGIN,
        topMargin=TOP_MARGIN,
        bottomMargin=BOTTOM_MARGIN,
        title=cv.get('profile', {}).get('name', 'CV'),
        author=cv.get('profile', {}).get('name', ''),
    )

    profile    = cv.get('profile', {})
    experience = cv.get('experience', [])
    education  = cv.get('education', [])
    skills     = cv.get('skills', [])
    knowledge  = cv.get('structural_knowledge', [])

    # Use AI summary if provided, otherwise fall back to CV's own summary
    summary = cv_summary or cv.get('summary', '')

    story = []
    story += _build_header(profile, styles)
    story += _build_summary(summary, styles)
    story += _build_experience(experience, styles)
    story += _build_education(education, styles)
    story += _build_skills(skills, styles)
    story += _build_knowledge(knowledge, styles)

    doc.build(story)
    return output_path