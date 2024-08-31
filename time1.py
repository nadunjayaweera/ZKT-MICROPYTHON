from datetime import datetime

def decode(time):
    """
    Decode a time integer into a datetime object.
    
    :param time: The encoded time as an integer.
    :return: A datetime object representing the decoded time.
    """
    second = time % 60
    time = (time - second) // 60

    minute = time % 60
    time = (time - minute) // 60

    hour = time % 24
    time = (time - hour) // 24

    day = time % 31 + 1
    time = (time - (day - 1)) // 31

    month = time % 12
    time = (time - month) // 12

    year = time + 2000

    return datetime(year, month + 1, day, hour, minute, second)

def encode(date):
    """
    Encode a datetime object into a time integer.
    
    :param date: A datetime object representing the date and time.
    :return: The encoded time as an integer.
    """
    return (
        ((date.year % 100) * 12 * 31 + date.month * 31 + date.day - 1) * (24 * 60 * 60) +
        (date.hour * 60 + date.minute) * 60 +
        date.second
    )
