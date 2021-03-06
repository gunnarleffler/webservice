import datetime
import dateutil.parser
import hydro_lib
import json
import os
import sys
import urllib


###############################################################################


def complain(e):
  return '{\n"error":"' + e + '"\n}'


###############################################################################
# Return a catalog of sites (locations) only


def site_catalog(search_criteria, config):
  output = {}
  tokens = []
  try:
    tokens = json.loads(urllib.unquote(search_criteria))
  except:
    complain("Malformed query")
    return
  if tokens == []:
    tokens = "['%']"
  r = hydro_lib.rec(
      [], table="sitecatalog", keys=hydro_lib.schemas["sitecatalog"])
  for token in tokens:
    t = r.search(config["cur"], "siteid", token)
    for key in t:
      output[key] = hydro_lib.new_site(t[key], conf=config)
  return output


###############################################################################
# Return a catalog of sites and timeseries names


def ts_catalog(search_criteria, config):
  output = {}
  tokens = []
  try:
    tokens = json.loads(urllib.unquote(search_criteria))
  except:
    complain("Malformed query")
    return output
  if tokens == []:
    complain("Please be more descriptive")
    return output
  elif len(tokens[0]) < 3:
    complain("Please be more descriptive")
    return output
  site = hydro_lib.rec(
      [], table="sitecatalog", keys=hydro_lib.schemas["sitecatalog"])
  series = hydro_lib.rec(
      [], table="seriescatalog", keys=hydro_lib.schemas["seriescatalog"])

  # loop through search criteria tokens and build response

  for token in tokens:
    token = token.replace(" ", "%")
    t = series.search(config["cur"], "name", "%" + token + "%")
    sites = site.search(config["cur"], "description", "%" + token + "%")
    for key in sites:
      t.update(series.search(config["cur"], "name", sites[key]["siteid"] + "%"))
    for key in t:
      siteid = t[key]["siteid"]
      if siteid in output:
        output[siteid]["timeseries"][key] = {"notes": t[key]["notes"]}
      else:
        s = site.get(config["cur"], "siteid", siteid)
        output[siteid] = hydro_lib.new_site(s, conf=config)
        output[siteid]["timeseries"][key] = {"notes": t[key]["notes"]}
        output[siteid]["time_format"] = config["time_format"]
        output[siteid]["tz_offset"] = config["tz_offset"]
  return output


###############################################################################


def query(search_criteria, config):
  output = ts_catalog(search_criteria, config)
  series = hydro_lib.rec(
      [], table="seriescatalog", keys=hydro_lib.schemas["seriescatalog"])
  for siteid in output:
    for tsid in output[siteid]["timeseries"]:
      s = series.get(config["cur"], "name", tsid)
      ts = hydro_lib.readTS(
          s["tablename"],
          config["dbconn"],
          config["startdt"],
          config["enddt"],
          timezone=config['timezone'])
      # date filter

      if "fed" in config and "fsd" in config:
        tdata = []
        for t in ts.data:
          jday = t[0].timetuple().tm_yday
          if jday >= config["fsd"] and jday <= config["fed"]:
            tdata.append(t)
        ts.data = tdata

      # add ts to datastructure

      if len(ts.data) > 0:
        output[siteid]["timeseries"][tsid] = hydro_lib.new_timeseries(
            s, ts, conf=config, dFamily=output[siteid]["responsibility"])
  return output


###############################################################################
# Parse Command-line Options
#
# Takes a form object, adjusts default settings based on url parameters:
#
#         "enddt" endtime   (defaults to now()
#       "startdt" starttime (defaults to now()-1d)
#      "backward" lookback from endtime, modifies starttime (format:1w2d3h4m)
#       "forward" lookforward from endtime, modifies endtime (format:1w2d3h4m)
#   "time_format" response date formatting (uses strftime specification)
#     "tz_offset" timezone offset on resultant data
#      "timezone" timezone and timezone offset on resultant data
#   "filterstart" filter values returned by day in year
#   "filterend"       (e.g. Apr 1 thru Apr 30)
#      "midnight" specifying this parameter causes midnight values to be displayed as 2400


def parseCommandLine(form):
  config = {
      "startdt": datetime.datetime.now() - datetime.timedelta(days=1),
      "enddt": datetime.datetime.now(),
      "forward": "0d",
      "backward": "1d",
      "time_format": "%Y-%m-%dT%H:%M:%S%z",
      "timezone": "PST",
      "midnight": False,
      "tz_offset": -8
  }
  ts = hydro_lib.timeSeries()

  if "startdate" in form:
    config["startdt"] = dateutil.parser.parse(form["startdate"])
  elif "startdt" in form:
    config["startdt"] = dateutil.parser.parse(form["startdt"])
  elif "backward" in form:
    config["startdt"] = (
        config["enddt"] - ts.parseTimedelta(form["backward"]))

  if "enddate" in form:
    config["enddt"] = dateutil.parser.parse(form["enddate"])
  elif "enddt" in form:
    config["enddt"] = dateutil.parser.parse(form["enddt"])
  elif "forward" in form:
    config["enddt"] = (
        config["enddt"] + ts.parseTimedelta(form["forward"]))

  if "time_format" in form:
    config["time_format"] = form["time_format"]

  if "midnight" in form:
    config["midnight"] = True

  if "filterstart" in form and "filterend" in form:
    config["fsd"] = dateutil.parser.parse(
        form["filterstart"]).timetuple().tm_yday
    config["fed"] = dateutil.parser.parse(
        form["filterend"]).timetuple().tm_yday

  val = 0
  if "tz_offset" in form:
    val = form["tz_offset"]
  if val != 0:
    try:
      config["tz_offset"] = float(val)
    except:
      pass

  if "timezone" in form:
    tzoffsets = {"PST": -8, "MST": -7, "CST": -6, "EST": -5, "GMT": 0}
    tz = form["timezone"]
    config["timezone"] = tz
    if tz in tzoffsets:
      config["tz_offset"] = tzoffsets[tz]
  return config


###############################################################################
###############################################################################
