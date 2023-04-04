#!/usr/bin/env python3

# TODO: prevent double execution. (currently only some prevention with bash script as starter)
# TODO: improve error handling
# TODO: Maybe async?
# TODO: add header
# rewrite for docker

from cmath import exp
from hashlib import blake2b
import sys
import os
from unittest import expectedFailure
import schedule
import time
import json
import requests
import logging
from logging.handlers import RotatingFileHandler
from discord_webhook import DiscordWebhook, DiscordEmbed
from dotenv import load_dotenv
from pathlib import Path

# global variables
announced_terrorzone = 'undefined'
announced_terrorzone_name = ''
logger = logging.getLogger('')
update_job = ''
WEBHOOK_ID = ''
WEBHOOK_TOKEN = ''
ENDPOINT_TZ = ''
ENDPOINT_TOKEN = ''
ARGS_DICT = {'FORCE_INITIAL_ANNOUNCEMENT': '0', 'LOG_TO_CONSOLE': '0', 'LOG_PATH': '', 'LOG_LEVEL': 'DEBUG'}
SCRIPT_HOME = '.'


def setup_custom_logger(name='terrorzone-discord-webhook'):
    global ARGS_DICT
    global SCRIPT_HOME

    formatter = logging.Formatter(fmt='%(asctime)s %(levelname)-8s %(process)d %(funcName)-20s %(message)s',
                                  datefmt='%Y-%m-%d %H:%M:%S')
    filename = 'terrorzone-discord-webhook.log'

    filepath = os.path.expanduser('~') + '/' + filename
    if bool(ARGS_DICT['LOG_PATH']):  # checks if not None or empty by converting to bool
        try:
            path = Path(ARGS_DICT['LOG_PATH'])
            path.mkdir(parents=True, exist_ok=True)
            if os.path.isdir(str(path)):
                filepath = ARGS_DICT['LOG_PATH'] + '/' + filename
        except PermissionError:
            path = Path(SCRIPT_HOME + '/logs')
            path.mkdir(parents=True, exist_ok=True)
            if os.path.isdir(str(path)):
                filepath = str(path) + '/' + filename
    else:
        path = Path(SCRIPT_HOME + '/logs')
        path.mkdir(parents=True, exist_ok=True)
        if os.path.isdir(str(path)):
            filepath = str(path) + '/' + filename

    print('filepath=' + filepath)
    handler = RotatingFileHandler(filepath, mode='a', maxBytes=2000000, backupCount=3)
    handler.setFormatter(formatter)
    custom_logger = logging.getLogger(name)
    if ARGS_DICT['LOG_LEVEL'].upper() == 'INFO':
        custom_logger.setLevel(logging.INFO)
    elif ARGS_DICT['LOG_LEVEL'].upper() == 'WARNING':
        custom_logger.setLevel(logging.WARNING)
    elif ARGS_DICT['LOG_LEVEL'].upper() == 'ERROR':
        custom_logger.setLevel(logging.ERROR)
    elif ARGS_DICT['LOG_LEVEL'].upper() == 'CRITICAL':
        custom_logger.setLevel(logging.CRITICAL)
    else:
        custom_logger.setLevel(logging.DEBUG)
    custom_logger.addHandler(handler)
    if ARGS_DICT['LOG_TO_CONSOLE'] == '1':
        screen_handler = logging.StreamHandler(stream=sys.stdout)
        screen_handler.setFormatter(formatter)
        custom_logger.addHandler(screen_handler)
    return custom_logger


