# slackbot
import os
import datetime
from flask import Flask, request, jsonify
import requests
from slackclient import SlackClient
import json

# gsheets
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# decorators
from decorators import channel, arguments, command, threaded
import decorators

# database
import database

# etc
import logging
import pprint
from threading import Thread
import time

PROD = int(os.environ.get('PROD'))

# https://www.fullstackpython.com/blog/build-first-slack-bot-python.html
# https://github.com/slackapi/python-message-menu-example/blob/master/example.py

# instantiate Slack client
if PROD:
    slack_client = SlackClient(os.environ.get('SLACK_BOT_TOKEN_PROD'))
    SLACK_SIGNING_SECRET = os.environ.get("SLACK_BOT_SIGNING_SECRET_PROD")
else:
    slack_client = SlackClient(os.environ.get('SLACK_BOT_TOKEN_DEBUG'))
    SLACK_SIGNING_SECRET = os.environ.get("SLACK_BOT_SIGNING_SECRET_DEBUG")

# instantiate google sheets
sheet = None
client = None

# google sheets constants
FLYERING_DATES_ROW = 17
FLYERING_DATES_COLUMN_START = 3
FLYERING_DATES_COLUMN_END = 11
FLYERING_ROW_START = 18
FLYERING_ROW_END = 118
MAX_PER_SHIFT = 4
# https://github.com/datadesk/slack-buttons-example/blob/master/app.py

# Flask
app = Flask(__name__)

# TODO security: https://api.slack.com/docs/verifying-requests-from-slack


def col_from_date(date):
    DATE_COLUMN = None

    # look up the correct column
    schedule_dates = sheet.range(FLYERING_DATES_ROW,
                                 FLYERING_DATES_COLUMN_START,
                                 FLYERING_DATES_ROW, FLYERING_DATES_COLUMN_END)
    for d in schedule_dates:
        if date in d.value:
            DATE_COLUMN = d.col
            break

    return DATE_COLUMN


def row_from_time(time):
    TIME_ROW = None

    # look up the correct column
    schedule_times = sheet.range(FLYERING_ROW_START, 1, FLYERING_ROW_END, 1)
    for t in schedule_times:
        if time == t.value[0:len(time)]:
            TIME_ROW = t.row
            break

    return TIME_ROW


@command
@arguments([2])
@channel(["shifts"])
def sub(channel, user, command_parts, response_url):
    sub_helper(channel, user, command_parts, response_url)
    return jsonify(text="Handling substitute.")


@threaded
def sub_helper(channel, user, command_parts, response_url):
    """
    *sub* <date> <time>
    > Handles shift substitutes
    """
    # TODO: add time check for past
    date = None
    time = None

    def get_response(channel, user, command_parts):
        nonlocal date, time
        client.login()

        (date, time) = command_parts
        TIME_ROW = row_from_time(time)
        DATE_COLUMN = col_from_date(date)

        if TIME_ROW is None and DATE_COLUMN is None:
            return "Invalid start time and date specified."
        elif TIME_ROW is None:
            return "Invalid start time specified."
        elif DATE_COLUMN is None:
            return "Invalid date specified."

        name = database.id_to_name(user)
        if name is None:
            return "ERROR: Please rerun register-users"

        schedule_people = sheet.range(TIME_ROW, DATE_COLUMN,
                                      TIME_ROW + MAX_PER_SHIFT, DATE_COLUMN)
        schedule_times = sheet.range(TIME_ROW + 1, 1,
                                     TIME_ROW + MAX_PER_SHIFT + 1, 1)
        person = None
        for t, p in zip(schedule_times, schedule_people):
            print(p.value, name, t)
            # if p.value.split(" ")[0] == name:
            if p.value[0:len(name)] == name:
                person = p
                break
            if t.value != "":
                break

        if person is None:
            return "Either couldn't find you on the schedule, or you are already looking for a substitute."

        sheet.update_cell(person.row, person.col, f'{name}*')

    response = get_response(channel, user, command_parts)
    if response:
        requests.post(
            response_url,
            json={
                "response_type": 'ephemeral',
                "text": f'{response}',
            })
    else:
        requests.post(
            response_url,
            json={
                "response_type":
                'in_channel',
                "text":
                '',
                "attachments": [{
                    "text":
                    f'<!channel> If anyone can substitute for <@{user}> on {date} {time}, please click the button below.',
                    "callback_id":
                    f'take-shift|{user}|{date}|{time}',
                    "color":
                    "#3AA3E3",
                    "attachment_type":
                    "default",
                    "actions": [{
                        "name": "take_shift",
                        "text": ":heavy_check_mark: Take Shift",
                        "type": "button",
                        "value": "take_shift"
                    }]
                }]
            })


