# Welcome to the Recognition Rabbit. The code here is pretty embarrassing :)
from collections import OrderedDict
import datetime
import pickle
import re
from slackclient import SlackClient
import time


SLACK_TOKEN = 'your-slack-token'
NOT_A_DB_FILE = 'why_am_i_not_using_a_database.pkl'

# Map between the channel the bot lives in and a triple of the form:
# ("Preferred Bot Username", ":preferred-emoji:", "Preferred Bot Identifier")
CHANNEL_INFO = {
    'CXXXXXXX1': ("Recognition Rabbit", ":rabbit:", "rabbit"),
    'CXXXXXXX2': ("Karma Chameleon", ":chameleon:", "karma")
}

# A list of names that the bot responds to for triggering commands.
# These will be case-sensitive and strip dashes (e.g. "T-rex" will trigger
# the bot along with "trex").
VALID_IDENTIFIERS = ["rabbit", "recognitionrabbit", "karma"]


# There isn't even a reason for this to be a class.
class RecognitionTracker(object):
    def __init__(self):
        try:
            self.thanks = pickle.load(open(NOT_A_DB_FILE, 'rb'))
        except:
            self.thanks = {}

        self.current_date = (datetime.datetime.now() -
                             datetime.timedelta(hours=17)).date()

    def generate_thanks(self, awarder, awardee, award_text):
        return [{
            "pretext": ("Way to go, %s, you're awesome: %s" %
                        (awardee, award_text)),
        }]

    def give_thanks(self, message, awarder, channel):
        split_message = message.split()
        if split_message and len(split_message) > 3:
            awardee = split_message[2].lower()
            award_text = " ".join(split_message[3:])

            if channel not in self.thanks:
                self.thanks[channel] = OrderedDict()

            if self.current_date not in self.thanks[channel]:
                self.thanks[channel][self.current_date] = {}

            if awardee not in self.thanks[channel][self.current_date]:
                self.thanks[channel][self.current_date][awardee] = []

            # Apparently unicode apostrophes are pretty common
            award_text = re.sub(u"\u2019", "'", award_text)
            award_text = award_text.encode('ascii', 'ignore')
            self.thanks[channel][self.current_date][awardee].append(
                award_text)

            return self.generate_thanks(awarder, awardee, award_text)


def is_valid_message(message):
    return (message.get("type") == "message" and
            message.get("text"))


def is_valid_identifier(identifier):
    return re.sub('[@|-]', '', identifier).lower() in VALID_IDENTIFIERS


def is_thanks(message):
    split_message = message["text"].split()
    return (split_message and len(split_message) >= 4 and
            is_valid_identifier(split_message[0]) and
            split_message[1].lower() == 'thanks')


def main():
    sc = SlackClient(SLACK_TOKEN)
    rt = RecognitionTracker()
    if sc.rtm_connect():
        while True:
            messages = sc.rtm_read()
            for message in messages:
                # It only watches the channels it's in, but to be extra
                # careful here.
                channel = message.get("channel")
                if not channel or channel not in CHANNEL_INFO.keys():
                    continue

                if is_valid_message(message):
                    if is_thanks(message):
                        message_to_write = rt.give_thanks(message['text'],
                                                          message['user'],
                                                          channel)

                if message_to_write:
                    sc.api_call("chat.postMessage", channel=channel,
                                username=CHANNEL_INFO[channel][0],
                                icon_emoji=CHANNEL_INFO[channel][1],
                                attachments=message_to_write)

                time.sleep(1)
    else:
        print "Oh noes, the sadness commences!"


if __name__ == "__main__":
    main()