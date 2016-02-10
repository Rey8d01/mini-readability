#!/usr/bin/env python3.5
"""Mini readability.

Имеется необходимость вытаскивать полезный контент из веб документов (без реклам и меню навигации) и представлять его в виде
текстового файла для чтения. Форматирование текстовых документов имеет определенные правила и может настраиваться
в отдельном файле конфигурации. Результирующий файл необходимо сохранять на диске в определенной директории
относительно текущего расположения программы в поддиректориях. Имена поддиректорий должны соответствовать сегментам урла
заданного веб документа.

"""
import json  # Используется для парсинга файла конфигурации.
import urllib.request  # Используется для получения веб документов.
import urllib.parse  # Используется для парсинга пути веб документа для формирования пути сохранения результирующего файла.
import textwrap  # Используется для переноса слов.
import os  # Используется для файловых операций и создания директорий.
import sys  # Используется для чтения параметров командной строки.
from html.parser import HTMLParser  # Основной класс наследник которого будет осуществлять обработку сырого веб документа.

# Стандартный набор настроек для приложения.
DEFAULT_CONFIG = {
    # Список разрешенных вложенных в основной блок контента тегов.
    "list_allow_nested_tags": ["p", "a", "b", "i", "u", "span"],
    # Основной тег для заголовка.
    "title_tag": "h1",
    # Атрибуты для основного тега заголовка.
    "title_tag_attributes": {},
    # Основной тег контента.
    "content_tag": "p",
    # Атрибуты для основного тега с контентом.
    "content_tag_attributes": {},
    # Основной тег параграфа, который разделяет контент на абзацы.
    "paragraph_tag": "p",
    # Максимальное количество символов в строке, при превышении которого текст будет переноситься на следующую строку по словам.
    "word_wrap_column": 80,
    # Настройки шаблона для определенных тегов.
    "template_tags": {
        "a": {
            # _data_ определяет шаблон для содержимого тега.
            "_data_": "%s",
            # Шаблоны для определенных атрибутов.
            "href": "[%s]",
        },
        "b": {
            "_data_": "**%s**",
        },
    },
    # Список хостов для которых будет действовать конфиг или True для всех сайтов.
    "hosts": True
}


