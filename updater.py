#!/usr/bin/python3
# script to update aptly mirrors of debian repositories
# repositories must support standard release file
# usage: python3 updater.py [-c|--config configfile.json]
# TODO: add more robust logging
# TODO: add better error handling
# TODO: modify check_if_update_required for variable recurring updates
# TODO: allow optional unstable repos in addition to stable

from datetime import datetime as dt
from os import path
import subprocess
import json
import logging
import requests
import sys
import time


def check_if_update_required(branch, last_update):
    update_required = False
    logging.info("checking {br} branch for updates since {upd} UTC".format(br=branch, upd=last_update))
    if last_update.day < dt.today().day:
        logging.info("first snapshot of the day, update of {branch} required".format(branch=branch))
        update_required = True
    else:
        for repo in branch['repos']:
            if check_snapshot_update_time(repo, last_update): 
                update_required = True
                logging.debug("update found for {repo}".format(repo=repo))
                break
    return update_required


def check_snapshot_update_time(repo, last_update):
    logging.info("checking {dist} for updates".format(dist=repo['dist']))
    try:
        debian_release_url = options['repo_base_url'] + "debian/dists/{}/Release".format(repo['dist'])
        release_latest = requests.get(debian_release_url)
    except:
        logging.error("Unexpected error occurred:", sys.exc_info()[0])
        raise
    if not release_latest.status_code == 200:
        logging.error("Failure status code received: {stat}, {txt}".format(stat=release_latest.status_code,
                        txt=release_latest.text))
        sys.exit(100)
    for line in release_latest.text.split("\n"):
        # print(line)
        if "Date:" in line:
            release_timestamp = line.split(',')[1].strip() # format 8 Nov 2019 15:04:51 UTC
            remote_updated = dt.strptime(release_timestamp, "%d %b %Y %H:%M:%S %Z")
            
    if  remote_updated > last_update:
        logging.debug("new update for {dist}/{br}: {upd_time} UTC".format(dist=repo['dist'], br=repo['branch'], upd_time=remote_updated))
        return True
    return False


# read config or last update
def read_last_update(filename):
    logging.debug("reading last update time from {fn}".format(fn=filename))
    #logging.debug('reading last update datetime')
    if path.exists(filename):
        with open(filename) as f:
            try:
                last_update = dt.strptime(f.read().strip(), options['dt_format'])
            except:
                logging.error("Unexpected error:", sys.exc_info()[0])
                raise
    else:
        last_update = dt(1970,1,1,0,0,0)
    return last_update


def set_last_update(filename, last_update):
    logging.debug("setting last update time in {fn} to current update time {upd} UTC".format(fn=filename, upd=last_update))
    with open(filename, 'w') as f:
        f.write(last_update.strftime(options['dt_format']))


# update snapshots and publish
def update_snapshots(branch, snapshot_datetime, passphrase):
    logging.info("udating the following repos: {}".format(branch))
    for branch_dist in branch['repos']:
        repo = "{mirror}-{branch}-{dist}".format(
                mirror=branch_dist['mirror'], branch=branch_dist['branch'], dist=branch_dist['dist']
            )
        snapshot = "{}-{}".format(repo, snapshot_datetime.strftime("%Y%m%d%H%M")) 
        logging.info("updating {repo} with snapshot {snapshot}".format(repo = repo, snapshot = snapshot
        ))
        subprocess.run(["/usr/bin/aptly", "mirror", "update", repo])
        subprocess.run(["/usr/bin/aptly", "snapshot", "create", snapshot,
        "from", "mirror", repo])
        subprocess.run(["/usr/bin/aptly", "publish", "switch", "-component={br}".format(br=branch_dist['branch']), "-gpg-provider=internal", 
                "-passphrase={}".format(passphrase), branch_dist['dist'], branch['publish_endpoint'], snapshot])


def rsync_call_to_bash(sync_required):
    source = path.join(options['local_repo_root'], options['branches']['stable']['publish_endpoint'])
    if sync_required:
        logging.info("rsync from {source} to {ep} started".format(source=source, ep=options['stable_remote']))
        subprocess.run(["/usr/bin/rsync", "-av", "--delete", source, options['stable_remote']])


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('-c','--config', help="configuration file to use", action='store')
    parser.add_argument('-l','--logging', help="logging level to use (info, debug, warn, error) default is info", action='store')
    parser.add_argument('-p','--passphrase', help="passphrase to unlock aptly repo signing key", action='store')
    args = parser.parse_args()

    if args.config:
        config_file = args.config
    else:
        config_file = 'config.json'
    with open(config_file, 'r') as f:
            options = json.load(f)
    # set up logging
    if args.logging:
        log_level = getattr(logging, args.logging.upper())
    else:
        log_level = logging.INFO
    if not isinstance(log_level, int):
        raise ValueError('Invalid log level: %s' % log_level)
    else:
        logging.basicConfig(filename=options['log_path'], level=log_level, format='%(asctime)s %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
    current_datetime = dt.now()
    current_utc = dt.utcnow()
    sync_required = {branch:False for branch in options['branches'].keys()}
    logging.info("update cycle started, checking for update on {}".format(options['branches']))
    for branch_name, branch_details in options['branches'].items():
        update_file = path.join(options['file_path'], "{}/{}-update-{}.date".format(options['file_path'],branch_details['mirror'],
                                branch_name))
        last_update = read_last_update(update_file)
        if check_if_update_required(branch_details, last_update):
            update_snapshots(branch_details, current_datetime, args.passphrase)
            sync_required[branch_name] = True
            set_last_update(update_file, current_utc)
    rsync_call_to_bash(sync_required)
        
    logging.info("update cycle complete, updated {}".format(sync_required))