@command
@channel(["shifts"])
def unsub(channel, user, command_parts, response_url):
    unsub_helper(channel, user, command_parts, response_url)
    return jsonify(text="Deleting your substitute request.")


@threaded
def unsub_helper(channel, user, command_parts, response_url):
    """
    *unsub* <date> <time>
    > Handles shift substitutes
    > user: str (user id)
    > command_parts: tuple of (day, shift time), both str
    """

    # TODO: add time check for past
    def get_response(channel, user, command_parts):
        client.login()

        (date, time) = command_parts
        TIME_ROW = row_from_time(time)
        DATE_COLUMN = col_from_date(date)

        if TIME_ROW is None and DATE_COLUMN is None:
            return "Invalid start time and date specified."
        elif TIME_ROW is None:
            return "Invalid start time specified."
        elif DATE_COLUMN is None:
            return "Invalid date specified."

        name = database.id_to_name(user)
        if name is None:
            return "ERROR: Please rerun register-users"

        schedule_people = sheet.range(TIME_ROW, DATE_COLUMN,
                                      TIME_ROW + MAX_PER_SHIFT, DATE_COLUMN)
        schedule_times = sheet.range(TIME_ROW + 1, 1,
                                     TIME_ROW + MAX_PER_SHIFT + 1, 1)
        person = None
        for t, p in zip(schedule_times, schedule_people):
            # if p.value.split(" ")[0][:-1] == name:
            if p.value[0:len(name)] == name:
                person = p
                break
            if t.value != "":
                break

        if person is None:
            return "Either couldn't find you on the schedule, or you are not looking for a substitute already."

        sheet.update_cell(person.row, person.col, f'{name}')

        return f'Not looking for substitutes for <@{user}> anymore.'

    response = get_response(channel, user, command_parts)
    requests.post(
        response_url,
        json={
            "response_type": 'in_channel',
            "text": f'{response}',
        })


@command
@channel(["shifts"])
def take_shift(channel, user, command_parts, response_url):
    take_shift_helper(channel, user, command_parts, response_url)
    return "Handling shift replacement."


@threaded
def take_shift_helper(channel, user, command_parts, response_url):
    """
    *take_shift* <user> <date> <time>
    > Handles shift substitutes
    > user: str (user id)
    > command_parts: tuple of (day, shift time), both str
    """

    # TODO: add time check for past
    # TODO: check that they aren't already in that shift
    def get_response(channel, user, command_parts):
        client.login()

        (user_to_replace, date, time) = command_parts
        # user_to_replace = user_to_replace[2:-1].split("|")[0] # gets rid of <@>
        TIME_ROW = row_from_time(time)
        DATE_COLUMN = col_from_date(date)

        if TIME_ROW is None and DATE_COLUMN is None:
            return "Invalid start time and date specified."
        elif TIME_ROW is None:
            return "Invalid start time specified."
        elif DATE_COLUMN is None:
            return "Invalid date specified."

        name = database.id_to_name(user_to_replace)
        if name is None:
            return "ERROR: Please rerun register-users"

        schedule_people = sheet.range(TIME_ROW, DATE_COLUMN,
                                      TIME_ROW + MAX_PER_SHIFT, DATE_COLUMN)
        schedule_times = sheet.range(TIME_ROW + 1, 1,
                                     TIME_ROW + MAX_PER_SHIFT + 1, 1)
        person = None
        for t, p in zip(schedule_times, schedule_people):
            # if p.value.split(" ")[0][:-1] == name:
            if p.value[0:len(name)] == name and "*" in p.value:
                person = p
                break
            if t.value != "":
                break

        if person is None:
            return "Either the user you specified has already found a replacement, or is not looking for one."

        sheet.update_cell(person.row, person.col,
                          f'{database.id_to_name(user)}')
        return f'<@{user_to_replace}>\'s {date} {time} shift replaced by <@{user}>'

    requests.post(
        response_url,
        json={
            "response_type": 'in_channel',
            "text": get_response(channel, user, command_parts),
        })


