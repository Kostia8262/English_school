# -*- coding: utf-8 -*-
"""Реєстр статей блогу.

Кожна стаття — окремий модуль art_*.py з єдиним словником ART. Так файл із
текстом однієї статті лишається читабельним, а додати наступну — це один рядок
тут. Перші десять статей писалися руками й лежать у blog/ як є; усе, що
з'явилося після 26.08.2026, збирається звідси.

Тексти пишуться за двома методичками з `Desktop/Инструкции для клода`:
humanize-guide і GEO-гайд. Головне правило звідти, яке не можна порушувати:
жодних вигаданих фактів, кейсів і цифр. Усе, що є числом, — або з брифу школи,
або позначена як оцінка, або арифметика, названа арифметикою.
"""
from __future__ import unicode_literals

from art_shkilna_anhliyska import ART as SHKILNA
from art_yak_obraty_shkolu import ART as OBRATY
from art_nosiy_movy import ART as NOSIY
from art_multyky_ta_ihry import ART as MULTYKY
from art_skilky_sliv import ART as SLOVA

ARTICLES = [
    SHKILNA,
    OBRATY,
    NOSIY,
    MULTYKY,
    SLOVA,
]
