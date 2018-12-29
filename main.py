# slackbot
from flask import Flask, request, make_response, Response
import os
import json
import time
import re
from slackclient import SlackClient
import datetime

# gsheets
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# decorators
from decorators import check_channel, parameters

# database
import database

# etc
import logging
import json

PROD = int(os.environ.get('PROD'))

# https://www.fullstackpython.com/blog/build-first-slack-bot-python.html
# https://github.com/slackapi/python-message-menu-example/blob/master/example.py

# instantiate Slack client
if PROD:
    slack_client = SlackClient(os.environ.get('SLACK_BOT_TOKEN_PROD'))
else:
    slack_client = SlackClient(os.environ.get('SLACK_BOT_TOKEN_DEBUG'))
bot_id = None

RTM_READ_DELAY = 1 # 1 second delay between reading from RTM
MENTION_REGEX = "^<@(|[WU].+?)>(.*)"

# instantiate google sheets
sheet = None

# google sheets constants
FLYERING_DATES_ROW = 18
FLYERING_DATES_COLUMN_START = 3
FLYERING_DATES_COLUMN_END = 11
FLYERING_ROW_START = 19
FLYERING_ROW_END = 86
TABLING_ROW_START = 24
TABLING_ROW_END = 83
MAX_PER_SHIFT = 4

def col_from_date(date):
    DATE_COLUMN = None

    # look up the correct column
    schedule_dates = sheet.range(FLYERING_DATES_ROW, FLYERING_DATES_COLUMN_START, FLYERING_DATES_ROW, FLYERING_DATES_COLUMN_END)
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

def parse_bot_commands(slack_events):
    """
    Looks through all commands and chooses to parse only @mentions
    Calls parse_direct_mention with actual message content
    """
    for event in slack_events:
        print(event)
        if event["type"] == "message" and not "subtype" in event:
            user_id, message = parse_direct_mention(event["text"])
            if user_id == bot_id:
                return message, event["channel"], event["user"]
    return None, None, None

def parse_direct_mention(message):
    """
    Parses @mentions
    """
    matches = re.search(MENTION_REGEX, message)
    # the first group contains the username, the second group contains the remaining message
    return (matches.group(1), matches.group(2).strip()) if matches else (None, None)

def handle_command(input_string, channel, user):
    """
    Executes bot command if the command is known
    """
    # Default response is help text for the user
    default_response = "Not sure what you mean. Try *help*."

    response = None
    # handle responses here
    print(f'command: {input_string}, channel: {channel}, user: {user}')

    (command, *command_parts) = input_string.split(" ")

    if command == "sub":
        if len(command_parts) == 2:
            response = sub(channel=channel, user=user, shift=command_parts)
        else:
            response = "Syntax is *@Shift Manager sub <date> <time>*\nFor example, try @Shift Manager 1/27 10:30"

    elif command == "unsub":
        if len(command_parts) == 2:
            response = unsub(channel=channel, user=user, shift=command_parts)
        else:
            response = "Syntax is *@Shift Manager unsub <date> <time>*\nFor example, try @Shift Manager 1/27 10:30"

    elif command == "take-shift":
        if len(command_parts) == 3:
            response = take_shift(channel=channel, user=user, shift=command_parts)
        else:
            response = "Syntax is *@Shift Manager take-shift <user> <time>*"

    elif command == "register-channel":
        if len(command_parts) == 1:
            response = register_channel(command_parts[0], channel)
        else:
            response = "Syntax was incorrect."

    elif command == "register-users":
        if len(command_parts) == 0:
            response = register_users(channel)
        else:
            response = "Syntax was incorrect."

    elif command == "noshow":
        if len(command_parts) == 3:
            response = noshow(channel=channel, user=user, shift=command_parts)
        else:
            response = "Syntax is *@Shift Manager noshow <user> <date> <time>*"

    elif command == "shifts":
        if len(command_parts) == 1:
            if command_parts[0] == "today":
                response = get_shifts(channel=channel, date=f'{datetime.date.today():%-m/%-d}')
            elif command_parts[0] == "tomorrow":
                response = get_shifts(channel=channel, date=f'{datetime.date.today()+datetime.timedelta(days=1):%-m/%-d}')
            else:
                response = get_shifts(channel=channel, date=command_parts[0])
        else:
            response = "Syntax was incorrect."

    elif command == "clean":
        response = clean_database()

    elif command == "help":
        response = help()

    # # testing something out
    # username = slack_client.api_call(
    #     "users.info",
    #     user=user
    # )['user']['profile']['display_name'] or None
    # response = f'@{username}'

    # Sends the response back to the channel
    slack_client.api_call(
        "chat.postMessage",
        channel=channel,
        text=response or default_response
    )

@check_channel("shifts")
def sub(channel, user, shift):
    """
    /sub <date> <time>
    """
    # TODO: add time check for past
    """
    Handles shift substitutes
    user: str (user id)
    shift: tuple of (day, shift time), both str
    """
    (date, time) = shift
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

    schedule_people = sheet.range(TIME_ROW, DATE_COLUMN, TIME_ROW+MAX_PER_SHIFT, DATE_COLUMN)
    schedule_times = sheet.range(TIME_ROW+1, 1, TIME_ROW+MAX_PER_SHIFT+1, 1)
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
        return "Either couldn't find you on the schedule, or you are already looking for a substitute.."

    sheet.update_cell(person.row, person.col, f'{name}*')

    return f'If anyone can substitute for <@{user}>, please respond with *@Shift Manager take-shift <@{user}> {date} {time}*'