class ExtractorContent(HTMLParser):
    """Парсер html страниц, который извлекает основной контент из них.

    Является наследником HTMLParser и наследует основные методы которые выполняются во время парсинга страницы.

    :type _title_tag: str
    :type _title_tag_attributes: str
    :type _content_tag: str
    :type _content_tag_attributes: str
    :type _paragraph_tag: str
    :type _list_allow_nested_tags: list
    :type _word_wrap_column: int
    :type _template_tags: dict
    :type _title: bool|str Заголовок страницы.
    :type _context: list Стек вложенных тегов, заполняется и очищается по мере парсинга страницы.
    :type _paragraph: list Текущий параграф с полезной информацией.
    :type _content: list Общий список параграфов с полезной информацией.
    :type _state_paragraph: bool Состояние параграфа, которое свидетельствует о парсинге элементов с полезным контентом в данный момент.
    """
    _title_tag = None
    _title_tag_attributes = None
    _content_tag = None
    _content_tag_attributes = None
    _paragraph_tag = None
    _list_allow_nested_tags = None
    _word_wrap_column = None
    _template_tags = None

    _title = False
    _context = None
    _paragraph = None
    _content = None
    _state_paragraph = False

    def __init__(self, **kwargs):
        super().__init__()

        # Фиксирование параметров конфигурации для парсинга страницы.
        self._title_tag = kwargs["title_tag"]
        self._title_tag_attributes = kwargs["title_tag_attributes"]
        self._content_tag = kwargs["content_tag"]
        self._content_tag_attributes = kwargs["content_tag_attributes"]
        self._paragraph_tag = kwargs["paragraph_tag"]
        self._list_allow_nested_tags = kwargs["list_allow_nested_tags"]
        self._word_wrap_column = kwargs["word_wrap_column"]
        self._template_tags = kwargs["template_tags"]

        self._context = []
        self._paragraph = []
        self._content = []

    def get_text_content(self) -> str:
        """Сборка контента в единый строковый вид после парсинга всей страницы.

        :return: Отформатированный текст готовый к сохранению.
        """
        content = []
        for paragraph in self._content:
            content.append(''.join(paragraph))

        text = self._title + "\n\n"
        for paragraph in content:
            text += "\n".join(textwrap.wrap(paragraph, self._word_wrap_column)) + "\n\n"
        return text

    def set_state_paragraph(self, tag: str, attrs: tuple):
        """Установка состояния параграфа. В активном (True) состоянии происходит запись в параграф.

        Активность параграфа определяется соответствием основного тега, который должен содержать контент и его атрибутов
        заданным значениям в настройках.

        """
        if not self._state_paragraph:
            # В рамках активного состояния параграфа (когда при парсинге происходит запись содержимого) при прохождении
            # вглубь html документа изменения состояния не происходит. Поэтому состояние параграфа будет меняться только в случае
            # если до этого его значение было False.
            dict_attrs = dict(attrs)
            if tag == self._content_tag:
                state_paragraph = True
                for tag_attr in self._content_tag_attributes:
                    if (tag_attr in dict_attrs) and (dict_attrs[tag_attr] == self._content_tag_attributes[tag_attr]):
                        state_paragraph = state_paragraph and True
                    else:
                        state_paragraph = False

                self._state_paragraph = state_paragraph

        if self._state_paragraph:
            # Запись тегов в контекст происходит только в активном состоянии параграфа.
            self._context.append(tag)

    def unset_paragraph_context(self):
        """Сброс состояния параграфа.

        Запись полезного контента в параграф прекращается в процессе парсинга документа, когда из контекста тегов, содержащих в себе
        полезную информацию, удаляется последний тег.

        """
        if self._state_paragraph:
            self._context.pop()
            if len(self._context) == 0:
                self._state_paragraph = False

    def handle_starttag(self, tag: str, attrs: tuple):
        """Метод срабатывает на этапе парсинга открывающего тега."""
        self.set_state_paragraph(tag, attrs)
        dict_attrs = dict(attrs)
        if self._state_paragraph:
            # Если тег относиться к тому, в котором содержиться информация требующая определенной обработки,
            # то информация в нем попадает в параграф.
            if tag in self._template_tags:
                # Если тег относиться к списку тегов с индивидуальными шаблонами, то в зависимости от
                # заданных настроек оформления, к атрибутам будут применен свой шаблон.
                for attribute in self._template_tags[tag]:
                    attribute_value = dict_attrs[attribute] if attribute in dict_attrs else False
                    if attribute_value:
                        # В параграф заноситься данные с индивидуальным шаблоном.
                        parse_attribute_value = self._template_tags[tag][attribute] % attribute_value
                        self._paragraph.append(parse_attribute_value)

        # Фиксируем необходимость записи заголовка.
        if (self._title is False) and (tag == self._title_tag):
            # Операция по сохранению состояния заголовка схожа с состоянием параграфа, но тут решил немного сэкономить на переменных.
            state_title = True
            for tag_attr in self._title_tag_attributes:
                if (tag_attr in dict_attrs) and (dict_attrs[tag_attr] == self._title_tag_attributes[tag_attr]):
                    state_title = state_title and True
                else:
                    state_title = False
            self._title = state_title

    def handle_data(self, data: str):
        """Метод срабатывает на этапе парсинга содержимого между тегами."""
        tag = self._context[-1] if len(self._context) > 0 else None
        if self._state_paragraph and (tag in self._list_allow_nested_tags):
            # Заносим информацию в параграф в том случае если контекст парсинга находиться в пределах области тега в котором содержится
            # полезная информация.
            if (tag in self._template_tags) and ("_data_" in self._template_tags[tag]):
                parse_attribute_value = self._template_tags[tag]["_data_"] % data
                self._paragraph.append(parse_attribute_value)
            else:
                self._paragraph.append(data)

        if self._title is True:
            self._title = data

    def handle_endtag(self, tag: str):
        """Метод срабатывает на этапе парсинга закрывающего тега."""
        # Удаляем из контекста тегов последний тег.
        self.unset_paragraph_context()
        if (len(self._paragraph) > 0) and (tag == self._paragraph_tag):
            # Если закрывается тег в рамках которого осуществляется сборка контента то накопленную информацию из параграфа сохраняем
            # в отдельном элементе общего списка отобранного контента, для последующего слияния.
            self._content.append(self._paragraph)
            self._paragraph = []


