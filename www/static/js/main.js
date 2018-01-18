/* jshint esversion: 6 */

/***************************************
 Initialization Functions v1.0.0
***************************************/

function navigate(section) {
  current_section = section;
  $("#sidebar").html("");
  $('#page_title').html(section);
  var urlVars = $.getUrlVars();

  if (section == "Rule Editor") {
    $.get("../webexec/service", {
      "getRuleEditor": "True"
    }, function(data) {
      $("#container").html(data);
    });
    init_rules();
  } else if (section == "System Status") {
    $("#srch-btn").click(function (){
        navigate("System Status");
    });
    $.get("../webexec/service", {
      "getAllFlags": "True"
    }, function(data) {
      data = JSON.parse(data);
      var k = $("#srch-term").val();
      if (k.length < 2) k = urlVars.k;
      template = '<tr><td style="background-color:$status">$name</td><td>$message</td></tr>'
      output = '<table class="table">';
      for (i = 0; i < data.length; i++) {
        var t = template.replace("$status",data[i].status).replace("$name",data[i].name).replace("$message",data[i].message);
        if (k !== undefined){
          if (data[i].name.toUpperCase().indexOf(k.toUpperCase()) != -1) output += t;
        } else output += t;
      }
      output += '</table>';
      $("#container").html(output);
    });
  } else {
    $.get("../webexec/service", {
      "getHelp": "True"
    }, function(data) {
      data = '<article class="markdown-body">' + marked(data) + '</article>';
      $("#container").html(data);
    });
  }
}

function initialize() {
  var m = moment($.now());
  navigate("System Status");
}

$(initialize);

/***************************************
 Rules Object v1.0.0
***************************************/

function init_rules(callback) {
  //$(':checkbox').checkboxpicker();
  rules = new ruleObject();
  rules.init();
  $('#srch-term').on("keypress", function(e) {
    if (e.keyCode == 13) {
      rules.setKeywordFilter();
    }
  });
}

ruleObject = function() { //Constructor
  this.rules = {};
  this.rules_schema = {};
  this.curRule = "";
  this.keywords = "";
  this.itemHTML = [
    '<li class = "nav-item" onclick = "rules.selectRule(\'$name\')">',
    '<a class="nav-link $class" href="#">$name</a>',
    //'<span class="remove-rule pull-right" onclick ="rules.removeRule(\'$name\')">X</span>',
    '</li>'
  ].join("\n");
};


ruleObject.prototype = { //object methods
  init: function() {
    this.webSvcBase = "../webexec/service";
    $.post(this.webSvcBase, {
      "getRuleList": "true"
    }).done(function(data) {
      this.rules = JSON.parse(data);
      this.populateIndex();
    }.bind(this));
    $.post(this.webSvcBase, {
      "getRuleSchema": "true"
    }).done(function(data) {
      this.rules_schema = JSON.parse(data);
    }.bind(this));

  },

  doRuleSave: function() {
    name = $("#rule_name").val();
    var payload = {}
    for (key in this.rules_schema) {
      payload[key] = $("#rule_" + key).val();
    }
    $.post("../webexec/service", {
        "putRule": JSON.stringify(payload)
      })
      .done(function(data) {
        if (data.indexOf("OK") != -1) {
          alert(data);
        } else {
          alert("Error occured while saving" + data);
        }
      });
    this.populate();
  },

  removeRule: function(id) {
    if (id in this.rules) {
      $.post("./hotlist", {
          "remove": id
        })
        .done(function(data) {
          if (data.indexOf("Success") == -1) {
            alert("Error occured while removing:" + data);
          } else {
            delete this.rules[id];
            this.populateIndex();
          }
        }.bind(this));
    }
  },

  checkKeywords: function(row) {
    console.log(row);
    if (this.keywords == "") return true;
    return (row.toLowerCase().indexOf(this.keywords) != -1);
  },

  setKeywordFilter: function() {
    var k = $('#srch-term').val();
    console.log(k);
    this.keywords = k.toLowerCase();
    this.populateIndex();
  },

  selectRule: function(id) {
    this.curRule = id;
    this.populateIndex();
    this.populateForm(id);
  },

  populateIndex: function() {
    var output = '';
    var found = false;
    for (var key in this.rules) {
      key = this.rules[key];
      var htm = "";
      var myClass = "";
      if (this.checkKeywords(key[0])) {
        found = true;
        if (key == this.curRule) myClass = ' active';
        htm = replaceAll(this.itemHTML, "$name", key).replace("$name", key)
          .replace("$class", myClass);
      }
      output += htm;
    }
    if (found == false) output = "<h1>No Matches found</h1>";
    $("#sidebar").html(output);
  },

  populateForm: function(id) {
    $.post(this.webSvcBase, {
      "getRule": id
    }).done(function(data) {
      data = JSON.parse(data);
      for (var key in data) {
        $("#rule_" + key).val(data[key]);
      }
    }.bind(this));
  },

  saveItem: function() {
    name = $("#rule_name").val();
    this.rules[id] = {};
    for (var key in this.rule_schema) {
      this.rules[id][key] = $("#itm_" + key).val();
    }
    this.curRule = id;
    this.populateIndex();
    $.post("./hotlist", {
        "set": JSON.stringify(this.rules[id])
      })
      .done(function(data) {
        if (data.indexOf("Success") == -1) {
          alert("Error occured while saving" + data);
        }
      });

  },

  /**
   * Opens a modal to edit a task.
   *
   * @param id string
   *      A name for aHandler, for use in error messages. If omitted, we use
   */
  doTaskModal: function(id) {
    var task = this.getTask(id);
    for (var k in this.taskKeys) {
      var key = this.taskKeys[k];
      $("#task_" + key).val(replaceAll(task[key], "\\n", "\n"));
    }
    if (task.id == "") $("#task_id").val(id);
    $("#myModal").modal('show');
  }
};

