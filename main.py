# Welcome to the Recognition Rabbit. The code here is pretty embarrassing :)
import datetime
import pickle
from slackclient import SlackClient
import time


SLACK_TOKEN = 'your-slack-token'
NOT_A_DB_FILE = 'why_am_i_not_using_a_database.pkl'


# There isn't even a reason for this to be a class.
class RecognitionTracker(object):
    def __init__(self):
        try:
            self.thanks = pickle.load(open(NOT_A_DB_FILE, 'rb'))
        except:
            self.thanks = {}

        self.current_date = (datetime.datetime.now() -
                             datetime.timedelta(hours=17)).date()


def main():
    sc = SlackClient(SLACK_TOKEN)
    rt = RecognitionTracker()
    if sc.rtm_connect():
        while True:
            messages = sc.rtm_read()
            for message in messages:
                # Process message

                time.sleep(1)
    else:
        print "Oh noes, the sadness commences!"


if __name__ == "__main__":
    main()