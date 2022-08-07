#!/usr/bin/python3

from TanyaSkynet import *


if __name__ == '__main__':
    speaker = gTTSSpeaker('ru') # Инициализация спикера
    app = Application() # Инициализация приложения
    
    app.accept_rules = ( # Правила обработки обращения к помошнику
        r'^\s*\bТан(?:я|юша|ечка)\b',
        r'^\s*\bТатьян(?:а|очка)\b',
        r'^\s*\b(OK\s+)?Google\b'
    )
    app.actions = ( # Действия для помошника и условия их вызова
        RegExpEvent(
            regexp=(
                r'\bнай(?:ди|ти)\b.*\bgoogle\b',
                r'\bпои(?:ск|щи)\b.*\bgoogle\b',
                r'\bgoogle\b.*\bнай(?:ди|ти)\b',
                r'\bgoogle\b.*\bпои(?:ск|щи)\b'
            )
        ).action(GoogleSearchAction()),
        RegExpEvent(
            regexp=(
                r'\bнай(?:ди|ти)\b.*\b(?:yandex|яндексе?)\b',
                r'\bпои(?:ск|щи)\b.*\b(?:yandex|яндексе?)\b',
                r'\b(?:yandex|яндексе?)\b.*\bнай(?:ди|ти)\b',
                r'\b(?:yandex|яндексе?)\b.*\bпои(?:ск|щи)\b'
            )
        ).action(YandexSearchAction()),
        RegExpEvent(
            regexp=(
                r'\bнай(?:ди|ти)\b',
                r'\bпои(?:ск|щи)\b'
            )
        ).action(GoogleSearchAction()),
        RegExpEvent(
            regexp=(
                r'\bпогода\b',
                r'\bпрогноз\b'
            )
        ).action(WeatherAction( 
            speak_message_weather=VoiceMessage(speaker),
            speak_message_error=VoiceMessage(speaker, 'Ошибка при обновлении сведений о погоде. Попробуйте еще раз.')
        )),
        RegExpEvent(
            regexp=(
                r'\b(?:скажи|повтори)\b',
            )
        ).action(SpeakAction(speaker=speaker)),
        RegExpEvent(
            regexp=(
                r'\b(?:выход|закройся)\b',
            )
        ).action(ExitAction()),
        AlwaysEvent().action(FallbackAction(speak_message=VoiceMessage(speaker, 'Не понятно. Попробуйте еще раз.')))
    )
    
    app.start()
    
    