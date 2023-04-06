#!/usr/bin/env python3

# TODO: improve error handling
# TODO: Maybe async?


import os
import sys
import schedule
import time
import json
import requests
import logging
from logging.handlers import RotatingFileHandler
from discord_webhook import DiscordWebhook, DiscordEmbed
import signal

# global variables
fail_count = 0  # reduces reads from file
announced_terrorzone = 'undefined'
announced_terrorzone_name = ''
logger = logging.getLogger('')
update_job = ''
WEBHOOK_ID = ''
WEBHOOK_TOKEN = ''
ENDPOINT_TZ = ''
ENDPOINT_TOKEN = ''
CONTACT = ''
PLATFORM = ''
PUBLIC_REPO = ''


class GracefulKiller:
    kill_now = False

    def __init__(self):
        signal.signal(signal.SIGINT, self.exit_gracefully)
        signal.signal(signal.SIGTERM, self.exit_gracefully)

    def exit_gracefully(self, *args):
        self.kill_now = True


def setup_custom_logger(name='terrorzone-discord-webhook'):
    formatter = logging.Formatter(fmt='%(asctime)s %(levelname)-8s %(funcName)-20s %(message)s',
                                  datefmt='%Y-%m-%d %H:%M:%S')

    logpath = './logs/terrorzone-discord-webhook.log'
    print('logpath=' + logpath)
    custom_logger = logging.getLogger(name)
    if not os.access('./logs', os.W_OK):
        handler = logging.StreamHandler(stream=sys.stdout)
    else:
        handler = RotatingFileHandler(logpath, mode='a', maxBytes=2000000, backupCount=3)
    handler.setFormatter(formatter)
    custom_logger.addHandler(handler)

    loglevel = os.getenv("LOG_LEVEL", "DEBUG")
    if loglevel.upper() == 'INFO':
        custom_logger.setLevel(logging.INFO)
    elif loglevel.upper() == 'WARNING':
        custom_logger.setLevel(logging.WARNING)
    elif loglevel.upper() == 'ERROR':
        custom_logger.setLevel(logging.ERROR)
    elif loglevel.upper() == 'CRITICAL':
        custom_logger.setLevel(logging.CRITICAL)
    else:
        custom_logger.setLevel(logging.DEBUG)

    return custom_logger


def load_env():
    # load environment variables
    global WEBHOOK_ID
    global WEBHOOK_TOKEN
    global ENDPOINT_TZ
    global ENDPOINT_TOKEN
    global CONTACT
    global PLATFORM
    global PUBLIC_REPO

    logger.debug('ENTER Function')
    WEBHOOK_ID = os.getenv("WEBHOOK_ID")
    logger.debug('WEBHOOK_ID=' + WEBHOOK_ID)
    WEBHOOK_TOKEN = os.getenv("WEBHOOK_TOKEN")
    logger.debug('WEBHOOK_TOKEN=' + WEBHOOK_TOKEN)
    ENDPOINT_TZ = os.getenv("ENDPOINT_TZ", "https://d2runewizard.com/api/terror-zone")
    print(ENDPOINT_TZ)
    logger.debug('ENDPOINT_TZ=' + ENDPOINT_TZ)
    print(os.getenv("ENDPOINT_TOKEN"))
    ENDPOINT_TOKEN = os.getenv("ENDPOINT_TOKEN")
    logger.debug('ENDPOINT_TOKEN=' + ENDPOINT_TOKEN)
    CONTACT = os.getenv("CONTACT")
    logger.debug('CONTACT=' + CONTACT)
    PLATFORM = os.getenv("PLATFORM")
    logger.debug('PLATFORM=' + PLATFORM)
    PUBLIC_REPO = os.getenv("PUBLIC_REPO")
    logger.debug('PUBLIC_REPO=' + PUBLIC_REPO)
    logger.debug('EXIT Function')


# access the zone-info.json file to get additional area information for the current terrorzone
# create message with this information
def create_message():
    global logger
    global announced_terrorzone_name

    logger.debug('ENTER Function')
    act, immunities, monster_pack, super_uniques, sparkly_chests = ('', '', '', '', '')
    zone_found = False
    error_occurred = False
    message = ''
    zone_name = announced_terrorzone_name
    zone_info = './zone-info/zone-info.json'
    if not os.path.exists(zone_info):
        zone_info = 'zone-info.json'
    try:
        with open(zone_info) as data_file:
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

        response = webhook.execute()
        if not response.ok:
            health(False)
            logger.error('Failed to execute webhook! Response from api: ' + str(response))
            raise ConnectionError(f"{response.status_code} - {response.json()}")
        else:
            logger.info('Announce successful! New Terrorzone: ' + announced_terrorzone_name)
            health(True)
    logger.debug('EXIT Function 1')
    return 1


# if the most reported terrorzone changes, update current terrorzone
def update_terrorzone():
    global logger
    global announced_terrorzone
    global announced_terrorzone_name

    logger.debug('ENTER Function')
    # initial start of the script (assume the script was running before and discord contains that information)
    # just set announced_* without announcing when force_initial_announcement=False
    if announced_terrorzone == 'undefined':
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
    global CONTACT
    global PLATFORM
    global PUBLIC_REPO

    logger.debug('ENTER Function')

    params = {'token': ENDPOINT_TOKEN}
    headers = {'D2R-Contact': CONTACT, 'D2R-Platform': PLATFORM, 'D2R-Repo': PUBLIC_REPO}
    response = requests.get(ENDPOINT_TZ, params=params, headers=headers)
    if not response.ok:
        health(False)
        update_ttl(10)  # set new update interval to 10 minutes
        raise ConnectionError(f"{response.status_code} - {response.json()['message']}")
    else:
        health(True)

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


def health(state=False):
    global logger
    global fail_count

    logger.debug('ENTER Function')
    if state and fail_count == 0:
        logger.debug('EXIT Function 1')
        return    
    elif not state and fail_count == 1:
        logger.debug('EXIT Function 2')
        return
    elif state and fail_count == 1:
        fail_count = 0
    elif not state and fail_count == 0:
        fail_count = 1
 
    with open('health', "w") as f:
        f.write(str(fail_count))
    logger.info(f"health set to: {str(fail_count)}")
    logger.debug('EXIT Function')


def main():
    global logger
    global update_job

    logger = setup_custom_logger()

    logger.info('')
    logger.info('=============================================')
    logger.info('MAIN SCRIPT START')
    logger.info('=============================================')
    logger.info('')

    load_env()

    # execute every full hour (give 31 seconds time for people to report the new terrorzone)
    schedule.every().hour.at("00:31").do(announce_terrorzone)

    # check if there is a new 'best' zone
    update_job = schedule.every().seconds.do(update_terrorzone)

    logger.info(schedule.get_jobs())

    # run indefinitely and wait for new tasks to run
    killer = GracefulKiller()
    while not killer.kill_now:
        schedule.run_pending()
        time.sleep(5)
    print()
    logger.info("End of container. Stopped gracefully :)")  # timeout needs to be 30+sec


if __name__ == "__main__":
    main()
