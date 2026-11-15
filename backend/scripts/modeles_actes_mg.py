"""
Génère les modèles malgaches des actes de naissance et de décès à partir des modèles français.

    .venv/bin/python scripts/modeles_actes_mg.py

Lit static/mairy_admin/actes/originaux/acte_{naissance,deces}.jpg (modèles de la Commune, en français),
efface chaque libellé français (le fond — papier et filigrane — est reconstitué colonne par colonne)
et le réécrit en malgache, à la même place et dans une police équivalente (Liberation Serif, mêmes
proportions que Times New Roman). Écrit static/mairy_admin/actes/acte_{naissance,deces}.jpg et
affiche les coordonnées des pointillés à reporter dans agents/pdf.py.
"""
import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ACTES = Path(__file__).resolve().parent.parent / 'static' / 'mairy_admin' / 'actes'
FONTS = Path('/usr/share/fonts/truetype/liberation')
FACES = {
    'bold': FONTS / 'LiberationSerif-Bold.ttf',
    'regular': FONTS / 'LiberationSerif-Regular.ttf',
    'italic': FONTS / 'LiberationSerif-Italic.ttf',
}
INK = (22, 22, 22)
PAPER = (243, 242, 243)
DOTS_END = 1017


def font(face, size):
    return ImageFont.truetype(str(FACES[face]), size)


def fit_size(face, reference, height):
    """Taille de police pour que `reference` (le texte français d'origine) ait la hauteur d'encre `height`."""
    size = height
    for candidate in range(int(height * 0.8), int(height * 2.2)):
        top, bottom = font(face, candidate).getbbox(reference, anchor='ls')[1::2]
        if bottom - top >= height:
            return candidate
        size = candidate
    return size


def _is_ink(p, threshold=200):
    return sum(p) / 3 < threshold


