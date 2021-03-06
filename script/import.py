#!/usr/bin/python

helpText = """
import.py
v1.0.0 - 1/17/2018

this program imports data into the webservice database data/hydro.db

"""

import sys
sys.path.append("../www")
import socket
import atexit
import argparse
import datetime
import hydro_lib
import json
import os
import random
import requests
import time
import wslib_ext as wslib
import dateutil.parser as dateparser

pisces_cwms_map = {
    "siteid": "LOCATION_ID",
    "description": "PUBLIC_NAME",
    "latitude": "LATITUDE",
    "longitude": "LONGITUDE",
    "elevation": "ELEVATION",
    "active_flag": "ACTIVE_FLAG",
    "horizontal_datum": "HORIZONTAL_DATUM",
    "vertical_datum": "VERTICAL_DATUM",
    "responsibility": "OFFICE_ID"
}

conf = {
    "lookback": 7,
    "lookback1": 7,
    "lookback2": 30000,
    "chance": 200,
    "defaultUSCS": hydro_lib.defaultUnits,
    "sql_path": "../data/newdata.sql",
    "pathnames_path": "../www/pathnames.txt",
    "pathnames_list": "./pathnames.list"
}

paths = []

# metadata methods
#-----------------------------------------------


def repeatLog(n):
  time.sleep(n)
  output = sys.stderr
  output.write("import.py is running\n")
  repeatLog(n)


#repeatLog(2)


def storeCwmsMeta(d):
  r = hydro_lib.rec([],
                    table="sitecatalog",
                    keys=hydro_lib.schemas["sitecatalog"])
  for key in pisces_cwms_map:
    r[key] = d[pisces_cwms_map[key]]
  logSQL(r.store(cur))
  dbconn.commit()


def storeHydroJSONMeta(siteid, site):
  # Store metadata that comes in from a HydroJSON file
  r = hydro_lib.rec([],
                    table="sitecatalog",
                    keys=hydro_lib.schemas["sitecatalog"])
  for key in pisces_cwms_map:
    r[key] = site.get(key, "")
  r["siteid"] = siteid
  r["description"] = site.get("name", "")
  r["elevation"] = site.get("elevation", {}).get("value", 0)
  r["horizontal_datum"] = site.get("elevation", {}).get("value", 0)
  r["vertical_datum"] = site.get("vertical_datum", {}).get("value", 0)
  r["latitude"] = site.get("coordinates", {}).get("latitude", 0)
  r["longitude"] = site.get("coordinates", {}).get("longitude", 0)
  logSQL(r.store(cur))
  dbconn.commit()


# Logging Methods
#-------------------------------------


def logSQL(s):
  if args.logsql:
    sf.write(s + "\n")
  return s


def log(message, level="MSG"):
  '''
  log code which returns parsable logs in the following format
  <ISO 8601 date> <Logging Level> <message>
  '''
  output = sys.stdout
  if args.verbose or (level != "STOR" and level != "MSG"):
    if level != "STOR":
      output = sys.stderr
    output.write("%s\t%s\t%s\n" %
                 (datetime.datetime.now().isoformat(), level, message))
  if level == "FATAL":
    sys.exit(-1)


# Timeseries Methods
#-----------------------------------------------


def getDefaultUnits(tsid):
  tsid = tsid.lower()
  tokens = tsid.split(".")

  # Check to see if full Parameter is in default units and return
  param = tokens[1]
  if param in conf["defaultUSCS"]:
    return conf["defaultUSCS"][param]

  # Check to see if parameter is in default units and return
  param = tokens[1].split("-")[0]
  if param in conf["defaultUSCS"]:
    return conf["defaultUSCS"][param]

  return ""


def tsFromList(lst):
  ts = hydro_lib.timeseries()
  for line in lst:
    # try:
    tstamp = tstamp = dateparser.parse(line[0], fuzzy=True)
    #print "&&&&&&&tstamp before: ", tstamp
    if tstamp.tzinfo == None:
      tstamp = mytz.localize(tstamp)
    #print "&&&&&&&tstamp after: ", tstamp
    ts.insert(tstamp, float(line[1]))
  # except:
  #  log ("Error Parsing %s" % str(line), level = "ERR")
  return ts


