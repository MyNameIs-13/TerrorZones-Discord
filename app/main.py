#!/usr/bin/env python3

# TODO: Maybe async?
# TODO: class
# TODO: dclone tracker
# TODO: change provider to https://www.d2emu.com/?

import os
import sys
import re
import time
import json
from time import sleep

import requests
import signal
import logging

from logging.handlers import RotatingFileHandler

import schedule

from discord_webhook import DiscordWebhook, DiscordEmbed
from dotenv import load_dotenv

# global variables
HEALTH_STATE: int = 0  # reduces reads from file
ANNOUNCED_TERRORZONE_NAME: str = ''
ANNOUNCED_TERRORZONE_WEBHOOK: DiscordWebhook
UPDATE_JOB: schedule.Job
IMMUNITY_EMOJIS = {
    "c": "\U00002744️",
    "f": "\U0001F525",
    "l": "\U000026A1",
    "p": "\U00002620",
    "ph": "\U0001F4AA",
    "m": "\U00002728",
}


class GracefulKiller:
    kill_now = False

    def __init__(self):
        signal.signal(signal.SIGINT, self.exit_gracefully)
        signal.signal(signal.SIGTERM, self.exit_gracefully)

    def exit_gracefully(self, *args):
        self.kill_now = True


class SensitiveDataFilter(logging.Filter):
    def filter(self, record):
        # If the log message is a dictionary, mask sensitive fields
        if hasattr(record, 'msg'):
            if isinstance(record.msg, (list, str)):
                # Use regex to find and replace the value of "password"
                if 'TOKEN' in str(record.msg):
                    record.msg = re.sub(r"(TOKEN'?:? ?=?'?)[^\s^']+", r"\1****", str(record.msg))
        return True


def setup_custom_logger(name='terrorzone-discord-webhook') -> logging.Logger:
    """

    :param name: name of the logger which will be created
    :return: logger as logger
    """

    formatter = logging.Formatter(fmt='%(asctime)s %(levelname)-8s %(funcName)-20s %(message)s',
                                  datefmt='%Y-%m-%d %H:%M:%S')
    logpath = './logs/terrorzone-discord-webhook.log'
    print(f'logpath={logpath}')
    logger = logging.getLogger(name)
    logger.addFilter(SensitiveDataFilter())
    if not os.access('./logs', os.W_OK):
        handler = logging.StreamHandler(stream=sys.stdout)
    else:
        handler = RotatingFileHandler(logpath, mode='a', maxBytes=2000000, backupCount=3)
    handler.setFormatter(formatter)
    logger.addHandler(handler)

    loglevel = os.getenv('LOGLEVEL', 'DEBUG')
    if loglevel.upper() == 'INFO':
        logger.setLevel(logging.INFO)
    elif loglevel.upper() == 'WARNING':
        logger.setLevel(logging.WARNING)
    elif loglevel.upper() == 'ERROR':
        logger.setLevel(logging.ERROR)
    elif loglevel.upper() == 'CRITICAL':
        logger.setLevel(logging.CRITICAL)
    else:
        logger.setLevel(logging.DEBUG)

    return logger


def load_env(env: dict, logger: logging.Logger):
    """
    load environment variables

    :param env:
    :param logger:
    :return:
    """

    # for debugging purposes when running outside of container
    if os.path.exists('../.secrets'):
        load_dotenv('../.secrets')

    logger.debug('ENTER')
    env['WEBHOOK_ID'] = os.getenv('WEBHOOK_ID')
    logger.debug(f'WEBHOOK_ID={env["WEBHOOK_ID"]}')
    env['WEBHOOK_TOKEN'] = os.getenv("WEBHOOK_TOKEN")
    logger.debug(f'WEBHOOK_TOKEN={env["WEBHOOK_TOKEN"]}')
    env['ENDPOINT_TZ'] = os.getenv('ENDPOINT_TZ', 'https://d2runewizard.com/api/terror-zone')
    logger.debug(f'ENDPOINT_TZ={env["ENDPOINT_TZ"]}')
    env['ENDPOINT_TOKEN'] = os.getenv("ENDPOINT_TOKEN")
    logger.debug(f'ENDPOINT_TOKEN={env["ENDPOINT_TOKEN"]}')
    env['CONTACT'] = os.getenv("CONTACT")
    logger.debug(f'CONTACT={env["CONTACT"]}')
    env['PLATFORM'] = os.getenv("PLATFORM")
    logger.debug(f'PLATFORM={env["PLATFORM"]}')
    env['PUBLIC_REPO'] = os.getenv("PUBLIC_REPO")
    logger.debug(f'PUBLIC_REPO={env["PUBLIC_REPO"]}')
    logger.debug('EXIT')


def get_immunity_emojis(immunities: list) -> str:
    return (
        "".join([IMMUNITY_EMOJIS.get(immunity) for immunity in immunities]) if immunities else "None"
    )

