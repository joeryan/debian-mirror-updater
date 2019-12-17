# debian-mirror-updater
Debian based (APT) repository mirror update script

## description
This application gets the release file from remote APT repo and checks
if it is newer than the last recorded update time or if it should make a 
recurring snapshot.  If so:
- update aptly mirror
- create and publish a new aptly snapshot
- optionally, sync to remote filesystem using rsync

## Dependencies:
- as listed in requirements.txt
- aptly software installed locally configured for the user running the updater
- rysnc if remote filesystem sync is desired