class KeeperContent:
    """Основной класс для сохранения обработанного контента согласно определенным в конфиге параметрам.

    :type _config: dict Набор конфигураций для парсинга сайтов.
    """

    _config = None

    def __init__(self, config: list):
        self._config = config.copy()

    def get_template_by_hostname(self, hostname: str) -> dict:
        """Вернет подходящий шаблон для парсинга в зависимости от урла.

        Если подходящий шаблон не был найден, будет использоваться стандартный набор параметров для обработки html страницы.
        Все параметры найденного шаблона будут слиты со стандартным, заменяя старые значения новыми и оставляя неизменными те,
        которые не были определены

        :param hostname: Адрес сайта, без http:// и последнего /
        :return: Настройки для шаблона.
        """
        for config in self._config:
            if ("hosts" in config) and ((config["hosts"] == True) or (hostname in config["hosts"])):
                return {**DEFAULT_CONFIG, **config.copy()}
        return DEFAULT_CONFIG

    def get_content_by_url(self, url: str) -> str:
        """Вернет распарсенный контент извлеченный из указанного урла.

        Подбирает подходящий шаблон обработки страницы и передает его в парсер, который извлечет нужную информацию и вернет ее в метод.
        Метод используется в основном для получения извлеченной информации из страницы и передачи ее в другие методы,
        которые будут осуществлять сохранение этого контента.

        :param url: Адрес страницы которую требуется распарсить и сохранить из нее контент.
        :return: Готовый к сохранению контент страницы.
        """
        hostname = urllib.parse.urlparse(url).hostname
        request = urllib.request.urlopen(url)
        # Попытка чтения страницы.
        try:
            # Приведение оригинальной кодировки страницы к правильному строковому виду.
            html = request.read().decode(request.info().get_charsets()[-1])
        except Exception:
            # В случае возникновения проблем с получением страницы или с преобразованием кодировки просто прервем работу.
            return ''

        extractor = ExtractorContent(**self.get_template_by_hostname(hostname))
        extractor.feed(html)
        extractor.close()
        return extractor.get_text_content()


class FileKeeperContent(KeeperContent):
    """Класс для сохранения результатов извлечения контента в файл с сохранением структуры сегментов урла."""

    def keep_content_by_url(self, url: str) -> bool:
        """Сохранение контента полученного из определенного урла в файл.

        :param url: Адрес страницы которую требуется распарсить и сохранить из нее контент.
        :return: Вернет True если сохранение прошло успешно или False если сохранить контент не удалось по каким то причинам.
        """
        content = self.get_content_by_url(url)
        if content == '':
            return False

        try:
            # Парсинг урла для определения места сохранения.
            result_parse = urllib.parse.urlparse(url)
            hostname = result_parse.hostname
            path = result_parse.path
            if path[-1] == "/":
                path = path[0:-1]
            path_items = path.split('/')

            # Получение конечного имени файла (исходя из последнего сегмента урла или расширения файла в урле).
            source_name = path_items[-1]
            file_name = source_name
            source_name_items = source_name.split('.')
            if len(source_name_items) > 1:
                file_name = '.'.join(source_name_items[0:-1])
            file_name += '.txt'

            # Формирование пути сохранения файла.
            relative_path = hostname + "/" + "/".join(path_items[1:-1])
            if not os.path.exists(relative_path):
                os.makedirs(relative_path)

            # Запись в файл полученного контента.
            f = open(relative_path + "/" + file_name, 'w', encoding='utf-8')
            f.write(content)
            f.close()
        except Exception:
            return False

        return True


if __name__ == "__main__":
    # Чтение файла с конфигурацией в котором хранятся индивидуальные настройки для парсинга различных сайтов.
    try:
        f = open("config.json")
        custom_config = json.load(f)
    except Exception:
        # В случае проблем с чтением настроек из файла, оставим пустые настройки.
        custom_config = []

    keeper = FileKeeperContent(custom_config)
    if (len(sys.argv) > 1) and keeper.keep_content_by_url(sys.argv[1]):
        print("Материал сохранен")
    else:
        print("В процессе обработки материала произошли ошибки")
