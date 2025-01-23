#!/usr/bin/env python3

# TODO: Maybe async?

import os
import sys
import re
import time
import json
import requests
import signal
import logging

from logging.handlers import RotatingFileHandler

import schedule

from discord_webhook import DiscordWebhook, DiscordEmbed
from dotenv import load_dotenv

# global variables
health_state: int = 0  # reduces reads from file
announced_terrorzone_name: str = ''
update_job: schedule.Job


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

    loglevel = os.getenv('LOG_LEVEL', 'DEBUG')
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


def create_message(terrorzone_name: str, logger: logging.Logger):
    """
    access the zone-info.json file to get additional area information for the current terrorzone
    create message with this information

    :param terrorzone_name: name of the terrorzone about to be announced
    :param logger:
    :return:
    """

    logger.debug('ENTER')
    act, immunities, monster_pack, super_uniques, sparkly_chests = ('', '', '', '', '')
    zone_found = False
    error_occurred = False
    message = ''
    zone_info = './zone-info/zone-info.json'
    if not os.path.exists(zone_info):
        zone_info = 'zone-info.json'
    try:
        with open(zone_info) as data_file:
            zone_info = json.load(data_file)
            for zones in zone_info['terror zones']:
                if zones['display name'] == terrorzone_name:
                    zone_found = True
                    act = zones['act']
                    immunities = zones['immunities']
                    monster_pack = zones['monster packs']
                    super_uniques = zones['super uniques']
                    sparkly_chests = zones['sparkly chests']

            if not zone_found:
                raise ValueError('No zone found that matches the current Terrorzone')

    except ValueError:
        logger.exception('')
        error_occurred = True
    except FileNotFoundError:
        logger.exception('data/zone-info.json not found! Empty message was created:')
        error_occurred = True
    finally:
        if not error_occurred:
            message = f"""
```
Act:              {act}
Immunities:       {immunities}
Monster packs:    {monster_pack}
Super uniques:    {super_uniques}
Sparkly chests:   {sparkly_chests}
```"""
            logger.debug(f'message created:\n{message}')
        logger.debug('EXIT')
        return message


def announce_terrorzone(env: dict, logger: logging.Logger, provided_by: str, announce_terrorzone_name: str, ttl_multiplier: int,  color: str='8B0000'):
    """
    announce_terrorzone

    :param env: loaded environment variables
    :param logger:
    :param provided_by: link to the tracker website
    :param announce_terrorzone_name:
    :param ttl_multiplier:
    :param color: define the bordercolor of the announced discord message
    :return:
    """
    global announced_terrorzone_name

    logger.debug('ENTER')

    # create embed object for webhook
    # you can set the color as a decimal (color=242424) or hex (color='03b2f8') number
    embed = DiscordEmbed(title=announce_terrorzone_name, description=create_message(announce_terrorzone_name, logger), color=color)
    # set footer
    embed.set_footer(text=f'terrorzone provided by {provided_by}')
    # set timestamp (default is now)
    embed.set_timestamp()
    # add embed object to webhook
    webhook = DiscordWebhook(url=f'https://discord.com/api/webhooks/{env["WEBHOOK_ID"]}/{env["WEBHOOK_TOKEN"]}')
    webhook.add_embed(embed)
    response = webhook.execute()
    if not response.ok:
        health(logger, False)
        logger.error(f'Failed to execute webhook! Response from api: {response}')
        raise ConnectionError(f'{response.status_code} - {response.json()}')
    else:
        update_ttl(env, logger, ttl_multiplier)
        announced_terrorzone_name = announce_terrorzone_name
        logger.info(f'Announce successful! New Terrorzone: {announced_terrorzone_name}')
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

    global announced_terrorzone_name

    logger.debug('ENTER')
    try:
        terrorzone_data: json = get_terrorzone_data(env, logger)
        provided_by: str = terrorzone_data.get('providedBy')
        current_terrorzone_name: str = terrorzone_data.get('currentTerrorZone').get('zone')
        next_terrorzone_name: str = terrorzone_data.get('nextTerrorZone').get('zone')
    except ConnectionError as e:
        logger.error(f'Failed to get terrorzone! Response from api: {e}')
    else:
        # website often fails to update the json response at the correct time.
        # as a workaround there are these conditions which try to circumvent this
        if not announced_terrorzone_name:
            logger.info('initial script, no announcement')
            announced_terrorzone_name = current_terrorzone_name
            update_ttl(env, logger, 10)
        elif announced_terrorzone_name != current_terrorzone_name and full_hour:
            logger.info('full hour, new terrorzone available')
            announce_terrorzone(env, logger, provided_by, current_terrorzone_name, 11)
        elif announced_terrorzone_name == current_terrorzone_name and full_hour:
            logger.info('full hour, terrorzone old, announce next instead')
            announce_terrorzone(env, logger, provided_by, next_terrorzone_name, 4)
        elif announced_terrorzone_name == current_terrorzone_name:
            logger.info('update check, terrorzone not changed, timer increased')
            update_ttl(env, logger, 10)
            pass  # nothing changed
        elif announced_terrorzone_name == next_terrorzone_name:
            logger.info('update check, terrorzone not changed')
            pass  # nothing changed
        else:
            logger.info('update check, terrorzone information outdated, new announcement with different color')
            announce_terrorzone(env, logger, provided_by, current_terrorzone_name, 4, color='00FF00')

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
    global update_job

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
    schedule.cancel_job(update_job)
    update_job = schedule.every(ttl).seconds.do(update_terrorzone, env=env, logger=logger)
    logger.debug('EXIT')


def health(logger: logging.Logger, state=False):
    """
    Writes health state to file for container orchestrator to use

    :param logger:
    :param state:
    :return:
    """

    global health_state

    logger.debug('ENTER')
    if state and health_state == 0:
        logger.debug('EXIT 1')
        return    
    elif not state and health_state == 1:
        logger.debug('EXIT 2')
        return
    elif state and health_state == 1:
        health_state = 0
    elif not state and health_state == 0:
        health_state = 1
 
    with open('/tmp/health', 'w') as f:
        f.write(str(health_state))
    logger.info(f'health set to: {str(health_state)}')
    logger.debug('EXIT')


def main():
    global update_job

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
    update_job = schedule.every().seconds.do(update_terrorzone, env=env_dict, logger=custom_logger)

    custom_logger.debug(schedule.get_jobs())

    # run indefinitely and wait for new tasks to run
    killer = GracefulKiller()
    while not killer.kill_now:
        schedule.run_pending()
        time.sleep(5)
    custom_logger.info('Stopped gracefully :)')  # timeout needs to be 30+sec


if __name__ == '__main__':
    main()
