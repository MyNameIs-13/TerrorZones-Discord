#!/usr/bin/env python3

# TODO: Maybe async?
# TODO: class
# TODO: dclone tracker
# TODO: change provider to https://www.d2emu.com/?

import json
import logging
import os
import re
import signal
import sys
import time
from logging.handlers import RotatingFileHandler

import requests
import schedule
from discord_webhook import DiscordEmbed, DiscordWebhook
from dotenv import load_dotenv

# global variables
HEALTH_STATE = 0  # reduces reads from file
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


def get_immunity_emojis(immunities: list) -> str:
    return (
        "".join([IMMUNITY_EMOJIS.get(immunity) for immunity in immunities]) if immunities else "None"
    )


def setup_custom_logger(name: str = __name__) -> logging.Logger:
    """
    :param name: name of the logger which will be created
    :return: logger as logger
    """
    # for debugging purposes when running outside of container
    if os.path.exists('../.env'):
        load_dotenv('../.env')
    log_level = os.getenv('LOG_LEVEL', 'DEBUG').upper()

    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, log_level.upper(), logging.DEBUG))
    logger.addFilter(SensitiveDataFilter())

    log_filepath = f'./logs/{name}.log'
    log_path = os.path.dirname(os.path.abspath(log_filepath))
    print(f'logpath={log_path}')
    if logger.getEffectiveLevel() == logging.DEBUG and os.access(log_path, os.W_OK):
        handler = RotatingFileHandler(log_filepath, mode='a', encoding='utf-8', maxBytes=5 * 1024 * 1024, backupCount=3)
    else:
        handler = logging.StreamHandler(stream=sys.stdout)

    dt_fmt = '%Y-%m-%d %H:%M:%S'
    formatter = logging.Formatter(fmt='[{asctime}] [{levelname:<8}] {funcName}: {message}', datefmt=dt_fmt, style='{')
    handler.setFormatter(formatter)
    logger.addHandler(handler)

    return logger


def load_env(logger: logging.Logger) -> dict:
    """
    load environment variables

    :param logger:
    :return:
    """

    logger.debug('ENTER')
    env: dict = {}

    # for debugging purposes when running outside of container
    if os.path.exists('../.secrets'):
        load_dotenv('../.secrets')
    if os.path.exists('../.env'):
        load_dotenv('../.env')

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

    return env


def create_embed(logger: logging.Logger, announce_data_dict: dict) -> DiscordEmbed:
    """
    access the zone-info.json file to get additional area information for the current terrorzone
    create message with this information

    :param logger:
    :param announce_data_dict:
    :return:
    """

    logger.debug('ENTER')
    zone_found = False
    embed = DiscordEmbed()
    embed.set_color(color=announce_data_dict['COLOR'])
    embed.set_title(title=announce_data_dict['TERRORZONE_NAME'])
    embed.set_description(f"**{'⠀'*((len(announce_data_dict['PROVIDED_BY'])+2)//3)}**")
    embed.set_footer(
        text=announce_data_dict['PROVIDED_BY'],
        icon_url="https://d2runewizard.com/icons/favicon-32x32.png")
    zone_info = './zone-info/zone-info.json'
    if not os.path.exists(zone_info):
        zone_info = 'zone-info.json'
    try:
        with open(zone_info) as data_file:
            zone_info = json.load(data_file)
            for zone in zone_info['terror zones']:
                if zone['display name'] == announce_data_dict['TERRORZONE_NAME']:
                    zone_found = True
                    embed.add_embed_field('Act:', zone['act'])
                    embed.add_embed_field('Immunities:', get_immunity_emojis(zone['immunities']))
                    embed.add_embed_field('Monster packs:', zone['monster packs'])
                    embed.add_embed_field('Super uniques:', zone['super uniques'] if zone['super uniques'] else 'None')
                    embed.add_embed_field('Sparkly chests:', zone['sparkly chests'])
            if not zone_found:
                raise ValueError('No zone found that matches the current Terrorzone')
    except ValueError:
        logger.exception('')
    except FileNotFoundError:
        logger.exception('data/zone-info.json not found! Empty message was created:')
    finally:
        logger.debug('EXIT')
        return embed


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


