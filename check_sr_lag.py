#!/usr/bin/env python

import sys
import time
import os, re
import platform
import subprocess
from optparse import OptionParser
import psycopg2
from socket import socket

"""
Graphite feed and Nagios check in one!

The script connects to given host and checks the state of the given replication
cluster; then depending on desiered output either submits the data to target
carbon server or spits out status in NRPE format.

Requires:
- repmgrd to be up and running on standbys
- psycopg2

You should be performing those checks against standby servers and not master
one.
"""

hostname = os.uname()[1].split('.')[0]
timestamp = int(time.time())

def graphite(hostname, time_lag, timestamp, carbonhost):
    # equivalent to timedelta.total_seconds() in python 2.7; we want just the number of seconds
    time_lag = ((time_lag.microseconds + (time_lag.seconds + time_lag.days * 24 * 3600)
            * 10**6) / 10**6)
    data = []

    data.append("servers.%s.pg_sr_time_lag %s %d" % (hostname, time_lag, timestamp))

    message = '\n'.join(data) + '\n'

    sock = socket()
    try:
        sock.connect((carbonhost, 2003)) # submit messages as plaintext so use default 2003 port
        sock.sendall(message)
        sock.close()
    except:
        print("ERROR!  Couldn't connect to carbon host on %s" % carbonhost)
        sys.exit(1)
        
def nagios(time_lag, warn, critical):
    time_lag = ((time_lag.microseconds + (time_lag.seconds + time_lag.days * 24 * 3600)
            * 10**6) / 10**6)

    if time_lag < warn:
        print("All good - timelag: %s" % time_lag)
        sys.exit(0)
    elif time_lag > warn and time_lag < critical:
        print("WARNING - timelag: %s" % time_lag)
        sys.exit(1)
    else:
        print("CRITICAL!!! timelag: %s" % time_lag )
        sys.exit(2)

def main():
    # process options and arguments
    usage = "usage: %prog [options] cluster_name"
    parser = OptionParser(usage)

    parser.add_option("-o", "--output", dest="output",
            help="output type; possible nagios, graphite",
            action="store", default="nagios")
    parser.add_option("-s", "--standby", dest="standby",
            help="standby hostname to make the checks against",
            action="store", default=hostname)
    parser.add_option("-c", "--carbonhost", dest="carbonhost",
            help="target Carbon host (only for -o == graphite)",
            action="store", default="localhost")
    parser.add_option("-n", "--nagioswarn", dest="warn",
            help="nagios warning level time lag (only for -o == nagios)",
            action="store", default=5)
    parser.add_option("-m", "--nagioscritical", dest="critical",
            help="nagios critical level time lag (only for -o == nagios)",
            action="store", default=15)
    parser.add_option("-a", "--pghost", dest="pghost",
            help="target PostgreSQL server host",
            action="store", default="localhost")
    parser.add_option("-p", "--pgport", dest="pgport",
            help="target PostgreSQL server port",
            action="store", default=5432)
    parser.add_option("-u", "--pguser", dest="pguser",
            help="target PostgreSQL username",
            action="store", default="foo")
    parser.add_option("-w", "--pgpass", dest="pgpass",
            help="target PostgreSQL user password",
            action="store", default="")
    parser.add_option("-d", "--pgdb", dest="pgdb",
            help="target PostgreSQL repmgr database",
            action="store", default="repmgr")

    (options, args) = parser.parse_args()
    if len(args) != 1:
        parser.error("You must specify cluster_name as a commandline argument!")

    # assign some sane variable names to command line arguments
    cluster = args[0]

    conn = psycopg2.connect(host=options.pghost, database=options.pgdb,
                            user=options.pguser, password=options.pgpass)
    cur = conn.cursor()
    
    # get current nodeid (default based on hostname)
    cur.execute("SELECT id FROM repmgr_%s.repl_nodes WHERE conninfo LIKE 'host=%s%%'" %
            (cluster, options.standby))
    nodeid = cur.fetchone()[0]
    
    # get time_lag
    cur.execute("SELECT time_lag FROM repmgr_%s.repl_status WHERE standby_node"
            " = %s" % (cluster, nodeid))
    time_lag = cur.fetchone()[0]
    
    if options.output == "graphite":
        graphite(options.standby, time_lag, timestamp, options.carbonhost)
    if options.output == "nagios":
        nagios(time_lag, options.warn, options.critical)

    cur.close()
    conn.close()

if __name__ == '__main__':
    main()

