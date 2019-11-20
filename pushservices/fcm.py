#!/usr/bin/python
# -*- coding: utf-8 -*-

from . import PushService
from oauth2client.service_account import ServiceAccountCredentials
from util import json_decode, json_encode
import argparse
import datetime
import logging
import tornado

BASE_URL = "https://fcm.googleapis.com"
SCOPES = ["https://www.googleapis.com/auth/firebase.messaging"]
_logger = logging.getLogger("fcm")
http = tornado.httpclient.AsyncHTTPClient()


class FCMException(Exception):
    def __init__(self, response_statuscode, error):
        self.response_statuscode = response_statuscode
        self.error = error


class FCMClient(PushService):
    def __str__(self):
        return "endpoint: %s" % (self.endpoint)

    def __init__(self, **kwargs):
        self.project_id = kwargs["project_id"]
        self.jsonkey = kwargs["jsonkey"]
        self.appname = kwargs["appname"]
        self.instanceid = kwargs["instanceid"]
        jsonData = json_decode(self.jsonkey)
        self.oauth_client = ServiceAccountCredentials.from_json_keyfile_dict(
            jsonData, SCOPES
        )
        self.endpoint = "%s/v1/projects/%s/messages:send" % (BASE_URL, self.project_id)

    def format_values(self, data=None):
        if not isinstance(data, dict):
            return data

        # Try to convert all fields to string.
        formatted = {}

        for (k, v) in data.items():
            if isinstance(v, bool):
                formatted[k] = "1" if v else "0"

            elif isinstance(v, dict):
                try:
                    formatted[k] = json_encode(self.format_values(v))
                except:
                    _logger.error("Error treating field " + k)

            elif v is not None:
                formatted[k] = str(v)

        return formatted

    def build_request(self, token, alert, **kwargs):
        if alert is not None and not isinstance(alert, dict):
            alert = {"body": alert, "title": alert}

        fcm_param = kwargs.get("payload", {})
        android = fcm_param.get("android", {})
        apns = fcm_param.get("apns", {})
        webpush = fcm_param.get("webpush", {})
        data = fcm_param.get("data", {})

        # data structure: https://firebase.google.com/docs/reference/fcm/rest/v1/projects.messages
        payload = {"message": {"token": token}}

        if alert:
            payload["message"]["notification"] = self.format_values(alert)

        if data:
            payload["message"]["data"] = self.format_values(data)

        if android:
            payload["message"]["android"] = android

        if webpush:
            payload["message"]["webpush"] = webpush

        if apns:
            payload["message"]["apns"] = apns

        text = json_encode(payload)
        return text

    async def process(self, **kwargs):

        payload = kwargs.get("payload", {})
        extra = kwargs.get("extra", {})
        alert = kwargs.get("alert", None)
        appdb = kwargs.get("appdb", None)
        token = kwargs["token"]

        if not token:
            raise FCMException(400, "devicde token is required")

        access_token, expires_in = self.oauth_client.get_access_token()
        _logger.info(
            "access token expiring in %s..." % datetime.timedelta(seconds=expires_in)
        )
        headers = {
            "Authorization": "Bearer %s" % access_token,
            "Content-Type": "application/json; UTF-8",
        }

        data = self.build_request(token, alert, extra=extra, payload=payload)

        response = await http.fetch(
            self.endpoint, method="POST", body=data, headers=headers
        )

        if response.code >= 400:
            jsonError = tornado.escape.json_decode(response.body)
            _logger.info("fcm response code is >= 400 %s" % jsonError)
            raise FCMException(400, jsonError["error"])
        return response
