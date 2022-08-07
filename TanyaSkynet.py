#!/usr/bin/python3
# Строка для bash, содержащая приложение, в которое будет передан скрипт для исполнения

__version__ = "1.0.1"

# Импорт библиотек
try:
    import re
    import io
    import webbrowser
    from xml.etree import ElementTree
except ImportError as exception:
    print('{}: Отсутствует системный модуль: "{}"'.format(__name__, exception.name))
    raise exception

try:
    import gtts
    import requests
    from pydub import AudioSegment
    from pydub.playback import play as pydub_play
    import speech_recognition
    import urllib.parse
except ImportError as exception:
    module_names = {
        'speech_recognition': 'SpeechRecognition',
        'urllib': 'urllib3'
    }
    module_real_name = exception.name
    if exception.name in module_names.keys():
        module_real_name = module_names[exception.name]
    print('{}: Отсутствует модуль: "{}". Установите его одной из следующих команд:'.format(__name__, exception.name))
    print('pip install {}'.format(module_real_name))
    print('python -m pip install {}'.format(module_real_name))
    print()
    raise exception

# Абстрактное событие
class Event:
    # Использующиеся параметры класса
    __slots__ = ['data_args', 'data_kwargs', 'action_list']
    
    # Конструктор класса
    def __init__(self, *args, **kwargs):
        self.data_args = list(args)
        self.data_kwargs = dict(kwargs)
        self.action_list = []
    
    # Добавление события для обработки
    # Возвращает объект, что позволяет создавать цепочки: obj.action(...).action(...).action(...)
    def action(self, action:callable, **kwargs):
        if not callable(action):
            return False
        self.action_list.append([action, kwargs])
        return self
        
    # Функция обработки условий инициирования события, переопределяется
    # Результат - [Событие подходет для параметров], [*args], [**kwargs]
    def _process(self, call_args, call_kwargs, data_args, data_kwargs):
        return False, [], {
            'event': self,
            '_call_args': call_args,
            '_call_kwargs': call_kwargs,
            '_data_args': data_args,
            '_data_kwargs': data_kwargs,
        }
    
    # Вызов события
    def __call__(self, *args, **kwargs):
        process_status, process_value_args, process_value_kwargs = self._process(
            call_args=args,
            call_kwargs=kwargs,
            data_args=self.data_args,
            data_kwargs=self.data_kwargs
        )
        if process_status:
            for action in self.action_list:
                action[0](*process_value_args, **process_value_kwargs)
        return process_status

# Событие, срабатывающее всегда
class AlwaysEvent(Event):
    __slots__ = []
    # Событие возникает всегда, при любых параметрах
    def _process(self, call_args, call_kwargs, data_args, data_kwargs):
        _, _, process_value_kwargs = super()._process(
            call_args=call_args,
            call_kwargs=call_kwargs,
            data_args=data_args,
            data_kwargs=data_kwargs
        )
        return True, [], process_value_kwargs
        
# Событие при нахождении подстроки по регулярному выражению
class RegExpEvent(Event):
    __slots__ = []
    # Событие возникает только если имеется хотя бы одно совпадение в имеющихся шаблонах
    def _process(self, call_args, call_kwargs, data_args, data_kwargs):
        if 'text' not in call_kwargs or not isinstance(call_kwargs['text'], str):
            return False, [], {}
        if 'regexp' not in data_kwargs or not (isinstance(data_kwargs['regexp'], list) or isinstance(data_kwargs['regexp'], tuple)):
            return False, [], {}
        re_flags = re.IGNORECASE # По умолчанию - игнорирование регистра
        if 'regexp_flags' in data_kwargs:
            re_flags = data_kwargs['regexp_flags']
        for regexp_item in data_kwargs['regexp']:
            match = re.search(regexp_item, call_kwargs['text'], re_flags)
            if match is not None:
                _, _, process_value_kwargs = super()._process(
                    call_args=call_args,
                    call_kwargs=call_kwargs,
                    data_args=data_args,
                    data_kwargs=data_kwargs
                )
                process_value_kwargs.update({
                    'text': call_kwargs['text'],
                    'regexp_item': regexp_item,
                    'regexp_match': match
                })
                return True, [], process_value_kwargs
        return super()._process(
            call_args=call_args,
            call_kwargs=call_kwargs,
            data_args=data_args,
            data_kwargs=data_kwargs
        )
    
    # Функция, возвращает запрос пользователя без шаблона
    def _get_user_text_without_search(self, action, args, kwargs):
        return re.sub(
            '\s+',
            ' ',
            re.sub(
                kwargs['regexp_item'],
                '', 
                action._get_user_text(),
                count=1,
                flags=re.IGNORECASE
            )
       ).strip()