# these arguments are supposed to override functionality if default is not desired
def load_arguments(arguments):
    global ARGS_DICT
    global SCRIPT_HOME
    global logger

    if len(arguments) > 1:

        if os.path.isdir(arguments[1]):
            SCRIPT_HOME = arguments[1]

        logger = setup_custom_logger('initialize')  # runs with default values instead of overwrites
        logger.debug('ENTER Function')
        logger.info('=============================================')
        logger.info('SCRIPT INITIALIZE')
        logger.info('=============================================')
        logger.debug('SCRIPT_HOME: ' + SCRIPT_HOME)

        for i in range(1, len(arguments)):
            try:
                if i == 1 and os.path.isdir(arguments[1]):
                    continue
                key, value = arguments[i].split('=')
                ARGS_DICT[key.upper()] = value
                logger.debug('Dict[' + key + '] = ' + value)
            except ValueError:
                logger.error('invalid argument! Cannot unpack: ' + arguments[i])
    for handler in logger.handlers[:]:  # prevent double logging (new logger instance is started in main)
        handler.close()
    logger.debug('EXIT Function')


def load_env():
    # load environment variables (or load them from a .env file)
    global WEBHOOK_ID
    global WEBHOOK_TOKEN
    global ENDPOINT_TZ
    global ENDPOINT_TOKEN
    global SCRIPT_HOME

    logger.debug('ENTER Function')
    env_path = Path(SCRIPT_HOME) / 'data/.env'
    load_dotenv(dotenv_path=env_path)
    logger.debug('env_path=' + str(env_path))
    WEBHOOK_ID = os.getenv("WEBHOOK_ID")
    logger.debug('WEBHOOK_ID=' + WEBHOOK_ID)
    WEBHOOK_TOKEN = os.getenv("WEBHOOK_TOKEN")
    logger.debug('WEBHOOK_TOKEN=' + WEBHOOK_TOKEN)
    ENDPOINT_TZ = os.getenv("ENDPOINT_TZ")
    logger.debug('ENDPOINT_TZ=' + ENDPOINT_TZ)
    ENDPOINT_TOKEN = os.getenv("ENDPOINT_TOKEN")
    logger.debug('ENDPOINT_TOKEN=' + ENDPOINT_TOKEN)
    logger.debug('EXIT Function')


# very silly approach to reduce double execution (bash script uses the information to kill the process)
def check_lock():
    global logger
    global SCRIPT_HOME
    ret_val = False

    logger.debug('ENTER Function')
    path = Path(SCRIPT_HOME + '/logs')
    path.mkdir(parents=True, exist_ok=True)
    filepath = str(path) + '/.lock'
    if os.path.isfile(filepath):
        logger.debug('EXIT Function a')
        ret_val = False
        raise FileExistsError('lock exists. Please stop the previous execution first')
    elif os.path.isdir(str(path)):
        file1 = open(filepath, 'w')
        file1.write(str(os.getpid()))
        file1.close()
        logger.info('lock created')
        ret_val = True
    else:
        logger.error('lock not created')
        logger.debug('EXIT Function b')
        ret_val = False
        raise FileNotFoundError('Cannot create lock file. Does the path exist?')
    logger.debug('EXIT Function')
    return ret_val


# access the zone-info.json file to get additional area information for the current terrorzone
# create message with this information
def create_message():
    global SCRIPT_HOME
    global logger
    global announced_terrorzone_name

    logger.debug('ENTER Function')
    act, immunities, monster_pack, super_uniques, sparkly_chests = ('', '', '', '', '')
    zone_found = False
    error_occurred = False
    message = ''
    zone_name = announced_terrorzone_name
    try:
        with open(SCRIPT_HOME + '/data/zone-info.json') as data_file:
            zone_info = json.load(data_file)
            for zones in zone_info['terror zones']:
                if zones['display name'] == zone_name:
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
            message = '\
```\
Act:              ' + act + '\n\
Immunities:       ' + immunities + '\n\
Monster packs:    ' + monster_pack + '\n\
Super uniques:    ' + super_uniques + '\n\
Sparkly chests:   ' + sparkly_chests + '\n\
```'
            logger.debug('message created:\n' + message)
        logger.debug('EXIT Function')
        return message


