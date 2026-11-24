# -*- coding: utf-8 -*-
"""
Comprehensive Bilingual Scholarly Catalog of the 33 Sunnah Books (جامع السنة النبوية)
and the 10 Canonical Hadith Collections (صحاح ستہ، موطا مالک، اربعین نووی، قدسی، دہلوی).
"""

from typing import Dict, List

# Exact 33 Primary Sunnah Collections on hadeeth.com (/collections) with Salafi Urdu Metadata
HADEETH_33_COLLECTIONS: Dict[int, Dict[str, object]] = {
    1: {"title_ar": "صحيح البخاري", "title_ur": "صحیح البخاری (الجامع المسند الصحیح)", "author_ur": "امام محمد بن اسماعیل البخاری رحمہ اللہ (۲۵۶ھ)", "group": "kutub_sittah", "group_ur": "کتبِ ستہ (صحاحِ ستہ)", "canon_slug": "bukhari"},
    2: {"title_ar": "صحيح مسلم", "title_ur": "صحیح مسلم (المسند الصحیح المختصر)", "author_ur": "امام مسلم بن حجاج القشیری رحمہ اللہ (۲۶۱ھ)", "group": "kutub_sittah", "group_ur": "کتبِ ستہ (صحاحِ ستہ)", "canon_slug": "muslim"},
    3: {"title_ar": "سنن أبي داود", "title_ur": "سنن ابی داؤد", "author_ur": "امام ابوداؤد سلیمان بن اشعث السجستانی رحمہ اللہ (۲۷۵ھ)", "group": "kutub_sittah", "group_ur": "کتبِ ستہ (صحاحِ ستہ)", "canon_slug": "abudawud"},
    4: {"title_ar": "جامع الترمذي", "title_ur": "جامع الترمذی (سنن الترمذی)", "author_ur": "امام ابوعیسیٰ محمد بن عیسیٰ الترمذی رحمہ اللہ (۲۷۹ھ)", "group": "kutub_sittah", "group_ur": "کتبِ ستہ (صحاحِ ستہ)", "canon_slug": "tirmidhi"},
    5: {"title_ar": "سنن النسائي", "title_ur": "سنن النسائی (المجتبیٰ من السنن)", "author_ur": "امام احمد بن شعیب النسائی رحمہ اللہ (۳۰۳ھ)", "group": "kutub_sittah", "group_ur": "کتبِ ستہ (صحاحِ ستہ)", "canon_slug": "nasai"},
    6: {"title_ar": "سنن ابن ماجه", "title_ur": "سنن ابن ماجہ", "author_ur": "امام محمد بن یزید ابن ماجہ القزوینی رحمہ اللہ (۲۷۳ھ)", "group": "kutub_sittah", "group_ur": "کتبِ ستہ (صحاحِ ستہ)", "canon_slug": "ibnmajah"},
    7: {"title_ar": "موطأ مالك", "title_ur": "موطا امام مالک", "author_ur": "امام مالک بن انس رحمہ اللہ (۱۷۹ھ)", "group": "muwatta_musannafat", "group_ur": "موطا اور مصنفات", "canon_slug": "malik"},
    8: {"title_ar": "مسند أحمد", "title_ur": "مسند امام احمد بن حنبل", "author_ur": "امام اہل السنۃ احمد بن محمد بن حنبل رحمہ اللہ (۲۴۱ھ)", "group": "masanid", "group_ur": "مسانید"},
    9: {"title_ar": "مسند الدارمي", "title_ur": "مسند الدارمی (سنن الدارمی)", "author_ur": "امام ابومحمد عبداللہ بن عبدالرحمٰن الدارمی رحمہ اللہ (۲۵۵ھ)", "group": "sunan", "group_ur": "کتبِ سنن"},
    10: {"title_ar": "صحيح ابن حبان", "title_ur": "صحیح ابن حبان (الاحسان فی تقریب صحیح ابن حبان)", "author_ur": "امام محمد بن حبان البستی رحمہ اللہ (۳۵۴ھ)", "group": "sihah_mustadrakat", "group_ur": "صحاح اور مستدرکات"},
    11: {"title_ar": "صحيح ابن خزيمة", "title_ur": "صحیح ابن خزیمہ", "author_ur": "امام الائمہ محمد بن اسحاق ابن خزیمہ رحمہ اللہ (۳۱۱ھ)", "group": "sihah_mustadrakat", "group_ur": "صحاح اور مستدرکات"},
    12: {"title_ar": "المعجم الكبير", "title_ur": "المعجم الکبیر للطبرانی", "author_ur": "حافظ ابوالقاسم سلیمان بن احمد الطبرانی رحمہ اللہ (۳۶۰ھ)", "group": "maajim", "group_ur": "معاجمِ حدیث"},
    13: {"title_ar": "المعجم الأوسط", "title_ur": "المعجم الاوسط للطبرانی", "author_ur": "حافظ ابوالقاسم سلیمان بن احمد الطبرانی رحمہ اللہ (۳۶۰ھ)", "group": "maajim", "group_ur": "معاجمِ حدیث"},
    14: {"title_ar": "المعجم الصغير", "title_ur": "المعجم الصغیر للطبرانی", "author_ur": "حافظ ابوالقاسم سلیمان بن احمد الطبرانی رحمہ اللہ (۳۶۰ھ)", "group": "maajim", "group_ur": "معاجمِ حدیث"},
    15: {"title_ar": "مصنف ابن أبي شيبة", "title_ur": "مصنف ابن ابی شیبہ", "author_ur": "حافظ ابوبکر عبداللہ بن محمد بن ابی شیبہ رحمہ اللہ (۲۳۵ھ)", "group": "muwatta_musannafat", "group_ur": "موطا اور مصنفات"},
    16: {"title_ar": "مصنف عبد الرزاق", "title_ur": "مصنف عبدالرزاق الصنعانی", "author_ur": "حافظ ابوبکر عبدالرزاق بن ہمام الصنعانی رحمہ اللہ (۲۱۱ھ)", "group": "muwatta_musannafat", "group_ur": "موطا اور مصنفات"},
    17: {"title_ar": "سنن البيهقي الكبرى", "title_ur": "السنن الکبریٰ للبیہقی", "author_ur": "امام ابوبکر احمد بن حسین البیہقی رحمہ اللہ (۴۵۸ھ)", "group": "sunan", "group_ur": "کتبِ سنن"},
    18: {"title_ar": "سنن الدارقطني", "title_ur": "سنن الدارقطنی", "author_ur": "امام ابوالحسن علی بن عمر الدارقطنی رحمہ اللہ (۳۸۵ھ)", "group": "sunan", "group_ur": "کتبِ سنن"},
    19: {"title_ar": "مسند البزار", "title_ur": "مسند البزار (البحر الزخار)", "author_ur": "حافظ ابوبکر احمد بن عمرو البزار رحمہ اللہ (۲۹۲ھ)", "group": "masanid", "group_ur": "مسانید"},
    20: {"title_ar": "مسند الحميدي", "title_ur": "مسند الحمیدی", "author_ur": "امام ابوبکر عبداللہ بن زبیر الحمیدی رحمہ اللہ (۲۱۹ھ)", "group": "masanid", "group_ur": "مسانید"},
    21: {"title_ar": "مسند الطيالسي", "title_ur": "مسند ابی داؤد الطیالسی", "author_ur": "حافظ سلیمان بن داؤد الطیالسی رحمہ اللہ (۲۰۴ھ)", "group": "masanid", "group_ur": "مسانید"},
    22: {"title_ar": "السنن الكبرى", "title_ur": "السنن الکبریٰ للنسائی", "author_ur": "امام احمد بن شعیب النسائی رحمہ اللہ (۳۰۳ھ)", "group": "sunan", "group_ur": "کتبِ سنن"},
    23: {"title_ar": "مسند أبي يعلى الموصلي", "title_ur": "مسند ابی یعلیٰ الموصلی", "author_ur": "حافظ احمد بن علی بن المثنیٰ ابویعلیٰ الموصلی رحمہ اللہ (۳۰۷ھ)", "group": "masanid", "group_ur": "مسانید"},
    24: {"title_ar": "المستدرك على الصحيحين", "title_ur": "المستدرک علی الصحیحین للحاکم", "author_ur": "امام ابوعبداللہ محمد بن عبداللہ الحاکم رحمہ اللہ (۴۰۵ھ)", "group": "sihah_mustadrakat", "group_ur": "صحاح اور مستدرکات"},
    25: {"title_ar": "الأحاديث المختارة", "title_ur": "الاحادیث المختارہ للضیاء المقدسی", "author_ur": "حافظ ضیاء الدین محمد بن عبدالواحد المقدسی رحمہ اللہ (۶۴۳ھ)", "group": "sihah_mustadrakat", "group_ur": "صحاح اور مستدرکات"},
    26: {"title_ar": "المطالب العالية", "title_ur": "المطالب العالیہ بزوائد المسانید الثمانیہ", "author_ur": "حافظ شہاب الدین ابن حجر العسقلانی رحمہ اللہ (۸۵۲ھ)", "group": "other", "group_ur": "دیگر امہاتِ حدیث"},
    27: {"title_ar": "المنتقى", "title_ur": "المنتقیٰ من السنن المسندہ لابن الجارود", "author_ur": "امام عبداللہ بن علی بن الجارود النیسابوری رحمہ اللہ (۳۰۷ھ)", "group": "sihah_mustadrakat", "group_ur": "صحاح اور مستدرکات"},
    28: {"title_ar": "شرح معاني الآثار", "title_ur": "شرح معانی الآثار للطحاوی", "author_ur": "امام ابوجعفر احمد بن محمد الطحاوی رحمہ اللہ (۳۲۱ھ)", "group": "other", "group_ur": "دیگر امہاتِ حدیث"},
    29: {"title_ar": "مسند عبد بن حميد", "title_ur": "مسند عبد بن حمید (المنتخب)", "author_ur": "حافظ ابومحمد عبد بن حمید الکشّی رحمہ اللہ (۲۴۹ھ)", "group": "masanid", "group_ur": "مسانید"},
    30: {"title_ar": "سنن سعيد بن منصور", "title_ur": "سنن سعید بن منصور", "author_ur": "حافظ ابوعثمان سعید بن منصور الخراسانی رحمہ اللہ (۲۲۷ھ)", "group": "sunan", "group_ur": "کتبِ سنن"},
    31: {"title_ar": "شرح مشكل الآثار", "title_ur": "شرح مشکل الآثار للطحاوی", "author_ur": "امام ابوجعفر احمد بن محمد الطحاوی رحمہ اللہ (۳۲۱ھ)", "group": "other", "group_ur": "دیگر امہاتِ حدیث"},
    32: {"title_ar": "المراسيل لأبي داود", "title_ur": "المراسیل لابی داؤد", "author_ur": "امام ابوداؤد سلیمان بن اشعث السجستانی رحمہ اللہ (۲۷۵ھ)", "group": "other", "group_ur": "دیگر امہاتِ حدیث"},
    33: {"title_ar": "الشمائل المحمدية", "title_ur": "الشمائل المحمدیہ للترمذی", "author_ur": "امام ابوعیسیٰ محمد بن عیسیٰ الترمذی رحمہ اللہ (۲۷۹ھ)", "group": "other", "group_ur": "دیگر امہاتِ حدیث"},
}