@command
@channel(["shift-managers"])
def register_users(channel, user, command_parts, response_url):
    """
    *register_users*
    > Registers users to database
    > Puts in both ids -> name and name -> id.
    > In the case of first name collisions, last names will be used.
    > This is to ensure consistency with the spreadsheet
    """
    members = slack_client.api_call("users.list")["members"]
    for member in members:
        if member["deleted"]:
            continue
        user_id = member["id"]
        name = member["real_name"].split(" ")
        if name[0] != "Neil":
            user_name = name[0]
        else:
            user_name = name[1]
        user = {"name": user_name, "id": user_id}
        database.add_user(user)
    return "Registered names to IDs."


@command
@arguments([3])
@channel(["shift-managers"])
def noshow(channel, user, command_parts, response_url):
    noshow_helper(channel, user, command_parts, response_url)
    return jsonify(text="Handling noshow.")


@threaded
def noshow_helper(channel, user, command_parts, response_url):
    """
    *noshow* <user>
    > Marks user as noshow on spreadsheet
    """

    def get_response(channel, user, command_parts, response_url):
        client.login()

        (checkoff_user, date, time) = command_parts
        checkoff_user = checkoff_user[2:-1].split("|")[0]  # gets rid of <@>
        TIME_ROW = row_from_time(time)
        DATE_COLUMN = col_from_date(date)

        if TIME_ROW is None and DATE_COLUMN is None:
            return "Invalid start time and date specified."
        elif TIME_ROW is None:
            return "Invalid start time specified."
        elif DATE_COLUMN is None:
            return "Invalid date specified."

        name = database.id_to_name(checkoff_user)
        if name is None:
            return "ERROR: Please rerun register-users"

        schedule_people = sheet.range(TIME_ROW, DATE_COLUMN,
                                      TIME_ROW + MAX_PER_SHIFT, DATE_COLUMN)
        schedule_times = sheet.range(TIME_ROW + 1, 1,
                                     TIME_ROW + MAX_PER_SHIFT + 1, 1)
        person = None
        for t, p in zip(schedule_times, schedule_people):
            # if p.value.split(" ")[0] == name:
            if p.value[0:len(name)] == name:
                person = p
                break
            if t.value != "":
                break

        if person is None:
            return "Either that user did not have this shift, or is already marked off."

        sheet.update_cell(person.row, person.col,
                          f'{database.id_to_name(checkoff_user)} NOSHOW')

        return f'<@{checkoff_user}> marked as noshow by <@{user}>'

    requests.post(
        response_url,
        json={
            "response_type": 'in_channel',
            "text": get_response(channel, user, command_parts, response_url)
        })


@command
@arguments([0])
def register_channel(channel, user, command_parts, response_url):
    """
    *register-channel*
    > Registers channel for script to use
    """
    channel_name = slack_client.api_call(
        "channels.info", channel=channel)["channel"]["name"]
    channel_id = channel
    channel = {"name": channel_name, "id": channel_id}
    database.add_channel(channel)
    return f'Channel registered as {channel_id}'


@command
@arguments([1, 2])
@channel(["shift-managers", "shifts"])
def shifts(channel, user, command_parts, response_url):
    shifts_helper(channel, user, command_parts, response_url)
    return jsonify(text="Finding shifts.")


