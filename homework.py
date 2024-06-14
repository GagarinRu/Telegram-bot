import logging
import os
import time
from http import HTTPStatus
from logging.handlers import RotatingFileHandler

import requests
from dotenv import load_dotenv
from telebot import TeleBot

from constans import RETRY_PERIOD, ENDPOINT, HOMEWORK_VERDICTS, HEADERS
from exception import InvalidResponseCode

load_dotenv()

PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
handler = RotatingFileHandler(
    __file__ + '.log',
    maxBytes=50000000,
    backupCount=5,
    encoding='UTF-8'
)

logger.addHandler(handler)
formatter = logging.Formatter(
    '%(asctime)s, %(levelname)s, line %(lineno)s, '
    'in %(funcName)s, %(message)s'
)
handler.setFormatter(formatter)
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
console_handler.setFormatter(formatter)
logger.addHandler(console_handler)


def check_tokens():
    """Доступность переменных окружения."""
    variables = (
        ('PRACTICUM_TOKEN', PRACTICUM_TOKEN),
        ('TELEGRAM_TOKEN', TELEGRAM_TOKEN),
        ('TELEGRAM_CHAT_ID', TELEGRAM_CHAT_ID)
    )
    check_bool = True
    for name, token in variables:
        if not token:
            check_bool = False
            logger.critical(f'Отсутствует {name}.')
    if check_bool is False:
        raise KeyError('Не найден токен.')


def send_message(bot, message):
    """Извлекает информацию о конкретной домашней работе статус этой работы."""
    try:
        bot.send_message(
            chat_id=TELEGRAM_CHAT_ID,
            text=message
        )
    except Exception as error:
        logger.error(f'Ошибка {error}.{message}.')
        return False
    logging.debug(f'Бот отправил сообщение: "{message}')
    return True


def get_api_answer(timestamp):
    """Запрос к URL API-сервиса."""
    payload = {'from_date': timestamp}
    requests_variables = {
        'url': ENDPOINT,
        'headers': HEADERS,
        'params': payload
    }
    logger.info(
        'Запрос: {url}, {headers}, {params}'
        .format(**requests_variables)
    )
    try:
        response = requests.get(**requests_variables)
    except requests.RequestException as error:
        raise ConnectionError(
            'Ошибка при запросе к API: {error}.'
            'Данные:{url}, {headers}, {params}'
            .format(**requests_variables, error=error)
        )
    if response.status_code != HTTPStatus.OK:
        raise InvalidResponseCode(
            f'Код запроса: {response.status_code}'
            f'Описание кода запроса: {response.reason}'
            f'Текст кода: {response.text}'
        )
    logger.info(f'Отправка запроса {response}.')
    return response.json()


def check_response(response):
    """Соответствие документации ответа API."""
    if not isinstance(response, dict):
        raise TypeError('Тип данных ответа API не соответствуют документации.')
    if 'homeworks' not in response:
        raise KeyError('Данные отсутствуют при ответе API.')
    homeworks = response['homeworks']
    if not isinstance(homeworks, list):
        raise TypeError(
            'Тип данных ответа API не соответствуют документации.'
        )
    return homeworks


def parse_status(homework):
    """Извлечение информации о статусе последней работы."""
    logger.info(f'Полученные данные последней домашней работы: {homework}.')
    if 'status' not in homework or 'homework_name' not in homework:
        raise KeyError(
            'Данные(status, homework_name) последней домашней работы '
            'отсутствуют в homework.')
    homework_name = homework['homework_name']
    status_work = homework['status']
    if status_work not in HOMEWORK_VERDICTS:
        raise ValueError(f'Неизвестный статус работы: {status_work}.')
    verdict = HOMEWORK_VERDICTS[status_work]
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Основная логика работы бота."""
    check_tokens()
    timestamp = int(time.time())
    bot = TeleBot(token=TELEGRAM_TOKEN)
    last_status = ''
    while True:
        try:
            response = get_api_answer(timestamp)
            logger.info('Запрос API оттправлен')
            homeworks = check_response(response)
            if not homeworks:
                logging.debug('Список homeworks пустой.')
                continue
            current_work = response['homeworks'][0]
            verdict = parse_status(current_work)
            if last_status != verdict and send_message(bot, verdict):
                last_status = verdict
                timestamp = response.get('current_date', timestamp)
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            logger.error(f'{message}')
            if last_status != message and send_message(bot, message):
                last_status = message
        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