# every hour a new terrorzone is announced
# if an update is needed (wrong terrorzone announced) use a different color and footer
def announce_terrorzone(update=False, color='8B0000'):
    global logger
    global announced_terrorzone
    global announced_terrorzone_name
    global WEBHOOK_ID
    global WEBHOOK_TOKEN

    logger.debug('ENTER Function')

    try:
        if not update:
            announced_terrorzone, announced_terrorzone_name = get_new_terrorzone()
    except ConnectionError as e:
        logger.error('Failed to get terrorzone! Response from api: ' + str(e))        
    else:        
        amount = announced_terrorzone['terrorZone']['highestProbabilityZone']['amount']
        update_ttl(amount)
        if amount == 0:  # no terrorzone known yet. Will trust in the update method to be called again shortly
            announced_terrorzone_name = "NotKnownYet"
            logger.warning('could not announce a terrorzone. None is known yet')
            logger.debug('EXIT Function 0a')
            return '0a'

        webhook = DiscordWebhook(
            url='https://discord.com/api/webhooks/' + str(WEBHOOK_ID) + '/' + str(WEBHOOK_TOKEN))

        # create embed object for webhook
        # you can set the color as a decimal (color=242424) or hex (color='03b2f8') number
        embed = DiscordEmbed(title=announced_terrorzone_name, description=create_message(), color=color)

        # set footer
        provided_by = 'terrorzone provided by ' + announced_terrorzone['providedBy']
        if update:
            embed.set_footer(text='updated ' + provided_by)
        else:
            embed.set_footer(text='new ' + provided_by)

        # set timestamp (default is now)
        embed.set_timestamp()

        # add embed object to webhook
        webhook.add_embed(embed)

        try:
            response = webhook.execute()
            logger.info('Announce successful! New Terrorzone: ' + announced_terrorzone_name)
        except:
            if not response.ok:
                logger.error('Failed to execute webhook! Response from api: ' + str(response))
                logger.debug('EXIT Function 0b')
                return '0b'
        
    logger.debug('EXIT Function 1')
    return 1


# if the most reported terrorzone changes, update current terrorzone
def update_terrorzone():
    global logger
    global announced_terrorzone
    global announced_terrorzone_name
    global ARGS_DICT

    logger.debug('ENTER Function')
    # initial start of the script (assume the script was running before and discord contains that information)
    # just set announced_* without announcing when force_initial_announcement=False
    if announced_terrorzone == 'undefined':
        if ARGS_DICT['FORCE_INITIAL_ANNOUNCEMENT'] == '1':
            logger.warning('call announce_terrorzone(new). Initial announcement is forced')
            try:
                announce_terrorzone()
            except ConnectionError as e:
                logger.error('Failed to get terrorzone! Response from api: ' + str(e))
            logger.debug('initiate EXIT Function 1')
        else:
            try:
                announced_terrorzone, announced_terrorzone_name = get_new_terrorzone()
            except ConnectionError as e:
                logger.error('Failed to get terrorzone! Response from api: ' + str(e))
            else:
                logger.debug('terrorzone updated from None to ' + announced_terrorzone_name)
                announced_reported_amount = announced_terrorzone['terrorZone']['highestProbabilityZone']['amount']
                update_ttl(announced_reported_amount)
                if announced_reported_amount == 0:  # no terrorzone known yet.
                    announced_terrorzone_name = "NotKnownYet"
                    logger.info('could not announce a terrorzone. None is known yet')
                logger.debug('initiate EXIT Function 2')

    # when at full hour no terrorzone is known
    elif announced_terrorzone_name == "NotKnownYet":
        logger.warning('call announce_terrorzone(new). Scheduled run too early')
        try:
            announce_terrorzone()
        except ConnectionError as e:
            logger.error('Failed to get terrorzone! Response from api: ' + str(e))
        logger.debug('initiate EXIT Function 3')
    else:
        try:
            new_terrorzone, new_terrorzone_name = get_new_terrorzone()
        except ConnectionError as e:
             logger.error('Failed to get terrorzone! Response from api: ' + str(e))            
        else:
            new_reported_amount = new_terrorzone['terrorZone']['highestProbabilityZone']['amount']
            announced_reported_amount = announced_terrorzone['terrorZone']['highestProbabilityZone']['amount']

            # there was a change, previous announced terrorzone was wrongly reported
            if new_reported_amount > announced_reported_amount and new_terrorzone_name != announced_terrorzone_name:
                logger.warning('call announce_terrorzone(update). Previous reports were wrong')
                announced_terrorzone = new_terrorzone
                announced_terrorzone_name = new_terrorzone_name
                announce_terrorzone(True, '00FF00')
                logger.debug('initiate EXIT Function 4')

            # if reported_amount is higher than before, we can increase the scheduled interval
            elif new_reported_amount > announced_reported_amount:
                logger.debug('call update_ttl')
                update_ttl(new_reported_amount)
                logger.debug('initiate EXIT Function 5')
            else:
                logger.debug('no change, nothing to do')
                logger.debug('initiate EXIT Function 6')
    logger.debug('EXIT Function')


