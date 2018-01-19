#!/usr/local/bin/python
#Web Service Database Interface Library
# v2.0.0 01/17/2018
#Author: Gunnar Leffler
import sys, os, time, datetime, sqlite3, json
import dateutil.parser as dateparser
#sys.path = ['/usr/dd/external/common/web_service/webexec'] + sys.path
import hydro_lib
#Timeseries object

timeseries = hydro_lib.timeseries


#Connects to a SQLITE database
class dataService:

  def __init__(self, *args):
    #initialize with Default Configuration
    self.status = "OK"
    self.configuration = ddWebServiceConfig.getDefaultSettings()
    #Database Cursors
    if len(args) > 0:
      self.dbpath = args[0]
    else:
      self.dbpath = "../data/hydro.db"
    self.connect()

  #This method disconnects from the database
  def disconnect(self):
    self.dbconn.close()

  #Stub method for backwards compatibility
  def connect(self):
    self.dbconn = hydro_lib.connect(self.dbpath)
    #Set status to hydro_lib's status
    self.status = hydro_lib.status

  #this updates configuration settings from a ddWebSvcConfig object
  def updateConfig(self, config):
    for key in config.settings:
      self.configuration[key] = config.settings[key]

  def readTS(self, _tsid, start_time=None, end_time=None, units="Default"):
    """
     Reads a time series from the database#
     tsid - string LOC_PARAM
     start_time - datetime
     end_time - datetime
    """
    series = hydro_lib.rec(
        [], table="seriescatalog", keys=hydro_lib.schemas["seriescatalog"])
    cur = self.dbconn.cursor()
    tsid = series.get(cur, "name", _tsid)["tablename"]
    #tsid = "TS_"+hashlib.sha1(_tsid).hexdigest().upper()
    ts = timeseries()
    if tsid == "":
      return ts
    sqltxt = "SELECT * FROM " + tsid
    if start_time != None and end_time != None:
      start = time.mktime(start_time.timetuple())
      end = time.mktime(end_time.timetuple())
      sqltxt += " WHERE DateTime >= " + str(start) + " AND DateTime <= " + str(
          end)
    try:
      cur.execute(sqltxt)
      rows = cur.fetchall()
      for d in rows:
        row = [datetime.datetime.fromtimestamp(d[0])]
        row.append(d[1])
        if len(d) == 3:
          row.append(d[2])
        else:
          row.append(0)
        ts.data.append(row)
    except Exception, e:
      self.status = "\nCould not read %s\n" % tsid
      self.status += "\n%s" + str(e)
    cur.close()
    if self.configuration["tz_offset"] != 0:
      ts = ts.timeshift(
          datetime.timedelta(hours=self.configuration["tz_offset"]))
    if "fed" in self.configuration and "fsd" in self.configuration:
      tdata = []
      for t in ts.data:
        jday = t[0].timetuple().tm_yday
        if jday >= self.configuration["fsd"] and jday <= self.configuration[
            "fed"]:
          tdata.append(t)
      ts.data = tdata
    if "filter" in self.configuration:
      ts = ts.cull(configuration["filter"]["op"],
                   configuration["filter"]["operand"])
    return ts

  def makeTablename(self, _tsid):
    return "TS_" + hashlib.sha1(_tsid).hexdigest().upper()[:10]

  #reads a timeseries from the database by self evaluating the table name, does not work for aliases
  def readTSblind(self, _tsid, start_time=None, end_time=None, units="Default"):
    cur = self.dbconn.cursor()
    tsid = "TS_" + hashlib.sha1(_tsid).hexdigest().upper()[:10]
    ts = timeseries()
    sqltxt = "SELECT * FROM " + tsid
    if start_time != None and end_time != None:
      start = time.mktime(start_time.timetuple())
      end = time.mktime(end_time.timetuple())
      sqltxt += " WHERE DateTime >= " + str(start) + " AND DateTime <= " + str(
          end)
    try:
      cur.execute(sqltxt)
      rows = cur.fetchall()
      for d in rows:
        row = [datetime.datetime.fromtimestamp(d[0])]
        row.append(d[1])
        if len(d) == 3:
          row.append(d[2])
        else:
          row.append(0)
        ts.data.append(row)
    except Exception, e:
      self.status = "\nCould not read %s\n" % tsid
      self.status += "\n%s" + str(e)
    cur.close()
    return ts

  def writeTS(self, tsid, ts, replace_table=False):
    tsid = tsid.upper()
    try:
      cur = self.dbconn.cursor()
      if replace_table == True:
        cur.execute("DROP TABLE " + tsid)
      cur.execute("CREATE TABLE IF NOT EXISTS " + tsid +
                  "(DateTime INTEGER PRIMARY KEY, val REAL, quality INTEGER")
      for line in ts.data:
        sqltxt = "INSERT OR REPLACE INTO " + tsid + " VALUES(%d,%f,%s)" % (
            int(time.mktime(line[0].timetuple())), line[1], int(line[2]))
        cur.execute(sqltxt)
      self.dbconn.commit()
    except Exception, e:
      self.status = "\nCould not store " + tsid
      self.status += "\n%s" % str(e)
    cur.close()

  def max_datetime(self, ts_id):
    max = None
    sql = "SELECT MAX( datetime ) FROM %s" % (self.makeTablename(ts_id))
    cur = self.db.cursor()
    try:
      if cur.execute(sql) is not None:
        (max,) = cur.fetchone()
    except sqlite3.Error as e:
      print e.args[0]

    if max is not None:
      max = pytz.utc.localize(datetime.utcfromtimestamp(max))
    return max

  def min_datetime(self, ts_id):
    min = None
    sql = "SELECT MIN( datetime ) FROM %s" % (self.makeTablename(ts_id))
    cur = self.db.cursor()
    try:
      if cur.execute(sql) is not None:
        (min,) = cur.fetchone()
    except sqlite3.Error as e:
      print e.args[0]

    if min is not None:
      min = pytz.utc.localize(datetime.utcfromtimestamp(min))
    return min