function pleaseWait(id) {
  $("#" + id).html(
    '<center>' +
    '<h3> one moment.....</h3>' +
    '<img src="img/hex-loader2.gif">' +
    '</center>');
}

function Clear() {
  $("#genSearch").val("");
  $('#stationList').html('');
}


function postexample() {
  pleaseWait("results");
  $.post(correctionsBase, payload, function(data) {
    $("#results").html('<pre>' + data +
      '</pre><center> <button class="btn btn-primary"' +
      'onclick="refreshResults()">OK</button></center>');
  });
}


//============================Chart===========================

function newChart(proj, _title, _data, _units, _yaxis) {
  $("#container").empty();
  chart = Highcharts.stockChart('container', {
    rangeSelector: {
      selected: 3
    },

    title: {
      text: proj + _title
    },
    yAxis: [{ // Primary yAxis
      labels: {
        format: '{value} ' + _units,
        style: {
          color: Highcharts.getOptions().colors[1]
        }
      },
      title: {
        text: _yaxis,
        style: {
          color: Highcharts.getOptions().colors[1]
        }
      },
      opposite: true
    }],
    series: [{
      name: proj,
      data: _data,
      tooltip: {
        valueDecimals: 2
      },
      point: {
        cursor: 'pointer',
        events: {
          click: function(e) {
            powerhouse_status(proj, Highcharts.dateFormat(
              '%Y-%m-%d %H:%M:%S', this.x));
          }
        },
      },
    }]
  });

}

function FOPChart(proj) {
  pleaseWait('container');
  $.getJSON('../webexec/service?getFOPSpill=' + proj, function(data) {
    newChart(proj, ' FOP Spill', data, "kcfs", "Flow");
    /*
    $.getJSON('../webexec/service?getFOP=' + proj, function (data) {
      console.log(proj);
      chart.addSeries({
        name: 'Raw FOP',
        data: data,
        tooltip: {
          valueDecimals: 2
        }
      });
    }); */
    $.getJSON('../webexec/service?getSTP=' + proj, function(data) {
      console.log(proj);
      chart.addSeries({
        name: 'STP',
        data: data,
        tooltip: {
          valueDecimals: 2
        }
      });
    });
    $.getJSON('../webexec/service?getSTPAvail=' + proj, function(data) {
      console.log(proj);
      chart.addSeries({
        name: 'STP Avail Gen',
        data: data,
        tooltip: {
          valueDecimals: 2
        }
      });
    });
    $.getJSON('../webexec/service?getSimpleCapacity=' + proj, function(
      data) {
      console.log(proj);
      chart.addSeries({
        name: ' Estimated Hydraulic Capacity',
        data: data,
        tooltip: {
          valueDecimals: 2
        }
      });
    });
  });
}

function STPChart(proj) {
  pleaseWait('container');
  $.getJSON('../webexec/service?getSimpleCapacity=' + proj, function(data) {
    newChart(proj, ' Estimated Hydraulic Capacity', data, "kcfs", "Flow");
    $.getJSON('../webexec/service?getSTP=' + proj, function(data) {
      console.log(proj);
      chart.addSeries({
        name: 'STP',
        data: data,
        tooltip: {
          valueDecimals: 2
        }
      });
    });
  });
}


function simpleCapacityChart(proj) {
  pleaseWait('container');
  $.getJSON('../webexec/service?getSimpleCapacity=' + proj, function(data) {
    newChart(proj, ' Estimated Hydraulic Capacity', data, "kcfs", "Flow");
  });
}

function unitAvailablityChart(proj) {
  pleaseWait('container');
  $.getJSON('../webexec/service?getTotalAvailability=' + proj, function(data) {
    newChart(proj, ' Unit Availibilty', data, "Units", "");
  });
}

function powerhouse_status(proj, dt) {
  pleaseWait('powerhouse_status');
  $.getJSON('../webexec/service?getProjectOutages={"proj":"' + proj +
    '", "datetime":"' + dt + '"}',
    function(data) {
      output = '<table class="table table-striped"><thead><tr>';
      for (var key in data) {
        color = 'success';
        if (data[key] < 1) color = "warning";
        if (data[key] < 0.01) color = "danger";
        output += '<th class="table-' + color + '">Unit ' + key + '</th>';
      }
      output += '</tr></thead></table>';
      $('#powerhouse_status').html(output);
    });
}

//============================Helper functions===========================

function formatTimeNumber(n) {
  output = n + "";
  if (n <= 9)
    output = "0" + output;
  return output;
}

function isNumeric(n) {
  return !isNaN(parseFloat(n)) && isFinite(n);
}

function replaceAll(str, stringToFind, stringToReplace) {
  var index = str.indexOf(stringToFind);
  while (index != -1) {
    str = str.replace(stringToFind, stringToReplace);
    index = str.indexOf(stringToFind);
  }
  return str;
}

/*
 ** Add-on to JQuery that reads url parameters into an associative array.
 */

$.extend({
  getUrlVars: function() {
    var vars = [],
      hash;
    var hashes = window.location.href.slice(
      window.location.href.indexOf('?') + 1).split('&');
    for (var i = 0; i < hashes.length; i++) {
      hash = hashes[i].split('=');
      vars.push(hash[0]);
      vars[hash[0]] = hash[1];
    }
    return vars;
  },
  getUrlVar: function(name) {
    return $.getUrlVars()[name];
  }
});

