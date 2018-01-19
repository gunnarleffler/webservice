#!/usr/bin/python
import base64
import datetime
import json
import hydrojson
import os
import sqlite3
import sys
import wslib_ext as wslib
import hydro_lib
import sys
import atexit

import requests
from flask import Flask, Response, escape, redirect, request, session, url_for
from werkzeug import secure_filename

# from OpenSSL import SSL

app = Flask(__name__, static_folder='static', static_url_path='')
app.config['TEMPLATES'] = 'templates/'
alerts = []


def doTemplate(path, j):
  f = open(app.config["TEMPLATES"] + path, "r")
  s = f.read()
  f.close()
  for key in j:
    s = s.replace(key, j[key])
  return s


def fromf(path):
  f = open(app.config["TEMPLATES"] + path, "r")
  s = f.read()
  return s


@app.route('/')
def index():
  # return doTemplate("index.html", {
  #      "<!--MAIN-->": fromf("notes.html"),
  #      "<!--META-->": ''
  #  })
  return fromf("index.html")


@app.route('/getjson', methods=['GET', 'POST'])
def outputHydroJSON():
  qs = request.args
  config = {}
  try:
    config = hydrojson.parseCommandLine(qs)
  except:
    return hydrojson.complain("Invalid Request")
  config["dbconn"] = hydro_lib.connect("../data/hydro.db")
  config["cur"] = config["dbconn"].cursor()
  result = []
  if "catalog" in qs:
    result = hydrojson.site_catalog(qs["catalog"], config)
  elif "tscatalog" in qs:
    result = hydrojson.ts_catalog(qs["tscatalog"], config)
  elif "query" in qs:
    result = hydrojson.query(qs["query"], config)
  else:
    result = hydrojson.complain("No Parameters Given!")
  return Response(json.dumps(result, sort_keys=True, indent=3), mimetype="text/plain")


@app.route('/csv', methods=['GET', 'POST'])
def outputCSV():
  ws = wslib.dataService("../data/hydro.db")
  config = wslib.ddWebServiceConfig()
  config.parseParameters(request.args)
  ws.updateConfig(config)
  maxLen = 0
  wsData = []
  output = []
  # read the data and find the max length
  for tsid in config.settings["id"]:
    t = ws.readTS(tsid[0], config.settings["start"], config.settings["end"],
                  tsid[1]).data
    # apply options to timeseries
    if t != None:
      ts = ws.applyOptions(wslib.timeseries(t), config)
      if len(ts.data) > maxLen:
        maxLen = len(ts.data)
    else:
      ts = wslib.timeseries()
    wsData.append(ts.data)
    output.append("timestamp," + tsid[0])

  # display the data
  output = ",".join(output) + "\n"
  pattern = "%s,%0." + config.settings["digits"] + "f,"
  for i in xrange(0, maxLen):
    for d in wsData:
      if i < len(d):
        if d[i][1] != None:
          output += pattern % (d[i][0].strftime(config.settings["timeformat"]),
                               d[i][1])
        else:
          output += "%s,," % (d[i]
                              [0].strftime(config.settings["timeformat"]))
      else:
        output += ",,"
    output += "\n"
  ws.disconnect()


