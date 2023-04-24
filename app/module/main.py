import ssl
import socket
import time
from contants import SLACK_TOKEN,SLACK_CHANNEL_ID
from datetime import datetime
import datetime
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from flask import Flask, request
import copy

SLACK_TOKEN = SLACK_TOKEN
SLACK_CHANNEL_ID = SLACK_TOKEN

app = Flask(__name__)

websites = [
    'www.eddiebauer.com',
    'www.eddiebauer.ca',
    'www.eddiebaueroutlet.com'
]

HEADER_TEMPLATE = {
    "type": "header",
    "text": {
        "type": "plain_text",
        "text": "SSL Certificate :alert_1: :alert_1:",
        "emoji": True
    }
}

HEADER_SECTION_TEMPLATE = {
    "type": "section",
    "text": {
        "type": "mrkdwn",
        "text": "_Eddie Bauer's website has an SSL certificate, which indicates that data transmitted between the website and users is encrypted and secure._"
    },
    "accessory": {
        "type": "image",
        "image_url": "https://icon-library.net/images/ssl-certificate-icon/ssl-certificate-icon-28.jpg",
        "alt_text": "SSL thumbnail"
    }
}

REMINDER_TEMPLATE = {
    "type": "context",
    "elements": [
        {
            "type": "image",
            "image_url": "https://api.slack.com/img/blocks/bkb_template_images/notificationsWarningIcon.png",
            "alt_text": "notifications warning icon"
        },
        {
            "type": "mrkdwn",
            "text": "*Reminder for SSL Cert Expiry*"
        }
    ]
}

DIVIDER_TEMPLATE = {
    "type": "divider"
}

SLASH_COMMAND_TEMPLATE = {
    "type": "context",
    "elements": [
        {
            "type": "mrkdwn",
            "text": ":pushpin: Please utilize the `/cert-details` command to access a comprehensive overview of the SSL certificate details."
        }
    ]
}

MESSAGE_SECTION_TEMPLATE = {
    "type": "section",
    "text": {
        "type": "mrkdwn",
        "text": ""
    }
}

PROCEED_TEMPLATE = {
    "type": "actions",
    "elements": [
        {
            "type": "button",
            "text": {
                "type": "plain_text",
                "text": "Secure",
                "emoji": True
            },
            "style": "primary",
            "value": "Proceed",
            "url": "https://aws.amazon.com/certificate-manager/",
            "action_id": "button-action"
        }
    ]
}

client = WebClient(token=SLACK_TOKEN)

def get_ssl_socket(website):
    context = ssl.create_default_context()
    try:
        conn = context.wrap_socket(socket.socket(
            socket.AF_INET), server_hostname=website)
        conn.settimeout(10.0)
        conn.connect((website, 443))
        return conn
    except socket.gaierror as e:
        print(f"Failed to resolve hostname: {e}")
        return None

def check_cert_expiry(website):
    ssl_date_fmt = r'%b %d %H:%M:%S %Y %Z'
    ssl_socket = get_ssl_socket(website)
    ssl_info = ssl_socket.getpeercert()
    expires_on = datetime.datetime.strptime(ssl_info['notAfter'], ssl_date_fmt)
    days_until_expiry = (expires_on - datetime.datetime.now()).days
    ssl_socket.close()
    return days_until_expiry, expires_on

message_sections = []
cert_details = {}
for website in websites:
    days_until_expiry, expires_on = check_cert_expiry(website)
    if days_until_expiry is not None and days_until_expiry < 604800:
        cert_details[website] = {
            "days_until_expiry": days_until_expiry,
            "expires_on": expires_on
        }
        message_section = MESSAGE_SECTION_TEMPLATE.copy()
        message_section["text"]["text"] = f"*<https://{website}|{website}>*\n\t\t\t_Expiry on_ : *{expires_on}*\t\t\t_Days remaining_ : *{days_until_expiry}*"
        message_sections.append(copy.deepcopy(message_section))

#block to schedule messages in the slack
    # if days_until_expiry is not None and days_until_expiry >= 7:
    #     cert_details[website] = {
    #         "days_until_expiry": days_until_expiry,
    #         "expires_on": expires_on
    #     }
    #     num_weeks_until_expiry = min(days_until_expiry // 7, 17)  # limit to 17 weeks to avoid "time_too_far" error
    #     for i in range(num_weeks_until_expiry):
    #         days_remaining = days_until_expiry - (i + 1) * 7
    #         if days_remaining > 0:
    #             scheduled_time = int((time.time()) + (i + 1) * 604800)  # schedule message every week
    #             message_section = MESSAGE_SECTION_TEMPLATE.copy()
    #             message_section["text"]["text"] = f"*<https://{website}|{website}>*\n\t\t\t_Expiry on_ : *{expires_on}*\t\t\t_Days remaining_ : *{days_until_expiry}*"
    #             message_sections.append(copy.deepcopy(message_section))
    #         else:
    #             print(f"Skipping message scheduling for {website} because certificate has expired or will expire before next scheduled message.")

if message_sections:
    my_payload = [
        HEADER_TEMPLATE,
        HEADER_SECTION_TEMPLATE,
        REMINDER_TEMPLATE,
        DIVIDER_TEMPLATE,
    ]
    my_payload.extend(message_sections)
    my_payload.extend([
        DIVIDER_TEMPLATE,
        SLASH_COMMAND_TEMPLATE,
        PROCEED_TEMPLATE
    ])

    try:
        response = client.chat_postMessage(channel=SLACK_CHANNEL_ID, blocks=my_payload)
        print(f"Sent message to slack channel")
    except SlackApiError as e:
        print(f"Error sending message to Slack channel: {e}")
    # try:
    #     response = client.chat_scheduleMessage(channel=SLACK_CHANNEL_ID,  blocks=my_payload)
    #     print(f"Scheduled message to Slack channel: {message}")
    # except SlackApiError as e:
    #     print(f"Error scheduling message to Slack channel: {e}")
            
@app.route("/cert-details", methods=["POST"])
def cert_details():
    command = request.form.get("command")
    if command == "/cert-details":
        response_text = ""
        for website in websites:
            ssl_socket = get_ssl_socket(website)
            if ssl_socket is None:
                response_text += f"Error retrieving certificate details for {website}: Failed to resolve hostname\n\n"
                continue
            try:
                ssl_info = ssl_socket.getpeercert()
                response_text += f"Certificate details for {website}:\n{ssl_info}\n\n"
            except Exception as e:
                response_text += f"Error retrieving certificate details for {website}: {str(e)}\n\n"
            ssl_socket.close()
        try:
            client.chat_postMessage(
                channel=request.form["channel_id"], text=response_text)
        except SlackApiError as e:
            print(f"Error sending response to Slack: {e}")
    return ""

if __name__ == "__main__":
    app.run(debug=True)