#gets status message of object and resets it to "OK"

  def getStatus(self):
    s = self.status
    self.status = "OK"
    return s

  #A roll your own strftime implementation that allows dates before 1900
  #Based on the matplotlib version
  def strftime(self, dt, fmt, usemidnight=False):

    def _findall(text, substr):
      # Also finds overlaps
      sites = []
      i = 0
      while 1:
        j = text.find(substr, i)
        if j == -1:
          break
        sites.append(j)
        i = j + 1
      return sites

    #fmt = self.illegal_s.sub(r"\1", fmt)
    domidnight = False
    if dt.hour == 0 and dt.minute == 0 and usemidnight != False:
      domidnight = True
    fmt = fmt.replace("%s", "s")
    if dt.year > 1900:
      if domidnight == True:
        dt2 = dt - datetime.timedelta(days=1)
        return dt2.strftime(fmt).replace("00:00", "24:00").replace("0000",
                                                                   "2400")
      return dt.strftime(fmt)
    year = dt.year
    # For every non-leap year century, advance by
    # 6 years to get into the 28-year repeat cycle
    delta = 2000 - year
    off = 6 * (delta // 100 + delta // 400)
    year = year + off

    # Move to around the year 2000
    year = year + ((2000 - year) // 28) * 28
    timetuple = dt.timetuple()
    s1 = time.strftime(fmt, (year,) + timetuple[1:])
    sites1 = _findall(s1, str(year))

    s2 = time.strftime(fmt, (year + 28,) + timetuple[1:])
    sites2 = _findall(s2, str(year + 28))

    sites = []
    for site in sites1:
      if site in sites2:
        sites.append(site)
    s = s1
    syear = "%4d" % (dt.year,)
    for site in sites:
      s = s[:site] + syear + s[site + 4:]
    return s

  def applyOptions(self, ts, config):
    """ this method takes a config object and a timeseries and applies
        changes to the timeseries based on the specified options
    """
    if ts.data != []:
      if "interpolate" in config.settings:
        interval = ts.parseTimedelta(config.settings["interpolate"])
        #We don't want an absurd interval to tie up system resources
        if interval >= datetime.timedelta(seconds=30):
          ts = ts.interpolate(interval)
      if "sum" in config.settings:
        interval = ts.parseTimedelta(config.settings["sum"])
        #We don't want an absurd interval to tie up system resources
        if interval >= timedelta(seconds=30):
          ts = ts.accumulate(interval)
      if "snap" in config.settings:
        interval = ts.parseTimedelta(config.settings["snap"])
        if interval >= datetime.timedelta(seconds=30):
          ts = ts.snap(interval, interval / 2)
      if "hardsnap" in config.settings:
        interval = ts.parseTimedelta(config.settings["hardsnap"])
        if interval >= datetime.timedelta(seconds=30):
          try:
            t1 = ts.data[0][0]
            t2 = datetime.datetime(year=t1.year, month=t1.month, day=t1.day)
            ts = ts.snap(interval, interval / 2, starttime=t2)
          except:
            ts.data = []
      if "average" in config.settings:
        interval = ts.parseTimedelta(config.settings["average"])
        if interval >= datetime.timedelta(seconds=30):
          ts = ts.average(interval)
      if "maximum" in config.settings:
        interval = ts.parseTimedelta(config.settings["maximum"])
        ts = ts.maxmin(interval, lambda x, y: x > y)
      if "minimum" in config.settings:
        interval = ts.parseTimedelta(config.settings["minimum"])
        ts = ts.maxmin(interval, lambda x, y: x < y)
      if "timeshift" in config.settings:
        interval = ts.parseTimedelta(config.settings["timeshift"])
        ts = ts.timeshift(interval)
      if "systdgfilter" in config.settings:
        interval = ts.parseTimedelta(config.settings["systdgfilter"])
        if interval >= datetime.timedelta(seconds=30) and len(ts.data) > 0:
          t1 = ts.data[0][0]
          t2 = datetime(year=t1.year, month=t1.month, day=t1.day, hour=t1.hour)
          ts = ts.timeshift(t1 - t2)
          ts = ts.interpolate(interval)
    return ts


class ddWebServiceConfig:

  def __init__(self):
    #initialize with Default Configuration
    self.status = "OK"
    self.settings = self.getDefaultSettings()

  def __getitem__(self, key):
    if key in self.settings:
      return self.settings[key]
    return None

  #This method sets up the default configuration
  @classmethod
  def getDefaultSettings(self):
    conf = {}
    #initialize time parameters
    conf["timeformat"] = "%d-%b-%Y %H:%M"  #Time format
    conf["timezone"] = "PST"
    conf["tz_offset"] = -8
    conf["lookback"] = "7"
    conf["lookforward"] = "0"
    conf["digits"] = "3"
    conf["delimiter"] = "|"
    conf["midnight"] = False
    conf["end"] = datetime.datetime.now() + datetime.timedelta(
        days=int(conf["lookforward"]))
    conf["start"] = datetime.datetime.now() - datetime.timedelta(
        days=int(conf["lookback"]))
    return conf

  def loadConfig(self, path):
    conf = json.loads(open(path, "r").read())
    for key in conf:
      self.settings[key] = conf[key]
    if "defaultUnits" in self.settings:
      self.units = conf["defaultUnits"]
      if "default" in self.settings["defaultUnits"]:
        self.settings["defaultUnits"] = self.settings["defaultUnits"]["default"]

  def parseParameters(self, params):  #Parse URL Parameters

    def parseTime(val):
      ts = hydro_lib.timeseries()
      try:
        return datetime.timedelta(days=int(val))
      except:
        return ts.parseTimedelta(val)
      return datetime.timedelta(days=7)

    p = {}

    for key in params:  #lowercase dictionary keys
      p[key.lower()] = params.get(key)

    self.settings["midnight"] = False
    self.settings["id"] = [["", "ft"]]
    for param in ('average', 'delimiter', 'filename', 'hardsnap', 'interpolate',
                  'lookback', 'lookforward', 'maximum', 'midnight', 'minimum',
                  'snap', 'systdgfilter', 'timeformat', 'timeshift', 'digits',
                  'timezone', 'backward', 'forward', 'sum'):
      if param in p:
        self.settings[param] = p.get(param)

    if "lookback" in p:
      self.settings["start"] = datetime.datetime.now() - parseTime(
          p.get("lookback"))
    if "backward" in p:
      self.settings["start"] = datetime.datetime.now() - parseTime(
          p.get("backward"))
    if "lookforward" in p:
      self.settings["end"] = datetime.datetime.now() + parseTime(
          p.get("lookforward"))
    if "forward" in p:
      self.settings["end"] = datetime.datetime.now() + parseTime(
          p.get("forward"))
    for param in ('end', 'start'):
      if param in p:
        self.settings[param] = dateparser.parse(p.get(param), fuzzy=True)

    if "enddate" in p:
      self.settings["end"] = dateparser.parse(p["enddate"], fuzzy=True)
    if "startdate" in p:
      self.settings["start"] = dateparser.parse(
          p["startdate"], fuzzy=True)
    if "id" in p:
      self.settings["id"] = self.parseId(p.get("id"),
                                         self.settings["delimiter"])
    if "tzoffset" in p:
      val = p["tzoffset"]
      try:
        self.settings["tz_offset"] = float(val)
      except:
        pass
    if "timezone" in p:
      tzoffsets = {"PST": -8, "MST": -7, "CST": -6, "EST": -5, "GMT": 0}
      tz = p.get("timezone")
      self.settings["timezone"] = tz
      self.settings["tz_offset"] = tzoffsets.get(tz, 0)
    if "filterstart" in p and "filterend" in p:
      self.settings["fsd"] = dateparser.parse(
          p["filterstart"]).timetuple().tm_yday
      self.settings["fed"] = dateparser.parse(
          p["filterend"]).timetuple().tm_yday

  #Parses ID string, returns a list of [tsid,units]
  def parseId(self, idStr, delimiter):
    output = []
    tokens = idStr.split(delimiter)
    for token in tokens:
      ts = token.split(":")
      if len(ts) > 1:
        output.append([ts[0], ts[1].split("=")[-1]])
      else:
        output.append([ts[0], "default"])
    return output


ddWebService = dataService  #for backwards compatibility
