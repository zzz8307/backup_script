import os
import sys
import time
import shutil
import hashlib
import zipfile
import argparse
import textwrap
import threading
from datetime import date

from logger import *

START_TIME = time.time()
LOGGER = Logger().getlogger()
BACKUP_NAME = "Backup-" + str(date.today())


class ArchiveCheckError(Exception):
    """ Raised when archive integrity check failed. """
    pass


class FileCheckError(Exception):
    """ Raised when file integrity check failed. """
    pass


# override error() to log the error messages
class ArgparseLogger(argparse.ArgumentParser):
    def error(self, message):
        LOGGER.error(message)
        super().error(message)


def main():
    # get what we need from command-line arguments
    try:
        src_path, dst_path, onedrive_path, onedrive_flag, dst_exists_flag = init()
    except SystemExit:
        return
    except FileNotFoundError:
        LOGGER.error("Source path doesn't exist.")
        return
    except Exception:
        LOGGER.exception("Error occurred.")
        return

    # start backup process
    LOGGER.info("Starting " + str(BACKUP_NAME))
    try:
        shutil.copytree(src_path, dst_path, ignore=_logpath, copy_function=copy3, dirs_exist_ok=dst_exists_flag)
        if onedrive_flag:
            copy_od(onedrive_path, "zip", dst_path, logger=LOGGER)
    except KeyboardInterrupt:
        LOGGER.error("Cancelled by user.")
    except FileCheckError:
        LOGGER.error("File integrity check failed.")
    except ArchiveCheckError:
        LOGGER.error("OneDrive archive integrity check failed.")
    except Exception:
        LOGGER.exception("Backup failed.")
    else:
        LOGGER.info("Finished " + str(BACKUP_NAME))


def copy3(src, dst):
    LOGGER.info("Start copying - {0}".format(src))

    # run file integrity check if dst exists.
    if os.path.exists(dst):
        LOGGER.info("File exists - {0}".format(dst))
        file_check_flag = file_check(src, dst)
        # if pass, skip copying
        if file_check_flag:
            LOGGER.info("Skipped - {0}".format(src))
            return dst

    st = time.time()

    # pg_thread for showing progress
    pg_thread = threading.Thread(name="pg_thread", target=copy3_progress, args=(src, dst))
    pg_thread.setDaemon(True)
    LOGGER.debug(pg_thread)
    pg_thread.start()
    LOGGER.debug(pg_thread)

    # copy the file
    shutil.copy2(src, dst)
    LOGGER.info("Copy completed. Time spent: {:.3f}s".format(time.time() - st))
    LOGGER.debug(pg_thread)

    # check file integrity
    file_check_flag = file_check(src, dst)
    if not file_check_flag:
        return copy3(src, dst)
    LOGGER.info("Finished - {0}".format(src))
    return dst


def copy3_progress(src, dst):
    while not os.path.exists(dst):
        time.sleep(.5)

    src_size = os.path.getsize(src)
    while (dst_size := os.path.getsize(dst)) < src_size:
        print("{:.3f}%".format(dst_size / src_size * 100), end='\r')
        time.sleep(.5)


def file_check(src, dst):
    LOGGER.info("File integrity check start.")
    cnt = 0  # count of failures

    # get files name
    fn_search = dst.split(BACKUP_NAME)
    src_filename = fn_search[-1]
    dst_filename = "\\{0}{1}".format(BACKUP_NAME, src_filename)

    src_md5 = cal_md5(src, src_filename)
    dst_md5 = cal_md5(dst, dst_filename)
    if src_md5 != dst_md5:
        if cnt > 2:
            LOGGER.error("File integrity check has reached maximum retries - {0}".format(dst_filename))
            raise FileCheckError
        cnt += 1
        LOGGER.warning("File integrity check failed {0} times, retrying...".format(cnt))
        return False
    LOGGER.info("Check passed - {0}".format(dst_filename))
    return True


