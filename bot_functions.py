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

    if command in decorators.valid_commands:
        response = decorators.valid_commands[command](
            channel=channel,
            user=user,
            command_parts=command_parts
        )

    # Sends the response back to the channel
    slack_client.api_call(
        "chat.postMessage",
        channel=channel,
        text=response or default_response
    )
