import logging
import os
import time
from http import HTTPStatus

import requests
from dotenv import load_dotenv
from logging.handlers import RotatingFileHandler
from telebot import TeleBot

from constans import RETRY_PERIOD, ENDPOINT, HOMEWORK_VERDICTS, HEADERS


load_dotenv()

PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
handler = RotatingFileHandler(
    'my_logger.log',
    maxBytes=50000000,
    backupCount=5,
    encoding='UTF-8'
)
logger.addHandler(handler)
formatter = logging.Formatter(
    '%(asctime)s - %(levelname)s - %(message)s'
)
handler.setFormatter(formatter)


def check_tokens():
    """Доступность переменных окружения."""
    variables = (PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID)
    logger.info(f'токены: {variables}')
    if None in variables:
        logger.critical('Отсутствует токен.')
        raise KeyError('Не найден токен.')


def send_message(bot, message):
    """Извлекает информацию о конкретной домашней работе статус этой работы."""
    try:
        bot.send_message(
            chat_id=TELEGRAM_CHAT_ID,
            text=message
        )
        logging.debug(f'Бот отправил сообщение: "{message}')
    except Exception as error:
        logger.error(f'Ошибка {error}.Сбой в отправке сообщения:{message}.')
        raise RuntimeError(
            'Ошибка {error}.Сбой в отправки сообщения:{message}.'
        )


def get_api_answer(timestamp):
    """Запрос к URL API-сервиса."""
    try:
        payload = {'from_date': timestamp}
        logger.info(f'Запрос: {ENDPOINT}, {HEADERS}, {payload}')
        response = requests.get(
            ENDPOINT,
            headers=HEADERS,
            params=payload
        )
        logger.info(f'Отправка запроса {response}.')
    except Exception as error:
        logger.error(f'Ошибка при запросе к API: {error}.')
    if response.status_code != HTTPStatus.OK:
        logger.error(f'Код запроса {ENDPOINT} не 200.')
        raise ValueError(f'{ENDPOINT} ошибка.')
    return response.json()


def check_response(response):
    """Соответствие документации ответа API."""
    check_list = (
        ('homeworks', list),
        ('current_date', int)
    )
    logger.info(f'Полученные данные: {response}.')
    if not isinstance(response, dict):
        logger.error('Ошибка типа данных при запросе к API.')
        raise TypeError('Тип данных ответа API не соответствуют документации.')
    for count, type in check_list:
        if count not in response:
            logger.error(f'Ошибка наличия {count} при запросе к API.')
            raise KeyError('Данные отсутствуют при ответе API.')
        elif not isinstance(response[count], type):
            logger.error(f'Запрос к API. Ошибка типа данных({count}, {type}).')
            raise TypeError(
                'Тип данных ответа API не соответствуют документации.'
            )
        elif not response[count]:
            raise IndexError('homeworks list is empty.')


def parse_status(homework):
    """Извлечение информации о статусе последней работы."""
    logger.info(f'Полученные данные: {homework}.')
    if 'status' not in homework or 'homework_name' not in homework:
        logger.error('Ошибка наличия данных в homework.')
        raise TypeError('Данные отсутствуют в homework.')
    homework_name = homework['homework_name']
    status_work = homework['status']
    if status_work not in HOMEWORK_VERDICTS:
        logger.error(f'Неизвестный статус работы: {status_work}.')
        raise TypeError(f'Неизвестный статус работы: {status_work}.')
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
            check_response(response)
            current_work = response['homeworks'][0]
            current_status = current_work['status']
            if last_status != current_status:
                last_status = current_status
                send_message(bot, parse_status(current_work))
            timestamp = response.get('current_date', timestamp)
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            send_message(bot, message)
            logger.error(f'{message}')
        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
