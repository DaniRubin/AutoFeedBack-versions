#!/usr/bin/python3
# -*- coding: UTF-8 -*-


import sys
import subprocess
import logging
import traceback
import re

FEEDBACK_MSG = 'הקובץ/קוד/טקסט נשמר בשרת בהצלחה. ציון 100 מעיד על הצלחה בשמירה, ולא מתייחס לנכונות הפתרון..'


def checking_is_staff():
    logging.debug('Checking is staff')

    username = subprocess.run(['getinput', 'username'],
                              stdout=subprocess.PIPE, check=True).stdout
    username = str(username, encoding='utf8')

    logging.debug('Username <{}>' .format(username))
    is_staff = (re.match('^s[0-9]+$', username) is None)
    logging.info('is_staff=' + str(is_staff))

    return is_staff


def main():
    subprocess.run(['feedback-msg', '-a', '-m',
                    FEEDBACK_MSG], check=True)
    subprocess.run(['feedback-result', 'success'], check=True)
    subprocess.run(['feedback-grade', '100'], check=True)


if __name__ == '__main__':
    try:
        try:
            is_staff = checking_is_staff()
        except Exception as err:
            is_staff = False
            raise err

        main()
        sys.exit(0)

    except Exception as err:

        logging.exception('Exception in main! ' + repr(err))

        text = 'התרחשה תקלה במערכת. נסו להגיש שוב. אם התקלה חוזרת, אנא פנו למדריך. '

        if is_staff:
            text += repr(err)
            text += traceback.format_exc()

        subprocess.run(['feedback-result', 'crash'], check=True)
        subprocess.run(['feedback-msg', '-a', '-m', text], check=True)

        sys.exit(-1)
