# Welcome to the Recognition Rabbit. The code here is pretty embarrassing :)
import boto3
from collections import OrderedDict
import datetime
import os
import pickle
import re
from slackclient import SlackClient
import time


SLACK_TOKEN = 'your-slack-token'
BUCKET_NAME = "recognition-bot"
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
            if not os.path.exists(NOT_A_DB_FILE):
                self.download_file_from_s3()

            self.thanks = pickle.load(open(NOT_A_DB_FILE, 'rb'))
        except:
            self.thanks = {}
            self.upload_file_to_s3()

        self.current_date = (datetime.datetime.now() -
                             datetime.timedelta(hours=17)).date()

    # Why S3 you might ask? Well, allow me to begin.... The story begins with
    # a naive version of myself wanting to build a cool new bot. But, you see,
    # the true me is also a victim of "laziness". Thus, pickled files. But,
    # I also wanted to use heroku. Thus, ephemeral storage. For some reason,
    # I ended up sending things off to S3 instead of building a proper
    # database. This was, of course, a terrible choice. But, you know.....
    def download_file_from_s3(self):
        s3 = boto3.client('s3')
        s3.download_file(BUCKET_NAME, NOT_A_DB_FILE, NOT_A_DB_FILE)

    def upload_file_to_s3(self):
        s3 = boto3.client('s3')
        pickle.dump(self.thanks, open(NOT_A_DB_FILE, 'wb'))
        s3.upload_file(NOT_A_DB_FILE, BUCKET_NAME, NOT_A_DB_FILE)

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

            try:
                self.upload_file_to_s3()
            except:
                pass

            return self.generate_thanks(awarder, awardee, award_text)

    def get_summary(self, channel):
        map_most_recent_entries = {}
        for current_date, day_info in self.thanks.get(channel, {}).iteritems():
            for name, messages in day_info.iteritems():
                map_most_recent_entries[name] = messages[-1]

        most_recent_entries = [{
            "pretext": ("Check out the collective awesomeness of everyone "
                        " on the team:"),
        }]
        for name, message in map_most_recent_entries.iteritems():
            most_recent_entries.append({
                "color": "good",
                "mrkdwn_in": ["text"],
                "text": "*" + str(name) + "*: " + str(message)
            })

        return most_recent_entries

    def get_daily(self, channel, override=False):
        today_entries = [{
            "pretext": ("Check out all the awesome things folks have" +
                        " done in the past day:"),
        }]
        for name, messages in self.thanks.get(channel, {}).get(
                self.current_date, {}).iteritems():
            for message in messages:
                today_entries.append({
                    "color": "good",
                    "mrkdwn_in": ["text"],
                    "text": "*" + str(name) + "*: " + str(message)
                })

        return today_entries if len(today_entries) > 1 or override else None

    def get_help(self, channel):
        return [{
            "pretext": "Welcome to " + CHANNEL_INFO[channel][0] + "!",
            "color": "good",
            "mrkdwn_in": ["text"],
            "text": ("*To thank someone for their awesomeness:* `" +
                     CHANNEL_INFO[channel][2] +
                     " thanks <their_name> <the awesome thing they did>`" +
                     "\n*To see a summary of our collective awesomeness" +
                     ":* `" + CHANNEL_INFO[channel][2] + " summary`"
                     "\n*To view today's awesomeness" +
                     ":* `" + CHANNEL_INFO[channel][2] + " today`")
        }]


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


def is_summarize(message):
    split_message = message["text"].split()
    return (split_message and len(split_message) >= 2 and
            is_valid_identifier(split_message[0]) and
            split_message[1].lower() == 'summary')


def is_today(message):
    split_message = message["text"].split()
    return (split_message and len(split_message) >= 2 and
            is_valid_identifier(split_message[0]) and
            split_message[1].lower() == 'today')


def is_help(message):
    split_message = message["text"].split()
    return (split_message and len(split_message) >= 2 and
            is_valid_identifier(split_message[0]) and
            split_message[1].lower() == 'help')


def main():
    sc = SlackClient(SLACK_TOKEN)
    rt = RecognitionTracker()
    if sc.rtm_connect():
        while True:
            messages = sc.rtm_read()
            for message in messages:
                message_to_write = None

                # It only watches the channels it's in, but to be extra
                # careful here.
                channel = message.get("channel")
                if not channel or channel not in CHANNEL_INFO.keys():
                    continue

                # The first time you get here after 10AM on a new day, print
                # out some random results.
                current_date = (datetime.datetime.now() -
                                datetime.timedelta(hours=17)).date()
                if current_date != rt.current_date:
                    # Write the daily message to every channel
                    for channel_key in CHANNEL_INFO.iterkeys():
                        possible_message_to_write = rt.get_daily(channel_key)
                        if possible_message_to_write:
                            sc.api_call(
                                "chat.postMessage",
                                channel=channel_key,
                                username=CHANNEL_INFO[channel_key][0],
                                icon_emoji=CHANNEL_INFO[channel_key][1],
                                attachments=possible_message_to_write
                            )

                    rt.current_date = current_date

                if is_valid_message(message):
                    if is_thanks(message):
                        message_to_write = rt.give_thanks(message['text'],
                                                          message['user'],
                                                          channel)

                    if is_summarize(message):
                        message_to_write = rt.get_summary(channel)

                    if is_help(message):
                        message_to_write = rt.get_help(channel)

                    if is_today(message):
                        message_to_write = rt.get_daily(channel,
                                                        override=True)

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