def create_embed(announce_data_dict: dict, logger: logging.Logger) -> DiscordEmbed:
    """
    access the zone-info.json file to get additional area information for the current terrorzone
    create message with this information

    :param announce_data_dict:
    :param logger:
    :return:
    """

    logger.debug('ENTER')
    zone_found = False
    # create embed object for webhook
    # you can set the color as a decimal (color=242424) or hex (color='03b2f8') number
    embed = DiscordEmbed()
    embed.set_title(title=announce_data_dict['TERRORZONE_NAME'])
    embed.set_color(color=announce_data_dict['COLOR'])
    embed.set_footer(
        text=announce_data_dict['PROVIDED_BY'],
        icon_url="https://d2runewizard.com/icons/favicon-32x32.png")
    embed.set_description('-'*(len(embed.footer['text'])+2))

    zone_info = './zone-info/zone-info.json'
    if not os.path.exists(zone_info):
        zone_info = 'zone-info.json'

    try:
        with open(zone_info) as data_file:
            zone_info = json.load(data_file)
            for zone in zone_info['terror zones']:
                if zone['display name'] == announce_data_dict['TERRORZONE_NAME']:
                    zone_found = True
                    embed.add_embed_field('Act:', zone['act'], inline=True)
                    embed.add_embed_field('Immunities:', get_immunity_emojis(zone['immunities']), inline=True)
                    embed.add_embed_field('Monster packs:', zone['monster packs'], inline=True)
                    embed.add_embed_field('Super uniques:', zone['super uniques'] if zone['super uniques'] else 'None', inline=True)
                    embed.add_embed_field('Sparkly chests:', zone['sparkly chests'], inline=True)
            if not zone_found:
                raise ValueError('No zone found that matches the current Terrorzone')
    except ValueError:
        logger.exception('')
    except FileNotFoundError:
        logger.exception('data/zone-info.json not found! Empty message was created:')
    finally:
        logger.debug('EXIT')
        return embed


def announce_terrorzone(env: dict, logger: logging.Logger, announce_data_dict: dict, ttl_multiplier: int):
    """
    announce_terrorzone

    :param announce_data_dict:
    :param env: loaded environment variables
    :param logger:
    :param ttl_multiplier:
    :return:
    """
    global ANNOUNCED_TERRORZONE_NAME
    global ANNOUNCED_TERRORZONE_WEBHOOK

    logger.debug('ENTER')

    # add embed object to webhook
    webhook = DiscordWebhook(url=f'https://discord.com/api/webhooks/{env["WEBHOOK_ID"]}/{env["WEBHOOK_TOKEN"]}')
    webhook.add_embed(create_embed(announce_data_dict, logger))
    response = webhook.execute()
    if not response.ok:
        health(logger, False)
        logger.error(f'Failed to execute webhook! Response from api: {response}')
        raise ConnectionError(f'{response.status_code} - {response.json()}')
    else:
        ANNOUNCED_TERRORZONE_WEBHOOK = webhook
        update_ttl(env, logger, ttl_multiplier)
        ANNOUNCED_TERRORZONE_NAME = announce_data_dict['TERRORZONE_NAME']
        logger.info(f'Announce successful! New Terrorzone: {ANNOUNCED_TERRORZONE_NAME}')
        health(logger, True)
    logger.debug('EXIT')


def update_terrorzone(env: dict, logger: logging.Logger, full_hour: bool=False):
    """
    Checks if the announced terrorzone needs to be changed.

    :param env: loaded environment variables
    :param logger:
    :param full_hour:
    :return:
    """

    global ANNOUNCED_TERRORZONE_NAME

    logger.debug('ENTER')
    try:
        terrorzone_data: json = get_terrorzone_data(env, logger)
        provided_by: str = f'terrorzone provided by {terrorzone_data.get('providedBy')}'
        current_terrorzone_name: str = terrorzone_data.get('currentTerrorZone').get('zone')
        next_terrorzone_name: str = terrorzone_data.get('nextTerrorZone').get('zone')
        announce_data_dict = {'PROVIDED_BY': provided_by, 'TERRORZONE_NAME': current_terrorzone_name, 'COLOR': '8B0000'}
    except ConnectionError as e:
        logger.error(f'Failed to get terrorzone! Response from api: {e}')
    else:
        # website often fails to update the json response at the correct time.
        # as a workaround there are these conditions which try to circumvent this
        if not ANNOUNCED_TERRORZONE_NAME:
            logger.info('initial script, no announcement')
            ANNOUNCED_TERRORZONE_NAME = current_terrorzone_name
            update_ttl(env, logger, 10)
        elif ANNOUNCED_TERRORZONE_NAME != current_terrorzone_name and full_hour:
            logger.info('full hour, new terrorzone available, long timer')
            announce_terrorzone(env, logger, announce_data_dict, 10)
        elif ANNOUNCED_TERRORZONE_NAME == current_terrorzone_name and full_hour:
            logger.info('full hour, terrorzone old, announce next instead, short timeer')
            announce_data_dict['TERRORZONE_NAME'] = next_terrorzone_name
            announce_terrorzone(env, logger, announce_data_dict, 4)
        elif ANNOUNCED_TERRORZONE_NAME == current_terrorzone_name:
            logger.info('update check, terrorzone not changed, long timer')
            update_ttl(env, logger, 10)
            pass  # nothing changed
        elif ANNOUNCED_TERRORZONE_NAME == next_terrorzone_name:
            logger.info('update check, terrorzone not changed, short timer')
            pass  # nothing changed
        else:
            logger.info('update check, terrorzone information outdated, new announcement with different color')
            ANNOUNCED_TERRORZONE_WEBHOOK.delete()
            announce_data_dict['PROVIDED_BY'] = f'updated {provided_by}'
            announce_data_dict['COLOR'] = '00FF00'
            announce_terrorzone(env, logger, announce_data_dict, 4)

    logger.debug('EXIT')