# Абстрактное действие
class Action:
    __slots__ = ['data_args', 'data_kwargs', 'call_args', 'call_kwargs']
    def __init__(self, *args, **kwargs):
        self.data_args = list(args)
        self.data_kwargs = dict(kwargs)
        self.call_args = None
        self.call_kwargs = None
    
    # Вызов события, сохраняем аргументы
    def __call__(self, *args, **kwargs):
        self.call_args = args
        self.call_kwargs = kwargs
        self._process()
    
    # Функция обработки события, переопределяется
    def _process(self):
        pass
    
    # Возвращает текст, введенный пользователем (ключ "text" параметров, если отсутствует - ключ "text" базовых параметров) 
    def _get_user_text(self):
        if 'text' in self.call_kwargs:
            return self.call_kwargs['text']
        elif 'text' in self.call_kwargs['_call_kwargs']:
            return self.call_kwargs['_call_kwargs']['text']
        return None
    
    # Возвращает текст, введенный пользователем, за исключение фразы, совпадающей с регулярным выражением
    def _get_user_text_without_search(self):
        user_text = self._get_user_text()
        if hasattr(self.call_kwargs['event'], '_get_user_text_without_search'):
            user_text = self.call_kwargs['event']._get_user_text_without_search(self, self.call_args, self.call_kwargs)
        return user_text

# Действие для отладки - выводит состояние
class TestAction(Action):
    __slots__ = []
    def _process(self):
        print(self.call_args, self.call_kwargs, self.data_args, self.data_kwargs)

# Выход из программы
class ExitAction(Action):
    __slots__ = []
    def _process(self):
        print('Выход...')
        exit()

# Действие при ошибке распознавания
class FallbackAction(Action):
    __slots__ = []
    def _process(self):
        print('Ошибка распознавания, входные данные: "{}"'.format(self._get_user_text()))
        if 'speak_message' in self.data_kwargs:
            self.data_kwargs['speak_message']()

# Действие для воспроизведения текста
class SpeakAction(Action):
    __slots__ = []
    def _process(self):
        user_text = self._get_user_text_without_search()
        print('Говорю: "{}"'.format(user_text.strip()))
        if 'speaker' in self.data_kwargs:
            self.data_kwargs['speaker'].play(user_text)

# Действие для получения и вывода прогноза погоды
class WeatherAction(Action):
    __slots__ = []
    def _process(self):
        city_id = 4368 # Идентификатор города, по умолчанию - 4368 (Россия, Москва)
        if 'city' in self.data_kwargs and int(self.data_kwargs['city']):
            city_id = int(self.data_kwargs['city'])
        response = requests.get(
            r'http://2c527f91.services.gismeteo.ru/inform-service/3ee0e2ab46f729161fbc8d6200e99fcf/forecast/',
            params={
                'city': city_id,
                'all_langs': '1',
                'ver': '1.0.0.0'
            }
        )
        if response.status_code != 200:
            if 'speak_message_error' in self.data_kwargs:
                self.data_kwargs['speak_message_error']()
            return False
        response.raw.decode_content = True # Декодировать до уровня RAW, убрать возможно сжатие
        location = ElementTree.ElementTree(ElementTree.fromstring(response.content)).getroot().find('location') # Парсинг XML, получение XML элемента location
        location_fact = location.find('fact').find('values')  # Получение XML элементов fact>values
        
        infp = 'Сейчас {} {}'.format(location.attrib['name_r_ru'], location_fact.attrib['descr_ru']) # Получение атрибутов XML элементов
        print('Прогноз погоды: {}'.format(infp))
        if 'speak_message_weather' in self.data_kwargs:
            self.data_kwargs['speak_message_weather'](infp)