def cal_md5(file, name):
    if not os.path.isfile(file):
        return
    LOGGER.debug("Calculating md5 - {0}...".format(name))
    st = time.time()

    # in order to show the progress
    s = 0
    file_size = os.path.getsize(file)

    # start checking file's md5
    with open(file, 'rb') as f:
        md5 = hashlib.md5()
        while chunk := f.read(65536):
            md5.update(chunk)
            s += 65536
            print("{:.3f}%".format(s / file_size * 100), end='\r')
    file_md5 = md5.hexdigest()
    LOGGER.debug("{0} - {1}".format(file_md5, name))
    LOGGER.info("Calculation completed. Time spent: {:.3f}s - {}".format(time.time() - st, name))
    return file_md5


def copy_od(od_path, arc_type, root_dir, logger):
    LOGGER.info("Creating archive {0} to OneDrive.".format(str(BACKUP_NAME)))

    try:
        bck_zip = shutil.make_archive(od_path, arc_type, root_dir, logger=logger)
    except Exception:
        LOGGER.exception("Error occurred.")
        return

    # check archive integrity
    archive_check_flag = archive_check(bck_zip)
    if not archive_check_flag:
        return copy_od(bck_zip)
    LOGGER.info("Archive created, let OneDrive take care of the rest!")


def archive_check(zip_filename):
    LOGGER.info("Checking the archive file...")
    cnt = 0  # count of failures
    try:
        with zipfile.ZipFile(zip_filename) as zf:
            zip_check = zf.testzip()
    except Exception:
        LOGGER.exception("Error occurred.")
    if zip_check is not None:
        if cnt > 2:
            LOGGER.error("Archive integrity check has reached maximum retries - {0}".format(zip_filename))
            raise ArchiveCheckError
        cnt += 1
        LOGGER.warning("Archive integrity check failed {0} times, retrying...".format(cnt))
        return False
    LOGGER.info("Check passed - {0}".format(zip_filename))
    return True


def init():
    LOGGER.info("Initializing...")
    LOGGER.debug(sys.argv)

    argp = ArgparseLogger(description="Backup script",
                          formatter_class=argparse.RawDescriptionHelpFormatter,
                          epilog=textwrap.dedent('''
                            For example, if you specify --src as 'C:\\srcfiles', --dst as 'D:\\dstfiles', --bckname as 'KB',
                            files in 'C:\\srcfiles' will be backup to 'D:\\dstfiles\\KB_Backup\\Backup-{0}'.
                            If --bckname is not specify, files will be backup to 'D:\\dstfiles\\Backup\\Backup-{0}'
                          '''.format(str(date.today()))))

    argp.add_argument("--bckname", default="", help="Name of your backup.", dest="bckname")
    argp.add_argument("--src", required=True, help="The path that you would like to backup.", dest="srcpath")
    argp.add_argument("--dst", required=True, help="The path that you would like to store your backup.", dest="dstpath")
    argp.add_argument("--dstexists", action="store_true", help="Specify this argument if dst exists, or an exception will be raised.", dest="dst_exists_flag")
    argp.add_argument("-o", "--onedrive", action="store_true", help="Specify this argument to backup to OneDrive (Default: False)", dest="onedrive_flag")

    args = argp.parse_args()
    LOGGER.debug(args)

    if args.bckname != "":
        global BACKUP_NAME
        BACKUP_NAME = os.path.join("{0}_Backup".format(args.bckname), BACKUP_NAME)

    src_path = args.srcpath
    dst_path = os.path.join(args.dstpath, BACKUP_NAME)
    onedrive_path = ""
    onedrive_flag = args.onedrive_flag
    dst_exists_flag = args.dst_exists_flag

    if not os.path.exists(src_path):
        raise FileNotFoundError

    if onedrive_flag:
        onedrive_env = os.getenv("onedrive")
        if onedrive_env != "":
            onedrive_path = os.path.join(onedrive_env, BACKUP_NAME)
        else:
            LOGGER.warning("Failed to get path of OneDrive, check your OneDrive installation. Skipping backup to OneDrive.")
            onedrive_flag = False

    return src_path, dst_path, onedrive_path, onedrive_flag, dst_exists_flag


def _logpath(path, names):
    LOGGER.info("Working in {0}".format(path))
    return []


if __name__ == "__main__":
    main()
    LOGGER.info("Script exit. Time spent: {:.3f}s".format(time.time() - START_TIME))
