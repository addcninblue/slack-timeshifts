import database
from functools import wraps

valid_commands = {}

# checks channel
def channel(channel_check):
    def decorator_checked_channel(func):
        @wraps(func)
        def wrapper_function(channel, *args, **kwargs):
            if database.id_to_channel(channel) in channel_check:
                return func(channel=channel, *args, **kwargs)
            return "Bad permissions"
        return wrapper_function
    return decorator_checked_channel

def arguments(params, error_message="Number of parameters incorrect."):
    def decorator_checked_parameters(func):
        @wraps(func)
        def wrapper_function(command_parts, *args, **kwargs):
            print(command_parts)
            print(len(command_parts))
            if len(command_parts) not in params:
                return error_message
            return func(command_parts=command_parts, *args, **kwargs)
        return wrapper_function
    return decorator_checked_parameters

def command(func):
    name = func.__name__.replace("_", "-")
    valid_commands[name] = func
    def wrapper_function(*args, **kwargs):
        return func(*args, **kwargs)
    return wrapper_function