def storeJSON(j, fmt):
  j = json.loads(j)
  replace_flag = False
  log("Storing JSON")
  for siteid in j:
    #log("Processing site: %s" % siteid)
    storeHydroJSONMeta(siteid, j[siteid])
    for tsid in j[siteid]["timeseries"]:
      #log("Processing ts: %s" % tsid)
      parts = tsid.split(".")
      r = hydro_lib.rec([],
                        table="seriescatalog",
                        keys=hydro_lib.schemas["seriescatalog"])
      r = r.get(cur, "name", tsid)
      r["name"] = tsid
      r["tablename"] = hydro_lib.makeTablename(tsid)
      r["siteid"] = siteid
      for key in ["enabled", "units", "parameter", "timeinterval", "timezone"]:
        #r[key] = j[siteid]["timeseries"].get(key, "")
        r[key] = j[siteid]["timeseries"][tsid].get(key, "")

      ts = tsFromList(j[siteid]["timeseries"][tsid].get("values", []))
      if len(ts.data) > 0:
        newdata = hydro_lib.writeTS(
            r["tablename"], ts, dbconn, replace_table=replace_flag)
        logSQL(newdata)
      #log("Wrote %d values: %s" % (len(ts.data), hydro_lib.status))
      #print "Data: ", ts.data
      #r["notes"] = getTSextents(tsid)
      # print r["notes"]
      logSQL(r.store(cur))
    dbconn.commit()


def postJSON(infile, fmt="hydroJSON"):
  raw = []
  endflag = False
  log("Posting JSON")
  for line in infile:
    line = line.rstrip()
    if line == "":
      continue
    # Fix lazy JSON errors (looking at you Mike)
    if len(raw) > 0 and len(line) > 0:
      if len(raw[-1]) > 1:
        if line.strip()[0] != "}" and raw[-1][-1] != "," and "{" not in raw[
            -1] and "[" not in raw[-1]:
          raw[-1] += ","
        if line.strip()[0] == "}" and raw[-1][-1] == ",":
          raw[-1] = raw[-1][:-1]
        if line.strip()[0] == "]" and raw[-1][-1] == ",":
          raw[-1] = raw[-1][:-1]
    # End Fix
    if line == "{" and endflag:
      if raw != []:
        try:
          storeJSON("\n".join(raw), fmt)
        except:
          pass
          #log ("error occured while parsing json",level = "ERR")
      del raw
      raw = ["{"]
    else:
      if len(line) > 0:
        raw.append(line)
    if line == "}":
      endflag = True
    else:
      endflag = False


###############################################################################
p = argparse.ArgumentParser(description=helpText)
p.add_argument('-f', '--file', help='Specify input file (default is STDIN)')
p.add_argument('-a', '--ipaddress', help='remote ip address to bind')
p.add_argument('-p', '--port', help='remote port to listen')

p.add_argument(
    '-hj',
    '--hydroJSON',
    action='store_true',
    help='Input is in hydroJSON format')
p.add_argument(
    '-l',
    '--logsql',
    action='store_true',
    help='log SQL for debuggin purposes.',
    default="")
p.add_argument('-v', '--verbose', action='store_true', help='Work verbosely')
args = p.parse_args()

infile = sys.stdin
if args.file:
  try:
    log("Using file from disk: " + args.file)
    infile = open(args.file, "r")
  except:
    log("File Not found: " + args.file, level="FATAL")

if args.ipaddress and args.port:
  print "Listening to %s port %s" % (args.ipaddress, args.port)
  sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
  sock.bind((args.ipaddress, int(args.port)))
  infile = sock.makefile()

os.environ["TZ"] = "UTC"
time.tzset()

ds = wslib.ddWebService()
config = wslib.ddWebServiceConfig()
config.loadConfig("../config/config.json")
ds.updateConfig(config)
ds.connect()
if ds.status != "OK":
  raise Exception(ds.status)
atexit.register(ds.disconnect)
# file where SQL is written
if args.logsql:
  sf = open(conf["sql_path"], "w")
dbconn = hydro_lib.connect("../data/hydro.db")
cur = dbconn.cursor()
# When we upgrade to python 3.3+ use the following to log SQL:hydro_lib.dbconn.set_trace_callback(logSQL)
print "hydrolib: " + hydro_lib.status
print "Connection: " + ds.configuration["dbname"]

if args.hydroJSON:
  postJSON(infile)
else:
  log("Input format not specified.", level="FATAL")

# Close differences file
if args.logsql:
  sf.close()
