#!/usr/bin/python3

import argparse
import os
import subprocess
import sys

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


def run_tests(tests):
    """Run all the given tests. Return the number that fail."""
    num_failed = 0
    for test in tests:
        clean_directory()
        print("Running ", test, "... ", sep='', end='', flush=True)
        try:
            output = subprocess.check_output(['python3', test], timeout=30, stderr=subprocess.STDOUT)
            output = output.decode('utf-8')
            output = output.split('\n')
            test_passed = True
            for line in output:
                line = line.lower()
                if "test pattern modes" in line:  # libcamera spits out a bogus error here
                    pass
                elif "qxcbconnection" in line:  # this can come out when running headless
                    pass
                elif "xdg_runtime_dir" in line:  # this one too when running on behalf of GitHub
                    pass
                elif "error" in line:
                    print("\tERROR")
                    print("\t", line)
                    test_passed = False
                    num_failed = num_failed + 1
                    break
            if test_passed:
                print("\tPASSED")
        except subprocess.CalledProcessError:
            print("\tFAILED")
            num_failed = num_failed + 1
        except subprocess.TimeoutExpired:
            print("\tTIMED OUT")
            num_failed = num_failed + 1
    return num_failed


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='picamera2 automated tests')
    parser.add_argument('--dir', '-d', action='store', default='/home/pi/picamera2_tests',
                        help='Folder in which to run tests')
    parser.add_argument('--picamera2-dir', '-p', action='store', default='/home/pi/picamera2',
                        help='Location of picamera2 folder')
    parser.add_argument('--test-list-file', '-t', action='store', default='tests/test_list.txt',
                        help='File containing list of tests to run')
    args = parser.parse_args()

    dir = args.dir
    picamera2_dir = args.picamera2_dir
    test_list_file = os.path.join(picamera2_dir, args.test_list_file)
    print("dir:", dir)
    print("Picamera2 dir:", picamera2_dir)
    print("Test list file:", test_list_file)

    tests = load_test_list(test_list_file, picamera2_dir)

    if not os.path.exists(dir):
        os.makedirs(dir)
    os.chdir(dir)

    print("Running", len(tests), "tests")
    print()
    num_failed = run_tests(tests)
    print()
    if num_failed == 0:
        print("ALL TESTS PASSED!")
    else:
        print(f"*** {num_failed} TEST{'S' if num_failed > 1 else ''} FAILED! ***")
    sys.exit(num_failed)