def get_terrorzone_data(env: dict, logger: logging.Logger) -> json:
    """
    webrequest to retrieve  terrorzone data
    :param env: loaded environment variables
    :param logger:
    :return: terrorzone data as json
    """

    logger.debug('ENTER')
    params = {'token': env['ENDPOINT_TOKEN']}
    headers = {'D2R-Contact': env['CONTACT'], 'D2R-Platform': env['PLATFORM'], 'D2R-Repo': env['PUBLIC_REPO']}
    response = requests.get(env['ENDPOINT_TZ'], params=params, headers=headers)
    if not response.ok:
        health(logger, False)
        update_ttl(env, logger, 10)  # set new update interval to 10 minutes
        raise ConnectionError(f'{response.status_code} - {response.json()["message"]}')
    else:
        health(logger, True)
    terrorzone_data = response.json()
    logger.debug(f'json={json.dumps(terrorzone_data, indent=4)}')
    logger.debug('EXIT')
    return terrorzone_data


def update_ttl(env: dict, logger: logging.Logger, multiplier: int=0):
    """
    try to avoid flooding the tracker with requests. Depending on the reported amount, wait longer until next request

    :param env: loaded environment variables
    :param logger:
    :param multiplier:
    :return:
    """
    global UPDATE_JOB

    logger.debug('ENTER')
    if multiplier > 10:
        ttl = 3600  # if there are so many votes, it's probably the correct one, not necessary to check anymore
    elif multiplier > 3:
        ttl = multiplier * 60
    elif multiplier > 0:
        ttl = 60
    else:
        ttl = 30
    logger.info(f'new TTL={ttl}')
    # recreate the tasks with the new TTL
    schedule.cancel_job(UPDATE_JOB)
    UPDATE_JOB = schedule.every(ttl).seconds.do(update_terrorzone, env=env, logger=logger)
    logger.debug('EXIT')


def health(logger: logging.Logger, state=False):
    """
    Writes health state to file for container orchestrator to use

    :param logger:
    :param state:
    :return:
    """

    global HEALTH_STATE

    logger.debug('ENTER')
    if state and HEALTH_STATE == 0:
        logger.debug('EXIT 1')
        return    
    elif not state and HEALTH_STATE == 1:
        logger.debug('EXIT 2')
        return
    elif state and HEALTH_STATE == 1:
        HEALTH_STATE = 0
    elif not state and HEALTH_STATE == 0:
        HEALTH_STATE = 1
 
    with open('/tmp/health', 'w') as f:
        f.write(str(HEALTH_STATE))
    logger.info(f'health set to: {str(HEALTH_STATE)}')
    logger.debug('EXIT')


def main():
    global UPDATE_JOB

    env_dict: dict = {'WEBHOOK_ID': '',
                 'WEBHOOK_TOKEN': '',
                 'ENDPOINT_TZ': '',
                 'ENDPOINT_TOKEN': '',
                 'CONTACT': '',
                 'PLATFORM': '',
                 'PUBLIC_REPO': ''}
    custom_logger = setup_custom_logger()

    custom_logger.info('')
    custom_logger.info('=============================================')
    custom_logger.info('MAIN SCRIPT START')
    custom_logger.info('=============================================')
    custom_logger.info('')

    load_env(env_dict, custom_logger)

    with open('/tmp/health', 'w') as f:
        f.write(str(0))

    # execute every full hour
    schedule.every().hour.at('00:00').do(update_terrorzone, env=env_dict, logger=custom_logger, full_hour=True)

    # check if there is a new 'best' zone
    UPDATE_JOB = schedule.every().seconds.do(update_terrorzone, env=env_dict, logger=custom_logger)

    custom_logger.debug(schedule.get_jobs())

    # run indefinitely and wait for new tasks to run
    killer = GracefulKiller()
    while not killer.kill_now:
        schedule.run_pending()
        time.sleep(5)
    custom_logger.info('Stopped gracefully :)')  # timeout needs to be 30+sec


if __name__ == '__main__':
    main()