class D2TerrorZone:
    logger: logging.Logger = None
    env_dict: dict = {}
    announced_tz_name: str = ''
    announced_tz_webhook: DiscordWebhook = None
    tz_cache_json: json = {}
    ttl_multiplier: int = 0
    job: schedule.Job = None

    def __init__(self):
        self.logger = setup_custom_logger('D2TerrorZone')
        self.env_dict = load_env(self.logger)
        self.ttl_multiplier = 10


    def get_terrorzone_json(self) -> json:
        """
        webrequest to retrieve  terrorzone

        :return: terrorzone as json
        """

        self.logger.debug('ENTER')
        params = {'token': self.env_dict['ENDPOINT_TOKEN']}
        headers = {'D2R-Contact': self.env_dict['CONTACT'], 'D2R-Platform': self.env_dict['PLATFORM'], 'D2R-Repo': self.env_dict['PUBLIC_REPO']}
        response = requests.get(self.env_dict['ENDPOINT_TZ'], params=params, headers=headers)
        if not response.ok:
            health(self.logger, False)
            self.ttl_multiplier = 10
            self.update_job_frequency()
            raise ConnectionError(f'{response.status_code} - {response.json()["message"]}')
        else:
            health(self.logger, True)
        tz_json = response.json()
        self.logger.debug(f'json={json.dumps(tz_json, indent=4)}')
        self.logger.debug('EXIT')

        return tz_json


    def announce_terrorzone(self, announce_data_dict: dict):
        """
        announce_terrorzone

        :param announce_data_dict:
        :return:
        """

        self.logger.debug('ENTER')
        # add embed object to webhook
        webhook = DiscordWebhook(url=f'https://discord.com/api/webhooks/{self.env_dict["WEBHOOK_ID"]}/{self.env_dict["WEBHOOK_TOKEN"]}')
        webhook.add_embed(create_embed(self.logger, announce_data_dict))
        response = webhook.execute()
        if not response.ok:
            health(self.logger, False)
            self.ttl_multiplier = 10
            self.update_job_frequency()
            self.logger.error(f'Failed to execute webhook! Response from api: {response}')
            raise ConnectionError(f'{response.status_code} - {response.json()}')
        else:
            self.announced_tz_webhook = webhook
            self.announced_tz_name = announce_data_dict['TERRORZONE_NAME']
            self.logger.info(f'Announce successful! New Terrorzone: {self.announced_tz_name}')
            self.update_job_frequency()
            health(self.logger, True)
        self.logger.debug('EXIT')


    def update_terrorzone(self, full_hour: bool=False):
        """
        Checks if the announced terrorzone needs to be changed.

        :param full_hour:
        :return:
        """

        self.logger.debug('ENTER')
        try:
            tz_json: json = self.get_terrorzone_json()
        except ConnectionError as e:
            self.logger.error(f'Failed to get terrorzone! Response from api: {e}')
        else:
            provided_by: str = f'terrorzone provided by {tz_json.get('providedBy')}'
            current_terrorzone_name: str = tz_json.get('currentTerrorZone', {}).get('zone')
            next_terrorzone_name: str = tz_json.get('nextTerrorZone', {}).get('zone')
            announce_data_dict = {'PROVIDED_BY': provided_by, 'TERRORZONE_NAME': current_terrorzone_name, 'COLOR': '8B0000'}
            # website often fails to update the json response at the correct time.
            # as a workaround there are these conditions which try to circumvent this
            if not self.announced_tz_name:  # on initial script run
                self.logger.info('inital script start, no announcment')
                self.announced_tz_name = current_terrorzone_name
                self.ttl_multiplier = 10
                self.update_job_frequency()
            elif full_hour and self.announced_tz_name != current_terrorzone_name:
                self.logger.info('full hour, new terrorzone available, long timer')
                self.ttl_multiplier = 10
                self.announce_terrorzone(announce_data_dict)
            elif full_hour and self.announced_tz_name == current_terrorzone_name:
                self.logger.info('full hour, terrorzone old, announce next instead, short timeer')
                announce_data_dict['TERRORZONE_NAME'] = next_terrorzone_name
                self.ttl_multiplier = 10
                self.announce_terrorzone(announce_data_dict)
            elif self.announced_tz_name == current_terrorzone_name:
                self.logger.info('update check, terrorzone not changed, long timer')
                self.ttl_multiplier = 10
                self.update_job_frequency()
            elif self.announced_tz_name == next_terrorzone_name:
                self.logger.info('update check, terrorzone not changed, short timer')
                self.ttl_multiplier = 4
                self.update_job_frequency()
            else:
                self.logger.info('update check, terrorzone information outdated, new announcement with different color')
                # when script initially starts it does not exist, in all other cases it shoudl exist
                if self.announced_tz_webhook:
                    self.announced_tz_webhook.delete()
                    announce_data_dict['PROVIDED_BY'] = f'updated {provided_by}'
                    announce_data_dict['COLOR'] = '00FF00'
                self.ttl_multiplier = 4
                self.announce_terrorzone(announce_data_dict)

        finally:
            self.logger.debug('EXIT')


    def update_job_frequency(self):
        """
        try to avoid flooding the tracker with requests. Depending on the reported amount, wait longer until next request

        :return:
        """

        self.logger.debug('ENTER')
        if self.ttl_multiplier > 10:
            ttl = 3600  # if there are so many votes, it's probably the correct one, not necessary to check anymore
        elif self.ttl_multiplier > 3:
            ttl = self.ttl_multiplier * 60
        elif self.ttl_multiplier > 0:
            ttl = 60
        else:
            ttl = 30
        self.logger.info(f'new TTL={ttl}')
        # recreate the tasks with the new TTL
        schedule.cancel_job(self.job)
        self.job = schedule.every(ttl).seconds.do(self.update_terrorzone)
        self.logger.debug('EXIT')


def main():

    custom_logger = setup_custom_logger('main')

    custom_logger.info('')
    custom_logger.info('=============================================')
    custom_logger.info('MAIN SCRIPT START')
    custom_logger.info('=============================================')
    custom_logger.info('')

    tz = D2TerrorZone()

    with open('/tmp/health', 'w') as f:
        f.write(str(0))

    # execute every full hour
    schedule.every().hour.at('00:00').do(tz.update_terrorzone, full_hour=True)

    # check if there is a new 'best' zone
    tz.job = schedule.every().seconds.do(tz.update_terrorzone)

    custom_logger.debug(schedule.get_jobs())

    # run indefinitely and wait for new tasks to run
    killer = GracefulKiller()
    while not killer.kill_now:
        schedule.run_pending()
        time.sleep(5)
    custom_logger.info('Stopped gracefully :)')  # timeout needs to be 30+sec


if __name__ == '__main__':
    main()