# Действие для поиска в абстрактной поисковой системе
class SearchAction(Action):
    __slots__ = []
    # Открыть URL в браузере, по возможности в новой вкладке
    def _search_open(self, url):
        webbrowser.open_new_tab(url)
    # Открыть URL в браузере, экранировать и вставить подстроку в URL
    def _search_text(self, urlmask, text):
        self._search_open(urlmask.format(urllib.parse.quote(text)))
    def _process(self):
        pass

# Действие для поиска в Google
class GoogleSearchAction(SearchAction):
    __slots__ = []
    def _process(self):
        user_text = self._get_user_text_without_search()
        print('Поиск в Google: {}'.format(user_text.strip()))
        self._search_text('https://www.google.com/search?q={}', user_text)

# Действие для поиска в Яндекс
class YandexSearchAction(SearchAction):
    __slots__ = []
    def _process(self, *args, **kwargs):
        user_text = self._get_user_text_without_search()
        print('Поиск в Яндекс: {}'.format(user_text.strip()))
        self._search_text('https://yandex.ru/search/?text={}', user_text)

# Драйвер устройства вывода текста
class Speaker:
    __slots__ = ['lang']
    def __init__(self, lang='ru'):
        self.lang = lang
    # Воспроизвести текст
    def play(self, text):
        pass
    # Сохранить текст в файл
    def file(self, text, file):
        pass

# Драйвер устройства ввода
class gTTSSpeaker(Speaker):
    __slots__ = []
    def play(self, text):
        mp3_handler = io.BytesIO() # Получение потока для массива байтов
        gtts.gTTS(text, lang=self.lang).write_to_fp(mp3_handler) # Синтез речи и вывод его в созданный поток
        mp3_handler.seek(0) # Установка указателя на первый символ потока
        speak_audio = AudioSegment.from_file(mp3_handler, format='mp3') # Получение объекта для воспроизведение
        pydub_play(speak_audio) # Воспроизведение
    def file(self, text, file):
        gtts.gTTS(text, lang=self.lang).save(file) # Синтез речи и сохранение в файл

# Класс для вывода голосовых сообщений
class VoiceMessage:
    __slots__ = ['speaker', 'data_args', 'data_kwargs', 'allow_replace']
    def __init__(self, speaker: Speaker, *args, **kwargs):
        self.speaker = speaker
        self.data_args = args
        self.data_kwargs = kwargs
        self.allow_replace = True
    
    # Вызов - проигрывание голосового сообщения
    def __call__(self, *args, **kwargs):
        data_args = self.data_args
        data_kwargs = self.data_kwargs
        if self.allow_replace and (len(args) or len(kwargs)): # Если переданы параметры, используем их
            data_args = args
            data_kwargs = kwargs
        if not len(data_args) and not len(data_kwargs): # Если данных для воспроизведения нет - выбрасываем исключение
            raise Exception('Нет данных для воспроизведения')
        self.speaker.play(*data_args, **data_kwargs) # Проигрываем данные

# Абстрактный слушатель
class Listener:
    __slots__ = [
        'language',
        'source',
        'source_args',
        'source_kwargs'
    ]
    def __init__(self, language:str='ru-RU', source:str='google'):
        self.language = language
        self.source = source
        self.source_args = []
        self.source_kwargs = {}
    # Функция распознавания текста с микрофона
    def recognize(self):
        return None
    