def erase(im, box, grow=None):
    """
    Efface l'encre (texte, pointillés) de la zone sans toucher au filigrane qui l'entoure : chaque pixel
    d'encre, élargi de 2 px, est remplacé par l'interpolation verticale des pixels de fond les plus proches.
    """
    px = im.load()
    x0, y0, x1, y1 = box
    # Halo d'anticrénelage plus large autour des grands caractères (titre).
    grow = grow or max(3, (y1 - y0) // 12)
    mask = set()
    for y in range(y0, y1 + 1):
        for x in range(x0, x1 + 1):
            if _is_ink(px[x, y]):
                for dy in range(-grow, grow + 1):
                    for dx in range(-grow, grow + 1):
                        if x0 <= x + dx <= x1 and y0 <= y + dy <= y1:
                            mask.add((x + dx, y + dy))
    # Reste du halo gris collé aux lettres : ajouté au masque de proche en proche.
    pending = [(x, y, 0) for x, y in mask]
    while pending:
        x, y, depth = pending.pop()
        if depth >= 4:  # au plus 4 px : le filigrane plus loin reste intact
            continue
        for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
            if (nx, ny) not in mask and x0 <= nx <= x1 and y0 <= ny <= y1 and _is_ink(px[nx, ny], 228):
                mask.add((nx, ny))
                pending.append((nx, ny, depth + 1))

    def clean(x, y, step):
        """Premier pixel de fond franc (ni encre ni halo) en partant de (x, y), vers le haut ou le bas."""
        for k in range(12):
            yy = y + k * step
            if 0 <= yy < im.height and (x, yy) not in mask and not _is_ink(px[x, yy], 228):
                return px[x, yy]
        return None

    for x in range(x0, x1 + 1):
        y = y0
        while y <= y1:
            if (x, y) not in mask:
                y += 1
                continue
            start = y
            while y <= y1 and (x, y) in mask:
                y += 1
            above = clean(x, start - 1, -1)
            below = clean(x, y, 1)
            above = above or below or PAPER
            below = below or above
            span = y - start + 1
            for k in range(start, y):
                t = (k - start + 1) / span
                px[x, k] = tuple(round(a + (b - a) * t) for a, b in zip(above, below))


class Writer:
    def __init__(self, path):
        self.im = Image.open(path).convert('RGB')
        self.draw = ImageDraw.Draw(self.im)
        self.slots = {}

    def replace(self, band, french, malagasy, face='bold', align='center', max_width=None, erase_box=None):
        """Remplace le texte `french` (bande d'encre `band` = (y0, y1, x0, x1)) par `malagasy`."""
        y0, y1, x0, x1 = band
        erase(self.im, erase_box or (x0 - 3, y0 - 3, x1 + 3, y1 + 3))
        size = fit_size(face, french, y1 - y0 + 1)
        top = font(face, size).getbbox(french, anchor='ls')[1]
        baseline = y0 - top
        width_limit = max_width or (x1 - x0)
        while size > 8 and font(face, size).getlength(malagasy) > width_limit:
            size -= 1
        f = font(face, size)
        x = (x0 + x1) / 2 - f.getlength(malagasy) / 2 if align == 'center' else x0
        self.draw.text((x, baseline), malagasy, font=f, fill=INK, anchor='ls')
        return x, x + f.getlength(malagasy), baseline, size

    def dots(self, name, left, right, baseline, size):
        """Pointillés de `left` à `right` ; mémorise la zone pour y écrire la valeur dans le PDF."""
        f = font('regular', size)
        count = int((right - left) / f.getlength('.'))
        self.draw.text((left, baseline), '.' * count, font=f, fill=INK, anchor='ls')
        self.slots[name] = [round(left), round(left + count * f.getlength('.')), round(baseline)]
        return left + count * f.getlength('.')

    def row(self, name, band, malagasy, size, baseline, face='bold', dots=True):
        """Ligne « Libellé : ........ » à la taille commune du formulaire, posée sur la ligne de base d'origine."""
        y0, y1, x0, _ = band
        erase(self.im, (x0 - 3, y0 - 3, DOTS_END + 4, y1 + 3))
        f = font(face, size)
        self.draw.text((x0, baseline), malagasy, font=f, fill=INK, anchor='ls')
        if dots:
            self.dots(name, x0 + f.getlength(malagasy) + 10, DOTS_END, baseline, size)

    def date_line(self, band, french, malagasy):
        """« Natao teto Mahajanga, tamin'ny ........ / ........ / ........ »."""
        y0, y1, x0, x1 = band
        erase(self.im, (x0 - 3, y0 - 3, x1 + 3, y1 + 3))
        _, end, baseline, size = self.replace((y0, y1, x0, x0 + 2000), french, malagasy, 'regular', 'left',
                                              erase_box=(x0, y0, x0, y0))
        f = font('regular', size)
        slash = f.getlength(' / ')
        x = end + 8
        for name, width in (('day', 80), ('month', 80), ('year', 96)):
            x = self.dots(name, x, x + width, baseline, size)
            if name != 'year':
                self.draw.text((x, baseline), ' / ', font=f, fill=INK, anchor='ls')
                x += slash

    def signature(self, maire, officier, nom):
        """« Le Maire, Officier de l'Etat Civil » et « Nom et Prénoms » (souligné)."""
        self.replace(maire, 'Le Maire,', "Ny Ben'ny Tanàna,", max_width=360)
        self.replace(officier, "Officier de l’Etat Civil", 'Mpiandraikitra ny fiankohonana', max_width=360)
        y0, y1, x0, x1 = nom
        erase(self.im, (x0 - 6, y0 - 3, x1 + 6, 1351))
        left, right, baseline, _ = self.replace(nom, 'Nom et Prénoms', "Anarana sy fanampin'anarana", 'italic',
                                                max_width=340, erase_box=(x0, y0, x0, y0))
        self.draw.rectangle((left, 1347, right, 1348), fill=INK)

    def header(self, lines, ministere, acte):
        """Colonne de gauche (région, district, commune, arrondissement) et de droite (ministère, N° d'acte)."""
        region, district, commune, arrondissement = lines
        self.replace(region, 'REGION  BOENY', 'FARITRA BOENY')
        self.replace(district, 'DISTRICT DE MAHAJANGA', "DISTRIKAN'I MAHAJANGA")
        self.replace(commune, 'COMMUNE URBAINE DE MAHAJANGA', "KAOMININA AMBONIVOHITR'I MAHAJANGA", max_width=385)
        y0, y1, x0, x1 = arrondissement
        erase(self.im, (x0 - 3, y0 - 3, x1 + 3, y1 + 3))
        label = 'BORIBORINTANY FAHA-'
        size = fit_size('bold', 'ARRONDISSEMENT N°', y1 - y0 + 1)
        top = font('bold', size).getbbox('ARRONDISSEMENT N°', anchor='ls')[1]
        baseline = y0 - top
        total = font('bold', size).getlength(label) + 8 + 64
        left = (x0 + x1) / 2 - total / 2
        self.draw.text((left, baseline), label, font=font('bold', size), fill=INK, anchor='ls')
        self.dots('arrondissement', left + font('bold', size).getlength(label) + 8, left + total, baseline, size)

        ministere_1, ministere_2 = ministere
        self.replace(ministere_1, 'MINISTERE DE L’INTERIEUR', "MINISTERAN'NY ATITANY")
        self.replace(ministere_2, 'ET DE LA DECENTRALISATION', "SY NY FITSINJARAM-PAHEFANA", max_width=345)
        y0, y1, x0, x1 = acte
        erase(self.im, (x0 - 3, y0 - 3, 1022, y1 + 3))
        _, end, baseline, size = self.replace((y0, y1, x0, x0 + 2000), 'N° d’Acte :', 'Laharana :', 'bold',
                                              'left', erase_box=(x0, y0, x0, y0))
        self.dots('act_number', end + 8, 1018, baseline, size)

    def title(self, band, french, malagasy, subtitle, inside, erase_box=None):
        # L'intérieur du cadre du titre est du papier uni : repeint d'un aplat plutôt que reconstitué.
        x0, y0, x1, y1 = inside
        px = self.im.load()
        paper = sorted(px[x, y] for x in range(x0, x1, 7) for y in (y0, y1) if not _is_ink(px[x, y], 228))
        self.draw.rounded_rectangle(inside, radius=9, fill=paper[len(paper) // 2] if paper else PAPER)
        self.replace(band, french, malagasy, max_width=700, erase_box=erase_box or (x0, y0, x0, y0))
        self.replace(subtitle, '(Copie intégrale)', '(Dika feno)', 'italic')

    def save(self, path):
        self.im.save(path, quality=92, optimize=True)


def naissance():
    w = Writer(ACTES / 'originaux' / 'acte_naissance.jpg')
    w.header(
        [(146, 161, 135, 319), (192, 208, 89, 365), (238, 254, 40, 413), (281, 295, 84, 374)],
        [(52, 68, 710, 1020), (80, 96, 694, 1029)],
        (182, 200, 733, 1015),
    )
    w.title((342, 390, 201, 888), 'ACTE DE NAISSANCE', "KOPIAN'NY SORA-PAHATERAHANA", (417, 455, 398, 692),
            inside=(154, 331, 932, 399))
    w.date_line((1050, 1075, 71, 621), 'Fait à Mahajanga, le', "Natao teto Mahajanga, tamin'ny")
    w.signature((1106, 1131, 783, 906), (1143, 1165, 697, 989), (1323, 1343, 751, 951))
    w.save(ACTES / 'acte_naissance.jpg')
    return w.slots


def deces():
    w = Writer(ACTES / 'originaux' / 'acte_deces.jpg')
    w.header(
        [(140, 155, 136, 314), (183, 200, 88, 363), (223, 239, 41, 411), (268, 283, 76, 373)],
        [(49, 64, 707, 1021), (77, 93, 688, 1030)],
        (181, 200, 732, 1017),
    )
    # Accents de « DÉCÈS » au-dessus des majuscules : effacés avec le titre.
    w.title((327, 377, 245, 845), 'ACTE DE DECES', "KOPIAN'NY SORA-PAHAFATESANA", (403, 442, 391, 698),
            inside=(169, 314, 922, 386))
    # Introduction : deux lignes à la même taille (mesurée sur la seconde ligne d'origine).
    first_line = "Ny Ben'ny Tanànan'ny Kaominina Ambonivohitr'i Mahajanga, Mpiandraikitra ny"
    intro = fit_size('regular', 'dresse le présent acte de décès concernant :', 542 - 515 + 1) + 1
    while font('regular', intro - 1).getlength(first_line) > 1008 - 114:
        intro -= 1
    for box in ((111, 479, 1011, 512), (54, 512, 574, 545)):
        erase(w.im, box)
    w.draw.text((114, 503), first_line,
                font=font('regular', intro - 1), fill=INK, anchor='ls')
    w.draw.text((57, 536), 'fiankohonana, no nanoratra ity sora-pahafatesana ity momba an’i :',
                font=font('regular', intro - 1), fill=INK, anchor='ls')
    # Lignes du formulaire : même taille pour toutes, posées sur la ligne des pointillés d'origine.
    size = fit_size('bold', 'Date de naissance :', 661 - 642 + 1)
    rows = [
        ('deceased', (569, 595, 75), 591, "Anarana sy fanampin'anaran'ny maty :", 'bold'),
        ('sex', (605, 626, 75), 627, 'Lahy na vavy :', 'bold'),
        ('birth_date', (642, 661, 75), 661, 'Daty nahaterahana :', 'bold'),
        ('birth_place', (677, 697, 75), 696, 'Toerana nahaterahana :', 'bold'),
        ('death_date', (716, 736, 75), 736, 'Daty nahafatesana :', 'bold'),
        ('death_time', (753, 773, 75), 772, 'Ora nahafatesana :', 'bold'),
        ('death_place', (787, 807, 75), 807, 'Toerana nahafatesana :', 'bold'),
        ('cause', (823, 848, 76), 843, 'Antony nahafatesana (raha fantatra) :', 'italic'),
        ('spouse', (886, 912, 75), 908, "Anaran'ny vady velona :", 'bold'),
        ('father', (962, 984, 137), 985, 'Ray :', 'bold'),
        ('mother', (998, 1019, 136), 1019, 'Reny :', 'bold'),
    ]
    for name, (y0, y1, x0), baseline, malagasy, face in rows:
        w.row(name, (y0, y1, x0, None), malagasy, size, baseline, face)
    erase(w.im, (72, 920, 498, 952))
    w.draw.text((75, 945), "Anaran'ny ray aman-dreny :", font=font('bold', size), fill=INK, anchor='ls')
    w.date_line((1062, 1088, 76, 632), 'Fait à Mahajanga, le', "Natao teto Mahajanga, tamin'ny")
    w.signature((1128, 1150, 793, 917), (1164, 1184, 716, 1000), (1323, 1343, 765, 961))
    w.save(ACTES / 'acte_deces.jpg')
    return w.slots


if __name__ == '__main__':
    print(json.dumps({'naissance': naissance(), 'deces': deces()}, indent=1))