@threaded
def shifts_helper(channel, user, command_parts, response_url):
    """
    *shifts* <date>
    > Returns shifts from given date
    """

    def get_response(channel, user, command_parts):
        client.login()

        date = command_parts[0]
        notify = len(command_parts) == 2 and "notify" in command_parts[1]
        DATE_COLUMN = col_from_date(date)

        if DATE_COLUMN is None:
            return "Invalid date."

        # Get shifts
        shifts = {}
        timeshift_data = sheet.range(FLYERING_ROW_START, DATE_COLUMN,
                                     FLYERING_ROW_END, DATE_COLUMN)
        shift_times = sheet.range(FLYERING_ROW_START, 1, FLYERING_ROW_END, 1)
        current_shifts = []
        for shift, time in zip(timeshift_data, shift_times):
            shift, time = shift.value, time.value
            if time != "":
                current_shifts = []
                shifts[time] = current_shifts

            user = ""
            if shift is not "":
                if shift[-1] == "*":
                    shift = shift[:-1]
                user_id = database.name_to_id(shift)
                if user_id and notify:
                    user = f'<@{user_id}>'
                else:
                    user = shift
            if user:
                current_shifts.append(user)

        output = f'Shifts for *{date}*:\n'
        for time, shift in shifts.items():
            if shift:
                people = ", ".join(shift)
                time = time.replace("\n", " ")
                output += f'*{time}*: {people}\n'
        return output

    requests.post(
        response_url,
        json={
            "response_type": 'in_channel',
            "text": get_response(channel, user, command_parts)
        })


@command
@channel(["shift-managers"])
@arguments([0])
def clean(channel, user, command_parts, response_url):
    """
    *clean*
    > Drops all databases.
    > Don't use if you don't know what you're doing
    """
    database.clean_database()
    return "Cleaned database."


@command
@arguments([0])
def help(channel, user, command_parts, response_url):
    """
    *help*
    > Help pages
    """
    return "*To find sub*: sub <date> <time>\n*To take shift*: take-shift <user> <date> <time>\n*To show shifts*: shifts <today | tomorrow | date>"


@command
@arguments([0])
def all_commands(channel, user, command_parts, response_url):
    """
    *all-commands*
    > Prints all commands
    """
    output = ""
    for title, content in decorators.help_pages.items():
        output += f'{content}\n'
    return output


@app.route('/action-endpoint', methods=['POST'])
def action_endpoint():
    payload = json.loads(request.form["payload"])
    (command, *command_parts) = payload["callback_id"].split("|")
    channel_id = payload["channel"].get("id")
    user_id = payload["user"].get("id")
    response_url = payload["response_url"]
    pprint.pprint(payload)
    if command in decorators.valid_commands:
        return decorators.valid_commands[command](
            channel=channel_id,
            user=user_id,
            command_parts=command_parts,
            response_url=response_url)
    return "Unimplemented"


@app.route('/commands', methods=['POST'])
def commands():
    """
    Handle slash commands
    """
    payload = request.form
    command = payload.get("command")[1:]
    text = payload.get("text")
    response_url = payload.get("response_url")
    user_id = payload.get("user_id")
    channel_id = payload.get("channel_id")
    response_url = payload.get("response_url")

    response = "None"
    print(text)
    if command in decorators.valid_commands:
        response = decorators.valid_commands[command](
            channel=channel_id,
            user=user_id,
            command_parts=(text.split(" ") if text else []),
            response_url=response_url)

    return response


@app.route("/")
def root():
    return "OK"


def main():
    global bot_id
    global sheet, client

    # authenticate with api
    scope = [
        'https://spreadsheets.google.com/feeds',
        'https://www.googleapis.com/auth/drive'
    ]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(
        json.loads(os.environ.get('GOOGLE_API_CREDS')), scope)
    client = gspread.authorize(creds)
    sheet = client.open("Spring 2019 Recruitment Master").sheet1

    database.load_database()
    print("CHANNELS:", [record for record in database.channels.find()])
    print("USERS:", [record for record in database.users.find()])

    if PROD:
        website = os.environ.get('WEBSITE_PROD')
    else:
        website = os.environ.get('WEBSITE_DEBUG')


main()

if __name__ == '__main__':
    try:
        app.run()
    except KeyboardInterrupt:
        print('Shutting Down')
    except:
        logging.exception("Fatal Exception Occurred")