class SpeechRecognitionListener(Listener):
    __slots__ = [
        'recognition',
        'recognition_microphone',
        'callback_recognize_init',
        'callback_recognize_listen',
        'callback_recognize_wait'
    ]
    def __init__(self, language:str='ru-RU', source:str='google'):
        super().__init__(language, source) # Вызов конструктора родителя класса
        self.recognition = speech_recognition.Recognizer()
        self.recognition_microphone = speech_recognition.Microphone()
        self.callback_recognize_init = None
        self.callback_recognize_listen = None
        self.callback_recognize_wait = None
        with self.recognition_microphone as audio_stream: # Работа с микрофоном
            self.recognition.adjust_for_ambient_noise(audio_stream, duration=2.0) # Настройка для определения посторонних шумов. Параметр "duration" отвечает за длительность
    
    def recognize(self):
        # Если не существует свойство объекта (т.е., если такой источник не существует) - выход
        if not hasattr(self.recognition, 'recognize_{}'.format(self.source)):
            return None
        if self.callback_recognize_init is not None and callable(self.callback_recognize_init):
            self.callback_recognize_init() # Обработка callback'ов
        with self.recognition_microphone as audio_stream: # Работа с микрофоном
            if self.callback_recognize_listen is not None and callable(self.callback_recognize_listen):
                self.callback_recognize_listen() # Обработка callback'ов
            audio = self.recognition.listen(audio_stream) # Прослушивание с микрофона до окончания речи
            if self.callback_recognize_wait is not None and callable(self.callback_recognize_wait):
                self.callback_recognize_wait() # Обработка callback'ов
            try:
                return getattr(self.recognition, 'recognize_{}'.format(self.source))( # Вызов ф-ии распознавания речи сервиса, передача аргументов
                    audio, language=self.language, *self.source_args, **self.source_kwargs
                )
            except speech_recognition.UnknownValueError:
                return None

class Application:
    __slots__ = [
        'actions',
        'accept_rules'
    ]
    
    # Функция для определения допустимости сообщения (т.е., обращаются ли к нам)
    # Результат: [Обращение: bool], [Сообщение: str]
    def _is_accept_message(self, message:str):
        for accept_rule in self.accept_rules:
            match = re.search(accept_rule, message, re.IGNORECASE)
            if match is not None:
                return True, message[(match.end() + 1):]
        return False, None
    
    # Функция для вывода сообщения
    @staticmethod
    def _recognize_print_before():
        print('Говорите...')

    # Функция запуска приложения - глобальная обработка исключений
    def start(self, *args, **kwargs):
        try:
            return self._begin(*args, **kwargs)
        except KeyboardInterrupt:
            print('Прервано пользователем, выход...')
    
    # Функция приложения
    def _begin(self):
        print('Запуск приложения... Пожалуйста, подождите.')
        listener = SpeechRecognitionListener() # Работа с микрофоном
        listener.callback_recognize_listen = self._recognize_print_before # Установка callback'ов
        while True: # Бсконечный цикл
            user_text = listener.recognize() # Прослушивание и распознавание текста
            if user_text is None:
                continue
            message_accept, message = self._is_accept_message(user_text) # Определение допустимости распознавания
            if message is not None and len(message):
                for action in self.actions: # Обработка действий
                    if action(text=message):
                        break
            else:
                print('Адресовано не мне, игнорирую...')

__all__ = [
    'Event',
    'AlwaysEvent',
    'RegExpEvent',
    'Action',
    'TestAction',
    'ExitAction',
    'FallbackAction',
    'SpeakAction',
    'WeatherAction',
    'SearchAction',
    'GoogleSearchAction',
    'YandexSearchAction',
    'Speaker',
    'gTTSSpeaker',
    'VoiceMessage',
    'Listener',
    'SpeechRecognitionListener',
    'Application'
]

