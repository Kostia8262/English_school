# -*- coding: utf-8 -*-
"""Перелік країн у підвалі — в кілька колонок, з одного джерела.

Країн у серії стало 21, і рядок із переносом, на який підвал був розрахований
раніше, їх уже не тримає: посилання злипаються в суцільну стрічку, у якій
нічого не знайти. Тому тут сітка — дві колонки на телефоні, три на планшеті,
чотири на десктопі; 22 пункти лягають шістьма рядами.

Перелік один — `country_art.COUNTRIES`, — але розмітку треба дві: посадкові
сторінки носять українську в тексті й російську в `data-ru`, а шаблон головної
досі написаний директивами Alpine, які `tools/home/build.py` розгортає на
складанні. Звідси дві функції замість однієї; джерело даних у них спільне, тож
нова країна з'являється в обох підвалах одночасно.

Сортування — за українською абеткою, а не за `sorted()`: в Unicode «І», «Ї» та
«Є» стоять перед «А», і без власного ключа Ірландія з Іспанією опинялися б на
початку списку.
"""
from __future__ import unicode_literals

from country_art import COUNTRIES


# Українська абетка. Літери, яких тут немає (латиниця, цифри), сортуються після
# кирилиці — у назвах країн їх не буває, але хай поведінка буде визначена.
_ALPHABET = "абвгґдеєжзиіїйклмнопрстуфхцчшщьюя"
_ORDER = {ch: i for i, ch in enumerate(_ALPHABET)}


def _key(name):
    return [_ORDER.get(ch, len(_ALPHABET)) for ch in name.lower()]


def _sorted_countries():
    return sorted(COUNTRIES, key=lambda row: _key(row[1]))


# Сітка, а не `flex-wrap`: колонки вирівнюють початки слів, і оком видно, що
# перелік упорядкований за абеткою.
_UL_CLASS = ("grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 "
             "gap-x-6 gap-y-2 text-base")

_A_CLASS = "hover:text-fox-400 transition-colors duration-200"

_ALL_UK, _ALL_RU = "Усі країни", "Все страны"
_ALL_SLUG = "anhliyska-dlya-ditey-za-kordonom"


def html_data_ru():
    """Розмітка для посадкових: текст українською, російська в `data-ru`."""
    rows = list(_sorted_countries()) + [(_ALL_SLUG, _ALL_UK, _ALL_RU)]
    out = ['        <ul class="%s">' % _UL_CLASS]
    for slug, uk, ru in rows:
        out.append(
            '          <li><a href="/%s" class="%s" data-ru="%s">%s</a></li>'
            % (slug, _A_CLASS, ru, uk))
    out.append('        </ul>')
    return "\n".join(out)


def html_alpine():
    """Розмітка для шаблону головної: директиви Alpine, які розгортає build.py."""
    rows = list(_sorted_countries()) + [(_ALL_SLUG, _ALL_UK, _ALL_RU)]
    a_class = "hover:text-fox-400 transition-colors"
    out = ['            <ul class="%s">' % _UL_CLASS]
    for slug, uk, ru in rows:
        out.append(
            '                <li><a :href="lang===\'ru\'?\'/%s?lang=ru\':\'/%s\'"'
            ' class="%s" x-text="lang===\'uk\'?\'%s\':\'%s\'">%s</a></li>'
            % (slug, slug, a_class, uk, ru, uk))
    out.append('            </ul>')
    return "\n".join(out)