CANONICAL_EDITIONS_SPEC: List[Dict[str, object]] = [
    {"slug": "bukhari", "hadeeth_book_id": 1, "ar_file": "ara-bukhari.min.json", "ur_file": "urd-bukhari.min.json", "title_ar": "صحيح البخاري", "title_ur": "صحیح البخاری (مکمل اردو ترجمہ — مولانا محمد داؤد راز رحمہ اللہ)", "dorar_aliases": ["صحيح البخاري"]},
    {"slug": "muslim", "hadeeth_book_id": 2, "ar_file": "ara-muslim.min.json", "ur_file": "urd-muslim.min.json", "title_ar": "صحيح مسلم", "title_ur": "صحیح مسلم (مکمل اردو ترجمہ — علامہ وحید الزماں / دارالسلام مراجعہ)", "dorar_aliases": ["صحيح مسلم"]},
    {"slug": "abudawud", "hadeeth_book_id": 3, "ar_file": "ara-abudawud.min.json", "ur_file": "urd-abudawud.min.json", "title_ar": "سنن أبي داود", "title_ur": "سنن ابی داؤد (مکمل اردو ترجمہ مع حکمِ البانی و زبیر علی زئی رحمہما اللہ)", "dorar_aliases": ["سنن أبي داود", "صحيح أبي داود", "ضعيف أبي داود", "تخريج سنن أبي داود"]},
    {"slug": "tirmidhi", "hadeeth_book_id": 4, "ar_file": "ara-tirmidhi.min.json", "ur_file": "urd-tirmidhi.min.json", "title_ar": "جامع الترمذي", "title_ur": "جامع الترمذی (مکمل اردو ترجمہ مع حکمِ البانی و زبیر علی زئی رحمہما اللہ)", "dorar_aliases": ["سنن الترمذي", "جامع الترمذي", "صحيح الترمذي", "ضعيف الترمذي", "تخريج سنن الترمذي"]},
    {"slug": "nasai", "hadeeth_book_id": 5, "ar_file": "ara-nasai.min.json", "ur_file": "urd-nasai.min.json", "title_ar": "سنن النسائي", "title_ur": "سنن النسائی (مکمل اردو ترجمہ مع حکمِ البانی و زبیر علی زئی رحمہما اللہ)", "dorar_aliases": ["سنن النسائي", "صحيح النسائي", "ضعيف النسائي"]},
    {"slug": "ibnmajah", "hadeeth_book_id": 6, "ar_file": "ara-ibnmajah.min.json", "ur_file": "urd-ibnmajah.min.json", "title_ar": "سنن ابن ماجه", "title_ur": "سنن ابن ماجہ (مکمل اردو ترجمہ مع حکمِ البانی و زبیر علی زئی رحمہما اللہ)", "dorar_aliases": ["سنن ابن ماجه", "سنن ابن ماجة", "صحيح ابن ماجه", "ضعيف ابن ماجه"]},
    {"slug": "malik", "hadeeth_book_id": 7, "ar_file": "ara-malik.min.json", "ur_file": "urd-malik.min.json", "title_ar": "موطأ مالك", "title_ur": "موطا امام مالک (مکمل اردو ترجمہ مع تخریج شیخ سلیم الہلالی)", "dorar_aliases": ["موطأ مالك", "الموطأ"]},
    {"slug": "nawawi", "hadeeth_book_id": 0, "ar_file": "ara-nawawi.min.json", "ur_file": "", "title_ar": "الأربعون النووية", "title_ur": "اربعینِ نووی (امام یحییٰ بن شرف النووی رحمہ اللہ)", "dorar_aliases": ["الأربعون النووية"]},
    {"slug": "qudsi", "hadeeth_book_id": 0, "ar_file": "ara-qudsi.min.json", "ur_file": "", "title_ar": "الأحاديث القدسية الأربعون", "title_ur": "اربعینِ احادیثِ قدسیہ", "dorar_aliases": []},
    {"slug": "dehlawi", "hadeeth_book_id": 0, "ar_file": "ara-dehlawi.min.json", "ur_file": "", "title_ar": "الأربعون للشاه ولي الله الدهلوي", "title_ur": "چہل حدیث (شاہ ولی اللہ محدث دہلوی رحمہ اللہ)", "dorar_aliases": []},
]
