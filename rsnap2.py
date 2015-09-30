#!/usr/bin/env python3
"""
rsync nas backups
"""

import argparse
import datetime
import operator
import os
import re
import shlex
import subprocess


class RsyncBackuper:
    def __init__(self, root, rsync_args):
        assert os.path.isabs(root)
        self.root = root
        self.rsync_args = rsync_args
        self.dests = self._list_previous_dests()

    def backup(self, src):

        dest = RsyncBackuperDest.new(self.root)
        previous_backup = None
        if len(self.dests) > 0:
            previous_backup = next((x for x in self.dests if x.is_complete), None)

        rsync_call = ["rsync", src, dest.path]
        rsync_call += self.rsync_args
        if previous_backup is not None:
            rsync_call += ["--link-dest", previous_backup.path]

        print("issuing:", " ".join([shlex.quote(x) for x in rsync_call]))
        print("---")
        rsync_ret = subprocess.call(rsync_call)
        if rsync_ret != 0:
            raise Exception("rsync failed!")

        dest.complete()

    def _list_previous_dests(self):
        previous_dests = []

        root_subdirs = [child for child in os.listdir(self.root) if os.path.isdir(os.path.join(self.root, child))]
        for root_subdir in root_subdirs:
            dest = RsyncBackuperDest.parse(root_subdir, self.root)

            if dest is not None:
                previous_dests.append(dest)

        previous_dests.sort(key=operator.attrgetter("time"), reverse=True)

        return previous_dests


class RsyncBackuperDest:
    DEST_DIR_FORMAT = "{time}{dotflag}"
    DEST_DIR_DATE_FORMAT = "%Y-%m-%d_%H-%M-%S.%f"
    DEST_DIR_RE = re.compile(r"^(?P<time>\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2}.\d{6})(?P<flag>\.partial)?$")

    def __init__(self, dirname, root, time, is_complete):
        self.dirname = dirname
        self.root = root
        self.time = time
        self.is_complete = is_complete

    @property
    def path(self):
        return os.path.join(self.root, self.dirname)

    def complete(self):
        path_old = self.path

        self.is_complete = True
        self.dirname = self._get_dirname(self.time)
        path_new = self.path

        os.rename(path_old, path_new)

    @classmethod
    def parse(cls, dirname, root):
        match = cls.DEST_DIR_RE.match(dirname)
        if match is None:
            return None

        time = datetime.datetime.strptime(match.group("time"), cls.DEST_DIR_DATE_FORMAT)

        flag = match.group("flag")
        is_complete = flag is None

        return cls(dirname=dirname, root=root, time=time, is_complete=is_complete)

    @classmethod
    def new(cls, root):
        time = datetime.datetime.now()
        dirname = cls._get_dirname(time, "partial")

        return cls(dirname=dirname, root=root, time=time, is_complete=False)

    @classmethod
    def _get_dirname(cls, time, flag=None):
        return cls.DEST_DIR_FORMAT.format(
            time=time.strftime(cls.DEST_DIR_DATE_FORMAT),
            dotflag="" if flag is None else ".{}".format(flag)
        )



if __name__ == "__main__":
    args_parser = argparse.ArgumentParser(description="rsync nas backups")
    args_parser.add_argument("source")
    args_parser.add_argument("root")
    args_parser.add_argument("--rsync-args", nargs=argparse.REMAINDER, default=["-a", "-v"])
    args = args_parser.parse_args()

    if True in (arg.startswith("--link-dest") for arg in args.rsync_args):
        raise ValueError("--link-dest cannot be overwritten in --rsync-args")

    root = os.path.abspath(args.root)
    if not os.path.exists(root) or not os.path.isdir(root):
        raise ValueError("no such dir: {0}".format(args.root))

    backuper = RsyncBackuper(root, args.rsync_args)
    backuper.backup(args.source)