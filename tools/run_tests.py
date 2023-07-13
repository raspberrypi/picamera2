#!/usr/bin/python3

import argparse
import os
import subprocess
import sys
import time

# Execute this script with no arguments to run all the tests listed in the
# tests/test-list.txt file. It prints out whether each test passes, fails,
# seems to contain an error in its output, or times out. The return code
# is the number of non-passing tests, so the value zero indicates that
# everything passed.
#
# New tests are welcome. Where possible these should be placed in the tests
# folder and should be self-checking, returning a non-zero exit code if they
# are deemed to have failed.
#
# The script assumes the Picamera2 code is in /home/pi/picamera2, the list
# of tests to run is in tests/test_list.txt below that. The tests run in
# the folder /home/pi/picamera2_tests where temporary files can be created,
# and which are deleted before each test starts. These locations can be
# altered with the options:
#
# -d - folder for temporary files where the tests run (default /home/pi/picamera2_tests)
# -p - location where the picamera2 repository has been cloned (default /home/pi/picamera2)
# -t - file listing tests to be run (default tests/test_list.txt)
#
# Within the test list file, entries should be one per line and give the
# location under the picamera2 folder. Any individual test must take less
# than 30 seconds, otherwise they will be deemed to have timed out.
# Any line starting with # is ignored. The special value EOL is also
# recognised, which stops the reading of any further tests from the file.


def load_test_list(test_list_file, picamera2_dir):
    tests = []
    with open(test_list_file, 'r') as f:
        for test in f:
            test = test.strip()
            if test == "EOL":
                break
            elif not test.startswith('#'):
                tests.append(os.path.join(picamera2_dir, test))
    return tests


def clean_directory():
    cwd = os.getcwd()
    for f in os.listdir(cwd):
        os.remove(os.path.join(cwd, f))


def indent(text, num_spaces=4):
    between = "\n" + " " * num_spaces
    return between.join(text.splitlines()) + "\n"


def print_subprocess_output(exc: subprocess.CalledProcessError):
    if exc.stdout is not None:
        print("=" * 20 + "    STDOUT    " + "=" * 20)
        print(indent(exc.stdout.decode('utf-8')))

    if exc.stderr is not None:
        print("=" * 20 + "    STDERR    " + "=" * 20)
        print(indent(exc.stderr.decode('utf-8')))


def run_tests(tests, xserver=True):
    """Run all the given tests. Return the number that fail."""
    if not xserver:
        vt = 1
    else:
        vt = 7
    if os.system(f"sudo chvt {vt}") != 0:
        print("FAILED to switch VT")
        return len(tests)
    time.sleep(3)
    num_failed = 0
    for test in tests:
        clean_directory()
        print("Running ", test, "... ", sep='', end='', flush=True)
        try:
            output = subprocess.check_output(['python3', test], timeout=90, stderr=subprocess.STDOUT)
            output = output.decode('utf-8')
            output = output.split('\n')
            test_passed = True
            test_skipped = False
            for line in output:
                line = line.lower()
                if "test pattern modes" in line:  # libcamera spits out a bogus error here
                    pass
                elif "qxcbconnection" in line:  # this can come out when running headless
                    pass
                elif "xdg_runtime_dir" in line:  # this one too when running on behalf of GitHub
                    pass
                elif "unable to set controls" in line:  # currently provoked by multi camera tests
                    pass
                elif "skipped" in line:  # allow tests to report that they aren't doing anything
                    test_skipped = True
                elif "error" in line:
                    print("\tERROR")
                    print("\t", line)
                    test_passed = False
                    num_failed = num_failed + 1
                    break
            if test_passed:
                print("\tSKIPPED" if test_skipped else "\tPASSED")
        except subprocess.CalledProcessError as e:
            print("\tFAILED")
            print_subprocess_output(e)
            num_failed = num_failed + 1
        except subprocess.TimeoutExpired as e:
            print("\tTIMED OUT")
            print_subprocess_output(e)
            num_failed = num_failed + 1
    return num_failed


def directoryexists(arg):
    if not os.path.isdir(arg):
        raise argparse.ArgumentTypeError(f"The directory {arg} doesn't exist")
    else:
        return arg


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='picamera2 automated tests')
    parser.add_argument('--dir', '-d', action='store',
                        default='/home/pi/picamera2_tests', help='Folder in which to run tests')
    parser.add_argument('--picamera2-dir', '-p', action='store', type=directoryexists,
                        default='/home/pi/picamera2', help='Location of picamera2 folder')
    parser.add_argument('--test-list-files', '-t', action='store',
                        default='test_list_drm.txt, test_list.txt',
                        help='Comma-separated list of files, each containing a list of tests to run')
    args = parser.parse_args()

    dir = args.dir
    picamera2_dir = args.picamera2_dir
    test_dir = os.path.join(picamera2_dir, "tests")
    test_list_files = [os.path.join(test_dir, file.strip()) for file in args.test_list_files.split(",")]

    print("dir:", dir)
    print("Picamera2 dir:", picamera2_dir)
    print("Test list files:", test_list_files)

    all_tests = [load_test_list(file, picamera2_dir) for file in test_list_files]

    if not os.path.exists(dir):
        os.makedirs(dir)
    os.chdir(dir)

    print("Running", sum([len(tests) for tests in all_tests]), "tests")
    print()

    num_failed = 0
    for name, tests in zip(test_list_files, all_tests):
        print("Running tests in", name)
        # There is a convention here that tests with "drm" in the name will run without X
        xserver = "drm" not in name
        num_failed += run_tests(tests, xserver=xserver)
    print()
    if num_failed == 0:
        print("ALL TESTS PASSED!")
    else:
        print(f"*** {num_failed} TEST{'S' if num_failed > 1 else ''} FAILED! ***")
    sys.exit(num_failed)
