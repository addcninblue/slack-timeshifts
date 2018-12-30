# Slack-Timeshifts: Timeshift manager as an app for Slack

## Local Development

To develop locally:

* setup mongodb
* setup [serveo](http://serveo.net) to forward local development server
```
$ git clone https://github.com/addcninblue/slack-timeshifts
$ # ensure that python3 version >= 3.7.0
$ virtualenv -p python3 .
$ gunicorn main:app
```

## Server Development

The server runs on the following stack:

* Google Spreadsheets (gsheets)
* Flask
* Gunicorn
* Heroku
* Slack

## Core Features

* Finding substitute for shift
* Marking people as tardy or noshow
* Seeing shifts for the day
