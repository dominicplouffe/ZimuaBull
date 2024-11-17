"""
deploy.py

Usage:
    deploy.py --ip=<ip> --key=<key>
    deploy.py --ip=<ip> --key=<key> --zip-only

Example:
    deploy.py --ip=192.168.0.122 --key=~/.ssh/keys/General.pem
    deploy.py --ip=192.168.0.122 --key=~/.ssh/keys/General.pem
"""

import os
from tools import zip
from docopt import docopt
import paramiko
import time

BUILD_DIRS = ["pidash", "weather", "tools", "manage.py", "code", "requirements.txt"]

ZIP_FILENAME = "pidash.zip"


def create_zip():
    if ZIP_FILENAME in os.listdir("."):
        os.remove(ZIP_FILENAME)

    print("Packaging Files")
    utilities = zip.ZipUtilities()
    utilities.to_zip(BUILD_DIRS, ZIP_FILENAME)


def create_ssh_connection(public_ip, key_path):
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    ssh.connect(public_ip, username="domnic", key_filename=key_path)

    return ssh


def copy_code(ssh):
    print("Copying Code")
    res = ssh.exec_command("sudo /home/domnic/copy.sh")
    time.sleep(5.0)
    ssh.exec_command("sudo systemctl restart pidash")
    time.sleep(5.0)
    ssh.exec_command("sudo systemctl restart deadheatsup")
    print("Done Copying Code")


def put_file(ssh):
    print("Uploading Zip File")
    ssh.exec_command("rm -r deadheat")
    ssh.exec_command("rm %s" % ZIP_FILENAME)

    sftp = ssh.open_sftp()
    sftp.put(ZIP_FILENAME, ZIP_FILENAME)


def deploy(ip_address, key_path, zip_only=False):
    create_zip()

    print("Deploying to %s" % ip_address)
    ssh = create_ssh_connection(ip_address, key_path)
    put_file(ssh)
    if zip_only:
        return
    time.sleep(5.0)
    copy_code(ssh)


if __name__ == "__main__":
    args = docopt(__doc__)

    ip_address = args["--ip"]
    key_path = args["--key"]
    zip_only = args.get("--zip-only", False)

    if ip_address is None:
        raise Exception("Must provide a ip address type")

    if key_path is None:
        raise Exception("Must provide a key path")

    deploy(ip_address, key_path, zip_only=zip_only)