#  access the tracker with a GET request to have the new terrorzone as JSON
def get_new_terrorzone():
    global logger
    global ENDPOINT_TZ
    global ENDPOINT_TOKEN

    logger.debug('ENTER Function')

    params = {'token': ENDPOINT_TOKEN}
    response = requests.get(ENDPOINT_TZ, params=params)
    if not response.ok:
        update_ttl(10)  # set new update interval to 10 minutes
        raise ConnectionError(f"{response.status_code} - {response.json()['message']}")

    new_terrorzone = response.json()
    new_terrorzone_name = new_terrorzone['terrorZone']['highestProbabilityZone']['zone']
    logger.info('new terrorzone=' + new_terrorzone_name)
    logger.debug('new reported_amount=' + str(
        new_terrorzone['terrorZone']['highestProbabilityZone']['amount']))   
    logger.debug('EXIT Function')
    return new_terrorzone, new_terrorzone_name


# try to avoid flooding the tracker with requests. Depending on the reported amount, wait longer until next request
def update_ttl(reported_amount=0):
    global logger
    global update_job

    logger.debug('ENTER Function')
    if reported_amount > 10:
        ttl = 3600  # if there are so many votes, it's probably the correct one, not necessary to check anymore
    elif reported_amount > 3:
        ttl = reported_amount * 60
    elif reported_amount > 0:
        ttl = 60
    else:
        ttl = 30
    logger.info('new TTL=' + str(ttl))
    # recreate the tasks with the new TTL
    schedule.cancel_job(update_job)
    update_job = schedule.every(ttl).seconds.do(update_terrorzone)
    logger.debug('EXIT Function')


def main():
    global logger
    global update_job
    own_lock = False
    try:
        load_arguments(sys.argv)

        logger = setup_custom_logger()

        logger.info('')
        logger.info('=============================================')
        logger.info('MAIN SCRIPT START')
        logger.info('=============================================')
        logger.info('')

        own_lock = check_lock()
        logger.debug('own_lock=' + str(own_lock))
        load_env()

        # execute every full hour (give 15 seconds time for people to report the new terrorzone)
        schedule.every().hour.at("00:31").do(announce_terrorzone)

        # check if there is a new 'best' zone
        update_job = schedule.every().seconds.do(update_terrorzone)

        logger.info(schedule.get_jobs())

        # run indefinitely and wait for new tasks to run
        while True:
            schedule.run_pending()
            time.sleep(5)

    finally:
        if own_lock:
            path = Path(SCRIPT_HOME + '/logs')
            filepath = str(path) + '/.lock'
            os.remove(filepath)
            logger.info('lock file removed')
        logger.exception('END OF PROGRAM:')


if __name__ == "__main__":
    main()
