check-sr-lag
============

Graphite feed and Nagios check in one!

The script connects to given host and checks the state of the given replication
cluster; then depending on desiered output either submits the data to target
carbon server or spits out status in NRPE format.

Requires:
- repmgrd to be up and running on standbys
- psycopg2

You should be performing those checks against standby servers and not master
one.

