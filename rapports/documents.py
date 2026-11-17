"""Génération des documents PDF avec ReportLab."""

from io import BytesIO

from django.conf import settings
from django.http import HttpResponse
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


class DocumentPdf:
    """Petit constructeur de documents pour éviter la duplication de code."""

    def __init__(self, titre, sous_titre=''):
        self.buffer = BytesIO()
        self.document = SimpleDocTemplate(
            self.buffer, pagesize=A4,
            leftMargin=18 * mm, rightMargin=18 * mm,
            topMargin=18 * mm, bottomMargin=18 * mm,
            title=titre, author=settings.PHARMACIE_NOM,
        )
        styles = getSampleStyleSheet()
        self.styles = styles
        self.titre_style = ParagraphStyle(
            'TitrePharmaGest', parent=styles['Title'], fontSize=17, spaceAfter=4 * mm,
        )
        self.elements = [
            Paragraph(settings.PHARMACIE_NOM, styles['Heading2']),
            Paragraph(titre, self.titre_style),
        ]
        if sous_titre:
            self.elements.append(Paragraph(sous_titre, styles['Normal']))
        self.elements.append(Spacer(1, 5 * mm))

    def paragraphe(self, texte):
        self.elements.append(Paragraph(texte, self.styles['Normal']))

    def tableau(self, donnees, largeurs=None):
        tableau = Table(donnees, colWidths=largeurs, repeatRows=1, hAlign='LEFT')
        tableau.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#0d6efd')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('GRID', (0, 0), (-1, -1), 0.4, colors.grey),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f1f5f9')]),
            ('LEFTPADDING', (0, 0), (-1, -1), 5),
            ('RIGHTPADDING', (0, 0), (-1, -1), 5),
        ]))
        self.elements.append(tableau)
        self.elements.append(Spacer(1, 5 * mm))

    def reponse(self, nom_fichier):
        self.document.build(self.elements)
        pdf = self.buffer.getvalue()
        response = HttpResponse(pdf, content_type='application/pdf')
        response['Content-Disposition'] = f'inline; filename="{nom_fichier}.pdf"'
        return response
