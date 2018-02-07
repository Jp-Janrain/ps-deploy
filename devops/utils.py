def prompt_yn(question, default=None):
    """Ask a yes/no question in the terminal.

    "question" is a string that is presented to the user.
    "default" is the presumed answer if the user just hits <Enter>.

    The "answer" return value is True for "yes" or False for "no".
    """
    valid = {"yes": True, "y": True, "ye": True,
             "no": False, "n": False}
    if default is None:
        question += " [y/n] "
    elif default is True:
        question += " [Y/n] "
    elif default is False:
        question += " [y/N] "
    else:
        raise ValueError("invalid default answer: {}".format(repr(default)))

    while True:
        choice = raw_input(question).lower()
        if default is not None and choice == '':
            return default
        elif choice in valid:
            return valid[choice]
        else:
            print "Please respond with 'yes' or 'no' (or 'y' or 'n')."


def aws2dict(lst):
    return {item['Key']: item['Value'] for item in lst}


def dict2aws(dct):
    return [{'Key': k, 'Value': v} for k, v in dct.iteritems()]