@check_channel("shifts")
def unsub(channel, user, shift):
    """
    Handles shift substitutes
    user: str (user id)
    shift: tuple of (day, shift time), both str
    TODO: add time check for past
    """
    (date, time) = shift
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

    schedule_people = sheet.range(TIME_ROW, DATE_COLUMN, TIME_ROW+MAX_PER_SHIFT, DATE_COLUMN)
    schedule_times = sheet.range(TIME_ROW+1, 1, TIME_ROW+MAX_PER_SHIFT+1, 1)
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

@check_channel("shifts")
def take_shift(channel, user, shift):
    """
    Handles shift substitutes
    user: str (user id)
    shift: tuple of (day, shift time), both str
    TODO: add time check for past
    TODO: check that they aren't already in that shift
    """
    (user_to_replace, date, time) = shift
    user_to_replace = user_to_replace[2:-1] # gets rid of @<>
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

    schedule_people = sheet.range(TIME_ROW, DATE_COLUMN, TIME_ROW+MAX_PER_SHIFT, DATE_COLUMN)
    schedule_times = sheet.range(TIME_ROW+1, 1, TIME_ROW+MAX_PER_SHIFT+1, 1)
    person = None
    for t, p in zip(schedule_times, schedule_people):
        print(t, p, name)
        # if p.value.split(" ")[0][:-1] == name:
        if p.value[0:len(name)] == name:
            person = p
            break
        if t.value != "":
            break

    if person is None:
        return "Either the user you specified has already found a replacement, or is not looking for one."

    sheet.update_cell(person.row, person.col, f'{database.id_to_name(user)}')

    return f'<@{user_to_replace}>\'s {date} {time} shift replaced by <@{user}>'

@check_channel("shift-managers")
def register_users(channel):
    """
    Registers users to database
    Puts in both ids -> name and name -> id.
    In the case of first name collisions, last names will be used.
    This is to ensure consistency with the spreadsheet
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

@check_channel("shift-managers")
def noshow(channel, user, shift):
    (checkoff_user, date, time) = shift
    checkoff_user = checkoff_user[2:-1] # gets rid of @<>
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

    schedule_people = sheet.range(TIME_ROW, DATE_COLUMN, TIME_ROW+MAX_PER_SHIFT, DATE_COLUMN)
    schedule_times = sheet.range(TIME_ROW+1, 1, TIME_ROW+MAX_PER_SHIFT+1, 1)
    person = None
    for t, p in zip(schedule_times, schedule_people):
        print(t, p, name)
        # if p.value.split(" ")[0] == name:
        if p.value[0:len(name)] == name:
            person = p
            break
        if t.value != "":
            break

    if person is None:
        return "Either that user did not have this shift, or is already marked off."

    sheet.update_cell(person.row, person.col, f'{database.id_to_name(user)} NOSHOW')

    return f'<@{checkoff_user}> marked as noshow by <@{user}>'

    return "Not implemented yet."

def register_channel(channel_name, channel_id):
    channel = {"name": channel_name, "id": channel_id}
    database.add_channel(channel)
    return f'Channel registered as {channel_id}'

@check_channel("shifts")
def get_shifts(date, channel):
    """
    Returns shifts from given date
    """

    DATE_COLUMN = col_from_date(date)

    if DATE_COLUMN is None:
        return "Invalid date."

    # Get shifts
    shifts = {}
    timeshift_data = sheet.range(FLYERING_ROW_START, DATE_COLUMN, FLYERING_ROW_END, DATE_COLUMN)
    shift_times = sheet.range(FLYERING_ROW_START, 1, FLYERING_ROW_END, 1)
    current_time = None
    current_shifts = []
    for shift, time in zip(timeshift_data, shift_times):
        shift, time = shift.value, time.value
        if time != "":
            if current_time != None:
                shifts[current_time] = current_shifts
            current_time = time
            current_shifts = []

        user = "N/A"
        if shift is not "":
            if shift[-1] == "*":
                shift = shift[:-1]
            user_id = database.name_to_id(shift)
            if user_id:
                user = f'<@{user_id}>'
            else:
                user = shift
        current_shifts.append(user)

    output = ""
    for time, shift in shifts.items():
        people = ", ".join(shift)
        output += f'*{time}*: {people}\n'
    return output

def clean_database():
    database.clean_database()
    return "Cleaned database."

def help():
    return "*To find sub*: sub <date> <time>\n*To take shift*: take-shift <user> <date> <time>\n*To show shifts*: shifts <today | tomorrow | date>"

def main():
    global bot_id
    global sheet

    # authenticate with api
    scope = ['https://spreadsheets.google.com/feeds',
             'https://www.googleapis.com/auth/drive']
    creds = ServiceAccountCredentials.from_json_keyfile_dict(json.loads(os.environ.get('GOOGLE_API_CREDS')), scope)
    client = gspread.authorize(creds)
    sheet = client.open("Spring 2019 Recruitment Master").sheet1

    database.load_database()
    print("CHANNELS:", [record for record in database.channels.find()])
    print("USERS:", [record for record in database.users.find()])

    # slack portion
    if slack_client.rtm_connect(with_team_state=False):
        print("VCG ON ME VCG ON 3")
        bot_id = slack_client.api_call("auth.test")["user_id"]
        while True:
            command, channel, user = parse_bot_commands(slack_client.rtm_read())
            if command:
                handle_command(command, channel, user)
            time.sleep(RTM_READ_DELAY)
    else:
        print("Connection failed. Exception traceback printed above.")

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print('Shutting Down')
    except:
        logging.exception("Fatal Exception Occurred")
