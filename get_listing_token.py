#!/usr/bin/env python3.6

from googleapiclient.discovery import build
from httplib2 import Http
from oauth2client import file, client, tools
import os, logging, sys, argparse, email, base64, time, pytz, html5lib, requests
from oauth2client.client import flow_from_clientsecrets
from oauth2client.client import FlowExchangeError
from apiclient.discovery import build
from apiclient import errors
from bs4 import BeautifulSoup
import numpy as np
import pandas as pd
import datetime as dt

def gprint(text):
    #Print text in green color
    print ("\x1b[32m{0}\x1b[0m".format(text))    

def bprint(text):
    #print text in blue color
    print ("\x1b[34m{0}\x1b[0m".format(text))
    
parser = argparse.ArgumentParser()
parser.add_argument("--user",default="<email>")

# If modifying these scopes, delete the file token.json.
SCOPES = 'https://www.googleapis.com/auth/gmail.readonly'


store = file.Storage('token.json')
creds = store.get()
if not creds or creds.invalid:
    flow = client.flow_from_clientsecrets('credentials.json', SCOPES)
    creds = tools.run_flow(flow, store)
service = build('gmail', 'v1', http=creds.authorize(Http()))

def ListMessages(service, user, query=''):
    """Gets a list of messages.
    Args:
      service: Authorized Gmail API service instance.
      user: The email address of the account.
      query: String used to filter messages returned.
             Eg.- 'label:UNREAD' for unread Messages only.
  
    Returns:
      List of messages that match the criteria of the query. Note that the
      returned list contains Message IDs, you must use get with the
      appropriate id to get the details of a Message.
    """
    try:
        response = service.users().messages().list(userId=user, q=query).execute()
        messages = response['messages']

        while 'nextPageToken' in response:
            page_token = response['nextPageToken']
            response = service.users().messages().list(userId=user, q=query,
                                         pageToken=page_token).execute()
            messages.extend(response['messages'])

        return messages
    except (errors.HttpError, error):
        print ('An error occurred: %s' % error)
        if error.resp.status == 401:
      # Credentials have been revoked.
      # TODO: Redirect the user to the authorization URL.
          raise NotImplementedError()
            
def GetMimeMessage(service, user_id, msg_id):
    """Get a Message and use it to create a MIME Message.

  Args:
    service: Authorized Gmail API service instance.
    user_id: User's email address. The special value "me"
    can be used to indicate the authenticated user.
    msg_id: The ID of the Message required.

  Returns:
    A MIME Message, consisting of data from Message.
  """
    try:
        message = service.users().messages().get(userId=user_id, id=msg_id,
                                             format='raw').execute()

        print ('Message snippet: %s' % message['snippet'])

        msg_str = base64.urlsafe_b64decode(message['raw'].encode('ASCII'))

        mime_msg = email.message_from_bytes(msg_str)

        return mime_msg
    except errors.HttpError:
        print ('An error occurred: %s')
        
def main():
    userID = parser.parse_args().user
    MESSAGES = ListMessages(service,userID)
    print ("user id: {}\nMessages: {}\n\n\n".format(userID,len(MESSAGES)))
    
    for _,message in enumerate (MESSAGES):
        msg = GetMimeMessage(service,userID,message['id'])
        if msg['From'] == '<patty@paulaclarkrealtor.com>':
            date = msg['Date']
            bprint (f"Message #{_} is from patty@paulaclarkrealtor.com\n\n")
            try:
                links = BeautifulSoup(msg.get_payload(),'html5lib').findAll('a')
                token = [link.replace('"','')[2:] for link in [link.get('?token') for link in links] if link is not None][0]
            except:
                print("No token found!")
                pass
            gprint (f"{date} - http://www.priv.njmlsnew.xmlsweb.com/cc2/account/tokenlogin?token={token}\n\n")
            
if __name__ == "__main__":
    main()            