@app.route('/html', methods=['GET', 'POST'])
def outputHTML():
  def generateBlankLine(count):
    output = []
    for i in xrange(count):
      output.append(None)
    return output

  def addValue(column, count, _datetime, value):
    if not _datetime in valTable:
      valTable[_datetime] = generateBlankLine(count)
    valTable[_datetime][column] = value

  ws = wslib.dataService("../data/hydro.db")
  config = wslib.ddWebServiceConfig()
  config.parseParameters(request.args)
  mimetype = "text/html"
  if "filename" in config.settings:
    mimetype += "\ncontent-disposition: attachment; filename=" + config.settings[
        "filename"]

  valTable = {}
  ws.updateConfig(config)
  wsData = []
  output = []
  output = '<table class ="ws"><thead class = "ws"><tr><th class = "ws">Date Time</th>'
  colCount = len(config.settings["id"])
  i = 0
  for tsid in config.settings["id"]:
    t = ws.readTS(tsid[0], config.settings["start"],
                  config.settings["end"]).data
    # apply options to timeseries
    if t != None:
      ts = ws.applyOptions(wslib.timeseries(t), config)
      for d in ts.data:
        addValue(i, colCount, d[0], d[1])
    if tsid[1] == "default":
      tsid[1] = ws.getDefaultUnits(tsid[0])
    output += "<th class = \"ws\">" + tsid[0] + "[" + tsid[1] + "]\t" + "</th>"
    i += 1
  output += "</tr></thead>"
  output = [output]
  # display the data
  keylist = valTable.keys()
  while None in keylist:
    keylist.remove(None)
  keylist.sort()
  cl = "ws"
  pattern = "%0." + config.settings["digits"] + "f\t"
  for key in keylist:
    if cl == "wsodd":
      cl = "ws"
    else:
      cl = "wsodd"
    row = '<tr class="' + cl + '"><td class = "ws">' + ws.strftime(
        key, config.settings["timeformat"],
        usemidnight=config["midnight"]) + '\t</td>'
    for val in valTable[key]:
      row += "<td>"
      if val != None:
        row += pattern % val
      else:
        row += "\t"
      row += "</td>"
    row += "</tr>"
    output.append(row)
  output.append("</table>")
  ws.disconnect()
  return Response("\n".join(output), mimetype=mimetype)


@app.route('/ecsv', methods=['GET', 'POST'])
def outputECSV():
  def generateBlankLine(count):
    output = []
    for i in xrange(count):
      output.append(None)
    return output

  def addValue(column, count, _datetime, value):
    if not _datetime in valTable:
      valTable[_datetime] = generateBlankLine(count)
    valTable[_datetime][column] = value

  ws = wslib.dataService("../data/hydro.db")
  config = wslib.ddWebServiceConfig()
  config.parseParameters(request.args)
  valTable = {}
  ws.updateConfig(config)
  wsData = []
  mimetype = "text/plain"
  if "filename" in config.settings:
    mimetype += "\ncontent-disposition: attachment; filename=" + config.settings[
        "filename"]
  output = ['Date Time']
  colCount = len(config.settings["id"])
  i = 0
  for tsid in config.settings["id"]:
    t = ws.readTS(tsid[0], config.settings["start"],
                  config.settings["end"]).data
    # apply options to timeseries
    if t != None:
      ts = ws.applyOptions(wslib.timeseries(t), config)
      for d in ts.data:
        addValue(i, colCount, d[0], d[1])
    if tsid[1] == "default":
      tsid[1] = ws.getDefaultUnits(tsid[0])
    output.append("%s [%s]" % (tsid[0], tsid[1]))
    i += 1
  output = [escape(",".join(output))]
  # display the data
  keylist = valTable.keys()
  while None in keylist:
    keylist.remove(None)
  keylist.sort()
  cl = "ws"
  pattern = "%0." + config.settings["digits"] + "f"
  for key in keylist:
    row = [
        ws.strftime(
            key, config.settings["timeformat"], usemidnight=config["midnight"])
    ]
    for val in valTable[key]:
      if val != None:
        row.append(pattern % val)
      else:
        row.append("")
    output.append(",".join(row))
  ws.disconnect()
  return Response("\n".join(output), mimetype=mimetype)


@app.errorhandler(404)
def not_found(error):
  return "<h1>NOT FOUND</h1>", 404


app.secret_key = 'ABCDEFGHIJKLMNOP'

if __name__ == "__main__":
  context = ('db/server.crt', 'db/server.key')
  app.run(host='0.0.0.0', port=5001, threaded=True, debug=True)
