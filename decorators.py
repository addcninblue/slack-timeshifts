import database

# checks channel
def check_channel(channel_check):
    def decorator_checked_channel(func):
        def wrapper_function(channel, *args, **kwargs):
            if database.data["channels"].get(channel) == channel_check:
                return func(channel=channel, *args, **kwargs)
            return "Bad permissions"
        return wrapper_function
    return decorator_checked_channel

def parameters(args, error_message="Number of parameters incorrect."):
    def decorator_checked_parameters(func):
        def wrapper_function(*args, **kwargs):
            print(args)
            print(len(args))
            if len(args) not in args:
                return error_message
            return func(*args, **kwargs)
        return wrapper_function
    return decorator_checked_parameters
